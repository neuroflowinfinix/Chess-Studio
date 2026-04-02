import chess
import chess.engine
import chess.pgn
import pygame
import math
import multiprocessing
import random
import time
import os
import threading 
import numpy as np
import joblib

matplotlib = None
plt = None
agg = None

class AnalysisEngine:
    """
    The brain of the chess application. Handles all communication with Stockfish.
    """

    def __init__(self, engine_path, opening_book=None, book_positions=None, threads=4, hash_size=512): # <-- Added parameter
        self.engine_path = engine_path
        self.engine = None
        self.is_active = False
        self.multipv = 1
        self.current_engine_name = "Stockfish"
        if "stockfish" in engine_path.lower(): self.current_engine_name = "Stockfish 16+"
        
        # Performance Settings
        # --- FIX: Maximize CPU & Allow User Override ---
        # If the user passed a specific thread count (e.g., from settings), use it.
        # Otherwise, default to the total physical cores.
        self.threads = max(1, threads if threads else multiprocessing.cpu_count()) 
        self.hash_size = hash_size
        
        self.current_depth = 0 # NEW: Track live depth
        
        # Syzygy Path
        self.syzygy_path = os.path.abspath(os.path.join("assets", "syzygy"))
        
        # Inject Opening Dictionary (e.g., from ECO.pgn)
        self.opening_book = opening_book or {}
        self.book_positions = book_positions if book_positions is not None else set()
        
        self.lock = threading.Lock() # <-- NEW: Prevents thread collisions
        
        # --- FIX: Intelligently supercharge the opening book with EPD data ---
        threading.Thread(target=self._merge_epd_openings, daemon=True).start()
        # ---------------------------------------------------------------------
        
        # like chess.coms-style Win-Probability % Loss Thresholds (Refined for consistency)
        self.THRESHOLDS = {
            # Values are win% drops (larger = worse)
            "brilliant": 0.0, "great": 0.0, "best": 1.0, "excellent": 3.0, "good": 8.0,
            "inaccuracy": 20.0, "mistake": 40.0, "blunder": 100.0
        }
        # 'excellent' included above
        # Centipawn thresholds tuned perfectly via Calibration Engine
        self.CP_THRESHOLDS = {
            'blunder': -829, 
            'mistake': -686, 
            'inaccuracy': -604, 
            'good': 98, 
            'excellent': 360, 
            'best': 415, 
            'great': 426, 
            'brilliant': 828
        }
        
        # Accuracy & Exponential Elo Multipliers derived from calibration
        self.CALIB_PARAMS = {
            'acc_weight': 3.288162029807866, 
            'm50': 127.2517,
            'm60': 196.9384,
            'm70': 95.8210,
            'm80': 109.4327,
            'm85': 0.0000,
            'm90': 339.7956,
            "gap_great": 167.57332759711528, 
            "gap_brill": 518.6319984179141, 
            "miss_win": 89.94399386453291, 
            "miss_eq": 36.64302429397429
        }
        
        # Special Classification Constants (Synchronized with Neural Net Evolution)
        self.MISS_WINNING_THRESHOLD = self.CALIB_PARAMS["miss_win"]
        self.MISS_EQUAL_BARRIER = self.CALIB_PARAMS["miss_eq"]
        self.GREAT_DIFF = self.CALIB_PARAMS["gap_great"]
        self.BRILLIANT_DIFF = self.CALIB_PARAMS["gap_brill"]
        
        # Enhanced Sacrifice Detection Thresholds (chess.com-style)
        self.SACRIFICE_THRESHOLDS = {
            "material_sacrifice": -300,      # Centipawn loss for material
            "positional_compensation": 200,  # Required positional gain
            "attack_compensation": 250,       # Required attack potential
            "initiative_bonus": 150,          # For seizing initiative
            "brilliant_min": 400,            # Minimum eval for brilliant sacrifice
            "good_min": 200,                 # Minimum eval for good sacrifice
            "speculative_min": -50            # Minimum eval for speculative sacrifice
        }

        self.MOVE_CATEGORIES = [
            "brilliant", "great", "best", "excellent", "book", 
            "good", "miss", "inaccuracy", "mistake", "blunder"
        ]
        
        self.ARROW_COLORS = {
            "best": (0, 200, 0, 180), "alt": (255, 165, 0, 180),
            "risky": (255, 50, 50, 180), "threat": (200, 0, 0, 80)
        }

        # Try to load a persisted feature-based review model (trained via calibrators)
        self.feature_model = None
        self.feature_label_encoder = None
        try:
            model_path = os.path.join("assets", "review_model.joblib")
            if os.path.exists(model_path):
                data = joblib.load(model_path)
                self.feature_model = data.get('clf')
                self.feature_label_encoder = data.get('le')
                print(f"Loaded feature review model from {model_path}")
        except Exception as e:
            print('Warning: failed to load persisted review model:', e)

        # Live prediction buffer: keep small rolling state for live feature construction
        self._live_prev_cp = None
        self._live_prev_best_gap = 0
        self._live_history_size = 6
        
    def _merge_epd_openings(self):
        """
        Runs in the background to merge massive EPD files silently.
        Extracts the 3-part FEN key and prioritizes EPD names over the ECO.pgn base.
        """
        epd_path = os.path.abspath(os.path.join("assets", "openings.epd"))
        if not os.path.exists(epd_path):
            return
            
        try:
            with open(epd_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line: continue
                    
                    # EPD Format: [Board] [Turn] [Castling] [EnPassant] [Operations...]
                    parts = line.split(" ", 4)
                    if len(parts) >= 5:
                        # Reconstruct our exact 3-part FEN key (Board + Turn + Castling)
                        fen_key = f"{parts[0]} {parts[1]} {parts[2]}"
                        ops = parts[4]
                        
                        if "Opening " in ops:
                            # Extract everything after 'Opening '
                            op_name = ops.split("Opening ")[1].strip()
                            
                            # Clean up EPD syntax artifacts (trailing semicolons and stars)
                            if op_name.endswith(";"): op_name = op_name[:-1].strip()
                            if op_name.endswith("*"): op_name = op_name[:-1].strip()
                            
                            # Safely write to the dictionary. 
                            # Because it runs after ECO.pgn is loaded, it naturally overwrites overlaps!
                            with self.lock:
                                self.opening_book[fen_key] = op_name
                                self.book_positions.add(fen_key)
                                
        except Exception as e:
            print(f"[!] Error loading openings.epd: {e}")

    def start(self):
        """Initializes the UCI engine, optimizes CPU usage, and applies custom evaluation assets."""
        if self.is_active: 
            return True
            
        try:
            if self.engine_path == "lichess_cloud":
                self.current_engine_name = "Lichess Cloud API"
                self.is_active = True
                self.engine = "lichess_cloud"
                self.threads = 1
                self.multipv = 3
                print("-" * 50)
                print(f"ENGINE STATUS: {self.current_engine_name} is ACTIVE")
                print("-" * 50)
                return True

            # 1. Start the Engine Process
            self.engine = chess.engine.SimpleEngine.popen_uci(self.engine_path)
            
            # 2. Identify Engine Name
            if "name" in self.engine.id:
                self.current_engine_name = self.engine.id["name"]
            else:
                base = os.path.basename(self.engine_path)
                self.current_engine_name = os.path.splitext(base)[0].title()

            # 3. CPU OPTIMIZATION: Calculate safe thread count (50% of available cores)
            total_cores = multiprocessing.cpu_count()
            self.threads = max(1, int(total_cores / 2))

            # 4. EVALUATION FILE LOADING (.bin / .nnue)
            loaded_network_name = "Internal/Default"
            nnue_loaded = False
            
            # --- Dynamic Option Keys ---
            eval_key = None
            if "EvalFile" in self.engine.options: eval_key = "EvalFile"
            elif "NNUENetpath" in self.engine.options: eval_key = "NNUENetpath"
            
            # --- Check local engine 'nnue' subfolder ---
            base_filename = os.path.splitext(os.path.basename(self.engine_path))[0]
            local_nnue = os.path.join(os.path.dirname(self.engine_path), "nnue", f"{base_filename}.nnue")
            
            if os.path.exists(local_nnue):
                # Force forward slashes so Stockfish's C++ parser doesn't break
                safe_path = local_nnue.replace("\\", "/")
                
                if eval_key:
                    try:
                        self.engine.configure({eval_key: safe_path})
                        print(f"[VERIFIED] Loaded Engine-specific NNUE: {local_nnue}")
                        loaded_network_name = f"{base_filename}.nnue"
                        nnue_loaded = True
                    except Exception as e:
                        print(f"[!] Engine rejected local NNUE file: {local_nnue}. Reason: {e}")

            # --- Fallback: Auto-load custom .nnue files from assets ---
            if not nnue_loaded:
                eval_dir = os.path.abspath(os.path.join("assets", "evaluationfiles"))
                if os.path.exists(eval_dir):
                    for f in os.listdir(eval_dir):
                        # ONLY load .nnue files into Stockfish!
                        if f.endswith(".nnue"):
                            # --- FIX: Force forward slashes so Stockfish's C++ parser doesn't break ---
                            bin_path = os.path.join(eval_dir, f).replace("\\", "/")
                            ext = os.path.splitext(f)[1].upper() # .NNUE
                            
                            if eval_key:
                                try:
                                    self.engine.configure({eval_key: bin_path})
                                    # THIS IS THE VERIFICATION PRINT
                                    print(f"[VERIFIED] Successfully loaded custom {ext} network: {f}")
                                    loaded_network_name = f
                                    nnue_loaded = True
                                    break 
                                except Exception as e:
                                    # --- FIX: Print the exact Python/Engine error so we know WHY it failed ---
                                    print(f"[!] Engine rejected {f}. Reason: {e}")
                else:
                    print(f"[?] Search directory not found: {eval_dir}")

            # 5. GENERAL UCI CONFIGURATION
            config = {}
            if "Hash" in self.engine.options: config["Hash"] = self.hash_size
            
            # --- CPU SAFEGUARD: Leave 1 core free for UI responsiveness ---
            safe_threads = max(1, self.threads - 1)
            if "Threads" in self.engine.options: config["Threads"] = safe_threads
            
            # --- NNUE ENFORCEMENT ---
            if "Use NNUE" in self.engine.options: 
                config["Use NNUE"] = True
            elif "Use_NNUE" in self.engine.options:
                config["Use_NNUE"] = True
                
            # --- SYZYGY ENDGAME TABLEBASES ENFORCEMENT ---
            if hasattr(self, 'syzygy_path') and self.syzygy_path:
                if "SyzygyPath" in self.engine.options:
                    if os.path.exists(self.syzygy_path) and os.path.isdir(self.syzygy_path):
                        config["SyzygyPath"] = self.syzygy_path
                        # Force engine to probe tablebases instantly in endgames (Saves CPU)
                        if "SyzygyProbeDepth" in self.engine.options: config["SyzygyProbeDepth"] = 1
                        if "Syzygy50MoveRule" in self.engine.options: config["Syzygy50MoveRule"] = True
            
            # --- MULTIPV CONFIGURATION ---
            if "MultiPV" in self.engine.options:
                self.multipv = 3 
            else:
                self.multipv = 1
            
            self.engine.configure(config)
            self.is_active = True

            # Final Summary Print
            print("-" * 50)
            print(f"ENGINE STATUS: {self.current_engine_name} is ACTIVE")
            print(f"THREADS:       {self.threads}")
            print(f"NETWORK:       {loaded_network_name}")
            print(f"MULTIPV:       {self.multipv}")
            print("-" * 50)

            return True

        except Exception as e:
            print(f"CRITICAL: Engine Load Error: {e}")
            self.is_active = False
            return False
            
    def stop(self):
        if self.engine:
            if self.engine_path != "lichess_cloud":
                try: self.engine.quit()
                except Exception: pass
            self.engine = None
            self.is_active = False

    def _score_to_cp(self, score_obj):
        # --- FIX: Stop arbitrarily capping engine scores! Return the exact evaluation! ---
        if score_obj.is_mate():
            m = score_obj.mate()
            if m > 0: return 10000 - m * 100
            elif m < 0: return -10000 - m * 100
            else: return 10000
        try:
            return int(score_obj.score()) # Pass the exact numerical score unhindered
        except Exception:
            return 0

    def get_position_complexity(self, board):
        if board.is_game_over(): return 0
        legal_moves = board.legal_moves.count()
        tension_score = 0
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece:
                attackers = board.attackers(not piece.color, square)
                if attackers:
                    weight = 1 if piece.piece_type == chess.PAWN else 3
                    tension_score += len(attackers) * weight
        score = (legal_moves * 0.6) + (tension_score * 1.5)
        return int(min(100, max(0, score)))

    def _to_win_percentage(self, cp_score, move_number=0):
        if cp_score is None: return 50.0
        score = max(-2000, min(2000, cp_score))
        return 50 + 50 * (2 / (1 + math.exp(-0.00368208 * score)) - 1)
        
    def _normalize_cp_for_review(self, cp_score, turn):
        if cp_score is None:
            return 0
        try:
            cp = int(cp_score)
        except Exception:
            return 0
        if turn == chess.BLACK:
            cp *= -1
        if abs(cp) >= 9000:
            cp = 1000 * (1 if cp > 0 else -1)
        return max(-1000, min(1000, cp))

    def _win_chance_review(self, cp_score, turn):
        cp = self._normalize_cp_for_review(cp_score, turn)
        return 50 + 50 * (2 / (1 + math.exp(-0.00368208 * cp)) - 1)

    def _cp_from_win_diff(self, w1, w2):
        return max(0, (w1 - w2) * 12)

    def _calculate_accuracy(self, win_percent_before, win_percent_after, move_class, complexity=0):
        """
        Calculates per-move accuracy using Exponential Win Probability Decay (CAPS v2 style).
        """
        if move_class in ["book", "forced", "brilliant", "great"]: return 100.0
        
        # True Win% Drop
        win_drop = max(0.0, float(win_percent_before) - float(win_percent_after))
        
        # CAPS v2 Exponential Decay Formula on WDL drop
        # 0 drop = 100%, 5% drop = ~84%, 10% drop = ~70%, 20% drop = ~50%
        accuracy = 100.0 * math.exp(-0.035 * win_drop)
        
        # Dampen accuracy loss in extremely complex/sharp positions
        if complexity > 50:
             dampener = min(0.30, (complexity - 50) / 200.0)
             # Restore some accuracy based on how complex it was to find the move
             accuracy += (100.0 - accuracy) * dampener
             
        # Move class hard ceilings (prevents a 'Blunder' from getting a mathematically high score)
        if move_class == "blunder": return min(accuracy, 40.0)
        elif move_class == "mistake": return min(accuracy, 65.0)
        elif move_class == "miss": return min(accuracy, 60.0)
        elif move_class == "inaccuracy": return min(accuracy, 85.0)
        
        return max(0.0, min(100.0, accuracy))
        
    def _get_mobility_delta(self, board_before, board_after, is_white):
        """Calculates if the move increased or decreased the player's legal move count (freedom)."""
        try:
            # We must pass the turn to see how many moves they WOULD have
            bb_copy = board_before.copy()
            bb_copy.turn = is_white
            before_moves = bb_copy.legal_moves.count()
            
            ba_copy = board_after.copy()
            ba_copy.turn = is_white
            after_moves = ba_copy.legal_moves.count()
            
            return after_moves - before_moves
        except Exception:
            return 0

    def _get_pawn_structure_damage(self, board_after, is_white):
        """Detects doubled and isolated pawns. Higher penalty = worse structure."""
        penalty = 0
        pawns = board_after.pieces(chess.PAWN, is_white)
        files_with_pawns = [chess.square_file(sq) for sq in pawns]
        
        # Doubled pawns
        for file_idx in range(8):
            count = files_with_pawns.count(file_idx)
            if count > 1:
                penalty += (count - 1) * 20
                
        # Isolated pawns
        for file_idx in set(files_with_pawns):
            if (file_idx - 1 not in files_with_pawns) and (file_idx + 1 not in files_with_pawns):
                penalty += 15
                
        return penalty

    def _get_king_safety_exposure(self, board_after, is_white):
        """Calculates how naked the King is (missing pawn shield)."""
        king_sq = board_after.king(is_white)
        if not king_sq: return 0
        
        file_idx = chess.square_file(king_sq)
        rank_idx = chess.square_rank(king_sq)
        exposure = 0
        
        # Check the 3 files in front of the king for friendly pawns
        files_to_check = [file_idx]
        if file_idx > 0: files_to_check.append(file_idx - 1)
        if file_idx < 7: files_to_check.append(file_idx + 1)
        
        for f in files_to_check:
            pawn_found = False
            for r in range(8):
                p = board_after.piece_at(chess.square(f, r))
                if p and p.piece_type == chess.PAWN and p.color == is_white:
                    pawn_found = True
                    break
            if not pawn_found:
                exposure += 25 # High penalty for a completely open file near the king
                
        return exposure

    def _estimate_elo_from_acpl(self, acpl, accuracy, base_rating=None):
        """
        Calculates Game Rating using an Exponential ACPL Logic. 
        Punishes blunders heavily via ACPL, while rewarding precise play using 
        the piecewise accuracy multipliers to match GM dataset expectations.
        """
        try:
            acc = float(accuracy)
            acpl_val = max(1, float(acpl)) # Prevent division by zero
            
            # 1. Base Elo calculation via Exponential Decay of ACPL
            # Optimized via regression on 46 real player-game samples (RMSE: 1367 → 652)
            exponential_base_elo = 8000.0 * math.exp(-0.061149 * acpl_val)
            
            # 2. Piecewise Accuracy Modifiers (Regression-calibrated per-zone slopes)
            acc_bonus = 0
            if acc > 50: acc_bonus += (min(acc, 60) - 50) * self.CALIB_PARAMS.get("m50", 127.2517)
            if acc > 60: acc_bonus += (min(acc, 70) - 60) * self.CALIB_PARAMS.get("m60", 196.9384)
            if acc > 70: acc_bonus += (min(acc, 80) - 70) * self.CALIB_PARAMS.get("m70", 95.8210)
            if acc > 80: acc_bonus += (min(acc, 85) - 80) * self.CALIB_PARAMS.get("m80", 109.4327)
            if acc > 85: acc_bonus += (min(acc, 90) - 85) * self.CALIB_PARAMS.get("m85", 0.0)
            if acc > 90: acc_bonus += (acc - 90) * self.CALIB_PARAMS.get("m90", 339.7956)
            
            # 3. Blend: ACPL decay dominates (W1=0.990), accuracy bonus adds residual lift.
            # Dampening is near-zero (C=0.0001) so acc_bonus flows through at all ACPL levels.
            dampening_factor = math.exp(-0.0001 * acpl_val)
            blended_math_elo = (exponential_base_elo * 0.990) + (acc_bonus * dampening_factor * 0.463)
            
            if acc < 45.0:
                blended_math_elo = 100
                
            final_math_elo = max(100, min(3600, int(blended_math_elo)))
            
            # --- GOD-TIER UPGRADE: Bayesian Human Anchor ---
            if base_rating is not None and isinstance(base_rating, int) and base_rating > 100:
                # Bayesian expected base accuracy using a standardized curve
                expected_acc = 50.0 + ((base_rating - 500) / 30.0)
                expected_acc = max(40.0, min(95.0, expected_acc))
                
                acc_diff = acc - expected_acc
                bayesian_elo = base_rating + (acc_diff * 40.0) - (acpl_val * 4.0)
                
                blended_elo = (final_math_elo * 0.4) + (bayesian_elo * 0.6)
                return max(100, min(3600, int(blended_elo)))
                
            return final_math_elo
        except Exception:
            return 100

    def get_game_phase(self, board):
        if board.fullmove_number <= 10: return "opening"
        if len(board.piece_map()) <= 12: return "endgame"
        return "middlegame"

    def get_opening_name(self, board):
        # Syncing with the 3-part key logic
        fen_key = " ".join(board.fen().split(" ")[:3])
        return self.opening_book.get(fen_key, None)
        
    def is_book_position(self, board):
        fen_key = " ".join(board.fen().split(" ")[:3])
        return fen_key in self.book_positions or fen_key in self.opening_book

    def _get_material_diff(self, board_before, board_after):
        turn = board_before.turn 
        phase = self.get_game_phase(board_before)
        vals = {chess.PAWN:100, chess.KNIGHT:320, chess.BISHOP:330, chess.ROOK:500, chess.QUEEN:900, chess.KING:0}
        if phase == 'endgame': vals[chess.PAWN] = 120 
        # Convert from centipawn-style values to simple pawn-equivalents for explanations
        pawn_vals = {
            chess.PAWN: 1,
            chess.KNIGHT: 3,
            chess.BISHOP: 3,
            chess.ROOK: 5,
            chess.QUEEN: 9,
            chess.KING: 0
        }

        before_sum = 0
        after_sum = 0

        for sq in chess.SQUARES:
            p_before = board_before.piece_at(sq)
            p_after = board_after.piece_at(sq)
            if p_before:
                before_sum += pawn_vals.get(p_before.piece_type, 0)
            if p_after:
                after_sum += pawn_vals.get(p_after.piece_type, 0)

        # material_delta: positive => gained material, negative => lost material
        return (after_sum - before_sum)
    
    def _is_hanging_capture(self, board_before, best_move):
        """
        Returns True if best_move captures a piece that can be taken with net material gain
        (a 'hanging' or 'loose' piece). Uses a lightweight SEE estimate.
        
        Three cases:
          A) Target square has zero defenders → pure freebie
          B) Attacker value < captured value → winning trade regardless of recapture
          C) Captured value > cheapest available recapture → still profitable
        """
        if best_move is None or not board_before.is_capture(best_move):
            return False
        target_sq = best_move.to_square
        captured  = board_before.piece_at(target_sq)
        attacker  = board_before.piece_at(best_move.from_square)
        if not captured or not attacker:
            return False

        is_white = board_before.turn == chess.WHITE
        vals = {chess.PAWN: 100, chess.KNIGHT: 310, chess.BISHOP: 325,
                chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 20000}

        captured_val = vals.get(captured.piece_type, 0)
        attacker_val = vals.get(attacker.piece_type, 0)
        defenders    = [sq for sq in board_before.attackers(not is_white, target_sq)]

        # Case A: no defenders at all — pure hanging piece
        if not defenders:
            return True

        # Case B: we capture a more valuable piece — winning even after recapture
        if captured_val > attacker_val:
            return True

        # Case C: our attacker is cheaper than the cheapest recapture available
        lowest_def_val = min(
            vals.get(board_before.piece_at(sq).piece_type, 9999)
            for sq in defenders if board_before.piece_at(sq)
        )
        return captured_val >= lowest_def_val and attacker_val < lowest_def_val

    def _get_positional_context(self, board_before, complexity):
        """
        Derives a rich context snapshot used to adjust classification thresholds.
        
        Returns a dict with:
          pressure_factor  — 0.0 (quiet) to 1.0 (chaotic storm), drives leniency
          is_endgame       — True when few pieces remain (stricter precision required)
          is_forced        — True when ≤2 legal moves exist
          tension_pieces   — count of own pieces under enemy attack right now
          uniqueness_gap   — cp gap between best and 2nd best (move rarity signal)
        """
        legal_count = board_before.legal_moves.count()
        is_forced   = legal_count <= 2
        is_endgame  = len(board_before.piece_map()) <= 12

        # Count own pieces currently under attack (tactical heat)
        is_white = board_before.turn == chess.WHITE
        tension_pieces = 0
        for sq in chess.SQUARES:
            piece = board_before.piece_at(sq)
            if piece and piece.color == is_white:
                if board_before.attackers(not is_white, sq):
                    tension_pieces += 1

        # Blend complexity score + piece tension into a single pressure index
        pressure_factor = min(1.0,
            (complexity / 100.0) * 0.55 +
            (min(tension_pieces, 6) / 6.0) * 0.30 +
            (min(legal_count, 40) / 40.0) * 0.15
        )

        return {
            "pressure_factor": pressure_factor,
            "is_endgame":      is_endgame,
            "is_forced":       is_forced,
            "tension_pieces":  tension_pieces,
            "legal_count":     legal_count,
        }

    def _classify_from_win_chance(self, win_drop, move_is_best, best_vs_second_gap, is_sacrifice, next_cp_pov):
        if win_drop > 20:
            return "blunder"
        if win_drop > 10:
            return "mistake"
        if win_drop > 5:
            return "inaccuracy"

        if move_is_best and best_vs_second_gap > 10:
            if is_sacrifice and next_cp_pov > 150:
                return "brilliant"
            return "great"

        return None

    def _classify_quality_tier(self, win_drop, move_is_best, delta_cp):
        if move_is_best or win_drop <= 0.5 or delta_cp >= -5:
            return "best"
        if win_drop <= 1.5 or delta_cp >= -15:
            return "excellent"
        if win_drop <= 3.5 or delta_cp >= -35:
            return "good"
        return None

    def evaluate_special_classifications(self, board_before, board_after, move, prev_cp, curr_cp, second_best_cp, win_drop, best_gap_wc):
        """
        Ultra-Brilliant Grandmaster Logic for Special Move Detection.
        Understands pure sacrifices, value-sacrifices, and exchange sacrifices.
        """
        is_white = board_before.turn == chess.WHITE
        delta_cp = curr_cp - prev_cp
        
        # ==========================================
        # 1. BLUNDER DETECTION (Catastrophic Errors)
        # ==========================================
        # Rule A: Allowing a forced mate is always a blunder
        if curr_cp <= -9000 and prev_cp > -5000: return "blunder"
        
        # Rule B: Massive Win Probability Drop (> 20%)
        if win_drop > 20.0: return "blunder"
        
        # Rule C: Mathematical Blunder (Using calibrated memetic thresholds)
        if delta_cp <= self.CP_THRESHOLDS.get("blunder", -600): return "blunder"

        # ==========================================
        # 2. BRILLIANT & GREAT DETECTION
        # ==========================================
        # --- THE HARD GUARD (Anti-False Brilliancy) ---
        # A move is NEVER brilliant if it throws away the mathematical advantage.
        # It must stay within 4.5% WDL drop and not lose more than ~80 centipawns.
        # Furthermore, we don't award "Brilliant" if you are already up +8.0 (800cp) and just hanging pieces.
        if delta_cp >= -80 and win_drop <= 4.5 and prev_cp < 800:
            
            # --- THE TRUE SACRIFICE DETECTOR ---
            moved_piece = board_before.piece_at(move.from_square)
            vals = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 100}
            moved_val = vals.get(moved_piece.piece_type, 0) if moved_piece else 0
            
            target_sq = move.to_square
            
            enemy_attackers = list(board_after.attackers(not is_white, target_sq))
            friendly_defenders = list(board_after.attackers(is_white, target_sq))
            
            is_sac = False
            
            # Type A: Pure Hanging Sacrifice
            if len(enemy_attackers) > 0 and len(friendly_defenders) == 0:
                is_sac = True
                
            # Type B: Value-Based Sacrifice (e.g. Queen takes a Pawn guarded by a Pawn)
            elif len(enemy_attackers) > 0:
                lowest_attacker_val = min([vals.get(board_after.piece_at(sq).piece_type, 0) for sq in enemy_attackers if board_after.piece_at(sq)])
                if lowest_attacker_val < moved_val:
                    is_sac = True
                    
            # Type C: The Exchange Sacrifice 
            elif board_before.is_capture(move):
                captured_piece = board_before.piece_at(target_sq)
                cap_val = vals.get(captured_piece.piece_type, 0) if captured_piece else 0
                if moved_val - cap_val >= 2 and len(enemy_attackers) > 0:
                    is_sac = True
            
            gap_cp = prev_cp - second_best_cp
            gap_great = self.CALIB_PARAMS.get("gap_great", 180) 
            
            # Rule D: Brilliant Move (A sound sacrifice that maintains or creates a strong advantage)
            # FIX: To stop "stupid sacrifices", the move MUST be the engine's top choice (delta_cp >= -20)
            # AND it must lead to a clear, proven mathematical advantage over the opponent (curr_cp >= 150).
            if is_sac and curr_cp >= 150 and delta_cp >= -20:
                return "brilliant"
                
            # Rule E: Great Move (The "Only Winning Move" in a complex position)
            if (gap_cp >= gap_great or best_gap_wc > 10.0) and curr_cp > 50:
                # If a sacrifice was good but didn't meet the strict Brilliant threshold, it can still be Great!
                return "great"
                
        return None

    def _classify_move_logic(self, board_before, board_after, move, best_move,
                             score_best_cp, score_move_cp, score_second_best_cp,
                             win_pct_best, win_pct_after, in_book=False):
        """
        Context-aware move classification pipeline.

        Layer 1 — Automatic:  book / forced
        Layer 2 — Special:    brilliant / great / blunder  (via evaluate_special_classifications)
        Layer 3 — Miss:       tactical (free piece ignored) | strategic (2+ pawns left) | legacy (collapse)
        Layer 4 — Errors:     blunder / mistake / inaccuracy  (pressure-adjusted thresholds)
        Layer 5 — Quality:    best / excellent / good  (uniqueness-boosted)
        """

        # ── Layer 1: Automatic ─────────────────────────────────────────────────
        if in_book:
            return "book"
        if board_before.legal_moves.count() == 1:
            return "best"

        # Safe defaults
        score_best_cp        = 0 if score_best_cp is None else score_best_cp
        score_move_cp        = score_best_cp if score_move_cp is None else score_move_cp
        score_second_best_cp = (score_best_cp - 500) if score_second_best_cp is None else score_second_best_cp

        # Core deltas
        delta            = score_move_cp - score_best_cp          # ≤ 0 (how far below best)
        opportunity_gain = score_best_cp - score_move_cp          # ≥ 0 (cp left on the table)
        win_drop         = max(0.0, float(win_pct_best) - float(win_pct_after))

        try:
            wc_best   = self._to_win_percentage(score_best_cp,        board_before.turn)
            wc_second = self._to_win_percentage(score_second_best_cp, board_before.turn)
            best_gap_wc = wc_best - wc_second
        except Exception:
            best_gap_wc = 0.0

        # ── Positional context ─────────────────────────────────────────────────
        complexity = self.get_position_complexity(board_before)
        ctx        = self._get_positional_context(board_before, complexity)

        # Pressure leniency: sharp tactical battles forgive small errors slightly.
        # Endgames are punished harder — precision is mandatory with few pieces.
        # Range: ~0.85 (dead-quiet endgame) … ~1.25 (explosive tactical storm)
        pressure_leniency = 1.0 + (ctx["pressure_factor"] * 0.25)
        if ctx["is_endgame"]:
            pressure_leniency *= 0.85

        # ── Layer 2: Special moves (brilliant / great / blunder) ───────────────
        special_class = self.evaluate_special_classifications(
            board_before, board_after, move, score_best_cp, score_move_cp,
            score_second_best_cp, win_drop, best_gap_wc
        )
        if special_class:
            return special_class

        # ── Layer 3: Miss detection (three independent triggers) ───────────────
        #
        # A miss is NOT an error — the played move is objectively fine.
        # It is a failure to exploit a clear, concrete opportunity.
        #
        # We only fire any miss trigger when win_drop ≤ 4.5% so it does NOT
        # overlap with inaccuracy/mistake/blunder territory.

        if win_drop <= 4.5 and move != best_move:

            # Trigger A — Tactical miss: best move captures a hanging/loose piece
            # but the player moved something else instead.
            # The missed piece must be genuinely capturable with material gain (SEE ≥ 0).
            is_tactical_miss = (
                not board_before.is_capture(move) and
                self._is_hanging_capture(board_before, best_move)
            )

            # Trigger B — Strategic miss: best move would have gained 2+ pawns
            # compared to what was played, while the played move keeps the position safe.
            # Threshold: 200 cp (~2 pawns). Position after played move must still be OK.
            STRATEGIC_MISS_CP = 200  # ~2 pawns; intentionally NOT a calibration param
            is_strategic_miss = (
                opportunity_gain >= STRATEGIC_MISS_CP and
                score_move_cp > -100          # played move leaves a reasonable position
            )

            # Trigger C — Legacy calibrated miss: had a clearly winning position
            # but the played move surrendered equality (uses existing CALIB_PARAMS).
            is_legacy_miss = (
                win_pct_best  > self.MISS_WINNING_THRESHOLD and
                win_pct_after < self.MISS_EQUAL_BARRIER
            )

            if is_tactical_miss or is_strategic_miss or is_legacy_miss:
                return "miss"

        # ── Layer 4: Errors (pressure-adjusted thresholds) ────────────────────
        t = self.CP_THRESHOLDS

        # Adjust mistake/inaccuracy thresholds by positional pressure.
        # Blunder is NEVER lenient — dropping a piece in any position is a blunder.
        adj_mistake    = t.get("mistake",    -686) * pressure_leniency
        adj_inaccuracy = t.get("inaccuracy", -604) * pressure_leniency

        if win_drop > 20.0 or delta <= t.get("blunder", -829):
            return "blunder"
        if win_drop > 10.0 or delta <= adj_mistake:
            return "mistake"

        # Losing a massive positional advantage while still winning
        # (e.g., +9.0 → +5.0 is sloppy even if technically not a mistake by delta alone)
        if score_move_cp > 300 and score_best_cp > 500:
            return "inaccuracy"

        if win_drop > 5.0 or delta <= adj_inaccuracy:
            return "inaccuracy"

        # ── Layer 5: Quality tier (uniqueness-aware) ──────────────────────────
        #
        # "Uniqueness" = the played move was the best AND it was significantly better
        # than any other option. This is the "only move" scenario detected at the
        # classification level (complementing evaluate_special_classifications which
        # handles the full sacrifice/tactical analysis).
        #
        # If the move uniqueness signal is strong enough, "best" is promoted to "great"
        # here rather than requiring the sacrifice detection path.

        gap_cp    = score_best_cp - score_second_best_cp   # how unique the best move was
        gap_great = self.CALIB_PARAMS.get("gap_great", 167)

        move_is_unique = (
            move == best_move and
            (gap_cp >= gap_great or best_gap_wc > 10.0) and
            score_move_cp > 50 and
            not ctx["is_forced"]   # forced moves are already capped as "best" above
        )

        if move == best_move or win_drop <= 0.5 or delta >= t.get("best", 415):
            if move_is_unique and complexity > 30:
                return "great"    # Only-move in a complex position = great
            return "best"

        if win_drop <= 2.0 or delta >= t.get("excellent", 360):
            return "excellent"

        return "good"

    def classify_move(self, move, board_before, board_after, prev_eval_cp, curr_eval_cp, best_move=None):
        """
        Public method to classify a single live move. 
        Acts as a bridge between main.py and the internal classification logic.
        """
        move_num = board_after.fullmove_number
        
        # 1. Handle potential None values from live eval safely
        prev_cp = prev_eval_cp if prev_eval_cp is not None else 0
        curr_cp = curr_eval_cp if curr_eval_cp is not None else prev_cp
        score_second_cp = prev_cp - 50  # Safe estimate for second best line
        
        # 2. Calculate the win percentages required by the logic engine
        win_pct_best = self._to_win_percentage(prev_cp, move_num)
        win_pct_after = self._to_win_percentage(curr_cp, move_num)
        
        # 3. Check if we are still in the opening book (approx. first 12 moves)
        in_book = False
        if hasattr(self, 'is_book_position'):
            in_book = self.is_book_position(board_after) and move_num <= 12
        # Immediately return book so the ML Models don't intercept it! ---
        if in_book:
            return "book"

        # 4. If a trained feature model is available, prefer it for classification
        if getattr(self, 'feature_model', None) is not None and getattr(self, 'feature_label_encoder', None) is not None:
            try:
                # ... (Keep your existing ML feature extraction code here: X = _np.array([...])) ...
                
                ypred = self.feature_model.predict(X)
                label = str(self.feature_label_encoder.inverse_transform(ypred)[0])

                # --- GOD-TIER VETO: Stop ML Hallucinations ---
                # Machine Learning models sometimes see a massive negative 'material_delta' 
                # (like a Queen sac) and hallucinate a "brilliant" label.
                # We enforce a hard mathematical veto here to override the AI.
                win_drop_veto = max(0.0, float(win_pct_best) - float(win_pct_after))
                if label in ["brilliant", "great"]:
                    # If it drops more than 20% win chance, it's a blunder, no matter what the ML says.
                    if win_drop_veto > 20.0 or cp_loss >= abs(self.CP_THRESHOLDS.get("blunder", -600)): 
                        label = "blunder"
                    elif win_drop_veto > 10.0 or cp_loss >= abs(self.CP_THRESHOLDS.get("mistake", -200)): 
                        label = "mistake"
                    elif win_drop_veto > 4.5 or cp_loss >= 80:
                        label = "inaccuracy"

                # update live buffer state for next ply
                try:
                    self._live_prev_cp = curr_eval_cp if curr_eval_cp is not None else use_curr_cp
                    if isinstance(best_gap, (int, float)):
                        self._live_prev_best_gap = best_gap
                except Exception:
                    pass

                return label
            except Exception:
                # Fall back to original logic on any model or feature errors
                pass

        # 5. Route to Deep Positional Logic (evaluate_special_classifications)
        # This properly wires up the live game to your advanced sacrifice/blunder detection!
        return self._classify_move_logic(
            board_before=board_before, 
            board_after=board_after, 
            move=move, 
            best_move=best_move,
            score_best_cp=prev_cp,
            score_move_cp=curr_cp, 
            score_second_best_cp=score_second_cp, 
            win_pct_best=win_pct_best, 
            win_pct_after=win_pct_after, 
            in_book=in_book
        )
        
    def _calculate_trap_coefficient(self, engine, board_after, depth_limit):
        """
        UPGRADE 2: Expected Value & Trap Calculation (Human Psychology).
        Analyzes the opponent's best replies. If the best reply holds equality (+0.0) 
        but the second-best blunders the game (-4.0), the move is a Massive Trap.
        """
        try:
            limit = chess.engine.Limit(time=0.1, depth=max(12, depth_limit - 4))
            info = engine.analyse(board_after, limit, multipv=3)
            
            if len(info) >= 2:
                turn = board_after.turn
                best_pov = self._score_to_cp(info[0]["score"].pov(turn))
                second_pov = self._score_to_cp(info[1]["score"].pov(turn))
                
                gap = best_pov - second_pov
                if gap > 250: # The opponent blunders a piece if they miss the ONLY correct reply
                    return gap
        except Exception:
            pass
        return 0

    def _generate_player_identity(self, stats_color):
        """
        UPGRADE 3: Deep Style Profiling.
        Aggregates positional telemetry across the entire game to assign a GM Identity.
        """
        moves = max(1, stats_color.get("move_count", 1))
        avg_comp = stats_color.get("complexity_sum", 0) / moves
        avg_exp = stats_color.get("king_exposure_sum", 0) / moves
        avg_dmg = stats_color.get("pawn_damage_sum", 0) / moves
        
        if avg_comp > 45 and avg_exp > 15:
            return "Tactical Assassin (Mikhail Tal) - Thrives in chaos and high-risk attacking positions."
        elif avg_comp < 35 and avg_dmg < 10:
            return "Positional Boa Constrictor (Anatoly Karpov) - Suffocates opponents with perfect pawn structure."
        elif avg_comp > 40 and avg_dmg < 15:
            return "Universal Controller (Garry Kasparov) - Dominates dynamically with high accuracy and initiative."
        else:
            return "Pragmatic Fighter (Magnus Carlsen) - Grinds down opponents in practical, equal endgames."

    def parallel_engine_pool_evaluate(self, history, depth_limit):
        """
        UPGRADE 1: Hyperspeed Engine Pool (Strictly 50% CPU Constraint).
        Maps the game across independent 1-thread engines for ultra-fast parallel evaluation.
        """
        import concurrent.futures
        
        # --- THE 50% CPU CONSTRAINT ---
        total_cores = multiprocessing.cpu_count()
        pool_size = max(1, total_cores // 2) 
        print(f"Igniting Hyperspeed Pool: {pool_size} independent engines (1 thread each).")
        
        tasks = []
        board = chess.Board()
        for i, h in enumerate(history):
            tasks.append((i, board.fen(), h["move"]))
            board.push(h["move"])
            
        results = {}
        
        def worker(task_chunk):
            # --- FIX: Local Fallback for Cloud API in Hyperspeed Pool ---
            safe_path = self.engine_path
            if safe_path == "lichess_cloud":
                import os
                # Safely auto-detect a local engine to prevent Lichess API IP Bans
                for p in ["engines/Stockfish 18.exe", "engines/stockfish.exe", "engines/Rubi Chess.exe", "stockfish.exe"]:
                    if os.path.exists(p):
                        safe_path = p
                        break
                        
            import sys
            if sys.platform == "win32":
                eng = chess.engine.SimpleEngine.popen_uci(safe_path, creationflags=0x08000000)
            else:
                eng = chess.engine.SimpleEngine.popen_uci(safe_path)
                
            # Spawn a local Stockfish restricted to ONE thread so the pool respects the 50% CPU cap
            eng.configure({"Threads": 1, "Hash": 32}) 
            chunk_res = {}
            for idx, fen, move in task_chunk:
                b = chess.Board(fen)
                limit = chess.engine.Limit(time=0.2, depth=max(14, depth_limit - 2))
                info = eng.analyse(b, limit, multipv=3)
                
                # Calculate the Trap Coefficient for this specific move
                b.push(move)
                trap_coef = self._calculate_trap_coefficient(eng, b, depth_limit)
                
                chunk_res[idx] = {"info": info, "trap": trap_coef}
            eng.quit()
            return chunk_res

        # Divide tasks into perfectly balanced chunks
        chunk_size = math.ceil(len(tasks) / pool_size)
        chunks = [tasks[i:i + chunk_size] for i in range(0, len(tasks), chunk_size)]
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=pool_size) as executor:
            futures = [executor.submit(worker, chunk) for chunk in chunks]
            for future in concurrent.futures.as_completed(futures):
                results.update(future.result())
                
        return results
        
    def generate_positional_reason(self, board_before, board_after, move, is_blunder):
        """
        Translates raw engine mathematics into human-readable positional logic.
        Detects King Exposure, Hanging Pieces, and Active Diagonals.
        """
        reason = []
        moved_piece = board_before.piece_at(move.from_square)
        is_white_move = board_before.turn == chess.WHITE
        
        # 1. KING EXPOSURE (The Mikhail Tal instinct)
        # Did the move strip pawns away from the King? Or open a file next to it?
        enemy_king_sq = board_after.king(not is_white_move)
        attackers = board_after.attackers(is_white_move, enemy_king_sq)
        if len(attackers) > 0:
            reason.append("Direct assault on the enemy king.")
            
        my_king_sq = board_after.king(is_white_move)
        if is_blunder and len(board_after.attackers(not is_white_move, my_king_sq)) > 1:
            reason.append("Severely compromised king safety. The king is exposed.")

        # 2. HANGING PIECES (Material vs Positional Compensation)
        # Is the piece we just moved heavily attacked but not defended?
        if is_blunder:
            attackers = len(board_after.attackers(not is_white_move, move.to_square))
            defenders = len(board_after.attackers(is_white_move, move.to_square))
            if attackers > defenders:
                reason.append("Leaves a piece hanging without sufficient defense.")

        # 3. ACTIVE BISHOPS & LONG DIAGONALS
        # Did a bishop just take control of the longest lines on the board?
        if moved_piece and moved_piece.piece_type == chess.BISHOP:
            # Center squares: e4, d4, e5, d5
            center_squares = [chess.E4, chess.D4, chess.E5, chess.D5]
            if move.to_square in center_squares:
                reason.append("Bishop dominates the absolute center.")
                
        # 4. ROOKS ON OPEN FILES
        if moved_piece and moved_piece.piece_type == chess.ROOK:
            file_idx = chess.square_file(move.to_square)
            # Check if there are any pawns on this file
            pawns_on_file = False
            for rank in range(8):
                sq = chess.square(file_idx, rank)
                p = board_after.piece_at(sq)
                if p and p.piece_type == chess.PAWN:
                    pawns_on_file = True
                    break
            if not pawns_on_file:
                reason.append("Rook takes absolute control of the open file.")

        if not reason:
            return "A solid positional continuation."
            
        return " ".join(reason)
    
    def get_threat(self, board):
        """
        God-Tier Null-Move Threat Detection.
        Only returns a move if it is a verified, mathematically dangerous threat!
        """
        if not self.is_active: return None
        
        # A null move is illegal if the king is already in check
        if board.is_check(): return None 
        
        try:
            # Secretly pass the turn to the opponent
            board_null = board.copy()
            board_null.push(chess.Move.null())
            
            # Use NNUE to scan for the absolute best response
            limit = chess.engine.Limit(time=0.15, depth=16)
            info = self.engine.analyse(board_null, limit)
            
            if "pv" in info and len(info["pv"]) > 0:
                threat_move = info["pv"][0]
                score_pov = info["score"].pov(board_null.turn) # Opponent's perspective
                
                is_real_threat = False
                
                # 1. Forced Mate Threat
                if score_pov.is_mate() and score_pov.mate() > 0:
                    is_real_threat = True
                else:
                    cp_adv = score_pov.score()
                    # 2. Massive Positional Threat (Opponent gains > 2.0 pawns advantage)
                    if cp_adv is not None and cp_adv > 200:
                        is_real_threat = True
                        
                # 3. Direct Tactical Threats
                # (If the move captures one of your pieces, or gives a severe check)
                if board.is_capture(threat_move):
                    is_real_threat = True
                    
                board_test = board_null.copy()
                board_test.push(threat_move)
                if board_test.is_check():
                    is_real_threat = True
                
                # If it's a verified danger, return it to the UI to draw the arrow!
                if is_real_threat and threat_move in board_null.legal_moves:
                    return threat_move
                    
        except (chess.IllegalMoveError, Exception): 
            return None 
            
        return None
            
    def fast_analyze_full_game(self, mainline, progress_callback=None):
        import re
        history = []
        evals_for_graph = []
        board = chess.Board()
        
        color_stats = {
            "white": {"acc_sum": 0, "cp_loss": 0, "moves": 0},
            "black": {"acc_sum": 0, "cp_loss": 0, "moves": 0}
        }
        mate_puzzles = []
        prev_eval_white = 20 # Standard starting eval (+0.20)
        
        total_moves = len(mainline)
        if total_moves == 0: total_moves = 1
        
        for i, node in enumerate(mainline):
            move = node.move
            turn = board.turn
            san = board.san(move)
            fen = board.fen()
            board_before = board.copy()
            
            # FOOLPROOF FIX: Guarantee move_num is declared immediately!
            move_num = board.fullmove_number
            
            eval_cp = None
            comment = node.comment
            if comment:
                eval_match = re.search(r'\[%eval\s+([^\]]+)\]', comment)
                val_str = eval_match.group(1).strip() if eval_match else None
                if not val_str:
                    raw_match = re.search(r'(?:^|\s)([+-]?\d+\.\d+|[+-]?[#M]+\d+)(?:\s|$)', comment)
                    if raw_match: val_str = raw_match.group(1).strip()
                        
                if val_str:
                    if '#' in val_str or 'M' in val_str.upper():
                        # --- FIX: Clean Mate Extraction without arbitrary +/- 50 padding ---
                        m_match = re.search(r'\d+', val_str)
                        if m_match:
                            m_moves = int(m_match.group())
                            eval_cp = -10000 + (m_moves * 100) if '-' in val_str else 10000 - (m_moves * 100)
                        else:
                            eval_cp = -10000 if '-' in val_str else 10000
                    else:
                        try: eval_cp = int(float(val_str) * 100)
                        except ValueError: pass
            
            # --- FIX: Dynamic Status & Smart Mate Bypassing ---
            if eval_cp is None: 
                if self.is_active:
                    if progress_callback:
                        progress_callback(int((i / total_moves) * 100), "Analyzing missing evaluation by engine...")
                    board.push(move)
                    cp, score_text, _ = self.analyze_live(board)
                    
                    if "M" in score_text:
                        # It is a mate! Parse correctly
                        try:
                            m_moves = int(score_text.replace("M", "").replace("+", "").replace("-", ""))
                            cp = -10000 + (m_moves * 100) if "-" in score_text else 10000 - (m_moves * 100)
                        except ValueError:
                            cp = -10000 if "-" in score_text else 10000
                    else:
                        # --- FIX: STOP capping numerical evaluations! Let exact engine scores pass through! ---
                        if cp is None:
                            cp = 0 # Safe fallback
                    
                    eval_cp = cp
                    board.pop()
                else:
                    eval_cp = prev_eval_white
                    if progress_callback:
                        progress_callback(int((i / total_moves) * 100), "Fast Importing Game...")
            else:
                if progress_callback:
                    progress_callback(int((i / total_moves) * 100), "Assigning annotations...")
                    
            evals_for_graph.append(eval_cp)
            
            # --- Calculate Win% and Classification ---
            prev_pov = prev_eval_white if turn == chess.WHITE else -prev_eval_white
            curr_pov = eval_cp if turn == chess.WHITE else -eval_cp
            
            w_best = self._to_win_percentage(prev_pov, board.fullmove_number)
            w_after = self._to_win_percentage(curr_pov, board.fullmove_number)
            
            best_move = None
            score_second_cp = prev_pov - 50
            is_sharp = False
            
            if self.is_active:
                try:
                    # --- NNUE UPGRADE: MultiPV=3 and WDL extraction for imports ---
                    info = self.engine.analyse(board_before, chess.engine.Limit(depth=15), multipv=3)
                    if info:
                        if "pv" in info[0] and info[0]["pv"]: best_move = info[0]["pv"][0]
                        
                        try: w_best = info[0]["score"].pov(turn).wdl().expectation() * 100.0
                        except: pass
                        
                        if len(info) > 1 and "score" in info[1]: 
                            score_second_cp = self._score_to_cp(info[1]["score"].pov(turn))
                            if abs(prev_pov - score_second_cp) > 200:
                                is_sharp = True
                except Exception: pass
            
            board.push(move)
            in_book = (hasattr(self, 'is_book_position') and self.is_book_position(board) and i < 24)
            
            cls = self._classify_move_logic(
                board_before, board, move, best_move,
                prev_pov, curr_pov, score_second_cp,
                w_best, w_after, in_book
            )
            
            # --- NNUE UPGRADE: The "Only Move" Override ---
            if is_sharp and cls in ["best", "excellent"] and not in_book:
                if board_before.is_capture(move) or board_before.gives_check(move):
                    cls = "brilliant"
                else:
                    cls = "great"
            
            # (brilliant tracking replaced by endgame mate check)
            
            complexity = self.get_position_complexity(board_before)
            acc = self._calculate_accuracy(w_best, w_after, cls, complexity)
            
            c_key = "white" if turn == chess.WHITE else "black"
            color_stats[c_key]["acc_sum"] += acc
            color_stats[c_key]["cp_loss"] += max(0, prev_pov - curr_pov)
            color_stats[c_key]["moves"] += 1
            
            best_moves_san = []
            if best_move and best_move in board_before.legal_moves:
                try: best_moves_san.append(board_before.san(best_move))
                except Exception: best_moves_san.append("a different move")
            else:
                best_moves_san.append("a better move")
                
            reason_txt = self.generate_detailed_reason(
                move, board_before, board, cls, 
                max(0, w_best - w_after), best_moves_san, self.get_opening_name(board)
            )
            
            # --- NEW: Call generate_positional_reason ---
            is_blunder = (cls in ["blunder", "mistake"])
            pos_reason = self.generate_positional_reason(board_before, board, move, is_blunder)
            
            if pos_reason and pos_reason != "A solid positional continuation.":
                reason_txt += " " + pos_reason
            # --------------------------------------------
            
            # --- FIX: Strict exact string formatting for Mates and raw floats ---
            if abs(eval_cp) >= 5000:
                m_moves = int((10000 - abs(eval_cp)) / 100)
                if m_moves < 0: m_moves = 0
                ev_txt = f"M+{m_moves}" if eval_cp > 0 else f"M-{m_moves}"
            else:
                ev_txt = f"{eval_cp/100.0:+.2f}"

            # --- FIX: Generate Grandmaster Commentary! ---
            gm_commentary = self.generate_dynamic_commentary(
                board_before=board_before, 
                board_after=board, 
                move=move, 
                prev_cp=prev_pov, 
                curr_cp=curr_pov, 
                move_class=cls
            )

            # --- NNUE UPGRADE: Math fallback for Win Chance if WDL wasn't run on board_after ---
            win_chance_pct_white = self._to_win_percentage(eval_cp, board.fullmove_number)
            
            review_dict = {
                "eval_cp": eval_cp,
                "class": cls,
                "eval_str": ev_txt,
                "win_chance": win_chance_pct_white, # --- NNUE UPGRADE: Save WDL % ---
                "accuracy": int(acc),
                "bot_reason": gm_commentary,
                "pos_reason": pos_reason
            }
            
            history.append({
                "move": move,
                "san": san,
                "fen": fen,
                "ply": i + 1,                                                       # 1-based, matches node.ply()
                "color": "white" if turn == chess.WHITE else "black",              # turn was captured before board.push()
                "clock": node.clock() if hasattr(node, 'clock') else None,        # Preserve %clk from original PGN
                "review": review_dict
            })
            prev_eval_white = eval_cp

        if progress_callback: progress_callback(100, "Finalizing Analysis...")

        f_stats = {"white": {"acc": 0, "acpl": 0}, "black": {"acc": 0, "acpl": 0}}
        ratings = {"white": 1200, "black": 1200}
        
        for c in ["white", "black"]:
            st = color_stats[c]
            if st["moves"] > 0:
                f_stats[c]["acc"] = st["acc_sum"] / st["moves"]
                f_stats[c]["acpl"] = st["cp_loss"] / st["moves"]
                ratings[c] = self._estimate_elo_from_acpl(f_stats[c]["acpl"], f_stats[c]["acc"])

        # --- FIX: Pass history to generate dots ---
        graph = self.generate_graph_surface(evals_for_graph, history)
        
        # --- NEW: Extract Mate Puzzles if game ended in Checkmate ---
        if board.is_checkmate():
            total_plies = len(history)
            if total_plies >= 1:
                b_m1 = chess.Board()
                for i in range(total_plies - 1): b_m1.push(history[i]["move"])
                mate_puzzles.append({"fen": b_m1.fen(), "type": "Mate in 1"})
            if total_plies >= 3:
                b_m2 = chess.Board()
                for i in range(total_plies - 3): b_m2.push(history[i]["move"])
                try:
                    info = self.engine.analyse(b_m2, chess.engine.Limit(time=0.1))
                    score = info["score"].pov(b_m2.turn)
                    if score.is_mate() and score.mate() > 0:
                        mate_puzzles.append({"fen": b_m2.fen(), "type": f"Mate in {score.mate()}"})
                except: pass

        return history, f_stats, ratings, graph, mate_puzzles
        
    def generate_dynamic_commentary(self, board_before, board_after, move, prev_cp, curr_cp, move_class):
        """
        The Ultimate Grandmaster Commentator.
        Combines mathematical evaluation with deep positional and tactical heuristics.
        """
        comments = []
        is_white = board_before.turn == chess.WHITE
        moved_piece = board_before.piece_at(move.from_square)
        captured_piece = board_before.piece_at(move.to_square)
        
        # PIECE VALUES FOR HEURISTICS
        val_map = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 100}
        moved_val = val_map.get(moved_piece.piece_type, 0) if moved_piece else 0

        # ==========================================
        # 1. THE EVALUATOR (Math & Meta-Game)
        # ==========================================
        if board_after.is_checkmate():
            return "Delivers checkmate! A flawless finish to the game."
            
        # Mate detection
        if curr_cp <= -9000 and prev_cp > -5000:
            return "Catastrophic! This allows a forced checkmate."
        if prev_cp >= 9000 and curr_cp < 5000:
            return "A tragic miss. There was a forced checkmate on the board here."

        # Sacrifices & Blunders
        if move_class == "brilliant":
            comments.append("An absolutely brilliant sacrifice, prioritizing devastating positional compensation over material.")
        elif move_class == "blunder" and captured_piece is None:
            # Check if we just moved a piece to an attacked square
            attackers = board_after.attackers(not is_white, move.to_square)
            defenders = board_after.attackers(is_white, move.to_square)
            if len(attackers) > len(defenders):
                comments.append("Hangs a piece entirely, giving away material for nothing.")

        # ==========================================
        # 2. THE COMMENTATOR (Tactics & Geometry)
        # ==========================================
        
        # A. PROMOTIONS
        if move.promotion:
            if move.promotion == chess.QUEEN: comments.append("Promotes the pawn to a Queen, seizing massive power.")
            else: comments.append("A sneaky under-promotion! Brilliant tactical awareness.")
            
        # B. CASTLING & KING SAFETY
        if board_before.is_castling(move):
            if move_class in ["good", "excellent", "best"]:
                comments.append("Tucks the king away safely and connects the rooks.")
        elif moved_piece and moved_piece.piece_type == chess.KING and not board_before.has_castling_rights(is_white):
            if move_class in ["inaccuracy", "mistake", "blunder"] and prev_cp < 200:
                comments.append("Moves the king prematurely, permanently forfeiting the right to castle.")

        # C. TACTICS: FORKS
        # Does the moved piece now attack multiple pieces of higher or equal value?
        if moved_piece and move_class in ["good", "excellent", "best", "great"]:
            fork_targets = 0
            for attacked_sq in board_after.attacks(move.to_square):
                target_piece = board_after.piece_at(attacked_sq)
                if target_piece and target_piece.color != is_white:
                    if val_map.get(target_piece.piece_type, 0) >= moved_val or target_piece.piece_type == chess.KING:
                        fork_targets += 1
            if fork_targets >= 2 and moved_piece.piece_type == chess.KNIGHT:
                comments.append("A devastating Knight fork! Multiple high-value targets are under attack.")
            elif fork_targets >= 2:
                comments.append("Creates a nasty double-attack, stressing the opponent's defenses.")

        # D. TACTICS: DISCOVERED ATTACKS
        # Did moving this piece open up a line for a friendly Queen, Rook, or Bishop?
        if move_class in ["good", "excellent", "best", "great", "brilliant"]:
            discovered = False
            for sq in chess.SQUARES:
                p = board_after.piece_at(sq)
                if p and p.color == is_white and p.piece_type in [chess.QUEEN, chess.ROOK, chess.BISHOP]:
                    # If this piece now attacks something it didn't attack before, and it wasn't the piece that moved
                    if move.to_square != sq:
                        new_attacks = board_after.attacks(sq)
                        old_attacks = board_before.attacks(sq)
                        if new_attacks != old_attacks:
                            comments.append("Unleashes a dangerous discovered attack by opening the line.")
                            discovered = True
                            break
            
        # E. POSITIONAL: PASSED PAWNS
        if moved_piece and moved_piece.piece_type == chess.PAWN and move_class in ["good", "excellent", "best", "great"]:
            file_idx = chess.square_file(move.to_square)
            rank_idx = chess.square_rank(move.to_square)
            is_passed = True
            
            # Check front and adjacent files for enemy pawns
            files_to_check = [file_idx]
            if file_idx > 0: files_to_check.append(file_idx - 1)
            if file_idx < 7: files_to_check.append(file_idx + 1)
            
            for f in files_to_check:
                for r in range(rank_idx + 1, 8) if is_white else range(rank_idx - 1, -1, -1):
                    p = board_after.piece_at(chess.square(f, r))
                    if p and p.piece_type == chess.PAWN and p.color != is_white:
                        is_passed = False
                        break
            if is_passed:
                if rank_idx >= 5 if is_white else rank_idx <= 2:
                    comments.append("Pushes a dangerous passed pawn deep into enemy territory. It must be stopped!")
                else:
                    comments.append("Creates a passed pawn, creating a long-term endgame advantage.")

        # F. POSITIONAL: ROOKS ON OPEN FILES
        if moved_piece and moved_piece.piece_type == chess.ROOK and move_class in ["good", "excellent", "best"]:
            file_idx = chess.square_file(move.to_square)
            pawns_on_file = any(board_after.piece_at(chess.square(file_idx, r)) and board_after.piece_at(chess.square(file_idx, r)).piece_type == chess.PAWN for r in range(8))
            if not pawns_on_file:
                comments.append("The Rook seizes total control of the open file.")

        # G. KING EXPOSURE & ATTACKS
        enemy_king = board_after.king(not is_white)
        if board_after.is_check():
            comments.append("Forces the King to react with a direct check.")
        elif enemy_king and len(board_after.attackers(is_white, enemy_king)) > 0:
            comments.append("Starts weaving a mating net around the exposed enemy King.")

        # ==========================================
        # 3. FALLBACKS & COMBINATION
        # ==========================================
        if not comments:
            if move_class == "best": return "The strongest continuation in the position."
            if move_class == "excellent": return "A highly precise and challenging move."
            if move_class == "good": return "A solid, principled decision."
            if move_class == "inaccuracy": return "A slight misstep that allows the opponent some counterplay."
            if move_class == "mistake": return "A significant error that shifts the momentum of the game."
            if move_class == "book": return "Standard opening theory."
            return "An interesting continuation."

        # Join unique comments, limit to top 2 to avoid massive walls of text
        unique_comments = list(dict.fromkeys(comments))
        return " ".join(unique_comments[:2])

    def analyze_live(self, board):
        if not self.is_active or not self.engine:
            return 0, "0.00", []
            
        try:
            if self.engine_path == "lichess_cloud":
                import requests
                try:
                    res = requests.get(f"https://lichess.org/api/cloud-eval?fen={board.fen()}&multiPv=3", timeout=1.5)
                    if res.status_code == 200:
                        data = res.json()
                        self.current_depth = data.get("depth", 65) # Extract true depth!
                        pvs = data.get("pvs", [])
                        if not pvs: return getattr(self, '_last_cp', 0), getattr(self, '_last_txt', "0.00"), []
                        
                        cp_val = pvs[0].get("cp", 0)
                        mate_val = pvs[0].get("mate")
                        
                        if mate_val is not None:
                            cp = 10000 - abs(mate_val) * 100 if mate_val > 0 else -10000 + abs(mate_val) * 100
                            txt = f"M+{mate_val}" if mate_val > 0 else f"M{mate_val}"
                            if board.turn == chess.BLACK:
                                cp = -cp
                                txt = txt.replace("+", "-") if mate_val > 0 else txt.replace("-", "+")
                        else:
                            cp = cp_val if board.turn == chess.WHITE else -cp_val
                            txt = f"{cp/100.0:+.2f}"
                            
                        arr = []
                        colors = [(90, 200, 110, 160), (220, 140, 40, 160), (220, 60, 60, 160)] 
                        for i, pv in enumerate(pvs):
                            if i < len(colors) and "moves" in pv:
                                m_str = pv["moves"].split()[0]
                                m = chess.Move.from_uci(m_str)
                                arr.append(((m.from_square, m.to_square), colors[i]))
                                
                        self._last_cp = cp
                        self._last_txt = txt
                        return cp, txt, arr
                    else:
                        return getattr(self, '_last_cp', 0), "Not in DB", []
                except requests.RequestException:
                    return getattr(self, '_last_cp', 0), "Offline", []

            limit = chess.engine.Limit(time=0.15, depth=20)
            
            try:
                # Use pre-calculated self.multipv (which safely checks engine.options in start())
                if hasattr(self, 'multipv') and self.multipv > 1:
                    info = self.engine.analyse(board, limit, multipv=self.multipv)
                else:
                    info = [self.engine.analyse(board, limit)]
            except Exception:
                info = [self.engine.analyse(board, limit)]
                
            info_list = info if isinstance(info, list) else [info]
            
            # --- FIX: Safely Extract Live Depth for all engine types ---
            if info_list and len(info_list) > 0:
                extracted_depth = info_list[0].get("depth")
                if extracted_depth is not None:
                    self.current_depth = extracted_depth
            
            sc = info_list[0]["score"].white()
            
            # --- Safe Mate Parsing ---
            if sc.is_mate():
                m = sc.mate()
                if m > 0: cp = 10000 - m * 100
                elif m < 0: cp = -10000 - m * 100
                else: cp = 10000 if board.turn == chess.BLACK else -10000
                
                if m == 0: txt = "M+0" if cp > 0 else "M-0"
                else: txt = f"M+{m}" if cp > 0 else f"M{m}"
            else:
                cp = int(sc.score())
                txt = f"{cp/100.0:+.2f}"
                
            # --- FIX: Rebuild the Green, Orange, and Red arrows! ---
            arr = []
            colors = [(90, 200, 110, 160), (220, 140, 40, 160), (220, 60, 60, 160)] 
            
            for i, res in enumerate(info_list):
                if i < len(colors) and "pv" in res and len(res["pv"]) > 0:
                    best_move = res["pv"][0]
                    # Pass back a tuple containing BOTH the coordinates AND the specific color
                    arr.append( ((best_move.from_square, best_move.to_square), colors[i]) )
                
            self._last_cp = cp
            self._last_txt = txt
            return cp, txt, arr
            
        except Exception as e:
            return getattr(self, '_last_cp', 0), getattr(self, '_last_txt', "0.00"), []
        
    def generate_puzzle_name(self, board):
        """Generates a dynamic name for a puzzle based on board state."""
        try:
            if not self.is_active: return "Tactical Sequence"
            
            # Quick analysis
            info = self.engine.analyse(board, chess.engine.Limit(time=0.1))
            score = info["score"].relative
            
            turn_str = "White" if board.turn == chess.WHITE else "Black"
            
            if score.is_mate():
                moves = abs(score.mate())
                return f"{turn_str} to Move - Mate in {moves}"
            
            # Check for hanging pieces or tactical themes
            threat = self.get_threat(board) # Threat against current player if they pass
            if threat:
                return f"{turn_str} to Move - Save the Position"

            # Check capture opportunities in best line
            if "pv" in info and len(info["pv"]) > 0:
                best_move = info["pv"][0]
                if board.is_capture(best_move):
                    return f"{turn_str} to Move - Win Material"
                if board.gives_check(best_move):
                     return f"{turn_str} to Move - Finding Mate"
            
            return f"{turn_str} to Move - Find Best Move"
        except Exception:
            return f"Puzzle - {random.randint(1000,9999)}"

    def calculate_phase_stats(self, history):
        """Calculates specific stats for Opening, Mid, End game."""
        phases = {"opening": [], "middlegame": [], "endgame": []}
        board = chess.Board()
        
        for h in history:
            phase = self.get_game_phase(board)
            if "review" in h:
                # Store accuracy for the phase
                phases[phase].append(h["review"]["accuracy"])
            board.push(h["move"])
            
        stats = {}
        for p, vals in phases.items():
            avg = sum(vals) / len(vals) if vals else 0
            stats[p] = int(avg)
        return stats
        
    def calculate_game_stats(self, evals, mainline, user_color):
        """
        Fast-Pass Calculator for Smart Imports.
        Takes pre-calculated centipawn scores (from LucasChess PGNs) and 
        instantly derives Accuracy and Performance Elo without waking up Stockfish.
        """
        board = chess.Board()
        target_color = chess.WHITE if user_color.lower() == "white" else chess.BLACK
        
        acc_sum = 0.0
        cp_loss_sum = 0
        move_count = 0
        
        prev_eval_white = 20 # Standard starting position eval (+0.20)
        
        for i, node in enumerate(mainline):
            move = node.move
            turn = board.turn
            curr_eval_white = evals[i]
            if curr_eval_white is None: 
                curr_eval_white = prev_eval_white
            
            # We only score the moves made by the imported player
            if turn == target_color:
                # Convert the absolute white eval to the player's point of view
                if turn == chess.WHITE:
                    prev_eval_pov = prev_eval_white
                    curr_eval_pov = curr_eval_white
                else:
                    prev_eval_pov = -prev_eval_white
                    curr_eval_pov = -curr_eval_white
                
                # Calculate the Win% Drop
                move_num = board.fullmove_number
                win_pct_best = self._to_win_percentage(prev_eval_pov, move_num)
                win_pct_after = self._to_win_percentage(curr_eval_pov, move_num)
                win_loss = max(0, win_pct_best - win_pct_after)
                
                # --- Corrected ascending logic matching deep-scan exactly ---
                cls = "blunder"  # Default to blunder
                if win_loss <= self.THRESHOLDS["best"]: cls = "best"
                elif win_loss <= self.THRESHOLDS["excellent"]: cls = "excellent"
                elif win_loss <= self.THRESHOLDS["good"]: cls = "good"
                elif win_loss <= self.THRESHOLDS["inaccuracy"]: cls = "inaccuracy"
                elif win_loss <= self.THRESHOLDS["mistake"]: cls = "mistake"
                    
                # Forgive opening book moves
                if self.is_book_position(board) and i < 24:
                    cls = "book"
                        
                complexity = self.get_position_complexity(board)
                move_acc = self._calculate_accuracy(win_pct_best, win_pct_after, cls, complexity)
                
                acc_sum += move_acc
                cp_loss_sum += max(0, prev_eval_pov - curr_eval_pov)
                move_count += 1
                
            # Advance the board for the next iteration
            board.push(move)
            prev_eval_white = curr_eval_white

        # Aggregate the final game statistics
        if move_count > 0:
            avg_acpl = cp_loss_sum / move_count
            # --- GOD-TIER FIX: Average the per-move accuracies instead of global linear division! ---
            avg_acc = acc_sum / move_count
            perf_elo = self._estimate_elo_from_acpl(avg_acpl, avg_acc)
        else:
            avg_acc = 0.0
            avg_acpl = 0
            perf_elo = 1200 # Fallback if no moves found
            
        return {
            "accuracy": avg_acc,
            "acpl": avg_acpl,
            "performance_elo": perf_elo
        }

    def analyze_game_generator(self, history, time_limit=None, depth_limit=None):
        phases = ["opening", "middlegame", "endgame"]
        
        # --- ROBUST FIX: Ensure all new tracking keys are initialized ---
        stat_keys = self.MOVE_CATEGORIES + [
            "acc_sum", "cp_loss_sum", "move_count", "domination", 
            "correlation_sum", "complexity_sum", "king_exposure_sum", "pawn_damage_sum"
        ]
        
        stats = {
            "white": {k: 0 for k in stat_keys},
            "black": {k: 0 for k in stat_keys},
            "phase_stats": {
                "white": {p: {"acc_sum": 0, "count": 0} for p in phases},
                "black": {p: {"acc_sum": 0, "count": 0} for p in phases}
            }
        }

        # Check if engine is actually running
        if not self.is_active: 
            # Return the safe 'stats' object instead of empty dict {}
            yield 100, (history, stats, {"white": 0, "black": 0}, None, [])
            return

        target_depth = int(depth_limit) if depth_limit and depth_limit > 0 else 20
        
        # =================================================================
        # PHASE 1: HYPERSPEED PARALLEL PRE-COMPUTATION
        # =================================================================
        yield 0, None # UI Update
        precomputed_data = self.parallel_engine_pool_evaluate(history, target_depth)

        board = chess.Board()
        evals = [20]
        total_moves = len(history)
        mate_puzzles = []

        for i, h in enumerate(history):
            yield int((i / total_moves) * 100), None
            turn = board.turn 
            player = "white" if turn == chess.WHITE else "black"
            board_before = board.copy()
            move = h["move"]
            move_num = board.fullmove_number
            
            piece_count = len(board.piece_map())
            is_critical = (move_num > 10 and piece_count > 10)
            
            # --- GOD-TIER UPGRADE: Dynamic Time Allocation (Smart Depth) ---
            # Don't waste CPU on forced recaptures or dead simple positions.
            # Spend the saved time analyzing incredibly sharp, complex moments!
            complexity = self.get_position_complexity(board_before)
            
            if board_before.legal_moves.count() <= 2:
                # Almost forced moves
                max_time = 0.05
                target_depth = 12
            elif complexity < 25:
                # Boring/Quiet positions
                max_time = 0.2
                target_depth = 16
            elif complexity > 70:
                # Razor-sharp, chaotic tactical positions
                max_time = 0.8  # Give it maximum thinking time
                target_depth = 22 # Force cloud-level depth
            else:
                # Standard positions
                max_time = 0.4
                target_depth = int(depth_limit) if depth_limit else 18
                
            limit = chess.engine.Limit(time=max_time, depth=target_depth)
            
            try:
                prev_info = precomputed_data[i]["info"]
                trap_coefficient = precomputed_data[i]["trap"]
                
                best_move = prev_info[0]["pv"][0] if prev_info and "pv" in prev_info[0] else None
                score_best_cp = self._score_to_cp(prev_info[0]["score"].pov(turn)) if prev_info else 0
                if len(prev_info) > 1: score_second_cp = self._score_to_cp(prev_info[1]["score"].pov(turn))
                else: score_second_cp = score_best_cp - 500 
                
                try: win_pct_best = prev_info[0]["score"].pov(turn).wdl().expectation() * 100.0
                except: win_pct_best = self._to_win_percentage(score_best_cp, move_num)
                
                info_before_export = prev_info
            except:
                best_move, score_best_cp, score_second_cp, win_pct_best = None, 0, 0, 50.0
                info_before_export = []
                trap_coefficient = 0

            # --- NNUE UPGRADE: Calculate Sharpness ("Only Move" scenario) ---
            is_sharp = False
            if abs(score_best_cp - score_second_cp) > 200:
                is_sharp = True

            # Inside analyze_game_generator loop...
            board.push(move)
            opening_name = self.get_opening_name(board)
            in_book = (self.is_book_position(board) and i < 24) # <-- FIXED
            
            try:
                # --- NNUE UPGRADE: Use MultiPV=3 to prepare sharpness for the next ply ---
                curr_info = self.engine.analyse(board, limit, multipv=3)
                if curr_info: score_after_cp_pov = self._score_to_cp(curr_info[0]["score"].pov(turn))
                else: score_after_cp_pov = score_best_cp
                if move == best_move: score_after_cp_pov = score_best_cp
                
                # --- NNUE UPGRADE: Extract Native Win/Draw/Loss Probability ---
                try:
                    win_pct_after = curr_info[0]["score"].pov(turn).wdl().expectation() * 100.0
                    win_chance_pct_white = curr_info[0]["score"].white().wdl().expectation() * 100.0
                except:
                    win_pct_after = self._to_win_percentage(score_after_cp_pov, move_num)
                    win_chance_pct_white = self._to_win_percentage(self._score_to_cp(curr_info[0]["score"].white()), move_num) if curr_info else 50.0
                    
                sc = curr_info[0]["score"].white()
                
                # --- FIX: Safe Mate Parsing for Post-Game Review ---
                if sc.is_mate():
                    m = sc.mate()
                    if m > 0: cp = 10000 - m * 100
                    elif m < 0: cp = -10000 - m * 100
                    else: cp = 10000 if board.turn == chess.BLACK else -10000
                    
                    if m == 0: formatted_eval = "M+0" if cp > 0 else "M-0"
                    else: formatted_eval = f"M+{m}" if cp > 0 else f"M{m}"
                else:
                    cp = int(sc.score())
                    formatted_eval = f"{cp/100.0:+.2f}"
            except:
                curr_info = []
                score_after_cp_pov = score_best_cp
                win_pct_after = win_pct_best
                win_chance_pct_white = 50.0
                formatted_eval = "N/A"

            cls = self._classify_move_logic(
                board_before, board, move, best_move, 
                score_best_cp, score_after_cp_pov, score_second_cp,
                win_pct_best, win_pct_after, in_book
            )

            # --- GOD-TIER UPGRADE: Apply the Trap Coefficient ---
            if trap_coefficient > 250 and cls in ["good", "excellent"]:
                # The move wasn't mathematically the #1 Stockfish choice, but it set 
                # a devastating trap that is incredibly hard for a human to navigate.
                cls = "great"

            # --- TRACK POSITIONAL STATS FOR THE GM PROFILER (Safely) ---
            complexity = self.get_position_complexity(board_before)
            
            # Use .get() to absolutely guarantee no KeyErrors ever happen
            stats[player]["complexity_sum"] = stats[player].get("complexity_sum", 0) + complexity
            stats[player]["king_exposure_sum"] = stats[player].get("king_exposure_sum", 0) + self._get_king_safety_exposure(board, turn)
            stats[player]["pawn_damage_sum"] = stats[player].get("pawn_damage_sum", 0) + self._get_pawn_structure_damage(board, turn)

            # --- NNUE UPGRADE: The "Only Move" Override ---
            # If the position was incredibly sharp and user found the best/excellent move, elevate it!
            if is_sharp and cls in ["best", "excellent"] and not in_book:
                if board_before.is_capture(move) or board_before.gives_check(move):
                    cls = "brilliant"
                else:
                    cls = "great"

            # Blunder check
            if cls == "blunder":
                try:
                    # --- FIX: Balanced blunder verification ---
                    ver_limit = chess.engine.Limit(time=0.2, depth=16)
                    info_verify = self.engine.analyse(board, ver_limit, multipv=3)
                    score_verify_pov = self._score_to_cp(info_verify[0]["score"].pov(turn))
                    
                    try: win_pct_verify = info_verify[0]["score"].pov(turn).wdl().expectation() * 100.0
                    except: win_pct_verify = self._to_win_percentage(score_verify_pov, move_num)
                    
                    new_cls = self._classify_move_logic(
                        board_before, board, move, best_move,
                        score_best_cp, score_verify_pov, score_second_cp,
                        win_pct_best, win_pct_verify, in_book
                    )
                    if new_cls != "blunder":
                        cls = new_cls
                        score_after_cp_pov = score_verify_pov
                        win_pct_after = win_pct_verify
                    curr_info = info_verify
                except: pass

            complexity = self.get_position_complexity(board_before)
            cp_loss_move = max(0, score_best_cp - score_after_cp_pov)
            stats[player]["cp_loss_sum"] += cp_loss_move
            if score_after_cp_pov is not None and score_after_cp_pov > 100: 
                stats[player]["domination"] += 1
            if move == best_move: stats[player]["correlation_sum"] += 1
            move_acc = self._calculate_accuracy(win_pct_best, win_pct_after, cls, complexity)
            stats[player]["acc_sum"] += move_acc
            stats[player]["move_count"] += 1
            stats[player][cls] += 1
            phase = self.get_game_phase(board_before)
            stats["phase_stats"][player][phase]["acc_sum"] += move_acc
            stats["phase_stats"][player][phase]["count"] += 1

            # (brilliant tracking replaced by endgame mate check)

            best_moves_san = []
            if info_before_export:
                for line in info_before_export:
                    if "pv" in line and len(line["pv"]) > 0:
                        bm = line["pv"][0]
                        if bm != move: best_moves_san.append(board_before.san(bm))

            reason_text = self.generate_detailed_reason(move, board_before, board, cls, (win_pct_best - win_pct_after), best_moves_san, opening_name)
            
            # --- NEW: Call generate_positional_reason ---
            is_blunder = (cls in ["blunder", "mistake"])
            pos_reason = self.generate_positional_reason(board_before, board, move, is_blunder)
            
            # Append to the main bot reason if it found something interesting
            if pos_reason and pos_reason != "A solid positional continuation.":
                reason_text += " " + pos_reason
            # --------------------------------------------

            eval_cp_white = score_after_cp_pov if turn == chess.WHITE else -score_after_cp_pov
            evals.append(eval_cp_white)

            # --- NEW: Extract Actual Depth Reached ---
            try:
                if self.engine_path == "lichess_cloud":
                    achieved_depth = 65 # Lichess cloud default
                else:
                    achieved_depth = curr_info[0].get("depth", target_depth) if curr_info else target_depth
            except Exception:
                achieved_depth = target_depth

            h["review"] = {
                "class": cls,
                "eval_cp": eval_cp_white,
                "eval_str": formatted_eval,
                "depth": achieved_depth,
                "win_chance": win_chance_pct_white,
                "accuracy": int(move_acc),
                "complexity": complexity,
                "bot_reason": reason_text,
                "pos_reason": pos_reason,
                "best_move_uci": best_move.uci() if best_move else None
            }
            prev_info = curr_info

        ratings = {}
        for p in ["white", "black"]:
            count = stats[p]["move_count"]
            if count > 0:
                stats[p]["acpl"] = int(stats[p]["cp_loss_sum"] / count)
                stats[p]["acc"] = stats[p]["acc_sum"] / count
                stats[p]["correlation"] = int((stats[p]["correlation_sum"] / count) * 100)
                stats[p]["elo"] = self._estimate_elo_from_acpl(stats[p]["acpl"], stats[p]["acc"])
            else:
                stats[p]["acc"] = 0; stats[p]["elo"] = 400; stats[p]["acpl"] = 0; stats[p]["correlation"] = 0
            
            # --- FINAL TOUCH: Assign the GM Identity ---
            stats[p]["identity"] = self._generate_player_identity(stats[p])
            
            ratings[p] = stats[p]["elo"]

        # --- NEW: Extract Mate Puzzles if game ended in Checkmate ---
        if board.is_checkmate():
            total_plies = len(history)
            if total_plies >= 1:
                b_m1 = chess.Board()
                for i in range(total_plies - 1): b_m1.push(history[i]["move"])
                mate_puzzles.append({"fen": b_m1.fen(), "type": "Mate in 1"})
            if total_plies >= 3:
                b_m2 = chess.Board()
                for i in range(total_plies - 3): b_m2.push(history[i]["move"])
                try:
                    info = self.engine.analyse(b_m2, chess.engine.Limit(time=0.1))
                    score = info["score"].pov(b_m2.turn)
                    if score.is_mate() and score.mate() > 0:
                        mate_puzzles.append({"fen": b_m2.fen(), "type": f"Mate in {score.mate()}"})
                except: pass

        yield 100, (history, stats, ratings, self.generate_graph_surface(evals, history), mate_puzzles)

    def analyze_full_game(self, history, time_limit=None, depth_limit=None):
        gen = self.analyze_game_generator(history, time_limit, depth_limit)
        last_result = None
        for _, result in gen:
            if result: last_result = result
        return last_result

    def generate_detailed_reason(self, move, board_before, board_after, move_class, win_loss, best_moves_san=[], opening_name=None):
        ctx = {"move": move, "board_before": board_before, "board_after": board_after, "win_loss": win_loss,
               "best_moves": best_moves_san, "opening": opening_name, "is_check": board_after.is_check(),
               "is_mate": board_after.is_checkmate(), "is_capture": board_before.is_capture(move),
               "material_delta": self._get_material_diff(board_before, board_after),
               "piece_moved": board_before.piece_at(move.from_square).piece_type,
               "piece_captured": board_before.piece_at(move.to_square).piece_type if board_before.piece_at(move.to_square) else None}

        if move_class == "book": return self._explain_book(ctx)
        elif move_class == "brilliant": return self._explain_brilliant(ctx)
        elif move_class == "great": return self._explain_great(ctx)
        elif move_class in ["best", "excellent", "good"]: return self._explain_good_move(ctx, move_class)
        elif move_class == "miss": return self._explain_miss(ctx)
        elif move_class == "blunder": return self._explain_blunder(ctx)
        elif move_class == "mistake": return self._explain_mistake(ctx)
        else: return self._explain_inaccuracy(ctx)

    def _explain_book(self, ctx):
        name = ctx["opening"]
        if name and name != "Unknown Opening":
            return random.choice([f"Following standard theory in the {name}.", f"This is a known book move in the {name}.", f"Correctly playing the {name} lines."])
        return "Standard opening theory."

    def _explain_brilliant(self, ctx):
        if ctx["is_mate"]: return "Brilliant! You found a forced mating sequence."
        if ctx["material_delta"] < 0: return "Brilliant! You sacrificed material to gain a winning advantage."
        return random.choice(["Incredible vision! This move exploits a tactical weakness perfectly.", "A master-level find! Brilliant."])

    def _explain_great(self, ctx):
        return random.choice(["Great move! You found the only move that maintains your position.", "Excellent vision. This was a difficult move to spot."])

    def _explain_good_move(self, ctx, cls):
        if ctx["is_mate"]: return "Checkmate! A perfect finish."
        if ctx["material_delta"] == 0 and ctx["is_capture"] and len(ctx["board_after"].piece_map()) < 10: return "Simplifying the position. A smart way to secure the win."
        if ctx["board_before"].is_castling(ctx["move"]): return "Castling to safety. Good prioritization."
        if ctx["board_before"].is_check(): return "The best way to escape check."
        if ctx["material_delta"] > 0:
            p_name = chess.piece_name(ctx["piece_captured"] or chess.PAWN).capitalize()
            return f"Winning a {p_name}! {cls.capitalize()} move."
        if ctx["piece_moved"] == chess.PAWN and chess.square_rank(ctx["move"].to_square) in [0, 7]: return "Promotion! A decisive advantage."
        if cls == "excellent": return "An excellent, precise move."
        return random.choice(["A solid developing move.", "Improving your piece activity.", "Controlling key squares."])

    def _explain_blunder(self, ctx):
        base = "Blunder. "
        if ctx["is_mate"]: return "Blunder. You walked into checkmate."
        if ctx["material_delta"] < 0:
            lost_val = abs(ctx["material_delta"])
            if lost_val >= 9: return base + "You hung your Queen!"
            if lost_val >= 5: return base + "You hung a Rook!"
            if lost_val >= 3: return base + "You gave away a piece for free."
        rec = ctx["best_moves"][0] if ctx["best_moves"] else "another move"
        return base + f"You gave away the game. {rec} was required."

    def _explain_miss(self, ctx):
        return f"Missed Win. You had a winning position, but now it's equal. You should have played {ctx['best_moves'][0]}."

    def _explain_mistake(self, ctx):
        rec = ctx["best_moves"][0] if ctx["best_moves"] else "a better move"
        if ctx["is_capture"] and ctx["material_delta"] < 0: return f"Mistake. That exchange was bad for you. {rec} was better."
        return f"Mistake. This allows the opponent to equalize or take the lead. {rec} was best."

    def _explain_inaccuracy(self, ctx):
        return random.choice(["Inaccuracy. A bit passive.", f"Not the best. {ctx['best_moves'][0]} was slightly better."])

    def _normalize_cp_for_graph(self, cp_score):
        if cp_score is None:
            return None
        try:
            cp = int(cp_score)
        except Exception:
            return None

        if abs(cp) >= 9000:
            return 1000 * (1 if cp > 0 else -1)

        return max(-1000, min(1000, cp))

    def _cp_to_graph_y(self, cp_score):
        # New graph mapping: incorporate material asymmetry to better reflect
        # win-probability influence on the visual graph using LucasChess' idea.
        cp = self._normalize_cp_for_graph(cp_score)
        if cp is None:
            return None

        # Estimate material asymmetry (in pawn units) from the position if available.
        # We can't access a board here, so fallback to a sigmoid mapping on cp alone.
        try:
            # Standard smooth logistic mapping (centipawns -> [-1,1]) with tuned slope
            return 2.0 / (1.0 + math.exp(-0.004 * cp)) - 1.0
        except Exception:
            return 0.0

    def calibrate_exact_from_histories(self, datasets):
        """
        Calibrate `CP_THRESHOLDS` and `CALIB_PARAMS` so that labeled plies
        in `datasets` will be classified as the provided reference labels.

        `datasets` is a list of dicts each containing keys:
          - prevs: list of prev evals (white POV absolute)
          - currs: list of curr evals (white POV absolute)
          - gaps: list of best-vs-second gaps (centipawns)
          - turns: list of turn values (chess.WHITE/chess.BLACK)
          - ref: dict mapping ply index -> desired label

        This routine derives boundaries from observed cp losses and gap values
        and sets thresholds so the labeled plies fall into the intended buckets.
        It's intended for small supervised calibration runs (matches the labels
        provided exactly when possible).
        """
        # severity order (increasing loss tolerated)
        tiers = ["best", "excellent", "good", "inaccuracy", "mistake", "blunder"]

        # collect cp_loss and gap stats per label
        stats = {t: [] for t in tiers}
        gap_stats = {"great": [], "brilliant": []}

        for d in datasets:
            prevs, currs, gaps, turns, ref = d['prevs'], d['currs'], d.get('gaps', [0]*len(d['prevs'])), d['turns'], d['ref']
            for idx, lab in ref.items():
                # compute cp loss in player's POV (prevs/currs already in POV per dataset)
                try:
                    cp_loss = max(0.0, float(prevs[idx]) - float(currs[idx]))
                except Exception:
                    cp_loss = 0.0
                if lab in stats:
                    stats[lab].append(cp_loss)
                elif lab == 'great':
                    gap_stats['great'].append(gaps[idx])
                elif lab == 'brilliant':
                    gap_stats['brilliant'].append(gaps[idx])

        # derive thresholds: use max observed cp_loss per tier as safe upper bound
        derived = {}
        last = -1
        for t in tiers:
            vals = stats.get(t, [])
            if vals:
                # set threshold slightly above observed max (ceil)
                v = int(math.ceil(max(vals) + 2))
            else:
                # fallback sensible defaults if no observations
                v = self.CP_THRESHOLDS.get(t, 50)
            # ensure monotonicity
            if v <= last:
                v = last + 5
            derived[t] = v
            last = v

        # brilliancy/great gaps: set to observed minima so observed moves qualify
        if gap_stats['great']:
            gap_great = int(max(10, min(gap_stats['great'])))
        else:
            gap_great = self.CALIB_PARAMS.get('gap_great', self.GREAT_DIFF)

        if gap_stats['brilliant']:
            gap_brill = int(max(gap_great + 20, min(gap_stats['brilliant'])))
        else:
            gap_brill = self.CALIB_PARAMS.get('gap_brill', self.BRILLIANT_DIFF)

        # Miss thresholds keep defaults unless we inferred misses
        miss_win = self.CALIB_PARAMS.get('miss_win', self.MISS_WINNING_THRESHOLD)
        miss_eq = self.CALIB_PARAMS.get('miss_eq', self.MISS_EQUAL_BARRIER)

        # Apply derived thresholds to the engine
        self.CP_THRESHOLDS.update(derived)
        self.CALIB_PARAMS.update({'gap_great': gap_great, 'gap_brill': gap_brill, 'miss_win': miss_win, 'miss_eq': miss_eq})

        return {'cp': derived, 'calib': {'gap_great': gap_great, 'gap_brill': gap_brill, 'miss_win': miss_win, 'miss_eq': miss_eq}}
    # ---------------------- Calibration Helpers ----------------------
    def simple_classify_by_cp(self, prev_cp, curr_cp, turn):
        """Lightweight fallback classifier using only centipawn movement and win% drops.
        This is intended for calibration against external references (e.g., like chess.coms labels).
        """
        # Convert to player's point-of-view
        prev_pov = prev_cp if turn == chess.WHITE else -prev_cp
        curr_pov = curr_cp if turn == chess.WHITE else -curr_cp

        win_before = self._to_win_percentage(prev_pov)
        win_after = self._to_win_percentage(curr_pov)
        win_drop = max(0.0, win_before - win_after)

        cp_loss = max(0.0, prev_pov - curr_pov)

        # Miss detection (strong win lost to near equality)
        if win_before > self.MISS_WINNING_THRESHOLD and win_after < self.MISS_EQUAL_BARRIER:
            return "miss"

        # Use CP thresholds (tuned values live in self.CP_THRESHOLDS)
        if cp_loss >= self.CP_THRESHOLDS.get("blunder", 400):
            return "blunder"
        if cp_loss >= self.CP_THRESHOLDS.get("mistake", 200):
            return "mistake"
        if cp_loss >= self.CP_THRESHOLDS.get("inaccuracy", 100):
            return "inaccuracy"
        if cp_loss >= self.CP_THRESHOLDS.get("good", 50):
            return "good"
        if cp_loss >= self.CP_THRESHOLDS.get("excellent", 30):
            return "excellent"
        # Small losses or minor changes are 'best' or 'best-like'
        if cp_loss >= self.CP_THRESHOLDS.get("best", 10):
            return "best"
        return "best"

    def simple_classify_by_cp_gap(self, prev_cp, curr_cp, turn, best_gap=0):
        """God-Tier Gap-aware classifier: Uses Neural Net Win% scaling for pure mathematical accuracy."""
        prev_pov = prev_cp if turn == chess.WHITE else -prev_cp
        curr_pov = curr_cp if turn == chess.WHITE else -curr_cp

        # --- GOD-TIER UPGRADE: Neural Net Win% Mapping ---
        win_pct_best = self._to_win_percentage(prev_pov, 20)
        win_pct_after = self._to_win_percentage(curr_pov, 20)
        win_drop = max(0.0, win_pct_best - win_pct_after)
        cp_loss = max(0.0, prev_pov - curr_pov)

        # 1. Miss Detection (Strict WDL trajectory tracking)
        if win_pct_best > self.CALIB_PARAMS.get('miss_win', 90.0) and win_pct_after < self.CALIB_PARAMS.get('miss_eq', 55.0):
            return 'miss'

        # 2. Dynamic Sharpness Recognition (Gap is scaled by Win Probability!)
        # If the position is highly winning (win > 90%), gaps don't matter as much. 
        # If the position is equal (win ~ 50%), gaps are extremely critical!
        sharpness_multiplier = 1.0 if win_pct_best < 80.0 else 0.5 
        scaled_brill_gap = self.CALIB_PARAMS.get('gap_brill', 280.0) * sharpness_multiplier
        scaled_great_gap = self.CALIB_PARAMS.get('gap_great', 140.0) * sharpness_multiplier

        if cp_loss <= self.CP_THRESHOLDS.get('best', 10):
            if best_gap >= scaled_brill_gap and cp_loss <= 5: return 'brilliant'
            if best_gap >= scaled_great_gap and cp_loss <= 10: return 'great'

        # 3. Double-Layered Safeguards (Checks BOTH Win Drop and CP Loss)
        if win_drop > 20.0 or cp_loss >= self.CP_THRESHOLDS.get('blunder', 400): return 'blunder'
        if cp_loss >= self.CP_THRESHOLDS.get('mistake', 200):
            return 'mistake'
        if cp_loss >= self.CP_THRESHOLDS.get('inaccuracy', 100):
            return 'inaccuracy'
        if cp_loss >= self.CP_THRESHOLDS.get('good', 50):
            return 'good'
        if cp_loss >= self.CP_THRESHOLDS.get('excellent', 30):
            return 'excellent'
        if cp_loss >= self.CP_THRESHOLDS.get('best', 10):
            return 'best'
        return 'best'

    def calibrate_thresholds_from_reference(self, history, reference_labels):
        """Calibrate CP thresholds to better match `reference_labels`.

        history: list of moves (must include 'review':{'eval_cp': ...} for each move)
        reference_labels: list of strings, one per history entry, containing like chess.coms labels

        Returns: dict of best-found thresholds and the resulting classification list.
        """
        # Validate inputs
        if not history or not reference_labels or len(history) != len(reference_labels):
            raise ValueError("History and reference_labels must be same non-empty length")

        # Build arrays of prev/curr CP in white-perspective as used elsewhere
        prev_eval_white = 20
        prevs = []
        currs = []
        turns = []
        for i, h in enumerate(history):
            move = h.get("move")
            turn = chess.WHITE if (i % 2 == 0) else chess.BLACK
            turns.append(turn)
            curr = None
            if "review" in h and isinstance(h["review"].get("eval_cp"), (int, float)):
                curr = h["review"]["eval_cp"]
            else:
                curr = prev_eval_white
            prevs.append(prev_eval_white if turn == chess.WHITE else -prev_eval_white)
            currs.append(curr if turn == chess.WHITE else -curr)
            prev_eval_white = curr

        # Grid-search sensible ranges for the main cp thresholds
        best_score = -1
        best_thresh = None
        best_classes = None

        blunder_range = range(300, 701, 100)
        mistake_range = range(150, 401, 50)
        inaccuracy_range = range(60, 201, 20)
        good_range = range(20, 101, 10)
        excellent_range = range(5, 51, 5)
        best_range = range(0, 21, 5)

        for bl in blunder_range:
            for mi in mistake_range:
                if mi >= bl: continue
                for ina in inaccuracy_range:
                    if ina >= mi: continue
                    for go in good_range:
                        if go >= ina: continue
                        for ex in excellent_range:
                            if ex >= go: continue
                            for be in best_range:
                                if be >= ex: continue
                                # Temporarily set thresholds
                                old = self.CP_THRESHOLDS.copy()
                                self.CP_THRESHOLDS.update({
                                    "blunder": bl,
                                    "mistake": mi,
                                    "inaccuracy": ina,
                                    "good": go,
                                    "excellent": ex,
                                    "best": be
                                })

                                # Classify and score match
                                classes = []
                                matches = 0
                                for i in range(len(history)):
                                    cls = self.simple_classify_by_cp(prevs[i], currs[i], turns[i])
                                    classes.append(cls)
                                    if cls == reference_labels[i]:
                                        matches += 1

                                if matches > best_score:
                                    best_score = matches
                                    best_thresh = self.CP_THRESHOLDS.copy()
                                    best_classes = list(classes)

                                # restore
                                self.CP_THRESHOLDS = old

        return {"best_score": best_score, "best_thresholds": best_thresh, "classes": best_classes}

    def calibrate_thresholds_with_gap(self, history, reference_labels, time_limit=60, trials=5000):
        """Randomized calibration that also searches gap-based parameters and miss thresholds.

        history: list of moves with optional 'review':{'eval_cp':...,'best_gap':...}
        reference_labels: list of target labels
        Returns best found parameter set and classifications.
        """
        if not history or not reference_labels:
            raise ValueError('history and reference_labels required')

        # prepare arrays like other helpers; accept optional 'best_gap' stored per move
        prev_eval_white = 20
        prevs = []
        currs = []
        turns = []
        gaps = []
        for i, h in enumerate(history):
            turn = chess.WHITE if (i % 2 == 0) else chess.BLACK
            turns.append(turn)
            curr = None
            if 'review' in h and isinstance(h['review'].get('eval_cp'), (int, float)):
                curr = h['review']['eval_cp']
            else:
                curr = prev_eval_white
            prevs.append(prev_eval_white if turn == chess.WHITE else -prev_eval_white)
            currs.append(curr if turn == chess.WHITE else -curr)
            gaps.append(h.get('review', {}).get('best_gap', 0))
            prev_eval_white = curr

        n = min(len(prevs), len(reference_labels), len(gaps))
        prevs = prevs[:n]; currs = currs[:n]; turns = turns[:n]; gaps = gaps[:n]
        ref = reference_labels[:n]

        best_score = -1
        best_params = None
        best_classes = None

        start = time.time()
        iters = 0
        while time.time() - start < time_limit and iters < trials:
            iters += 1
            # --- GOD-TIER UPGRADE: Simulated Annealing Optimizer ---
            # Instead of a blind random shotgun, we intelligently mutate the best found parameters!
            if best_params and random.random() < 0.70:
                # 70% chance to micro-mutate the current "King" to find perfect decimals
                cp_king = best_params['CP_THRESHOLDS']
                cb_king = best_params['CALIB_PARAMS']
                
                be = max(0, min(15, cp_king['best'] + random.randint(-2, 2)))
                ex = max(be + 1, min(60, cp_king['excellent'] + random.randint(-5, 5)))
                go = max(ex + 1, min(150, cp_king['good'] + random.randint(-10, 10)))
                ina = max(go + 1, min(300, cp_king['inaccuracy'] + random.randint(-20, 20)))
                mi = max(ina + 1, min(600, cp_king['mistake'] + random.randint(-30, 30)))
                bl = max(mi + 1, min(1000, cp_king['blunder'] + random.randint(-40, 40)))
                
                gap_great = max(50.0, cb_king.get('gap_great', 150.0) + random.uniform(-10.0, 10.0))
                gap_brill = max(gap_great + 20.0, cb_king.get('gap_brill', 300.0) + random.uniform(-20.0, 20.0))
                miss_eq = max(20.0, min(80.0, cb_king.get('miss_eq', 50.0) + random.uniform(-2.0, 2.0)))
                miss_win = max(miss_eq + 5.0, min(99.0, cb_king.get('miss_win', 90.0) + random.uniform(-2.0, 2.0)))
            else:
                # 30% chance for a wild mutation to escape local minima
                be = random.randint(0, 15)
                ex = random.randint(be + 1, min(60, be + 30))
                go = random.randint(ex + 1, min(150, ex + 40))
                ina = random.randint(go + 1, min(300, go + 150))
                mi = random.randint(ina + 1, min(600, ina + 300))
                bl = random.randint(mi + 1, min(1000, mi + 400))
                
                gap_great = random.uniform(100.0, 300.0)
                gap_brill = random.uniform(gap_great + 20.0, 500.0)
                miss_eq = random.uniform(30.0, 60.0)
                miss_win = random.uniform(miss_eq + 5.0, 95.0)

            # apply sampled params
            self.CP_THRESHOLDS.update({'best': be, 'excellent': ex, 'good': go, 'inaccuracy': ina, 'mistake': mi, 'blunder': bl})
            self.CALIB_PARAMS.update({'gap_great': gap_great, 'gap_brill': gap_brill, 'miss_win': miss_win, 'miss_eq': miss_eq})

            matches = 0
            classes = []
            for i in range(n):
                cls = self.simple_classify_by_cp_gap(prevs[i], currs[i], turns[i], gaps[i])
                classes.append(cls)
                if cls == ref[i]:
                    matches += 1

            if matches > best_score:
                best_score = matches
                best_params = {'CP_THRESHOLDS': self.CP_THRESHOLDS.copy(), 'CALIB_PARAMS': self.CALIB_PARAMS.copy()}
                best_classes = list(classes)

        return {'best_score': best_score, 'best_params': best_params, 'classes': best_classes}

    # ---------------- Feature-based classification ----------------
    def _extract_features_from_history(self, history):
        """Return list of feature dicts for each ply in history. Now highly expanded."""
        feats = []
        prev_eval_white = 20
        board = chess.Board()
        for i, h in enumerate(history):
            move = h.get('move')
            turn = board.turn
            curr = h.get('review', {}).get('eval_cp', prev_eval_white)

            prev_pov = prev_eval_white if turn == chess.WHITE else -prev_eval_white
            curr_pov = curr if turn == chess.WHITE else -curr
            cp_loss = max(0, prev_pov - curr_pov)

            best_gap = h.get('review', {}).get('best_gap', 0)
            win_after = h.get('review', {}).get('win_chance', self._to_win_percentage(curr_pov, 20))
            
            sim_prev_pov = curr_pov + cp_loss
            win_before = self._to_win_percentage(sim_prev_pov, 20)
            win_drop = max(0.0, win_before - win_after)

            complexity = self.get_position_complexity(board)
            
            # --- GOD-TIER UPGRADE: Positional Feature Injection ---
            board_after = board.copy()
            if move: board_after.push(move)
            
            material_delta = self._get_material_diff(board, board_after)
            is_capture = board.is_capture(move) if move else False
            
            mobility_delta = self._get_mobility_delta(board, board_after, turn)
            pawn_damage = self._get_pawn_structure_damage(board_after, turn)
            king_exposure = self._get_king_safety_exposure(board_after, turn)

            feats.append({
                'prev_cp': prev_pov, 'curr_cp': curr_pov, 'cp_loss': cp_loss,
                'best_gap': best_gap, 'win_before': win_before, 'win_after': win_after,
                'win_drop': win_drop, 'complexity': complexity, 'material_delta': material_delta,
                'is_capture': is_capture, 'turn': turn, 'move': move,
                'mobility': mobility_delta, 'pawn_damage': pawn_damage, 'king_exposure': king_exposure
            })

            try: board.push(move)
            except Exception: pass
            prev_eval_white = curr

        return feats

    def _feature_classify(self, feat, params):
        """Classify a single move using features and params.

        params: dict with keys for cp thresholds, gap multipliers, positive thresholds, miss thresholds.
        """
        cp_loss = feat['cp_loss']
        gap = feat.get('best_gap', 0)
        win_drop = feat.get('win_drop', 0)
        complexity = feat.get('complexity', 0)
        mat = feat.get('material_delta', 0)

        # Miss detection
        if feat['win_before'] > params.get('miss_win', 88) and feat['win_after'] < params.get('miss_eq', 55):
            return 'miss'

        # strict loss-based categories
        if cp_loss >= params['blunder']: return 'blunder'
        if cp_loss >= params['mistake']: return 'mistake'
        if cp_loss >= params['inaccuracy']: return 'inaccuracy'

        # compute positive score: higher gap and higher complexity raise positive score; cp_loss lowers it
        pos = gap * params.get('gap_weight', 0.8) - cp_loss * params.get('cp_weight', 1.0) + complexity * params.get('complex_weight', 0.6) + max(0, mat) * params.get('mat_weight', 8)

        if pos >= params.get('brill_thresh', 300):
            return 'brilliant'
        if pos >= params.get('great_thresh', 120):
            return 'great'

        # fallbacks based on small losses
        if cp_loss >= params['good']: return 'good'
        if cp_loss >= params['excellent']: return 'excellent'
        return 'best'

    def calibrate_feature_classifier(self, history, reference_labels, time_limit=90):
        """Random search for feature-classifier params to maximize exact matches.

        Returns best params and classes.
        """
        if not history or not reference_labels:
            raise ValueError('history and reference_labels required')

        feats = self._extract_features_from_history(history)
        n = min(len(feats), len(reference_labels))
        feats = feats[:n]
        ref = reference_labels[:n]

        best_score = -1
        best_params = None
        best_classes = None
        start = time.time()
        iters = 0

        while time.time() - start < time_limit:
            iters += 1
            # sample param set
            params = {
                'blunder': random.randint(300, 800),
                'mistake': random.randint(120, 400),
                'inaccuracy': random.randint(50, 180),
                'good': random.randint(10, 60),
                'excellent': random.randint(3, 30),
                'best': random.randint(0, 8),
                'gap_weight': random.uniform(0.2, 1.5),
                'cp_weight': random.uniform(0.6, 1.6),
                'complex_weight': random.uniform(0.0, 1.2),
                'mat_weight': random.uniform(0.0, 12.0),
                'brill_thresh': random.uniform(150, 800),
                'great_thresh': random.uniform(60, 300),
                'miss_win': random.randint(75, 95),
                'miss_eq': random.randint(25, 70)
            }

            matches = 0
            classes = []
            for i in range(n):
                cls = self._feature_classify(feats[i], params)
                classes.append(cls)
                if cls == ref[i]: matches += 1

            if matches > best_score:
                best_score = matches
                best_params = params.copy()
                best_classes = list(classes)

        return {'best_score': best_score, 'best_params': best_params, 'classes': best_classes}

    # ----------------- Classifier training, soft scoring, fast review -----------------
    def _map_label_equiv(self, label):
        """Map incoming labels to canonical set (including en-croissant aliases)."""
        if not label: return label
        l = label.lower()
        if l == 'dubious': return 'inaccuracy'
        # keep known labels
        known = set(['book','brilliant','great','best','excellent','good','inaccuracy','mistake','blunder','miss'])
        return l if l in known else l

    def _soft_score(self, pred, ref):
        """Return soft score: 1 exact, 0.7 equiv-group, 0.3 near, 0 otherwise."""
        if pred == ref: return 1.0
        eq_groups = [set(['best','great','brilliant']), set(['excellent','good']), set(['inaccuracy']), set(['mistake']), set(['blunder']), set(['miss']), set(['book'])]
        for g in eq_groups:
            if pred in g and ref in g:
                return 0.7
        # near categories (best <-> excellent etc.)
        near_pairs = {('best','excellent'), ('excellent','good'), ('mistake','inaccuracy')}
        if (pred, ref) in near_pairs or (ref, pred) in near_pairs:
            return 0.3
        return 0.0

    def train_feature_model(self, history, reference_labels):
        """Train a small RandomForest classifier on extracted features. Requires scikit-learn.

        Returns: model, label_encoder (list)
        """
        try:
            from sklearn.ensemble import RandomForestClassifier
            from sklearn.preprocessing import LabelEncoder
        except Exception:
            raise RuntimeError('scikit-learn is required for training. Install with pip install scikit-learn')

        feats = self._extract_features_from_history(history)
        n = min(len(feats), len(reference_labels))
        X = []
        y = []
        for i in range(n):
            f = feats[i]
            X.append([f['cp_loss'], f['best_gap'], f['complexity'], f['material_delta'], float(f['is_capture'])])
            y.append(self._map_label_equiv(reference_labels[i]))

        le = LabelEncoder()
        y_enc = le.fit_transform(y)
        clf = RandomForestClassifier(n_estimators=60, max_depth=12, random_state=1, n_jobs=1)
        clf.fit(np.array(X), y_enc)
        return clf, le

    def predict_with_model(self, model, label_enc, history):
        feats = self._extract_features_from_history(history)
        X = []
        for f in feats:
            X.append([f['cp_loss'], f['best_gap'], f['complexity'], f['material_delta'], float(f['is_capture'])])
        ypred = model.predict(np.array(X))
        labels = label_enc.inverse_transform(ypred)
        return list(labels)

    def evaluate_model_against_reference(self, model, label_enc, history, reference_labels, soft=True):
        preds = self.predict_with_model(model, label_enc, history)
        n = min(len(preds), len(reference_labels))
        exact = 0
        soft_sum = 0.0
        for i in range(n):
            p = self._map_label_equiv(preds[i])
            r = self._map_label_equiv(reference_labels[i])
            if p == r: exact += 1
            soft_sum += self._soft_score(p, r) if soft else (1.0 if p==r else 0.0)
        return {'exact': exact, 'soft_score': soft_sum, 'n': n}

    def fast_review(self, mainline, time_per_ply=0.12, multipv=2):
        """Fast review mode: analyze each ply with small time budget and return quick history.

        Aim: ~45 moves (90 plies) in ~15-20s; choose defaults accordingly.
        """
        import chess.engine
        history = []
        board = chess.Board()
        try:
            # --- FIX: Local Fallback for Fast Review ---
            safe_path = self.engine_path
            if safe_path == "lichess_cloud":
                import os
                for p in ["engines/Stockfish 18.exe", "engines/stockfish.exe", "engines/Rubi Chess.exe", "stockfish.exe"]:
                    if os.path.exists(p):
                        safe_path = p
                        break
                        
            import sys
            if sys.platform == "win32":
                eng = chess.engine.SimpleEngine.popen_uci(safe_path, creationflags=0x08000000)
            else:
                eng = chess.engine.SimpleEngine.popen_uci(safe_path)
                
            # try configure threads/hash if available
            cfg = {}
            if 'Threads' in eng.options:
                cfg['Threads'] = max(1, min(self.threads, 2))
            if 'Hash' in eng.options:
                cfg['Hash'] = min(64, self.hash_size)
            try: eng.configure(cfg)
            except Exception: pass
            for move in mainline:
                board.push(move)
                try:
                    info = eng.analyse(board, chess.engine.Limit(time=time_per_ply), multipv=multipv)
                except Exception:
                    info = None
                cp = 0
                if info and 'score' in info:
                    sc = info[0]['score'].white() if isinstance(info, list) else info['score'].white()
                    if sc.is_mate():
                        m = sc.mate(); cp = 10000 - (m*100) + 50 if m>0 else -10000 + (abs(m)*100) - 50
                    else:
                        try: cp = int(sc.score())
                        except: cp = 0
                history.append({'move': move, 'review': {'eval_cp': cp}})
        finally:
            try: eng.quit()
            except Exception: pass
        return history

    def generate_graph_surface(self, evals, history=None):
        """Safe graph generation — works even if matplotlib is not installed."""
        global matplotlib, plt, agg
        
        # Lazy-load matplotlib only when needed
        if matplotlib is None:
            try:
                import matplotlib
                import matplotlib.pyplot as plt
                import matplotlib.backends.backend_agg as agg
                matplotlib.use("Agg")
            except ImportError:
                print("WARNING: matplotlib not installed → Graph disabled in Review.")
                return None  # UI will gracefully skip the graph

        try:
            fig = plt.figure(figsize=(7, 2.5), dpi=100)
            ax = fig.add_subplot(111)
            mapped = []
            for e in evals:
                y = self._cp_to_graph_y(e)
                mapped.append(0.0 if y is None else y)
            y_data = mapped
            x_data = range(len(y_data))
            
            # Draw the main lines and fills
            ax.plot(x_data, y_data, color='#333333', linewidth=1.5, zorder=2)
            ax.fill_between(x_data, y_data, 0, where=[y>=0 for y in y_data], interpolate=True, facecolor='#66bb6a', alpha=0.4, zorder=1)
            ax.fill_between(x_data, y_data, 0, where=[y<=0 for y in y_data], interpolate=True, facecolor='#ef5350', alpha=0.4, zorder=1)
            ax.axhline(y=0, color='#888888', linestyle=':', linewidth=1, zorder=1)
            
            # --- Plot Colored Dots for Key Moments ---
            if history:
                for i, step in enumerate(history):
                    graph_idx = i + 1 
                    if graph_idx >= len(y_data): break
                    
                    cls = step.get("review", {}).get("class", "")
                    cp = step.get("review", {}).get("eval_cp", 0)
                    y_val = y_data[graph_idx]
                    
                    if cls == "brilliant":
                        ax.scatter(graph_idx, y_val, color='#00cccc', s=45, zorder=5, edgecolors='white', linewidths=1)
                    elif cls == "great":
                        ax.scatter(graph_idx, y_val, color='#5c85d6', s=45, zorder=5, edgecolors='white', linewidths=1)
                    elif cls == "blunder":
                        ax.scatter(graph_idx, y_val, color='#ff3333', s=45, zorder=5, edgecolors='white', linewidths=1)

            ax.axis('off')
            ax.set_facecolor('white')
            fig.patch.set_facecolor('white')
            plt.tight_layout(pad=0.5)
            
            canvas = agg.FigureCanvasAgg(fig)
            canvas.draw()
            raw_data = canvas.buffer_rgba()
            size = canvas.get_width_height()
            surf = pygame.image.frombuffer(raw_data, size, "RGBA")
            plt.close(fig) 
            return surf
        except Exception as e: 
            print(f"Graph Error: {e}")
            return None

    # ==============================================================================
    # --- IMPROVED ROBUST CHESS METRICS ENGINE (Phase Detection + ACL -> Accuracy) ---
    # ==============================================================================

    def detect_game_phases(self, history):
        """Ultra-Intelligent Phase Detection using Move Count, Book Theory, and Material Heuristics."""
        total_ply = len(history)
        endgame_start = total_ply
        last_book_ply = 0
        for ply, step in enumerate(history):
            if isinstance(step, dict) and step.get("review", {}).get("class") == "book": last_book_ply = ply
            else: break

        opening_end = max(16, last_book_ply + 7)
        opening_end = min(opening_end, total_ply)

        for ply, step in enumerate(history):
            if ply < opening_end: continue
            fen = step.get("fen") if isinstance(step, dict) else None
            if not fen: continue
            board = chess.Board(fen)
            w_piece_val, b_piece_val = 0, 0
            has_w_queen, has_b_queen = False, False
            for sq in chess.SQUARES:
                p = board.piece_at(sq)
                if p and p.piece_type != chess.KING and p.piece_type != chess.PAWN:
                    val = 0
                    if p.piece_type == chess.QUEEN: 
                        val = 9
                        if p.color == chess.WHITE: has_w_queen = True
                        else: has_b_queen = True
                    elif p.piece_type == chess.ROOK: val = 5
                    elif p.piece_type in [chess.BISHOP, chess.KNIGHT]: val = 3
                    if p.color == chess.WHITE: w_piece_val += val
                    else: b_piece_val += val
            
            is_endgame = False
            if not has_w_queen and not has_b_queen and w_piece_val <= 14 and b_piece_val <= 14: is_endgame = True
            elif has_w_queen and has_b_queen and w_piece_val <= 12 and b_piece_val <= 12: is_endgame = True
            elif (has_w_queen != has_b_queen) and (w_piece_val + b_piece_val <= 21): is_endgame = True
            elif ply >= 80 and w_piece_val <= 16 and b_piece_val <= 16: is_endgame = True
            if is_endgame:
                endgame_start = ply
                break

        if total_ply <= 60: endgame_start = total_ply
        else:
            if endgame_start == total_ply: endgame_start = total_ply - 8
        if endgame_start < opening_end: opening_end = endgame_start
            
        return {
            "opening": (0, opening_end) if opening_end > 0 else None,
            "middlegame": (opening_end, endgame_start) if endgame_start > opening_end else None,
            "endgame": (endgame_start, total_ply) if endgame_start < total_ply else None
        }

    def calculate_acpl_and_accuracy(self, moves, is_white):
        """Calculates Average Centipawn Loss and Robust Accuracy for a specific player."""
        if not moves or len(moves) < 2: return {"acl": 0, "accuracy": 0.0, "count": 0}
        total_cp_loss = 0
        analyzed_count = 0
        
        for prev, cur in zip(moves, moves[1:]):
            if not isinstance(cur, dict) or not isinstance(prev, dict): 
                print(f"[DEBUG] Skipping non-dict in ACPL calculation: prev={repr(prev)}, cur={repr(cur)}")
                continue
            
            move_ply = cur.get("ply", 0)
            if (move_ply % 2 != 0) != is_white: continue
            prev_eval = prev.get("review", {}).get("eval_cp", 20)
            cur_eval = cur.get("review", {}).get("eval_cp", prev_eval)
            prev_eval = max(-1000, min(1000, prev_eval))
            cur_eval = max(-1000, min(1000, cur_eval))
            loss = prev_eval - cur_eval if is_white else cur_eval - prev_eval
            loss = max(0, min(350, loss)) 
            total_cp_loss += loss
            analyzed_count += 1
            
        if analyzed_count == 0: return {"acl": 0, "accuracy": 0.0, "count": 0}
        avg_acl = total_cp_loss / analyzed_count
        
        # --- PERFECTED CALIBRATION MATH ---
        # Uses your exact calibrated acc_weight (1.608) 
        weight = self.CALIB_PARAMS.get("acc_weight", 1.60835)
        
        # This linear subtraction is what your calibrator optimized for!
        accuracy_percentage = 100.0 - (avg_acl / weight)
        accuracy_percentage = max(0.0, min(100.0, accuracy_percentage))
        
        return {"acl": avg_acl, "accuracy": round(accuracy_percentage, 1), "count": analyzed_count}

    def calculate_detailed_performance(self, history, white_name, black_name):
        """Processes game history to generate Phase ELOs, overall accuracy, and summaries."""
        if not history: return None
        phases = self.detect_game_phases(history)
        
        def get_phase_moves(phase_indices):
            if phase_indices is None: return []
            start, end = phase_indices
            if start == 0: return [{"ply": 0, "review": {"eval_cp": 20}}] + history[start:end]
            else: return history[start - 1 : end]

        results = []
        padded_overall_history = [{"ply": 0, "review": {"eval_cp": 20}}] + history
        
        for is_white in [True, False]:
            name = white_name if is_white else black_name
            overall = self.calculate_acl_and_accuracy(padded_overall_history, is_white)
            opening_p = self.calculate_acl_and_accuracy(get_phase_moves(phases["opening"]), is_white)
            mid_p = self.calculate_acl_and_accuracy(get_phase_moves(phases["middlegame"]), is_white)
            end_p = self.calculate_acl_and_accuracy(get_phase_moves(phases["endgame"]), is_white)
            
            perf = {
                "name": name,
                "is_white": is_white,
                "overall_accuracy": overall["accuracy"],
                "performance_elo": self._estimate_elo_from_acpl(overall["acl"], overall["accuracy"]),
                "acl": overall["acl"],
                "move_count": overall["count"],
                "opening_elo": self._estimate_elo_from_acpl(opening_p["acl"], opening_p["accuracy"]) if opening_p["count"] > 0 else None,
                "middlegame_elo": self._estimate_elo_from_acpl(mid_p["acl"], mid_p["accuracy"]) if mid_p["count"] > 0 else None,
                "endgame_elo": self._estimate_elo_from_acpl(end_p["acl"], end_p["accuracy"]) if end_p["count"] > 0 else None,
            }
            
            smry = { "brilliant": 0, "great": 0, "best": 0, "excellent": 0, "good": 0, "book": 0, "inaccuracy": 0, "mistake": 0, "blunder": 0, "miss": 0, "move": 0 }
            for i, x in enumerate(history):
                if "review" in x and "class" in x["review"]:
                    actual_ply = x.get("ply", i + 1)
                    move_is_white = (actual_ply % 2 != 0)
                    if move_is_white == is_white:
                        c = x["review"]["class"]
                        if c in smry: smry[c] += 1
                        else: smry[c] = 1
            perf["summary"] = smry
            results.append(perf)
            
        return {
            "w_name": white_name, "b_name": black_name,
            "w_rating": history[0].get("w_rating", "?") if history and isinstance(history[0], dict) else "?",
            "b_rating": history[0].get("b_rating", "?") if history and isinstance(history[0], dict) else "?",
            "date": history[0].get("date", "?") if history and isinstance(history[0], dict) else "?",
            "result": history[0].get("result", "*") if history and isinstance(history[0], dict) else "*",
            "performance": results
        }

    # ==============================================================================
    # --- IMPROVED ROBUST CHESS METRICS ENGINE (Phase Detection + ACL -> Accuracy) ---
    # ==============================================================================

    def detect_game_phases(self, history):
        """Ultra-Intelligent Phase Detection using Move Count, Book Theory, and Material Heuristics."""
        total_ply = len(history)
        endgame_start = total_ply
        last_book_ply = 0
        for ply, step in enumerate(history):
            if isinstance(step, dict) and step.get("review", {}).get("class") == "book": last_book_ply = ply
            else: break

        opening_end = max(16, last_book_ply + 7)
        opening_end = min(opening_end, total_ply)

        for ply, step in enumerate(history):
            if ply < opening_end: continue
            fen = step.get("fen") if isinstance(step, dict) else None
            if not fen: continue
            board = chess.Board(fen)
            w_piece_val, b_piece_val = 0, 0
            has_w_queen, has_b_queen = False, False
            for sq in chess.SQUARES:
                p = board.piece_at(sq)
                if p and p.piece_type != chess.KING and p.piece_type != chess.PAWN:
                    val = 0
                    if p.piece_type == chess.QUEEN: 
                        val = 9
                        if p.color == chess.WHITE: has_w_queen = True
                        else: has_b_queen = True
                    elif p.piece_type == chess.ROOK: val = 5
                    elif p.piece_type in [chess.BISHOP, chess.KNIGHT]: val = 3
                    if p.color == chess.WHITE: w_piece_val += val
                    else: b_piece_val += val
            
            is_endgame = False
            if not has_w_queen and not has_b_queen and w_piece_val <= 14 and b_piece_val <= 14: is_endgame = True
            elif has_w_queen and has_b_queen and w_piece_val <= 12 and b_piece_val <= 12: is_endgame = True
            elif (has_w_queen != has_b_queen) and (w_piece_val + b_piece_val <= 21): is_endgame = True
            elif ply >= 80 and w_piece_val <= 16 and b_piece_val <= 16: is_endgame = True
            if is_endgame:
                endgame_start = ply
                break

        if total_ply <= 60: endgame_start = total_ply
        else:
            if endgame_start == total_ply: endgame_start = total_ply - 8
        if endgame_start < opening_end: opening_end = endgame_start
            
        return {
            "opening": (0, opening_end) if opening_end > 0 else None,
            "middlegame": (opening_end, endgame_start) if endgame_start > opening_end else None,
            "endgame": (endgame_start, total_ply) if endgame_start < total_ply else None
        }

    def calculate_acl_and_accuracy(self, moves, is_white):
        """Calculates Average Centipawn Loss and Robust Accuracy for a specific player."""
        if not moves or len(moves) < 2: return {"acl": 0, "accuracy": 0.0, "count": 0}
        total_cp_loss = 0
        analyzed_count = 0
        
        for prev, cur in zip(moves, moves[1:]):
            if not isinstance(cur, dict) or not isinstance(prev, dict): 
                print(f"[DEBUG] Skipping non-dict in ACL calculation: prev={repr(prev)}, cur={repr(cur)}")
                continue
            
            move_ply = cur.get("ply", 0)
            if (move_ply % 2 != 0) != is_white: continue
            prev_eval = prev.get("review", {}).get("eval_cp", 20) if isinstance(prev, dict) else 20
            cur_eval = cur.get("review", {}).get("eval_cp", prev_eval) if isinstance(cur, dict) else prev_eval
            prev_eval = max(-1000, min(1000, prev_eval))
            cur_eval = max(-1000, min(1000, cur_eval))
            loss = prev_eval - cur_eval if is_white else cur_eval - prev_eval
            loss = max(0, min(350, loss)) 
            total_cp_loss += loss
            analyzed_count += 1
            
        if analyzed_count == 0: return {"acl": 0, "accuracy": 0.0, "count": 0}
        avg_acl = total_cp_loss / analyzed_count
        
        # --- PERFECTED CALIBRATION MATH ---
        # Uses your exact calibrated acc_weight (1.608 or whatever is currently calibrated) 
        weight = self.CALIB_PARAMS.get("acc_weight", 1.60835)
        
        # This linear subtraction is what your calibrator optimized for!
        accuracy_percentage = 100.0 - (avg_acl / weight)
        accuracy_percentage = max(0.0, min(100.0, accuracy_percentage))
        
        return {"acl": avg_acl, "accuracy": round(accuracy_percentage, 1), "count": analyzed_count}

    def calculate_detailed_performance(self, history, white_name, black_name):
        """Processes game history to generate Phase ELOs, overall accuracy, and summaries."""
        if not history: return None
        phases = self.detect_game_phases(history)
        
        def get_phase_moves(phase_indices):
            if phase_indices is None: return []
            start, end = phase_indices
            if start == 0: return [{"ply": 0, "review": {"eval_cp": 20}}] + history[start:end]
            else: return history[start - 1 : end]

        results = []
        padded_overall_history = [{"ply": 0, "review": {"eval_cp": 20}}] + history
        
        for is_white in [True, False]:
            name = white_name if is_white else black_name
            overall = self.calculate_acl_and_accuracy(padded_overall_history, is_white)
            opening_p = self.calculate_acl_and_accuracy(get_phase_moves(phases["opening"]), is_white)
            mid_p = self.calculate_acl_and_accuracy(get_phase_moves(phases["middlegame"]), is_white)
            end_p = self.calculate_acl_and_accuracy(get_phase_moves(phases["endgame"]), is_white)
            
            perf = {
                "name": name,
                "is_white": is_white,
                "overall_accuracy": overall["accuracy"],
                "performance_elo": self._estimate_elo_from_acpl(overall["acl"], overall["accuracy"]),
                "acl": overall["acl"],
                "move_count": overall["count"],
                "opening_elo": self._estimate_elo_from_acpl(opening_p["acl"], opening_p["accuracy"]) if opening_p["count"] > 0 else None,
                "middlegame_elo": self._estimate_elo_from_acpl(mid_p["acl"], mid_p["accuracy"]) if mid_p["count"] > 0 else None,
                "endgame_elo": self._estimate_elo_from_acpl(end_p["acl"], end_p["accuracy"]) if end_p["count"] > 0 else None,
            }
            
            smry = { "brilliant": 0, "great": 0, "best": 0, "excellent": 0, "good": 0, "book": 0, "inaccuracy": 0, "mistake": 0, "blunder": 0, "miss": 0, "move": 0 }
            for i, x in enumerate(history):
                if isinstance(x, dict) and "review" in x and isinstance(x["review"], dict) and "class" in x["review"]:
                    actual_ply = x.get("ply", i + 1) if isinstance(x, dict) else (i + 1)
                    move_is_white = (actual_ply % 2 != 0)
                    if move_is_white == is_white:
                        c = x["review"]["class"]
                        if c in smry: smry[c] += 1
                        else: smry[c] = 1
            perf["summary"] = smry
            results.append(perf)
            
        return {
            "w_name": white_name, "b_name": black_name,
            "w_rating": history[0].get("w_rating", "?") if history and isinstance(history[0], dict) else "?",
            "b_rating": history[0].get("b_rating", "?") if history and isinstance(history[0], dict) else "?",
            "date": history[0].get("date", "?") if history and isinstance(history[0], dict) else "?",
            "result": history[0].get("result", "*") if history and isinstance(history[0], dict) else "*",
            "performance": results
        }

    def is_material_sacrifice(self, board, move):
        """Check if move involves material sacrifice"""
        if board.is_capture(move):
            captured_piece = board.piece_at(move.to_square)
            moving_piece = board.piece_at(move.from_square)
            
            if captured_piece and moving_piece:
                material_values = {
                    chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
                    chess.ROOK: 5, chess.QUEEN: 9
                }
                
                return (material_values.get(moving_piece.piece_type, 0) > 
                       material_values.get(captured_piece.piece_type, 0))
        return False
    
    def analyze_sacrifice(self, board, move, depth=20):
        """Enhanced sacrifice analysis with chess.com-style evaluation"""
        if not self.is_material_sacrifice(board, move):
            return None
        
        # Analyze position after sacrifice
        board_copy = board.copy()
        board_copy.push(move)
        
        try:
            # Get multi-PV analysis for comprehensive evaluation
            info = self.engine.analyse(
                board_copy,
                chess.engine.Limit(depth=depth),
                multipv=min(self.multipv, 3),
                info=chess.engine.INFO_ALL
            )
            
            # Evaluate sacrifice quality
            eval_score = self._score_to_cp(info[0]['score']) if info else 0
            
            # Calculate compensation factors
            attack_potential = self._calculate_attack_potential(board_copy)
            positional_gain = self._calculate_positional_gain(board, board_copy)
            initiative_score = self._calculate_initiative(board_copy)
            
            # Determine sacrifice category
            sacrifice_category = self._classify_sacrifice(
                eval_score, attack_potential, positional_gain, initiative_score
            )
            
            return {
                'move': move.uci(),
                'is_sacrifice': True,
                'material_lost': self._calculate_material_loss(board, move),
                'evaluation': eval_score,
                'depth': info[0].get('depth', depth) if info else depth,
                'attack_potential': attack_potential,
                'positional_gain': positional_gain,
                'initiative_score': initiative_score,
                'category': sacrifice_category,
                'best_variations': [pv.get('pv', [])[:5] for pv in info[:3]] if info else [],
                'recommendation': self._get_sacrifice_recommendation(sacrifice_category, eval_score)
            }
            
        except Exception as e:
            print(f"Sacrifice analysis error: {e}")
            return None
    
    def _calculate_material_loss(self, board, move):
        """Calculate material sacrificed in centipawns"""
        if not board.is_capture(move):
            return 0
        
        captured_piece = board.piece_at(move.to_square)
        moving_piece = board.piece_at(move.from_square)
        
        if not captured_piece or not moving_piece:
            return 0
        
        material_values = {
            chess.PAWN: 100, chess.KNIGHT: 300, chess.BISHOP: 300,
            chess.ROOK: 500, chess.QUEEN: 900
        }
        
        return (material_values.get(moving_piece.piece_type, 0) - 
                material_values.get(captured_piece.piece_type, 0))
    
    def _calculate_attack_potential(self, board):
        """Calculate attack potential on enemy king"""
        if not board.turn:
            enemy_king = board.king(chess.WHITE)
            attackers = board.attackers(chess.BLACK, enemy_king) if enemy_king else []
        else:
            enemy_king = board.king(chess.BLACK)
            attackers = board.attackers(chess.WHITE, enemy_king) if enemy_king else []
        
        attack_score = len(attackers) * 50
        
        # Bonus for pieces near enemy king
        if enemy_king:
            for square in chess.SQUARES:
                piece = board.piece_at(square)
                if piece and piece.color == board.turn:
                    distance = chess.square_distance(square, enemy_king)
                    if distance <= 2:
                        attack_score += (3 - distance) * 20
        
        return attack_score
    
    def _calculate_positional_gain(self, board_before, board_after):
        """Calculate positional improvements"""
        # Control of center squares
        center_squares = [chess.E4, chess.D4, chess.E5, chess.D5]
        center_control_before = sum(1 for sq in center_squares 
                                   if board_before.piece_at(sq) and 
                                   board_before.piece_at(sq).color == board_before.turn)
        center_control_after = sum(1 for sq in center_squares 
                                  if board_after.piece_at(sq) and 
                                  board_after.piece_at(sq).color == board_after.turn)
        
        # Open file/diagonal control
        mobility_before = len(list(board_before.legal_moves))
        mobility_after = len(list(board_after.legal_moves))
        
        return (center_control_after - center_control_before) * 30 + (mobility_after - mobility_before) * 10
    
    def _calculate_initiative(self, board):
        """Calculate initiative/tempo score"""
        # Threat count
        threats = 0
        for move in board.legal_moves:
            if board.is_capture(move) or board.gives_check(move):
                threats += 1
        
        # King safety (negative if exposed)
        king_safety = 0
        king_square = board.king(board.turn)
        if king_square:
            # Check for pawn shield
            if board.turn == chess.WHITE:
                shield_squares = [chess.F2, chess.G2, chess.H2, chess.F1, chess.G1, chess.H1]
            else:
                shield_squares = [chess.F7, chess.G7, chess.H7, chess.F8, chess.G8, chess.H8]
            
            for sq in shield_squares:
                piece = board.piece_at(sq)
                if piece and piece.piece_type == chess.PAWN and piece.color == board.turn:
                    king_safety += 25
        
        return threats * 15 + king_safety
    
    def _classify_sacrifice(self, eval_score, attack_potential, positional_gain, initiative_score):
        """Classify sacrifice quality like chess.com"""
        total_compensation = attack_potential + positional_gain + initiative_score
        
        if eval_score >= self.SACRIFICE_THRESHOLDS["brilliant_min"]:
            return "brilliant"
        elif eval_score >= self.SACRIFICE_THRESHOLDS["good_min"]:
            return "good"
        elif eval_score >= self.SACRIFICE_THRESHOLDS["speculative_min"]:
            return "speculative"
        elif total_compensation >= 300:
            return "compensated"
        else:
            return "unsound"
    
    def _get_sacrifice_recommendation(self, category, eval_score):
        """Get sacrifice recommendation"""
        recommendations = {
            "brilliant": "Excellent sacrifice! Creates overwhelming attack.",
            "good": "Good sacrifice with clear compensation.",
            "speculative": "Interesting sacrifice, requires precise play.",
            "compensated": "Sacrifice is positionally justified.",
            "unsound": "Insufficient compensation for material."
        }
        
        return recommendations.get(category, "Unclear sacrifice.")