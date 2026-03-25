import pygame
import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import time
import os
import json
from account_manager import ChessAccountManager, GameChatAnalyzer, NetworkStatusMonitor

class AccountPopup:
    def __init__(self, app):
        self.app = app
        self.active = True
        
        # Increased size to fit URL import and Local Files list
        w, h = 750, 720
        self.rect = pygame.Rect((app.width - w)//2, (app.height - h)//2, w, h)
        
        self.account_manager = ChessAccountManager()
        self.network_monitor = NetworkStatusMonitor()
        
        self.font_title = self.app.font_b if hasattr(self.app, 'font_b') else pygame.font.SysFont("Segoe UI", 20, bold=True)
        self.font_header = self.app.font_m if hasattr(self.app, 'font_m') else pygame.font.SysFont("Segoe UI", 16, bold=True)
        self.font_normal = self.app.font_m if hasattr(self.app, 'font_m') else pygame.font.SysFont("Segoe UI", 14)
        self.font_small = self.app.font_s if hasattr(self.app, 'font_s') else pygame.font.SysFont("Segoe UI", 12)
        
        self.buttons = {
            'close': pygame.Rect(self.rect.x + self.rect.w - 40, self.rect.y + 10, 30, 30),
            'chess_com_connect': pygame.Rect(self.rect.x + 440, self.rect.y + 70, 120, 35),
            'lichess_connect': pygame.Rect(self.rect.x + 440, self.rect.y + 160, 120, 35),
            'download_chess_com': pygame.Rect(self.rect.x + 580, self.rect.y + 70, 120, 35),
            'download_lichess': pygame.Rect(self.rect.x + 580, self.rect.y + 160, 120, 35),
            'download_url': pygame.Rect(self.rect.x + 580, self.rect.y + 250, 120, 35)
        }
        
        self.chess_com_input = ""
        self.lichess_input = ""
        self.url_input = ""
        self.active_input = None
        self.cursor_timer = 0
        
        self.status_message = "Ready to connect accounts or paste URLs"
        self.status_color = (100, 100, 100)
        
        self.is_downloading = False
        self.last_network_check = 0

        self.accounts_file = os.path.join("assets", "saved_accounts.json")
        self.saved_accounts = self.load_accounts()
        self.saved_chips_rects = [] 
        
        self.local_files = []
        self.local_file_rects = []
        self.refresh_local_files()

    def load_accounts(self):
        if os.path.exists(self.accounts_file):
            try:
                with open(self.accounts_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception: pass
        return {"chess_com": [], "lichess": []}
        
    def save_account(self, platform, username):
        if not username: return
        if username not in self.saved_accounts[platform]:
            self.saved_accounts[platform].append(username)
            if len(self.saved_accounts[platform]) > 5:
                self.saved_accounts[platform].pop(0)
            os.makedirs("assets", exist_ok=True)
            try:
                with open(self.accounts_file, "w", encoding="utf-8") as f:
                    json.dump(self.saved_accounts, f, indent=4)
            except Exception: pass

    def refresh_local_files(self):
        """Scans the assets/downloads folder for saved profiles"""
        self.local_files = []
        dir_path = os.path.join("assets", "downloads")
        if os.path.exists(dir_path):
            for f in os.listdir(dir_path):
                if f.endswith(".pgn"):
                    self.local_files.append(f)
                    
    def save_download(self, prefix, name, games):
        """Writes downloaded games to a specific file, overwriting old data to prevent duplication"""
        os.makedirs(os.path.join("assets", "downloads"), exist_ok=True)
        # Sanitize filename
        safe_name = "".join(c for c in name if c.isalnum() or c in "_-")
        if prefix == "url": safe_name = f"imported_{int(time.time())}"
            
        path = os.path.join("assets", "downloads", f"{prefix}_{safe_name}.pgn")
        
        # "w" mode overwrites the file, completely fixing the 422 duplicates bug!
        with open(path, "w", encoding="utf-8") as f:
            for g in games:
                pgn_data = g if isinstance(g, str) else g.get('pgn', '')
                if pgn_data:
                    f.write(str(pgn_data) + "\n\n")
        self.refresh_local_files()

    def set_status(self, message, color):
        self.status_message = message
        self.status_color = color
        
    def handle_click(self, pos):
        if not self.active: return
            
        for rect, platform, username in self.saved_chips_rects:
            if rect.collidepoint(pos):
                if platform == 'chess_com': self.chess_com_input = username; self.active_input = 'chess_com'
                else: self.lichess_input = username; self.active_input = 'lichess'
                return

        # Handle Local File clicks
        for rect, filename in self.local_file_rects:
            if rect.collidepoint(pos):
                path = os.path.join("assets", "downloads", filename)
                from popups import PGNSelectionPopup
                self.app.active_popup = PGNSelectionPopup(self.app, path)
                self.app.active_popup.active = True
                self.active = False
                return

        if self.buttons['close'].collidepoint(pos): self.active = False; return
            
        input_zones = [
            (pygame.Rect(self.rect.x + 20, self.rect.y + 70, 400, 35), 'chess_com'),
            (pygame.Rect(self.rect.x + 20, self.rect.y + 160, 400, 35), 'lichess'),
            (pygame.Rect(self.rect.x + 20, self.rect.y + 250, 540, 35), 'url')
        ]
        
        clicked_input = False
        for rect, key in input_zones:
            if rect.collidepoint(pos):
                self.active_input = key
                clicked_input = True
                break
                
        if not clicked_input: self.active_input = None
            
        if self.buttons['chess_com_connect'].collidepoint(pos): self.validate_account('chess_com')
        elif self.buttons['lichess_connect'].collidepoint(pos): self.validate_account('lichess')
        elif self.buttons['download_chess_com'].collidepoint(pos) and self.chess_com_input: self.download_games('chess_com')
        elif self.buttons['download_lichess'].collidepoint(pos) and self.lichess_input: self.download_games('lichess')
        elif self.buttons['download_url'].collidepoint(pos) and self.url_input: self.download_games('url')
    
    def handle_input(self, event):
        if not self.active or not self.active_input: return
            
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_v and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                try:
                    root = tk.Tk(); root.withdraw()
                    pasted = root.clipboard_get()
                    root.destroy()
                    clean = "".join(c for c in pasted if c.isprintable())
                    
                    if self.active_input == 'chess_com': self.chess_com_input += clean
                    elif self.active_input == 'lichess': self.lichess_input += clean
                    elif self.active_input == 'url': self.url_input += clean
                except: pass
                return

            if event.key == pygame.K_BACKSPACE:
                if self.active_input == 'chess_com': self.chess_com_input = self.chess_com_input[:-1]
                elif self.active_input == 'lichess': self.lichess_input = self.lichess_input[:-1]
                elif self.active_input == 'url': self.url_input = self.url_input[:-1]
            elif event.key == pygame.K_RETURN:
                if self.active_input == 'chess_com': self.validate_account('chess_com')
                elif self.active_input == 'lichess': self.validate_account('lichess')
                elif self.active_input == 'url': self.download_games('url')
            elif event.key == pygame.K_ESCAPE:
                self.active_input = None
            else:
                char = event.unicode
                if char.isprintable():
                    if self.active_input == 'chess_com': self.chess_com_input += char
                    elif self.active_input == 'lichess': self.lichess_input += char
                    elif self.active_input == 'url': self.url_input += char
    
    def validate_account(self, platform):
        user = self.chess_com_input if platform == 'chess_com' else self.lichess_input
        if not user:
            self.set_status(f"Please enter a username", (220, 60, 60))
            return
            
        self.set_status(f"Validating {platform} account...", (200, 150, 40))
        
        def validate():
            try:
                res = self.account_manager.validate_chess_com_username(user) if platform == 'chess_com' else self.account_manager.validate_lichess_username(user)
                if res.get("valid"):
                    self.save_account(platform, user)
                    self.set_status(f"✓ Found '{user}' ({res.get('count', 0)} games recorded)", (40, 160, 40))
                else:
                    self.set_status(f"✗ Account '{user}' not found", (220, 60, 60))
            except Exception as e:
                self.set_status(f"Network error: {str(e)}", (220, 60, 60))
        
        threading.Thread(target=validate, daemon=True).start()
    
    def download_games(self, platform):
        if self.is_downloading: return
            
        user = ""
        if platform == 'chess_com': user = self.chess_com_input
        elif platform == 'lichess': user = self.lichess_input
        elif platform == 'url': user = self.url_input
            
        self.is_downloading = True
        self.set_status(f"Downloading games...", (200, 150, 40))
        
        def download():
            try:
                if platform == 'chess_com':
                    res = self.account_manager.get_chess_com_games(user, max_games=500)
                elif platform == 'lichess':
                    res = self.account_manager.get_lichess_games(user, max_games=500)
                else:
                    res = self.account_manager.download_from_url(user)
                
                if 'error' in res:
                    self.set_status(f"Download failed: {res['error']}", (220, 60, 60))
                else:
                    games = res['games']
                    self.save_download(platform, user, games)
                    if platform != 'url': self.save_account(platform, user)
                    self.set_status(f"✓ Successfully saved {len(games)} games!", (40, 160, 40))
                    
            except Exception as e:
                self.set_status(f"Download error: {str(e)}", (220, 60, 60))
            finally:
                self.is_downloading = False
        
        threading.Thread(target=download, daemon=True).start()
    
    def update(self, dt):
        if self.active_input: self.cursor_timer += dt
        current_time = time.time()
        if current_time - self.last_network_check > 30:
            self.last_network_check = current_time
            if self.network_monitor.check_connection(): self.app.network_status = 'online'
            else: self.app.network_status = 'offline'
    
    def draw(self, screen, fb=None, fm=None):
        if not self.active: return
            
        self.cursor_timer += 1
        overlay = pygame.Surface((self.app.width, self.app.height))
        overlay.set_alpha(150)
        overlay.fill((0, 0, 0))
        screen.blit(overlay, (0, 0))
        
        pygame.draw.rect(screen, (248, 248, 252), self.rect, border_radius=12)
        pygame.draw.rect(screen, (200, 200, 210), self.rect, border_radius=12, width=2)
        
        title_surf = self.font_title.render("Account Manager & Importer", True, (40, 40, 45))
        screen.blit(title_surf, title_surf.get_rect(centerx=self.rect.centerx, y=self.rect.y + 15))
        
        self.saved_chips_rects = []
        
        # 3 Input Sections
        self.draw_input_section(screen, "Chess.com", self.chess_com_input, self.rect.y + 70, 'chess_com', 400)
        self.draw_input_section(screen, "Lichess", self.lichess_input, self.rect.y + 160, 'lichess', 400)
        self.draw_input_section(screen, "Master Games URL Import", self.url_input, self.rect.y + 250, 'url', 540)
        
        self.draw_buttons(screen)
        
        # Status message
        status_surf = self.font_normal.render(self.status_message, True, self.status_color)
        screen.blit(status_surf, status_surf.get_rect(centerx=self.rect.centerx, y=self.rect.y + 310))
        
        # Local Downloaded Profiles Viewer
        self.draw_local_files_viewer(screen)
        
        close_surf = self.font_normal.render("×", True, (100, 100, 100))
        screen.blit(close_surf, close_surf.get_rect(center=self.buttons['close'].center))
    
    def draw_input_section(self, screen, platform, text, y, section, width):
        screen.blit(self.font_header.render(platform, True, (60, 60, 65)), (self.rect.x + 20, y - 25))
        
        input_rect = pygame.Rect(self.rect.x + 20, y, width, 35)
        color = (255, 255, 255) if self.active_input == section else (240, 240, 245)
        pygame.draw.rect(screen, color, input_rect, border_radius=6)
        
        b_color = (100, 150, 220) if self.active_input == section else (180, 180, 190)
        pygame.draw.rect(screen, b_color, input_rect, border_radius=6, width=2 if self.active_input == section else 1)
        
        t_col = (20, 20, 25)
        if not text and self.active_input != section:
            t_col = (140, 140, 150)
            text = "Paste URL..." if section == 'url' else "Enter username..."
            
        t_surf = self.font_normal.render(text, True, t_col)
        screen.blit(t_surf, (input_rect.x + 10, input_rect.y + 8))
        
        if self.active_input == section and int(self.cursor_timer) % 60 < 30:
            cx = input_rect.x + 10 + t_surf.get_width()
            pygame.draw.line(screen, (20, 20, 25), (cx, input_rect.y + 8), (cx, input_rect.y + 27), 2)
                           
        if section != 'url':
            saved_list = self.saved_accounts.get(section, [])
            if saved_list:
                chip_y, chip_x = y + 42, self.rect.x + 20
                saved_lbl = self.font_small.render("Saved:", True, (120, 120, 120))
                screen.blit(saved_lbl, (chip_x, chip_y + 4))
                chip_x += saved_lbl.get_width() + 10
                
                for acc in saved_list:
                    acc_surf = self.font_small.render(acc, True, (80, 120, 180))
                    chip_rect = pygame.Rect(chip_x, chip_y, acc_surf.get_width() + 16, 22)
                    bg_color = (220, 230, 250) if chip_rect.collidepoint(pygame.mouse.get_pos()) else (235, 240, 250)
                    
                    pygame.draw.rect(screen, bg_color, chip_rect, border_radius=10)
                    pygame.draw.rect(screen, (180, 200, 230), chip_rect, border_radius=10, width=1)
                    screen.blit(acc_surf, (chip_x + 8, chip_y + 4))
                    
                    self.saved_chips_rects.append((chip_rect, section, acc))
                    chip_x += chip_rect.width + 8

    def draw_local_files_viewer(self, screen):
        """Draws the list of permanently saved downloaded games"""
        panel = pygame.Rect(self.rect.x + 20, self.rect.y + 340, self.rect.width - 40, 350)
        pygame.draw.rect(screen, (255, 255, 255), panel, border_radius=8)
        pygame.draw.rect(screen, (220, 220, 230), panel, 2, border_radius=8)
        
        screen.blit(self.font_header.render("Local Downloaded Accounts", True, (60, 60, 70)), (panel.x + 15, panel.y + 15))
        
        if not self.local_files:
            screen.blit(self.font_normal.render("No games downloaded yet. Fetch an account above!", True, (150, 150, 150)), (panel.x + 15, panel.y + 60))
            return
            
        # Draw files grid
        self.local_file_rects = []
        y = panel.y + 50
        for f in self.local_files:
            if y > panel.bottom - 40: break
            
            row = pygame.Rect(panel.x + 15, y, panel.width - 30, 45)
            col = (240, 248, 255) if row.collidepoint(pygame.mouse.get_pos()) else (250, 250, 252)
            pygame.draw.rect(screen, col, row, border_radius=6)
            pygame.draw.rect(screen, (230, 230, 235), row, 1, border_radius=6)
            
            # Format text cleanly based on file convention
            display_name = f.replace(".pgn", "")
            domain = "Custom"
            if display_name.startswith("chesscom_"): domain = "Chess.com"; display_name = display_name[9:]
            elif display_name.startswith("lichess_"): domain = "Lichess"; display_name = display_name[8:]
            elif display_name.startswith("url_"): domain = "URL Import"; display_name = display_name[4:]
            
            screen.blit(self.font_title.render(display_name, True, (40, 100, 180)), (row.x + 15, row.y + 10))
            screen.blit(self.font_small.render(domain, True, (120, 120, 120)), (row.right - 80, row.y + 15))
            
            self.local_file_rects.append((row, f))
            y += 55
    
    def draw_buttons(self, screen):
        mpos = pygame.mouse.get_pos()
        for name, rect in self.buttons.items():
            if name == 'close': continue
            hov = rect.collidepoint(mpos)
            
            if name in ['download_chess_com', 'download_lichess', 'download_url']:
                if (name == 'download_chess_com' and self.chess_com_input) or \
                   (name == 'download_lichess' and self.lichess_input) or \
                   (name == 'download_url' and self.url_input):
                    color = (80, 130, 200) if not hov else (100, 150, 220)
                    t_col = (255, 255, 255)
                    text = "Download"
                else:
                    color = (220, 220, 225)
                    t_col = (150, 150, 150)
                    text = "Awaiting Input"
            else:
                color = (230, 230, 235) if not hov else (240, 240, 245)
                t_col = (60, 60, 70)
                text = "Verify"
            
            pygame.draw.rect(screen, color, rect, border_radius=6)
            pygame.draw.rect(screen, (180, 180, 190) if color == (220, 220, 225) else color, rect, border_radius=6, width=1)
            t_surf = self.font_small.render(text, True, t_col)
            screen.blit(t_surf, t_surf.get_rect(center=rect.center))
    
    def draw_progress_bar(self, screen):
        """Draw active download progress bar"""
        progress_rect = pygame.Rect(self.rect.x + 20, self.rect.y + 330, self.rect.width - 40, 15)
        pygame.draw.rect(screen, (220, 220, 225), progress_rect, border_radius=8)
        
        # Animated progress cycle
        progress = (pygame.time.get_ticks() % 2000) / 2000.0
        fill_width = int(progress_rect.width * progress)
        pygame.draw.rect(screen, (80, 130, 200), 
                        (progress_rect.x, progress_rect.y, fill_width, progress_rect.height),
                        border_radius=8)
    
    def draw_games_summary(self, screen):
        """Draw final summary of fetched games"""
        y = self.rect.y + 360
        
        # Chess.com games
        if self.chess_com_games:
            text = f"✓ Chess.com ({self.dl_chess_com_user}): {len(self.chess_com_games)} games ready"
            surf = self.font_normal.render(text, True, (40, 140, 40))
            screen.blit(surf, (self.rect.x + 20, y))
            y += 25
        
        # Lichess games
        if self.lichess_games:
            text = f"✓ Lichess ({self.dl_lichess_user}): {len(self.lichess_games)} games ready"
            surf = self.font_normal.render(text, True, (40, 140, 40))
            screen.blit(surf, (self.rect.x + 20, y))
