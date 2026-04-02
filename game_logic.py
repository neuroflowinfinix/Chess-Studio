import chess
import chess.pgn
import re

class GameLogic:
    """
    The Central Brain for Chess Rules & State Management.
    Ensures fail-safe move validation, history tracking, and game status checks.
    """
    
    def __init__(self):
        self.board = chess.Board()
        self.history = []  # List of dicts: {'move', 'san', 'fen', 'review'}
        self.view_ply = 0  # Support for reviewing past moves (Undo/Redo view)
        self.material_advantage = 0
        self.pgn_metadata = {} # Stores 'Engine', 'Depth', 'Time' etc.
        
        # Standard Piece Values for Material Calculation
        self.PIECE_VALUES = {
            chess.PAWN: 1,
            chess.KNIGHT: 3,
            chess.BISHOP: 3,
            chess.ROOK: 5,
            chess.QUEEN: 9,
            chess.KING: 0
        }

    def reset_game(self):
        """Resets the board and clears history for a new game."""
        self.board.reset()
        self.history = []
        self.view_ply = 0
        self.material_advantage = 0
        self.pgn_metadata = {}

    def load_fen(self, fen):
        """Safely loads a specific board state from a FEN string."""
        try:
            self.board.set_fen(fen)
            self.history = [] # History is lost on manual FEN set
            self.view_ply = self.board.ply()
            self.calculate_material()
        except ValueError:
            pass # Invalid FEN ignored
            
    def analyze_tactical_event(self, move):
        """
        Secretly looks one move into the future to detect tactical geometries
        like Forks, Pins, Discovered Attacks, and Checks.
        Returns a string event tag (e.g. 'fork', 'pin', 'checkmate').
        """
        if not move: return None
        
        # 1. Base Flags (These must be checked BEFORE the move is pushed)
        is_capture = self.board.is_capture(move)
        is_en_passant = self.board.is_en_passant(move)
        is_castle = self.board.is_castling(move)
        is_promotion = bool(move.promotion)
        
        # 2. PUSH THE MOVE (Look into the future)
        self.board.push(move)
        
        event = None
        try:
            opponent = self.board.turn # After push, it is the opponent's turn
            moved_piece = self.board.piece_at(move.to_square)
            
            # --- A. Mates & Checks ---
            if self.board.is_checkmate():
                event = "checkmate"
            elif self.board.is_check():
                if len(self.board.checkers()) > 1:
                    event = "double_check"
                elif move.to_square not in self.board.checkers():
                    event = "discovered_check"
                else:
                    event = "check"
                    
            # --- B. Positional Tactics (Forks & Pins) ---
            if not event and moved_piece:
                # Fork Detection: The piece that just moved now attacks 2+ valuable targets
                attacks = self.board.attacks(move.to_square)
                valuable_targets = 0
                for sq in attacks:
                    target_piece = self.board.piece_at(sq)
                    # Count attacked opponent pieces: exclude pawns, but king only counts
                    # if it's the sole check source (avoid double-tagging checked positions as forks)
                    if target_piece and target_piece.color == opponent:
                        if target_piece.piece_type == chess.PAWN:
                            continue
                        if target_piece.piece_type == chess.KING and self.board.is_check():
                            continue  # King already flagged as check above; don't double-count
                        valuable_targets += 1

                if valuable_targets >= 2:
                    event = "fork"
                    
                # Pin Detection: The sliding piece that just moved is now pinning an enemy piece
                if not event and moved_piece.piece_type in [chess.BISHOP, chess.ROOK, chess.QUEEN]:
                    for sq in attacks:
                        p = self.board.piece_at(sq)
                        if p and p.color == opponent and self.board.is_pinned(opponent, sq):
                            event = "pin"

            # --- C. Standard Actions (Fallbacks) ---
            if not event:
                if is_en_passant: event = "en_passant"
                elif is_castle: event = "castle"
                elif is_promotion: event = "promote"
                elif is_capture: event = "capture"
        except Exception as e:
            print(f"[analyze_tactical_event] Error during analysis: {e}")
            event = None
        finally:
            # 3. POP THE MOVE (Restore the board — guaranteed even on exception)
            self.board.pop()
        
        return event
        
        return event

    def validate_move(self, from_sq, to_sq, promotion=None):
        """
        Checks if a move from 'from_sq' to 'to_sq' is legal.
        Handles Promotion. If promotion is missing but required, returns special flag.
        """
        # 1. Create Basic Move
        move = chess.Move(from_sq, to_sq, promotion=promotion)
        
        # 2. Check for Promotion requirement
        p = self.board.piece_at(from_sq)
        if p and p.piece_type == chess.PAWN:
            rank = chess.square_rank(to_sq)
            if (p.color == chess.WHITE and rank == 7) or (p.color == chess.BLACK and rank == 0):
                if promotion is None:
                    # Check if legal with queen (just to see if move geometry is valid)
                    test_move = chess.Move(from_sq, to_sq, promotion=chess.QUEEN)
                    if test_move in self.board.legal_moves:
                        return "PROMOTION_NEEDED" # Signal UI to ask user
        
        # 3. Validate against legal moves
        if move in self.board.legal_moves:
            return move
        return None

    def apply_move(self, move):
        """
        Executes a move, updates history, and recalculates material.
        Returns True if successful, False if illegal.
        """
        if move in self.board.legal_moves:
            # 1. Get Notation (SAN) before pushing
            san = self.board.san(move)
            
            # 2. Update Board
            self.board.push(move)
            
            # 3. Update History
            self.history.append({
                "move": move,
                "san": san,
                "fen": self.board.fen()
                # "review" key is added later by the Analysis Engine in main.py
            })
            self.view_ply = self.board.ply()
            
            # 4. Update Material Count
            self.calculate_material()
            return True
        return False

    def calculate_material(self):
        """
        Calculates material difference (White - Black).
        Used for the 'Material Advantage' display (e.g., +3).
        """
        w_score = 0
        b_score = 0
        
        for square in chess.SQUARES:
            piece = self.board.piece_at(square)
            if piece:
                val = self.PIECE_VALUES.get(piece.piece_type, 0)
                if piece.color == chess.WHITE:
                    w_score += val
                else:
                    b_score += val
        
        self.material_advantage = w_score - b_score
        return self.material_advantage

    def get_game_status_text(self):
        """
        Returns the text string for overlays (CHECK, DRAW, etc.).
        """
        if self.board.is_checkmate():
            return "CHECKMATE"
        elif self.board.is_stalemate():
            return "DRAW (Stalemate)"
        elif self.board.is_insufficient_material():
            return "DRAW (Material)"
        elif self.board.is_seventy_five_moves():
            return "DRAW (75 Moves)"
        elif self.board.is_fivefold_repetition():
            return "DRAW (Repetition)"
        elif self.board.is_check():
            return "CHECK"
        return None

    def is_game_over(self):
        return self.board.is_game_over()

    def undo_last_move(self):
        """ safely undoes the last move if possible. """
        if len(self.history) > 0:
            self.board.pop()
            self.history.pop()
            self.view_ply = self.board.ply()
            self.calculate_material()
            return True
        return False

    def export_pgn(self, history=None, white_name="Player", black_name="Stockfish", headers=None):
        """
        Returns a string representation of the current game in PGN format.
        Includes evaluation data in comments if available.
        """
        game = chess.pgn.Game()
        game.headers["Event"] = "Chess Studio Game"
        game.headers["White"] = white_name
        game.headers["Black"] = black_name
        
        if headers:
            for k, v in headers.items():
                game.headers[k] = v
        
        # Add Analysis Metadata
        if self.pgn_metadata:
            for k, v in self.pgn_metadata.items():
                game.headers[k] = str(v)

        # Build the PGN tree
        node = game
        
        # --- FIX: Use the fully annotated history passed from main.py ---
        hist_to_use = history if history is not None else self.history
        
        for h in hist_to_use:
            if not isinstance(h, dict): continue
            
            move = h.get("move")
            if not move: continue
            
            node = node.add_variation(move)
            
            # Preserve Legacy NAGs if they exist
            if "nags" in h and h["nags"]:
                for nag in h["nags"]: node.nags.add(nag)
            
            # Inject Review Data as Comments
            if "review" in h and h["review"]:
                rev = h["review"]
                comment_parts = []

                # Prefer numeric eval if available
                if isinstance(rev.get("eval_cp"), (int, float)):
                    try:
                        val = rev["eval_cp"] / 100.0
                        comment_parts.append(f"[%eval {val:+.2f}]")
                    except Exception:
                        pass
                # Fallback: use formatted eval string if present
                elif rev.get("eval_str"):
                    sval = rev.get("eval_str")
                    comment_parts.append(f"[%eval {sval}]")

                # Classification tag (This ensures our PNG icons load next time!)
                if rev.get("class"):
                    comment_parts.append(f"[%class {rev.get('class')}]")

                # Human readable score / reason
                if rev.get("bot_reason"):
                    comment_parts.append(rev.get("bot_reason"))
                elif rev.get("reason"):
                    comment_parts.append(rev.get("reason"))

                if comment_parts:
                    node.comment = " ".join([c for c in comment_parts if c])
        
        return str(game)