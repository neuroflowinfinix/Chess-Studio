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
        self.w, self.h = w, h
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
        ov = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 150))
        screen.blit(ov, (0, 0))
        # Light Theme
        pygame.draw.rect(screen, (250, 250, 252), self.rect, border_radius=12)
        pygame.draw.rect(screen, (200, 200, 200), self.rect, 2, border_radius=12)
        
        # Title Bar
        screen.blit(fb.render(title, True, (40, 40, 40)), (self.rect.x + 20, self.rect.y + 20))
        
        self.close_btn = pygame.Rect(self.rect.right - 40, self.rect.y + 15, 30, 30)
        pygame.draw.rect(screen, (220, 220, 220), self.close_btn, border_radius=6)
        screen.blit(fb.render("X", True, (0, 0, 0)), (self.close_btn.x + 8, self.close_btn.y + 2))

        # --- FIX 7: Image Close Button ---
        if self.close_btn:
            close_icon = self.parent.assets.icons.get("close_btn")
            # Try to load from assets/icons/close_btn.png if not present in assets
            if not close_icon:
                try:
                    p = os.path.join('assets', 'icons', 'close_btn.png')
                    if os.path.exists(p):
                        img = pygame.image.load(p).convert_alpha()
                        # Cache original; scaling will be applied when blitting
                        self.parent.assets.icons['close_btn'] = img
                        close_icon = img
                except Exception:
                    close_icon = None

            if close_icon:
                try:
                    screen.blit(pygame.transform.smoothscale(close_icon, (self.close_btn.w, self.close_btn.h)), (self.close_btn.x, self.close_btn.y))
                except Exception:
                    # If scaling fails, blit raw
                    screen.blit(close_icon, (self.close_btn.x, self.close_btn.y))
            else:
                # Fallback if image fails to load
                pygame.draw.rect(screen, (200, 200, 200), self.close_btn, border_radius=5)
                screen.blit(fb.render("X", True, (0, 0, 0)), (self.close_btn.x + 8, self.close_btn.y + 2))

# =============================================================================
#  PUZZLE POPUP
# =============================================================================
# In popups.py

class PuzzlePopup(BasePopup):
    def __init__(self, parent):
        super().__init__(parent, 800, 600) # Made wider for 3 tabs
        self.assets = parent.assets
        self.tab = "unsolved" # "unsolved", "solved", "appmade"
        self.scroll = 0
        self.zones = []
        self.edit_idx = -1
        self.edit_text = ""
        
        # Tab Rects
        self.btn_unsolved = None
        self.btn_solved = None
        self.btn_appmade = None # New Tab
        
        self.btn_new = None
        self.btn_reload = None
        
        self.assets.refresh_puzzles() 

    def draw(self, screen, fb, fm):
        self.draw_bg(screen, "Chess Puzzles", fb)
        
        # --- TABS ---
        tab_y = self.rect.y + 70
        tab_w = 140
        self.btn_unsolved = pygame.Rect(self.rect.x + 20, tab_y, tab_w, 35)
        self.btn_solved = pygame.Rect(self.rect.x + 170, tab_y, tab_w, 35)
        self.btn_appmade = pygame.Rect(self.rect.x + 320, tab_y, tab_w, 35) # New
        
        # Colors
        col_u = THEME["accent"] if self.tab == "unsolved" else (220, 220, 220)
        col_s = THEME["accent"] if self.tab == "solved" else (220, 220, 220)
        col_a = THEME["accent"] if self.tab == "appmade" else (220, 220, 220)
        
        # Draw Tabs
        pygame.draw.rect(screen, col_u, self.btn_unsolved, border_radius=6)
        screen.blit(fm.render("Unsolved", True, (255,255,255) if self.tab=="unsolved" else (0,0,0)), (self.btn_unsolved.x+35, self.btn_unsolved.y+8))
        
        pygame.draw.rect(screen, col_s, self.btn_solved, border_radius=6)
        screen.blit(fm.render("Solved", True, (255,255,255) if self.tab=="solved" else (0,0,0)), (self.btn_solved.x+40, self.btn_solved.y+8))
        
        pygame.draw.rect(screen, col_a, self.btn_appmade, border_radius=6)
        screen.blit(fm.render("My Puzzles", True, (255,255,255) if self.tab=="appmade" else (0,0,0)), (self.btn_appmade.x+25, self.btn_appmade.y+8))

        # --- ACTION BUTTONS (Right Side) ---
        self.btn_new = pygame.Rect(self.rect.right - 140, tab_y, 120, 35)
        pygame.draw.rect(screen, (60, 180, 60), self.btn_new, border_radius=6)
        screen.blit(fm.render("Random", True, (255,255,255)), (self.btn_new.x+30, self.btn_new.y+8))
        
        if self.parent.mode == "puzzle":
            self.btn_reload = pygame.Rect(self.rect.right - 280, tab_y, 120, 35)
            pygame.draw.rect(screen, (200, 180, 50), self.btn_reload, border_radius=6)
            screen.blit(fm.render("Reload", True, (255,255,255)), (self.btn_reload.x+35, self.btn_reload.y+8))

        # --- PUZZLE LIST ---
        # Select source based on tab
        if self.tab == "unsolved":
            puzzles = self.assets.puzzles_unsolved
        elif self.tab == "solved":
            puzzles = self.assets.puzzles_solved
        else:
            puzzles = self.assets.appmade_puzzles
        
        clip_rect = pygame.Rect(self.rect.x + 20, self.rect.y + 120, self.w - 40, self.h - 140)
        pygame.draw.rect(screen, (255,255,255), clip_rect, border_radius=8)
        screen.set_clip(clip_rect)
        
        total_h = len(puzzles) * 60
        max_scroll = max(0, total_h - clip_rect.height)
        self.scroll = max(0, min(self.scroll, max_scroll))
        
        y = clip_rect.y - self.scroll
        self.zones = []
        
        # Use different icons for different tabs
        icon_key = "puzzles"
        if self.tab == "appmade": icon_key = "brilliant" # Use brilliant icon for my puzzles
        icon = self.assets.icons.get(icon_key)
        
        for i, p in enumerate(puzzles):
            if y + 60 < clip_rect.y: y += 60; continue
            if y > clip_rect.bottom: break
            
            row = pygame.Rect(clip_rect.x, y, clip_rect.width, 50)
            if row.collidepoint(pygame.mouse.get_pos()): pygame.draw.rect(screen, (240, 240, 250), row)
            
            if icon: screen.blit(pygame.transform.smoothscale(icon, (30,30)), (row.x+10, row.y+10))
            
            # Name or Edit Box
            if i == self.edit_idx:
                edit_box = pygame.Rect(row.x+50, row.y+10, 300, 30)
                pygame.draw.rect(screen, (255,255,255), edit_box)
                pygame.draw.rect(screen, THEME["accent"], edit_box, 2)
                screen.blit(fm.render(self.edit_text, True, (0,0,0)), (edit_box.x+5, edit_box.y+5))
            else:
                screen.blit(fm.render(p["name"], True, (0,0,0)), (row.x+50, row.y+15))
            
            # Buttons
            btn_load = pygame.Rect(row.right-80, row.y+10, 70, 30)
            pygame.draw.rect(screen, (60, 160, 220), btn_load, border_radius=4)
            screen.blit(self.parent.font_s.render("Play", True, (255,255,255)), (btn_load.x+20, btn_load.y+6))
            
            btn_edit = pygame.Rect(row.right-160, row.y+10, 70, 30)
            pygame.draw.rect(screen, (200, 200, 200), btn_edit, border_radius=4)
            screen.blit(self.parent.font_s.render("Rename", True, (0,0,0)), (btn_edit.x+12, btn_edit.y+6))
            
            self.zones.append({"load": btn_load, "edit": btn_edit, "idx": i, "puzzle": p})
            
            pygame.draw.line(screen, (230,230,230), (row.x, row.bottom), (row.right, row.bottom))
            y += 60
            
        screen.set_clip(None)

    def handle_scroll(self, e):
        if e.button == 4: self.scroll -= 30
        elif e.button == 5: self.scroll += 30

    def handle_click(self, pos):
        if self.close_btn.collidepoint(pos): self.active = False; return
        
        # Tab Switching
        if self.btn_unsolved.collidepoint(pos): self.tab = "unsolved"; self.scroll=0; self.edit_idx=-1; return
        if self.btn_solved.collidepoint(pos): self.tab = "solved"; self.scroll=0; self.edit_idx=-1; return
        if self.btn_appmade.collidepoint(pos): self.tab = "appmade"; self.scroll=0; self.edit_idx=-1; return
        
        if self.btn_new.collidepoint(pos):
            # Pick random from current tab
            current_list = self.assets.puzzles_unsolved
            if self.tab == "solved": current_list = self.assets.puzzles_solved
            elif self.tab == "appmade": current_list = self.assets.appmade_puzzles
            
            if current_list:
                p = random.choice(current_list)
                self.parent.start_puzzle(p)
                self.active = False
            return

        if self.btn_reload and self.btn_reload.collidepoint(pos):
            if self.parent.active_puzzle:
                self.parent.start_puzzle(self.parent.active_puzzle)
                self.active = False
            return
            
        if self.edit_idx != -1: self.commit_edit(); return

        for z in self.zones:
            if z["load"].collidepoint(pos):
                self.parent.start_puzzle(z["puzzle"])
                self.active = False
                return
            if z["edit"].collidepoint(pos):
                self.edit_idx = z["idx"]
                self.edit_text = z["puzzle"]["name"]
                return

    def handle_input(self, e):
        if e.type == pygame.KEYDOWN and self.edit_idx != -1:
            if e.key == pygame.K_RETURN: self.commit_edit()
            elif e.key == pygame.K_BACKSPACE: self.edit_text = self.edit_text[:-1]
            else: self.edit_text += e.unicode

    def commit_edit(self):
        if self.edit_idx != -1:
            if self.tab == "unsolved": puzzles = self.assets.puzzles_unsolved
            elif self.tab == "solved": puzzles = self.assets.puzzles_solved
            else: puzzles = self.assets.appmade_puzzles
            
            if 0 <= self.edit_idx < len(puzzles):
                p = puzzles[self.edit_idx]
                if self.edit_text.strip():
                    self.assets.rename_puzzle(p, self.edit_text)
            self.edit_idx = -1
            self.edit_text = ""

# =============================================================================
#  SAVE BRILLIANT POPUP
# =============================================================================
# In popups.py

class SaveBrilliantPopup(BasePopup):
    def __init__(self, parent, brilliant_fens):
        super().__init__(parent, 550, 400)  # Increased height slightly
        self.fens = brilliant_fens
        self.current_idx = 0
        self.btn_save = None
        self.btn_next = None
        
        # Checkbox states
        self.do_not_save_all = False
        self.save_all = False
        
        # Rects for checkboxes
        self.chk_nosave_rect = None
        self.chk_saveall_rect = None

    def draw(self, screen, fb, fm):
        # Dim background
        ov = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 180))
        screen.blit(ov, (0, 0))
        
        # Main Box
        cx, cy = (screen.get_width() - self.w)//2, (screen.get_height() - self.h)//2
        self.rect = pygame.Rect(cx, cy, self.w, self.h)
        
        pygame.draw.rect(screen, (255, 255, 255), self.rect, border_radius=15)
        pygame.draw.rect(screen, (200, 200, 200), self.rect, 2, border_radius=15)
        
        # Icon
        ic = self.parent.assets.icons.get("brilliant")
        if ic: screen.blit(pygame.transform.smoothscale(ic, (60,60)), (cx+245, cy+20))
        
        # Title & Info
        title = fb.render("Brilliant Move Found!", True, (20, 160, 20))
        screen.blit(title, (cx + (self.w - title.get_width())//2, cy + 90))
        
        msg = fm.render(f"Puzzle {self.current_idx+1} of {len(self.fens)}", True, (80, 80, 80))
        screen.blit(msg, (cx + (self.w - msg.get_width())//2, cy + 130))
        
        # --- CHECKBOXES ---
        chk_y = cy + 180
        
        # Option 1: Save All
        self.chk_saveall_rect = pygame.Rect(cx + 60, chk_y, 20, 20)
        pygame.draw.rect(screen, (200, 200, 200), self.chk_saveall_rect, 2)
        if self.save_all:
            pygame.draw.rect(screen, (40, 40, 40), (cx + 64, chk_y + 4, 12, 12))
        screen.blit(fm.render("Save ALL as puzzles", True, (0,0,0)), (cx + 90, chk_y))

        # Option 2: Do Not Save Any
        self.chk_nosave_rect = pygame.Rect(cx + 60, chk_y + 40, 20, 20)
        pygame.draw.rect(screen, (200, 200, 200), self.chk_nosave_rect, 2)
        if self.do_not_save_all:
             pygame.draw.rect(screen, (40, 40, 40), (cx + 64, chk_y + 44, 12, 12))
        screen.blit(fm.render("Discard ALL (Don't Save)", True, (0,0,0)), (cx + 90, chk_y + 40))

        # Buttons
        btn_y = cy + 280
        self.btn_save = pygame.Rect(cx + 60, btn_y, 180, 45)
        
        # Logic: If "Discard All" is checked, this button becomes disabled/grey
        if self.do_not_save_all:
             pygame.draw.rect(screen, (200, 200, 200), self.btn_save, border_radius=8)
             save_txt = "Skip All"
        elif self.save_all:
             pygame.draw.rect(screen, (60, 180, 60), self.btn_save, border_radius=8)
             save_txt = "Finish & Save"
        else:
             pygame.draw.rect(screen, (60, 180, 60), self.btn_save, border_radius=8)
             save_txt = "Save This One"
             
        txt_surf = fb.render(save_txt, True, (255,255,255))
        screen.blit(txt_surf, (self.btn_save.centerx - txt_surf.get_width()//2, self.btn_save.centery - txt_surf.get_height()//2))

        self.btn_next = pygame.Rect(cx + 260, btn_y, 180, 45)
        pygame.draw.rect(screen, (200, 60, 60), self.btn_next, border_radius=8)
        
        # Text changes based on context
        next_txt = "Next / Skip"
        if self.save_all or self.do_not_save_all: next_txt = "Confirm"
        elif self.current_idx == len(self.fens) - 1: next_txt = "Close"
            
        txt_surf2 = fb.render(next_txt, True, (255,255,255))
        screen.blit(txt_surf2, (self.btn_next.centerx - txt_surf2.get_width()//2, self.btn_next.centery - txt_surf2.get_height()//2))
        
        self.close_btn = pygame.Rect(cx + self.w - 40, cy + 10, 30, 30)

    def handle_click(self, pos):
        # 1. Handle Checkboxes (Exclusive logic)
        if self.chk_saveall_rect.collidepoint(pos):
            self.save_all = not self.save_all
            if self.save_all: self.do_not_save_all = False # Uncheck other
            return

        if self.chk_nosave_rect.collidepoint(pos):
            self.do_not_save_all = not self.do_not_save_all
            if self.do_not_save_all: self.save_all = False # Uncheck other
            return

        # 2. Handle Save Action
        if self.btn_save.collidepoint(pos):
            if self.do_not_save_all:
                self.active = False # Just close
            elif self.save_all:
                # Save REMAINING puzzles
                for i in range(self.current_idx, len(self.fens)):
                    self.save_puzzle(i)
                self.active = False
            else:
                # Save just this one
                self.save_puzzle(self.current_idx)
                self.advance()

        # 3. Handle Next/Skip
        elif self.btn_next.collidepoint(pos) or (self.close_btn and self.close_btn.collidepoint(pos)):
            if self.save_all:
                # User clicked "Confirm" with Save All checked
                for i in range(self.current_idx, len(self.fens)):
                    self.save_puzzle(i)
                self.active = False
            elif self.do_not_save_all:
                # User clicked "Confirm" with Discard All checked
                self.active = False
            else:
                # Just skip this one
                self.advance()
            
    def save_puzzle(self, idx):
        if idx < len(self.fens):
            fen = self.fens[idx]
            self.parent.assets.save_appmade_puzzle(fen, f"Brilliant Move {random.randint(100,999)}")

    def advance(self):
        self.current_idx += 1
        if self.current_idx >= len(self.fens):
            self.active = False

# =============================================================================
#  ENGINE POPUP
# =============================================================================
class EnginePopup(BasePopup):
    def __init__(self, parent):
        super().__init__(parent, 750, 550) # Taller and wider for the dual-pane layout
        
        # --- FIX: Inject Lichess Cloud as a Virtual Engine ---
        self.engines = list(self.parent.assets.engines)
        if not any(e["path"] == "lichess_cloud" for e in self.engines):
            self.engines.insert(0, {"name": "Lichess Cloud API", "path": "lichess_cloud"})
            
        self.scroll = 0
        self.zones = []
        self.selected_idx = 0
        
        # Find current active engine index
        curr_path = self.parent.current_engine_info.get("path", "")
        for i, e in enumerate(self.engines):
            if e["path"] == curr_path:
                self.selected_idx = i
                break
                
        # Preserve all vital settings from the old code
        self.engine_settings = {
            'depth': getattr(parent, 'max_depth', 20),
            'threads': getattr(parent, 'engine_threads', 4),
            'hash_size': getattr(parent, 'engine_hash', 512),
            'use_cloud': getattr(parent, 'use_cloud_analysis', True),
            'multi_pv': getattr(parent, 'engine_multipv', 3)
        }
        
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
        
        # Layout Setup
        list_rect = pygame.Rect(self.rect.x + 20, self.rect.y + 70, 320, 390)
        settings_rect = pygame.Rect(self.rect.x + 360, self.rect.y + 70, 350, 390)
        
        # ==========================================
        # --- LEFT PANE: SCROLLABLE ENGINE LIST ---
        # ==========================================
        pygame.draw.rect(screen, (245, 245, 250), list_rect, border_radius=8)
        pygame.draw.rect(screen, (200, 200, 210), list_rect, 1, border_radius=8)
        screen.blit(fb.render("Available Engines", True, (60, 60, 70)), (list_rect.x + 15, list_rect.y + 15))
        
        engine_list_y = list_rect.y + 45
        clip_rect = pygame.Rect(list_rect.x, engine_list_y, list_rect.width, list_rect.height - 45)
        screen.set_clip(clip_rect)
        
        total_h = len(self.engines) * 55
        max_scroll = max(0, total_h - clip_rect.height)
        self.scroll = max(0, min(self.scroll, max_scroll))
        
        # Check network status for Lichess Cloud API
        is_online = True
        if hasattr(self.parent, 'network_monitor') and self.parent.network_monitor:
            is_online = self.parent.network_monitor.check_connection()

        ey = clip_rect.y - self.scroll
        for i, eng in enumerate(self.engines):
            if ey + 55 < clip_rect.y: ey += 55; continue
            if ey > clip_rect.bottom: break
            
            is_lichess = (eng["path"] == "lichess_cloud")
            is_disabled = is_lichess and not is_online
            
            er = pygame.Rect(clip_rect.x + 10, ey, clip_rect.width - 20, 48)
            is_hover = er.collidepoint(pygame.mouse.get_pos()) and not is_disabled
            is_sel = (i == self.selected_idx)
            
            if is_disabled:
                bg = (240, 240, 240)
            else:
                bg = (220, 230, 255) if is_sel else ((235, 240, 245) if is_hover else (255, 255, 255))
                
            pygame.draw.rect(screen, bg, er, border_radius=6)
            if is_sel and not is_disabled: 
                pygame.draw.rect(screen, (100, 150, 220), er, 2, border_radius=6)
            elif is_disabled:
                pygame.draw.rect(screen, (200, 200, 200), er, 1, border_radius=6)
            
            if is_disabled:
                name_color = (150, 150, 150)
            else:
                name_color = (20, 20, 20) if is_sel else (80, 80, 80)
                
            screen.blit(fm.render(eng["name"], True, name_color), (er.x + 15, er.y + 5))
            
            if is_disabled:
                path_text = "Offline (No Internet)"
                path_col = (200, 100, 100)
            else:
                short_path = eng["path"][-30:] if len(eng["path"]) > 30 else eng["path"]
                path_text = f"...{short_path}" if not is_lichess else "Remote Cloud Database"
                path_col = (120, 120, 120)
                
            screen.blit(self.parent.font_s.render(path_text, True, path_col), (er.x + 15, er.y + 25))
            
            if not is_disabled:
                self.zones.append((er, "select_engine", i))
            ey += 55
            
        screen.set_clip(None)
            
        # ==========================================
        # --- RIGHT PANE: SETTINGS & STATUS ---
        # ==========================================
        pygame.draw.rect(screen, (250, 250, 252), settings_rect, border_radius=8)
        pygame.draw.rect(screen, (200, 200, 210), settings_rect, 1, border_radius=8)
        screen.blit(fb.render("Configuration", True, (60, 60, 70)), (settings_rect.x + 15, settings_rect.y + 15))
        
        # NNUE & Syzygy Status Badges
        sel_path = self.engines[self.selected_idx]["path"] if self.engines else ""
        nnue_ok = self.has_nnue(sel_path)
        syz_ok = self.has_syzygy()
        
        sy = settings_rect.y + 50
        self._draw_status_pill(screen, "NNUE", nnue_ok, settings_rect.x + 15, sy)
        self._draw_status_pill(screen, "Syzygy", syz_ok, settings_rect.x + 120, sy)
        
        sy += 45
        
        # Configuration Spinners (Replaces Pygame text typing for better UI)
        sy = self._draw_spinner(screen, fm, "Analysis Depth", self.engine_settings['depth'], 1, 65, settings_rect.x + 15, sy, "depth")
        sy = self._draw_spinner(screen, fm, "CPU Threads", self.engine_settings['threads'], 1, 64, settings_rect.x + 15, sy, "threads")
        sy = self._draw_spinner(screen, fm, "Hash Size (MB)", self.engine_settings['hash_size'], 16, 8192, settings_rect.x + 15, sy, "hash", step=64)
        sy = self._draw_spinner(screen, fm, "MultiPV Lines", self.engine_settings['multi_pv'], 1, 10, settings_rect.x + 15, sy, "multipv")
        
        # Lichess Cloud Toggle
        cloud_rect = pygame.Rect(settings_rect.x + 15, sy + 10, 20, 20)
        col = (80, 180, 80) if self.engine_settings['use_cloud'] else (200, 200, 200)
        pygame.draw.rect(screen, col, cloud_rect, border_radius=4)
        if self.engine_settings['use_cloud']:
            pygame.draw.line(screen, (255,255,255), (cloud_rect.x+4, cloud_rect.centery), (cloud_rect.centerx-2, cloud_rect.bottom-4), 2)
            pygame.draw.line(screen, (255,255,255), (cloud_rect.centerx-2, cloud_rect.bottom-4), (cloud_rect.right-4, cloud_rect.y+4), 2)
        screen.blit(fm.render("Use Lichess Cloud Analysis", True, (60, 60, 60)), (cloud_rect.right + 10, cloud_rect.y))
        self.zones.append((cloud_rect, "toggle_cloud", None))
        
        # Action Buttons
        by = settings_rect.bottom - 55
        
        # Save JSON Button (From old code)
        btn_save = pygame.Rect(settings_rect.x + 15, by, 100, 40)
        col_save = (100, 150, 200) if btn_save.collidepoint(pygame.mouse.get_pos()) else (80, 130, 180)
        pygame.draw.rect(screen, col_save, btn_save, border_radius=8)
        t_save = fm.render("Save File", True, (255, 255, 255))
        screen.blit(t_save, (btn_save.centerx - t_save.get_width()//2, btn_save.centery - t_save.get_height()//2))
        self.zones.append((btn_save, "save", None))
        
        # Apply & Restart Button
        btn_apply = pygame.Rect(settings_rect.right - 165, by, 150, 40)
        col_apply = (60, 180, 60) if btn_apply.collidepoint(pygame.mouse.get_pos()) else (50, 160, 50)
        pygame.draw.rect(screen, col_apply, btn_apply, border_radius=8)
        t_app = fm.render("Apply & Restart", True, (255, 255, 255))
        screen.blit(t_app, (btn_apply.centerx - t_app.get_width()//2, btn_apply.centery - t_app.get_height()//2))
        self.zones.append((btn_apply, "apply", None))

    def _draw_status_pill(self, screen, label, is_active, x, y):
        color = (80, 180, 80) if is_active else (180, 180, 180)
        text_color = (255, 255, 255)
        font = self.parent.font_s
        surf = font.render(f"{label}: {'ON' if is_active else 'OFF'}", True, text_color)
        r = pygame.Rect(x, y, surf.get_width() + 20, 26)
        pygame.draw.rect(screen, color, r, border_radius=13)
        screen.blit(surf, (x + 10, y + 4))

    def _draw_spinner(self, screen, fm, label, value, min_v, max_v, x, y, tag, step=1):
        screen.blit(fm.render(label, True, (80, 80, 80)), (x, y + 5))
        
        btn_minus = pygame.Rect(x + 150, y, 30, 30)
        pygame.draw.rect(screen, (220, 220, 230), btn_minus, border_radius=4)
        screen.blit(fm.render("-", True, (40, 40, 40)), (btn_minus.centerx - 4, btn_minus.centery - 8))
        self.zones.append((btn_minus, "dec", (tag, min_v, step)))
        
        val_surf = fm.render(str(value), True, (20, 20, 20))
        screen.blit(val_surf, (x + 195 - val_surf.get_width()//2, y + 5))
        
        btn_plus = pygame.Rect(x + 210, y, 30, 30)
        pygame.draw.rect(screen, (220, 220, 230), btn_plus, border_radius=4)
        screen.blit(fm.render("+", True, (40, 40, 40)), (btn_plus.centerx - 6, btn_plus.centery - 8))
        self.zones.append((btn_plus, "inc", (tag, max_v, step)))
        
        return y + 45

    def handle_scroll(self, e):
        # Allow scrolling in the left pane engine list
        if e.button == 4: self.scroll -= 40
        elif e.button == 5: self.scroll += 40

    def handle_click(self, pos):
        if self.close_btn and self.close_btn.collidepoint(pos):
            self.active = False
            return
            
        for rect, action, data in self.zones:
            if rect.collidepoint(pos):
                if action == "select_engine":
                    self.selected_idx = data
                elif action == "dec":
                    tag, min_v, step = data
                    if tag == "depth": self.engine_settings['depth'] = max(min_v, self.engine_settings['depth'] - step)
                    elif tag == "threads": self.engine_settings['threads'] = max(min_v, self.engine_settings['threads'] - step)
                    elif tag == "hash": self.engine_settings['hash_size'] = max(min_v, self.engine_settings['hash_size'] - step)
                    elif tag == "multipv": self.engine_settings['multi_pv'] = max(min_v, self.engine_settings['multi_pv'] - step)
                elif action == "inc":
                    tag, max_v, step = data
                    if tag == "depth": self.engine_settings['depth'] = min(max_v, self.engine_settings['depth'] + step)
                    elif tag == "threads": self.engine_settings['threads'] = min(max_v, self.engine_settings['threads'] + step)
                    elif tag == "hash": self.engine_settings['hash_size'] = min(max_v, self.engine_settings['hash_size'] + step)
                    elif tag == "multipv": self.engine_settings['multi_pv'] = min(max_v, self.engine_settings['multi_pv'] + step)
                elif action == "toggle_cloud":
                    self.engine_settings['use_cloud'] = not self.engine_settings['use_cloud']
                elif action == "save":
                    self.save_engine_settings()
                elif action == "apply":
                    self.apply_settings()
                return

    def apply_settings(self):
        """Apply all settings to the parent and restart engine"""
        if not self.engines: return
        sel_eng = self.engines[self.selected_idx]
        
        # Apply to parent
        self.parent.max_depth = self.engine_settings['depth']
        self.parent.engine_threads = self.engine_settings['threads']
        self.parent.engine_hash = self.engine_settings['hash_size']
        self.parent.engine_multipv = self.engine_settings['multi_pv']
        self.parent.use_cloud_analysis = self.engine_settings['use_cloud']
        
        # Save to main settings.json
        self.parent.settings["engine_threads"] = self.engine_settings['threads']
        self.parent.settings["engine_hash"] = self.engine_settings['hash_size']
        self.parent.settings["engine_multipv"] = self.engine_settings['multi_pv']
        self.parent.settings["use_cloud_analysis"] = self.engine_settings['use_cloud']
        self.parent.save_config()
        
        # Update analyzer constraints if available
        if hasattr(self.parent, 'analyzer') and self.parent.analyzer:
            self.parent.analyzer.threads = self.engine_settings['threads']
            self.parent.analyzer.hash_size = self.engine_settings['hash_size']
            self.parent.analyzer.multipv = self.engine_settings['multi_pv']
            
        # Restart engine with new path
        self.parent.current_engine_info = sel_eng
        self.parent.change_engine(sel_eng)
        self.active = False

    def save_engine_settings(self):
        """Save current engine settings to a configuration file (From old code)"""
        try:
            import json
            import os
            import time
            
            # Create engine config directory if it doesn't exist
            config_dir = "assets/config"
            if not os.path.exists(config_dir):
                os.makedirs(config_dir)
            
            config_file = os.path.join(config_dir, "engine_settings.json")
            
            sel_eng = self.engines[self.selected_idx] if self.engines else {}
            
            # Prepare settings data
            settings_data = {
                "engine_name": sel_eng.get("name", "Unknown"),
                "engine_path": sel_eng.get("path", ""),
                "depth": self.engine_settings['depth'],
                "threads": self.engine_settings['threads'],
                "hash_size": self.engine_settings['hash_size'],
                "multi_pv": self.engine_settings['multi_pv'],
                "use_cloud": self.engine_settings['use_cloud'],
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # Save to file
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(settings_data, f, indent=2)
            
            # Show success message to user
            self.parent.status_msg = "Engine settings saved successfully to assets/config!"
            
        except Exception as e:
            self.parent.status_msg = f"Error saving engine settings: {e}"

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
            
            # Label
            screen.blit(fb.render(ph, True, (0,0,0)), (self.rect.x + 50, y))
            
            # Bar Background
            bar_bg = pygame.Rect(self.rect.x + 180, y + 5, 250, 20)
            pygame.draw.rect(screen, (220, 220, 220), bar_bg, border_radius=10)
            
            # Bar Fill
            fill_w = int((score / 100) * 250)
            col = (200, 50, 50) # Red
            if score > 50: col = (220, 180, 50) # Yellow
            if score > 80: col = (50, 180, 50) # Green
            
            bar_fill = pygame.Rect(self.rect.x + 180, y + 5, fill_w, 20)
            pygame.draw.rect(screen, col, bar_fill, border_radius=10)
            
            # Text Score
            screen.blit(fm.render(f"{score}/100", True, (0,0,0)), (bar_bg.right + 15, y))
            
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
        ov = pygame.Surface(screen.get_size(), pygame.SRCALPHA); ov.fill((0,0,0,100)); screen.blit(ov, (0,0))
        pygame.draw.rect(screen, (250,250,250), self.rect, border_radius=12)
        pygame.draw.rect(screen, (0,0,0), self.rect, 2, border_radius=12)
        
        title = self.parent.font_b.render("Promote Pawn", True, (0,0,0))
        screen.blit(title, (self.rect.centerx - title.get_width()//2, self.rect.y + 10))
        
        pcs = [chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT]
        names = ["Queen", "Rook", "Bishop", "Knight"]
        c = 'w' if self.color == chess.WHITE else 'b'
        bx = self.rect.x + 20
        for i, p in enumerate(pcs):
            r = pygame.Rect(bx, self.rect.y+50, 80, 90)
            col = (230,230,230) if r.collidepoint(pygame.mouse.get_pos()) else (255,255,255)
            pygame.draw.rect(screen, col, r, border_radius=6)
            pygame.draw.rect(screen, (200,200,200), r, 1, border_radius=6)
            
            k = c + chess.Piece(p, self.color).symbol().lower()
            if k in self.parent.assets.pieces:
                screen.blit(pygame.transform.smoothscale(self.parent.assets.pieces[k], (60,60)), (r.x+10, r.y+5))
            
            f = self.parent.font_s
            t = f.render(names[i], True, (0,0,0))
            screen.blit(t, (r.centerx - t.get_width()//2, r.y+70))
            
            self.zones.append((r, p))
            bx += 90

    def handle_click(self, pos):
        for r, p in self.zones:
            if r.collidepoint(pos):
                m = chess.Move(self.ft[0], self.ft[1], promotion=p)
                self.parent.finish_promotion(m)
                self.active = False

# =============================================================================
#  REVIEW POPUP
# =============================================================================
class ReviewPopup:
    def __init__(self, parent, history, engine, assets, headers=None, cached_results=None):
        self.parent = parent; self.history = history
        self.engine_path = engine; self.assets = assets 
        self.headers = headers or {}
        self.active = True; self.status = "Analyzing..."
        self.stats = {}; self.ratings = {"white":0, "black":0}
        self.graph_surface = None
        
        # --- NEW: Setup container for detailed Phase ELO math ---
        self.detailed_review = None 
        
        # FIX: Increased base height from 750 to 820 to fit all icons
        self.w, self.h = 1000, 820 
        
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
                if "ply" not in step:
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
        self.w = min(1000, mw-40)
        
        # FIX: Increased dynamic height limit from 750 to 820
        self.h = min(820, mh-40) 
        
        self.rect = pygame.Rect((mw-self.w)//2, (mh-self.h)//2, self.w, self.h)

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
                self.parent.save_brilliant_popup = SaveBrilliantPopup(self.parent, bf)
                self.parent.save_brilliant_popup.active = True

            self.parent.cached_review = (h, s, r, g, bf)
            
            self.status = "Complete"
            self.worker.stop()
        except Exception as e:
            print(f"Review Error: {e}")
            self.status = "Failed"

    def handle_click(self, pos):
        if self.close_btn and self.close_btn.collidepoint(pos): self.active = False
        if self.settings_mode:
            self.handle_settings_click(pos)
            return

        # --- NEW: Interactive Graph Click to Jump to Move ---
        if hasattr(self, 'graph_rect') and self.graph_rect.collidepoint(pos):
            total_moves = len(self.history)
            if total_moves > 0:
                relative_x = pos[0] - self.graph_rect.x
                move_idx = int(round((relative_x / self.graph_rect.width) * (total_moves - 1)))
                if 0 <= move_idx < len(self.history):
                    self.selected_move_idx = move_idx
                    self.parent.view_ply = move_idx + 1 # Update board ply
                    self.parent.update_opening_label()
                    return # Handled
        # ----------------------------------------------------

        col_w = (self.rect.width // 2) - 30
        right_x = self.rect.centerx + 10
        curr_y = self.rect.y + 80
        list_h = self.h - 100 
        
        if right_x <= pos[0] <= right_x + col_w and curr_y <= pos[1] <= curr_y + list_h:
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
            col_w = (self.rect.width // 2) - 30
            right_x = self.rect.centerx + 10
            
            # Only scroll if the mouse is hovering over the right column (move list)
            if right_x <= e.pos[0] <= right_x + col_w:
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
        ov = pygame.Surface(screen.get_size(), pygame.SRCALPHA); ov.fill((0,0,0,150)); screen.blit(ov, (0,0))
        pygame.draw.rect(screen, (250,250,252), self.rect, border_radius=12)
        pygame.draw.rect(screen, (255,255,255), (self.rect.x, self.rect.y, self.rect.width, 60), border_top_left_radius=12, border_top_right_radius=12)
        screen.blit(fb.render("Game Review", True, (40,40,40)), (self.rect.x+20, self.rect.y+15))
        self.close_btn = pygame.Rect(self.rect.right-40, self.rect.y+15, 30,30)
        pygame.draw.rect(screen, (220,100,100), self.close_btn, border_radius=5)
        screen.blit(fb.render("X", True, (255,255,255)), (self.close_btn.x+8, self.close_btn.y+2))
        
        if self.settings_mode: self.draw_settings(screen, fb, fm); return

        left_x = self.rect.x + 20
        col_w = (self.rect.width // 2) - 30
        curr_y = self.rect.y + 80
        
        # --- FIX: SHOW LIVE ANALYSIS PROGRESS ABOVE GRAPH ---
        if self.status != "Complete":
            # Draw the progress text above the graph box dynamically
            status_color = (40, 140, 200) if "Analyzing" in self.status else (100, 100, 100)
            screen.blit(fb.render(self.status, True, status_color), (left_x, curr_y - 27))
            
        # --- NATIVE LUCASCHESS-STYLE AREA GRAPH ---
        graph_rect = pygame.Rect(left_x, curr_y, col_w, 180)
        
        # --- FIX: Save the rect to 'self' so the hover logic can find it! ---
        self.graph_rect = graph_rect 
        
        pygame.draw.rect(screen, (250, 250, 252), graph_rect, border_radius=8)
        pygame.draw.rect(screen, THEME["border"], graph_rect, 2, border_radius=8)
        
        baseline_y = graph_rect.centery
        
        # --- FIX: Clean, Static Graph Scaling ---
        # 1. Start with an explicit 0.0 Centipawn anchor for the starting position (Ply 0)
        evals = [0] 
        
        for step in self.history:
            if "review" in step and "eval_cp" in step["review"]:
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
            
            # --- FIX: Draw Colored Dots (Shifted by +1 for the Ply 0 Anchor) ---
            for i, step in enumerate(self.history):
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
        
        curr_y += 200
        # -----------------------------------------------
        
        # --- NEW: LucasChess Robust Evaluation Integration ---
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
            
            w_summary, b_summary = pw["summary"], pb["summary"]
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
            w_summary = self.stats.get('white', {})
            b_summary = self.stats.get('black', {})

        # White Overall Box
        pygame.draw.rect(screen, (255,255,255), (left_x, curr_y, col_w//2 - 5, 80), border_radius=8)
        screen.blit(fb.render(f"W: {w_acc:.1f}%", True, (0,0,0)), (left_x+10, curr_y+10))
        screen.blit(fm.render(f"ACPL: {w_cpl}", True, (100,100,100)), (left_x+10, curr_y+35))
        # FIX: Removed [:12] truncation so the full name displays
        screen.blit(self.parent.font_s.render(w_name, True, (50,50,60)), (left_x+10, curr_y+60))
        
        # Black Overall Box
        pygame.draw.rect(screen, (40,40,40), (left_x+col_w//2 + 5, curr_y, col_w//2 - 5, 80), border_radius=8)
        screen.blit(fb.render(f"B: {b_acc:.1f}%", True, (255,255,255)), (left_x+col_w//2+15, curr_y+10))
        screen.blit(fm.render(f"ACPL: {b_cpl}", True, (200,200,200)), (left_x+col_w//2+15, curr_y+35))
        # FIX: Removed [:12] truncation so the full name displays
        screen.blit(self.parent.font_s.render(b_name, True, (200,200,220)), (left_x+col_w//2+15, curr_y+60))
        curr_y += 90
        
        # Overall ELO
        screen.blit(fb.render(f"Est. Elo White: {w_elo or '?'}", True, (40,140,40)), (left_x, curr_y))
        screen.blit(fb.render(f"Est. Elo Black: {b_elo or '?'}", True, (40,140,40)), (left_x+col_w//2 + 5, curr_y))
        curr_y += 35

        # Phase ELOs
        def safe_elo(val): return str(val) if val else "-"
        screen.blit(fm.render(f"Opening:  {safe_elo(w_op)}", True, (80,80,80)), (left_x, curr_y))
        screen.blit(fm.render(f"Opening:  {safe_elo(b_op)}", True, (80,80,80)), (left_x+col_w//2 + 5, curr_y))
        curr_y += 20
        screen.blit(fm.render(f"Middle:   {safe_elo(w_mg)}", True, (80,80,80)), (left_x, curr_y))
        screen.blit(fm.render(f"Middle:   {safe_elo(b_mg)}", True, (80,80,80)), (left_x+col_w//2 + 5, curr_y))
        curr_y += 20
        screen.blit(fm.render(f"Endgame:  {safe_elo(w_eg)}", True, (80,80,80)), (left_x, curr_y))
        screen.blit(fm.render(f"Endgame:  {safe_elo(b_eg)}", True, (80,80,80)), (left_x+col_w//2 + 5, curr_y))
        curr_y += 60

        # Categories List
        cats = [
            ("Book", "book"), ("Brilliant", "brilliant"), ("Great", "great"), 
            ("Best", "best"), ("Excellent", "excellent"), ("Good", "good"), 
            ("Inaccuracy", "inaccuracy"), ("Mistake", "mistake"), 
            ("Blunder", "blunder"), ("Miss", "miss")
        ]
        
        # --- FIX: Dynamically re-tally categories directly from history so Book moves never display as 0 ---
        safe_w_summary = {k: 0 for _, k in cats}
        safe_b_summary = {k: 0 for _, k in cats}
        for step in self.history:
            if "review" in step and "class" in step["review"]:
                c = step["review"]["class"]
                ply = step.get("ply", 1)
                if ply % 2 != 0: safe_w_summary[c] = safe_w_summary.get(c, 0) + 1
                else: safe_b_summary[c] = safe_b_summary.get(c, 0) + 1
        # --------------------------------------------------------------------------------------------------
        
        for name, key in cats:
            ic_key = "eval_book" if key == "book" and "eval_book" in self.assets.icons else key
            
            ic = self.assets.icons.get(ic_key)
            if ic: screen.blit(pygame.transform.smoothscale(ic,(20,20)),(left_x, curr_y))
            screen.blit(fm.render(name, True, (80,80,80)), (left_x+30, curr_y))
            
            wc = safe_w_summary.get(key,0)
            bc = safe_b_summary.get(key,0)
            screen.blit(fm.render(str(wc), True, (0,0,0)), (left_x+250, curr_y))
            screen.blit(fm.render(str(bc), True, (0,0,0)), (left_x+350, curr_y))
            curr_y += 28

        # --- PRESERVED EXISTING RIGHT COLUMN (Move List, Chat, & Avatars) ---
        right_x = self.rect.centerx + 10
        curr_y = self.rect.y + 80
        list_h = self.h - 100 
        
        pygame.draw.rect(screen, (255,255,255), (right_x, curr_y, col_w, list_h), border_radius=8)
        clip = pygame.Rect(right_x, curr_y, col_w, list_h)
        screen.set_clip(clip)
        
        my = curr_y + 10 - self.move_scroll
        item_h = 140 
        
        # FIX: Calculate total height based on all moves
        total_list_h = len(self.history) * item_h
        max_scroll = max(0, total_list_h - list_h + 50)
        self.move_scroll = max(0, min(self.move_scroll, max_scroll))
        
        # --- FIX: Dynamically show the selected Engine name instead of hardcoding ---
        if getattr(self.parent, 'active_bot', None):
            bot_name = self.parent.active_bot.get("name")
            bot_av = self.assets.get_avatar(bot_name)
        else:
            # Change the label to Stockfish 18
            bot_name = getattr(self.parent, 'current_engine_info', {}).get("name", "Stockfish 18")
            
            # Intercept the blue square fallback and force the Stockfish icon to load!
            if getattr(self.parent, 'stockfish_icon', None):
                bot_av = self.parent.stockfish_icon
            else:
                bot_av = self.assets.get_avatar(bot_name)
        # ----------------------------------------------------------------------------
        
        for i, move in enumerate(self.history):
            if my > clip.bottom: break
            if my + item_h > clip.y:
                bg = (248,248,252) if i%2==0 else (255,255,255)
                if i == self.selected_move_idx: bg = (230, 230, 250)
                
                pygame.draw.rect(screen, bg, (right_x, my, col_w, item_h-2))
                
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
                        screen.blit(tx_surf, (right_x + col_w - 60, my+10))
                    if ic_key and ic_key in self.assets.icons:
                        screen.blit(pygame.transform.smoothscale(self.assets.icons[ic_key], (24,24)), (right_x + col_w - 100, my+7))
                    
                    if reason:
                        if bot_av:
                            scaled_av = self.assets.scale_keep_aspect(bot_av, (30, 30))
                            ox = (30 - scaled_av.get_width()) // 2
                            oy = (30 - scaled_av.get_height()) // 2
                            screen.blit(scaled_av, (right_x + 10 + ox, my + 40 + oy))
                            screen.blit(self.parent.font_s.render(f"{bot_name}:", True, (100,100,150)), (right_x + 45, my + 40))
                            self.parent.renderer.draw_multiline_text(reason, self.parent.font_s, (60,60,60), right_x+45, my+60, col_w-60)
                        else:
                            self.parent.renderer.draw_multiline_text(reason, self.parent.font_s, (80,80,80), right_x+15, my+40, col_w-30)
                else:
                     screen.blit(self.parent.font_s.render("Analyzing...", True, (150,150,150)), (right_x+15, my+35))
            
            my += item_h
        screen.set_clip(None)

        # --- NEW: Interactive Graph Hover Tooltip ---
        if hasattr(self, 'graph_rect') and hasattr(self, 'history'):
            mx, my = pygame.mouse.get_pos()
            # Only show tooltip if mouse is hovering over the graph box
            if self.graph_rect.collidepoint(mx, my):
                total_moves = len(self.history)
                if total_moves > 0:
                    # Map mouse X coordinate to the exact move in history
                    relative_x = mx - self.graph_rect.x
                    
                    # --- FIX: Snapping math aligned with the static anchored grid ---
                    move_idx = int(round((relative_x / self.graph_rect.width) * total_plies)) - 1
                    
                    if 0 <= move_idx < len(self.history):
                        step = self.history[move_idx]
                        
                        # Only show tooltip if the move has been analyzed!
                        if "review" in step and "eval_str" in step["review"]:
                            move_num = (move_idx // 2) + 1
                            san = step.get("san", "")
                            eval_str = step["review"].get("eval_str", "")
                        
                        # --- FIX: Inject the Move Icon into the Tooltip! ---
                        cls = step.get("review", {}).get("class", "")
                        ic_key = "eval_book" if cls == "book" else cls
                        icon = self.assets.icons.get(ic_key)
                        
                        # Build tooltip text
                        tt_text = f" Move {move_num} ({san}) | Eval: {eval_str} "
                        tt_surf = fm.render(tt_text, True, (0, 0, 0))
                        
                        # Calculate Box Width (Text + padding + optional icon space)
                        box_w = tt_surf.get_width() + 10
                        if icon: box_w += 26
                        
                        # Draw Tooltip Box following the mouse
                        tt_rect = pygame.Rect(mx + 15, my + 15, box_w, tt_surf.get_height() + 10)
                        
                        # Keep tooltip from flying off the right side of the screen
                        if tt_rect.right > screen.get_width(): 
                            tt_rect.x -= tt_rect.width + 30
                        
                        # Draw the white box and blue border
                        pygame.draw.rect(screen, (255, 255, 255), tt_rect, border_radius=6)
                        pygame.draw.rect(screen, (0, 150, 255), tt_rect, 2, border_radius=6) 
                        
                        # Draw Icon and Text inside the Tooltip
                        content_x = tt_rect.x + 5
                        content_y = tt_rect.y + 5
                        
                        if icon:
                            scaled_ic = pygame.transform.smoothscale(icon, (20, 20))
                            screen.blit(scaled_ic, (content_x, tt_rect.centery - 10))
                            content_x += 26
                            
                        screen.blit(tt_surf, (content_x, content_y))
                        # ---------------------------------------------------
                        
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
            move = step["move"]
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
                    
            # C. Brilliant/Blunder Classifications (for like pro chess softwares & Lichess)
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
            txt_prev = fm.render("◀ Prev", True, (255, 255, 255))
        else:
            pygame.draw.rect(screen, (220, 220, 220), self.btn_prev, border_radius=6)
            txt_prev = fm.render("◀ Prev", True, (150, 150, 150))
        screen.blit(txt_prev, (self.btn_prev.centerx - txt_prev.get_width()//2, self.btn_prev.centery - txt_prev.get_height()//2))

        page_txt = fb.render(f"Page {self.current_page + 1} of {self.total_pages}", True, (80, 80, 80))
        screen.blit(page_txt, (cx - page_txt.get_width()//2, bottom_y + 8))

        self.btn_next = pygame.Rect(cx + 70, bottom_y, 80, 35)
        if self.current_page < self.total_pages - 1:
            pygame.draw.rect(screen, (100, 150, 200), self.btn_next, border_radius=6)
            txt_next = fm.render("Next ▶", True, (255, 255, 255))
        else:
            pygame.draw.rect(screen, (220, 220, 220), self.btn_next, border_radius=6)
            txt_next = fm.render("Next ▶", True, (150, 150, 150))
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
            ("Calibrate Engine", "calibrate"), ("Settings", "settings")
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
        ov = pygame.Surface(screen.get_size(), pygame.SRCALPHA); ov.fill((0, 0, 0, 150)); screen.blit(ov, (0, 0))
        pygame.draw.rect(screen, (250, 250, 252), self.rect, border_radius=12)
        pygame.draw.line(screen, (200,200,200), (self.rect.centerx, self.rect.y+60), (self.rect.centerx, self.rect.bottom-80))
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
        ov = pygame.Surface(screen.get_size(), pygame.SRCALPHA); ov.fill((0, 0, 0, 200)); screen.blit(ov, (0, 0))
        cw, ch = 500, 300
        cx, cy = (screen.get_width() - cw)//2, (screen.get_height() - ch)//2
        pygame.draw.rect(screen, (255, 255, 255), (cx, cy, cw, ch), border_radius=15)
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
        btn_y = cy + 120
        w_rect = pygame.Rect(cx + 80, btn_y, 140, 140)
        pygame.draw.rect(screen, (240, 240, 240), w_rect, border_radius=10)
        if wk_img: screen.blit(wk_img, (w_rect.x + 20, w_rect.y + 10))
        screen.blit(self.parent.font_s.render("White", True, (0, 0, 0)), (w_rect.centerx - 20, w_rect.bottom - 30))
        self.rects["white"] = w_rect
        b_rect = pygame.Rect(cx + 280, btn_y, 140, 140)
        pygame.draw.rect(screen, (180, 180, 180), b_rect, border_radius=10)
        if bk_img: screen.blit(bk_img, (b_rect.x + 20, b_rect.y + 10))
        screen.blit(self.parent.font_s.render("Black", True, (0, 0, 0)), (b_rect.centerx - 20, b_rect.bottom - 30))
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
        y = self.rect.y + 80
        # Renamed to Bot Voice
        opts = [("Sound", "sound"), ("Bot Voice", "speech")]
        self.toggle_rects = []
        for label, key in opts:
            val = self.parent.settings.get(key, True)
            col = (50, 200, 50) if val else (200, 50, 50)
            btn = pygame.Rect(self.rect.x + 250, y, 60, 30)
            pygame.draw.rect(screen, col, btn, border_radius=15)
            toggle_x = btn.right - 25 if val else btn.x + 5
            pygame.draw.circle(screen, (255,255,255), (toggle_x + 10, y+15), 12)
            screen.blit(fm.render(label, True, (0,0,0)), (self.rect.x+30, y+5))
            self.toggle_rects.append((btn, key))
            y += 50

     def handle_click(self, pos):
         if self.close_btn.collidepoint(pos): self.active = False; return
         for btn, key in getattr(self, 'toggle_rects', []):
             if btn.collidepoint(pos):
                 # Toggle setting and save immediately to config!
                 self.parent.settings[key] = not self.parent.settings.get(key, False)
                 self.parent.save_config()
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
        ov = pygame.Surface(screen.get_size(), pygame.SRCALPHA); ov.fill((0, 0, 0, 150)); screen.blit(ov, (0, 0))
        pygame.draw.rect(screen, (250, 250, 252), self.rect, border_radius=12)
        screen.blit(fb.render("What would a Grandmaster play?", True, (40, 40, 40)), (self.rect.x + 20, self.rect.y + 20))
        
        pygame.draw.rect(screen, (200, 200, 200), self.close_btn, border_radius=5)
        screen.blit(fb.render("X", True, (0, 0, 0)), (self.close_btn.x + 8, self.close_btn.y + 2))
        
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
        
        # Bot Avatar (Keep the UI consistent)
        bot_name = self.parent.active_bot.get("name") if self.parent.active_bot else "player"
        av = self.parent.assets.get_avatar(bot_name)
        if av:
            screen.blit(pygame.transform.smoothscale(av, (80, 80)), (cx - 40, cy + 60))
        
        # --- FIX: Dynamic Question Text based on sequence type ---
        # Determine if it was a mate sequence or opening based on stored context
        status = getattr(self.parent, 'status_msg', '').lower()
        op_name = getattr(self.parent, 'opening_name', '').lower()
        
        if "mate sequence" in status or "mate" in op_name:
            type_str = "mate sequence"
        else:
            type_str = "opening"
            
        txt = fb.render(f"Shall we practice another {type_str}?", True, (40, 40, 40))
        screen.blit(txt, (cx - txt.get_width()//2, cy + 160))
        # ---------------------------------------------------------
        
        # Option 1: Yes (Green)
        self.btn_yes = pygame.Rect(cx - 120, cy + 210, 240, 45)
        col_yes = (60, 180, 60) if self.btn_yes.collidepoint(pygame.mouse.get_pos()) else (50, 160, 50)
        pygame.draw.rect(screen, col_yes, self.btn_yes, border_radius=8)
        t_yes = fb.render("Yes, sure !", True, (255, 255, 255))
        screen.blit(t_yes, (self.btn_yes.centerx - t_yes.get_width()//2, self.btn_yes.centery - t_yes.get_height()//2))
        
        # Option 2: No (Gray)
        self.btn_no = pygame.Rect(cx - 120, cy + 270, 240, 45)
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
        ov = pygame.Surface(screen.get_size(), pygame.SRCALPHA); ov.fill((0, 0, 0, 200)); screen.blit(ov, (0, 0))
        cw, ch = 500, 300
        cx, cy = (screen.get_width() - cw)//2, (screen.get_height() - ch)//2
        pygame.draw.rect(screen, (255, 255, 255), (cx, cy, cw, ch), border_radius=15)
        
        self.close_btn = pygame.Rect(cx + cw - 40, cy + 10, 30, 30)
        x_col = (220, 220, 220) if self.close_btn.collidepoint(pygame.mouse.get_pos()) else (240, 240, 240)
        pygame.draw.rect(screen, x_col, self.close_btn, border_radius=5)
        screen.blit(self.parent.font_b.render("X", True, (0,0,0)), (self.close_btn.x + 8, self.close_btn.y + 1))
        
        title_text = self.training_data.get('name', 'Practice')
        if len(title_text) > 30: title_text = title_text[:27] + "..."
        title = self.parent.font_b.render(f"Practice: {title_text}", True, (20, 20, 20))
        screen.blit(title, (cx + (cw - title.get_width())//2, cy + 30))
        
        wk_img = self.parent.assets.pieces.get("wk") or self.parent.assets.pieces.get("wK")
        bk_img = self.parent.assets.pieces.get("bk") or self.parent.assets.pieces.get("bK")
        if wk_img: wk_img = pygame.transform.smoothscale(wk_img, (100, 100))
        if bk_img: bk_img = pygame.transform.smoothscale(bk_img, (100, 100))
        
        btn_y = cy + 100
        w_rect = pygame.Rect(cx + 80, btn_y, 140, 140)
        pygame.draw.rect(screen, (240, 240, 240), w_rect, border_radius=10)
        if wk_img: screen.blit(wk_img, (w_rect.x + 20, w_rect.y + 10))
        screen.blit(self.parent.font_s.render("Play as White", True, (0, 0, 0)), (w_rect.centerx - 35, w_rect.bottom - 25))
        self.rects["white"] = w_rect
        
        b_rect = pygame.Rect(cx + 280, btn_y, 140, 140)
        pygame.draw.rect(screen, (180, 180, 180), b_rect, border_radius=10)
        if bk_img: screen.blit(bk_img, (b_rect.x + 20, b_rect.y + 10))
        screen.blit(self.parent.font_s.render("Play as Black", True, (0, 0, 0)), (b_rect.centerx - 35, b_rect.bottom - 25))
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
        
    def handle_scroll(self, e):
        # FIX: Ensure accurate limits based on the ACTIVE tab
        if self.tab == "matches":
            item_count = len(self.ledger)
        else:
            item_count = len(self.practice_ledger)
            
        total_content_height = item_count * 60
        
        # Calculate exactly how much content overflows the viewable window
        viewable_height = self.rect.height - 290
        max_scroll_allowed = max(0, total_content_height - viewable_height)

        if e.type == pygame.MOUSEWHEEL:
            if e.y > 0: # Scroll Up
                self.scroll = max(0, self.scroll - 45)
            elif e.y < 0: # Scroll Down
                self.scroll = min(max_scroll_allowed, self.scroll + 45)
        elif e.type == pygame.MOUSEBUTTONDOWN:
            if e.button == 4: # Wheel Up
                self.scroll = max(0, self.scroll - 45)
            elif e.button == 5: # Wheel Down
                self.scroll = min(max_scroll_allowed, self.scroll + 45)

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
        
        screen.blit(self.parent.font_huge.render(str(self.parent.player_elo), True, THEME["accent"]), (top_rect.x + 120, top_rect.y + 30))
        screen.blit(fm.render("Current Elo", True, (100, 100, 100)), (top_rect.x + 125, top_rect.y + 90))
        
        # --- 2. Action Buttons & Tabs ---
        bar_y = top_rect.bottom + 20
        
        self.btn_tab_matches = pygame.Rect(self.rect.x + 20, bar_y, 140, 35)
        col_m = THEME["accent"] if self.tab == "matches" else (220, 220, 220)
        pygame.draw.rect(screen, col_m, self.btn_tab_matches, border_radius=6)
        screen.blit(fm.render("Matches", True, (255,255,255) if self.tab=="matches" else (0,0,0)), (self.btn_tab_matches.x+40, self.btn_tab_matches.y+8))
        
        self.btn_tab_practice = pygame.Rect(self.rect.x + 170, bar_y, 140, 35)
        col_p = THEME["accent"] if self.tab == "practice" else (220, 220, 220)
        pygame.draw.rect(screen, col_p, self.btn_tab_practice, border_radius=6)
        screen.blit(fm.render("Practice", True, (255,255,255) if self.tab=="practice" else (0,0,0)), (self.btn_tab_practice.x+40, self.btn_tab_practice.y+8))
        
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
        list_rect = pygame.Rect(self.rect.x + 20, bar_y + 50, self.rect.width - 40, self.rect.height - 290)
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

        # --- 4. Mini Prompt overlay for Color Selection ---
        if self.pending_import_path:
            ov = pygame.Surface(screen.get_size(), pygame.SRCALPHA); ov.fill((0,0,0,150)); screen.blit(ov, (0,0))
            prompt = pygame.Rect(cx - 150, self.rect.centery - 80, 300, 160)
            pygame.draw.rect(screen, (255, 255, 255), prompt, border_radius=12)
            screen.blit(fb.render("Which side did you play?", True, (0,0,0)), (prompt.x + 50, prompt.y + 20))
            
            self.btn_white = pygame.Rect(prompt.x + 20, prompt.y + 80, 120, 45)
            pygame.draw.rect(screen, (240, 240, 240), self.btn_white, border_radius=8)
            pygame.draw.rect(screen, (100, 100, 100), self.btn_white, 1, border_radius=8)
            screen.blit(fb.render("White", True, (0,0,0)), (self.btn_white.x + 35, self.btn_white.y + 12))
            
            self.btn_black = pygame.Rect(prompt.right - 140, prompt.y + 80, 120, 45)
            pygame.draw.rect(screen, (40, 40, 40), self.btn_black, border_radius=8)
            screen.blit(fb.render("Black", True, (255,255,255)), (self.btn_black.x + 35, self.btn_black.y + 12))

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
            path = filedialog.askopenfilename(filetypes=[("PGN Files", "*.pgn")])
            if path: self.pending_import_path = path
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
        
        txt = fm.render("This PGN already contains LucasChess evaluations.", True, (50,50,50))
        screen.blit(txt, (cx - txt.get_width()//2, cy - 30))
        txt2 = fb.render("Do you want to run a Full Deep Analysis again?", True, (20,20,20))
        screen.blit(txt2, (cx - txt2.get_width()//2, cy - 5))
        
        # YES Button (Deep Scan) - Widened to 170
        self.btn_yes = pygame.Rect(cx - 180, cy + 40, 170, 45)
        pygame.draw.rect(screen, (200, 80, 80), self.btn_yes, border_radius=8)
        t_yes = fb.render("Yes (Deep Scan)", True, (255,255,255))
        screen.blit(t_yes, (self.btn_yes.centerx - t_yes.get_width()//2, self.btn_yes.centery - t_yes.get_height()//2))

        # NO Button (Fast Import) - Widened to 170
        self.btn_no = pygame.Rect(cx + 10, cy + 40, 170, 45)
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
        
        pct_txt = fm.render(f"{self.progress}%", True, (0, 0, 0))
        screen.blit(pct_txt, (self.rect.centerx - pct_txt.get_width()//2, bar_y + 35))

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
        
        # --- FIX: Removed Cancel Button & Centered the remaining 3 ---
        self.btn_save = pygame.Rect(cx - 185, cy + 40, 110, 45)
        pygame.draw.rect(screen, (60, 180, 60), self.btn_save, border_radius=8)
        t_save = fb.render("Save", True, (255,255,255))
        screen.blit(t_save, (self.btn_save.centerx - t_save.get_width()//2, self.btn_save.centery - t_save.get_height()//2))

        self.btn_save_as = pygame.Rect(cx - 55, cy + 40, 110, 45)
        pygame.draw.rect(screen, (40, 140, 200), self.btn_save_as, border_radius=8)
        t_save_as = fb.render("Save As...", True, (255,255,255))
        screen.blit(t_save_as, (self.btn_save_as.centerx - t_save_as.get_width()//2, self.btn_save_as.centery - t_save_as.get_height()//2))

        self.btn_discard = pygame.Rect(cx + 75, cy + 40, 110, 45)
        pygame.draw.rect(screen, (200, 60, 60), self.btn_discard, border_radius=8)
        t_no = fb.render("Discard", True, (255,255,255))
        screen.blit(t_no, (self.btn_discard.centerx - t_no.get_width()//2, self.btn_discard.centery - t_no.get_height()//2))

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
        # FIX: Removed `Tk()` initialization to stop application freezes!
        try:
            from tkinter import filedialog
            if hasattr(self.parent, 'root') and self.parent.root:
                self.parent.root.update()
            filename = filedialog.asksaveasfilename(defaultextension=".pgn", filetypes=[("PGN", "*.pgn")])
            
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
        
        # Save Button
        save_btn = pygame.Rect(self.rect.x + 30, self.rect.y + self.h - 60, 100, 35)
        save_color = (50, 150, 50) if save_btn.collidepoint(pygame.mouse.get_pos()) else (40, 120, 40)
        pygame.draw.rect(screen, save_color, save_btn, border_radius=6)
        save_text = self.parent.font_s.render("Save Settings", True, (255, 255, 255))
        screen.blit(save_text, (save_btn.x + 15, save_btn.y + 8))
        self.save_btn = save_btn
        
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
            dn = self.attached_filename if len(self.attached_filename) <= 35 else self.attached_filename[:32] + "..."
            itx = fm.render(f"📎 Attached! {dn}", True, (20, 140, 40))
            screen.blit(itx, (self.rect.x + 30, self.rect.bottom - 55))
            
            self.btn_clear_file = pygame.Rect(self.rect.x + 40 + itx.get_width(), self.rect.bottom - 60, 25, 25)
            pygame.draw.rect(screen, (255, 100, 100), self.btn_clear_file, border_radius=4)
            cx_txt = fb.render("X", True, (255, 255, 255))
            screen.blit(cx_txt, (self.btn_clear_file.centerx - cx_txt.get_width()//2, self.btn_clear_file.centery - cx_txt.get_height()//2))
        else:
            self.btn_clear_file = None

        # 5. Load Button (Dynamic Color)
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
            if hasattr(self.parent, 'root') and self.parent.root: self.parent.root.update()
            path = filedialog.askopenfilename(filetypes=[("Chess Files", "*.pgn;*.fen"), ("PGN", "*.pgn"), ("FEN", "*.fen")])
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
                    if game: self.parent.trigger_auto_analysis(game)
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
        screen.blit(fb.render("+ Add PGN", True, (255, 255, 255)), (self.btn_add.x + 25, self.btn_add.y + 10))

        self.btn_run = pygame.Rect(self.rect.right - 190, self.rect.y + 50, 160, 40)
        col_run = (100, 100, 100) if self.is_calibrating else (60, 180, 60)
        pygame.draw.rect(screen, col_run, self.btn_run, border_radius=8)
        screen.blit(fb.render("Run Calibration", True, (255, 255, 255)), (self.btn_run.x + 15, self.btn_run.y + 10))

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
                    
                    # Parse like pro chess softwares's text tags (Support BOTH formats)
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