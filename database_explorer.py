import chess
import chess.pgn
import sqlite3
import os
import threading
import pygame

class OpeningExplorer:
    def __init__(self, db_path="assets/database/explorer.sqlite"):
        self.db_path = db_path
        self.is_fetching = False
        self.current_results = None
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS position_stats (
                        fen TEXT, move TEXT, 
                        white_wins INTEGER, draws INTEGER, black_wins INTEGER,
                        PRIMARY KEY (fen, move))''')
        c.execute('''CREATE TABLE IF NOT EXISTS top_games (
                        fen TEXT, white_player TEXT, black_player TEXT, 
                        white_elo INTEGER, black_elo INTEGER, 
                        result TEXT, date TEXT)''')
        c.execute('CREATE INDEX IF NOT EXISTS idx_stats_fen ON position_stats(fen)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_games_fen ON top_games(fen)')
        conn.commit()
        conn.close()

    def fetch_position_async(self, board):
        if self.is_fetching: return
        self.is_fetching = True
        self.current_results = None 
        fen_key = " ".join(board.fen().split(" ")[:4]) 
        threading.Thread(target=self._query_db, args=(fen_key,), daemon=True).start()

    def _query_db(self, fen_key):
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            c.execute('SELECT move, white_wins, draws, black_wins FROM position_stats WHERE fen=?', (fen_key,))
            moves_data = c.fetchall()
            
            c.execute('''SELECT white_player, black_player, white_elo, black_elo, result, date 
                         FROM top_games WHERE fen=? ORDER BY (white_elo + black_elo) DESC LIMIT 15''', (fen_key,))
            games_data = c.fetchall()
            conn.close()
            
            total_position_games = sum([m[1] + m[2] + m[3] for m in moves_data])
            stats = []
            for m in moves_data:
                total_move = m[1] + m[2] + m[3]
                stats.append({
                    "move": m[0], "total": total_move,
                    "w_pct": m[1] / total_move, "d_pct": m[2] / total_move, "l_pct": m[3] / total_move
                })
            stats.sort(key=lambda x: x["total"], reverse=True)
            
            self.current_results = {"total_games": total_position_games, "moves": stats, "top_games": games_data}
        except Exception as e:
            print(f"Explorer Error: {e}")
            self.current_results = {"error": True}
        finally:
            self.is_fetching = False

class ExplorerUI:
    def __init__(self, font_small, font_medium):
        self.font_small = font_small
        self.font_medium = font_medium
        self.is_open = False
        self.scroll_y = 0
        
        self.rect = pygame.Rect(0, 0, 850, 600) # Increased Width to 850!
        
        self.COLOR_W = (76, 175, 80)   
        self.COLOR_D = (144, 148, 151) 
        self.COLOR_L = (244, 67, 54)   

    def handle_event(self, event, explorer_db, current_board):
        if not self.is_open: return False
        
        # Only handling scroll wheel now, the button is gone!
        if event.type == pygame.MOUSEBUTTONDOWN:
            mouse_pos = event.pos
            if self.rect.collidepoint(mouse_pos):
                if event.button == 4: self.scroll_y = max(0, self.scroll_y - 40) 
                if event.button == 5: self.scroll_y += 40 
                return True
        return False

    def draw_wdl_bar(self, surface, x, y, width, height, w_pct, d_pct, l_pct):
        w_width = int(width * w_pct)
        d_width = int(width * d_pct)
        l_width = width - w_width - d_width 

        if w_width > 0:
            pygame.draw.rect(surface, self.COLOR_W, (x, y, w_width, height), border_top_left_radius=5, border_bottom_left_radius=5)
        if d_width > 0:
            pygame.draw.rect(surface, self.COLOR_D, (x + w_width, y, d_width, height))
        if l_width > 0:
            pygame.draw.rect(surface, self.COLOR_L, (x + w_width + d_width, y, l_width, height), border_top_right_radius=5, border_bottom_right_radius=5)
            
        if w_width > 35:
            wt = self.font_small.render(f"{w_pct*100:.1f}%", True, (255,255,255))
            surface.blit(wt, (x + w_width//2 - wt.get_width()//2, y + 2))
        if d_width > 35:
            dt = self.font_small.render(f"{d_pct*100:.1f}%", True, (255,255,255))
            surface.blit(dt, (x + w_width + d_width//2 - dt.get_width()//2, y + 2))
        if l_width > 35:
            lt = self.font_small.render(f"{l_pct*100:.1f}%", True, (255,255,255))
            surface.blit(lt, (x + w_width + d_width + l_width//2 - lt.get_width()//2, y + 2))

    def draw(self, screen, explorer_db):
        if not self.is_open: return

        res = explorer_db.current_results
        if res and "error" not in res and res["total_games"] > 0:
            inner_h = 100 + (len(res["moves"]) * 70) + 70 + (len(res["top_games"]) * 32) + 30
        else:
            inner_h = 200 

        screen_w, screen_h = screen.get_size()
        self.rect.w = 850
        self.rect.h = min(screen_h - 100, inner_h + 20) 
        self.rect.x = (screen_w - self.rect.w) // 2
        self.rect.y = (screen_h - self.rect.h) // 2

        panel_surface = pygame.Surface((self.rect.w, self.rect.h), pygame.SRCALPHA)
        pygame.draw.rect(panel_surface, (250, 250, 252, 245), (0, 0, self.rect.w, self.rect.h), border_radius=12)
        pygame.draw.rect(panel_surface, (180, 180, 190, 255), (0, 0, self.rect.w, self.rect.h), width=2, border_radius=12)

        inner_surf = pygame.Surface((self.rect.w - 20, inner_h), pygame.SRCALPHA)
        y_offset = 20
        
        # New sleek loading state (No Button)
        if explorer_db.current_results is None or explorer_db.is_fetching:
            txt_surf = self.font_medium.render("Loading Grandmaster Database...", True, (80, 80, 80))
            inner_surf.blit(txt_surf, ((self.rect.w - 20)//2 - txt_surf.get_width()//2, y_offset + 30))
        else:
            if "error" in res or res["total_games"] == 0:
                txt = self.font_medium.render("No games found in database for this exact position.", True, (180, 50, 50))
                inner_surf.blit(txt, (40, y_offset + 20))
            else:
                hdr = self.font_medium.render(f"{res['total_games']:,} Master Games Reached This Setup", True, (80, 80, 80))
                inner_surf.blit(hdr, (30, y_offset))
                y_offset += 50
                
                for move in res["moves"]:
                    m_txt = self.font_medium.render(f"{move['move']}  ({move['total']:,})", True, (30, 30, 30))
                    inner_surf.blit(m_txt, (30, y_offset))
                    self.draw_wdl_bar(inner_surf, 30, y_offset + 25, self.rect.w - 80, 24, move["w_pct"], move["d_pct"], move["l_pct"])
                    y_offset += 75
                    
                pygame.draw.line(inner_surf, (210, 210, 220), (30, y_offset), (self.rect.w - 50, y_offset))
                y_offset += 20
                
                hdr_games = self.font_medium.render("Top Grandmaster Games", True, (180, 120, 0))
                inner_surf.blit(hdr_games, (30, y_offset))
                y_offset += 40
                
                # WIDENED COLUMNS
                pygame.draw.rect(inner_surf, (235, 235, 240), (30, y_offset, self.rect.w - 80, 30), border_radius=4)
                c_w = self.font_small.render("White Player", True, (120, 120, 120))
                c_b = self.font_small.render("Black Player", True, (120, 120, 120))
                c_r = self.font_small.render("Result (Year)", True, (120, 120, 120))
                
                # Spread out to utilize the new 850px width
                inner_surf.blit(c_w, (40, y_offset + 5))
                inner_surf.blit(c_b, (350, y_offset + 5))
                inner_surf.blit(c_r, (660, y_offset + 5))
                y_offset += 40
                
                for g in res["top_games"]:
                    w_name, b_name, w_elo, b_elo, result, date = g
                    
                    w_n = w_name if w_name not in ["?", ""] else "--"
                    b_n = b_name if b_name not in ["?", ""] else "--"
                    w_e = f" ({w_elo})" if w_elo > 0 else ""
                    b_e = f" ({b_elo})" if b_elo > 0 else ""
                    year = date.split(".")[0] if date and date != "?" else "----"
                    
                    # Allowed longer names since we have more room now!
                    t_white = self.font_small.render(f"{w_n[:25]}{w_e}", True, (50, 50, 50))
                    t_black = self.font_small.render(f"{b_n[:25]}{b_e}", True, (50, 50, 50))
                    
                    r_col = self.COLOR_W if result == "1-0" else self.COLOR_L if result == "0-1" else self.COLOR_D
                    t_res = self.font_small.render(f"{result} ({year})", True, r_col)
                    
                    inner_surf.blit(t_white, (40, y_offset))
                    inner_surf.blit(t_black, (350, y_offset))
                    inner_surf.blit(t_res, (660, y_offset))
                    y_offset += 32

        panel_surface.blit(inner_surf, (10, 10), area=pygame.Rect(0, self.scroll_y, self.rect.w - 20, self.rect.h - 20))
        screen.blit(panel_surface, (self.rect.x, self.rect.y))