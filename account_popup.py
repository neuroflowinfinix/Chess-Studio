import pygame
import threading
import time
import os
import json
from account_manager import ChessAccountManager, NetworkStatusMonitor


class AccountPopup:
    """
    'Add Account' popup — matches the reference design:
      - Player Name  (optional grouping label)
      - Website toggle: Lichess | Chess.com
      - Username text field
      - Add button  →  validates, downloads, saves to accounts panel
    """

    # ------------------------------------------------------------------ init
    def __init__(self, app):
        self.app    = app
        self.active = True

        self.w, self.h = 640, 520  # Increased from 600x480 for better spacing
        self._recentre()

        # fonts - use better sizing for UI hierarchy
        self.font_title  = getattr(app, 'font_b', pygame.font.SysFont("Segoe UI", 20, bold=True))
        self.font_header = getattr(app, 'font_m', pygame.font.SysFont("Segoe UI", 13, bold=True))
        self.font_normal = getattr(app, 'font_m', pygame.font.SysFont("Segoe UI", 12))
        self.font_small  = getattr(app, 'font_s', pygame.font.SysFont("Segoe UI", 11))

        # state
        self.site          = "lichess"   # "lichess" | "chess_com"
        self.player_input  = ""          # optional player name
        self.username_input= ""
        self.active_field  = None        # "player" | "username"
        self.cursor_timer  = 0

        self.status_msg   = ""
        self.status_color = (100, 100, 100)
        self.is_busy      = False

        self.account_manager = ChessAccountManager()

        # button rects (built in draw)
        self.btn_close    = None
        self.btn_lichess  = None
        self.btn_chesscom = None
        self.btn_add      = None
        self.rect_player  = None
        self.rect_username= None

    # ------------------------------------------------------------------ helpers
    def _recentre(self):
        sw = getattr(self.app, 'width',  1280)
        sh = getattr(self.app, 'height', 800)
        self.rect = pygame.Rect((sw - self.w) // 2, (sh - self.h) // 2, self.w, self.h)

    def _set_status(self, msg, color=(100, 100, 100)):
        self.status_msg   = msg
        self.status_color = color

    # ------------------------------------------------------------------ events
    def handle_click(self, pos):
        if not self.active:
            return

        # close
        if self.btn_close and self.btn_close.collidepoint(pos):
            self._close()
            return

        # site toggle
        if self.btn_lichess and self.btn_lichess.collidepoint(pos):
            self.site = "lichess"
            return
        if self.btn_chesscom and self.btn_chesscom.collidepoint(pos):
            self.site = "chess_com"
            return

        # text fields
        clicked_field = False
        if self.rect_player and self.rect_player.collidepoint(pos):
            self.active_field = "player"
            clicked_field = True
        if self.rect_username and self.rect_username.collidepoint(pos):
            self.active_field = "username"
            clicked_field = True
        if not clicked_field:
            self.active_field = None

        # Add button
        if self.btn_add and self.btn_add.collidepoint(pos):
            self._do_add()

    def handle_input(self, event):
        if not self.active:
            return
        if not hasattr(event, 'type'):
            return
        if event.type != pygame.KEYDOWN:
            return
        if self.active_field is None:
            return

        key = event.key

        # Ctrl-V paste
        if event.mod & pygame.KMOD_CTRL and key == pygame.K_v:
            try:
                import tkinter as tk
                root = tk.Tk(); root.withdraw()
                pasted = root.clipboard_get(); root.destroy()
                clean = "".join(c for c in pasted if c.isprintable())
                self._append(clean)
            except Exception:
                pass
            return

        if key == pygame.K_ESCAPE:
            self.active_field = None
        elif key == pygame.K_TAB:
            self.active_field = "username" if self.active_field == "player" else "player"
        elif key == pygame.K_RETURN:
            self._do_add()
        elif key == pygame.K_BACKSPACE:
            if self.active_field == "player":
                self.player_input = self.player_input[:-1]
            else:
                self.username_input = self.username_input[:-1]
        else:
            char = event.unicode
            if char and char.isprintable():
                self._append(char)

    def _append(self, text):
        if self.active_field == "player":
            self.player_input += text
        elif self.active_field == "username":
            self.username_input += text

    def handle_scroll(self, event):
        pass   # nothing to scroll in this popup

    def update(self, dt):
        self.cursor_timer += dt

    # ------------------------------------------------------------------ logic
    def _close(self):
        self.active = False
        if hasattr(self.app, 'add_account_popup'):
            self.app.add_account_popup = None

    def _do_add(self):
        """Validate + download + save account, then refresh the accounts panel."""
        username = self.username_input.strip()
        if not username:
            self._set_status("Please enter a username.", (220, 60, 60))
            return
        if self.is_busy:
            return

        self.is_busy = True
        self._set_status(f"Validating {username}…", (200, 150, 40))

        def _worker():
            try:
                # 1. Validate
                if self.site == "chess_com":
                    res = self.account_manager.validate_chess_com_username(username)
                else:
                    res = self.account_manager.validate_lichess_username(username)

                if not res.get("valid"):
                    self._set_status(f"✗ '{username}' not found on "
                                     f"{'Chess.com' if self.site == 'chess_com' else 'Lichess'}.",
                                     (220, 60, 60))
                    self.is_busy = False
                    return

                game_count = res.get("count", 0)
                self._set_status(f"✓ Found {game_count} games. Downloading…", (200, 150, 40))

                # 2. Download games
                if self.site == "chess_com":
                    dl = self.account_manager.get_chess_com_games(username, max_games=500)
                else:
                    dl = self.account_manager.get_lichess_games(username, max_games=500)

                if "error" in dl:
                    self._set_status(f"Download failed: {dl['error']}", (220, 60, 60))
                    self.is_busy = False
                    return

                games = dl["games"]

                # 3. Save PGN file to assets/downloads/
                self._save_pgn(username, games)

                # 4. Save account entry to assets/accounts/<username>.json
                self._save_account_json(username, games)

                # 5. Refresh the parent AccountPopup (popups.py) account list
                acc_popup = getattr(self.app, 'account_popup', None)
                if acc_popup and hasattr(acc_popup, '_load_accounts'):
                    try:
                        acc_popup.accounts = acc_popup._load_accounts()
                        if acc_popup.accounts:
                            acc_popup.selected_account = acc_popup.accounts[0]["username"]
                    except Exception:
                        pass

                self._set_status(
                    f"✓ {len(games)} games saved for '{username}'!", (40, 160, 40))
                self.is_busy = False

                # Auto-close after 1.5 s on success
                time.sleep(1.5)
                self._close()

            except Exception as exc:
                self._set_status(f"Error: {exc}", (220, 60, 60))
                self.is_busy = False

        threading.Thread(target=_worker, daemon=True).start()

    def _save_pgn(self, username, games):
        """Save downloaded games as a PGN file."""
        os.makedirs(os.path.join("assets", "downloads"), exist_ok=True)
        prefix = "chess_com" if self.site == "chess_com" else "lichess"
        safe   = "".join(c for c in username if c.isalnum() or c in "_-")
        path   = os.path.join("assets", "downloads", f"{prefix}_{safe}.pgn")
        with open(path, "w", encoding="utf-8") as f:
            for g in games:
                pgn_data = g if isinstance(g, str) else g.get("pgn", "")
                if pgn_data:
                    f.write(str(pgn_data) + "\n\n")

    def _save_account_json(self, username, games):
        """Save account metadata so the AccountPopup panel can list it."""
        os.makedirs(os.path.join("assets", "accounts"), exist_ok=True)
        site_label = "Chess.com" if self.site == "chess_com" else "Lichess"
        player_name = self.player_input.strip() or username

        # Build a lightweight game list with rating data
        game_list = []
        for g in games:
            if isinstance(g, dict):
                opponent = g.get("black", "?") if g.get("user_color") == "white" else g.get("white", "?")
                result = g.get("result", "*")
                date = g.get("date", "")
                rating = g.get("rating", 0)
                rating_change = g.get("rating_change", 0)
                
                entry = {
                    "opponent": opponent,
                    "result": result,
                    "date": date,
                    "rating": rating,
                    "rating_change": rating_change,
                }
                # Try to pull PGN path for loading
                safe = "".join(c for c in username if c.isalnum() or c in "_-")
                prefix = "chess_com" if self.site == "chess_com" else "lichess"
                entry["pgn_path"] = os.path.join(
                    "assets", "downloads", f"{prefix}_{safe}.pgn")
                game_list.append(entry)

        data = {
            "username": username,
            "player_name": player_name,
            "site": site_label,
            "games": game_list,
        }
        safe = "".join(c for c in username if c.isalnum() or c in "_-")
        path = os.path.join("assets", "accounts", f"{safe}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    # ------------------------------------------------------------------ draw
    def draw(self, screen, fb=None, fm=None):
        if not self.active:
            return

        self._recentre()
        self.cursor_timer += 1

        # dim overlay
        ov = pygame.Surface((screen.get_width(), screen.get_height()), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 160))
        screen.blit(ov, (0, 0))

        rx, ry, rw, rh = self.rect.x, self.rect.y, self.rect.w, self.rect.h

        # panel background + border with modern shadow
        shadow_rect = pygame.Rect(rx + 4, ry + 4, rw + 2, rh + 2)
        shadow_surf = pygame.Surface((shadow_rect.width + 4, shadow_rect.height + 4), pygame.SRCALPHA)
        pygame.draw.rect(shadow_surf, (0, 0, 0, 40), shadow_surf.get_rect(), border_radius=16)
        screen.blit(shadow_surf, (shadow_rect.x - 2, shadow_rect.y - 2))
        
        pygame.draw.rect(screen, (252, 252, 254), self.rect, border_radius=16)
        pygame.draw.rect(screen, (210, 210, 218), self.rect, 2, border_radius=16)

        # ---------- title bar ----------
        title = self.font_title.render("Add Online Account", True, (30, 30, 35))
        screen.blit(title, (rx + 30, ry + 24))

        # close × button with better positioning
        self.btn_close = pygame.Rect(rx + rw - 50, ry + 18, 32, 32)
        cc = (235, 90, 90) if self.btn_close.collidepoint(pygame.mouse.get_pos()) else (215, 215, 225)
        pygame.draw.rect(screen, cc, self.btn_close, border_radius=8)
        xs = self.font_title.render("×", True, (255, 255, 255) if cc[0] > 220 else (255, 255, 255))
        screen.blit(xs, xs.get_rect(center=self.btn_close.center))

        pygame.draw.line(screen, (225, 225, 232), (rx + 20, ry + 64), (rx + rw - 20, ry + 64), 1)

        y = ry + 85  # Increased from 80 for better spacing
        pad = 32  # Increased from 30 for better margins

        # ---------- Player Name ----------
        screen.blit(self.font_header.render("Player Name", True, (50, 50, 58)), (rx + pad, y))
        sub = self.font_small.render("Optional: group accounts by player", True, (140, 140, 150))
        screen.blit(sub, (rx + pad, y + 20))  # Adjusted spacing
        y += 48  # Increased from 42

        self.rect_player = pygame.Rect(rx + pad, y, rw - pad * 2, 42)  # Increased height from 40
        active_p = (self.active_field == "player")
        pygame.draw.rect(screen, (255, 255, 255), self.rect_player, border_radius=8)
        pygame.draw.rect(screen,
                         (80, 140, 220) if active_p else (205, 205, 215),
                         self.rect_player, 2 if active_p else 1, border_radius=8)

        disp_p = self.player_input if self.player_input else ""
        if not disp_p and not active_p:
            ps = self.font_normal.render("e.g., Alex, Magnus", True, (170, 170, 180))
        else:
            ps = self.font_normal.render(disp_p, True, (20, 20, 25))
        screen.blit(ps, (self.rect_player.x + 14, self.rect_player.y + 11))  # Centered vertically
        if active_p and int(self.cursor_timer) % 60 < 30:
            cx = self.rect_player.x + 14 + ps.get_width()
            pygame.draw.line(screen, (20, 20, 25),
                             (cx, self.rect_player.y + 10), (cx, self.rect_player.y + 32), 2)

        y += 60  # Increased from 54

        # ---------- Website ----------
        wlbl = self.font_header.render("Website", True, (50, 50, 58))
        screen.blit(wlbl, (rx + pad, y))
        # required star
        star = self.font_header.render(" *", True, (220, 60, 60))
        screen.blit(star, (rx + pad + wlbl.get_width(), y))
        y += 30  # Increased from 28

        btn_w = (rw - pad * 2 - 16) // 2  # Adjusted spacing
        self.btn_lichess  = pygame.Rect(rx + pad, y, btn_w, 58)  # Increased height
        self.btn_chesscom = pygame.Rect(rx + pad + btn_w + 16, y, btn_w, 58)

        for btn, label, key in [
            (self.btn_lichess,  "Lichess", "lichess"),
            (self.btn_chesscom, "Chess.com", "chess_com"),
        ]:
            selected = (self.site == key)
            bg  = (255, 255, 255)
            brd = (78, 140, 220) if selected else (210, 210, 220)
            bw  = 2 if selected else 1
            pygame.draw.rect(screen, bg, btn, border_radius=10)
            pygame.draw.rect(screen, brd, btn, bw, border_radius=10)

            # Icon handling - support actual image files  
            ic_cx = btn.x + 38
            ic_cy = btn.centery
            
            icon_key = "lichess" if key == "lichess" else "chess_com" 
            icon_img = self.app.assets.icons.get(icon_key)
            
            if icon_img:
                try:
                    scaled_icon = pygame.transform.smoothscale(icon_img, (34, 34))
                    screen.blit(scaled_icon, (ic_cx - 17, ic_cy - 17))
                except:
                    # Fallback
                    ic_col = (70, 140, 220) if key == "lichess" else (100, 180, 100)
                    pygame.draw.circle(screen, ic_col, (ic_cx, ic_cy), 17)
            else:
                # Fallback circles with Unicode chess symbols
                ic_col = (70, 140, 220) if key == "lichess" else (100, 180, 100)
                pygame.draw.circle(screen, ic_col, (ic_cx, ic_cy), 17)
                icon_char = "♗" if key == "lichess" else "♘"
                ic_s = self.font_header.render(icon_char, True, (255, 255, 255))
                screen.blit(ic_s, ic_s.get_rect(center=(ic_cx, ic_cy)))

            lbl_s = self.font_header.render(label, True, (20, 20, 28))
            screen.blit(lbl_s, (btn.x + 64, btn.centery - lbl_s.get_height() // 2))

        y += 72  # Increased from 68

        # ---------- Username ----------
        ulbl = self.font_header.render("Username", True, (50, 50, 58))
        screen.blit(ulbl, (rx + pad, y))
        star2 = self.font_header.render(" *", True, (220, 60, 60))
        screen.blit(star2, (rx + pad + ulbl.get_width(), y))
        y += 30  # Increased from 28

        self.rect_username = pygame.Rect(rx + pad, y, rw - pad * 2, 42)  # Increased height
        active_u = (self.active_field == "username")
        pygame.draw.rect(screen, (255, 255, 255), self.rect_username, border_radius=8)
        pygame.draw.rect(screen,
                         (80, 140, 220) if active_u else (205, 205, 215),
                         self.rect_username, 2 if active_u else 1, border_radius=8)

        disp_u = self.username_input if self.username_input else ""
        if not disp_u and not active_u:
            us = self.font_normal.render("Enter your username", True, (170, 170, 180))
        else:
            us = self.font_normal.render(disp_u, True, (20, 20, 25))
        screen.blit(us, (self.rect_username.x + 14, self.rect_username.y + 11))  # Centered vertically
        if active_u and int(self.cursor_timer) % 60 < 30:
            cx = self.rect_username.x + 14 + us.get_width()
            pygame.draw.line(screen, (20, 20, 25),
                             (cx, self.rect_username.y + 10), (cx, self.rect_username.y + 32), 2)

        y += 58  # Increased from 54

        # ---------- status message ----------
        if self.status_msg:
            ss = self.font_small.render(self.status_msg, True, self.status_color)
            screen.blit(ss, (rx + pad, y))
        y += 28  # Increased from 24

        # ---------- Add button ----------
        self.btn_add = pygame.Rect(rx + pad, y, rw - pad * 2, 48)  # Increased height from 46
        if self.is_busy:
            add_col = (155, 155, 160)
        elif self.btn_add.collidepoint(pygame.mouse.get_pos()):
            add_col = (60, 140, 230)
        else:
            add_col = (75, 160, 245)
        pygame.draw.rect(screen, add_col, self.btn_add, border_radius=10)
        add_lbl = self.font_header.render(
            "Adding…" if self.is_busy else "Add Account", True, (255, 255, 255))
        screen.blit(add_lbl, add_lbl.get_rect(center=self.btn_add.center))
