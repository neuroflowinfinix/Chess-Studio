import chess.pgn
import sqlite3
import os
import time
import sys

def build_explorer_database(pgn_path="assets/database/database.pgn", db_path="assets/database/explorer.sqlite"):
    print("Igniting Unrestricted Grandmaster Database Builder...")
    
    if not os.path.exists(pgn_path):
        print(f"[!] Error: Could not find {pgn_path}. Please place your PGN here.")
        return

    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    conn = sqlite3.connect(db_path, isolation_level=None) 
    c = conn.cursor()
    # Your settings have been left entirely untouched
    c.execute('PRAGMA synchronous = OFF')
    c.execute('PRAGMA journal_mode = MEMORY')
    c.execute('PRAGMA temp_store = MEMORY')
    c.execute('PRAGMA cache_size = 100000') 
    
    c.execute('BEGIN TRANSACTION')
    c.execute('CREATE TABLE IF NOT EXISTS position_stats (fen TEXT, move TEXT, white_wins INTEGER, draws INTEGER, black_wins INTEGER, PRIMARY KEY (fen, move))')
    c.execute('CREATE TABLE IF NOT EXISTS top_games (fen TEXT, white_player TEXT, black_player TEXT, white_elo INTEGER, black_elo INTEGER, result TEXT, date TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS build_state (id INTEGER PRIMARY KEY, last_byte INTEGER)')
    c.execute('COMMIT')
    
    c.execute('SELECT last_byte FROM build_state WHERE id=1')
    row = c.fetchone()
    resume_byte = row[0] if row else 0

    total_bytes = os.path.getsize(pgn_path)
    start_time = time.time()
    games_processed = 0
    positions_saved = 0
    
    if resume_byte > 0:
        print(f"[*] Resuming from previous save state (Byte: {resume_byte:,} / {total_bytes:,})...")

    c.execute('BEGIN TRANSACTION')
    
    with open(pgn_path, 'r', encoding="utf-8", errors="ignore") as f:
        if resume_byte > 0: f.seek(resume_byte)
            
        while True:
            game = chess.pgn.read_game(f)
            if game is None: break
            
            headers = game.headers
            w_elo_str = headers.get("WhiteElo", "?")
            b_elo_str = headers.get("BlackElo", "?")
            w_elo = int(w_elo_str) if w_elo_str.isdigit() else 0
            b_elo = int(b_elo_str) if b_elo_str.isdigit() else 0
            
            result = headers.get("Result", "*")
            w_win = 1 if result == "1-0" else 0
            draw = 1 if result == "1/2-1/2" else 0
            b_win = 1 if result == "0-1" else 0
            
            # --- THE FIX: Wrap board logic to catch "invalid position" and illegal moves ---
            try:
                board = game.board()
                
                # Deep Indexing: First 40 ply (20 full moves)
                for i, move in enumerate(game.mainline_moves()):
                    if i > 40: break 
                    
                    fen_key = " ".join(board.fen().split(" ")[:4])
                    san_move = board.san(move)
                    
                    c.execute('''INSERT INTO position_stats (fen, move, white_wins, draws, black_wins) 
                                 VALUES (?, ?, ?, ?, ?)
                                 ON CONFLICT(fen, move) DO UPDATE SET 
                                 white_wins=white_wins+?, draws=draws+?, black_wins=black_wins+?''', 
                              (fen_key, san_move, w_win, draw, b_win, w_win, draw, b_win))
                    
                    if (w_elo >= 2200 and b_elo >= 2200) or (w_elo == 0 and b_elo == 0):
                        try:
                            c.execute('INSERT INTO top_games VALUES (?, ?, ?, ?, ?, ?, ?)',
                                      (fen_key, headers.get("White","?"), headers.get("Black","?"), w_elo, b_elo, result, headers.get("Date","?")))
                            positions_saved += 1
                        except Exception: pass
                    
                        board.push(move)
            except Exception:
                # If the PGN data is corrupt, silently skip the rest of the game and move on
                pass
                
            games_processed += 1
            
            if games_processed % 500 == 0:
                current_position = f.tell() # Capture position AFTER reading the game
                progress = current_position / total_bytes
                elapsed_time = time.time() - start_time
                progress_made = max(0.0001, (current_position - resume_byte) / max(1, (total_bytes - resume_byte)))
                eta_seconds = (elapsed_time / progress_made) - elapsed_time if progress_made > 0 else 0
                
                m, s = divmod(int(eta_seconds), 60)
                h, m = divmod(m, 60)
                eta_str = f"{h}h {m}m {s}s" if h > 0 else f"{m}m {s}s"
                
                bar_length = 30
                filled_len = int(bar_length * progress)
                bar = '█' * filled_len + '-' * (bar_length - filled_len)
                
                sys.stdout.write(f'\r[{bar}] {progress*100:.1f}% | Games: {games_processed:,} | Positions: {positions_saved:,} | ETA: {eta_str} ')
                sys.stdout.flush()
                
                if games_processed % 5000 == 0:
                    # Save the byte offset of the NEXT game so you don't double-count on resume
                    c.execute('REPLACE INTO build_state (id, last_byte) VALUES (1, ?)', (current_position,))
                    c.execute('COMMIT')
                    c.execute('BEGIN TRANSACTION')

    c.execute('REPLACE INTO build_state (id, last_byte) VALUES (1, ?)', (total_bytes,))
    c.execute('COMMIT')

    sys.stdout.write('\n\n[100%] Parsing complete! Building ultra-fast search indexes (this takes a moment)...')
    sys.stdout.flush()
    
    c.execute('CREATE INDEX IF NOT EXISTS idx_stats_fen ON position_stats(fen)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_games_fen ON top_games(fen)')
    c.execute('VACUUM')
    
    conn.close()
    
    total_time = time.time() - start_time
    m, s = divmod(int(total_time), 60)
    print(f"\nDatabase built successfully in {m}m {s}s! Indexed {positions_saved} searchable board positions.")

if __name__ == "__main__":
    build_explorer_database()
