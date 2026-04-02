import pygame
import chess
import chess.pgn
import chess.polyglot
import datetime
import os
import threading
import random
from tkinter import filedialog
import re
import time
from assets import THEME, BOTS

# Try importing analysis engine for ReviewPopup
try: import analysis_engine
except ImportError: analysis_engine = None

# =============================================================================
#  BASE POPUP CLASS (Helper)
# =============================================================================
class BasePopup:
    def __init__(self, parent, w=600, h=500):
        self.parent = parent
        self.active = True
        # UI POLISH: Universally scale up ALL popups by 10% for a more spacious, breathable look
        self.w, self.h = int(w * 1.10), int(h * 1.10)
        self.rect = pygame.Rect(0, 0, self.w, self.h)
        self.update_rect()
        self.close_btn = None

    def update_rect(self):
        mw, mh = self.parent.width, self.parent.height
        self.w = min(self.w, mw - 40)
        self.h = min(self.h, mh - 40)
        self.rect = pygame.Rect((mw - self.w)//2, (mh - self.h)//2, self.w, self.h)

    def draw_bg(self, screen, title, fb):
        self.update_rect()
        
        # 1. Darker, smoother overlay behind the popup to focus attention
        ov = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 160))
        screen.blit(ov, (0, 0))
        
        # 2. Modern Drop Shadow (Dynamic size matching the popup)
        shadow_rect = self.rect.copy()
        shadow_rect.y += 8
        shadow_surf = pygame.Surface((shadow_rect.width + 10, shadow_rect.height + 10), pygame.SRCALPHA)
        pygame.draw.rect(shadow_surf, (0, 0, 0, 50), shadow_surf.get_rect(), border_radius=20)
        screen.blit(shadow_surf, (shadow_rect.x, shadow_rect.y))
        
        # 3. Main Popup Body (Light Theme to preserve child text colors, with softer radius)
        pygame.draw.rect(screen, (252, 252, 254), self.rect, border_radius=16)
        pygame.draw.rect(screen, (210, 210, 215), self.rect, 2, border_radius=16)
        
        # Title Bar — centred horizontally
        t_surf = fb.render(title, True, (40, 40, 45))
        screen.blit(t_surf, (self.rect.centerx - t_surf.get_width()//2, self.rect.y + 24))
        
        self.close_btn = pygame.Rect(self.rect.right - 46, self.rect.y + 18, 30, 30)

        # --- FIX 7: Image Close Button (With Hover Dynamics) ---
        if self.close_btn:
            close_icon = self.parent.assets.icons.get("close_btn")
            if not close_icon:
                try:
                    p = os.path.join('assets', 'icons', 'close_btn.png')
                    if os.path.exists(p):
                        img = pygame.image.load(p).convert_alpha()
                        self.parent.assets.icons['close_btn'] = img
                        close_icon = img
                except Exception:
                    close_icon = None

            if close_icon:
                try:
                    # Optional: Add a slight dark overlay on hover to image
                    if self.close_btn.collidepoint(pygame.mouse.get_pos()):
                        pygame.draw.rect(screen, (230, 230, 235), self.close_btn, border_radius=6)
                    screen.blit(pygame.transform.smoothscale(close_icon, (self.close_btn.w, self.close_btn.h)), (self.close_btn.x, self.close_btn.y))
                except Exception:
                    screen.blit(close_icon, (self.close_btn.x, self.close_btn.y))
            else:
                # Modern Red Close Button Fallback
                is_hover = self.close_btn.collidepoint(pygame.mouse.get_pos())
                col = (240, 80, 80) if is_hover else (225, 225, 230)
                txt_col = (255, 255, 255) if is_hover else (100, 100, 100)
                pygame.draw.rect(screen, col, self.close_btn, border_radius=8)
                x_surf = fb.render("X", True, txt_col)
                screen.blit(x_surf, (self.close_btn.centerx - x_surf.get_width()//2,
                                     self.close_btn.centery - x_surf.get_height()//2))

class PuzzlePopup(BasePopup):
    def __init__(self, parent):
        super().__init__(parent, 880, 640)
        self.assets    = parent.assets
        self.tab       = "unsolved"
        self.scroll    = 0
        self.zones     = []
        self.edit_idx  = -1
        self.edit_text = ""

        self.btn_unsolved         = None
        self.btn_solved           = None
        self.btn_appmade          = None
        self.btn_new              = None
        self.btn_reload           = None
        self.btn_solution         = None
        self.btn_download_lichess = None

        # Lichess download state
        self._dl_status   = ""     # "" | "downloading" | "done — N added!" | "error: …"
        self._dl_progress = 0.0    # 0.0 – 1.0
        self._dl_bytes_done = 0    # bytes received so far
        self._dl_bytes_total = 0   # total content-length (0 if unknown)
        self._dl_count    = 0
        self._sidecar     = {}
        self._online_cache = None  # None = unchecked

        # Toast
        self._toast_msg      = ""
        self._toast_timer    = 0
        self._TOAST_DURATION = 150

        self.assets.refresh_puzzles()
        self._sidecar = self.assets.get_lichess_sidecar()

    # ------------------------------------------------------------------ draw
    def draw(self, screen, fb, fm):
        self.draw_bg(screen, "Chess Puzzles", fb)

        tab_y  = self.rect.y + 70
        tab_w  = 126
        tab_gap = 8

        self.btn_unsolved = pygame.Rect(self.rect.x + 20, tab_y, tab_w, 34)
        self.btn_solved   = pygame.Rect(self.rect.x + 20 + tab_w + tab_gap, tab_y, tab_w, 34)
        self.btn_appmade  = pygame.Rect(self.rect.x + 20 + (tab_w + tab_gap) * 2, tab_y, tab_w, 34)

        for btn, label, key in [
            (self.btn_unsolved, "Unsolved", "unsolved"),
            (self.btn_solved,   "Solved",   "solved"),
            (self.btn_appmade,  "My Puzzles","appmade"),
        ]:
            active  = (self.tab == key)
            bg_col  = THEME["accent"] if active else (218, 218, 224)
            pygame.draw.rect(screen, bg_col, btn, border_radius=7)
            t = fm.render(label, True, (255,255,255) if active else (50,50,60))
            screen.blit(t, (btn.centerx - t.get_width()//2, btn.centery - t.get_height()//2))

        # ── Lichess download button ───────────────────────────────────────────
        dl_btn_x = self.rect.x + 20 + (tab_w + tab_gap) * 3 + 14
        self.btn_download_lichess = pygame.Rect(dl_btn_x, tab_y, 190, 34)

        if self._dl_status == "downloading":
            dl_col   = (50, 140, 60)
            dl_label = "Downloading…"
        else:
            if self._online_cache is None:
                try:
                    import socket
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(0.4)
                    s.connect(("8.8.8.8", 53))
                    s.close()
                    self._online_cache = True
                except Exception:
                    self._online_cache = False
            dl_col  = (38, 155, 68) if self._online_cache else (155, 155, 155)
            dl_label = "↓ Lichess Attraction" if self._online_cache else "↓ Offline"

        if self.btn_download_lichess.collidepoint(pygame.mouse.get_pos()) and dl_col != (155,155,155):
            dl_col = tuple(min(255, c + 18) for c in dl_col)
        pygame.draw.rect(screen, dl_col, self.btn_download_lichess, border_radius=7)
        dl_t = self.parent.font_s.render(dl_label, True, (255,255,255))
        screen.blit(dl_t, (self.btn_download_lichess.centerx - dl_t.get_width()//2,
                             self.btn_download_lichess.centery - dl_t.get_height()//2))

        # ── Download progress bar (shown while downloading) ───────────────────
        if self._dl_status == "downloading":
            pb_rect = pygame.Rect(self.rect.x + 20, tab_y + 40, self.rect.width - 40, 18)
            pygame.draw.rect(screen, (210, 220, 210), pb_rect, border_radius=9)
            fill_w = int(self._dl_progress * pb_rect.width)
            if fill_w > 0:
                pygame.draw.rect(screen, (50, 190, 80),
                                 pygame.Rect(pb_rect.x, pb_rect.y, fill_w, pb_rect.height),
                                 border_radius=9)
            # Label: "Downloading … 47%  (3.2 / 6.8 MB)"
            pct_str = f"{int(self._dl_progress * 100)}%"
            if self._dl_bytes_total > 0:
                done_mb  = self._dl_bytes_done  / (1024 * 1024)
                total_mb = self._dl_bytes_total / (1024 * 1024)
                size_str = f"  ({done_mb:.1f} / {total_mb:.1f} MB)"
            else:
                size_str = f"  ({self._dl_bytes_done // 1024} KB received)"
            pb_label = self.parent.font_s.render(
                f"Downloading Lichess puzzles…  {pct_str}{size_str}", True, (30, 80, 30))
            screen.blit(pb_label, (pb_rect.centerx - pb_label.get_width()//2,
                                    pb_rect.y + (pb_rect.height - pb_label.get_height())//2))
            list_top_offset = 130   # push list down to make room
        else:
            list_top_offset = 120
            # Show last status message (done / error) next to download button
            if self._dl_status:
                st_col = (40,155,40) if "done" in self._dl_status else (190,50,50)
                st = self.parent.font_s.render(self._dl_status, True, st_col)
                screen.blit(st, (self.btn_download_lichess.right + 10,
                                  self.btn_download_lichess.centery - st.get_height()//2))

        # ── Random / Reload / Solution buttons ────────────────────────────────
        self.btn_new = pygame.Rect(self.rect.right - 128, tab_y, 108, 34)
        pygame.draw.rect(screen, (55, 175, 55), self.btn_new, border_radius=7)
        t = fm.render("Random", True, (255,255,255))
        screen.blit(t, (self.btn_new.centerx - t.get_width()//2, self.btn_new.centery - t.get_height()//2))

        self.btn_reload = None
        self.btn_solution = None
        if self.parent.mode == "puzzle":
            self.btn_reload = pygame.Rect(self.rect.right - 128, tab_y + 42, 108, 30)
            pygame.draw.rect(screen, (195, 175, 45), self.btn_reload, border_radius=7)
            t = self.parent.font_s.render("Reload", True, (255,255,255))
            screen.blit(t, (self.btn_reload.centerx - t.get_width()//2,
                             self.btn_reload.centery - t.get_height()//2))

            if getattr(self.parent, 'puzzle_wrong_attempts', 0) >= 1:
                self.btn_solution = pygame.Rect(self.rect.right - 128, tab_y + 80, 108, 30)
                sol_col = (185, 50, 50) if self.btn_solution.collidepoint(pygame.mouse.get_pos()) else (160, 42, 42)
                pygame.draw.rect(screen, sol_col, self.btn_solution, border_radius=7)
                t = self.parent.font_s.render("Solution", True, (255,255,255))
                screen.blit(t, (self.btn_solution.centerx - t.get_width()//2,
                                 self.btn_solution.centery - t.get_height()//2))

        # ── Puzzle list ───────────────────────────────────────────────────────
        if self.tab == "unsolved":  puzzles = self.assets.puzzles_unsolved
        elif self.tab == "solved":  puzzles = self.assets.puzzles_solved
        else:                       puzzles = self.assets.appmade_puzzles

        clip_rect = pygame.Rect(self.rect.x + 20, self.rect.y + list_top_offset,
                                self.w - 40, self.h - list_top_offset - 20)
        pygame.draw.rect(screen, (255,255,255), clip_rect, border_radius=8)
        pygame.draw.rect(screen, (215,215,222), clip_rect, 1, border_radius=8)
        screen.set_clip(clip_rect)

        total_h  = len(puzzles) * 60
        max_scroll = max(0, total_h - clip_rect.height)
        self.scroll = max(0, min(self.scroll, max_scroll))

        y = clip_rect.y - self.scroll
        self.zones = []
        use_drawn_icon = (self.tab == "appmade")
        icon = None if use_drawn_icon else self.assets.icons.get("puzzles")

        for i, p in enumerate(puzzles):
            if y + 60 < clip_rect.y: y += 60; continue
            if y > clip_rect.bottom: break

            row = pygame.Rect(clip_rect.x, y, clip_rect.width, 54)
            if row.collidepoint(pygame.mouse.get_pos()):
                pygame.draw.rect(screen, (238, 242, 255), row)

            # Icon
            if use_drawn_icon:
                ic_cx, ic_cy = row.x + 26, row.y + 27
                pygame.draw.circle(screen, (30, 30, 35), (ic_cx, ic_cy), 16)
                pygame.draw.circle(screen, (60, 60, 70), (ic_cx, ic_cy), 16, 1)
                h_s = self.parent.font_b.render("#", True, (255,255,255))
                screen.blit(h_s, (ic_cx - h_s.get_width()//2, ic_cy - h_s.get_height()//2 - 1))
            elif icon:
                screen.blit(pygame.transform.smoothscale(icon, (30, 30)), (row.x + 10, row.y + 12))

            # Lichess badge + rating
            fen_key      = " ".join(p.get("fen","").split()[:3])
            sc_entry     = self._sidecar.get(fen_key, {})
            is_lichess   = bool(sc_entry) or "Lichess" in p.get("name","")
            rating_str   = str(sc_entry.get("rating","")) if sc_entry else ""

            if is_lichess:
                badge_s = self.parent.font_s.render("♟ Lichess", True, (255,255,255))
                badge_r = pygame.Rect(row.x + 50, row.y + 8, badge_s.get_width() + 10, 17)
                pygame.draw.rect(screen, (28, 148, 126), badge_r, border_radius=5)
                screen.blit(badge_s, (badge_r.x + 5, badge_r.y + 2))
                name_x = badge_r.right + 8
            else:
                name_x = row.x + 50

            if i == self.edit_idx:
                edit_box = pygame.Rect(name_x, row.y + 8, 280, 28)
                pygame.draw.rect(screen, (255,255,255), edit_box)
                pygame.draw.rect(screen, THEME["accent"], edit_box, 2, border_radius=4)
                screen.blit(fm.render(self.edit_text, True, (0,0,0)), (edit_box.x+5, edit_box.y+5))
            else:
                p_name = p["name"]
                if is_lichess and rating_str:
                    p_name = f"{p_name}  [{rating_str}]"
                screen.blit(fm.render(p_name, True, (20,20,30)), (name_x, row.y + 16))

            # Buttons
            btn_load = pygame.Rect(row.right - 76, row.y + 11, 66, 28)
            pygame.draw.rect(screen, (48, 148, 215), btn_load, border_radius=5)
            t = self.parent.font_s.render("Play", True, (255,255,255))
            screen.blit(t, (btn_load.centerx - t.get_width()//2, btn_load.centery - t.get_height()//2))

            btn_edit = pygame.Rect(row.right - 150, row.y + 11, 66, 28)
            pygame.draw.rect(screen, (198,198,204), btn_edit, border_radius=5)
            t = self.parent.font_s.render("Rename", True, (40,40,40))
            screen.blit(t, (btn_edit.centerx - t.get_width()//2, btn_edit.centery - t.get_height()//2))

            btn_again = None
            if self.tab == "solved":
                btn_again = pygame.Rect(row.right - 228, row.y + 11, 70, 28)
                pygame.draw.rect(screen, (155,155,168), btn_again, border_radius=5)
                ta = self.parent.font_s.render("▶ Again", True, (255,255,255))
                screen.blit(ta, (btn_again.centerx - ta.get_width()//2, btn_again.centery - ta.get_height()//2))

            self.zones.append({"load": btn_load, "edit": btn_edit,
                                "again": btn_again, "idx": i, "puzzle": p})
            pygame.draw.line(screen, (228,228,232), (row.x, row.bottom), (row.right, row.bottom))
            y += 60

        screen.set_clip(None)

        # ── Toast ─────────────────────────────────────────────────────────────
        if self._toast_timer > 0:
            self._toast_timer -= 1
            progress = self._toast_timer / self._TOAST_DURATION
            slide  = min(1.0, (1.0 - progress) / 0.2) if progress > 0.8 else \
                     (progress / 0.2 if progress < 0.2 else 1.0)
            alpha  = int(220 * slide)
            toast_h, toast_w = 42, min(440, self.w - 40)
            toast_x = self.rect.centerx - toast_w // 2
            toast_y = int((self.rect.bottom + 4) - ((self.rect.bottom + 4) - (self.rect.bottom - toast_h - 12)) * slide)
            bg = pygame.Surface((toast_w, toast_h), pygame.SRCALPHA)
            bg.fill((30, 30, 35, alpha))
            pygame.draw.rect(bg, (30,30,35,alpha), bg.get_rect(), border_radius=10)
            screen.blit(bg, (toast_x, toast_y))
            border = pygame.Surface((toast_w, toast_h), pygame.SRCALPHA)
            pygame.draw.rect(border, (220,70,70,alpha), border.get_rect(), 2, border_radius=10)
            screen.blit(border, (toast_x, toast_y))
            t_surf = fm.render(self._toast_msg, True, (255,255,255))
            ta2 = pygame.Surface(t_surf.get_size(), pygame.SRCALPHA)
            ta2.fill((255,255,255,alpha))
            t_surf.blit(ta2, (0,0), special_flags=pygame.BLEND_RGBA_MULT)
            screen.blit(t_surf, (toast_x + toast_w//2 - t_surf.get_width()//2,
                                  toast_y + toast_h//2 - t_surf.get_height()//2))

    # ------------------------------------------------------------------ interaction
    def handle_scroll(self, e):
        if e.button == 4: self.scroll = max(0, self.scroll - 32)
        elif e.button == 5: self.scroll += 32

    def handle_click(self, pos):
        if self.close_btn.collidepoint(pos): self.active = False; return

        if self.btn_unsolved and self.btn_unsolved.collidepoint(pos):
            self.tab = "unsolved"; self.scroll = 0; self.edit_idx = -1; return
        if self.btn_solved and self.btn_solved.collidepoint(pos):
            self.tab = "solved";   self.scroll = 0; self.edit_idx = -1; return
        if self.btn_appmade and self.btn_appmade.collidepoint(pos):
            self.tab = "appmade";  self.scroll = 0; self.edit_idx = -1; return

        if self.btn_new and self.btn_new.collidepoint(pos):
            lst = {"unsolved": self.assets.puzzles_unsolved,
                   "solved":   self.assets.puzzles_solved,
                   "appmade":  self.assets.appmade_puzzles}.get(self.tab, [])
            if lst:
                self.parent.start_puzzle(random.choice(lst))
                self.active = False
            return

        if self.btn_reload and self.btn_reload.collidepoint(pos):
            if self.parent.active_puzzle:
                self.parent.start_puzzle(self.parent.active_puzzle)
                self.active = False
            return

        # Solution button
        if self.btn_solution and self.btn_solution.collidepoint(pos):
            if self.parent.analyzer and self.parent.analyzer.is_active:
                try:
                    import chess.engine
                    info = self.parent.analyzer.engine.analyse(
                        self.parent.board, chess.engine.Limit(time=0.6), multipv=1)
                    if info and "pv" in info[0]:
                        pv = info[0]["pv"]
                        san_list, tmp = [], self.parent.board.copy()
                        for m in pv[:6]:
                            try: san_list.append(tmp.san(m)); tmp.push(m)
                            except Exception: break
                        self.parent.add_chat("Solution", "  ".join(san_list))
                        if pv: self.parent.trainer_hint_arrow = pv[0]
                except Exception as e:
                    print(f"Solution error: {e}")
            return

        # Lichess download button
        if (self.btn_download_lichess and self.btn_download_lichess.collidepoint(pos)
                and self._dl_status != "downloading" and self._online_cache):
            self._start_lichess_download()
            return

        if self.edit_idx != -1: self.commit_edit(); return

        for z in self.zones:
            if z["load"].collidepoint(pos):
                self.parent.start_puzzle(z["puzzle"]); self.active = False; return
            if z.get("again") and z["again"].collidepoint(pos):
                self.parent.start_puzzle(z["puzzle"]); self.active = False; return
            if z["edit"].collidepoint(pos):
                self.edit_idx = z["idx"]; self.edit_text = z["puzzle"]["name"]; return

    def handle_input(self, e):
        if e.type == pygame.KEYDOWN and self.edit_idx != -1:
            if e.key == pygame.K_RETURN:    self.commit_edit()
            elif e.key == pygame.K_BACKSPACE: self.edit_text = self.edit_text[:-1]
            else: self.edit_text += e.unicode

    def commit_edit(self):
        if self.edit_idx != -1:
            lst = {"unsolved": self.assets.puzzles_unsolved,
                   "solved":   self.assets.puzzles_solved,
                   "appmade":  self.assets.appmade_puzzles}.get(self.tab, [])
            if 0 <= self.edit_idx < len(lst):
                p = lst[self.edit_idx]
                if self.edit_text.strip():
                    self.assets.rename_puzzle(p, self.edit_text)
            self.edit_idx = -1; self.edit_text = ""

    # ------------------------------------------------------------------ download
    def _start_lichess_download(self):
        """
        Streams the Lichess puzzle batch API.
        Endpoint: GET https://lichess.org/api/puzzle/batch?nb=50&themes=attraction
        Returns JSON with a "puzzles" array.  No auth required.
        Progress is tracked by bytes received vs Content-Length.
        """
        import threading
        self._dl_status     = "downloading"
        self._dl_progress   = 0.0
        self._dl_bytes_done = 0
        self._dl_bytes_total = 0
        self._online_cache  = None   # re-check next open

        def _fetch():
            try:
                import urllib.request, json, chess as _chess

                url = "https://lichess.org/api/puzzle/batch?nb=50&themes=attraction"
                req = urllib.request.Request(url, headers={
                    "Accept":     "application/json",
                    "User-Agent": "ChessStudioPro/1.0",
                })

                with urllib.request.urlopen(req, timeout=20) as resp:
                    # Try to get total size for accurate progress bar
                    cl = resp.headers.get("Content-Length")
                    self._dl_bytes_total = int(cl) if cl else 0

                    # Stream in 4 KB chunks so the progress bar updates live
                    chunks = []
                    while True:
                        chunk = resp.read(4096)
                        if not chunk:
                            break
                        chunks.append(chunk)
                        self._dl_bytes_done += len(chunk)
                        if self._dl_bytes_total > 0:
                            self._dl_progress = self._dl_bytes_done / self._dl_bytes_total
                        else:
                            # Unknown size — pulse between 0.1 and 0.9
                            self._dl_progress = min(0.9, self._dl_progress + 0.04)

                    raw = b"".join(chunks).decode("utf-8")

                self._dl_progress = 1.0   # snap to full before parsing

                data = json.loads(raw)
                puzzles_raw = data.get("puzzles", [])

                existing_keys = self.assets.get_existing_lichess_fens()
                saved = 0

                for entry in puzzles_raw:
                    pz      = entry.get("puzzle", {})
                    game    = entry.get("game", {})
                    fen     = pz.get("fen") or game.get("fen", "")
                    solution = pz.get("solution", [])
                    pid     = pz.get("id", "?")
                    rating  = pz.get("rating", 1500)
                    themes  = pz.get("themes", [])

                    if not fen or not solution:
                        continue

                    # Validate FEN
                    try: _chess.Board(fen)
                    except Exception: continue

                    fen_key = " ".join(fen.split()[:3])
                    if fen_key in existing_keys:
                        continue

                    theme_str = ", ".join(themes[:3]) if themes else "attraction"
                    name = f"Lichess #{pid}  ★{rating}  [{theme_str}]"

                    ok = self.assets.save_lichess_puzzle(
                        fen=fen, name=name, solution_uci=solution, rating=rating)
                    if ok:
                        existing_keys.add(fen_key)
                        saved += 1

                self.assets.refresh_puzzles()
                self._sidecar = self.assets.get_lichess_sidecar()

                if saved > 0:
                    self._dl_status = f"done — {saved} puzzles added!"
                    self._dl_count += saved
                    self.parent.add_chat(
                        "System", f"Downloaded {saved} Lichess attraction puzzles. See Unsolved tab.")
                else:
                    self._dl_status = "done — all already saved"

            except Exception as e:
                self._dl_status = f"error: {str(e)[:50]}"
                self._dl_progress = 0.0
                print(f"Lichess download error: {e}")

        threading.Thread(target=_fetch, daemon=True).start()

# =============================================================================
#  SAVE MATE PUZZLE POPUP
# =============================================================================
class SaveMatePopup(BasePopup):
    def __init__(self, parent, mate_puzzles):
        super().__init__(parent, 550, 400)
        self.puzzles = mate_puzzles
        self.current_idx = 0
        self.btn_save = None
        self.btn_next = None
        self.do_not_save_all = False
        self.save_all = False
        self.chk_nosave_rect = None
        self.chk_saveall_rect = None

    def draw(self, screen, fb, fm):
        # Dim background
        ov = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 160))
        screen.blit(ov, (0, 0))
        
        cx, cy = (screen.get_width() - self.w)//2, (screen.get_height() - self.h)//2
        self.rect = pygame.Rect(cx, cy, self.w, self.h)
        
        shadow = self.rect.copy(); shadow.y += 8
        pygame.draw.rect(screen, (0,0,0,50), shadow, border_radius=20)
        pygame.draw.rect(screen, (252, 252, 254), self.rect, border_radius=16)
        pygame.draw.rect(screen, (210, 210, 215), self.rect, 2, border_radius=16)
        
        # --- NEW: GENERATED ICON (White Hashtag in Dark Black Circle) ---
        icon_center = (cx + self.w//2, cy + 55)
        pygame.draw.circle(screen, (30, 30, 35), icon_center, 32)
        pygame.draw.circle(screen, (60, 60, 70), icon_center, 32, 2)
        hash_txt = self.parent.font_huge.render("#", True, (255, 255, 255))
        screen.blit(hash_txt, (icon_center[0] - hash_txt.get_width()//2, icon_center[1] - hash_txt.get_height()//2 - 4))
        
        # Title & Info
        title = fb.render("Checkmate Puzzle Found!", True, (40, 180, 40))
        screen.blit(title, (cx + (self.w - title.get_width())//2, cy + 105))
        
        p_type = self.puzzles[self.current_idx].get("type", "Mate Puzzle")
        msg = fm.render(f"{p_type} - Puzzle {self.current_idx+1} of {len(self.puzzles)}", True, (80, 80, 80))
        screen.blit(msg, (cx + (self.w - msg.get_width())//2, cy + 135))
        
        # --- CHECKBOXES ---
        chk_y = cy + 180
        
        chk_x = cx + 60
        self.chk_saveall_rect = pygame.Rect(chk_x, chk_y, 20, 20)
        pygame.draw.rect(screen, (200, 200, 200), self.chk_saveall_rect, 2, border_radius=4)
        if self.save_all:
            pygame.draw.rect(screen, (40, 180, 40), (chk_x + 4, chk_y + 4, 12, 12), border_radius=2)
        lbl = fm.render("Autosave ALL mates as puzzles", True, (40, 40, 40))
        screen.blit(lbl, (chk_x + 28, chk_y + (20 - lbl.get_height())//2))

        self.chk_nosave_rect = pygame.Rect(chk_x, chk_y + 38, 20, 20)
        pygame.draw.rect(screen, (200, 200, 200), self.chk_nosave_rect, 2, border_radius=4)
        if self.do_not_save_all:
            pygame.draw.rect(screen, (200, 60, 60), (chk_x + 4, chk_y + 42, 12, 12), border_radius=2)
        lbl = fm.render("Discard ALL (Don't Save)", True, (40, 40, 40))
        screen.blit(lbl, (chk_x + 28, chk_y + 38 + (20 - lbl.get_height())//2))

        #Buttons
        btn_w, btn_h = 185, 45
        gap = 20
        total_btn = btn_w * 2 + gap
        btn_x = cx + (self.w - total_btn) // 2
        btn_y = cy + 295

        self.btn_save = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
        if self.do_not_save_all:
            pygame.draw.rect(screen, (200, 200, 200), self.btn_save, border_radius=8)
            save_txt = "Skip All"
        elif self.save_all:
            pygame.draw.rect(screen, (60, 180, 60), self.btn_save, border_radius=8)
            save_txt = "Finish & Save"
        else:
            pygame.draw.rect(screen, (60, 180, 60), self.btn_save, border_radius=8)
            save_txt = "Save This One"
        txt_surf = fb.render(save_txt, True, (255, 255, 255))
        screen.blit(txt_surf, (self.btn_save.centerx - txt_surf.get_width()//2,
                                self.btn_save.centery - txt_surf.get_height()//2))

        self.btn_next = pygame.Rect(btn_x + btn_w + gap, btn_y, btn_w, btn_h)
        pygame.draw.rect(screen, (200, 60, 60), self.btn_next, border_radius=8)
        next_txt = "Next / Skip"
        if self.save_all or self.do_not_save_all: next_txt = "Confirm"
        elif self.current_idx == len(self.puzzles) - 1: next_txt = "Close"
        txt_surf2 = fb.render(next_txt, True, (255, 255, 255))
        screen.blit(txt_surf2, (self.btn_next.centerx - txt_surf2.get_width()//2,
                                 self.btn_next.centery - txt_surf2.get_height()//2))

        self.close_btn = pygame.Rect(cx + self.w - 46, cy + 18, 30, 30)

    def handle_click(self, pos):
        if self.chk_saveall_rect.collidepoint(pos):
            self.save_all = not self.save_all
            if self.save_all: self.do_not_save_all = False
            return

        if self.chk_nosave_rect.collidepoint(pos):
            self.do_not_save_all = not self.do_not_save_all
            if self.do_not_save_all: self.save_all = False
            return

        if self.btn_save.collidepoint(pos):
            if self.do_not_save_all:
                self.active = False
            elif self.save_all:
                for i in range(self.current_idx, len(self.puzzles)):
                    self.save_puzzle(i)
                self.active = False
            else:
                self.save_puzzle(self.current_idx)
                self.advance()

        elif self.btn_next.collidepoint(pos) or (self.close_btn and self.close_btn.collidepoint(pos)):
            if self.save_all:
                for i in range(self.current_idx, len(self.puzzles)):
                    self.save_puzzle(i)
                self.active = False
            elif self.do_not_save_all:
                self.active = False
            else:
                self.advance()
            
    def save_puzzle(self, idx):
        if idx < len(self.puzzles):
            puz = self.puzzles[idx]
            new_fen = puz["fen"]
            new_key = " ".join(new_fen.split()[:3])
            existing = getattr(self.parent.assets, 'appmade_puzzles', [])
            for ex in existing:
                ex_key = " ".join(ex.get("fen", "").split()[:3])
                if ex_key == new_key:
                    pp = getattr(self.parent, 'puzzle_popup', None)
                    if pp and pp.active:
                        pp._toast_msg = "Puzzle already exists!"
                        pp._toast_timer = pp._TOAST_DURATION
                    return
            self.parent.assets.save_appmade_puzzle(new_fen, f"{puz['type']} {random.randint(100,999)}")

    def advance(self):
        self.current_idx += 1
        if self.current_idx >= len(self.puzzles):
            self.active = False

# =============================================================================
#  ENGINE POPUP  (3-column: engine list | core settings | full UCI options)
# =============================================================================
class EnginePopup(BasePopup):
    def __init__(self, parent):
        super().__init__(parent, 980, 680)
        
        self.engines = list(self.parent.assets.engines)
        if not any(e["path"] == "lichess_cloud" for e in self.engines):
            self.engines.insert(0, {"name": "Lichess Cloud API", "path": "lichess_cloud"})

        self.scroll       = 0
        self.zones        = []
        self.selected_idx = 0
        self.uci_options  = []
        self.uci_scroll   = 0
        self._uci_fetched = False
        self._fetch_token = 0  # incremented each time a new fetch starts; threads check this

        curr_path = self.parent.current_engine_info.get("path", "")
        for i, e in enumerate(self.engines):
            if e["path"] == curr_path:
                self.selected_idx = i; break

        self._engines_json = os.path.join("assets", "engines.json")
        self._all_configs  = self._load_engines_json()
        self.engine_settings = self._settings_for(self.selected_idx)
        self._fetch_uci_async()

    # ------------------------------------------------------------------ json helpers
    def _load_engines_json(self):
        import json
        try:
            if os.path.exists(self._engines_json):
                with open(self._engines_json, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception: pass
        return {}

    def _save_engines_json(self):
        import json
        try:
            os.makedirs(os.path.dirname(self._engines_json), exist_ok=True)
            with open(self._engines_json, "w", encoding="utf-8") as f:
                json.dump(self._all_configs, f, indent=2)
        except Exception as e: print(f"engines.json save error: {e}")

    def _settings_for(self, idx):
        key   = self.engines[idx].get("path","") if 0 <= idx < len(self.engines) else ""
        saved = self._all_configs.get(key, {})
        return {
            'depth':    saved.get('depth',    getattr(self.parent,'max_depth',20)),
            'threads':  saved.get('threads',  getattr(self.parent,'engine_threads',4)),
            'hash_size':saved.get('hash_size',getattr(self.parent,'engine_hash',512)),
            'use_cloud':saved.get('use_cloud',getattr(self.parent,'use_cloud_analysis',True)),
            'multi_pv': saved.get('multi_pv', getattr(self.parent,'engine_multipv',3)),
        }

    def _fetch_uci_async(self):
        self._uci_fetched = False
        self.uci_options  = []
        self._fetch_token += 1          # invalidate any running thread
        my_token = self._fetch_token
        idx  = self.selected_idx
        if idx < 0 or idx >= len(self.engines): return
        path = self.engines[idx].get("path","")
        if not path or path == "lichess_cloud":
            self._uci_fetched = True; return

        def _probe():
            import chess.engine
            opts = []
            import sys
            try:
                if sys.platform == "win32":
                    eng = chess.engine.SimpleEngine.popen_uci(path, creationflags=0x08000000)
                else:
                    eng = chess.engine.SimpleEngine.popen_uci(path)
                skip = {"uci_analysemode","uci_chess960","uci_limitstrength","ponder","multipv"}
                for name, opt in eng.options.items():
                    if name.lower() in skip: continue
                    saved_uci = self._all_configs.get(path,{}).get("uci_options",{})
                    entry = {
                        "name":    name,
                        "type":    str(opt.type),
                        "default": opt.default,
                        "min":     getattr(opt,"min",None),
                        "max":     getattr(opt,"max",None),
                        "var":     list(getattr(opt,"var",[]) or []),
                        "value":   saved_uci.get(name, opt.default),
                    }
                    opts.append(entry)
                eng.quit()
            except Exception as e: print(f"UCI probe: {e}")
            # Only commit if we are still the current request
            if my_token == self._fetch_token:
                self.uci_options  = opts
                self._uci_fetched = True

        import threading
        threading.Thread(target=_probe, daemon=True).start()

    def _persist_uci(self):
        if not self.engines: return
        path = self.engines[self.selected_idx].get("path","")
        if not path or path == "lichess_cloud": return
        if path not in self._all_configs: self._all_configs[path] = {}
        self._all_configs[path]["uci_options"] = {o["name"]: o["value"] for o in self.uci_options}
        self._save_engines_json()
        self.parent.status_msg = "UCI options saved!"

    def has_nnue(self, path):
        """Checks if the corresponding .nnue file exists in the engines/nnue folder"""
        if not path: return False
        base = os.path.splitext(os.path.basename(path))[0]
        p1 = os.path.join(os.path.dirname(path), "nnue", f"{base}.nnue")
        return os.path.exists(p1)
        
    def has_syzygy(self):
        """Checks if the syzygy folder exists and contains files"""
        s_path = self.parent.assets.path_syzygy
        if os.path.exists(s_path) and os.listdir(s_path):
            return True
        return False

    def draw(self, screen, fb, fm):
        self.draw_bg(screen, "Engine Management & Configuration", fb)
        self.zones = []
        PAD  = 18
        top_y = self.rect.y + 70
        bot_y = self.rect.bottom - 64

        col1_w = 220
        col2_w = 210
        col3_w = self.rect.width - col1_w - col2_w - PAD * 4

        list_r = pygame.Rect(self.rect.x + PAD, top_y, col1_w, bot_y - top_y)
        set_r  = pygame.Rect(list_r.right + PAD, top_y, col2_w, bot_y - top_y)
        uci_r  = pygame.Rect(set_r.right + PAD, top_y, col3_w, bot_y - top_y)

        # ── Col 1: engine list ────────────────────────────────────────────────
        pygame.draw.rect(screen, (245,245,250), list_r, border_radius=8)
        pygame.draw.rect(screen, (200,200,210), list_r, 1, border_radius=8)
        screen.blit(fb.render("Engines", True,(60,60,70)), (list_r.x+12, list_r.y+10))

        is_online = not (hasattr(self.parent,'network_monitor') and self.parent.network_monitor
                         and not self.parent.network_monitor.check_connection())
        cli = pygame.Rect(list_r.x, list_r.y+38, list_r.width, list_r.height-38)
        screen.set_clip(cli)
        total_h = len(self.engines)*52; max_s = max(0,total_h-cli.height)
        self.scroll = max(0,min(self.scroll,max_s))
        ey = cli.y - self.scroll
        for i, eng in enumerate(self.engines):
            if ey+52<cli.y: ey+=52; continue
            if ey>cli.bottom: break
            is_lc = eng["path"]=="lichess_cloud"
            is_dis = is_lc and not is_online
            er = pygame.Rect(cli.x+8, ey, cli.width-16, 46)
            is_sel = (i==self.selected_idx)
            bg = (240,240,240) if is_dis else ((218,230,255) if is_sel else ((232,238,248) if er.collidepoint(pygame.mouse.get_pos()) else (255,255,255)))
            pygame.draw.rect(screen,bg,er,border_radius=6)
            if is_sel and not is_dis: pygame.draw.rect(screen,(100,150,220),er,2,border_radius=6)
            nc = (150,150,150) if is_dis else ((20,20,20) if is_sel else (70,70,70))
            _ename = eng["name"] if len(eng["name"]) <= 18 else eng["name"][:17] + "…"
            screen.blit(fm.render(_ename,True,nc),(er.x+10,er.y+4))
            sp = eng["path"][-28:] if len(eng.get("path",""))>28 else eng.get("path","")
            pt = "Offline" if is_dis else ("Cloud API" if is_lc else f"…{sp}")
            pc = (200,80,80) if is_dis else (120,120,130)
            screen.blit(self.parent.font_s.render(pt,True,pc),(er.x+10,er.y+24))
            if not is_dis: self.zones.append((er,"select_engine",i))
            ey+=52
        screen.set_clip(None)

        # ── Col 2: core settings ──────────────────────────────────────────────
        pygame.draw.rect(screen,(250,250,252),set_r,border_radius=8)
        pygame.draw.rect(screen,(200,200,210),set_r,1,border_radius=8)
        screen.blit(fb.render("Core Settings",True,(60,60,70)),(set_r.x+12,set_r.y+10))

        sel_path = self.engines[self.selected_idx]["path"] if self.engines and 0 <= self.selected_idx < len(self.engines) else ""
        sy = set_r.y + 42
        self._draw_status_pill(screen,"NNUE",   self.has_nnue(sel_path), set_r.x+12, sy)
        self._draw_status_pill(screen,"Syzygy", self.has_syzygy(),        set_r.x+12, sy+28)
        sy += 66

        _is_cloud = sel_path == "lichess_cloud"
        sy = self._draw_spinner(screen,fm,"Depth",   self.engine_settings['depth'],   1,65,  set_r.x+12,sy,"depth",   disabled=_is_cloud)
        sy = self._draw_spinner(screen,fm,"Threads",  self.engine_settings['threads'],  1,64,  set_r.x+12,sy,"threads", disabled=_is_cloud)
        sy = self._draw_spinner(screen,fm,"Hash MB",  self.engine_settings['hash_size'],16,8192,set_r.x+12,sy,"hash",   step=64, disabled=_is_cloud)
        sy = self._draw_spinner(screen,fm,"MultiPV",  self.engine_settings['multi_pv'], 1,10,  set_r.x+12,sy,"multipv", disabled=_is_cloud)

        cr = pygame.Rect(set_r.x+12, sy+8, 18, 18)
        cc = (80,180,80) if self.engine_settings['use_cloud'] else (200,200,200)
        pygame.draw.rect(screen,cc,cr,border_radius=4)
        if self.engine_settings['use_cloud']:
            pygame.draw.line(screen,(255,255,255),(cr.x+3,cr.centery),(cr.centerx-1,cr.bottom-3),2)
            pygame.draw.line(screen,(255,255,255),(cr.centerx-1,cr.bottom-3),(cr.right-3,cr.y+3),2)
        screen.blit(self.parent.font_s.render("Use Lichess Cloud",True,(60,60,60)),(cr.right+8,cr.y+1))
        self.zones.append((cr,"toggle_cloud",None))

        apply_r = pygame.Rect(set_r.x+12, bot_y-46, set_r.width-24, 38)
        ac = (55,175,55) if apply_r.collidepoint(pygame.mouse.get_pos()) else (45,155,45)
        pygame.draw.rect(screen,ac,apply_r,border_radius=8)
        at = fm.render("Apply & Restart",True,(255,255,255))
        screen.blit(at,(apply_r.centerx-at.get_width()//2,apply_r.centery-at.get_height()//2))
        self.zones.append((apply_r,"apply",None))

        # ── Col 3: UCI options ────────────────────────────────────────────────
        pygame.draw.rect(screen,(248,248,252),uci_r,border_radius=8)
        pygame.draw.rect(screen,(200,200,210),uci_r,1,border_radius=8)
        screen.blit(fb.render("Engine Options (UCI)",True,(60,60,70)),(uci_r.x+12,uci_r.y+10))

        if not self._uci_fetched:
            screen.blit(fm.render("Probing engine…",True,(140,140,160)),(uci_r.x+18,uci_r.y+50))
        elif not self.uci_options:
            screen.blit(fm.render("No configurable options.",True,(160,160,165)),(uci_r.x+18,uci_r.y+50))
        else:
            uc = pygame.Rect(uci_r.x, uci_r.y+38, uci_r.width, uci_r.height-88)
            screen.set_clip(uc)
            row_h = 34
            max_us = max(0, len(self.uci_options)*row_h - uc.height)
            self.uci_scroll = max(0,min(self.uci_scroll,max_us))
            uy = uc.y - self.uci_scroll
            mpos = pygame.mouse.get_pos()
            for i, opt in enumerate(self.uci_options):
                if uy+row_h<uc.y: uy+=row_h; continue
                if uy>uc.bottom: break
                rr = pygame.Rect(uci_r.x+5, uy+2, uci_r.width-10, row_h-4)
                bg2 = (228,236,255) if rr.collidepoint(mpos) else ((240,240,250) if i%2==0 else (252,252,255))
                pygame.draw.rect(screen,bg2,rr,border_radius=4)
                ns = self.parent.font_s.render(opt["name"],True,(40,40,52))
                screen.blit(ns,(rr.x+7, rr.y+(row_h-4-ns.get_height())//2))
                vs = str(opt["value"]) if opt["value"] is not None else str(opt["default"])
                ot = opt["type"]
                if ot=="check":
                    on = str(opt["value"]).lower() in("true","1","yes")
                    pill = pygame.Rect(rr.right-62, rr.y+5, 54, 24)
                    pygame.draw.rect(screen,(70,175,70) if on else (175,175,175),pill,border_radius=12)
                    pt2 = self.parent.font_s.render("ON" if on else "OFF",True,(255,255,255))
                    screen.blit(pt2,(pill.centerx-pt2.get_width()//2,pill.centery-pt2.get_height()//2))
                    self.zones.append((pill,"uci_toggle",i))
                elif ot=="spin" and opt["min"] is not None:
                    bm = pygame.Rect(rr.right-108, rr.y+5, 24, 24)
                    bp = pygame.Rect(rr.right-28,  rr.y+5, 24, 24)
                    vb = pygame.Rect(bm.right+3,   rr.y+5, bp.left - bm.right - 6, 24)
                    pygame.draw.rect(screen,(208,208,215),bm,border_radius=5)
                    pygame.draw.rect(screen,(208,208,215),bp,border_radius=5)
                    pygame.draw.rect(screen,(244,244,250),vb,border_radius=4)
                    pygame.draw.rect(screen,(210,210,220),vb,1,border_radius=4)
                    for _r3,_t3 in[(bm,"−"),(bp,"+")]:
                        _s3=self.parent.font_s.render(_t3,True,(40,40,40))
                        screen.blit(_s3,(_r3.centerx-_s3.get_width()//2,_r3.centery-_s3.get_height()//2))
                    _vs=self.parent.font_s.render(vs,True,(20,20,20))
                    screen.blit(_vs,(vb.centerx-_vs.get_width()//2,vb.centery-_vs.get_height()//2))
                    self.zones.append((bm,"uci_dec",i)); self.zones.append((bp,"uci_inc",i))
                elif ot=="combo" and opt["var"]:
                    al  = pygame.Rect(rr.right-108, rr.y+5, 24, 24)
                    ar  = pygame.Rect(rr.right-28,  rr.y+5, 24, 24)
                    vb2 = pygame.Rect(al.right+3,   rr.y+5, ar.left - al.right - 6, 24)
                    pygame.draw.rect(screen,(208,208,215),al,border_radius=5)
                    pygame.draw.rect(screen,(208,208,215),ar,border_radius=5)
                    pygame.draw.rect(screen,(244,244,250),vb2,border_radius=4)
                    pygame.draw.rect(screen,(210,210,220),vb2,1,border_radius=4)
                    for _r4,_t4 in[(al,"◀"),(ar,"▶")]:
                        _s4=self.parent.font_s.render(_t4,True,(40,40,40))
                        screen.blit(_s4,(_r4.centerx-_s4.get_width()//2,_r4.centery-_s4.get_height()//2))
                    _vs2=self.parent.font_s.render(str(opt["value"])[:8],True,(20,20,20))
                    screen.blit(_vs2,(vb2.centerx-_vs2.get_width()//2,vb2.centery-_vs2.get_height()//2))
                    self.zones.append((al,"uci_combo_prev",i)); self.zones.append((ar,"uci_combo_next",i))
                else:
                    _vs3=self.parent.font_s.render(vs[:14],True,(90,90,100))
                    screen.blit(_vs3,(rr.right-_vs3.get_width()-10,rr.y+(row_h-4-_vs3.get_height())//2))
                uy+=row_h
            screen.set_clip(None)

            # ── Scrollbar for UCI list ────────────────────────────────────────
            if max_us > 0:
                sb_track = pygame.Rect(uci_r.right-8, uc.y, 5, uc.height)
                pygame.draw.rect(screen, (220,220,228), sb_track, border_radius=3)
                thumb_h   = max(24, int(uc.height * uc.height / (len(self.uci_options)*row_h)))
                thumb_y   = uc.y + int((uc.height - thumb_h) * self.uci_scroll / max_us)
                sb_thumb  = pygame.Rect(uci_r.right-8, thumb_y, 5, thumb_h)
                pygame.draw.rect(screen, (160,160,175), sb_thumb, border_radius=3)

            save_uci_r = pygame.Rect(uci_r.x+12, bot_y-46, uci_r.width-24, 38)
            sc2 = (45,110,185) if save_uci_r.collidepoint(pygame.mouse.get_pos()) else (38,95,165)
            pygame.draw.rect(screen,sc2,save_uci_r,border_radius=8)
            st2=fm.render("Save UCI Options",True,(255,255,255))
            screen.blit(st2,(save_uci_r.centerx-st2.get_width()//2,save_uci_r.centery-st2.get_height()//2))
            self.zones.append((save_uci_r,"save_uci",None))

    def _draw_status_pill(self, screen, label, is_active, x, y):
        color = (80,180,80) if is_active else (180,180,180)
        surf  = self.parent.font_s.render(f"{label}: {'ON' if is_active else 'OFF'}", True, (255,255,255))
        r = pygame.Rect(x, y, surf.get_width()+18, 24)
        pygame.draw.rect(screen, color, r, border_radius=12)
        screen.blit(surf, (x+9, r.centery - surf.get_height()//2))

    def _draw_spinner(self, screen, fm, label, value, min_v, max_v, x, y, tag, step=1, disabled=False):
        lbl_col = (180,180,185) if disabled else (75,75,85)
        btn_col = (232,232,235) if disabled else (218,218,228)
        txt_col = (170,170,175) if disabled else (40,40,40)
        val_col = (180,180,185) if disabled else (20,20,20)
        screen.blit(fm.render(label, True, lbl_col), (x, y+6))
        bm = pygame.Rect(x+80,  y+1, 28, 28)
        bp = pygame.Rect(x+158, y+1, 28, 28)
        vb = pygame.Rect(bm.right+3, y+1, bp.left - bm.right - 6, 28)
        pygame.draw.rect(screen, (244,244,250), vb, border_radius=5)
        pygame.draw.rect(screen, (210,210,220), vb, 1, border_radius=5)
        for _r,_l in[(bm,"−"),(bp,"+")]:
            pygame.draw.rect(screen, btn_col, _r, border_radius=5)
            _s=fm.render(_l, True, txt_col)
            screen.blit(_s,(_r.centerx-_s.get_width()//2,_r.centery-_s.get_height()//2))
        vs=fm.render(str(value), True, val_col)
        screen.blit(vs,(vb.centerx-vs.get_width()//2, vb.y+(vb.height-vs.get_height())//2))
        if not disabled:
            self.zones.append((bm,"dec",(tag,min_v,step)))
            self.zones.append((bp,"inc",(tag,max_v,step)))
        return y+42

    def handle_scroll(self, e):
        uci_left = self.rect.x + 18 + 220 + 18 + 210 + 18
        if pygame.mouse.get_pos()[0] > uci_left:
            if e.button==4: self.uci_scroll=max(0,self.uci_scroll-30)
            elif e.button==5: self.uci_scroll+=30
        else:
            if e.button==4: self.scroll=max(0,self.scroll-40)
            elif e.button==5: self.scroll+=40

    def handle_click(self, pos):
        if self.close_btn and self.close_btn.collidepoint(pos): self.active=False; return
        for rect, action, data in self.zones:
            if rect.collidepoint(pos):
                if action=="select_engine":
                    self.selected_idx=data
                    self.engine_settings=self._settings_for(data)
                    self.uci_options=[]; self._uci_fetched=False
                    self.uci_scroll = 0
                    self._fetch_uci_async()
                elif action=="dec":
                    tag,min_v,step=data
                    if tag=="depth":   self.engine_settings['depth']   =max(min_v,self.engine_settings['depth']   -step)
                    elif tag=="threads":self.engine_settings['threads'] =max(min_v,self.engine_settings['threads'] -step)
                    elif tag=="hash":   self.engine_settings['hash_size']=max(min_v,self.engine_settings['hash_size']-step)
                    elif tag=="multipv":self.engine_settings['multi_pv']=max(min_v,self.engine_settings['multi_pv']-step)
                elif action=="inc":
                    tag,max_v,step=data
                    if tag=="depth":   self.engine_settings['depth']   =min(max_v,self.engine_settings['depth']   +step)
                    elif tag=="threads":self.engine_settings['threads'] =min(max_v,self.engine_settings['threads'] +step)
                    elif tag=="hash":   self.engine_settings['hash_size']=min(max_v,self.engine_settings['hash_size']+step)
                    elif tag=="multipv":self.engine_settings['multi_pv']=min(max_v,self.engine_settings['multi_pv']+step)
                elif action=="toggle_cloud":
                    self.engine_settings['use_cloud']=not self.engine_settings['use_cloud']
                elif action=="uci_toggle":
                    opt=self.uci_options[data]
                    opt["value"]=not(str(opt["value"]).lower() in("true","1","yes"))
                elif action=="uci_dec":
                    opt=self.uci_options[data]
                    try:
                        v=int(opt["value"])-1
                        if opt["min"] is not None: v=max(int(opt["min"]),v)
                        opt["value"]=v
                    except Exception: pass
                elif action=="uci_inc":
                    opt=self.uci_options[data]
                    try:
                        v=int(opt["value"])+1
                        if opt["max"] is not None: v=min(int(opt["max"]),v)
                        opt["value"]=v
                    except Exception: pass
                elif action=="uci_combo_prev":
                    opt=self.uci_options[data]
                    if opt["var"]:
                        try: idx2=opt["var"].index(str(opt["value"]))
                        except ValueError: idx2=0
                        opt["value"]=opt["var"][(idx2-1)%len(opt["var"])]
                elif action=="uci_combo_next":
                    opt=self.uci_options[data]
                    if opt["var"]:
                        try: idx2=opt["var"].index(str(opt["value"]))
                        except ValueError: idx2=0
                        opt["value"]=opt["var"][(idx2+1)%len(opt["var"])]
                elif action=="save_uci":
                    self._persist_uci()
                elif action=="apply":
                    self.apply_settings()
                return

    def apply_settings(self):
        if not self.engines: return
        sel_eng=self.engines[self.selected_idx]
        key=sel_eng.get("path","")
        if key and key!="lichess_cloud":
            if key not in self._all_configs: self._all_configs[key]={}
            self._all_configs[key].update(self.engine_settings)
            self._save_engines_json()
        self.parent.max_depth          =self.engine_settings['depth']
        self.parent.engine_threads     =self.engine_settings['threads']
        self.parent.engine_hash        =self.engine_settings['hash_size']
        self.parent.engine_multipv     =self.engine_settings['multi_pv']
        self.parent.use_cloud_analysis =self.engine_settings['use_cloud']
        self.parent.settings["engine_threads"]     =self.engine_settings['threads']
        self.parent.settings["engine_hash"]        =self.engine_settings['hash_size']
        self.parent.settings["engine_multipv"]     =self.engine_settings['multi_pv']
        self.parent.settings["use_cloud_analysis"] =self.engine_settings['use_cloud']
        self.parent.save_config()
        if hasattr(self.parent,'analyzer') and self.parent.analyzer:
            self.parent.analyzer.threads  =self.engine_settings['threads']
            self.parent.analyzer.hash_size=self.engine_settings['hash_size']
            self.parent.analyzer.multipv  =self.engine_settings['multi_pv']
        self.parent.current_engine_info=sel_eng
        self.parent.change_engine(sel_eng)
        self.active=False

    def save_engine_settings(self):
        self.apply_settings()

# =============================================================================
#  PHASE STATS POPUP
# =============================================================================
class PhaseStatsPopup(BasePopup):
    def __init__(self, parent, stats):
        super().__init__(parent, 500, 400)
        self.stats = stats

    def draw(self, screen, fb, fm):
        self.draw_bg(screen, "Detailed Phase Analysis", fb)
        
        y = self.rect.y + 80
        phases = ["Opening", "Middlegame", "Endgame"]
        keys = ["opening", "middlegame", "endgame"]
        
        for i, ph in enumerate(phases):
            score = self.stats.get(keys[i], 0)

            label = fb.render(ph, True, (0,0,0))
            screen.blit(label, (self.rect.x + 40, y + 3))

            bar_bg = pygame.Rect(self.rect.x + 170, y, 260, 26)
            pygame.draw.rect(screen, (220, 220, 220), bar_bg, border_radius=13)

            fill_w = int((score / 100) * 260)
            col = (200, 50, 50)
            if score > 50: col = (220, 180, 50)
            if score > 80: col = (50, 180, 50)
            if fill_w > 0:
                bar_fill = pygame.Rect(bar_bg.x, bar_bg.y, fill_w, 26)
                pygame.draw.rect(screen, col, bar_fill, border_radius=13)

            score_surf = fm.render(f"{score}/100", True, (40, 40, 40))
            screen.blit(score_surf, (bar_bg.right + 14, y + (26 - score_surf.get_height())//2))

            y += 80

    def handle_click(self, pos):
        if self.close_btn.collidepoint(pos): self.active = False

# =============================================================================
#  PROMOTION POPUP
# =============================================================================
class PromotionPopup:
    def __init__(self, parent, color, f, t):
        self.parent = parent; self.color = color; self.ft = (f, t)
        self.active = True
        self.rect = pygame.Rect(parent.width//2-200, parent.height//2-80, 400, 160)
        self.zones = []

    def draw(self, screen):
        ov = pygame.Surface(screen.get_size(), pygame.SRCALPHA); ov.fill((0,0,0,160)); screen.blit(ov, (0,0))
        shadow_surf = pygame.Surface((self.rect.width + 10, self.rect.height + 10), pygame.SRCALPHA)
        pygame.draw.rect(shadow_surf, (0, 0, 0, 45), shadow_surf.get_rect(), border_radius=20)
        screen.blit(shadow_surf, (self.rect.x - 2, self.rect.y + 8))
        pygame.draw.rect(screen, (252, 252, 254), self.rect, border_radius=16)
        pygame.draw.rect(screen, (210, 210, 215), self.rect, 2, border_radius=16)

        title = self.parent.font_b.render("Promote Pawn", True, (30, 30, 30))
        screen.blit(title, (self.rect.centerx - title.get_width()//2, self.rect.y + 10))

        pcs = [chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT]
        names = ["Queen", "Rook", "Bishop", "Knight"]
        c = 'w' if self.color == chess.WHITE else 'b'

        card_w = 80
        gap = 10
        total = card_w * 4 + gap * 3
        bx = self.rect.centerx - total // 2
        self.zones = []

        for i, p in enumerate(pcs):
            r = pygame.Rect(bx, self.rect.y + 44, card_w, 95)
            col = (225, 235, 255) if r.collidepoint(pygame.mouse.get_pos()) else (248, 248, 248)
            pygame.draw.rect(screen, col, r, border_radius=8)
            pygame.draw.rect(screen, (200,200,200), r, 1, border_radius=8)

            k = c + chess.Piece(p, self.color).symbol().lower()
            if k in self.parent.assets.pieces:
                img = pygame.transform.smoothscale(self.parent.assets.pieces[k], (58, 58))
                screen.blit(img, (r.centerx - 29, r.y + 6))

            f = self.parent.font_s
            t = f.render(names[i], True, (30, 30, 30))
            screen.blit(t, (r.centerx - t.get_width()//2, r.bottom - 22))

            self.zones.append((r, p))
            bx += card_w + gap

    def handle_click(self, pos):
        for r, p in self.zones:
            if r.collidepoint(pos):
                m = chess.Move(self.ft[0], self.ft[1], promotion=p)
                self.parent.finish_promotion(m)
                self.active = False

# =============================================================================
#  POSITION COMPLEXITY POPUP  (H key)
# =============================================================================
class ComplexityPopup:
    """Live position complexity score with phase breakdown. Toggle with H key."""
    def __init__(self, parent):
        self.parent = parent
        self.active = True
        w, h = 380, 340
        self.rect = pygame.Rect(
            parent.width - w - 20,
            parent.bd_y if hasattr(parent, 'bd_y') else 80,
            w, h
        )
        self.close_btn = None
        self._last_fen = None
        self._score_cache = None

    def _compute(self):
        """Compute complexity score for the currently viewed board."""
        try:
            view_ply = getattr(self.parent, 'view_ply', 0)
            history = getattr(self.parent, 'history', [])
            board = chess.Board()
            for i in range(min(view_ply, len(history))):
                if isinstance(history[i], dict) and "move" in history[i]:
                    board.push(history[i]["move"])

            fen = board.fen()
            if fen == self._last_fen and self._score_cache is not None:
                return self._score_cache

            self._last_fen = fen

            # Count legal moves
            legal = list(board.legal_moves)
            n_legal = len(legal)

            # Hanging pieces
            hanging = 0
            for sq in chess.SQUARES:
                p = board.piece_at(sq)
                if p and board.is_attacked_by(not p.color, sq):
                    if not board.is_attacked_by(p.color, sq):
                        hanging += 1

            # Captures available
            n_caps = sum(1 for m in legal if board.is_capture(m))

            # Checks available
            n_checks = sum(1 for m in legal if board.gives_check(m))

            # Phase (piece count heuristic)
            pieces_left = sum(1 for sq in chess.SQUARES if board.piece_at(sq)
                              and board.piece_at(sq).piece_type != chess.PAWN)
            if pieces_left >= 12: phase = "Opening"
            elif pieces_left >= 6: phase = "Middlegame"
            else: phase = "Endgame"

            # Normalize each component to 0-100
            mobility_score = min(100, int(n_legal * 2.5))
            tension_score  = min(100, int(hanging * 20 + n_caps * 8))
            tactic_score   = min(100, int(n_checks * 25 + n_caps * 6))
            phase_mult = {"Opening": 0.7, "Middlegame": 1.0, "Endgame": 0.85}.get(phase, 1.0)
            overall = int((mobility_score * 0.3 + tension_score * 0.45 + tactic_score * 0.25) * phase_mult)
            overall = min(100, overall)

            self._score_cache = {
                "overall": overall,
                "mobility": mobility_score,
                "tension": tension_score,
                "tactics": tactic_score,
                "phase": phase,
                "hanging": hanging,
                "captures": n_caps,
                "checks": n_checks,
                "legal": n_legal,
            }
            return self._score_cache
        except Exception as e:
            return None

    def draw(self, screen, fb, fm):
        if not self.active: return

        # Panel
        pygame.draw.rect(screen, (245, 245, 250), self.rect, border_radius=14)
        pygame.draw.rect(screen, (190, 190, 200), self.rect, 2, border_radius=14)

        # Title
        title = fb.render("Position Complexity", True, (35, 35, 42))
        screen.blit(title, (self.rect.x + 16, self.rect.y + 14))

        # Close
        self.close_btn = pygame.Rect(self.rect.right - 36, self.rect.y + 12, 24, 24)
        cc = (220, 80, 80) if self.close_btn.collidepoint(pygame.mouse.get_pos()) else (200, 200, 208)
        pygame.draw.rect(screen, cc, self.close_btn, border_radius=6)
        cx_s = self.parent.font_s.render("×", True, (255, 255, 255))
        screen.blit(cx_s, (self.close_btn.centerx - cx_s.get_width() // 2,
                            self.close_btn.centery - cx_s.get_height() // 2))

        # H-key hint
        hint = self.parent.font_s.render("Press H to toggle", True, (160, 160, 170))
        screen.blit(hint, (self.rect.right - hint.get_width() - 40, self.rect.y + 17))

        data = self._compute()
        if not data:
            screen.blit(fm.render("No position loaded.", True, (130, 130, 130)),
                        (self.rect.x + 20, self.rect.y + 80))
            return

        y = self.rect.y + 50
        pad = 18

        # Overall score arc / big number
        overall = data["overall"]
        arc_col = (50, 180, 50) if overall >= 70 else (220, 170, 40) if overall >= 40 else (200, 60, 60)
        big = pygame.font.SysFont("Segoe UI", 42, bold=True).render(str(overall), True, arc_col)
        screen.blit(big, (self.rect.x + pad, y))
        lbl = self.parent.font_s.render("/ 100  Complexity", True, (100, 100, 110))
        screen.blit(lbl, (self.rect.x + pad + big.get_width() + 8, y + 18))

        # Phase pill
        phase_cols = {"Opening": (80, 140, 220), "Middlegame": (220, 130, 40), "Endgame": (80, 160, 100)}
        pc = phase_cols.get(data["phase"], (120, 120, 140))
        pr = pygame.Rect(self.rect.right - 120, y + 4, 100, 26)
        pygame.draw.rect(screen, pc, pr, border_radius=13)
        pt = self.parent.font_s.render(data["phase"], True, (255, 255, 255))
        screen.blit(pt, (pr.centerx - pt.get_width() // 2, pr.centery - pt.get_height() // 2))

        y += 60

        # Sub-bars
        sub_items = [
            ("Mobility",  data["mobility"],  (80, 130, 210)),
            ("Tension",   data["tension"],   (210, 100, 60)),
            ("Tactics",   data["tactics"],   (160, 70, 200)),
        ]
        bar_w = self.rect.width - pad * 2
        for label, val, col3 in sub_items:
            screen.blit(fm.render(label, True, (60, 60, 70)), (self.rect.x + pad, y))
            val_txt = self.parent.font_s.render(str(val), True, (80, 80, 90))
            screen.blit(val_txt, (self.rect.right - pad - val_txt.get_width(), y + 2))

            pygame.draw.rect(screen, (218, 218, 225),
                             pygame.Rect(self.rect.x + pad, y + 20, bar_w, 10), border_radius=5)
            fill_w = int((val / 100) * bar_w)
            if fill_w > 0:
                pygame.draw.rect(screen, col3,
                                 pygame.Rect(self.rect.x + pad, y + 20, fill_w, 10), border_radius=5)
            y += 44

        # Raw counts
        pygame.draw.line(screen, (210, 210, 218),
                         (self.rect.x + pad, y), (self.rect.right - pad, y))
        y += 10
        stats_txt = (f"Legal: {data['legal']}   "
                     f"Captures: {data['captures']}   "
                     f"Checks: {data['checks']}   "
                     f"Hanging: {data['hanging']}")
        st = self.parent.font_s.render(stats_txt, True, (110, 110, 120))
        screen.blit(st, (self.rect.x + pad, y))

    def handle_click(self, pos):
        if self.close_btn and self.close_btn.collidepoint(pos):
            self.active = False

    def handle_scroll(self, e): pass

# =============================================================================
#  MISSED WINS POPUP
# =============================================================================
class MissedWinsPopup:
    """Shows mini boards for positions where a winning advantage was let slip."""
    def __init__(self, parent, missed_wins, history):
        self.parent = parent
        self.missed_wins = missed_wins
        self.history = history
        self.active = True
        self.current = 0

        # Geometry — wider & taller so the board breathes
        w, h = 700, 580
        self.rect = pygame.Rect(
            (parent.width  - w) // 2,
            (parent.height - h) // 2,
            w, h
        )
        self.close_btn = None
        self.btn_prev  = None
        self.btn_next  = None
        self.btn_jump  = None

        self._board_cache = {}   # idx → chess.Board

    # ------------------------------------------------------------------ helpers
    def _get_board_at(self, idx):
        if idx in self._board_cache:
            return self._board_cache[idx]
        b = chess.Board()
        for i, step in enumerate(self.history):
            if i > idx: break
            if isinstance(step, dict) and "move" in step:
                try: b.push(step["move"])
                except Exception: pass
        self._board_cache[idx] = b
        return b

    def _render_mini_board(self, board, sq_sz):
        from assets import THEME
        style = getattr(self.parent, 'board_style', 'wood')
        cols  = THEME.get(style, THEME.get('wood', {}))
        light = cols.get('light', (240, 217, 181))
        dark  = cols.get('dark',  (181, 136, 99))

        surf = pygame.Surface((sq_sz * 8, sq_sz * 8))
        for r in range(8):
            for c in range(8):
                col = light if (r + c) % 2 == 0 else dark
                pygame.draw.rect(surf, col, (c * sq_sz, r * sq_sz, sq_sz, sq_sz))

        assets = getattr(self.parent, 'assets', None)
        if assets:
            scaled_pc = {}
            for sq in chess.SQUARES:
                p = board.piece_at(sq)
                if not p: continue
                key = ('w' if p.color else 'b') + p.symbol().lower()
                raw = assets.pieces.get(key)
                if not raw: continue
                if key not in scaled_pc:
                    scaled_pc[key] = pygame.transform.smoothscale(raw, (sq_sz - 4, sq_sz - 4))
                f  = chess.square_file(sq)
                r2 = 7 - chess.square_rank(sq)
                surf.blit(scaled_pc[key], (f * sq_sz + 2, r2 * sq_sz + 2))
        return surf

    def _draw_best_arrow(self, screen, bd_x, bd_y, sq_sz, move):
        """Dashed green arrow showing the best move the player should have played."""
        import math
        f1 = chess.square_file(move.from_square); r1 = 7 - chess.square_rank(move.from_square)
        f2 = chess.square_file(move.to_square);   r2 = 7 - chess.square_rank(move.to_square)
        x1 = bd_x + f1 * sq_sz + sq_sz // 2;  y1 = bd_y + r1 * sq_sz + sq_sz // 2
        x2 = bd_x + f2 * sq_sz + sq_sz // 2;  y2 = bd_y + r2 * sq_sz + sq_sz // 2
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)
        if length < 1: return
        nx, ny   = dx / length, dy / length
        color    = (20, 170, 80)
        tip_gap  = sq_sz * 0.28        # stop dashes before arrowhead
        dash, gap = 9, 5
        pos, drawing = 0.0, True
        while pos < length - tip_gap:
            end = min(pos + (dash if drawing else gap), length - tip_gap)
            if drawing:
                pygame.draw.line(screen, color,
                                 (int(x1 + nx * pos), int(y1 + ny * pos)),
                                 (int(x1 + nx * end), int(y1 + ny * end)), 3)
            pos += (dash if drawing else gap)
            drawing = not drawing
        # Arrowhead
        arr = sq_sz * 0.30
        angle = math.atan2(dy, dx)
        pts = [
            (x2, y2),
            (x2 - arr * math.cos(angle - math.pi / 6), y2 - arr * math.sin(angle - math.pi / 6)),
            (x2 - arr * math.cos(angle + math.pi / 6), y2 - arr * math.sin(angle + math.pi / 6)),
        ]
        pygame.draw.polygon(screen, color, [(int(px), int(py)) for px, py in pts])

    # ------------------------------------------------------------------ draw
    def draw(self, screen, fb, fm):
        import math

        # ── Overlay ──────────────────────────────────────────────────────────
        ov = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 170))
        screen.blit(ov, (0, 0))

        # ── Panel shadow + background ────────────────────────────────────────
        shd = pygame.Surface((self.rect.width + 12, self.rect.height + 20), pygame.SRCALPHA)
        pygame.draw.rect(shd, (0, 0, 0, 55), shd.get_rect(), border_radius=18)
        screen.blit(shd, (self.rect.x - 2, self.rect.y + 8))
        pygame.draw.rect(screen, (252, 252, 254), self.rect, border_radius=16)
        pygame.draw.rect(screen, (210, 210, 215), self.rect, 2, border_radius=16)

        # ── Title ────────────────────────────────────────────────────────────
        title_txt = fb.render("Missed Winning Moves", True, (40, 40, 45))
        screen.blit(title_txt, (self.rect.centerx - title_txt.get_width() // 2, self.rect.y + 18))

        # ── Close button ─────────────────────────────────────────────────────
        self.close_btn = pygame.Rect(self.rect.right - 44, self.rect.y + 14, 28, 28)
        close_col = (230, 80, 80) if self.close_btn.collidepoint(pygame.mouse.get_pos()) else (220, 220, 225)
        pygame.draw.rect(screen, close_col, self.close_btn, border_radius=7)
        cx_t = fb.render("×", True, (255, 255, 255) if self.close_btn.collidepoint(pygame.mouse.get_pos()) else (80, 80, 80))
        screen.blit(cx_t, (self.close_btn.centerx - cx_t.get_width() // 2,
                            self.close_btn.centery - cx_t.get_height() // 2))

        if not self.missed_wins:
            screen.blit(fm.render("No missed wins found.", True, (120, 120, 120)),
                        (self.rect.centerx - 80, self.rect.centery))
            return

        idx, step = self.missed_wins[self.current]

        # ── Board geometry ────────────────────────────────────────────────────
        sq_sz   = 52                           # 52×8 = 416 px board
        board_w = sq_sz * 8                    # 416
        bd_x    = self.rect.x + 22
        bd_y    = self.rect.y + 56

        # Show board BEFORE the bad move so the best-move arrow is meaningful
        board_before_idx = max(0, idx - 1)
        board_state = self._get_board_at(board_before_idx)
        board_surf  = self._render_mini_board(board_state, sq_sz)
        screen.blit(board_surf, (bd_x, bd_y))

        # Highlight from-square of the bad move (where they moved from)
        if isinstance(step, dict) and "move" in step:
            bad_move = step["move"]
            hl_from = pygame.Surface((sq_sz, sq_sz), pygame.SRCALPHA)
            hl_from.fill((220, 60, 60, 100))
            ff = chess.square_file(bad_move.from_square)
            rf = 7 - chess.square_rank(bad_move.from_square)
            screen.blit(hl_from, (bd_x + ff * sq_sz, bd_y + rf * sq_sz))

        # Best-move dashed arrow (green)
        best_uci = step.get("review", {}).get("best_move_uci")
        if best_uci:
            try:
                best_move_obj = chess.Move.from_uci(best_uci)
                if best_move_obj in board_state.legal_moves:
                    self._draw_best_arrow(screen, bd_x, bd_y, sq_sz, best_move_obj)
            except Exception:
                pass

        # Board border
        pygame.draw.rect(screen, (150, 150, 160),
                         pygame.Rect(bd_x - 1, bd_y - 1, board_w + 2, board_w + 2), 2, border_radius=4)

        # ── Info panel (right of board) ───────────────────────────────────────
        info_x = bd_x + board_w + 20
        info_w = self.rect.right - info_x - 18
        iy = bd_y

        # Move label
        ply      = step.get("ply", idx + 1)
        move_num = (ply + 1) // 2
        side     = "White" if ply % 2 != 0 else "Black"
        san      = step.get("san", "?")
        hdr = fb.render(f"Move {move_num})  {san}", True, (30, 30, 35))
        screen.blit(hdr, (info_x, iy))
        iy += 22
        side_lbl = self.parent.font_s.render(side, True, (120, 120, 130))
        screen.blit(side_lbl, (info_x, iy))
        iy += 30

        # Eval before / after box
        prev_cp = None
        if idx > 0 and isinstance(self.history[idx - 1], dict):
            prev_cp = self.history[idx - 1].get("review", {}).get("eval_cp")
        curr_cp = step.get("review", {}).get("eval_cp")

        def fmt_cp(v):
            if v is None: return "?"
            if abs(v) >= 9000: return ("+" if v > 0 else "") + "M"
            return f"{v / 100:+.2f}"

        eval_box = pygame.Rect(info_x, iy, info_w, 70)
        pygame.draw.rect(screen, (245, 245, 250), eval_box, border_radius=8)
        pygame.draw.rect(screen, (210, 210, 220), eval_box, 1, border_radius=8)

        screen.blit(self.parent.font_s.render("Before", True, (90, 90, 100)), (info_x + 10, iy + 8))
        before_col = (30, 150, 30) if (prev_cp or 0) > 0 else (190, 50, 50)
        screen.blit(fb.render(fmt_cp(prev_cp), True, before_col), (info_x + 10, iy + 28))

        mid = info_x + info_w // 2
        screen.blit(self.parent.font_s.render("After", True, (90, 90, 100)), (mid + 6, iy + 8))
        after_col = (30, 150, 30) if (curr_cp or 0) > 0 else (190, 50, 50)
        screen.blit(fb.render(fmt_cp(curr_cp), True, after_col), (mid + 6, iy + 28))

        # Divider between before/after
        pygame.draw.line(screen, (210, 210, 220), (mid, iy + 8), (mid, iy + 62), 1)
        iy += 82

        # Classification badge
        cls = step.get("review", {}).get("class", "move")
        cls_colors = {"blunder": (210, 50, 50), "mistake": (220, 130, 40),
                      "miss": (200, 80, 20), "inaccuracy": (190, 180, 30)}
        badge_col  = cls_colors.get(cls, (140, 140, 150))
        badge_rect = pygame.Rect(info_x, iy, min(info_w, 120), 28)
        pygame.draw.rect(screen, badge_col, badge_rect, border_radius=14)
        badge_txt = self.parent.font_s.render(cls.capitalize(), True, (255, 255, 255))
        screen.blit(badge_txt, (badge_rect.centerx - badge_txt.get_width() // 2,
                                badge_rect.centery - badge_txt.get_height() // 2))
        iy += 40

        # Best move hint label (just "Best: Nf3" — no wall of text)
        if best_uci:
            try:
                bm_obj = chess.Move.from_uci(best_uci)
                bm_san = board_state.san(bm_obj)
                bm_lbl = self.parent.font_s.render(f"Best:  {bm_san}", True, (20, 140, 70))
                screen.blit(bm_lbl, (info_x, iy))
                iy += 22
            except Exception:
                pass

        # ── Jump button — full width, anchored just above nav bar ────────────
        jump_y = self.rect.bottom - 96
        self.btn_jump = pygame.Rect(self.rect.x + 20, jump_y, self.rect.width - 40, 34)
        jcol = (50, 130, 200) if self.btn_jump.collidepoint(pygame.mouse.get_pos()) else (40, 110, 180)
        pygame.draw.rect(screen, jcol, self.btn_jump, border_radius=8)
        jt = fm.render("Jump to Position", True, (255, 255, 255))
        screen.blit(jt, (self.btn_jump.centerx - jt.get_width() // 2,
                          self.btn_jump.centery - jt.get_height() // 2))

        # ── Navigation bar — Prev | counter | Next ────────────────────────────
        nav_y   = self.rect.bottom - 50
        total   = len(self.missed_wins)
        btn_w2  = 100

        self.btn_prev = pygame.Rect(self.rect.x + 24,                   nav_y, btn_w2, 34)
        self.btn_next = pygame.Rect(self.rect.right - 24 - btn_w2,      nav_y, btn_w2, 34)

        for btn, label, enabled in [(self.btn_prev, "← Prev", self.current > 0),
                                     (self.btn_next, "Next →", self.current < total - 1)]:
            col2 = (160, 160, 168) if not enabled else \
                   (100, 160, 100) if btn.collidepoint(pygame.mouse.get_pos()) else (80, 140, 80)
            pygame.draw.rect(screen, col2, btn, border_radius=8)
            bt = fm.render(label, True, (255, 255, 255) if enabled else (210, 210, 210))
            screen.blit(bt, (btn.centerx - bt.get_width() // 2,
                              btn.centery - bt.get_height() // 2))

        # Counter centred between the two buttons
        counter_txt = fb.render(f"{self.current + 1} / {total}", True, (60, 60, 70))
        screen.blit(counter_txt, (self.rect.centerx - counter_txt.get_width() // 2,
                                  nav_y + (34 - counter_txt.get_height()) // 2))

    def handle_click(self, pos):
        if self.close_btn and self.close_btn.collidepoint(pos):
            self.active = False
            return
        if self.btn_prev and self.btn_prev.collidepoint(pos) and self.current > 0:
            self.current -= 1
            return
        if self.btn_next and self.btn_next.collidepoint(pos) and self.current < len(self.missed_wins) - 1:
            self.current += 1
            return
        if self.btn_jump and self.btn_jump.collidepoint(pos):
            idx, _ = self.missed_wins[self.current]
            self.parent.view_ply = idx + 1
            self.parent.update_opening_label()
            self.active = False
            return

    def handle_scroll(self, e): pass

# =============================================================================
#  REVIEW POPUP
# =============================================================================
class ReviewPopup:
    def __init__(self, parent, history, engine, assets, headers=None, cached_results=None):
        self.parent = parent; self.history = history
        self.engine_path = engine; self.assets = assets 
        self.headers = headers or {}
        self.active = True; self.status = "Analyzing... 0%"
        self.stats = {}; self.ratings = {"white":0, "black":0}
        self.graph_surface = None
        
        # --- NEW: Setup container for detailed Phase ELO math ---
        self.detailed_review = None 
        
        # Full-screen size — overridden dynamically by update_rect
        self.w, self.h = 1400, 900 
        
        self.rect = pygame.Rect(0,0,self.w,self.h)
        self.update_rect()
        self.close_btn = None
        self.move_scroll = 0
        self.selected_move_idx = -1 
        
        # Settings State - DISABLED FOR DIRECT REVIEW
        self.settings_mode = False 
        self.set_time = 1.0
        self.set_depth = 18 # Default to 18
        self.worker = None

        # Input handling state
        self.input_focus = -1 
        self.input_values = ["1.0", "18"]
        self.input_rects = []
        self.cursor_timer = 0
        self.btn_start = None
        self.btn_missed_wins = None
        self.missed_wins_popup = None
        self._missed_wins_cache = []
        self.graph_cursor_x = None
        self.btn_missed_wins = None          # shown only when missed wins exist
        self.missed_wins_popup = None        # sub-popup instance

        if not analysis_engine:
            self.status = "No Analysis Mod"
        
        # Load Cache if available
        if cached_results:
            try:
                if len(cached_results) == 5:
                    self.history, self.stats, self.ratings, self.graph_surface, _ = cached_results
                else:
                    self.history, self.stats, self.ratings, self.graph_surface = cached_results
                
                self.status = "Complete"
                # --- NEW: Generate detailed LucasChess metrics on cached loads ---
                self._generate_detailed_review()
            except Exception as e:
                print(f"Cache Load Error: {e}")
        
        # --- NEW: AUTO-START ANALYSIS IF NO CACHE ---
        elif analysis_engine:
            self.start_analysis()

    # --- NEW: Helper to generate phase metrics ---
    def _generate_detailed_review(self):
        try:
            # FIX: Dynamically inject the missing 'ply' integer into history
            # This guarantees the math engine knows exactly whose turn it was!
            for i, step in enumerate(self.history):
                if isinstance(step, dict) and "ply" not in step:
                    step["ply"] = i + 1

            w_name = self.headers.get("White", "White")
            b_name = self.headers.get("Black", "Black")
            
            # --- GOD-TIER FIX: Use the Analyzer's internal method so it perfectly syncs with CALIB_PARAMS! ---
            self.detailed_review = self.parent.analyzer.calculate_detailed_performance(self.history, w_name, b_name)
        except Exception as e:
            print(f"Failed to generate detailed review: {e}")
            self.detailed_review = None

    def update_rect(self):
        mw, mh = self.parent.width, self.parent.height
        self.w = mw - 20
        self.h = mh - 20
        self.rect = pygame.Rect((mw - self.w) // 2, (mh - self.h) // 2, self.w, self.h)

    def start_analysis(self):
        # --- FORCE DEPTH 20 ULTRA-SUPERFAST ANALYSIS ---
        self.set_time = 0.10  # Strict time cap per move
        self.set_depth = 20   # Target Depth 20
        
        self.settings_mode = False
        
        if analysis_engine:
            try:
                # FIX: Pass the book_positions set so full lines are recognized as Book moves!
                self.worker = analysis_engine.AnalysisEngine(
                    self.engine_path, 
                    opening_book=self.parent.assets.openings,
                    book_positions=self.parent.assets.book_positions
                )
                self.worker.start()
                threading.Thread(target=self.bg, daemon=True).start()
            except Exception as e:
                self.status = f"Engine Error: {e}"

    def bg(self):
        try:
            # FIX: Use the generator directly to update progress on UI!
            gen = self.worker.analyze_game_generator(
                self.history, 
                time_limit=self.set_time, 
                depth_limit=self.set_depth if self.set_depth > 0 else None
            )
            
            final_result = None
            for pct, res in gen:
                self.status = f"Analyzing... {pct}%"
                if res: final_result = res
                
            if final_result is None: raise Exception("Analysis returned None")
            
            bf = []
            if len(final_result) == 5:
                h, s, r, g, bf = final_result
            else:
                h, s, r, g = final_result

            # --- FIX: Securely merge the new analysis arrays into the main app state ---
            with self.parent.lock:
                self.history = h
                self.stats = s
                self.ratings = r
                self.graph_surface = g
                self.parent.history = h 
            
            # --- NEW: Generate detailed LucasChess metrics when analysis finishes ---
            self._generate_detailed_review()
            
            # --- Flag unsaved analysis so the app prompts before closing ---
            self.parent.unsaved_analysis = True
            
            self.parent.auto_archive_bot_game(s, r)
            
            if bf:
                self.parent.save_mate_popup = SaveMatePopup(self.parent, bf)
                self.parent.save_mate_popup.active = True

            self.parent.cached_review = (h, s, r, g, bf)
            self.status = "Complete"

            # --- Auto-generate puzzles from this game ---
            try:
                self._generate_game_puzzles(h)
            except Exception as _e:
                print(f"Puzzle generation skipped: {_e}")

            self.worker.stop()
        except Exception as e:
            print(f"Review Error: {e}")
            self.status = "Failed"

    def _generate_game_puzzles(self, history):
        """Scan game for fork/pin/mate positions the user actually played or missed, save as appmade puzzles."""
        import json, os, time as _time
        board = chess.Board()
        generated = []
        for i, step in enumerate(history):
            if not isinstance(step, dict) or "move" not in step: continue
            move = step["move"]
            rev  = step.get("review", {})
            cls  = rev.get("class", "")
            ply  = step.get("ply", i + 1)
            is_player = (ply % 2 != 0) == getattr(self.parent, 'playing_white', True)

            # Criteria: player missed a tactic (blunder/mistake) OR played a brilliant/great
            if cls in ("blunder", "mistake", "miss") and is_player:
                puzzle_type = "missed_tactic"
            elif cls in ("brilliant", "great") and is_player:
                puzzle_type = "brilliant_find"
            else:
                board.push(move)
                continue

            fen_before = board.fen()
            puzzle_name = f"Game Puzzle – Move {(ply+1)//2}) {step.get('san','?')} ({cls.capitalize()})"
            generated.append({
                "name": puzzle_name,
                "fen": fen_before,
                "type": puzzle_type,
                "source": "auto",
                "date": _time.strftime("%Y-%m-%d"),
            })
            board.push(move)

            if len(generated) >= 5:  # cap per game
                break

        if generated and hasattr(self.parent, 'assets'):
            existing = {p.get("fen") for p in self.parent.assets.appmade_puzzles}
            added = 0
            for p in generated:
                if p["fen"] not in existing:
                    self.parent.assets.appmade_puzzles.insert(0, p)
                    existing.add(p["fen"])
                    added += 1

            if added > 0:
                try:
                    path = os.path.join("assets", "puzzles", "appmade.json")
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(self.parent.assets.appmade_puzzles, f, indent=2)
                    self.parent.add_chat("System", f"{added} new puzzle(s) saved from this game!")
                except Exception as _e2:
                    print(f"Puzzle save error: {_e2}")
    
    def handle_click(self, pos):
        # Missed wins sub-popup gets clicks first
        if self.missed_wins_popup and self.missed_wins_popup.active:
            self.missed_wins_popup.handle_click(pos)
            return

        if self.close_btn and self.close_btn.collidepoint(pos): self.active = False
        if self.settings_mode:
            self.handle_settings_click(pos)
            return

        # Open missed wins popup
        if self.btn_missed_wins and self.btn_missed_wins.collidepoint(pos):
            mw = getattr(self, '_missed_wins_cache', [])
            if mw:
                self.missed_wins_popup = MissedWinsPopup(self.parent, mw, self.history)
                self.missed_wins_popup.active = True
            return

        # --- Eval Graph Click-to-Jump ---
        if hasattr(self, 'graph_rect') and self.graph_rect.collidepoint(pos):
            total_plies = max(10, len(self.history))
            if len(self.history) > 0:
                relative_x = pos[0] - self.graph_rect.x
                # Map pixel x → ply index (evals list has ply0 anchor at index 0)
                frac = relative_x / max(1, self.graph_rect.width)
                move_idx = int(round(frac * total_plies)) - 1
                move_idx = max(0, min(move_idx, len(self.history) - 1))
                self.selected_move_idx = move_idx
                self.parent.view_ply = move_idx + 1
                self.parent.update_opening_label()
                # Draw a vertical cursor line on next frame via stored x
                self.graph_cursor_x = self.graph_rect.x + int(frac * self.graph_rect.width)
                return
        # -----------------------------------------------

        left_col_w = self.rect.width * 62 // 100 - 30
        right_col_w = self.rect.width - left_col_w - 50
        right_x = self.rect.x + left_col_w + 40
        curr_y = self.rect.y + 70
        list_h = self.h - 90

        if right_x <= pos[0] <= right_x + right_col_w and curr_y <= pos[1] <= curr_y + list_h:
            rel_y = pos[1] - (curr_y + 10) + self.move_scroll
            idx = int(rel_y // 140) * 2
            if 0 <= idx < len(self.history):
                self.selected_move_idx = idx
                self.parent.view_ply = idx + 1
                self.parent.update_opening_label()
    
    def handle_settings_click(self, pos):
        if self.btn_start and self.btn_start.collidepoint(pos): 
            self.start_analysis()
            return

        self.input_focus = -1
        for i, rect in enumerate(self.input_rects):
            if rect.collidepoint(pos):
                self.input_focus = i
                return

    def handle_input(self, e):
        if self.settings_mode:
            if e.type == pygame.MOUSEBUTTONDOWN:
                self.handle_settings_click(e.pos)
            elif e.type == pygame.KEYDOWN:
                if self.input_focus >= 0:
                    val = self.input_values[self.input_focus]
                    if e.key == pygame.K_BACKSPACE:
                        self.input_values[self.input_focus] = val[:-1]
                    elif e.key == pygame.K_TAB:
                        self.input_focus = (self.input_focus + 1) % 2
                    elif e.key == pygame.K_RETURN or e.key == pygame.K_KP_ENTER:
                        self.input_focus = -1
                    elif e.key == pygame.K_UP: self.adjust_value(1)
                    elif e.key == pygame.K_DOWN: self.adjust_value(-1)
                    else:
                        char = e.unicode
                        if self.input_focus == 0: 
                            if char.isdigit() or (char == '.' and '.' not in val):
                                if len(val) < 5: self.input_values[0] += char
                        else:
                            if char.isdigit():
                                if len(val) < 2: self.input_values[1] += char
            return

        # --- RESTORED SCROLL LOGIC ---
        if e.type == pygame.MOUSEBUTTONDOWN:
            # Don't steal scroll events when missed wins sub-popup is open
            if self.missed_wins_popup and self.missed_wins_popup.active:
                return
            left_col_w = self.rect.width * 62 // 100 - 30
            right_col_w = self.rect.width - left_col_w - 50
            right_x = self.rect.x + left_col_w + 40
            if right_x <= e.pos[0] <= right_x + right_col_w:
                if e.button == 4: self.move_scroll = max(0, self.move_scroll - 40)
                elif e.button == 5: self.move_scroll += 40

    def adjust_value(self, direction):
        try:
            if self.input_focus == 0:
                val = float(self.input_values[0]) if self.input_values[0] else 0.0
                val += direction * 0.5
                if val < 0.1: val = 0.1
                self.input_values[0] = f"{val:.1f}"
            else:
                val = int(self.input_values[1]) if self.input_values[1] else 0
                val += direction
                if val < 0: val = 0
                self.input_values[1] = str(val)
        except ValueError: pass

    def draw_settings(self, screen, fb, fm):
        header_rect = pygame.Rect(self.rect.x, self.rect.y, self.rect.width, 80)
        labels = ["Analysis Time (sec/move)", "Engine Depth (0 = Auto)"]
        desc = ["Higher time = better accuracy, especially for 'Brilliant' moves.", "Fixed depth. Leave 0 for time-based analysis."]
        
        self.input_rects = []
        y = self.rect.y + 120
        
        for i in range(2):
            screen.blit(fb.render(labels[i], True, (60, 60, 60)), (self.rect.centerx - 150, y))
            box_rect = pygame.Rect(self.rect.centerx - 150, y + 30, 300, 45)
            self.input_rects.append(box_rect)
            
            is_focused = (self.input_focus == i)
            border_col = THEME["accent"] if is_focused else (200, 200, 200)
            pygame.draw.rect(screen, (255, 255, 255), box_rect, border_radius=8)
            pygame.draw.rect(screen, border_col, box_rect, 2, border_radius=8)
            
            txt_surf = fm.render(self.input_values[i], True, (0, 0, 0))
            text_y = box_rect.centery - txt_surf.get_height() // 2
            screen.blit(txt_surf, (box_rect.x + 15, text_y)) 
            
            if is_focused:
                self.cursor_timer += 1
                if (self.cursor_timer // 30) % 2 == 0:
                    cx = box_rect.x + 15 + txt_surf.get_width() + 2
                    cy = box_rect.y + 10
                    pygame.draw.line(screen, (0,0,0), (cx, cy), (cx, cy+25), 2)
            
            screen.blit(self.parent.font_s.render(desc[i], True, (120, 120, 120)), (self.rect.centerx - 150, y + 80))
            y += 130

        self.btn_start = pygame.Rect(self.rect.centerx - 100, self.rect.bottom - 120, 200, 50)
        col = THEME["accent"] if self.btn_start.collidepoint(pygame.mouse.get_pos()) else (100, 180, 100)
        if self.btn_start.collidepoint(pygame.mouse.get_pos()):
             col = (min(255, col[0]+20), min(255, col[1]+20), min(255, col[2]+20))
        pygame.draw.rect(screen, col, self.btn_start, border_radius=10)
        btn_txt = fb.render("Start Analysis", True, (255, 255, 255))
        screen.blit(btn_txt, (self.btn_start.centerx - btn_txt.get_width()//2, self.btn_start.centery - btn_txt.get_height()//2))

    def draw(self, screen, fb, fm):
        self.draw_content(screen, fb, fm)

    def draw_content(self, screen, fb, fm):
        ov = pygame.Surface(screen.get_size(), pygame.SRCALPHA); ov.fill((0,0,0,160)); screen.blit(ov, (0,0))
        shadow = self.rect.copy(); shadow.y += 8
        pygame.draw.rect(screen, (0,0,0,50), shadow, border_radius=20)
        pygame.draw.rect(screen, (252,252,254), self.rect, border_radius=16)
        pygame.draw.rect(screen, (210,210,215), self.rect, 2, border_radius=16)
        pygame.draw.rect(screen, (255,255,255), (self.rect.x, self.rect.y, self.rect.width, 60), border_top_left_radius=16, border_top_right_radius=16)
        screen.blit(fb.render("Game Review", True, (40,40,40)), (self.rect.x+20, self.rect.y+15))
        self.close_btn = pygame.Rect(self.rect.right-40, self.rect.y+15, 30,30)
        pygame.draw.rect(screen, (220,100,100), self.close_btn, border_radius=5)
        screen.blit(fb.render("X", True, (255,255,255)), (self.close_btn.x+8, self.close_btn.y+2))
        
        if self.settings_mode: self.draw_settings(screen, fb, fm); return

        left_x = self.rect.x + 20
        left_col_w = self.rect.width * 62 // 100 - 30
        right_col_w = self.rect.width - left_col_w - 50
        right_x = self.rect.x + left_col_w + 40
        curr_y = self.rect.y + 75

        # --- SHOW LIVE ANALYSIS PROGRESS ABOVE GRAPH ---
        if self.status != "Complete":
            status_color = (40, 140, 200) if "Analyzing" in self.status else (100, 100, 100)
            screen.blit(fb.render(self.status, True, status_color), (left_x, curr_y))
            curr_y += 30

        # --- NATIVE LUCASCHESS-STYLE AREA GRAPH ---
        graph_rect = pygame.Rect(left_x, curr_y, left_col_w, 200)
        
        # --- FIX: Save the rect to 'self' so the hover logic can find it! ---
        self.graph_rect = graph_rect 
        
        pygame.draw.rect(screen, (250, 250, 252), graph_rect, border_radius=8)
        pygame.draw.rect(screen, THEME["border"], graph_rect, 2, border_radius=8)
        
        baseline_y = graph_rect.centery
        
        # --- FIX: Clean, Static Graph Scaling ---
        # 1. Start with an explicit 0.0 Centipawn anchor for the starting position (Ply 0)
        evals = [0] 
        
        for step in self.history:
            if isinstance(step, dict) and "review" in step and "eval_cp" in step["review"]:
                evals.append(step["review"]["eval_cp"])
            elif self.status != "Complete":
                # Stop drawing the line here during live analysis!
                break 
            else:
                evals.append(0) # Fallback
                
        # Lock the X-axis scale to the total expected moves in the game!
        total_plies = max(10, len(self.history))
        
        if len(evals) > 1:
            pts = []
            for i, val in enumerate(evals):
                clamped_val = max(-1000, min(1000, val))
                
                # Fixed X scaling so it grows smoothly like a loading bar
                x = graph_rect.left + int(i * (graph_rect.width / total_plies))
                y = baseline_y - int((clamped_val / 1000.0) * (graph_rect.height / 2 - 10))
                pts.append((x, y))
                
            # Connect the polygon to the baseline so we can fill the area underneath it
            poly_points = [(graph_rect.left, baseline_y)] + pts + [(pts[-1][0], baseline_y)]
            surf_pts = [(px - graph_rect.x, py - graph_rect.y) for px, py in poly_points]
            
            # 1. White Advantage (Green Fill)
            white_surf = pygame.Surface(graph_rect.size, pygame.SRCALPHA)
            pygame.draw.polygon(white_surf, (100, 190, 100, 140), surf_pts)
            white_surf.set_clip(pygame.Rect(0, 0, graph_rect.width, graph_rect.height // 2))
            screen.blit(white_surf, graph_rect.topleft)
            
            # 2. Black Advantage (Red Fill)
            black_surf = pygame.Surface(graph_rect.size, pygame.SRCALPHA)
            pygame.draw.polygon(black_surf, (200, 80, 80, 140), surf_pts)
            black_surf.set_clip(pygame.Rect(0, graph_rect.height // 2, graph_rect.width, graph_rect.height // 2))
            screen.blit(black_surf, graph_rect.topleft)
            
            # 3. Draw the Zero-Line (Baseline)
            pygame.draw.line(screen, (180, 180, 180), (graph_rect.left, baseline_y), (graph_rect.right, baseline_y), 1)
            
            # 4. Draw the main continuous trend line on top
            pygame.draw.lines(screen, (40, 40, 40), False, pts, 2)

            # 4b. Graph cursor — vertical line at clicked position
            if hasattr(self, 'graph_cursor_x') and self.graph_cursor_x:
                cx_line = self.graph_cursor_x
                if graph_rect.left <= cx_line <= graph_rect.right:
                    pygame.draw.line(screen, (80, 80, 220), (cx_line, graph_rect.top + 4),
                                     (cx_line, graph_rect.bottom - 4), 2)
                    # Dot at intersection with eval line
                    frac = (cx_line - graph_rect.left) / max(1, graph_rect.width)
                    dot_idx = int(round(frac * total_plies))
                    if 0 < dot_idx < len(pts):
                        pygame.draw.circle(screen, (80, 80, 220), pts[dot_idx], 5)
            
            # --- FIX: Draw Colored Dots (Shifted by +1 for the Ply 0 Anchor) ---
            for i, step in enumerate(self.history):
                if not isinstance(step, dict): continue
                if (i + 1) < len(pts):
                    px, py = pts[i + 1]
                    cls = step.get("review", {}).get("class", "")
                    
                    if cls == "brilliant":
                        pygame.draw.circle(screen, (0, 204, 204), (px, py), 7) 
                        pygame.draw.circle(screen, (255, 255, 255), (px, py), 7, 2) 
                    elif cls == "great":
                        pygame.draw.circle(screen, (92, 133, 214), (px, py), 7) 
                        pygame.draw.circle(screen, (255, 255, 255), (px, py), 7, 2)
                    elif cls == "blunder":
                        pygame.draw.circle(screen, (255, 51, 51), (px, py), 7) 
                        pygame.draw.circle(screen, (255, 255, 255), (px, py), 7, 2)
            # -------------------------------------------------------
            
        elif self.status != "Complete":
            screen.blit(fm.render("Waiting for engine...", True, (180,180,180)), (graph_rect.centerx - 60, graph_rect.centery - 10))
        
        curr_y += 210

        # --- Move Time Bar Graph (single, unified with rich hover tooltip) ---
        time_data = [h.get("move_time", 0) for h in self.history if isinstance(h, dict)]
        history_list = [h for h in self.history if isinstance(h, dict)]
        if any(t > 0 for t in time_data):
            time_rect = pygame.Rect(left_x, curr_y, left_col_w, 72)
            pygame.draw.rect(screen, (248, 248, 252), time_rect, border_radius=6)
            pygame.draw.rect(screen, (210, 210, 220), time_rect, 1, border_radius=6)
            screen.blit(self.parent.font_s.render("Move Times", True, (100, 100, 120)),
                        (time_rect.x + 6, time_rect.y + 4))
            max_t = max(t for t in time_data if t > 0) or 1.0
            bar_area = pygame.Rect(time_rect.x + 4, time_rect.y + 20, time_rect.width - 8, 46)
            n = len(time_data)
            hovered_tip = None
            if n > 0:
                bw = max(2, bar_area.width // n)
                for i, t in enumerate(time_data):
                    bh = int((t / max_t) * bar_area.height)
                    col_bar = (80, 130, 220) if i % 2 == 0 else (220, 140, 60)
                    bx2 = bar_area.x + i * bw
                    if bh > 0:
                        pygame.draw.rect(screen, col_bar,
                                         (bx2, bar_area.bottom - bh, max(1, bw - 1), bh),
                                         border_radius=2)
                    hover_r = pygame.Rect(bx2, bar_area.y, max(1, bw), bar_area.height)
                    if hover_r.collidepoint(pygame.mouse.get_pos()):
                        step = history_list[i] if i < len(history_list) else {}
                        san = step.get("san", "?")
                        move_num = (i // 2) + 1
                        side_dot = "." if i % 2 == 0 else "…"
                        hovered_tip = (f"Move {move_num}{side_dot} {san}  |  {t:.2f}s", bx2)
            # Draw tooltip on top of all bars so it is never obscured
            if hovered_tip:
                tip_text, tip_bx = hovered_tip
                tip_surf = self.parent.font_s.render(tip_text, True, (20, 20, 20))
                tip_bg = pygame.Rect(tip_bx, time_rect.y + 2,
                                     tip_surf.get_width() + 14, tip_surf.get_height() + 8)
                if tip_bg.right > self.rect.right - 4:
                    tip_bg.x = self.rect.right - tip_bg.width - 4
                pygame.draw.rect(screen, (255, 255, 255), tip_bg, border_radius=5)
                pygame.draw.rect(screen, (100, 120, 200), tip_bg, 1, border_radius=5)
                screen.blit(tip_surf, (tip_bg.x + 7, tip_bg.y + 4))
            curr_y += 82

        # ── Gather player stats (LucasChess detailed or fallback) ─────────────
        w_name = self.headers.get("White", "White")
        b_name = self.headers.get("Black", "Black")

        if getattr(self, 'detailed_review', None):
            pw = self.detailed_review["performance"][0]
            pb = self.detailed_review["performance"][1]
            w_acc, w_cpl = pw["overall_accuracy"], int(pw["acl"])
            b_acc, b_cpl = pb["overall_accuracy"], int(pb["acl"])
            w_elo, b_elo = pw["performance_elo"], pb["performance_elo"]
            w_op, w_mg, w_eg = pw["opening_elo"], pw["middlegame_elo"], pw["endgame_elo"]
            b_op, b_mg, b_eg = pb["opening_elo"], pb["middlegame_elo"], pb["endgame_elo"]
        else:
            w_acc = self.stats.get('white', {}).get('acc', 0)
            b_acc = self.stats.get('black', {}).get('acc', 0)
            w_cpl = self.stats.get('white', {}).get('acpl', 0)
            if w_cpl == 0 and w_acc > 0: w_cpl = int((100 - w_acc) * 3.5)
            b_cpl = self.stats.get('black', {}).get('acpl', 0)
            if b_cpl == 0 and b_acc > 0: b_cpl = int((100 - b_acc) * 3.5)
            w_elo = self.ratings.get('white', '?')
            b_elo = self.ratings.get('black', '?')
            w_op = w_mg = w_eg = b_op = b_mg = b_eg = None

        def safe_elo(val): return str(val) if val else "-"

        # Compute per-phase accuracy from history
        phase_acc = {"opening": [[], []], "middlegame": [[], []], "endgame": [[], []]}

        # Use detect_game_phases for consistent phase ranges (same logic as the Elo bars)
        analyzer_inst = getattr(self.parent, 'analyzer', None) or getattr(self, 'worker', None)
        detected_phases = None
        if analyzer_inst and hasattr(analyzer_inst, 'detect_game_phases'):
            detected_phases = analyzer_inst.detect_game_phases(self.history)

        for idx, step in enumerate(self.history):
            if not isinstance(step, dict): continue
            rev = step.get("review", {})
            cls = rev.get("class", "")
            ply = step.get("ply", 1)
            side = 0 if ply % 2 != 0 else 1

            # 1. Check if phase was already saved in the review dictionary
            phase_key = rev.get("phase")

            # 2. Use detect_game_phases index ranges so bars match the Elo computation exactly
            if not phase_key and detected_phases is not None:
                for pk, rng in detected_phases.items():
                    if rng is not None and rng[0] <= idx < rng[1]:
                        phase_key = pk
                        break

            if not phase_key or phase_key not in phase_acc:
                phase_key = "middlegame"

            score = {"brilliant": 100, "great": 95, "best": 90, "excellent": 85,
                     "good": 75, "book": 80, "inaccuracy": 50, "mistake": 25,
                     "blunder": 0, "miss": 10}.get(cls, 70)
            phase_acc[phase_key][side].append(score)

        def mean_acc(lst): return round(sum(lst) / len(lst), 1) if lst else None
        phase_key_map = {"Opening": "opening", "Middlegame": "middlegame", "Endgame": "endgame"}
        phase_rows = [("Opening", w_op, b_op), ("Middlegame", w_mg, b_mg), ("Endgame", w_eg, b_eg)]

        # ── NEW LAYOUT: [Stats Box] + [Move Timing Box] ────────
        GAP = 12
        stats_panel_w = max(210, left_col_w // 3)
        timing_panel_w = left_col_w - stats_panel_w - GAP
        strip_y = curr_y

        stats_x = left_x
        timing_x = stats_x + stats_panel_w + GAP
        history_list = [h for h in self.history if isinstance(h, dict)]

        # --- Panel 1: White Stats Box ---
        w_box_h = 105
        pygame.draw.rect(screen, (255, 255, 255), pygame.Rect(stats_x, strip_y, stats_panel_w, w_box_h), border_radius=8)
        pygame.draw.rect(screen, (190, 220, 190), pygame.Rect(stats_x, strip_y, stats_panel_w, w_box_h), 1, border_radius=8)
        screen.blit(fb.render(f"W: {w_acc:.1f}%", True, (0, 0, 0)), (stats_x + 10, strip_y + 8))
        screen.blit(fm.render(f"ACPL: {w_cpl}", True, (100, 100, 100)), (stats_x + 10, strip_y + 32))
        screen.blit(fb.render(f"Est. Elo: {w_elo or '?'}", True, (40, 140, 40)), (stats_x + 10, strip_y + 56))
        screen.blit(self.parent.font_s.render(w_name, True, (50, 50, 60)), (stats_x + 10, strip_y + 80))

        # --- Panel 2: White Move Times Box ---
        w_time_rect = pygame.Rect(timing_x, strip_y, timing_panel_w, w_box_h)
        pygame.draw.rect(screen, (248, 252, 248), w_time_rect, border_radius=8)
        pygame.draw.rect(screen, (200, 220, 200), w_time_rect, 1, border_radius=8)
        screen.blit(self.parent.font_s.render("White Move Times", True, (60, 100, 60)), (w_time_rect.x + 8, w_time_rect.y + 4))

        w_moves = [(i, h) for i, h in enumerate(history_list) if i % 2 == 0]
        w_times = [h.get("move_time", 0) for _, h in w_moves]
        hovered_tip = None

        if w_times and max(w_times) > 0:
            max_t = max(w_times)
            bar_area = pygame.Rect(w_time_rect.x + 8, w_time_rect.y + 24, w_time_rect.width - 16, w_box_h - 32)
            n = len(w_times)
            bw = max(2, bar_area.width // n)
            for idx, t in enumerate(w_times):
                bh = int((t / max_t) * bar_area.height)
                bx = bar_area.x + idx * bw
                if bh > 0:
                    pygame.draw.rect(screen, (100, 180, 100), (bx, bar_area.bottom - bh, max(1, bw - 1), bh), border_radius=2)
                hover_r = pygame.Rect(bx, bar_area.y, max(1, bw), bar_area.height)
                if hover_r.collidepoint(pygame.mouse.get_pos()):
                    orig_idx, step = w_moves[idx]
                    san = step.get("san", "?")
                    move_num = (orig_idx // 2) + 1
                    hovered_tip = (f"{move_num}. {san}   {t:.1f}s", bx, bar_area.y)
        else:
            dash = fb.render("-", True, (180, 180, 180))
            screen.blit(dash, (w_time_rect.centerx - dash.get_width()//2, w_time_rect.centery - dash.get_height()//2 + 10))

        # --- Panel 3: Black Stats Box (Lighter Black) ---
        b_box_y = strip_y + w_box_h + GAP
        b_box_h = 105
        pygame.draw.rect(screen, (55, 55, 60), pygame.Rect(stats_x, b_box_y, stats_panel_w, b_box_h), border_radius=8)
        pygame.draw.rect(screen, (90, 90, 100), pygame.Rect(stats_x, b_box_y, stats_panel_w, b_box_h), 1, border_radius=8)
        screen.blit(fb.render(f"B: {b_acc:.1f}%", True, (240, 240, 245)), (stats_x + 10, b_box_y + 8))
        screen.blit(fm.render(f"ACPL: {b_cpl}", True, (200, 200, 210)), (stats_x + 10, b_box_y + 32))
        screen.blit(fb.render(f"Est. Elo: {b_elo or '?'}", True, (120, 210, 120)), (stats_x + 10, b_box_y + 56))
        screen.blit(self.parent.font_s.render(b_name, True, (180, 180, 190)), (stats_x + 10, b_box_y + 80))

        # --- Panel 4: Black Move Times Box ---
        b_time_rect = pygame.Rect(timing_x, b_box_y, timing_panel_w, b_box_h)
        pygame.draw.rect(screen, (252, 248, 248), b_time_rect, border_radius=8)
        pygame.draw.rect(screen, (220, 200, 200), b_time_rect, 1, border_radius=8)
        screen.blit(self.parent.font_s.render("Black Move Times", True, (120, 60, 60)), (b_time_rect.x + 8, b_time_rect.y + 4))

        b_moves = [(i, h) for i, h in enumerate(history_list) if i % 2 != 0]
        b_times = [h.get("move_time", 0) for _, h in b_moves]

        if b_times and max(b_times) > 0:
            max_t = max(b_times)
            bar_area = pygame.Rect(b_time_rect.x + 8, b_time_rect.y + 24, b_time_rect.width - 16, b_box_h - 32)
            n = len(b_times)
            bw = max(2, bar_area.width // n)
            for idx, t in enumerate(b_times):
                bh = int((t / max_t) * bar_area.height)
                bx = bar_area.x + idx * bw
                if bh > 0:
                    pygame.draw.rect(screen, (200, 100, 100), (bx, bar_area.bottom - bh, max(1, bw - 1), bh), border_radius=2)
                hover_r = pygame.Rect(bx, bar_area.y, max(1, bw), bar_area.height)
                if hover_r.collidepoint(pygame.mouse.get_pos()):
                    orig_idx, step = b_moves[idx]
                    san = step.get("san", "?")
                    move_num = (orig_idx // 2) + 1
                    hovered_tip = (f"{move_num}... {san}   {t:.1f}s", bx, bar_area.y)
        else:
            dash = fb.render("-", True, (180, 180, 180))
            screen.blit(dash, (b_time_rect.centerx - dash.get_width()//2, b_time_rect.centery - dash.get_height()//2 + 10))

        # Draw hovered tooltips overlapping everything
        if hovered_tip:
            tip_text, tip_x, tip_y = hovered_tip
            tip_surf = self.parent.font_s.render(tip_text, True, (20, 20, 20))
            tip_bg = pygame.Rect(tip_x, tip_y - 28, tip_surf.get_width() + 14, tip_surf.get_height() + 8)
            if tip_bg.right > left_x + left_col_w: tip_bg.right = left_x + left_col_w
            if tip_bg.y < strip_y: tip_bg.y = strip_y
            pygame.draw.rect(screen, (255, 255, 255), tip_bg, border_radius=5)
            pygame.draw.rect(screen, (100, 120, 200), tip_bg, 1, border_radius=5)
            screen.blit(tip_surf, (tip_bg.x + 7, tip_bg.y + 4))

        # ── Split Layout: Phases (Left) vs Move Classification (Right) ────────
        split_y = b_box_y + b_box_h + 15
        
        col_left_w = (left_col_w // 2) - 10
        col_right_w = (left_col_w // 2) - 10
        col_right_x = left_x + col_left_w + 20
        
        # --- Phases Column (Vertical Stack) ---
        current_ph_y = split_y
        bg_bar_w = col_left_w - 75 # Dynamic scaling width
        
        for label, w_elo_v, b_elo_v in phase_rows:
            pk = phase_key_map[label]
            w_pa = mean_acc(phase_acc[pk][0])
            b_pa = mean_acc(phase_acc[pk][1])
            
            # Box background
            pygame.draw.rect(screen, (248, 248, 250), (left_x, current_ph_y, col_left_w, 85), border_radius=6)
            pygame.draw.rect(screen, (220, 220, 225), (left_x, current_ph_y, col_left_w, 85), 1, border_radius=6)
            screen.blit(fm.render(label, True, (60, 60, 70)), (left_x + 10, current_ph_y + 8))
            
            # White Elo & Bar
            screen.blit(self.parent.font_s.render(f"W: {safe_elo(w_elo_v)}", True, (50, 100, 50)), (left_x + 10, current_ph_y + 35))
            pygame.draw.rect(screen, (220, 220, 220), (left_x + 65, current_ph_y + 39, bg_bar_w, 8), border_radius=4)
            if w_pa is not None:
                c_bar = (50, 180, 50) if w_pa >= 80 else (220, 170, 40) if w_pa >= 55 else (200, 60, 60)
                bw2 = int((w_pa / 100.0) * bg_bar_w) # Correct 0-100 logic
                if bw2 > 0: pygame.draw.rect(screen, c_bar, (left_x + 65, current_ph_y + 39, bw2, 8), border_radius=4)
                
            # Black Elo & Bar
            screen.blit(self.parent.font_s.render(f"B: {safe_elo(b_elo_v)}", True, (120, 60, 60)), (left_x + 10, current_ph_y + 60))
            pygame.draw.rect(screen, (220, 220, 220), (left_x + 65, current_ph_y + 64, bg_bar_w, 8), border_radius=4)
            if b_pa is not None:
                c_bar = (50, 180, 50) if b_pa >= 80 else (220, 170, 40) if b_pa >= 55 else (200, 60, 60)
                bw2 = int((b_pa / 100.0) * bg_bar_w)
                if bw2 > 0: pygame.draw.rect(screen, c_bar, (left_x + 65, current_ph_y + 64, bw2, 8), border_radius=4)

            current_ph_y += 95
            
        phases_bottom_y = current_ph_y

        # --- Move Classification Column (Right Side) ---
        class_y = split_y
        cats = [
            ("Book", "book"), ("Brilliant", "brilliant"), ("Great", "great"),
            ("Best", "best"), ("Excellent", "excellent"), ("Good", "good"),
            ("Inaccuracy", "inaccuracy"), ("Mistake", "mistake"),
            ("Blunder", "blunder"), ("Miss", "miss")
        ]
        safe_w_summary = {k: 0 for _, k in cats}
        safe_b_summary = {k: 0 for _, k in cats}
        for step in self.history:
            if isinstance(step, dict) and "review" in step and "class" in step["review"]:
                c = step["review"]["class"]
                ply = step.get("ply", 1)
                if ply % 2 != 0: safe_w_summary[c] = safe_w_summary.get(c, 0) + 1
                else: safe_b_summary[c] = safe_b_summary.get(c, 0) + 1

        # Header row
        screen.blit(fb.render("Move Classification", True, (55, 55, 65)), (col_right_x, class_y))
        screen.blit(fm.render("W", True, (80, 80, 80)), (col_right_x + col_right_w - 60, class_y + 2))
        screen.blit(fm.render("B", True, (80, 80, 80)), (col_right_x + col_right_w - 25, class_y + 2))
        pygame.draw.line(screen, (220, 220, 220), (col_right_x, class_y + 26), (col_right_x + col_right_w, class_y + 26))
        class_y += 35

        for name, key in cats:
            ic_key = "eval_book" if key == "book" and "eval_book" in self.assets.icons else key
            ic = self.assets.icons.get(ic_key)
            
            pygame.draw.rect(screen, (250, 250, 253), (col_right_x, class_y - 4, col_right_w, 26), border_radius=4)
            if ic: screen.blit(pygame.transform.smoothscale(ic, (20, 20)), (col_right_x + 4, class_y - 1))
            
            screen.blit(fm.render(name, True, (60, 60, 60)), (col_right_x + 32, class_y))
            
            wc = safe_w_summary.get(key, 0)
            bc = safe_b_summary.get(key, 0)
            
            screen.blit(fb.render(str(wc), True, (40, 100, 40) if wc > 0 else (150, 150, 150)), (col_right_x + col_right_w - 60, class_y))
            screen.blit(fb.render(str(bc), True, (180, 60, 60) if bc > 0 else (150, 150, 150)), (col_right_x + col_right_w - 25, class_y))
            class_y += 28

        final_y = max(phases_bottom_y, class_y) + 5

        # ── Missed Win Detection Button ───────────────────────────────────────
        missed_wins = []
        for i, step in enumerate(self.history):
            if not isinstance(step, dict): continue
            rev = step.get("review", {})
            prev_cp = None
            if i > 0 and isinstance(self.history[i - 1], dict):
                prev_cp = self.history[i - 1].get("review", {}).get("eval_cp")
            curr_cp = rev.get("eval_cp")
            if prev_cp is not None and curr_cp is not None:
                ply = step.get("ply", i + 1)
                is_white_move = (ply % 2 != 0)
                if is_white_move and prev_cp >= 500 and curr_cp < 150:
                    missed_wins.append((i, step))
                elif not is_white_move and prev_cp <= -500 and curr_cp > -150:
                    missed_wins.append((i, step))

        if missed_wins:
            self.btn_missed_wins = pygame.Rect(left_x, final_y, left_col_w // 2, 36)
            mw_col = (210, 80, 50) if self.btn_missed_wins.collidepoint(pygame.mouse.get_pos()) else (180, 60, 40)
            pygame.draw.rect(screen, mw_col, self.btn_missed_wins, border_radius=8)
            mw_txt = fb.render(f"Missed Wins  ({len(missed_wins)})", True, (255, 255, 255))
            screen.blit(mw_txt, (self.btn_missed_wins.centerx - mw_txt.get_width() // 2,
                                  self.btn_missed_wins.centery - mw_txt.get_height() // 2))
        else:
            self.btn_missed_wins = None

        self._missed_wins_cache = missed_wins

        if self.missed_wins_popup and self.missed_wins_popup.active:
            self.missed_wins_popup.draw(screen, fb, fm)

        # --- RIGHT COLUMN: Full Move List ---
        curr_y = self.rect.y + 70
        list_h = self.h - 90

        pygame.draw.rect(screen, (255, 255, 255),
                         (right_x, curr_y, right_col_w, list_h), border_radius=8)
        clip = pygame.Rect(right_x, curr_y, right_col_w, list_h)
        screen.set_clip(clip)
        
        my = curr_y + 10 - self.move_scroll
        item_h = 140 
        
        total_list_h = len(self.history) * item_h
        max_scroll = max(0, total_list_h - list_h + 50)
        self.move_scroll = max(0, min(self.move_scroll, max_scroll))
        
        if getattr(self.parent, 'active_bot', None):
            bot_name = self.parent.active_bot.get("name")
            bot_av = self.assets.get_avatar(bot_name)
        else:
            bot_name = getattr(self.parent, 'current_engine_info', {}).get("name", "Stockfish 18")
            if getattr(self.parent, 'stockfish_icon', None):
                bot_av = self.parent.stockfish_icon
            else:
                bot_av = self.assets.get_avatar(bot_name)
        
        for i, move in enumerate(self.history):
            if not isinstance(move, dict): continue
            if my > clip.bottom: break
            if my + item_h > clip.y:
                bg = (248,248,252) if i%2==0 else (255,255,255)
                if i == self.selected_move_idx: bg = (230, 230, 250)
                
                pygame.draw.rect(screen, bg, (right_x, my, right_col_w, item_h-2))
                
                txt = f"{i//2+1}. " if i%2==0 else "... "
                txt += move["san"]
                screen.blit(fb.render(txt, True, (0,0,0)), (right_x+10, my+10))
                
                if "review" in move:
                    ev = move["review"].get("eval_str", "")
                    ic_key = move["review"].get("class")
                    if ic_key == "book": ic_key = "eval_book"
                    reason = move["review"].get("bot_reason", "")
                    
                    if ev:
                        col = (20,160,20) if "+" in ev else (200,50,50)
                        tx_surf = fm.render(ev, True, col)
                        screen.blit(tx_surf, (right_x + right_col_w - 60, my+10))
                    if ic_key and ic_key in self.assets.icons:
                        screen.blit(pygame.transform.smoothscale(self.assets.icons[ic_key], (24,24)), (right_x + right_col_w - 100, my+7))
                    
                    if reason:
                        if bot_av:
                            scaled_av = self.assets.scale_keep_aspect(bot_av, (30, 30))
                            ox = (30 - scaled_av.get_width()) // 2
                            oy = (30 - scaled_av.get_height()) // 2
                            screen.blit(scaled_av, (right_x + 10 + ox, my + 40 + oy))
                            screen.blit(fm.render(f"{bot_name}:", True, (100,100,150)), (right_x + 45, my + 40))
                            self.parent.renderer.draw_multiline_text(reason, fm, (60,60,60), right_x+45, my+60, right_col_w-60)
                        else:
                            self.parent.renderer.draw_multiline_text(reason, fm, (80,80,80), right_x+15, my+40, right_col_w-30)
                else:
                     screen.blit(fm.render("Analyzing...", True, (150,150,150)), (right_x+15, my+35))
            
            my += item_h
        screen.set_clip(None)

        # --- NEW: Interactive Graph Hover Tooltip ---
        if hasattr(self, 'graph_rect') and hasattr(self, 'history'):
            mx, my = pygame.mouse.get_pos()
            if self.graph_rect.collidepoint(mx, my):
                total_moves = len(self.history)
                if total_moves > 0:
                    relative_x = mx - self.graph_rect.x
                    
                    # Calculate safe total_plies for grid snapping
                    safe_total_plies = max(10, len(self.history))
                    move_idx = int(round((relative_x / self.graph_rect.width) * safe_total_plies)) - 1
                    
                    if 0 <= move_idx < len(self.history):
                        step = self.history[move_idx]
                        
                        # FOOLPROOF INDENTATION: Everything must be inside this 'if' block!
                        # This prevents the app from crashing if a move hasn't been analyzed yet.
                        if isinstance(step, dict) and "review" in step and "eval_str" in step["review"]:
                            move_num = (move_idx // 2) + 1
                            san = step.get("san", "")
                            eval_str = step["review"].get("eval_str", "")
                            
                            cls = step["review"].get("class", "")
                            ic_key = "eval_book" if cls == "book" else cls
                            icon = self.assets.icons.get(ic_key)
                            
                            tt_text = f" Move {move_num} ({san}) | Eval: {eval_str} "
                            tt_surf = fm.render(tt_text, True, (0, 0, 0))
                            
                            box_w = tt_surf.get_width() + 10
                            if icon: box_w += 26
                            
                            tt_rect = pygame.Rect(mx + 15, my + 15, box_w, tt_surf.get_height() + 10)
                            
                            if tt_rect.right > screen.get_width(): 
                                tt_rect.x -= tt_rect.width + 30
                            
                            pygame.draw.rect(screen, (255, 255, 255), tt_rect, border_radius=6)
                            pygame.draw.rect(screen, (0, 150, 255), tt_rect, 2, border_radius=6) 
                            
                            content_x = tt_rect.x + 5
                            content_y = tt_rect.y + 5
                            
                            if icon:
                                scaled_ic = pygame.transform.smoothscale(icon, (20, 20))
                                screen.blit(scaled_ic, (content_x, tt_rect.centery - 10))
                                content_x += 26
                                
                            screen.blit(tt_surf, (content_x, content_y))
                        
class PGNSavePopup(BasePopup):
    def __init__(self, parent):
        # 3 options: Save, Save As, Discard. We need a taller box.
        super().__init__(parent, w=400, h=320)

    def draw(self, screen, fb, fm):
        self.draw_bg(screen, "Save Game", fb)
        r = self.rect
        x, y = r.x, r.y
        
        # Check if we are currently editing an existing file
        has_path = bool(self.parent.current_pgn_path)
        
        # Button metrics
        bw, bh = 220, 45
        bx = x + (r.width - bw) // 2
        cy = y + 70
        
        # Assign hitboxes
        self.parent.btn_rects["popup_save"] = pygame.Rect(bx, cy, bw, bh)
        self.parent.btn_rects["popup_save_as"] = pygame.Rect(bx, cy + 60, bw, bh)
        self.parent.btn_rects["popup_discard"] = pygame.Rect(bx, cy + 120, bw, bh)
        
        mpos = pygame.mouse.get_pos()
        
        # 1. SAVE BUTTON (Greyed out if no file loaded)
        r_save = self.parent.btn_rects["popup_save"]
        if not has_path:
            pygame.draw.rect(screen, (230, 230, 230), r_save, border_radius=8)
            pygame.draw.rect(screen, (200, 200, 200), r_save, 2, border_radius=8)
            txt = fm.render("Save (No File)", True, (150, 150, 150))
        else:
            col = (180, 230, 150) if r_save.collidepoint(mpos) else (150, 200, 120)
            pygame.draw.rect(screen, col, r_save, border_radius=8)
            pygame.draw.rect(screen, (130, 180, 100), r_save, 1, border_radius=8)
            txt = fm.render("Save", True, (20, 20, 20))
        screen.blit(txt, txt.get_rect(center=r_save.center))
        
        # 2. SAVE AS BUTTON (Always available)
        r_save_as = self.parent.btn_rects["popup_save_as"]
        col = (200, 220, 255) if r_save_as.collidepoint(mpos) else (180, 200, 240)
        pygame.draw.rect(screen, col, r_save_as, border_radius=8)
        pygame.draw.rect(screen, (150, 170, 210), r_save_as, 1, border_radius=8)
        txt = fm.render("Save As...", True, (20, 20, 20))
        screen.blit(txt, txt.get_rect(center=r_save_as.center))
        
        # 3. DISCARD BUTTON (Always available)
        r_discard = self.parent.btn_rects["popup_discard"]
        col = (255, 180, 180) if r_discard.collidepoint(mpos) else (240, 150, 150)
        pygame.draw.rect(screen, col, r_discard, border_radius=8)
        pygame.draw.rect(screen, (210, 120, 120), r_discard, 1, border_radius=8)
        txt = fm.render("Discard Game", True, (20, 20, 20))
        screen.blit(txt, txt.get_rect(center=r_discard.center))

    def handle_click(self, pos):
        if self.close_btn and self.close_btn.collidepoint(pos):
            self.active = False
            return
            
        has_path = bool(self.parent.current_pgn_path)
        
        # Only allow 'Save' to be clicked if a path exists
        if has_path and self.parent.btn_rects.get("popup_save", pygame.Rect(0,0,0,0)).collidepoint(pos):
            self._save_to_path(self.parent.current_pgn_path)
            self.parent.unsaved_analysis = False
            self.active = False
            self.parent.status_msg = "Game Saved successfully!"
            self.parent.sound_manager.play("game_start")
            
        elif self.parent.btn_rects.get("popup_save_as", pygame.Rect(0,0,0,0)).collidepoint(pos):
            import tkinter as tk
            from tkinter import filedialog
            
            # Hide the popup momentarily so the OS file dialog renders clearly
            if self.parent.root: self.parent.root.update()
            path = filedialog.asksaveasfilename(defaultextension=".pgn", filetypes=[("PGN Files", "*.pgn")])
            
            if path:
                self._save_to_path(path)
                self.parent.current_pgn_path = path # Update the active path
                self.parent.unsaved_analysis = False
                self.parent.status_msg = "Game Saved successfully!"
                self.parent.sound_manager.play("game_start")
            self.active = False
            
        elif self.parent.btn_rects.get("popup_discard", pygame.Rect(0,0,0,0)).collidepoint(pos):
            self.parent.unsaved_analysis = False
            self.parent.handle_ui("reset")
            self.active = False
            self.parent.sound_manager.play("click")
            
    def _save_to_path(self, filename):
        try:
            headers = {"White": "White", "Black": "Black"}
            if self.parent.mode_idx == 1:
                headers["White"] = "Player" if self.parent.playing_white else self.parent.active_bot["name"]
                headers["Black"] = self.parent.active_bot["name"] if self.parent.playing_white else "Player"
            
            # --- FIX: Pass the annotated history! ---
            # If reviewed, writes the evaluations and PNG tags. If not, just writes moves!
            pgn_str = self.parent.logic.export_pgn(
                history=self.parent.history, 
                white_name=headers["White"], 
                black_name=headers["Black"], 
                headers=headers
            )
            # ----------------------------------------
            
            with open(filename, "w", encoding="utf-8") as f: f.write(pgn_str)
            
            self.parent.unsaved_analysis = False
            self.parent.history = []
            self.execute_pending()
        except Exception as e: print(e)
        self.active = False
            
    def _generate_annotated_pgn(self):
        """Builds a strict, universally readable PGN containing all evaluations and classes."""
        game = chess.pgn.Game()
        
        # 1. Safely copy headers
        for k, v in self.parent.pgn_headers.items():
            game.headers[k] = str(v)
            
        # 2. Ensure critical headers exist
        if "Event" not in game.headers: game.headers["Event"] = "Casual Game"
        if "Site" not in game.headers: game.headers["Site"] = "Chess Studio Pro"
        
        bot_name = self.parent.active_bot.get("name", "Bot") if self.parent.active_bot else "Black"
        if "White" not in game.headers: 
            game.headers["White"] = "Player" if self.parent.playing_white else bot_name
        if "Black" not in game.headers: 
            game.headers["Black"] = bot_name if self.parent.playing_white else "Player"
            
        import time
        if "Date" not in game.headers: game.headers["Date"] = time.strftime("%Y.%m.%d")
        
        # 3. Iterate history and write Engine Evaluations
        node = game
        for step in self.parent.history:
            if not isinstance(step, dict): continue
            move = step.get("move")
            if not move: continue
            if isinstance(move, str): move = chess.Move.from_uci(move)
            
            node = node.add_variation(move)
            
            # --- EMBED ANNOTATIONS ---
            review = step.get("review", {})
            comments = []
            
            # A. Clock Times
            if "clock" in step and step["clock"] is not None:
                s = int(step["clock"])
                h = s // 3600
                m = (s % 3600) // 60
                sec = s % 60
                comments.append(f"[%clk {h}:{m:02d}:{sec:02d}]")
            
            # B. Evaluation Scores
            if "eval_str" in review and review["eval_str"]:
                val = review["eval_str"]
                if val.startswith("M+"):
                    comments.append(f"[%eval #{val[2:]}]")
                elif val.startswith("M-"):
                    comments.append(f"[%eval #-{val[2:]}]")
                else:
                    comments.append(f"[%eval {val}]")
                    
            # C. Brilliant/Blunder Classifications (for like chess.coms & Lichess)
            if "class" in review:
                cls_name = review["class"].capitalize()
                comments.append(f"[%class {cls_name}]")
                
            # D. Bot Reason
            if "bot_reason" in review:
                comments.append(str(review["bot_reason"]))
                
            # Embed all tags into the text comment
            if comments:
                node.comment = " ".join(comments)
                
            # E. Legacy Numeric Annotation Glyphs (NAGs) like $1 (Good), $4 (Blunder)
            nag_map = {"good": 1, "mistake": 2, "brilliant": 3, "blunder": 4, "excellent": 5, "inaccuracy": 6, "great": 1}
            if "class" in review and review["class"] in nag_map:
                node.nags.add(nag_map[review["class"]])
            elif "nags" in step and step["nags"]:
                for nag in step["nags"]: node.nags.add(nag)
                
        return str(game)

class PGNSelectionPopup(BasePopup):
    def __init__(self, parent, path):
        super().__init__(parent, 750, 850) # Taller for 12 games + Pagination
        self.path = path
        self.games = []
        
        # Pagination state
        self.current_page = 0
        self.items_per_page = 12
        self.total_pages = 0
        
        # Load games
        try:
            with open(path, encoding="utf-8") as f:
                while True:
                    off = f.tell()
                    g = chess.pgn.read_game(f)
                    if not g: break
                    h = g.headers
                    self.games.append({
                        "white": h.get("White", "?"),
                        "black": h.get("Black", "?"),
                        "result": h.get("Result", "*"), 
                        "date": h.get("Date", "????.??.??"),
                        "time": h.get("TimeControl", "-"),
                        "offset": off
                    })
            self.total_pages = max(1, (len(self.games) + self.items_per_page - 1) // self.items_per_page)
        except Exception as e:
            print(f"Error reading PGN for popup: {e}")
            
        self.zones = []
        self.btn_prev = None
        self.btn_next = None

    def draw(self, screen, fb, fm):
        self.draw_bg(screen, f"Select Game ({len(self.games)} found)", fb)
        
        self.zones = []
        
        # Load main icon
        main_icon = self.parent.assets.icons.get('main_pgn_icon_small')
        if not main_icon:
            try:
                p = os.path.join('assets', 'icons', 'main.png')
                if os.path.exists(p):
                    img = pygame.image.load(p).convert_alpha()
                    img = pygame.transform.smoothscale(img, (30, 30))
                    self.parent.assets.icons['main_pgn_icon_small'] = img
                    main_icon = img
            except Exception:
                main_icon = None

        # --- DRAW CURRENT PAGE ITEMS ---
        start_idx = self.current_page * self.items_per_page
        end_idx = min(start_idx + self.items_per_page, len(self.games))
        
        y = self.rect.y + 70
        
        for i in range(start_idx, end_idx):
            g = self.games[i]
            r = pygame.Rect(self.rect.x + 20, y, self.w - 40, 52)
            
            # Hover effect
            is_hover = r.collidepoint(pygame.mouse.get_pos())
            bg_col = (245, 250, 255) if is_hover else (255, 255, 255)
            pygame.draw.rect(screen, bg_col, r, border_radius=8)
            pygame.draw.rect(screen, (220, 220, 230), r, 1, border_radius=8)
            
            text_x = r.x + 15
            if main_icon:
                icon_y = r.y + (r.height - main_icon.get_height()) // 2
                screen.blit(main_icon, (r.x + 15, icon_y))
                text_x += main_icon.get_width() + 15
            else:
                text_x = r.x + 50
            
            # Format: "1. PlayerOne vs PlayerTwo"
            match_text = f"{(i + 1):03d}. {g['white']} vs {g['black']}"
            screen.blit(fb.render(match_text, True, (40, 40, 40)), (text_x, r.y + 8))
            
            # Format Result, Date, and Time underneath
            sub_text = f"Result: {g['result']}  |  Date: {g['date'].replace('?', '')}  |  Time: {g['time']}"
            screen.blit(self.parent.font_s.render(sub_text, True, (120, 120, 120)), (text_x, r.y + 30))
            
            # Load Button
            btn = pygame.Rect(r.right - 90, r.y + 10, 80, 32)
            btn_col = (80, 180, 80) if btn.collidepoint(pygame.mouse.get_pos()) else (60, 160, 60)
            pygame.draw.rect(screen, btn_col, btn, border_radius=6)
            load_txt = fm.render("Load", True, (255, 255, 255))
            screen.blit(load_txt, (btn.centerx - load_txt.get_width()//2, btn.centery - load_txt.get_height()//2))
            
            self.zones.append((btn, g['offset']))
            y += 58 # Compact spacing for 12 games without overlap
            
        # --- DRAW PAGINATION CONTROLS ---
        bottom_y = self.rect.bottom - 55
        cx = self.rect.centerx
        
        self.btn_prev = pygame.Rect(cx - 150, bottom_y, 80, 35)
        if self.current_page > 0:
            pygame.draw.rect(screen, (100, 150, 200), self.btn_prev, border_radius=6)
            txt_prev = fm.render("< Prev", True, (255, 255, 255))
        else:
            pygame.draw.rect(screen, (220, 220, 220), self.btn_prev, border_radius=6)
            txt_prev = fm.render("< Prev", True, (150, 150, 150))
        screen.blit(txt_prev, (self.btn_prev.centerx - txt_prev.get_width()//2, self.btn_prev.centery - txt_prev.get_height()//2))

        page_txt = fb.render(f"Page {self.current_page + 1} of {self.total_pages}", True, (80, 80, 80))
        screen.blit(page_txt, (cx - page_txt.get_width()//2, bottom_y + 8))

        self.btn_next = pygame.Rect(cx + 70, bottom_y, 80, 35)
        if self.current_page < self.total_pages - 1:
            pygame.draw.rect(screen, (100, 150, 200), self.btn_next, border_radius=6)
            txt_next = fm.render("Next >", True, (255, 255, 255))
        else:
            pygame.draw.rect(screen, (220, 220, 220), self.btn_next, border_radius=6)
            txt_next = fm.render("Next >", True, (150, 150, 150))
        screen.blit(txt_next, (self.btn_next.centerx - txt_next.get_width()//2, self.btn_next.centery - txt_next.get_height()//2))

    def handle_scroll(self, e):
        # Support both MOUSEWHEEL (new) and MOUSEBUTTON (old)
        if e.type == pygame.MOUSEWHEEL:
            if e.y > 0 and self.current_page > 0: self.current_page -= 1 # Scroll Up
            elif e.y < 0 and self.current_page < self.total_pages - 1: self.current_page += 1 # Scroll Down
        elif e.type == pygame.MOUSEBUTTONDOWN:
            if e.button == 4 and self.current_page > 0: self.current_page -= 1
            elif e.button == 5 and self.current_page < self.total_pages - 1: self.current_page += 1

    def handle_click(self, pos):
        if self.close_btn and self.close_btn.collidepoint(pos): self.active = False; return
        
        # Normal Prev/Next
        if self.btn_prev and self.btn_prev.collidepoint(pos) and self.current_page > 0: 
            self.current_page -= 1; return
        if self.btn_next and self.btn_next.collidepoint(pos) and self.current_page < self.total_pages - 1: 
            self.current_page += 1; return
            
        # Fast Jump: Click the center page text to skip 5 pages forward (or wrap around)
        cx = self.rect.centerx
        page_rect = pygame.Rect(cx - 60, self.rect.bottom - 55, 120, 35)
        if page_rect.collidepoint(pos):
            self.current_page = (self.current_page + 5) % self.total_pages
            return
            
        for btn, off in self.zones:
            if btn.collidepoint(pos):
                self.parent.smart_load_pgn(self.path, off) 
                self.active = False
                return

# =============================================================================
#  BUTTONS POPUP (Consolidated UI actions)
# =============================================================================
class ButtonsPopup(BasePopup):
    def __init__(self, parent):
        super().__init__(parent, 420, 480)
        self.parent = parent
        # Keep main UI buttons (like Profile) out of this consolidated popup
        self.btns = [
            ("New Game", "reset"), ("Flip Board", "flip"), ("Takeback", "undo"),
            ("Game Mode", "mode"), ("Puzzles", "puzzles"), ("Theme", "theme"),
            ("GM Move", "gm_move"), ("Engine Hints", "enginehint"),
            ("Live Annotations", "annotations"), ("Copy Current FEN", "copy_fen"),
            ("Select Piece Set", "select_piece_set"),
            ("Settings", "settings")
        ]
        self.zones = []
        self.scroll = 0
        self.max_scroll = 0

    def draw(self, screen, fb, fm):
        self.draw_bg(screen, "Actions", fb)
        clip = pygame.Rect(self.rect.x + 20, self.rect.y + 70, self.w - 40, self.h - 90)
        screen.set_clip(clip)
        y = clip.y - self.scroll
        self.zones = []
        for txt, tag in self.btns:
            r = pygame.Rect(clip.x + 10, y + 8, clip.width - 20, 42)
            col = (230, 240, 255) if r.collidepoint(pygame.mouse.get_pos()) else (255,255,255)
            pygame.draw.rect(screen, col, r, border_radius=8)
            pygame.draw.rect(screen, (200,200,200), r, 1, border_radius=8)
            # Attempt to draw icon similar to old button behavior
            ic_key = tag
            if tag == "gm_move": ic_key = "gm_icon"
            elif tag == "profile": ic_key = "pgnload"
            elif tag == "settings":
                ic_key = "settings"
                if not self.parent.assets.icons.get(ic_key):
                    # Try canonical filename first, then a possible misspelled variant
                    for fname in ("settings.png", "settiings.png"):
                        try:
                            p = os.path.join('assets', 'icons', fname)
                            if os.path.exists(p):
                                img = pygame.image.load(p).convert_alpha()
                                self.parent.assets.icons[ic_key] = img
                                break
                        except Exception:
                            continue
            icon = self.parent.assets.icons.get(ic_key)
            tx = r.x + 18
            if icon:
                screen.blit(pygame.transform.smoothscale(icon, (20,20)), (r.x + 12, r.y + 11))
                tx = r.x + 40
            
            # Add toggle indicator for specific buttons
            btn_txt = txt
            if tag == "enginehint" and hasattr(self.parent, 'show_hints'):
                status = "[ON]" if self.parent.show_hints else "[OFF]"
                btn_txt = f"{txt} {status}"
            elif tag == "annotations":
                status = "[ON]" if self.parent.settings.get("live_annotations", True) else "[OFF]"
                btn_txt = f"{txt} {status}"
            elif tag == "dark_theme":
                status = "[ON]" if self.parent.settings.get("dark_theme", False) else "[OFF]"
                btn_txt = f"{txt} {status}"
                
            screen.blit(fb.render(btn_txt, True, (20,20,20)), (tx, r.y + 10))
            self.zones.append((r, tag))
            y += 52
        # compute max scroll
        total_h = len(self.btns) * 52
        self.max_scroll = max(0, total_h - clip.height)
        screen.set_clip(None)

    def handle_click(self, pos):
        if self.close_btn and self.close_btn.collidepoint(pos): self.active = False; return
        for r, tag in self.zones:
            if r.collidepoint(pos):
                try:
                    self.parent.handle_ui(tag)
                except Exception:
                    pass
                self.active = False
                return

    def handle_scroll(self, e):
        # Mouse wheel: 4=up,5=down
        if e.button == 4:
            self.scroll = max(0, self.scroll - 40)
        elif e.button == 5:
            self.scroll = min(self.max_scroll, self.scroll + 40)

# --- REPLACED: BOT POPUP (With Ranked Mode) ---
class BotPopup:
    def __init__(self, parent):
        self.parent = parent
        self.active = True
        self.w, self.h = 900, 700
        cx, cy = parent.width // 2, parent.height // 2
        self.rect = pygame.Rect(cx - self.w // 2, cy - self.h // 2, self.w, self.h)
        self.scroll_l = 0; self.scroll_r = 0
        self.col_l_items = self.group_bots(BOTS)
        self.col_r_items = parent.assets.gm_books
        self.close_btn = None
        self.click_zones = []
        self.btn_ranked = None # NEW: Ranked Button

    def group_bots(self, bots):
        grps = {"Beginner":[], "Intermediate":[], "Advanced":[], "Master":[]}
        for b in bots: 
            # Allow standard engines OR the specific Checkmate Master bot
            if b.get("type") != "book" or b.get("name") == "Checkmate Master":
                grps.get(b.get("group", "Master"), []).append(b)
        return grps

    def draw(self, screen, fb, fm):
        ov = pygame.Surface(screen.get_size(), pygame.SRCALPHA); ov.fill((0, 0, 0, 160)); screen.blit(ov, (0, 0))
        shadow = self.rect.copy(); shadow.y += 8
        pygame.draw.rect(screen, (0,0,0,50), shadow, border_radius=20)
        pygame.draw.rect(screen, (252, 252, 254), self.rect, border_radius=16)
        pygame.draw.rect(screen, (210, 210, 215), self.rect, 2, border_radius=16)
        pygame.draw.line(screen, (220,220,225), (self.rect.centerx, self.rect.y+60), (self.rect.centerx, self.rect.bottom-80), 2)
        screen.blit(fb.render("Select Bot Engine", True, (50,50,50)), (self.rect.x+130, self.rect.y+20))
        screen.blit(fb.render("Select GM Personality", True, (50,50,50)), (self.rect.centerx+130, self.rect.y+20))
        
        self.click_zones = []
        ly = self.rect.y + 70 - self.scroll_l
        clip_l = pygame.Rect(self.rect.x, self.rect.y+60, self.w//2, self.h-140) # Shorter clip area
        screen.set_clip(clip_l)
        for gname, blist in self.col_l_items.items():
            if blist:
                screen.blit(fb.render(gname, True, THEME["accent"]), (self.rect.x+20, ly))
                ly += 30
                for b in blist:
                    r = pygame.Rect(self.rect.x+20, ly, self.w//2-40, 70)
                    col = (230,230,240) if r.collidepoint(pygame.mouse.get_pos()) else (255,255,255)
                    pygame.draw.rect(screen, col, r, border_radius=8)
                    av = self.parent.assets.get_avatar(b["name"])
                    if av:
                        scaled_av = self.parent.assets.scale_keep_aspect(av, (50, 50))
                        ox = (50 - scaled_av.get_width()) // 2
                        oy = (50 - scaled_av.get_height()) // 2
                        screen.blit(scaled_av, (r.x + 10 + ox, r.y + 10 + oy))
                    screen.blit(fb.render(b["name"], True, (0,0,0)), (r.x+70, r.y+10))
                    screen.blit(fm.render(f"Elo: {b['elo']} | {b['style']}", True, (100,100,100)), (r.x+70, r.y+40))
                    self.click_zones.append((r, b, "bot"))
                    ly += 80
        screen.set_clip(None)

        ry = self.rect.y + 70 - self.scroll_r
        clip_r = pygame.Rect(self.rect.centerx, self.rect.y+60, self.w//2, self.h-140) # Shorter clip area
        screen.set_clip(clip_r)
        for gm in self.col_r_items:
            r = pygame.Rect(self.rect.centerx+20, ry, self.w//2-40, 70)
            col = (230,230,240) if r.collidepoint(pygame.mouse.get_pos()) else (255,255,255)
            pygame.draw.rect(screen, col, r, border_radius=8)
            
            b_name = f"GM {gm['name']}"
            av_img = self.parent.assets.avatars.get(b_name) or self.parent.assets.icons.get("gm_icon")
            if av_img:
                scaled_av = self.parent.assets.scale_keep_aspect(av_img, (50, 50))
                ox = (50 - scaled_av.get_width()) // 2
                oy = (50 - scaled_av.get_height()) // 2
                screen.blit(scaled_av, (r.x + 10 + ox, r.y + 10 + oy))
                
            screen.blit(fb.render(gm["name"], True, (0,0,0)), (r.x+70, r.y+20))
            self.click_zones.append((r, gm, "gm"))
            ry += 80
        screen.set_clip(None)
        
        # --- NEW: RANKED MATCH BUTTON ---
        btn_y = self.rect.bottom - 70
        self.btn_ranked = pygame.Rect(self.rect.centerx - 150, btn_y, 300, 50)
        col_ranked = (210, 160, 40) if self.btn_ranked.collidepoint(pygame.mouse.get_pos()) else (230, 180, 50)
        pygame.draw.rect(screen, col_ranked, self.btn_ranked, border_radius=10)
        
        search_icon = self.parent.assets.icons.get("icon_search")
        txt = fb.render("Play Ranked (Auto-Match)", True, (255, 255, 255))
        
        if search_icon:
            scaled_icon = pygame.transform.smoothscale(search_icon, (28, 28))
            total_w = scaled_icon.get_width() + 10 + txt.get_width()
            start_x = self.btn_ranked.centerx - total_w // 2
            screen.blit(scaled_icon, (start_x, self.btn_ranked.centery - scaled_icon.get_height() // 2))
            screen.blit(txt, (start_x + scaled_icon.get_width() + 10, self.btn_ranked.centery - txt.get_height() // 2))
        else:
            txt_fallback = fb.render("🎲 Play Ranked (Auto-Match)", True, (255, 255, 255))
            screen.blit(txt_fallback, (self.btn_ranked.centerx - txt_fallback.get_width()//2, self.btn_ranked.centery - txt_fallback.get_height()//2))

        # --- RESTORED CLOSE BUTTON WITH ICON ---
        self.close_btn = pygame.Rect(self.rect.right - 40, self.rect.y + 10, 30, 30)
        close_icon = self.parent.assets.icons.get("close_btn")
        
        if close_icon:
            screen.blit(pygame.transform.smoothscale(close_icon, (30, 30)), (self.close_btn.x, self.close_btn.y))
        else:
            pygame.draw.rect(screen, (200, 200, 200), self.close_btn, border_radius=5)
            screen.blit(fb.render("X", True, (0, 0, 0)), (self.close_btn.x + 8, self.close_btn.y + 2))

    def handle_scroll(self, e):
        mx, my = e.pos if hasattr(e, 'pos') else pygame.mouse.get_pos()
        if mx < self.rect.centerx:
            if e.button == 4: self.scroll_l = max(0, self.scroll_l - 30)
            elif e.button == 5: self.scroll_l += 30
        else:
            if e.button == 4: self.scroll_r = max(0, self.scroll_r - 30)
            elif e.button == 5: self.scroll_r += 30

    def handle_click(self, pos):
        if self.close_btn.collidepoint(pos): self.active = False; return
        
        # --- Handle Ranked Match Click ---
        if self.btn_ranked and self.btn_ranked.collidepoint(pos):
            self.parent.start_ranked_match()
            self.active = False
            return
            
        for r, data, type_ in self.click_zones:
            if r.collidepoint(pos):
                if type_ == "bot": self.parent.side_popup = SideSelectionPopup(self.parent, data)
                else:
                    bot_data = {"name": f"GM {data['name']}", "elo": "Book", "style": "GM", "type": "book", "path": data["path"]}
                    self.parent.side_popup = SideSelectionPopup(self.parent, bot_data)
                self.active = False
                return

class SideSelectionPopup(BasePopup):
    def __init__(self, parent, bot_data):
        super().__init__(parent, 500, 300)
        self.bot_data = bot_data; self.rects = {}

    def draw(self, screen, fb=None, fm=None):
        ov = pygame.Surface(screen.get_size(), pygame.SRCALPHA); ov.fill((0, 0, 0, 160)); screen.blit(ov, (0, 0))
        cw, ch = 550, 330 # Enlarged slightly for modern feel
        cx, cy = (screen.get_width() - cw)//2, (screen.get_height() - ch)//2
        shadow = pygame.Rect(cx, cy + 8, cw, ch)
        pygame.draw.rect(screen, (0,0,0,50), shadow, border_radius=20)
        pygame.draw.rect(screen, (252, 252, 254), (cx, cy, cw, ch), border_radius=16)
        pygame.draw.rect(screen, (210, 210, 215), (cx, cy, cw, ch), 2, border_radius=16)
        self.close_btn = pygame.Rect(cx + cw - 40, cy + 10, 30, 30)
        x_col = (220, 220, 220) if self.close_btn.collidepoint(pygame.mouse.get_pos()) else (240, 240, 240)
        pygame.draw.rect(screen, x_col, self.close_btn, border_radius=5)
        screen.blit(self.parent.font_b.render("X", True, (0,0,0)), (self.close_btn.x + 8, self.close_btn.y + 1))
        title = self.parent.font_b.render(f"Play vs {self.bot_data['name']}", True, (20, 20, 20))
        screen.blit(title, (cx + (cw - title.get_width())//2, cy + 30))
        wk_img = None; bk_img = None
        try:
            wk_img = self.parent.assets.pieces.get("wk") or self.parent.assets.pieces.get("wK")
            bk_img = self.parent.assets.pieces.get("bk") or self.parent.assets.pieces.get("bK")
            if wk_img: wk_img = pygame.transform.smoothscale(wk_img, (100, 100))
            if bk_img: bk_img = pygame.transform.smoothscale(bk_img, (100, 100))
        except: pass
        card_w, card_h = 140, 140
        gap = 40
        total_cards_w = card_w * 2 + gap
        card_x_start = cx + (cw - total_cards_w) // 2
        btn_y = cy + (ch - card_h) // 2 + 10  # vertically centred with slight downward nudge for title

        w_rect = pygame.Rect(card_x_start, btn_y, card_w, card_h)
        pygame.draw.rect(screen, (240, 240, 240), w_rect, border_radius=10)
        if wk_img: screen.blit(wk_img, (w_rect.x + (card_w - wk_img.get_width()) // 2, w_rect.y + 10))
        w_lbl = self.parent.font_s.render("White", True, (0, 0, 0))
        screen.blit(w_lbl, (w_rect.centerx - w_lbl.get_width() // 2, w_rect.bottom - 28))
        self.rects["white"] = w_rect

        b_rect = pygame.Rect(card_x_start + card_w + gap, btn_y, card_w, card_h)
        pygame.draw.rect(screen, (180, 180, 180), b_rect, border_radius=10)
        if bk_img: screen.blit(bk_img, (b_rect.x + (card_w - bk_img.get_width()) // 2, b_rect.y + 10))
        b_lbl = self.parent.font_s.render("Black", True, (0, 0, 0))
        screen.blit(b_lbl, (b_rect.centerx - b_lbl.get_width() // 2, b_rect.bottom - 28))
        self.rects["black"] = b_rect

    def handle_click(self, pos):
        if self.close_btn.collidepoint(pos): self.active = False; return
        if self.rects["white"].collidepoint(pos): self.start_game(True)
        elif self.rects["black"].collidepoint(pos): self.start_game(False)
            
    def start_game(self, play_as_white):
        self.parent.active_bot = self.bot_data
        self.parent.playing_white = play_as_white
        self.parent.mode_idx = 1
        self.parent.mode = "play"
        
        # Reset both the library board and your custom logic handler
        self.parent.board.reset()
        if self.parent.logic:
            self.parent.logic.reset_game()
            
        self.parent.history = []
        self.parent.view_ply = 0
        self.parent.chat_log = []
        self.parent.add_chat("System", f"Game started vs {self.bot_data['name']}")
        self.active = False
        if self.parent.bot_popup: self.parent.bot_popup.active = False

class SettingsPopup(BasePopup):
     def __init__(self, parent):
        super().__init__(parent, 400, 400)
        self.toggle_rects = []
        
     def draw(self, screen, fb, fm):
        self.draw_bg(screen, "Settings", fb)
        y = self.rect.y + 90
        opts = [("Sound", "sound"), ("Bot Voice", "speech")]
        self.toggle_rects = []
        for label, key in opts:
            val = self.parent.settings.get(key, True)
            col = (50, 200, 50) if val else (200, 50, 50)
            btn = pygame.Rect(self.rect.right - 100, y, 60, 30)
            pygame.draw.rect(screen, col, btn, border_radius=15)
            toggle_x = btn.right - 25 if val else btn.x + 5
            pygame.draw.circle(screen, (255,255,255), (toggle_x + 10, btn.centery), 12)
            lbl = fm.render(label, True, (0,0,0))
            screen.blit(lbl, (self.rect.x + 40, btn.centery - lbl.get_height()//2))
            self.toggle_rects.append((btn, key))
            y += 55

     def handle_click(self, pos):
         if self.close_btn.collidepoint(pos): self.active = False; return
         for btn, key in getattr(self, 'toggle_rects', []):
             if btn.collidepoint(pos):
                 # Toggle setting and save immediately to config!
                 self.parent.settings[key] = not self.parent.settings.get(key, False)
                 self.parent.save_config()
                 return

# =============================================================================
#  PIECE SET SELECTION POPUP
# =============================================================================
class PieceSetPopup(BasePopup):
    def __init__(self, parent):
        super().__init__(parent, 400, 420)
        self.sets = []
        self.zones = []
        self._refresh()

    def _refresh(self):
        from assets import AssetLoader
        self.sets = AssetLoader.get_available_piece_sets()

    def draw(self, screen, fb, fm):
        self.draw_bg(screen, "Select Piece Set", fb)
        y = self.rect.y + 70
        self.zones = []
        current = self.parent.settings.get("piece_set", "default")

        for set_name in self.sets:
            r = pygame.Rect(self.rect.x + 30, y, self.rect.width - 60, 44)
            is_active = (set_name == current)
            is_hover = r.collidepoint(pygame.mouse.get_pos())

            if is_active:
                bg_col = THEME["accent"]
            elif is_hover:
                bg_col = (220, 228, 255)
            else:
                bg_col = (248, 248, 252)

            pygame.draw.rect(screen, bg_col, r, border_radius=8)
            pygame.draw.rect(screen, (200, 200, 210), r, 1, border_radius=8)

            label = set_name.capitalize() if set_name != "default" else "Default (Classic)"
            txt_col = (255, 255, 255) if is_active else (20, 20, 30)
            t = fm.render(label, True, txt_col)
            screen.blit(t, (r.x + 16, r.centery - t.get_height() // 2))

            # Active checkmark
            if is_active:
                ck = fm.render("✓", True, (255, 255, 255))
                screen.blit(ck, (r.right - ck.get_width() - 14, r.centery - ck.get_height() // 2))

            self.zones.append((r, set_name))
            y += 54

    def handle_click(self, pos):
        if self.close_btn and self.close_btn.collidepoint(pos):
            self.active = False
            return
        for r, set_name in self.zones:
            if r.collidepoint(pos):
                self.parent.apply_piece_set(set_name)
                self.active = False
                return

class GMPopup:
    def __init__(self, parent):
        self.parent = parent
        self.active = True
        self.w, self.h = 600, 500
        self.rect = pygame.Rect((parent.width - self.w)//2, (parent.height - self.h)//2, self.w, self.h)
        self.close_btn = pygame.Rect(self.rect.right - 40, self.rect.y + 10, 30, 30)
        self.click_zones = []
        self.scroll_y = 0

        # --- FIX: Load ALL books to the list, regardless of the current board state ---
        self.gm_list = []
        import chess.polyglot
        board = self.parent.board
        
        for gm in self.parent.assets.gm_books:
            move_info = None
            try:
                with chess.polyglot.open_reader(gm["path"]) as reader:
                    entries = list(reader.find_all(board))
                    if entries:
                        top_entry = entries[0]
                        move_info = {
                            "move": top_entry.move,
                            "san": board.san(top_entry.move),
                            "weight": top_entry.weight
                        }
            except Exception: pass
            
            self.gm_list.append({
                "gm_name": gm["name"],
                "file_name": os.path.basename(gm["path"]), # <-- FIX: Extracts just the filename!
                "move_info": move_info
            })
            
        # Sort so GMs who actually have a move appear at the top of the list!
        self.gm_list.sort(key=lambda x: (x["move_info"] is None, x["gm_name"]))

    def draw(self, screen, fb, fm):
        ov = pygame.Surface(screen.get_size(), pygame.SRCALPHA); ov.fill((0, 0, 0, 160)); screen.blit(ov, (0, 0))
        shadow_surf = pygame.Surface((self.w + 10, self.h + 10), pygame.SRCALPHA)
        pygame.draw.rect(shadow_surf, (0, 0, 0, 45), shadow_surf.get_rect(), border_radius=20)
        screen.blit(shadow_surf, (self.rect.x - 2, self.rect.y + 8))
        pygame.draw.rect(screen, (252, 252, 254), self.rect, border_radius=16)
        pygame.draw.rect(screen, (210, 210, 215), self.rect, 2, border_radius=16)
        t_surf = fb.render("What would a Grandmaster play?", True, (40, 40, 40))
        screen.blit(t_surf, (self.rect.centerx - t_surf.get_width()//2, self.rect.y + 24))

        self.close_btn = pygame.Rect(self.rect.right - 46, self.rect.y + 18, 30, 30)
        is_hover = self.close_btn.collidepoint(pygame.mouse.get_pos())
        col = (240, 80, 80) if is_hover else (225, 225, 230)
        txt_col = (255, 255, 255) if is_hover else (100, 100, 100)
        pygame.draw.rect(screen, col, self.close_btn, border_radius=8)
        x_surf = fb.render("X", True, txt_col)
        screen.blit(x_surf, (self.close_btn.centerx - x_surf.get_width()//2,
                              self.close_btn.centery - x_surf.get_height()//2))
        
        if not self.gm_list:
            screen.blit(fm.render("No GM books loaded in assets/books/", True, (150, 150, 150)), (self.rect.x + 50, self.rect.y + 150))
            return

        clip = pygame.Rect(self.rect.x, self.rect.y + 70, self.w, self.h - 80)
        screen.set_clip(clip)
        
        ly = self.rect.y + 70 - self.scroll_y
        self.click_zones = []
        
        for item in self.gm_list:
            r = pygame.Rect(self.rect.x + 20, ly, self.w - 40, 60)
            
            # --- 1. Background & Hover Logic ---
            if item["move_info"]:
                col = (235, 240, 255) if r.collidepoint(pygame.mouse.get_pos()) else (255, 255, 255)
                pygame.draw.rect(screen, col, r, border_radius=8)
                self.click_zones.append((r, item["move_info"]["move"]))
            else:
                pygame.draw.rect(screen, (245, 245, 245), r, border_radius=8)

            pygame.draw.rect(screen, (220, 220, 230), r, 1, border_radius=8)
            
            # --- 2. Draw Avatar ---
            av_img = self.parent.assets.avatars.get(f"GM {item['gm_name']}") or self.parent.assets.icons.get("gm_icon")
            if av_img:
                scaled_av = self.parent.assets.scale_keep_aspect(av_img, (40, 40))
                ox = (40 - scaled_av.get_width()) // 2
                oy = (40 - scaled_av.get_height()) // 2
                screen.blit(scaled_av, (r.x + 10 + ox, r.y + 10 + oy))
            
            # --- 3. Draw GM Name and Filename Subtitle ---
            screen.blit(fb.render(f"GM {item['gm_name']}", True, (50, 50, 50)), (r.x + 60, r.y + 10))
            screen.blit(fm.render(f"File: {item['file_name']}", True, (120, 120, 140)), (r.x + 60, r.y + 32))
            
            # --- 4. Draw Recommended Move (Right Side) ---
            if item["move_info"]:
                play_txt = fm.render("plays", True, (100, 100, 100))
                screen.blit(play_txt, (r.right - 120 - play_txt.get_width(), r.y + 20))
                
                move_txt = fb.render(item["move_info"]["san"], True, (20, 140, 40))
                screen.blit(move_txt, (r.right - 110, r.y + 20))
            else:
                out_txt = fm.render("Out of Book", True, (160, 160, 160))
                screen.blit(out_txt, (r.right - 20 - out_txt.get_width(), r.y + 20))
            
            ly += 70
            
        screen.set_clip(None)

    def handle_scroll(self, e):
        if e.button == 4: self.scroll_y = max(0, self.scroll_y - 30)
        elif e.button == 5: self.scroll_y += 30

    def handle_click(self, pos):
        if self.close_btn.collidepoint(pos):
            self.active = False
            return
        for r, move in self.click_zones:
            if r.collidepoint(pos):
                self.parent.apply_move(move) # <--- FIX: Just pass 'move', not move[0]
                self.active = False
                return
                
    def handle_input(self, e): pass
    
# =============================================================================
#  TRAINER COMPLETE POPUP
# =============================================================================
class TrainerCompletePopup(BasePopup):
    def __init__(self, parent):
        super().__init__(parent, 450, 350)
        self.btn_yes = None
        self.btn_no = None

    def draw(self, screen, fb, fm):
        self.draw_bg(screen, "Practice Completed!", fb)
        cx, cy = self.rect.centerx, self.rect.y

        bot_name = self.parent.active_bot.get("name") if self.parent.active_bot else "player"
        av = self.parent.assets.get_avatar(bot_name)
        if av:
            scaled = pygame.transform.smoothscale(av, (80, 80))
            screen.blit(scaled, (cx - scaled.get_width()//2, cy + 65))

        status = getattr(self.parent, 'status_msg', '').lower()
        op_name = getattr(self.parent, 'opening_name', '').lower()
        type_str = "mate sequence" if ("mate sequence" in status or "mate" in op_name) else "opening"

        txt = fb.render(f"Shall we practice another {type_str}?", True, (40, 40, 40))
        screen.blit(txt, (cx - txt.get_width()//2, cy + 165))

        self.btn_yes = pygame.Rect(cx - 120, cy + 218, 240, 45)
        col_yes = (60, 180, 60) if self.btn_yes.collidepoint(pygame.mouse.get_pos()) else (50, 160, 50)
        pygame.draw.rect(screen, col_yes, self.btn_yes, border_radius=8)
        t_yes = fb.render("Yes, sure !", True, (255, 255, 255))
        screen.blit(t_yes, (self.btn_yes.centerx - t_yes.get_width()//2, self.btn_yes.centery - t_yes.get_height()//2))

        self.btn_no = pygame.Rect(cx - 120, cy + 278, 240, 45)
        col_no = (200, 200, 200) if self.btn_no.collidepoint(pygame.mouse.get_pos()) else (220, 220, 220)
        pygame.draw.rect(screen, col_no, self.btn_no, border_radius=8)
        t_no = fb.render("Enough for now...", True, (80, 80, 80))
        screen.blit(t_no, (self.btn_no.centerx - t_no.get_width()//2, self.btn_no.centery - t_no.get_height()//2))

    def handle_click(self, pos):
        if self.btn_yes and self.btn_yes.collidepoint(pos):
            self.parent.handle_ui("trainer_reopen")
            self.active = False
        elif (self.btn_no and self.btn_no.collidepoint(pos)) or (self.close_btn and self.close_btn.collidepoint(pos)):
            self.parent.handle_ui("trainer_close")
            self.active = False
            
# =============================================================================
#  TRAINER SIDE SELECTION POPUP
# =============================================================================
class TrainerSideSelectionPopup(BasePopup):
    def __init__(self, parent, training_data, is_tutorial=False):
        super().__init__(parent, 500, 300)
        self.training_data = training_data
        self.is_tutorial = is_tutorial
        self.rects = {}
        
        # Instantly close the underlying Practice list so it doesn't overlap! ---
        if hasattr(self.parent, 'trainer_popup') and self.parent.trainer_popup:
            self.parent.trainer_popup.active = False

    def draw(self, screen, fb=None, fm=None):
        ov = pygame.Surface(screen.get_size(), pygame.SRCALPHA); ov.fill((0, 0, 0, 160)); screen.blit(ov, (0, 0))
        cw, ch = 550, 340
        cx, cy = (screen.get_width() - cw)//2, (screen.get_height() - ch)//2

        shadow_surf = pygame.Surface((cw + 10, ch + 10), pygame.SRCALPHA)
        pygame.draw.rect(shadow_surf, (0, 0, 0, 45), shadow_surf.get_rect(), border_radius=20)
        screen.blit(shadow_surf, (cx - 2, cy + 8))
        pygame.draw.rect(screen, (252, 252, 254), (cx, cy, cw, ch), border_radius=16)
        pygame.draw.rect(screen, (210, 210, 215), (cx, cy, cw, ch), 2, border_radius=16)

        self.close_btn = pygame.Rect(cx + cw - 42, cy + 12, 28, 28)
        x_col = (210, 210, 210) if self.close_btn.collidepoint(pygame.mouse.get_pos()) else (235, 235, 235)
        pygame.draw.rect(screen, x_col, self.close_btn, border_radius=6)
        x_surf = self.parent.font_b.render("X", True, (80, 80, 80))
        screen.blit(x_surf, (self.close_btn.centerx - x_surf.get_width()//2,
                              self.close_btn.centery - x_surf.get_height()//2))

        title_text = self.training_data.get('name', 'Practice')
        if len(title_text) > 30: title_text = title_text[:27] + "..."
        title = self.parent.font_b.render(f"Practice: {title_text}", True, (20, 20, 20))
        screen.blit(title, (cx + (cw - title.get_width())//2, cy + 28))

        wk_img = self.parent.assets.pieces.get("wk") or self.parent.assets.pieces.get("wK")
        bk_img = self.parent.assets.pieces.get("bk") or self.parent.assets.pieces.get("bK")
        if wk_img: wk_img = pygame.transform.smoothscale(wk_img, (100, 100))
        if bk_img: bk_img = pygame.transform.smoothscale(bk_img, (100, 100))

        card_w, card_h = 155, 160
        gap = 40
        total = card_w * 2 + gap
        card_start_x = cx + (cw - total) // 2
        btn_y = cy + 82

        w_rect = pygame.Rect(card_start_x, btn_y, card_w, card_h)
        pygame.draw.rect(screen, (242, 242, 242), w_rect, border_radius=12)
        pygame.draw.rect(screen, (210, 210, 215), w_rect, 1, border_radius=12)
        if wk_img:
            screen.blit(wk_img, (w_rect.centerx - wk_img.get_width()//2, w_rect.y + 16))
        lbl = self.parent.font_s.render("Play as White", True, (30, 30, 30))
        screen.blit(lbl, (w_rect.centerx - lbl.get_width()//2, w_rect.bottom - 28))
        self.rects["white"] = w_rect

        b_rect = pygame.Rect(card_start_x + card_w + gap, btn_y, card_w, card_h)
        pygame.draw.rect(screen, (175, 175, 175), b_rect, border_radius=12)
        pygame.draw.rect(screen, (140, 140, 140), b_rect, 1, border_radius=12)
        if bk_img:
            screen.blit(bk_img, (b_rect.centerx - bk_img.get_width()//2, b_rect.y + 16))
        lbl = self.parent.font_s.render("Play as Black", True, (20, 20, 20))
        screen.blit(lbl, (b_rect.centerx - lbl.get_width()//2, b_rect.bottom - 28))
        self.rects["black"] = b_rect

    def handle_click(self, pos):
        if self.close_btn.collidepoint(pos): 
            self.active = False
            self.parent.handle_ui("trainer_reopen")
            return
        if self.rects["white"].collidepoint(pos): self.start_practice(True)
        elif self.rects["black"].collidepoint(pos): self.start_practice(False)
            
    def start_practice(self, play_as_white):
        self.parent.start_trainer(self.training_data, play_as_white, self.is_tutorial)
        self.active = False
        if self.parent.trainer_popup: self.parent.trainer_popup.active = False

# =============================================================================
#  PROFILE & ARCHIVE POPUP
# =============================================================================
class ProfilePopup(BasePopup):
    def __init__(self, parent):
        super().__init__(parent, 1050, 750)
        self.ledger = parent.match_ledger 
        self.practice_ledger = parent.practice_ledger
        self.scroll = 0
        self.sort_by_acc = False
        
        self.tab = "matches" # "matches" or "practice"
        self.btn_tab_matches = None
        self.btn_tab_practice = None
        
        self.btn_import = None
        self.btn_sort = None
        self.click_zones = []
        
        # State for the "Select Color" mini-prompt
        self.pending_import_path = None
        self.btn_white = None
        self.btn_black = None
        
    def _max_scroll(self):
        n = len(self.ledger) if self.tab == "matches" else len(self.practice_ledger)
        return max(0, n * 60 - (self.rect.height - 290))

    def handle_scroll(self, e):
        ms = self._max_scroll()
        delta = 0
        if   e.type == pygame.MOUSEWHEEL:    delta = -45 if e.y > 0 else 45
        elif e.type == pygame.MOUSEBUTTONDOWN:
            if e.button == 4: delta = -45
            elif e.button == 5: delta = 45
        self.scroll = max(0, min(ms, self.scroll + delta))

    def draw(self, screen, fb, fm):
        self.draw_bg(screen, "My Chess Profile & Archive", fb)
        
        cx = self.rect.centerx
        
        # --- 1. Top Section: Stats & Graph Placeholder ---
        top_rect = pygame.Rect(self.rect.x + 20, self.rect.y + 60, self.rect.width - 40, 150)
        pygame.draw.rect(screen, (255, 255, 255), top_rect, border_radius=10)
        pygame.draw.rect(screen, (220, 220, 230), top_rect, 1, border_radius=10)
        
        # Avatar (Using pgnload.png as requested)
        av = self.parent.assets.icons.get("pgnload")
        if av: screen.blit(pygame.transform.smoothscale(av, (80, 80)), (top_rect.x + 20, top_rect.y + 35))
        
        screen.blit(self.parent.font_huge.render(str(self.parent.player_elo), True, THEME["accent"]),
                    (top_rect.x + 120, top_rect.y + 18))
        screen.blit(fm.render("Current Elo", True, (100,100,100)), (top_rect.x + 125, top_rect.y + 78))

        # --- Accuracy Trend Graph (last 20 games, right side of stats box) ---
        recent = list(reversed(self.ledger))[:20]
        if len(recent) >= 2:
            acc_vals = [g.get("accuracy", 0) for g in reversed(recent)]
            gr_x = top_rect.x + 280
            gr_y = top_rect.y + 16
            gr_w = top_rect.width - 300
            gr_h = top_rect.height - 32

            pygame.draw.rect(screen, (248, 248, 252),
                             pygame.Rect(gr_x, gr_y, gr_w, gr_h), border_radius=6)
            pygame.draw.rect(screen, (210, 210, 220),
                             pygame.Rect(gr_x, gr_y, gr_w, gr_h), 1, border_radius=6)

            albl = self.parent.font_s.render("Accuracy Trend (last 20 games)", True, (100, 100, 120))
            screen.blit(albl, (gr_x + 8, gr_y + 4))

            n = len(acc_vals)
            pts2 = []
            for i, av in enumerate(acc_vals):
                px2 = gr_x + 8 + int(i * (gr_w - 16) / max(1, n - 1))
                py2 = gr_y + gr_h - 18 - int((av / 100) * (gr_h - 30))
                pts2.append((px2, py2))

            if len(pts2) >= 2:
                # Catmull-Rom smooth green curve — no dots
                def _cr(p0, p1, p2, p3, t):
                    return 0.5 * (2*p1 + (-p0+p2)*t + (2*p0-5*p1+4*p2-p3)*t*t + (-p0+3*p1-3*p2+p3)*t*t*t)
                smooth2 = [pts2[0]]
                for i in range(1, len(pts2)):
                    q0 = pts2[max(0, i-2)]; q1 = pts2[i-1]; q2 = pts2[i]; q3 = pts2[min(len(pts2)-1, i+1)]
                    for s in range(1, 21):
                        t = s / 20
                        smooth2.append((int(_cr(q0[0],q1[0],q2[0],q3[0],t)), int(_cr(q0[1],q1[1],q2[1],q3[1],t))))
                # Green gradient fill
                fill2_surf = pygame.Surface((gr_w, gr_h), pygame.SRCALPHA)
                pygame.draw.polygon(fill2_surf, (50, 200, 90, 28),
                                    [(p[0]-gr_x, p[1]-gr_y) for p in smooth2] + [(smooth2[-1][0]-gr_x, gr_h-8), (smooth2[0][0]-gr_x, gr_h-8)])
                screen.blit(fill2_surf, (gr_x, gr_y))
                # AA green curve: wide faint then sharp — no dots
                pygame.draw.lines(screen, (40, 180, 80), False, smooth2, 4)
                pygame.draw.lines(screen, (50, 200, 90), False, smooth2, 2)

            # Average line
            avg_acc = sum(acc_vals) / len(acc_vals)
            avg_y2 = gr_y + gr_h - 18 - int((avg_acc / 100) * (gr_h - 30))
            pygame.draw.line(screen, (180, 180, 200), (gr_x + 8, avg_y2),
                             (gr_x + gr_w - 8, avg_y2), 1)
            avg_lbl = self.parent.font_s.render(f"Avg {avg_acc:.1f}%", True, (130, 130, 150))
            screen.blit(avg_lbl, (gr_x + gr_w - avg_lbl.get_width() - 6, avg_y2 - 14))
        
        # --- 2. Action Buttons & Tabs ---
        bar_y = top_rect.bottom + 20
        
        self.btn_tab_matches = pygame.Rect(self.rect.x + 20, bar_y, 140, 35)
        col_m = THEME["accent"] if self.tab == "matches" else (220, 220, 220)
        pygame.draw.rect(screen, col_m, self.btn_tab_matches, border_radius=6)
        t = fm.render("Matches", True, (255,255,255) if self.tab=="matches" else (0,0,0))
        screen.blit(t, (self.btn_tab_matches.centerx - t.get_width()//2, self.btn_tab_matches.centery - t.get_height()//2))

        self.btn_tab_practice = pygame.Rect(self.rect.x + 170, bar_y, 140, 35)
        col_p = THEME["accent"] if self.tab == "practice" else (220, 220, 220)
        pygame.draw.rect(screen, col_p, self.btn_tab_practice, border_radius=6)
        t = fm.render("Practice", True, (255,255,255) if self.tab=="practice" else (0,0,0))
        screen.blit(t, (self.btn_tab_practice.centerx - t.get_width()//2, self.btn_tab_practice.centery - t.get_height()//2))
        
        if self.tab == "matches":
            self.btn_sort = pygame.Rect(self.rect.x + 330, bar_y, 150, 35)
            pygame.draw.rect(screen, (240, 240, 245), self.btn_sort, border_radius=6)
            pygame.draw.rect(screen, (200, 200, 200), self.btn_sort, 1, border_radius=6)
            sort_txt = "Sort: Accuracy" if self.sort_by_acc else "Sort: Date"
            screen.blit(self.parent.font_s.render(sort_txt, True, (40, 40, 40)), (self.btn_sort.x + 20, self.btn_sort.y + 10))
            
            self.btn_import = pygame.Rect(self.rect.right - 180, bar_y, 160, 35)
            pygame.draw.rect(screen, (60, 160, 220), self.btn_import, border_radius=6)
            screen.blit(self.parent.font_s.render("+ Import Games", True, (255, 255, 255)), (self.btn_import.x + 30, self.btn_import.y + 10))
        else:
            self.btn_sort = None
            self.btn_import = None

        # Live Progress Tracker for Smart Import
        if hasattr(self.parent, 'import_status') and self.parent.import_status:
            status_surf = fm.render(self.parent.import_status, True, (200, 100, 20))
            if self.btn_import:
                try: sx = self.btn_import.x - 12 - status_surf.get_width()
                except Exception: sx = self.rect.x + 30
            else:
                sx = self.rect.x + 330
            sy = bar_y + (35 - status_surf.get_height()) // 2
            screen.blit(status_surf, (sx, sy))

        # --- 3. Match / Practice History List ---
        list_rect = pygame.Rect(self.rect.x + 20, bar_y + 45, self.rect.width - 40, self.rect.height - (bar_y + 45 - self.rect.y) - 20)
        pygame.draw.rect(screen, (255, 255, 255), list_rect, border_radius=8)
        screen.set_clip(list_rect)
        
        y_off = list_rect.y - self.scroll
        self.click_zones = []
        
        if self.tab == "matches":
            display_list = sorted(self.ledger, key=lambda x: x.get("accuracy", 0), reverse=True) if self.sort_by_acc else reversed(self.ledger)
            
            for game in display_list:
                if y_off + 60 < list_rect.y: y_off += 60; continue
                if y_off > list_rect.bottom: break
                
                row = pygame.Rect(list_rect.x, y_off, list_rect.width, 60)
                if row.collidepoint(pygame.mouse.get_pos()): pygame.draw.rect(screen, (245, 248, 255), row)
                pygame.draw.line(screen, (230, 230, 230), (row.x, row.bottom), (row.right, row.bottom))
                
                main_icon = self.parent.assets.icons.get('main_pgn_icon')
                if not main_icon:
                    try:
                        p = os.path.join('assets', 'icons', 'main.png')
                        if os.path.exists(p):
                            img = pygame.image.load(p).convert_alpha()
                            img = pygame.transform.smoothscale(img, (36, 36))
                            self.parent.assets.icons['main_pgn_icon'] = img
                            main_icon = img
                    except Exception:
                        main_icon = None

                text_x = row.x + 15
                if main_icon:
                    icon_y = row.y + (row.height - main_icon.get_height()) // 2
                    screen.blit(main_icon, (row.x + 15, icon_y))
                    text_x += main_icon.get_width() + 12

                my_color = "White" if game.get("user_color") == "white" else "Black"
                opp_color = "Black" if my_color == "White" else "White"
                opp_name = game.get('opponent', 'Unknown')
                if len(opp_name) > 12: opp_name = opp_name[:10] + ".."
                
                match_txt = f"Me ({my_color}) vs {opp_name} ({opp_color})"
                screen.blit(fb.render(match_txt, True, (30,30,30)), (text_x, row.y + 10))
                screen.blit(self.parent.font_s.render(game.get('date', ''), True, (120,120,120)), (text_x, row.y + 35))
                
                acc = game.get('accuracy', 0)
                elo = game.get('est_elo', 0)
                elo_c = game.get('elo_change', 0)

                right_x = row.right - 15

                del_w = 30
                del_btn = pygame.Rect(right_x - del_w, row.y + 15, del_w, 30)
                try: pygame.draw.rect(screen, THEME["border"], del_btn, 1, border_radius=4)
                except Exception: pygame.draw.rect(screen, (200,200,200), del_btn, 1, border_radius=4)
                    
                close_icon = self.parent.assets.icons.get('close_btn')
                if not close_icon:
                    try:
                        p = os.path.join('assets', 'icons', 'close_btn.png')
                        if os.path.exists(p):
                            img = pygame.image.load(p).convert_alpha()
                            self.parent.assets.icons['close_btn'] = img
                            close_icon = img
                    except Exception: close_icon = None

                if close_icon:
                    try:
                        icon_s = pygame.transform.smoothscale(close_icon, (del_btn.width - 8, del_btn.height - 8))
                        screen.blit(icon_s, (del_btn.x + 4, del_btn.y + 4))
                    except Exception:
                        del_txt = fb.render("X", True, (255,255,255))
                        screen.blit(del_txt, (del_btn.centerx - del_txt.get_width()//2, del_btn.y + (del_btn.height - del_txt.get_height())//2))
                else:
                    del_txt = fb.render("X", True, (255,255,255))
                    screen.blit(del_txt, (del_btn.centerx - del_txt.get_width()//2, del_btn.y + (del_btn.height - del_txt.get_height())//2))
                right_x = del_btn.x - 10

                load_w, load_h = 60, 30
                load_btn = pygame.Rect(right_x - load_w, row.y + 15, load_w, load_h)
                pygame.draw.rect(screen, (60, 160, 220), load_btn, border_radius=4)
                load_txt = fb.render("Load", True, (255,255,255))
                screen.blit(load_txt, (load_btn.centerx - load_txt.get_width()//2, load_btn.y + (load_h - load_txt.get_height())//2))
                right_x = load_btn.x - 12

                c_str = f"+{elo_c}" if elo_c > 0 else str(elo_c)
                col_elo = (40, 180, 40) if elo_c > 0 else (200, 50, 50)
                elo_surf = fb.render(c_str, True, col_elo)
                elo_x = right_x - elo_surf.get_width()
                screen.blit(elo_surf, (elo_x, row.y + 18))
                right_x = elo_x - 12

                acc_surf = fb.render(f"{acc:.1f}%", True, THEME["accent"])
                left_margin_x = row.x + 15
                mid_x = left_margin_x + (right_x - left_margin_x) // 2
                
                acc_x = (mid_x - acc_surf.get_width() // 2) + 60
                screen.blit(acc_surf, (acc_x, row.y + 18))

                played_surf = fm.render(f"Played Like: {elo}", True, (80,80,80))
                played_x = acc_x + acc_surf.get_width() + 15
                if played_x + played_surf.get_width() < elo_x - 8:
                    screen.blit(played_surf, (played_x, row.y + 18))

                self.click_zones.append({"del": del_btn, "load": load_btn, "id": game.get("id")})
                y_off += 60

        elif self.tab == "practice":
            for prac in reversed(self.practice_ledger):
                # Skip items above the visible area
                if y_off + 60 < list_rect.y: 
                    y_off += 60
                    continue
                
                # STOP drawing if we've reached the bottom of the visible area
                if y_off > list_rect.bottom: 
                    break
                
                row = pygame.Rect(list_rect.x, y_off, list_rect.width, 60)
                if row.collidepoint(pygame.mouse.get_pos()): pygame.draw.rect(screen, (245, 255, 248), row)
                pygame.draw.line(screen, (230, 230, 230), (row.x, row.bottom), (row.right, row.bottom))
                
                p_name = prac.get('name', 'Unknown')
                if len(p_name) > 35: p_name = p_name[:32] + "..."
                p_date = prac.get('date', '')
                p_type = prac.get('type', 'opening').capitalize()
                p_mode = prac.get('mode', 'Practice') # --- NEW: Retrieve the mode ---
                p_color = prac.get('color', 'white').capitalize()
                
                screen.blit(fb.render(f"{p_name}", True, (30,30,30)), (row.x + 20, row.y + 10))
                
                # --- FIX: Inject the mode into the display string ---
                sub_txt = f"Date: {p_date}  |  Type: {p_type} ({p_mode})  |  Played As: {p_color}"
                screen.blit(self.parent.font_s.render(sub_txt, True, (120,120,120)), (row.x + 20, row.y + 35))
                
                btn_w, btn_h = 130, 30
                btn_again = pygame.Rect(row.right - btn_w - 20, row.y + 15, btn_w, btn_h)
                pygame.draw.rect(screen, (40, 180, 80), btn_again, border_radius=6)
                txt_again = fm.render("Practice Again!", True, (255,255,255))
                screen.blit(txt_again, (btn_again.centerx - txt_again.get_width()//2, btn_again.centery - txt_again.get_height()//2))
                
                self.click_zones.append({"again": btn_again, "data": prac})
                y_off += 60
                
        screen.set_clip(None)

        # ── Scrollbar ─────────────────────────────────────────────────────────
        _ms2 = self._max_scroll()
        if _ms2 > 0:
            sb_x = list_rect.right - 6
            sb_h = list_rect.height
            th_h = max(24, int(sb_h*(sb_h/(sb_h+_ms2))))
            th_y = list_rect.y + int((self.scroll/_ms2)*(sb_h-th_h))
            pygame.draw.rect(screen,(212,212,220),pygame.Rect(sb_x,list_rect.y,5,sb_h),border_radius=3)
            pygame.draw.rect(screen,(158,158,178),pygame.Rect(sb_x,th_y,5,th_h),border_radius=3)

        # --- 4. Mini Prompt overlay for Color Selection ---
        if self.pending_import_path:
            ov = pygame.Surface(screen.get_size(), pygame.SRCALPHA); ov.fill((0,0,0,150)); screen.blit(ov, (0,0))
            prompt = pygame.Rect(cx - 150, self.rect.centery - 80, 300, 160)
            pygame.draw.rect(screen, (255, 255, 255), prompt, border_radius=12)
            prompt_title = fb.render("Which side did you play?", True, (0,0,0))
            screen.blit(prompt_title, (prompt.centerx - prompt_title.get_width()//2, prompt.y + 20))

            self.btn_white = pygame.Rect(prompt.x + 20, prompt.y + 80, 120, 45)
            pygame.draw.rect(screen, (240, 240, 240), self.btn_white, border_radius=8)
            pygame.draw.rect(screen, (100, 100, 100), self.btn_white, 1, border_radius=8)
            t = fb.render("White", True, (0,0,0))
            screen.blit(t, (self.btn_white.centerx - t.get_width()//2, self.btn_white.centery - t.get_height()//2))

            self.btn_black = pygame.Rect(prompt.right - 140, prompt.y + 80, 120, 45)
            pygame.draw.rect(screen, (40, 40, 40), self.btn_black, border_radius=8)
            t = fb.render("Black", True, (255,255,255))
            screen.blit(t, (self.btn_black.centerx - t.get_width()//2, self.btn_black.centery - t.get_height()//2))

    def handle_click(self, pos):
        # Handle Mini Prompt
        if self.pending_import_path:
            if self.btn_white.collidepoint(pos):
                self.parent.start_smart_import(self.pending_import_path, "white")
                self.pending_import_path = None
            elif self.btn_black.collidepoint(pos):
                self.parent.start_smart_import(self.pending_import_path, "black")
                self.pending_import_path = None
            return

        if self.close_btn.collidepoint(pos): self.active = False; return
        
        if self.btn_tab_matches and self.btn_tab_matches.collidepoint(pos): self.tab = "matches"; self.scroll = 0; return
        if self.btn_tab_practice and self.btn_tab_practice.collidepoint(pos): self.tab = "practice"; self.scroll = 0; return
        
        if self.btn_sort and self.btn_sort.collidepoint(pos): self.sort_by_acc = not self.sort_by_acc; return
        
        if self.btn_import and self.btn_import.collidepoint(pos):
            # FIX: Iconify fullscreen pygame window so the OS dialog appears on top
            pygame.display.iconify()
            if hasattr(self.parent, 'root') and self.parent.root:
                self.parent.root.deiconify()
                self.parent.root.lift()
                self.parent.root.focus_force()
                self.parent.root.update()
            path = filedialog.askopenfilename(
                title="Select PGN File",
                filetypes=[("PGN Files", "*.pgn")]
            )
            if hasattr(self.parent, 'root') and self.parent.root:
                self.parent.root.withdraw()
            pygame.event.clear()
            if path:
                self.pending_import_path = path
            return

        for zone in self.click_zones:
            if "del" in zone and zone["del"].collidepoint(pos):
                self.parent.delete_archived_game(zone["id"])
                self.ledger = self.parent.match_ledger 
                return
            elif zone.get("load") and zone["load"].collidepoint(pos):
                # Trigger the load in main.py
                self.parent.load_archived_game_to_ui(zone["id"])
                self.active = False
                return
            elif zone.get("again") and zone["again"].collidepoint(pos):
                # Re-launch trainer with this saved config
                from popups import TrainerSideSelectionPopup
                self.parent.active_popup = TrainerSideSelectionPopup(self.parent, zone["data"])
                self.parent.active_popup.active = True
                self.active = False
                return
                
class AnalyzePromptPopup(BasePopup):
    def __init__(self, parent, pgn_path, user_color="white", offset=0):
        # FIX 1: Widened popup from 450 to 520 to fit text comfortably
        super().__init__(parent, 520, 250) 
        self.pgn_path = pgn_path
        self.user_color = user_color
        self.offset = offset
        
    def draw(self, screen, fb, fm):
        self.draw_bg(screen, "Game Already Analyzed!", fb)
        cx, cy = self.rect.centerx, self.rect.centery

        txt = fm.render("This PGN already contains Chess evaluations.", True, (50,50,50))
        screen.blit(txt, (cx - txt.get_width()//2, cy - 35))
        txt2 = fb.render("Do you want to run a Full Deep Analysis again?", True, (20,20,20))
        screen.blit(txt2, (cx - txt2.get_width()//2, cy - 8))

        btn_w, btn_h = 170, 45
        gap = 20
        bx = cx - (btn_w * 2 + gap) // 2

        self.btn_yes = pygame.Rect(bx, cy + 38, btn_w, btn_h)
        pygame.draw.rect(screen, (200, 80, 80), self.btn_yes, border_radius=8)
        t_yes = fb.render("Yes (Deep Scan)", True, (255,255,255))
        screen.blit(t_yes, (self.btn_yes.centerx - t_yes.get_width()//2, self.btn_yes.centery - t_yes.get_height()//2))

        self.btn_no = pygame.Rect(bx + btn_w + gap, cy + 38, btn_w, btn_h)
        pygame.draw.rect(screen, (60, 160, 60), self.btn_no, border_radius=8)
        t_no = fb.render("No (Fast Import)", True, (255,255,255))
        screen.blit(t_no, (self.btn_no.centerx - t_no.get_width()//2, self.btn_no.centery - t_no.get_height()//2))

    def handle_click(self, pos):
        if self.close_btn and self.close_btn.collidepoint(pos): self.active = False; return
        if self.btn_yes.collidepoint(pos):
            # Run Deep Analysis via Engine
            self.parent.load_pgn_file(self.pgn_path, self.offset) 
            self.parent.handle_ui("review") # Automatically trigger Review Popup
            self.active = False
        elif self.btn_no.collidepoint(pos):
            self.parent.fast_load_pgn_to_ui(self.pgn_path, self.offset)
            self.active = False
            
# =============================================================================
#  FAST IMPORT LOADING POPUP
# =============================================================================
class FastImportLoadingPopup(BasePopup):
    def __init__(self, parent):
        super().__init__(parent, 450, 150) # Made slightly wider to fit new text
        self.progress = 0
        self.status_text = "Fast Importing Game..." # NEW: Dynamic status
        self.close_btn = None 
        
    def draw(self, screen, fb, fm):
        self.update_rect()
        ov = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 150))
        screen.blit(ov, (0, 0))
        
        pygame.draw.rect(screen, (250, 250, 252), self.rect, border_radius=12)
        pygame.draw.rect(screen, (200, 200, 200), self.rect, 2, border_radius=12)
        
        # --- NEW: Draw the dynamic status text ---
        title = fb.render(self.status_text, True, (40, 40, 40))
        screen.blit(title, (self.rect.centerx - title.get_width()//2, self.rect.y + 20))
        
        # --- Green Progress Bar ---
        bar_w = 350
        bar_h = 25
        bar_x = self.rect.centerx - bar_w//2
        bar_y = self.rect.y + 70
        
        pygame.draw.rect(screen, (220, 220, 220), (bar_x, bar_y, bar_w, bar_h), border_radius=12)
        
        fill_w = int((self.progress / 100.0) * bar_w)
        if fill_w > 0:
            pygame.draw.rect(screen, (60, 200, 60), (bar_x, bar_y, fill_w, bar_h), border_radius=12)
        
        pct_txt = fm.render(f"{self.progress}%", True, (60, 60, 60))
        screen.blit(pct_txt, (self.rect.centerx - pct_txt.get_width()//2, bar_y + bar_h + 10))

    def handle_click(self, pos): pass
    def handle_input(self, e): pass
    def handle_scroll(self, e): pass
    
# =============================================================================
#  UNSAVED ANALYSIS POPUP
# =============================================================================
class UnsavedAnalysisPopup(BasePopup):
    def __init__(self, parent):
        super().__init__(parent, 550, 250) 

    def draw(self, screen, fb, fm):
        self.draw_bg(screen, "Unsaved Game", fb)
        cx, cy = self.rect.centerx, self.rect.centery
        
        txt = fm.render("There is a game in progress. Save to PGN?", True, (50,50,50))
        screen.blit(txt, (cx - txt.get_width()//2, cy - 30))
        txt2 = self.parent.font_s.render("(Saves the moves and any analysis to a file)", True, (100,100,100))
        screen.blit(txt2, (cx - txt2.get_width()//2, cy - 5))
        
        btn_w, btn_h = 110, 45
        gap = 15
        bx = cx - (btn_w * 3 + gap * 2) // 2

        self.btn_save = pygame.Rect(bx, cy + 38, btn_w, btn_h)
        pygame.draw.rect(screen, (60, 180, 60), self.btn_save, border_radius=8)
        t = fb.render("Save", True, (255,255,255))
        screen.blit(t, (self.btn_save.centerx - t.get_width()//2, self.btn_save.centery - t.get_height()//2))

        self.btn_save_as = pygame.Rect(bx + btn_w + gap, cy + 38, btn_w, btn_h)
        pygame.draw.rect(screen, (40, 140, 200), self.btn_save_as, border_radius=8)
        t = fb.render("Save As...", True, (255,255,255))
        screen.blit(t, (self.btn_save_as.centerx - t.get_width()//2, self.btn_save_as.centery - t.get_height()//2))

        self.btn_discard = pygame.Rect(bx + (btn_w + gap) * 2, cy + 38, btn_w, btn_h)
        pygame.draw.rect(screen, (200, 60, 60), self.btn_discard, border_radius=8)
        t = fb.render("Discard", True, (255,255,255))
        screen.blit(t, (self.btn_discard.centerx - t.get_width()//2, self.btn_discard.centery - t.get_height()//2))

    def handle_click(self, pos):
        if self.close_btn and self.close_btn.collidepoint(pos): self.active = False; return
        
        if self.btn_save.collidepoint(pos):
            path = getattr(self.parent, 'current_pgn_path', None)
            import os
            if path and os.path.exists(path):
                self._save_to_path(path)
            else:
                self._save_as() 
                
        elif self.btn_save_as.collidepoint(pos):
            self._save_as()
            
        elif self.btn_discard.collidepoint(pos):
            self.parent.unsaved_analysis = False
            self.parent.history = [] # Clear history so it bypasses checks
            self.execute_pending()
            self.active = False

    def _save_to_path(self, filename):
        try:
            headers = {"White": "White", "Black": "Black"}
            if self.parent.mode_idx == 1:
                headers["White"] = "Player" if self.parent.playing_white else self.parent.active_bot["name"]
                headers["Black"] = self.parent.active_bot["name"] if self.parent.playing_white else "Player"
            pgn_str = self.parent.logic.export_pgn(headers["White"], headers["Black"], headers)
            with open(filename, "w", encoding="utf-8") as f: f.write(pgn_str)
            
            self.parent.unsaved_analysis = False
            self.parent.history = []
            self.execute_pending()
        except Exception as e: print(e)
        self.active = False

    def _save_as(self):
        try:
            from tkinter import filedialog
            # FIX: Iconify fullscreen pygame window so the OS dialog appears on top
            pygame.display.iconify()
            if hasattr(self.parent, 'root') and self.parent.root:
                self.parent.root.deiconify()
                self.parent.root.lift()
                self.parent.root.focus_force()
                self.parent.root.update()
            filename = filedialog.asksaveasfilename(
                defaultextension=".pgn",
                filetypes=[("PGN", "*.pgn")]
            )
            if hasattr(self.parent, 'root') and self.parent.root:
                self.parent.root.withdraw()
            pygame.event.clear()
            if filename:
                self._save_to_path(filename)
            else:
                self.active = False
        except Exception as e:
            print(f"Save Dialog Error: {e}")
            self.active = False
            
    def execute_pending(self):
        act = getattr(self.parent, "pending_action", None)
        if act == "quit": 
            self.parent.running = False
            self.parent.save_config()
            import sys
            pygame.quit()
            sys.exit()
        elif act == "reset": 
            self.parent.reset_game()
            
# =============================================================================
#  LOAD GAME POPUP (Rich Text Editor Edition)
# =============================================================================
class LoadGamePopup(BasePopup):
    def __init__(self, parent):
        super().__init__(parent, 800, 600)
        self.pgn_text = ""
        self.fen_text = ""
        self.attached_file = None
        self.attached_filename = ""
        self.active_box = None
        self.cursor_timer = 0
        
        self.scroll_pgn = 0
        self.scroll_fen = 0
        
        # New text selection architecture
        self.cursor = {"pgn": 0, "fen": 0}
        self.sel_start = {"pgn": None, "fen": None}
        self.dragging = None

        cx = self.rect.centerx
        self.rect_pgn = pygame.Rect(self.rect.x + 30, self.rect.y + 110, 350, 280)
        self.rect_fen = pygame.Rect(cx + 20, self.rect.y + 110, 350, 280)
        
        self.btn_file = pygame.Rect(cx - 120, self.rect.y + 420, 240, 50)
        self.btn_load = pygame.Rect(self.rect.right - 160, self.rect.bottom - 75, 130, 50)
        self.btn_clear_file = None

    def get_state(self):
        if self.attached_file: return "file"
        if self.pgn_text.strip(): return "pgn"
        if self.fen_text.strip(): return "fen"
        return "empty"

    def draw(self, screen, fb, fm):
        # 1. Beautiful Rich UI Overrides
        self.update_rect()
        ov = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 160))
        screen.blit(ov, (0, 0))
        
        # Soft white body
        pygame.draw.rect(screen, (248, 250, 252), self.rect, border_radius=12)
        pygame.draw.rect(screen, THEME["accent"], self.rect, 2, border_radius=12)
        
        # Rich Gradient/Solid Header
        header = pygame.Rect(self.rect.x, self.rect.y, self.rect.width, 70)
        pygame.draw.rect(screen, THEME["accent"], header, border_top_left_radius=10, border_top_right_radius=10)
        screen.blit(fb.render("Import Chess Game", True, (255, 255, 255)), (header.x + 30, header.y + 22))
        
        # Close Button
        self.close_btn = pygame.Rect(self.rect.x + self.w - 100, self.rect.y + 10, 80, 30)
        pygame.draw.rect(screen, (200, 100, 100), self.close_btn, border_radius=5)
        close_text = self.parent.font_s.render("Close", True, (255, 255, 255))
        screen.blit(close_text, (self.close_btn.x + 20, self.close_btn.y + 5))

        state = self.get_state()

        # 2. Render PGN Box
        pgn_act = (state in ["empty", "pgn"]) and not self.attached_file
        pgn_bg = (255, 255, 255) if pgn_act else (235, 235, 235)
        screen.blit(fb.render("Paste PGN here:", True, (50,50,50) if pgn_act else (150,150,150)), (self.rect_pgn.x, self.rect_pgn.y - 30))
        pygame.draw.rect(screen, pgn_bg, self.rect_pgn, border_radius=8)
        b_pgn = THEME["accent"] if self.active_box == "pgn" else (200, 200, 200)
        pygame.draw.rect(screen, b_pgn, self.rect_pgn, 2, border_radius=8)
        
        # 3. Render FEN Box
        fen_act = (state in ["empty", "fen"]) and not self.attached_file
        fen_bg = (255, 255, 255) if fen_act else (235, 235, 235)
        screen.blit(fb.render("Paste FEN here:", True, (50,50,50) if fen_act else (150,150,150)), (self.rect_fen.x, self.rect_fen.y - 30))
        pygame.draw.rect(screen, fen_bg, self.rect_fen, border_radius=8)
        b_fen = THEME["accent"] if self.active_box == "fen" else (200, 200, 200)
        pygame.draw.rect(screen, b_fen, self.rect_fen, 2, border_radius=8)

        font_m = self.parent.font_mono
        self.draw_text_box(screen, self.rect_pgn, self.pgn_text, self.scroll_pgn, self.active_box == "pgn" and pgn_act, font_m, "pgn")
        self.draw_text_box(screen, self.rect_fen, self.fen_text, self.scroll_fen, self.active_box == "fen" and fen_act, font_m, "fen")

        # 4. Rich Select File Button
        f_col = (235, 245, 255) if self.btn_file.collidepoint(pygame.mouse.get_pos()) else (255, 255, 255)
        pygame.draw.rect(screen, f_col, self.btn_file, border_radius=10)
        pygame.draw.rect(screen, THEME["accent"], self.btn_file, 2, border_radius=10)
        
        f_txt = fm.render("Select Local File", True, THEME["accent"])
        ic = self.parent.assets.icons.get("pgnload")
        
        if ic:
            ic_s = pygame.transform.smoothscale(ic, (26, 26))
            tot = ic_s.get_width() + 12 + f_txt.get_width()
            sx = self.btn_file.centerx - tot // 2
            screen.blit(ic_s, (sx, self.btn_file.centery - 13))
            screen.blit(f_txt, (sx + 38, self.btn_file.centery - f_txt.get_height()//2))
        else:
            screen.blit(f_txt, (self.btn_file.centerx - f_txt.get_width()//2, self.btn_file.centery - f_txt.get_height()//2))

        if self.attached_file:
            # --- DYNAMIC FILENAME TRUNCATION ---
            max_text_w = self.rect.width - 110  # Max width for text (leaves room for X button)
            display_text = f"Attached {self.attached_filename}"
            itx = fm.render(display_text, True, (20, 140, 40))
            
            # Shrink the filename character by character until it fits perfectly
            if itx.get_width() > max_text_w:
                truncated = self.attached_filename
                while itx.get_width() > max_text_w and len(truncated) > 1:
                    truncated = truncated[:-1]
                    display_text = f"File Attached! {truncated}..."
                    itx = fm.render(display_text, True, (20, 140, 40))
            
            text_x = self.rect.x + 30
            text_y = self.rect.bottom - 100  # Pushed up slightly to fit the centered Load button
            screen.blit(itx, (text_x, text_y))
            
            # Clear [X] Button dynamically positioned right after the text
            self.btn_clear_file = pygame.Rect(text_x + itx.get_width() + 15, text_y - 2, 25, 25)
            pygame.draw.rect(screen, (255, 100, 100), self.btn_clear_file, border_radius=4)
            cx_txt = fb.render("X", True, (255, 255, 255))
            screen.blit(cx_txt, (self.btn_clear_file.centerx - cx_txt.get_width()//2, self.btn_clear_file.centery - cx_txt.get_height()//2))
        else:
            self.btn_clear_file = None

        # 5. Load Button (Centered at Bottom)
        btn_w, btn_h = 240, 50
        self.btn_load = pygame.Rect(self.rect.centerx - btn_w // 2, self.rect.bottom - 65, btn_w, btn_h)

        if state != "empty":
            load_col = (40, 200, 80) if self.btn_load.collidepoint(pygame.mouse.get_pos()) else (50, 180, 70)
            pygame.draw.rect(screen, load_col, self.btn_load, border_radius=10)
            ld_txt = fb.render("Load Game", True, (255, 255, 255))
        else:
            pygame.draw.rect(screen, (210, 215, 220), self.btn_load, border_radius=10)
            ld_txt = fb.render("Load Game", True, (150, 160, 170))
            
        screen.blit(ld_txt, (self.btn_load.centerx - ld_txt.get_width()//2, self.btn_load.centery - ld_txt.get_height()//2))
        self.cursor_timer += 1

    # --- TEXT EDITOR LOGIC (Selection, Wrapping, Cursors) ---
    def wrap_text_mono(self, text, max_w, char_w):
        max_chars = max(1, max_w // char_w)
        lines, curr_line, line_start = [], "", 0
        for i, c in enumerate(text):
            if c == '\n':
                curr_line += c
                lines.append((curr_line, line_start))
                curr_line, line_start = "", i + 1
            else:
                curr_line += c
                if len(curr_line) == max_chars:
                    lines.append((curr_line, line_start))
                    curr_line, line_start = "", i + 1
        if curr_line or not lines: lines.append((curr_line, line_start))
        return lines

    def draw_text_box(self, screen, rect, text, scroll, is_active, font, box_type):
        char_w, char_h = font.size("A")
        clip = pygame.Rect(rect.x + 10, rect.y + 10, rect.width - 20, rect.height - 20)
        screen.set_clip(clip)
        
        lines = self.wrap_text_mono(text, clip.width, char_w)
        y = clip.y - scroll
        cursor = self.cursor[box_type]
        sel_start = self.sel_start[box_type]
        
        s1, s2 = None, None
        if sel_start is not None and sel_start != cursor:
            s1, s2 = min(sel_start, cursor), max(sel_start, cursor)
            
        for i, (line_str, start_idx) in enumerate(lines):
            line_len = len(line_str)
            
            # Draw Highlight Selection
            if s1 is not None:
                os_start, os_end = max(start_idx, s1), min(start_idx + line_len, s2)
                if os_start < os_end:
                    hx = clip.x + (os_start - start_idx) * char_w
                    hw = (os_end - os_start) * char_w
                    pygame.draw.rect(screen, (170, 215, 255), (hx, y, hw, char_h))
                    
            if y + char_h > clip.y and y < clip.bottom:
                if line_str:
                    s = font.render(line_str.replace('\n', ''), True, (40, 40, 40))
                    screen.blit(s, (clip.x, y))
                
                # Draw Blinking Cursor
                if is_active and s1 is None and start_idx <= cursor <= start_idx + line_len:
                    if cursor == start_idx + line_len and i < len(lines) - 1: pass 
                    else:
                        cx = clip.x + (cursor - start_idx) * char_w
                        if (self.cursor_timer // 60) % 2 == 0:
                            pygame.draw.line(screen, THEME["accent"], (cx, y+2), (cx, y+char_h-2), 2)
            y += char_h
        screen.set_clip(None)

    def get_char_idx(self, bt, pos):
        rect = self.rect_pgn if bt == "pgn" else self.rect_fen
        text = self.pgn_text if bt == "pgn" else self.fen_text
        scroll = self.scroll_pgn if bt == "pgn" else self.scroll_fen
        
        font = self.parent.font_mono
        char_w, char_h = font.size("A")
        clip = pygame.Rect(rect.x + 10, rect.y + 10, rect.width - 20, rect.height - 20)
        
        lines = self.wrap_text_mono(text, clip.width, char_w)
        
        line_idx = int((pos[1] - clip.y + scroll) // char_h)
        line_idx = max(0, min(line_idx, len(lines) - 1))
        line_str, start_idx = lines[line_idx]
        
        col_idx = int(round((pos[0] - clip.x) / char_w))
        col_idx = max(0, min(col_idx, len(line_str)))
        
        if col_idx == len(line_str) and line_str.endswith('\n'):
            col_idx = max(0, col_idx - 1)
            
        return start_idx + col_idx

    def autoscroll(self, bt):
        rect = self.rect_pgn if bt == "pgn" else self.rect_fen
        text = self.pgn_text if bt == "pgn" else self.fen_text
        cursor = self.cursor[bt]
        font = self.parent.font_mono
        char_w, char_h = font.size("A")
        clip = pygame.Rect(rect.x + 10, rect.y + 10, rect.width - 20, rect.height - 20)
        
        lines = self.wrap_text_mono(text, clip.width, char_w)
        c_line = 0
        for i, (line_str, start_idx) in enumerate(lines):
            if start_idx <= cursor <= start_idx + len(line_str):
                if cursor == start_idx + len(line_str) and i < len(lines) - 1: continue
                c_line = i
                break
                
        cy = c_line * char_h
        if bt == "pgn":
            if cy < self.scroll_pgn: self.scroll_pgn = cy
            elif cy + char_h > self.scroll_pgn + clip.height: self.scroll_pgn = cy + char_h - clip.height
        else:
            if cy < self.scroll_fen: self.scroll_fen = cy
            elif cy + char_h > self.scroll_fen + clip.height: self.scroll_fen = cy + char_h - clip.height

    def delete_selection(self, bt):
        if self.sel_start[bt] is not None and self.sel_start[bt] != self.cursor[bt]:
            s1, s2 = min(self.sel_start[bt], self.cursor[bt]), max(self.sel_start[bt], self.cursor[bt])
            if bt == "pgn": self.pgn_text = self.pgn_text[:s1] + self.pgn_text[s2:]
            else: self.fen_text = self.fen_text[:s1] + self.fen_text[s2:]
            self.cursor[bt] = s1
            self.sel_start[bt] = None
            return True
        return False

    def handle_input(self, e):
        # 1. Handle Mouse Dragging (Selection)
        if e.type == pygame.MOUSEMOTION:
            if self.dragging and pygame.mouse.get_pressed()[0]:
                self.cursor[self.dragging] = self.get_char_idx(self.dragging, e.pos)
                self.autoscroll(self.dragging)
                
        elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            if self.dragging:
                if self.sel_start[self.dragging] == self.cursor[self.dragging]:
                    self.sel_start[self.dragging] = None
                self.dragging = None

        # 2. Handle Typing / Keyboards
        if not self.active_box: return
        bt = self.active_box
        text = self.pgn_text if bt == "pgn" else self.fen_text
        
        if e.type == pygame.KEYDOWN:
            if e.mod & pygame.KMOD_CTRL and e.key == pygame.K_a:
                self.sel_start[bt], self.cursor[bt] = 0, len(text)
                return
            if e.mod & pygame.KMOD_CTRL and e.key == pygame.K_c:
                if self.sel_start[bt] is not None:
                    s1, s2 = min(self.sel_start[bt], self.cursor[bt]), max(self.sel_start[bt], self.cursor[bt])
                    self.parent.root.clipboard_clear()
                    self.parent.root.clipboard_append(text[s1:s2])
                return
            if e.mod & pygame.KMOD_CTRL and e.key == pygame.K_v:
                try:
                    pasted = self.parent.root.clipboard_get()
                    self.delete_selection(bt)
                    if bt == "pgn": self.pgn_text = self.pgn_text[:self.cursor[bt]] + pasted + self.pgn_text[self.cursor[bt]:]
                    else: self.fen_text = self.fen_text[:self.cursor[bt]] + pasted + self.fen_text[self.cursor[bt]:]
                    self.cursor[bt] += len(pasted)
                    self.autoscroll(bt)
                except: pass
                return
                
            if e.key == pygame.K_BACKSPACE:
                if not self.delete_selection(bt) and self.cursor[bt] > 0:
                    if bt == "pgn": self.pgn_text = self.pgn_text[:self.cursor[bt]-1] + self.pgn_text[self.cursor[bt]:]
                    else: self.fen_text = self.fen_text[:self.cursor[bt]-1] + self.fen_text[self.cursor[bt]:]
                    self.cursor[bt] -= 1
            elif e.key == pygame.K_DELETE:
                if not self.delete_selection(bt) and self.cursor[bt] < len(text):
                    if bt == "pgn": self.pgn_text = self.pgn_text[:self.cursor[bt]] + self.pgn_text[self.cursor[bt]+1:]
                    else: self.fen_text = self.fen_text[:self.cursor[bt]] + self.fen_text[self.cursor[bt]+1:]
            elif e.key == pygame.K_LEFT:
                self.sel_start[bt] = None if not e.mod & pygame.KMOD_SHIFT else (self.sel_start[bt] if self.sel_start[bt] is not None else self.cursor[bt])
                if self.cursor[bt] > 0: self.cursor[bt] -= 1
            elif e.key == pygame.K_RIGHT:
                self.sel_start[bt] = None if not e.mod & pygame.KMOD_SHIFT else (self.sel_start[bt] if self.sel_start[bt] is not None else self.cursor[bt])
                if self.cursor[bt] < len(text): self.cursor[bt] += 1
            elif e.key == pygame.K_RETURN:
                if bt == "pgn":
                    self.delete_selection(bt)
                    self.pgn_text = self.pgn_text[:self.cursor[bt]] + "\n" + self.pgn_text[self.cursor[bt]:]
                    self.cursor[bt] += 1
            else:
                if e.unicode and ord(e.unicode) >= 32:
                    self.delete_selection(bt)
                    if bt == "pgn": self.pgn_text = self.pgn_text[:self.cursor[bt]] + e.unicode + self.pgn_text[self.cursor[bt]:]
                    else: self.fen_text = self.fen_text[:self.cursor[bt]] + e.unicode + self.fen_text[self.cursor[bt]:]
                    self.cursor[bt] += 1
            self.autoscroll(bt)

    def handle_scroll(self, e):
        mx, my = e.pos if hasattr(e, 'pos') else pygame.mouse.get_pos()
        if self.active_box == "pgn" or self.rect_pgn.collidepoint((mx, my)):
            if e.button == 4: self.scroll_pgn = max(0, self.scroll_pgn - 30)
            elif e.button == 5: self.scroll_pgn += 30
        elif self.active_box == "fen" or self.rect_fen.collidepoint((mx, my)):
            if e.button == 4: self.scroll_fen = max(0, self.scroll_fen - 30)
            elif e.button == 5: self.scroll_fen += 30

    def handle_click(self, pos):
        if self.close_btn.collidepoint(pos): self.active = False; return
        state = self.get_state()

        if self.btn_clear_file and self.btn_clear_file.collidepoint(pos):
            self.attached_file, self.attached_filename = None, ""
            return

        if not self.attached_file:
            if self.rect_pgn.collidepoint(pos):
                if state in ["empty", "pgn"]:
                    self.active_box = "pgn"
                    self.cursor["pgn"] = self.sel_start["pgn"] = self.get_char_idx("pgn", pos)
                    self.dragging = "pgn"
            elif self.rect_fen.collidepoint(pos):
                if state in ["empty", "fen"]:
                    self.active_box = "fen"
                    self.cursor["fen"] = self.sel_start["fen"] = self.get_char_idx("fen", pos)
                    self.dragging = "fen"
            else:
                self.active_box = None

        if self.btn_file.collidepoint(pos):
            from tkinter import filedialog
            # FIX: Iconify fullscreen pygame window so the OS dialog appears on top
            pygame.display.iconify()
            if hasattr(self.parent, 'root') and self.parent.root:
                self.parent.root.deiconify()
                self.parent.root.lift()
                self.parent.root.focus_force()
                self.parent.root.update()
            path = filedialog.askopenfilename(
                title="Select Chess File",
                filetypes=[("Chess Files", "*.pgn;*.fen"), ("PGN", "*.pgn"), ("FEN", "*.fen")]
            )
            if hasattr(self.parent, 'root') and self.parent.root:
                self.parent.root.withdraw()
            pygame.event.clear()  # discard queued events that piled up while dialog was open
            if path:
                self.attached_file, self.attached_filename = path, os.path.basename(path)
                self.pgn_text, self.fen_text, self.active_box = "", "", None
            return

        if self.btn_load.collidepoint(pos) and state != "empty":
            if state == "file":
                if self.attached_file.lower().endswith(".fen"):
                    try:
                        with open(self.attached_file, "r") as f: fen = f.read().strip()
                        self._load_fen(fen)
                    except: pass
                else:
                    self.parent.side_popup = PGNSelectionPopup(self.parent, self.attached_file)
                    self.parent.side_popup.active = True
                self.active = False
            elif state == "pgn":
                import io
                try:
                    game = chess.pgn.read_game(io.StringIO(self.pgn_text))
                    if game:
                        self.parent.trigger_auto_analysis(game)
                        self.active = False
                    else:
                        from tkinter import messagebox
                        messagebox.showerror("Import Error", "Could not parse PGN. Please check the text and try again.")
                except Exception as e: print(e)
                self.active = False
            elif state == "fen":
                self._load_fen(self.fen_text.strip())
                self.active = False

    def _load_fen(self, fen):
        try:
            self.parent.handle_ui("reset_internal")
            if self.parent.logic:
                self.parent.logic.load_fen(fen)
                self.parent.board = self.parent.logic.board
            else: self.parent.board.set_fen(fen)
            self.parent.view_ply = self.parent.board.ply()
            self.parent.history = []
            self.parent.update_opening_label()
            
            # --- FIX: Switch to Manual Mode so the bot doesn't auto-play FENs ---
            self.parent.mode = "manual"
            self.parent.mode_idx = 0
            self.parent.active_bot = None
            # --------------------------------------------------------------------
            
            self.parent.status_msg = "FEN Loaded (Manual Mode)"
            self.parent.sound_manager.play("game_start")
        except: pass
        
# =============================================================================
#  POSITION COMPLEXITY POPUP  (H key)
# =============================================================================
class ComplexityPopup:
    """Live position complexity & context overlay.
    Shows complexity bars, SEE-based hanging/loose piece tiers,
    positional pressure context, and a miss-opportunity alert.
    Toggle with H key; close with the × button or press H again."""

    def __init__(self, parent):
        self.parent     = parent
        self.active     = True
        w, h            = 420, 590
        self.rect       = pygame.Rect(parent.width - w - 18,
                                      getattr(parent, 'bd_y', 80), w, h)
        self.close_btn  = None
        self._last_fen  = None
        self._cache     = None
        self._font_big  = None   # cached to avoid per-frame font creation

    # ------------------------------------------------------------------
    def _big_font(self):
        """Return the 40-pt bold font, creating it once and caching it."""
        if self._font_big is None:
            self._font_big = pygame.font.SysFont("Segoe UI", 40, bold=True)
        return self._font_big

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    def _compute(self):
        """Compute complexity data with SEE-based hanging/loose tiers and analyzer context."""
        try:
            vp   = getattr(self.parent, 'view_ply', 0)
            hist = getattr(self.parent, 'history', [])
            board = chess.Board()
            for i in range(min(vp, len(hist))):
                if isinstance(hist[i], dict) and "move" in hist[i]:
                    board.push(hist[i]["move"])

            fen = board.fen()
            if fen == self._last_fen and self._cache is not None:
                return self._cache
            self._last_fen = fen

            legal   = list(board.legal_moves)
            n_legal = len(legal)
            n_caps  = sum(1 for m in legal if board.is_capture(m))
            n_chks  = sum(1 for m in legal if board.gives_check(m))

            # ── SEE-based piece classification (two tiers) ──────────────────
            # Tier 1 — Pure hanging: attacked with zero defenders (completely free)
            # Tier 2 — Loose: defended but SEE-losing (profitable to capture anyway)
            vals = {chess.PAWN: 100, chess.KNIGHT: 310, chess.BISHOP: 325,
                    chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 20000}

            white_hanging, black_hanging = [], []   # pure undefended
            white_loose,   black_loose   = [], []   # SEE-losing but defended

            for sq in chess.SQUARES:
                p = board.piece_at(sq)
                if not p or p.piece_type == chess.KING:
                    continue
                piece_val  = vals.get(p.piece_type, 0)
                attackers  = list(board.attackers(not p.color, sq))
                defenders  = list(board.attackers(p.color,     sq))
                label = chess.piece_symbol(p.piece_type).upper() + chess.square_name(sq)

                if attackers and not defenders:
                    # Tier 1: completely undefended
                    if p.color == chess.WHITE: white_hanging.append(label)
                    else:                       black_hanging.append(label)
                elif attackers and defenders:
                    # Tier 2: check if cheapest attacker beats the piece even after recapture
                    cheapest_attacker = min(
                        vals.get(board.piece_at(s).piece_type, 9999)
                        for s in attackers if board.piece_at(s)
                    )
                    cheapest_defender = min(
                        vals.get(board.piece_at(s).piece_type, 9999)
                        for s in defenders if board.piece_at(s)
                    )
                    # SEE-losing: the piece can be taken profitably even considering recapture
                    if piece_val > cheapest_attacker and piece_val >= cheapest_defender:
                        if p.color == chess.WHITE: white_loose.append(label)
                        else:                       black_loose.append(label)

            hanging = len(white_hanging) + len(black_hanging)
            loose   = len(white_loose)   + len(black_loose)

            # ── Analyzer positional context ─────────────────────────────────
            analyzer = getattr(self.parent, 'analyzer', None)
            ctx = None
            pressure_factor   = 0.0
            pressure_leniency = 1.0

            if analyzer and callable(getattr(analyzer, 'get_position_complexity', None)):
                try:
                    complexity_raw = analyzer.get_position_complexity(board)
                    ctx = analyzer._get_positional_context(board, complexity_raw)
                    pressure_factor   = ctx["pressure_factor"]
                    pressure_leniency = 1.0 + (pressure_factor * 0.25)
                    pcs_left = len(board.piece_map())
                    if pcs_left <= 12:           # endgame
                        pressure_leniency *= 0.85
                except Exception:
                    ctx = None

            # ── Miss-opportunity alert (best move is a winning capture) ──────
            # Mirrors the tactical-miss trigger in _classify_move_logic.
            miss_alert = None
            if analyzer and getattr(analyzer, 'is_active', False):
                try:
                    # Use the cached best move from history if available, else skip
                    hist_entry = hist[vp - 1] if vp > 0 and len(hist) >= vp else None
                    best_move = None
                    if isinstance(hist_entry, dict):
                        rev = hist_entry.get("review", {})
                        # best_move stored as UCI string in some paths
                        bm_uci = rev.get("best_move_uci")
                        if bm_uci:
                            try: best_move = chess.Move.from_uci(bm_uci)
                            except Exception: pass
                    if best_move and analyzer._is_hanging_capture(board, best_move):
                        captured = board.piece_at(best_move.to_square)
                        if captured:
                            piece_name = chess.piece_name(captured.piece_type).capitalize()
                            sq_name    = chess.square_name(best_move.to_square).upper()
                            miss_alert = f"Capturable: {piece_name} on {sq_name}"
                except Exception:
                    miss_alert = None

            # ── Scores ───────────────────────────────────────────────────────
            pcs_left = sum(1 for sq in chess.SQUARES
                           if (p := board.piece_at(sq)) and p.piece_type != chess.PAWN)
            phase = "Opening" if pcs_left >= 12 else ("Middlegame" if pcs_left >= 6 else "Endgame")
            pm    = {"Opening": 0.7, "Middlegame": 1.0, "Endgame": 0.85}[phase]
            mob   = min(100, int(n_legal * 2.5))
            # Tension now weights both fully-hanging AND SEE-loose pieces
            ten   = min(100, int(hanging * 22 + loose * 10 + n_caps * 8))
            tac   = min(100, int(n_chks * 25 + n_caps * 6))
            overall = min(100, int((mob * 0.3 + ten * 0.45 + tac * 0.25) * pm))

            self._cache = {
                "overall": overall, "mobility": mob, "tension": ten, "tactics": tac,
                "phase": phase, "hanging": hanging, "loose": loose,
                "white_hanging": white_hanging, "black_hanging": black_hanging,
                "white_loose":   white_loose,   "black_loose":   black_loose,
                "captures": n_caps, "checks": n_chks, "legal": n_legal,
                "pressure_factor":   round(pressure_factor,   2),
                "pressure_leniency": round(pressure_leniency, 2),
                "miss_alert": miss_alert,
                "ctx": ctx,
            }
            return self._cache
        except Exception:
            return None

    # ------------------------------------------------------------------
    def _bar_descriptions(self, d):
        """Return one-line descriptions for Mobility, Tension, Tactics."""
        eval_val = getattr(self.parent, 'eval_val', 0)
        favors   = ""
        if abs(eval_val) > 150:
            favors = f", favors {'White' if eval_val > 0 else 'Black'}"

        # Pressure modifier hint (only shown when non-trivial)
        pf = d.get("pressure_factor", 0.0)
        pl = d.get("pressure_leniency", 1.0)
        if pl > 1.10:
            leniency_hint = " — errors more forgivable here"
        elif pl < 0.92:
            leniency_hint = " — precision critical"
        else:
            leniency_hint = ""

        mob  = d["mobility"]
        if mob >= 75:
            mob_desc = f"Very active — {d['legal']} moves available{favors}"
        elif mob >= 45:
            mob_desc = f"Moderate piece activity — {d['legal']} moves{favors}{leniency_hint}"
        else:
            mob_desc = f"Restricted — only {d['legal']} legal moves{favors}"

        h    = d["hanging"]
        loose = d.get("loose", 0)
        caps = d["captures"]
        ten  = d["tension"]
        if ten >= 60:
            ten_desc = f"{h} free, {loose} SEE-loose — very sharp{favors}"
        elif h > 0 or loose > 0:
            parts = []
            if h:    parts.append(f"{h} hanging")
            if loose: parts.append(f"{loose} SEE-loose")
            ten_desc = ", ".join(parts) + f", {caps} capture{'s' if caps != 1 else ''}{favors}"
        else:
            ten_desc = f"No loose pieces — calm{favors}"

        chks = d["checks"]
        tac  = d["tactics"]
        if tac >= 60:
            tac_desc = f"{chks} check{'s' if chks != 1 else ''} + {caps} captures — tactical fireworks{leniency_hint}"
        elif tac > 0:
            tac_desc = f"{chks} checking move{'s' if chks != 1 else ''}, {caps} captures — some forcing lines"
        else:
            tac_desc = f"No forcing moves{leniency_hint}"

        return mob_desc, ten_desc, tac_desc

    # ------------------------------------------------------------------
    def draw(self, screen, fb, fm):
        if not self.active:
            return

        fs = self.parent.font_s

        # Panel background
        pygame.draw.rect(screen, (244, 244, 250), self.rect, border_radius=14)
        pygame.draw.rect(screen, (188, 188, 202), self.rect, 2, border_radius=14)

        # ── Title row ──────────────────────────────────────────────────
        title = fb.render("Position Complexity", True, (35, 35, 42))
        screen.blit(title, (self.rect.x + 14, self.rect.y + 13))

        # Close button — far right (Bug B8: placed first so hint can avoid it)
        self.close_btn = pygame.Rect(self.rect.right - 46, self.rect.y + 10, 30, 30)
        close_icon = self.parent.assets.icons.get("close_btn")
        if not close_icon:
            try:
                p = os.path.join('assets', 'icons', 'close_btn.png')
                if os.path.exists(p):
                    img = pygame.image.load(p).convert_alpha()
                    self.parent.assets.icons['close_btn'] = img
                    close_icon = img
            except Exception:
                close_icon = None
        if close_icon:
            if self.close_btn.collidepoint(pygame.mouse.get_pos()):
                pygame.draw.rect(screen, (230, 230, 235), self.close_btn, border_radius=6)
            screen.blit(pygame.transform.smoothscale(close_icon, (self.close_btn.w, self.close_btn.h)),
                        (self.close_btn.x, self.close_btn.y))
        else:
            is_hover = self.close_btn.collidepoint(pygame.mouse.get_pos())
            pygame.draw.rect(screen, (240, 80, 80) if is_hover else (225, 225, 230),
                             self.close_btn, border_radius=8)
            x_surf = fb.render("X", True, (255, 255, 255) if is_hover else (100, 100, 100))
            screen.blit(x_surf, (self.close_btn.centerx - x_surf.get_width() // 2,
                                 self.close_btn.centery - x_surf.get_height() // 2))

        # H-toggle hint — snug to left of close button (Bug B8 fix)
        hint = fs.render("H to toggle", True, (158, 158, 172))
        screen.blit(hint, (self.close_btn.x - hint.get_width() - 8, self.rect.y + 15))

        # Thin separator under the title bar
        pygame.draw.line(screen, (212, 212, 222),
                         (self.rect.x + 10, self.rect.y + 42),
                         (self.rect.right - 10, self.rect.y + 42))

        d = self._compute()
        if not d:
            screen.blit(fm.render("No position loaded.", True, (130, 130, 130)),
                        (self.rect.x + 18, self.rect.y + 60))
            return

        y   = self.rect.y + 52
        pad = 16

        # ── Overall score ───────────────────────────────────────────────
        ov = d["overall"]
        oc = (50, 178, 50) if ov >= 70 else (218, 168, 38) if ov >= 40 else (198, 58, 58)
        big = self._big_font().render(str(ov), True, oc)      # Bug B6 fix: cached font
        screen.blit(big, (self.rect.x + pad, y))

        # "/ 100" vertically aligned to big font's baseline (Bug B7 fix)
        lbl100 = fs.render("/ 100", True, (105, 105, 118))
        screen.blit(lbl100, (self.rect.x + pad + big.get_width() + 8,
                              y + big.get_height() - lbl100.get_height() - 2))

        # Phase pill
        pc = {"Opening": (78, 138, 218),
              "Middlegame": (218, 128, 38),
              "Endgame": (78, 158, 98)}[d["phase"]]
        pr = pygame.Rect(self.rect.right - 118, y + 4, 100, 26)
        pygame.draw.rect(screen, pc, pr, border_radius=12)
        pt = fs.render(d["phase"], True, (255, 255, 255))
        screen.blit(pt, (pr.centerx - pt.get_width() // 2,
                         pr.centery - pt.get_height() // 2))

        y += big.get_height() + 10

        # Separator
        pygame.draw.line(screen, (218, 218, 228),
                         (self.rect.x + pad, y), (self.rect.right - pad, y))
        y += 10

        # ── Sub-bars (label + description + bar) ────────────────────────
        mob_desc, ten_desc, tac_desc = self._bar_descriptions(d)
        bw = self.rect.width - pad * 2
        bar_items = [
            ("Mobility", d["mobility"], (78, 128, 212), mob_desc),
            ("Tension",  d["tension"],  (212, 98, 58),  ten_desc),
            ("Tactics",  d["tactics"],  (158, 68, 198), tac_desc),
        ]
        for lbl, val, col, desc in bar_items:
            # Label + numeric value on same row
            lbl_s = fm.render(lbl, True, (58, 58, 70))
            val_s = fs.render(str(val), True, (82, 82, 92))
            screen.blit(lbl_s, (self.rect.x + pad, y))
            screen.blit(val_s, (self.rect.right - pad - val_s.get_width(), y + 2))
            y += lbl_s.get_height() + 3

            # Description line (Bug B4 fix)
            desc_s = fs.render(desc, True, (118, 118, 140))
            screen.blit(desc_s, (self.rect.x + pad, y))
            y += desc_s.get_height() + 6  # gap between description and bar (Bug B5 fix)

            # Progress bar
            pygame.draw.rect(screen, (215, 215, 222),
                             pygame.Rect(self.rect.x + pad, y, bw, 9), border_radius=4)
            fw = int((val / 100) * bw)
            if fw > 0:
                pygame.draw.rect(screen, col,
                                 pygame.Rect(self.rect.x + pad, y, fw, 9), border_radius=4)
            y += 20   # bar height + breathing room below bar

        # ── Stats row ─────────────────────────────────────────────────────
        pygame.draw.line(screen, (210, 210, 218),
                         (self.rect.x + pad, y), (self.rect.right - pad, y))
        y += 9
        stats = f"Legal: {d['legal']}   Captures: {d['captures']}   Checks: {d['checks']}"
        screen.blit(fs.render(stats, True, (112, 112, 124)), (self.rect.x + pad, y))
        y += fs.get_height() + 10

        # ── Pressure Context (from analyzer._get_positional_context) ──────
        pygame.draw.line(screen, (210, 210, 218),
                         (self.rect.x + pad, y), (self.rect.right - pad, y))
        y += 8
        ctx_title = fm.render("Position Context", True, (58, 58, 70))
        screen.blit(ctx_title, (self.rect.x + pad, y))
        y += ctx_title.get_height() + 4

        pf = d.get("pressure_factor", 0.0)
        pl = d.get("pressure_leniency", 1.0)

        # Pressure factor bar (0.0 – 1.0)
        pf_label = fs.render(f"Pressure  {pf:.2f}", True, (82, 82, 100))
        screen.blit(pf_label, (self.rect.x + pad, y))
        pf_bw = self.rect.width - pad * 2
        pf_barw = int(pf * pf_bw)
        pf_col = (80, 140, 220) if pf < 0.4 else (218, 158, 38) if pf < 0.7 else (210, 70, 70)
        pygame.draw.rect(screen, (215, 215, 222),
                         pygame.Rect(self.rect.x + pad, y + fs.get_height() + 2, pf_bw, 7), border_radius=3)
        if pf_barw > 0:
            pygame.draw.rect(screen, pf_col,
                             pygame.Rect(self.rect.x + pad, y + fs.get_height() + 2, pf_barw, 7), border_radius=3)
        y += fs.get_height() + 14

        # Leniency pill — tells the user exactly how the new engine is adjusting thresholds
        if pl > 1.10:
            pl_text = f"Leniency +{(pl - 1.0) * 100:.0f}%  (sharp — small errors forgiven)"
            pl_col  = (55, 160, 95)
        elif pl < 0.92:
            pl_text = f"Leniency -{(1.0 - pl) * 100:.0f}%  (endgame — precision critical)"
            pl_col  = (200, 80, 60)
        else:
            pl_text = "Leniency neutral  (standard position)"
            pl_col  = (100, 100, 120)
        pl_surf = fs.render(pl_text, True, pl_col)
        screen.blit(pl_surf, (self.rect.x + pad, y))
        y += pl_surf.get_height() + 10

        # ── Miss-opportunity alert ─────────────────────────────────────────
        miss_alert = d.get("miss_alert")
        if miss_alert:
            alert_bg = pygame.Rect(self.rect.x + pad, y,
                                   self.rect.width - pad * 2, fs.get_height() + 10)
            pygame.draw.rect(screen, (255, 244, 220), alert_bg, border_radius=6)
            pygame.draw.rect(screen, (218, 158, 38), alert_bg, 1, border_radius=6)
            alert_surf = fs.render(f"!  {miss_alert} — free material!", True, (140, 90, 20))
            screen.blit(alert_surf, (alert_bg.x + 8, alert_bg.y + 5))
            y += alert_bg.height + 8

        # ── Piece Safety (two-tier: hanging + SEE-loose) ──────────────────
        pygame.draw.line(screen, (210, 210, 218),
                         (self.rect.x + pad, y), (self.rect.right - pad, y))
        y += 8
        hang_title = fm.render("Piece Safety", True, (58, 58, 70))
        screen.blit(hang_title, (self.rect.x + pad, y))
        y += hang_title.get_height() + 4

        wh  = d["white_hanging"]
        bh  = d["black_hanging"]
        wlo = d.get("white_loose", [])
        blo = d.get("black_loose", [])

        if not wh and not bh and not wlo and not blo:
            screen.blit(fs.render("All pieces safe", True, (90, 160, 90)),
                        (self.rect.x + pad, y))
        else:
            # Tier 1 — completely free (red)
            if wh or bh:
                t1_title = fs.render("Free (undefended):", True, (180, 50, 50))
                screen.blit(t1_title, (self.rect.x + pad, y))
                y += t1_title.get_height() + 2
                for color_label, pieces, col in [("W", wh, (60, 80, 200)), ("B", bh, (200, 55, 55))]:
                    if pieces:
                        txt = f"  {color_label}: " + ", ".join(pieces[:6]) + ("…" if len(pieces) > 6 else "")
                        s = fs.render(txt, True, col)
                        screen.blit(s, (self.rect.x + pad, y))
                        y += s.get_height() + 2

            # Tier 2 — SEE-losing but defended (orange)
            if wlo or blo:
                t2_title = fs.render("SEE-loose (profitable capture):", True, (185, 120, 30))
                screen.blit(t2_title, (self.rect.x + pad, y))
                y += t2_title.get_height() + 2
                for color_label, pieces, col in [("W", wlo, (80, 100, 210)), ("B", blo, (210, 100, 50))]:
                    if pieces:
                        txt = f"  {color_label}: " + ", ".join(pieces[:6]) + ("…" if len(pieces) > 6 else "")
                        s = fs.render(txt, True, col)
                        screen.blit(s, (self.rect.x + pad, y))
                        y += s.get_height() + 2

    # ------------------------------------------------------------------
    def handle_click(self, pos):
        if self.close_btn and self.close_btn.collidepoint(pos):
            self.active = False

    def handle_scroll(self, e):
        pass

# =============================================================================
#  ACCOUNT POPUP
# =============================================================================
class AccountPopup(BasePopup):
    def __init__(self, parent):
        super().__init__(parent, 1100, 760)
        self.accounts         = self._load_accounts()
        self.selected_account = self.accounts[0]["username"] if self.accounts else None
        self.sort_key  = "date"
        self.sort_asc  = False
        self.page      = 0
        self.per_page  = 8
        self.scroll_acc= 0
        self.zones     = []
        self.btn_prev  = None
        self.btn_next  = None
        self.btn_add_account = None

    def _load_accounts(self):
        import json, glob
        acc_dir = os.path.join("assets","accounts")
        accs = []
        if not os.path.exists(acc_dir): return accs
        for path in glob.glob(os.path.join(acc_dir,"*.json")):
            try:
                with open(path,"r",encoding="utf-8") as f: data=json.load(f)
                if isinstance(data,dict): accs.append(data)
            except Exception: pass
        return accs

    def _get_account(self):
        for a in self.accounts:
            if a.get("username")==self.selected_account: return a
        return None

    def _games_for(self, acc):
        games = list(acc.get("games", []))
        # Compute rating_change dynamically from chronological order.
        # Use original list index as same-date tiebreaker to preserve API sequence.
        try:
            indexed = [(i, g) for i, g in enumerate(games)]
            chrono = sorted(indexed, key=lambda ig: (ig[1].get("date", ""), ig[0]))
            chrono_games = [g for _, g in chrono]
            for i in range(len(chrono_games)):
                prev_r = chrono_games[i - 1].get("rating") if i > 0 else None
                curr_r = chrono_games[i].get("rating")
                if i == 0 or prev_r is None or curr_r is None:
                    chrono_games[i] = dict(chrono_games[i], rating_change=0)
                else:
                    try:
                        change = int(curr_r) - int(prev_r)
                        # Per-game ELO swings above ±100 are impossible on chess.com/lichess;
                        # clamp them to 0 so broken sequence ordering doesn't produce garbage.
                        if abs(change) > 100:
                            change = 0
                        chrono_games[i] = dict(chrono_games[i], rating_change=change)
                    except (TypeError, ValueError):
                        chrono_games[i] = dict(chrono_games[i], rating_change=0)
            games = chrono_games
        except Exception:
            pass
        k = {"date": "date", "rating": "rating", "result": "result"}.get(self.sort_key, "date")
        try:
            games = sorted(games, key=lambda g: g.get(k, ""), reverse=not self.sort_asc)
        except Exception:
            pass
        return games

    def _delete_account(self, username):
        """Delete an account and its associated files"""
        import glob
        try:
            # Delete account JSON file
            safe = "".join(c for c in username if c.isalnum() or c in "_-")
            acc_file = os.path.join("assets", "accounts", f"{safe}.json")
            if os.path.exists(acc_file):
                os.remove(acc_file)
            
            # Delete associated PGN files
            pgn_files = glob.glob(os.path.join("assets", "downloads", f"*{safe}.pgn"))
            for pgn in pgn_files:
                try:
                    os.remove(pgn)
                except:
                    pass
            
            # Reload accounts list
            self.accounts = self._load_accounts()
            
            # Update selected account
            if self.selected_account == username:
                self.selected_account = self.accounts[0]["username"] if self.accounts else None
            
            self.page = 0
        except Exception as e:
            print(f"Error deleting account: {e}")

    def draw(self, screen, fb, fm):
        self.draw_bg(screen,"My Online Accounts",fb)
        
        # --- FIX: Replace default close button with 'Close' text button ---
        pygame.draw.rect(screen, (252, 252, 254), (self.rect.right - 60, self.rect.y + 8, 55, 45), border_top_right_radius=16)
        self.close_btn = pygame.Rect(self.rect.right - 100, self.rect.y + 10, 80, 30)
        pygame.draw.rect(screen, (200, 100, 100), self.close_btn, border_radius=5)
        close_text = self.parent.font_s.render("Close", True, (255, 255, 255))
        screen.blit(close_text, (self.close_btn.x + 20, self.close_btn.y + 5))
        
        self.zones=[]
        PAD=18; lw=290
        rx=self.rect.x+lw+PAD*2; rw=self.rect.width-lw-PAD*3
        ty=self.rect.y+66; by=self.rect.bottom-20

        # ── Left: account list ────────────────────────────────────────────────
        lr=pygame.Rect(self.rect.x+PAD,ty,lw,by-ty)
        pygame.draw.rect(screen,(248,248,252),lr,border_radius=10)
        pygame.draw.rect(screen,(210,210,220),lr,1,border_radius=10)
        
        # Header with ACCOUNTS label
        header_surf = fm.render("Accounts", True, (60,60,70))
        screen.blit(header_surf, (lr.x+14, lr.y+10))

        # + Add Account button - improved styling
        self.btn_add_account = pygame.Rect(lr.right - 108, lr.y + 8, 100, 24)
        btn_hover = self.btn_add_account.collidepoint(pygame.mouse.get_pos())
        add_col = (55, 135, 225) if btn_hover else (75, 160, 245)
        pygame.draw.rect(screen, add_col, self.btn_add_account, border_radius=6)
        add_txt = self.parent.font_s.render("+ Add", True, (255, 255, 255))
        screen.blit(add_txt, (self.btn_add_account.centerx - add_txt.get_width() // 2,
                               self.btn_add_account.centery - add_txt.get_height() // 2))

        ac=pygame.Rect(lr.x,lr.y+38,lr.width,lr.height-38)
        pygame.draw.rect(screen,(255,255,255),ac,border_radius=8)
        # Clamp scroll: only scroll if content taller than the visible area
        _total_acc_h = len(self.accounts) * 54
        _max_acc_scroll = max(0, _total_acc_h - ac.height)
        self.scroll_acc = max(0, min(self.scroll_acc, _max_acc_scroll))
        screen.set_clip(ac)
        ay=ac.y-self.scroll_acc
        
        for idx, acc in enumerate(self.accounts):
            un=acc.get("username","?"); site=acc.get("site","?")
            row=pygame.Rect(lr.x+3,ay,lr.width-6,50)
            is_sel=(un==self.selected_account)
            
            # Improved row background
            if is_sel:
                bg2=(215,228,255)
                pygame.draw.rect(screen,bg2,row,border_radius=7)
                pygame.draw.rect(screen,(85,135,215),row,2,border_radius=7)
            elif row.collidepoint(pygame.mouse.get_pos()):
                bg2=(235,240,250)
                pygame.draw.rect(screen,bg2,row,border_radius=7)
            else:
                bg2=(255,255,255) if idx % 2 == 0 else (250,251,254)
                pygame.draw.rect(screen,bg2,row,border_radius=7)
            
            # Draw Site Icon with fallback
            site_key = "lichess" if "lichess" in site.lower() else "chess_com"
            icon = self.parent.assets.icons.get(site_key)
            tx = row.x + 12
            
            if icon:
                try:
                    scaled_icon = pygame.transform.smoothscale(icon, (34, 34))
                    screen.blit(scaled_icon, (row.x + 10, row.y + 8))
                    tx = row.x + 52
                except:
                    tx = row.x + 12
            else:
                # Fallback circle with color
                col = (100, 150, 220) if site_key == "lichess" else (100, 180, 100)
                pygame.draw.circle(screen, col, (row.x + 26, row.y + 25), 17)
                tx = row.x + 52
                
            # Username and site
            un_surf = fb.render(un, True, (20,20,30))
            screen.blit(un_surf, (tx, row.y + 6))
            site_surf = self.parent.font_s.render(site, True, (140,140,155))
            screen.blit(site_surf, (tx, row.y + 28))
            
            # Delete button on the right side of row
            del_btn = pygame.Rect(row.right - 36, row.y + 6, 28, 38)
            del_hover = del_btn.collidepoint(pygame.mouse.get_pos())
            del_col = (220, 80, 80) if del_hover else (210, 100, 100)
            pygame.draw.rect(screen, del_col, del_btn, border_radius=5)
            del_txt = self.parent.font_s.render("✕", True, (255, 255, 255))
            screen.blit(del_txt, del_txt.get_rect(center=del_btn.center))
            self.zones.append((del_btn, "delete_acc", un))
            
            self.zones.append((row,"select_acc",un))
            ay+=54
        screen.set_clip(None)

        # ── Right: elo graph + game list ──────────────────────────────────────
        acc=self._get_account()
        if not acc:
            screen.blit(fm.render("No account selected.",True,(140,140,152)),(rx+20,ty+40)); return

        games=self._games_for(acc)
        tp=max(1,(len(games)+self.per_page-1)//self.per_page)
        self.page=max(0,min(self.page,tp-1))

        # Header
        screen.blit(fb.render(f"{acc.get('username','?')}  —  {acc.get('site','?')}",True,(30,30,42)),(rx,ty-22))

        # Elo graph - improved rendering with smooth curves
        gh=160; gr=pygame.Rect(rx,ty,rw,gh)
        pygame.draw.rect(screen,(252,252,254),gr,border_radius=8)
        pygame.draw.rect(screen,(220,220,228),gr,1,border_radius=8)
        
        # Extract ratings and build visualization
        elos=[g.get("rating") for g in games if g.get("rating") is not None and g.get("rating", 0) > 0]
        
        if len(elos) >= 1:
            # Calculate scaling
            if len(elos) == 1:
                mn, mx = elos[0] - 50, elos[0] + 50
            else:
                mn, mx = min(elos), max(elos)
            
            span = max(1, mx - mn)
            
            # Graph area with padding
            ga2 = pygame.Rect(gr.x + 20, gr.y + 28, gr.width - 40, gh - 48)
            
            # Draw background with subtle grid
            pygame.draw.rect(screen, (250, 251, 253), ga2, border_radius=4)
            
            # Draw horizontal grid lines
            grid_lines = 4
            for i in range(grid_lines + 1):
                y_pos = ga2.y + (i * ga2.height // grid_lines)
                alpha = 180 if i == 0 or i == grid_lines else 120
                pygame.draw.line(screen, (235, 235, 240), (ga2.x, y_pos), (ga2.right, y_pos), 1)
            
            # Calculate points
            pts_g = []
            for i, v in enumerate(elos):
                if len(elos) == 1:
                    px = ga2.centerx
                else:
                    px = ga2.x + int(i * ga2.width / max(1, len(elos) - 1))
                py = ga2.bottom - int((v - mn) / span * ga2.height)
                pts_g.append((px, py))
            
            # Draw smooth curve for multiple points using Catmull-Rom spline
            if len(pts_g) >= 2:
                # Helper function for Catmull-Rom interpolation
                def catmull_rom(p0, p1, p2, p3, t):
                    return 0.5 * (
                        2 * p1 +
                        (-p0 + p2) * t +
                        (2*p0 - 5*p1 + 4*p2 - p3) * t*t +
                        (-p0 + 3*p1 - 3*p2 + p3) * t*t*t
                    )
                
                # Build smooth curve with 20 steps per segment for silky rendering
                smooth_pts = [pts_g[0]]
                for i in range(1, len(pts_g)):
                    p0 = pts_g[max(0, i - 2)]
                    p1 = pts_g[i - 1]
                    p2 = pts_g[i]
                    p3 = pts_g[min(len(pts_g) - 1, i + 1)]
                    steps = 20
                    for t_step in range(1, steps + 1):
                        t = t_step / steps
                        x = int(catmull_rom(p0[0], p1[0], p2[0], p3[0], t))
                        y = int(catmull_rom(p0[1], p1[1], p2[1], p3[1], t))
                        # Clamp to graph area to prevent stray artefacts
                        x = max(ga2.x, min(ga2.right, x))
                        y = max(ga2.y, min(ga2.bottom, y))
                        smooth_pts.append((x, y))
                
                # Draw gradient fill under curve (clipped to graph area) — green tint
                if len(smooth_pts) >= 2:
                    fill_pts = smooth_pts + [(ga2.right, ga2.bottom), (smooth_pts[0][0], ga2.bottom)]
                    fill_surf = pygame.Surface((ga2.width, ga2.height), pygame.SRCALPHA)
                    pygame.draw.polygon(fill_surf, (50, 200, 90, 30),
                                        [(p[0] - ga2.x, p[1] - ga2.y) for p in fill_pts])
                    screen.blit(fill_surf, (ga2.x, ga2.y))
                
                # Anti-aliased green curve: wide faint pass then sharp pass (no dots)
                pygame.draw.lines(screen, (40, 180, 80), False, smooth_pts, 4)
                pygame.draw.lines(screen, (50, 200, 90), False, smooth_pts, 2)

            elif len(pts_g) == 1:
                # Single point - draw it prominently
                pt = pts_g[0]
                pygame.draw.circle(screen, (50, 200, 90), pt, 6)
                
                # Draw horizontal reference line
                pygame.draw.line(screen, (220, 220, 225), (ga2.x, pt[1]), (ga2.right, pt[1]), 1)
            
            # Draw axis labels with better positioning
            min_lbl = self.parent.font_s.render(f"{mn}", True, (140, 140, 155))
            max_lbl = self.parent.font_s.render(f"{mx}", True, (140, 140, 155))
            screen.blit(min_lbl, (gr.x + 4, ga2.bottom - 12))
            screen.blit(max_lbl, (gr.x + 4, ga2.y - 4))
            
            # Draw "Rating" label
            rating_lbl = self.parent.font_s.render("Rating", True, (100, 100, 120))
            screen.blit(rating_lbl, (gr.x + 4, gr.y + 4))
            
            # Interactive tooltip with improved hover detection
            mx_m, my_m = pygame.mouse.get_pos()
            show_tooltip = False
            tooltip_idx = None
            
            if len(pts_g) == 1:
                show_tooltip = True
                tooltip_idx = 0
            elif ga2.collidepoint(mx_m, my_m) and pts_g:
                # Find closest point within hover radius
                min_dist = float('inf')
                hover_radius = 15
                for i, pt in enumerate(pts_g):
                    dist = ((pt[0] - mx_m)**2 + (pt[1] - my_m)**2)**0.5
                    if dist < hover_radius and dist < min_dist:
                        min_dist = dist
                        tooltip_idx = i
                        show_tooltip = True
            
            # --- FIX: Tooltip Rendering has been moved to the very bottom of the method! ---
            
        else:
            # No data message
            no_data = fm.render("No games imported yet", True, (150, 150, 160))
            screen.blit(no_data, (gr.centerx - no_data.get_width() // 2, gr.centery - no_data.get_height() // 2))

        # Sort bar
        sy2=ty+gh+10
        sx3=rx
        for lbl_,sk_ in[("Date","date"),("Rating","rating"),("Result","result")]:
            ia_=(self.sort_key==sk_)
            sr_=pygame.Rect(sx3,sy2,88,26)
            sc_=THEME["accent"] if ia_ else (218,218,228)
            pygame.draw.rect(screen,sc_,sr_,border_radius=6)
            sl_=self.parent.font_s.render(lbl_+(" ↑" if ia_ and self.sort_asc else " ↓" if ia_ else ""),
                                           True,(255,255,255) if ia_ else (60,60,72))
            screen.blit(sl_,(sr_.centerx-sl_.get_width()//2,sr_.centery-sl_.get_height()//2))
            self.zones.append((sr_,"sort",sk_)); sx3+=94

        # Game list - improved layout with proper text alignment
        ly2=sy2+36; lh2=by-ly2-46
        lstr=pygame.Rect(rx,ly2,rw,lh2)
        pygame.draw.rect(screen,(255,255,255),lstr,border_radius=8)
        pygame.draw.rect(screen,(210,210,220),lstr,1,border_radius=8)
        
        # Add header row for game list
        header_y = ly2
        header_h = 32
        pygame.draw.rect(screen, (248, 248, 252), pygame.Rect(rx, header_y, rw, header_h), border_radius=8)
        pygame.draw.line(screen, (220, 220, 228), (rx, header_y + header_h), (rx + rw, header_y + header_h), 1)
        
        # Header labels with proper alignment
        h_opponent = self.parent.font_s.render("Opponent", True, (80, 80, 90))
        h_result = self.parent.font_s.render("Result", True, (80, 80, 90))
        h_rating = self.parent.font_s.render("Rating", True, (80, 80, 90))
        h_change = self.parent.font_s.render("Change", True, (80, 80, 90))
        h_date = self.parent.font_s.render("Date", True, (80, 80, 90))
        
        screen.blit(h_opponent, (rx + 15, header_y + 10))
        screen.blit(h_result, (rx + 180, header_y + 10))
        screen.blit(h_rating, (rx + 260, header_y + 10))
        screen.blit(h_change, (rx + 340, header_y + 10))
        screen.blit(h_date, (rx + 430, header_y + 10))
        
        # Adjust list rect to start after header
        lstr2 = pygame.Rect(rx, ly2 + header_h, rw, lh2 - header_h)
        screen.set_clip(lstr2)
        pg_games=games[self.page*self.per_page:(self.page+1)*self.per_page]
        gy2=lstr2.y+6; rh2=max(38,lh2//max(1,len(pg_games) if pg_games else 1))
        
        for gi_,g_ in enumerate(pg_games):
            num_=self.page*self.per_page+gi_+1
            grow_=pygame.Rect(lstr.x+8,gy2,lstr.width-16,rh2-4)
            
            # Alternating row background
            bg3_=(240,244,250) if gi_%2==0 else (250,251,255)
            if grow_.collidepoint(pygame.mouse.get_pos()):
                bg3_=(225,235,248)
            pygame.draw.rect(screen,bg3_,grow_,border_radius=5)
            
            # Opponent name (aligned with header)
            opp_=g_.get("opponent","?")
            if len(opp_) > 18:
                opp_ = opp_[:15] + "..."
            opp_txt = self.parent.font_s.render(opp_,True,(20,20,32))
            screen.blit(opp_txt, (grow_.x+10, grow_.y + (rh2 - opp_txt.get_height())//2))
            
            # Result (aligned with header)
            res_=g_.get("result","?")
            rc3_=(38,158,38) if res_=="1-0" else (178,38,38) if res_=="0-1" else (118,118,128)
            res_txt = self.parent.font_s.render(res_,True,rc3_)
            screen.blit(res_txt, (rx + 180, grow_.y + (rh2 - res_txt.get_height())//2))
            
            # Rating (aligned with header)
            rtr_=g_.get("rating","?")
            rating_txt = self.parent.font_s.render(str(rtr_),True,(40,40,52))
            screen.blit(rating_txt, (rx + 260, grow_.y + (rh2 - rating_txt.get_height())//2))
            
            # Rating change (aligned with header)
            rch2_=g_.get("rating_change",0) or 0
            rcs_=(f"+{rch2_}" if rch2_>0 else str(rch2_)) if isinstance(rch2_, int) else "0"
            rcc_=(38,158,38) if rch2_>0 else (178,38,38) if rch2_<0 else (128,128,140)
            change_txt = self.parent.font_s.render(rcs_,True,rcc_)
            screen.blit(change_txt, (rx + 340, grow_.y + (rh2 - change_txt.get_height())//2))
            
            # Date (aligned with header)
            date_val = str(g_.get("date",""))
            date_txt = self.parent.font_s.render(date_val, True, (100,100,120))
            screen.blit(date_txt, (rx + 430, grow_.y + (rh2 - date_txt.get_height())//2))
            
            # Load button (right-aligned)
            lb2_=pygame.Rect(grow_.right-70,grow_.y+(rh2-28)//2,62,28)
            lc3_=(48,138,208) if lb2_.collidepoint(pygame.mouse.get_pos()) else (68,148,228)
            pygame.draw.rect(screen,lc3_,lb2_,border_radius=5)
            lt3_=self.parent.font_s.render("Load",True,(255,255,255))
            screen.blit(lt3_,(lb2_.centerx-lt3_.get_width()//2,lb2_.centery-lt3_.get_height()//2))
            self.zones.append((lb2_,"load_game",g_))
            
            gy2+=rh2
        screen.set_clip(None)

        # Pagination
        py2=by-38
        self.btn_prev=pygame.Rect(rx,py2,78,28)
        self.btn_next=pygame.Rect(rx+rw-78,py2,78,28)
        for _btn_,_lbl_,_en_ in[(self.btn_prev,"< Prev",self.page>0),(self.btn_next,"Next >",self.page<tp-1)]:
            _c_=(98,148,208) if _en_ else (198,198,210)
            pygame.draw.rect(screen,_c_,_btn_,border_radius=6)
            _t_=self.parent.font_s.render(_lbl_,True,(255,255,255) if _en_ else (158,158,170))
            screen.blit(_t_,(_btn_.centerx-_t_.get_width()//2,_btn_.centery-_t_.get_height()//2))
        pg_=self.parent.font_s.render(f"Page {self.page+1} / {tp}",True,(80,80,92))
        screen.blit(pg_,(rx+rw//2-pg_.get_width()//2,py2+6))

        # --- FIX: Draw the Hover Tooltip LAST so it stays on top of everything ---
        if 'show_tooltip' in locals() and show_tooltip and tooltip_idx is not None and tooltip_idx < len(pts_g):
            # Draw hover highlight (green dot, no white inner dot)
            pygame.draw.circle(screen, (50, 200, 90), pts_g[tooltip_idx], 7)
            pygame.draw.circle(screen, (255, 255, 255), pts_g[tooltip_idx], 3)
            
            # Draw vertical reference line
            pygame.draw.line(screen, (200, 200, 210), 
                           (pts_g[tooltip_idx][0], ga2.y), 
                           (pts_g[tooltip_idx][0], ga2.bottom), 1)
            
            # Enhanced tooltip
            gh_ = games[tooltip_idx]
            rc_ = gh_.get("rating", "?")
            rch_ = gh_.get("rating_change", 0) or 0
            res_ = gh_.get("result", "*")
            opp_ = gh_.get("opponent", "?")
            if len(opp_) > 18:
                opp_ = opp_[:15] + "..."
            date_ = gh_.get("date", "")
            
            tooltip_lines = [
                f"Rating: {rc_}",
                f"Change: {'+'if rch_>0 else ''}{rch_}",
                f"vs {opp_}",
                f"Result: {res_}",
                f"{date_}"
            ]
            
            tw = 200
            th = len(tooltip_lines) * 16 + 12
            
            # Smart tooltip positioning
            tx = pts_g[tooltip_idx][0] + 15
            if tx + tw > gr.right - 8:
                tx = pts_g[tooltip_idx][0] - tw - 15
            
            tip_y = pts_g[tooltip_idx][1] - th - 10
            if tip_y < gr.y + 8:
                tip_y = pts_g[tooltip_idx][1] + 10
            
            # Tooltip background with shadow and orange border
            shadow_rect = pygame.Rect(tx + 2, tip_y + 2, tw, th)
            pygame.draw.rect(screen, (0, 0, 0, 30), shadow_rect, border_radius=6)
            pygame.draw.rect(screen, (248, 248, 252), pygame.Rect(tx, tip_y, tw, th), border_radius=6)
            pygame.draw.rect(screen, (230, 130, 30), pygame.Rect(tx, tip_y, tw, th), 2, border_radius=6)
            
            # Tooltip text with better spacing
            for line_idx, line in enumerate(tooltip_lines):
                if "Rating:" in line:
                    col = (40, 40, 52)
                elif "Change:" in line:
                    col = (60, 140, 60) if rch_ > 0 else (160, 40, 40) if rch_ < 0 else (100, 100, 100)
                elif "Result:" in line:
                    col = (40, 40, 52)
                else:
                    col = (80, 80, 92)
                
                line_surf = self.parent.font_s.render(line, True, col)
                screen.blit(line_surf, (tx + 10, tip_y + 6 + line_idx * 16))

    def handle_click(self, pos):
        if self.close_btn and self.close_btn.collidepoint(pos): self.active=False; return

        # + Add Account button → open the AccountPopup importer on top
        if getattr(self, 'btn_add_account', None) and self.btn_add_account.collidepoint(pos):
            from account_popup import AccountPopup as AccountImportPopup
            self.parent.add_account_popup = AccountImportPopup(self.parent)
            self.parent.add_account_popup.active = True
            return

        if self.btn_prev and self.btn_prev.collidepoint(pos) and self.page>0: self.page-=1; return
        if self.btn_next and self.btn_next.collidepoint(pos):
            acc=self._get_account()
            if acc:
                tp=max(1,(len(self._games_for(acc))+self.per_page-1)//self.per_page)
                if self.page<tp-1: self.page+=1
            return
        for r,action,data in self.zones:
            if r.collidepoint(pos):
                if action=="select_acc": self.selected_account=data; self.page=0
                elif action=="delete_acc":
                    # Delete the account
                    self._delete_account(data)
                    return
                elif action=="sort":
                    if self.sort_key==data: self.sort_asc=not self.sort_asc
                    else: self.sort_key=data; self.sort_asc=False
                    self.page=0
                elif action=="load_game":
                    pp=data.get("pgn_path")
                    if pp and os.path.exists(pp):
                        self.parent.smart_load_pgn(pp); self.active=False
                return

    def handle_scroll(self, e):
        if e.type==pygame.MOUSEBUTTONDOWN:
            if e.button==4: self.scroll_acc=max(0,self.scroll_acc-38)
            elif e.button==5: self.scroll_acc+=38

class BatchCalibrationPopup(BasePopup):
    def __init__(self, parent):
        super().__init__(parent, 900, 700)
        self.files = []  # List of dicts: {path, name, w_acc, b_acc, w_elo, b_elo, match_pct}
        self.scroll_y = 0
        self.active_input = None # (file_idx, field_name)
        
        self.is_calibrating = False
        self.generation = 0
        self.global_match = 0.0
        self.btn_add = None
        self.btn_run = None
        self.cursor_timer = 0

    def draw(self, screen, fb, fm):
        self.draw_bg(screen, "Batch Engine Calibration", fb)
        
        # Top Stats
        screen.blit(fm.render(f"Global Match: {self.global_match:.1f}%", True, THEME["accent"]), (self.rect.x + 30, self.rect.y + 60))
        if self.is_calibrating:
            screen.blit(fm.render(f"Calibrating... Generation {self.generation}/1000", True, (200, 100, 50)), (self.rect.centerx - 100, self.rect.y + 60))

        # Buttons
        self.btn_add = pygame.Rect(self.rect.right - 350, self.rect.y + 50, 140, 40)
        pygame.draw.rect(screen, (60, 160, 220), self.btn_add, border_radius=8)
        t = fb.render("+ Add PGN", True, (255, 255, 255))
        screen.blit(t, (self.btn_add.centerx - t.get_width()//2, self.btn_add.centery - t.get_height()//2))

        self.btn_run = pygame.Rect(self.rect.right - 190, self.rect.y + 50, 160, 40)
        col_run = (100, 100, 100) if self.is_calibrating else (60, 180, 60)
        pygame.draw.rect(screen, col_run, self.btn_run, border_radius=8)
        t = fb.render("Run Calibration", True, (255, 255, 255))
        screen.blit(t, (self.btn_run.centerx - t.get_width()//2, self.btn_run.centery - t.get_height()//2))

        # Render File List & Inputs
        list_rect = pygame.Rect(self.rect.x + 20, self.rect.y + 110, self.rect.width - 40, self.rect.height - 130)
        pygame.draw.rect(screen, (250, 250, 252), list_rect, border_radius=8)
        screen.set_clip(list_rect)
        
        y = list_rect.y + 10 - self.scroll_y
        self.input_zones = []
        
        for i, f in enumerate(self.files):
            if y > list_rect.bottom: break
            row = pygame.Rect(list_rect.x + 10, y, list_rect.width - 20, 80)
            pygame.draw.rect(screen, (255, 255, 255), row, border_radius=6)
            pygame.draw.rect(screen, (220, 220, 220), row, 1, border_radius=6)
            
            # File Name & Match %
            screen.blit(fb.render(f["name"], True, (40, 40, 40)), (row.x + 15, row.y + 10))
            match_col = (40, 180, 40) if f["match_pct"] >= 90 else (200, 80, 80)
            screen.blit(fm.render(f"Match: {f['match_pct']:.1f}%", True, match_col), (row.right - 150, row.y + 10))
            
            # Draw Input Boxes (W-Acc, B-Acc, W-Elo, B-Elo)
            fields = [("w_acc", "W-Acc"), ("b_acc", "B-Acc"), ("w_elo", "W-Elo"), ("b_elo", "B-Elo")]
            bx = row.x + 15
            for field, label in fields:
                screen.blit(self.parent.font_s.render(label, True, (100,100,100)), (bx, row.y + 40))
                box = pygame.Rect(bx + 50, row.y + 35, 60, 30)
                
                is_active = (self.active_input == (i, field))
                pygame.draw.rect(screen, THEME["accent"] if is_active else (230,230,230), box, 2, border_radius=4)
                
                # --- FIX: Use string directly and center perfectly ---
                self.cursor_timer += 1 # Advance the clock
                
                txt = str(f[field])
                txt_surf = self.parent.font_s.render(txt, True, (0,0,0))
                
                tx = box.centerx - txt_surf.get_width() // 2
                ty = box.centery - txt_surf.get_height() // 2
                screen.blit(txt_surf, (tx, ty))
                
                # --- NEW: Draw the blinking cursor if this box is selected ---
                if is_active and (self.cursor_timer // 60) % 2 == 0:
                    cursor_x = tx + txt_surf.get_width() + 2
                    pygame.draw.line(screen, THEME["accent"], (cursor_x, ty + 2), (cursor_x, ty + txt_surf.get_height() - 2), 2)
                
                self.input_zones.append((box, i, field))
                bx += 130
                
            y += 90
            
        screen.set_clip(None)

    def handle_click(self, pos):
        if self.close_btn and self.close_btn.collidepoint(pos): self.active = False; return
        if self.is_calibrating: return

        # Decides the no. of pgn input for calibration purposes
        if self.btn_add.collidepoint(pos) and len(self.files) < 70:
            path = filedialog.askopenfilename(filetypes=[("PGN", "*.pgn")])
            if path:
                # --- FIX: Read the file and create a row for EVERY game inside it! ---
                try:
                    import chess.pgn
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        game_num = 1
                        while len(self.files) < 70:
                            offset = f.tell() # Save the exact byte location of the game
                            game = chess.pgn.read_game(f)
                            if game is None:
                                break # End of file reached
                                
                            # Create a clean display name using the actual players
                            w_name = game.headers.get("White", "White")
                            b_name = game.headers.get("Black", "Black")
                            display_name = f"{game_num}. {w_name} vs {b_name}"
                            
                            self.files.append({
                                "path": path, 
                                "name": display_name, 
                                "offset": offset, # Remember where this game lives!
                                "w_acc": "", "b_acc": "", "w_elo": "", "b_elo": "", "match_pct": 0.0
                            })
                            game_num += 1
                except Exception as e:
                    print(f"Failed to read multi-game PGN: {e}")
            return
            
        if self.btn_run.collidepoint(pos) and self.files:
            self.is_calibrating = True
            threading.Thread(target=self._run_calibration_worker, daemon=True).start()
            return
            
        self.active_input = None
        for box, idx, field in self.input_zones:
            if box.collidepoint(pos):
                self.active_input = (idx, field)
                break

    def handle_input(self, e):
        if e.type == pygame.KEYDOWN and self.active_input:
            idx, field = self.active_input
            val_str = str(self.files[idx][field])
            
            if e.key == pygame.K_BACKSPACE: 
                val_str = val_str[:-1]
            # --- FIX: Safely append decimals without converting instantly ---
            elif e.unicode.isdigit() or (e.unicode == '.' and '.' not in val_str): 
                val_str += e.unicode
            
            self.files[idx][field] = val_str

    def handle_scroll(self, e):
        if e.button == 4: self.scroll_y = max(0, self.scroll_y - 30)
        elif e.button == 5: self.scroll_y += 30

    def _run_calibration_worker(self):
        """Memetic Evolutionary Algorithm with Live Stockfish Analysis."""
        dataset = []
        
        # --- FIX: Ensure the Engine is turned on before we start! ---
        if not self.parent.analyzer.is_active:
            try:
                self.parent.analyzer._start_engine()
            except Exception as e:
                print(f"[!] Failed to start engine for calibration: {e}")
                
        # 1. PARSING PHASE: Parse games & Analyze with Stockfish Live!
        print(f"\n[CALIBRATION] Starting Engine Analysis on {len(self.files)} games...")
        
        for f_data in self.files:
            print(f" -> Analyzing {f_data['name']} with Stockfish...")
            with open(f_data["path"], "r", encoding="utf-8", errors="ignore") as file:
                # --- FIX: Jump to the exact game using the saved offset ---
                if "offset" in f_data:
                    file.seek(f_data["offset"])
                    
                game = chess.pgn.read_game(file)
                if not game: continue
                
                board = game.board()
                file_moves = []
                prev_cp = 20 # Standard starting evaluation
                
                w_loss_sum, b_loss_sum = 0, 0
                w_moves, b_moves = 0, 0
                has_classes = False
                
                for node in game.mainline():
                    board_before = board.copy()
                    move = node.move
                    board.push(move)
                    
                    # --- NEW: LIVE ENGINE EVALUATION ---
                    try:
                        # --- NNUE WDL UPGRADE: Native MultiPV Parsing for Perfect Calibration ---
                        limit = chess.engine.Limit(depth=16)
                        
                        # Analyze BEFORE move to extract Best Move (for Sharpness calculation)
                        infos = self.parent.analyzer.engine.analyse(board_before, limit, multipv=3)
                        prev_sc = infos[0]["score"].white()
                        prev_cp = 10000 - (abs(prev_sc.mate())*100) if prev_sc.is_mate() else prev_sc.score()
                        best_move_before = infos[0].get("pv", [None])[0]
                        
                        # Analyze AFTER move
                        info_after = self.parent.analyzer.engine.analyse(board, limit)
                        curr_sc = info_after["score"].white()
                        curr_cp = 10000 - (abs(curr_sc.mate())*100) if curr_sc.is_mate() else curr_sc.score()
                    except Exception as e:
                        print(f"Engine failed on a move: {e}")
                        curr_cp = prev_cp # Fallback to prevent crash
                        best_move_before = None
                    
                    # Parse like chess.coms's text tags (Support BOTH formats)
                    comment = node.comment
                    class_match = None
                    if comment:
                        class_match = re.search(r"\[%class\s(\w+)\]", comment)
                        if not class_match:
                            class_match = re.search(r"type;([a-zA-Z]+);", comment)
                    
                    is_white_turn = board_before.turn == chess.WHITE
                    
                    # If this move has a "GreatFind", "Blunder", etc., save it for the GA!
                    if class_match:
                        has_classes = True
                        expected_class = class_match.group(1).lower()
                        
                        file_moves.append({
                            "move": move, 
                            "board_before": board_before,
                            "board_after": board.copy(),
                            "prev_cp": prev_cp, 
                            "curr_cp": curr_cp, 
                            "best_move": best_move_before, # --- WDL UPGRADE: Added Best Move for Gap/Sharpness! ---
                            "expected": expected_class, 
                            "turn": is_white_turn
                        })
                        
                    # Calculate Centipawn Loss using our own engine's math for Elo accuracy
                    loss = prev_cp - curr_cp if is_white_turn else curr_cp - prev_cp
                    loss = max(0, min(loss, 1000))
                    
                    if is_white_turn:
                        w_loss_sum += loss
                        w_moves += 1
                    else:
                        b_loss_sum += loss
                        b_moves += 1
                        
                    prev_cp = curr_cp
                
                if not has_classes:
                    print(f"[WARNING] Ignored {f_data['name']} - No Move Classifications found.")
                    continue
                    
                # Pre-calculate ACPL exactly once per game!
                f_data["w_acpl"] = w_loss_sum / max(1, w_moves)
                f_data["b_acpl"] = b_loss_sum / max(1, b_moves)
                
                dataset.append({"f_data": f_data, "moves": file_moves})
                
                # --- FIX: Detailed PGN Parsing Telemetry ---
                print(f"    [+] Parsed {len(file_moves)} classified moves successfully.")
                print(f"    [+] White ACPL: {f_data['w_acpl']:.1f} | Black ACPL: {f_data['b_acpl']:.1f}")

        print(f"[CALIBRATION] Analysis Complete! Starting Memetic Evolution...\n")

        # --- NEW: GOD-TIER MEMETIC ALGORITHM UPGRADE ---
        best_overall_score = -99999
        best_thresholds = None
        best_calib = None
        generations_without_improvement = 0
        
        original_model = getattr(self.parent.analyzer, 'feature_model', None)
        self.parent.analyzer.feature_model = None
        
        POP_SIZE = 150    
        GENERATIONS = 1200
        
        def enforce_bounds(ind):
            # Enforce logical mathematical boundaries so the engine doesn't crash
            ind["cp"]["blunder"] = min(ind["cp"]["blunder"], -50)
            ind["cp"]["mistake"] = max(ind["cp"]["blunder"] + 1, min(ind["cp"]["mistake"], -20))
            ind["cp"]["inaccuracy"] = max(ind["cp"]["mistake"] + 1, min(ind["cp"]["inaccuracy"], -1))
            ind["cp"]["good"] = max(5, ind["cp"]["good"])
            ind["cp"]["excellent"] = max(ind["cp"]["good"] + 1, ind["cp"]["excellent"])
            ind["cp"]["best"] = max(ind["cp"]["excellent"] + 1, ind["cp"]["best"])
            ind["cp"]["great"] = max(ind["cp"]["best"] + 1, ind["cp"]["great"])
            ind["cp"]["brilliant"] = max(ind["cp"]["great"] + 1, ind["cp"]["brilliant"])
            for m_key in ["m50", "m60", "m70", "m80", "m85", "m90"]:
                ind["calib"][m_key] = max(1.0, ind["calib"][m_key])
            ind["calib"]["acc_weight"] = max(0.5, ind["calib"]["acc_weight"])
            
            # --- WDL UPGRADE: Enforce logical bounds for Sharpness gaps and Win% Misses ---
            ind["calib"]["gap_great"] = max(10.0, ind["calib"]["gap_great"])
            ind["calib"]["gap_brill"] = max(ind["calib"]["gap_great"] + 20.0, ind["calib"]["gap_brill"])
            ind["calib"]["miss_eq"] = max(10.0, min(ind["calib"]["miss_eq"], 90.0))
            ind["calib"]["miss_win"] = max(ind["calib"]["miss_eq"] + 5.0, ind["calib"]["miss_win"])
            
            return ind

        def evaluate_individual(ind):
            # VITAL LOGIC KEPT SAFE HERE: Evaluates the individual against the Stockfish dataset
            if ind["fitness"] != -9999: return ind["fitness"]
            self.parent.analyzer.CP_THRESHOLDS = ind["cp"]
            self.parent.analyzer.CALIB_PARAMS = ind["calib"] # --- WDL UPGRADE: Apply CALIB_PARAMS! ---
            
            # Changed total_matches to a float (0.0) to hold decimal soft-scores!
            total_matches, total_moves, total_acc_error, total_elo_error = 0.0, 0, 0, 0
            
            for ds in dataset:
                f_data = ds["f_data"]
                
                # --- WDL UPGRADE: Soft-Scoring for Tactical Sharpness & Classes ---
                file_matches = 0.0
                for m in ds["moves"]:
                    pred = self.parent.analyzer.classify_move(
                        m["move"], m["board_before"], m["board_after"], 
                        m["prev_cp"], m["curr_cp"], best_move=m.get("best_move")
                    )
                    ref = m["expected"]
                    
                    # 1.0 points for exact match, 0.7 for same-category, 0.3 for near-miss
                    if pred == ref:
                        file_matches += 1.0
                    else:
                        file_matches += self.parent.analyzer._soft_score(pred, ref)
                
                sim_w_acc = max(0, 100 - (f_data["w_acpl"] / ind["calib"]["acc_weight"]))
                sim_b_acc = max(0, 100 - (f_data["b_acpl"] / ind["calib"]["acc_weight"]))
                
                def get_sim_elo(acc, cal):
                    if acc <= 50.0: return 100
                    b60 = 100 + (10 * cal["m50"])
                    b70 = b60 + (10 * cal["m60"])
                    b80 = b70 + (10 * cal["m70"])
                    b85 = b80 + (5 * cal["m80"])
                    b90 = b85 + (5 * cal["m85"])
                    
                    if acc < 60.0: e = 100 + (acc - 50.0) * cal["m50"]
                    elif acc < 70.0: e = b60 + (acc - 60.0) * cal["m60"]
                    elif acc < 80.0: e = b70 + (acc - 70.0) * cal["m70"]
                    elif acc < 85.0: e = b80 + (acc - 80.0) * cal["m80"]
                    elif acc < 90.0: e = b85 + (acc - 85.0) * cal["m85"]
                    else: e = b90 + (acc - 90.0) * cal["m90"]
                    return max(100, min(3600, e))

                sim_w_elo = get_sim_elo(sim_w_acc, ind["calib"])
                sim_b_elo = get_sim_elo(sim_b_acc, ind["calib"])
                
                target_w_acc = float(f_data["w_acc"]) if f_data.get("w_acc") else 0.0
                target_b_acc = float(f_data["b_acc"]) if f_data.get("b_acc") else 0.0
                target_w_elo = float(f_data["w_elo"]) if f_data.get("w_elo") else 0.0
                target_b_elo = float(f_data["b_elo"]) if f_data.get("b_elo") else 0.0

                if target_w_acc > 0: total_acc_error += abs(sim_w_acc - target_w_acc)
                if target_b_acc > 0: total_acc_error += abs(sim_b_acc - target_b_acc)
                if target_w_elo > 0: total_elo_error += abs(sim_w_elo - target_w_elo)
                if target_b_elo > 0: total_elo_error += abs(sim_b_elo - target_b_elo)
                
                total_matches += file_matches
                total_moves += len(ds["moves"])
                
            # Because total_matches is now a float (e.g., 48.3 / 50), this becomes your Soft Match %!
            class_match_pct = (total_matches / max(1, total_moves)) * 100
            ind["fitness"] = class_match_pct - (total_acc_error * 0.5) - (total_elo_error * 0.05)
            return ind["fitness"]

        # Initialize Population
        population = []
        for _ in range(POP_SIZE):
            r_vals = sorted([random.randint(-800, 800) for _ in range(8)])
            ind_cp = {
                "blunder": min(-50, r_vals[0]), "mistake": min(-20, max(r_vals[0] + 1, r_vals[1])),
                "inaccuracy": min(-1, max(r_vals[1] + 1, r_vals[2])), "good": max(5, r_vals[3]),
                "excellent": max(10, max(r_vals[3] + 1, r_vals[4])), "best": max(15, max(r_vals[4] + 1, r_vals[5])),
                "great": max(20, max(r_vals[5] + 1, r_vals[6])), "brilliant": max(25, max(r_vals[6] + 1, r_vals[7]))
            }
            ind_calib = {
                # --- OPTION 2: LOCKED ELO PARAMETERS (Perfect 74.5% / 1200 Anchor) ---
                "acc_weight": 3.288162, "m50": 5.655816, "m60": 28.524366, 
                "m70": 153.649243, "m80": 42.198487, "m85": 108.894600, "m90": 153.373501,
                
                # --- WDL UPGRADE: Evolving Tactical Sharpness ---
                "gap_great": random.uniform(100.0, 300.0),
                "gap_brill": random.uniform(200.0, 500.0),
                "miss_win": random.uniform(70.0, 95.0),
                "miss_eq": random.uniform(30.0, 60.0)
            }
            population.append(enforce_bounds({"cp": ind_cp, "calib": ind_calib, "fitness": -9999}))
            
        for gen in range(1, GENERATIONS + 1):
            self.generation = gen
            
            # 1. EVALUATE ALL
            for ind in population: evaluate_individual(ind)
            
            # 2. SORT BY FITNESS
            population.sort(key=lambda x: x["fitness"], reverse=True)
            self.global_match = population[0]["fitness"]
            
            # 3. GOD-TIER UPGRADE: True Memetic Gradient Descent (Local Hill Climbing)
            if gen % 15 == 0:
                print(f"    [+] Running Memetic Gradient Descent on the King...")
                improved_in_descent = True
                descent_steps = 0
                
                while improved_in_descent and descent_steps < 10:
                    improved_in_descent = False
                    descent_steps += 1
                    current_best = population[0]["fitness"]
                    
                    # Probe CP Thresholds
                    for k in population[0]["cp"].keys():
                        for step in [-4, 4]:
                            test_ind = {"cp": population[0]["cp"].copy(), "calib": population[0]["calib"].copy(), "fitness": -9999}
                            test_ind["cp"][k] += step
                            test_ind = enforce_bounds(test_ind)
                            evaluate_individual(test_ind)
                            if test_ind["fitness"] > current_best:
                                population[0] = test_ind
                                current_best = test_ind["fitness"]
                                improved_in_descent = True
                    
                    # Probe Piecewise Slopes & WDL Gaps
                    for k in population[0]["calib"].keys():
                        # --- OPTION 2: Do NOT let Gradient Descent touch the Elo curve! ---
                        if k in ["acc_weight", "m50", "m60", "m70", "m80", "m85", "m90"]:
                            continue 
                            
                        # Determine proper step-size for the gradient descent based on the variable
                        if k in ["miss_win", "miss_eq"]: step_size = 2.0
                        elif k in ["gap_great", "gap_brill"]: step_size = 10.0
                        else: step_size = 3.0
                        
                        for step in [-step_size, step_size]:
                            test_ind = {"cp": population[0]["cp"].copy(), "calib": population[0]["calib"].copy(), "fitness": -9999}
                            test_ind["calib"][k] += step
                            test_ind = enforce_bounds(test_ind)
                            evaluate_individual(test_ind)
                            if test_ind["fitness"] > current_best:
                                population[0] = test_ind
                                current_best = test_ind["fitness"]
                                improved_in_descent = True
            
            # 4. TRACK GLOBAL BEST
            if population[0]["fitness"] > best_overall_score:
                best_overall_score = population[0]["fitness"]
                best_thresholds = population[0]["cp"].copy()
                best_calib = population[0]["calib"].copy()
                generations_without_improvement = 0
            else:
                generations_without_improvement += 1
                
            # --- FIX: Live Percentage Progress Tracker in CMD ---
            progress_pct = (gen / GENERATIONS) * 100.0
            if gen % 10 == 0 or gen == 1:
                print(f"[Evolution: {progress_pct:05.1f}%] GEN {gen:03d}/{GENERATIONS} | Fitness: {best_overall_score:.2f} | "
                      f"m50: {best_calib['m50']:.1f}, m90: {best_calib['m90']:.1f} | Stall: {generations_without_improvement}/100")
                
            # Wait for 100 generations of zero improvement
            if generations_without_improvement > 100:
                print(f"\n[!] Population converged to absolute perfection early at generation {gen} ({progress_pct:.1f}% of max generations)!")
                break
            
            # 5. CREATE NEXT GENERATION
            next_gen = []
            
            # Elitism: Keep Top 3 unmodified
            next_gen.extend(population[:3])
            
            # Adaptive Simulated Annealing Mutation Rate
            mut_size = max(1, int(40 * (1 - (gen / GENERATIONS))))
            calib_mut_size = max(0.1, 2.0 * (1 - (gen / GENERATIONS)))
            
            # GOD-TIER UPGRADE: Multi-Point Tournament Crossover
            while len(next_gen) < POP_SIZE:
                p1 = max(random.sample(population[:POP_SIZE//2], 3), key=lambda x: x["fitness"])
                p2 = max(random.sample(population[:POP_SIZE//2], 3), key=lambda x: x["fitness"])
                
                child_cp = { k: p1["cp"][k] if random.random() < 0.5 else p2["cp"][k] for k in best_thresholds.keys() }
                child_calib = { k: p1["calib"][k] if random.random() < 0.5 else p2["calib"][k] for k in best_calib.keys() }
                
                # Apply Adaptive Mutation
                if random.random() < 0.30: 
                    mut_key = random.choice(list(child_cp.keys()))
                    child_cp[mut_key] += random.randint(-mut_size, mut_size)
                
                if random.random() < 0.30: 
                    # --- OPTION 2: Only allow WDL Gaps to mutate! ---
                    mut_key = random.choice(["gap_great", "gap_brill", "miss_win", "miss_eq"])
                    
                    if mut_key in ["miss_win", "miss_eq"]: 
                        child_calib[mut_key] = max(10.0, min(95.0, child_calib[mut_key] + random.uniform(-5.0, 5.0)))
                    elif mut_key in ["gap_great", "gap_brill"]: 
                        child_calib[mut_key] = max(50.0, child_calib[mut_key] + random.uniform(-20.0, 20.0))
                
                next_gen.append(enforce_bounds({"cp": child_cp, "calib": child_calib, "fitness": -9999}))
                
            population = next_gen[:POP_SIZE] 
            time.sleep(0.001) 
            
        # 3. Finalize and Output Best Configuration
        self.parent.analyzer.CP_THRESHOLDS = best_thresholds
        self.parent.analyzer.CALIB_PARAMS = best_calib
        
        self.parent.analyzer.feature_model = original_model
        self.is_calibrating = False
        
        print("\n=== CALIBRATION COMPLETE ===")
        print("Paste this into analysis_engine.py:")
        print("CP_THRESHOLDS =", best_thresholds)
        print("CALIB_PARAMS =", best_calib)
        print("============================\n")