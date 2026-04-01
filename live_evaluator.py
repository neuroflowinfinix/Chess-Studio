import chess
import chess.engine
import time
from analysis_engine import AnalysisEngine


class LiveEvaluator:
    """Helper wrapping AnalysisEngine for live-in-game evaluation using a small buffer.

    Usage:
      le = LiveEvaluator(engine_path)
      label = le.evaluate_move(board_before, move, time_for_analysis=0.3)
    """

    def __init__(self, engine_path, model=True):
        self.ae = AnalysisEngine(engine_path=engine_path)
        # ensure engine not started inside AnalysisEngine unless required
        self.engine_path = engine_path
        self._engine = None
        self.model_enabled = model and getattr(self.ae, 'feature_model', None) is not None

    def _start_engine(self):
        if self._engine is None:
            self._engine = chess.engine.SimpleEngine.popen_uci(self.engine_path)
            
            # --- FIX: Auto-load custom .bin Evaluation Files ---
            import os
            eval_dir = os.path.abspath(os.path.join("assets", "evaluationfiles"))
            if os.path.exists(eval_dir):
                for f in os.listdir(eval_dir):
                    # ONLY load .nnue files into Stockfish!
                    if f.endswith(".nnue"):
                        # Force forward slashes so Stockfish's C++ parser doesn't break
                        bin_path = os.path.join(eval_dir, f).replace("\\", "/")
                        
                        try:
                            # Tell Stockfish to use the specific custom neural network!
                            self._engine.configure({"EvalFile": bin_path})
                            print(f"[+] Successfully loaded custom NNUE: {f}")
                            break  # Load the first one found
                        except Exception as e:
                            print(f"[!] Engine rejected {f}. Reason: {e}")

            # --- ENGINE CONFIGURATION (NNUE, SYZYGY, CPU SAFEGUARD) ---
            import multiprocessing
            config = {}
            
            # Leave 2 cores free so the UI and Main Engine never lag!
            safe_threads = max(1, multiprocessing.cpu_count() - 2) 
            if "Threads" in self._engine.options: config["Threads"] = safe_threads
            if "Use NNUE" in self._engine.options: config["Use NNUE"] = True
            
            syzygy_path = os.path.abspath(os.path.join("assets", "syzygy"))
            if "SyzygyPath" in self._engine.options and os.path.exists(syzygy_path):
                config["SyzygyPath"] = syzygy_path
                if "SyzygyProbeDepth" in self._engine.options: config["SyzygyProbeDepth"] = 1
                if "Syzygy50MoveRule" in self._engine.options: config["Syzygy50MoveRule"] = True
            
            try: self._engine.configure(config)
            except Exception as e: print(f"[!] Live Config Error: {e}")

    def _stop_engine(self):
        if self._engine is not None:
            try:
                self._engine.quit()
            except Exception:
                pass
            self._engine = None

    def evaluate_move(self, board_before, move, time_for_analysis=0.3, multipv=3):
        self._start_engine()
        
        # --- FIX: Safe Centipawn Extractor ---
        def safe_cp(info_obj, is_turn_black):
            if not info_obj: return None
            try:
                io = info_obj[0] if isinstance(info_obj, list) else info_obj
                sc = io['score'].white()
                if sc.is_mate():
                    m = sc.mate()
                    if m > 0: return 10000 - m * 100
                    elif m < 0: return -10000 - m * 100
                    else: return 10000 if is_turn_black else -10000
                return int(sc.score())
            except:
                return None

        try:
            # --- CPU SAFEGUARD & NNUE MULTIPV ---
            # Depth 16 prevents CPU burn on simple/endgame positions!
            limit_before = chess.engine.Limit(time=time_for_analysis/2, depth=16)
            info_before = self._engine.analyse(board_before, limit_before, multipv=3)
        except Exception:
            info_before = None

        prev_cp = safe_cp(info_before, board_before.turn == chess.BLACK)
        
        best_gap = 0
        if isinstance(info_before, list) and len(info_before) > 1 and prev_cp is not None:
            try:
                sc1 = info_before[1]['score'].white()
                if sc1.is_mate():
                    m1 = sc1.mate()
                    sc1_cp = 10000 - m1 * 100 if m1 > 0 else (-10000 - m1 * 100 if m1 < 0 else (10000 if board_before.turn == chess.BLACK else -10000))
                else:
                    sc1_cp = int(sc1.score())
                best_gap = abs(prev_cp - sc1_cp)
            except: pass

        board_after = board_before.copy()
        board_after.push(move)

        try:
            # --- CPU SAFEGUARD ---
            limit_after = chess.engine.Limit(time=time_for_analysis/2, depth=16)
            info_after = self._engine.analyse(board_after, limit_after, multipv=1)
        except Exception:
            info_after = None

        curr_cp = safe_cp(info_after, board_after.turn == chess.BLACK)

        label = self.ae.classify_move(move, board_before, board_after, prev_cp, curr_cp, best_move=None)

        try:
            self.ae._live_prev_cp = curr_cp if curr_cp is not None else getattr(self.ae, '_live_prev_cp', 0)
            self.ae._live_prev_best_gap = best_gap if best_gap else getattr(self.ae, '_live_prev_best_gap', 0)
        except: pass

        return label

    def stop(self):
        self._stop_engine()
