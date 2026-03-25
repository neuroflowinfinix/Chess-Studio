import sys
import warnings
import os
# --- FIX 1: Silence specific DeprecationWarnings (pkg_resources/pygame) ---
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)
import pygame
import chess
import chess.engine
import logging
# Silences harmless python-chess engine warnings in the console
logging.getLogger("chess.engine").setLevel(logging.CRITICAL)
import chess.pgn
import chess.polyglot
import threading
import time
import queue 
import random
import json
import pyttsx3
from analysis_engine import HybridTablebase
import re
import tkinter as tk
from tkinter import filedialog, messagebox
import asyncio
from database_explorer import OpeningExplorer, ExplorerUI
# --- FIX: Prevent Stockfish 18 "Illegal Ponder Move" Crashes ---
# python-chess strictly validates ponder moves. Stockfish 18 sometimes sends 
# illegal ponder moves when finding a forced mate, crashing the entire app.
_original_parse_uci = chess.Board.parse_uci
def _safe_parse_uci(self, uci):
    try:
        return _original_parse_uci(self, uci)
    except chess.IllegalMoveError:
        return chess.Move.from_uci(uci)
chess.Board.parse_uci = _safe_parse_uci
# ---------------------------------------------------------------
# --- FIX 2: REMOVED the WindowsSelectorEventLoopPolicy setting ---
# Python 3.8+ on Windows defaults to ProactorEventLoop, which IS required 
# for chess.engine to communicate with Stockfish via subprocesses.
# The previous override was causing the NotImplementedError.
# Custom Modules
try: import bot_personalities
except ImportError: bot_personalities = None
try: import analysis_engine
except ImportError: analysis_engine = None
try: import game_logic
except ImportError: game_logic = None
from assets import AssetLoader, SoundManager, BOTS, THEME, BOT_VOICE_MAP, PIECE_VALS
from popups import (PGNSavePopup, AnalyzePromptPopup, BotPopup, PGNSelectionPopup, GMPopup, PromotionPopup, 
                   ReviewPopup, SideSelectionPopup, ProfilePopup, SettingsPopup, EnginePopup, 
                   PhaseStatsPopup, PuzzlePopup, SaveBrilliantPopup, TrainerCompletePopup, ButtonsPopup, FastImportLoadingPopup)
from ui_renderer import UIRenderer
class TrainerPopup:
    def __init__(self, app):
        self.app = app
        self.active = True
        
        # --- FIX: Widen popup to fit new tutorial/practice buttons ---
        w, h = 800, 750
        self.rect = pygame.Rect((app.width - w)//2, (app.height - h)//2, w, h)
        
        self.scroll_y = 0
        self.max_scroll = 0
        self.groups = {}
        self.expanded_groups = set()
        self.click_zones = []
        
        self.tab = "openings" # "openings" or "mates"
        self.btn_tab_openings = None
        self.btn_tab_mates = None
        
        self.font_title = pygame.font.SysFont("Segoe UI", 22, bold=True)
        self.font_group = pygame.font.SysFont("Segoe UI", 16, bold=True)
        self.font_var = pygame.font.SysFont("Segoe UI", 15, bold=True)
        self.font_moves = pygame.font.SysFont("Consolas", 13)
        
        self.close_icon = None
        icon_path = os.path.join("assets", "icons", "close_btn.png")
        if os.path.exists(icon_path):
            try: 
                img = pygame.image.load(icon_path).convert_alpha()
                self.close_icon = pygame.transform.smoothscale(img, (24, 24))
            except: pass
        
        self.filter_text = ""
        self.cursor_timer = 0
        self.load_data()
    def load_data(self):
        self.groups.clear()
        self.expanded_groups.clear()
        
        data_source = self.app.assets.opening_list if self.tab == "openings" else self.app.assets.mate_list
        
        if data_source:
            for op in data_source:
                name = op.get('name', 'Unknown')
                if ":" in name:
                    group, var = name.split(":", 1)
                    group = group.strip()
                    var = var.strip()
                else:
                    group = name
                    var = "Main Line" if self.tab == "openings" else "Sequence"
                
                if group not in self.groups: self.groups[group] = []
                
                move_str = self.generate_san_string(op.get('moves', []))
                self.groups[group].append({'name': var, 'moves_str': move_str, 'data': op})
        if len(self.groups) < 5:
            for g in self.groups: self.expanded_groups.add(g)
    def generate_san_string(self, moves):
        try:
            temp_board = chess.Board()
            san_list = []
            for i, move in enumerate(moves):
                if isinstance(move, str):
                    try: move = chess.Move.from_uci(move)
                    except: break 
                if move not in temp_board.legal_moves: break
                san = temp_board.san(move)
                temp_board.push(move)
                if i % 2 == 0: san_list.append(f"{i//2 + 1}.{san}")
                else: san_list.append(san)
            return " ".join(san_list)
        except: return "Moves unavailable"
    def draw_chevron(self, screen, color, center, pointing_down=True, size=6):
        x, y = center
        if pointing_down:
            points = [(x-size, y-size//2), (x, y+size//2), (x+size, y-size//2)]
        else: # Pointing Right
            points = [(x-size//2, y-size), (x+size//2, y), (x-size//2, y+size)]
        pygame.draw.lines(screen, color, False, points, 2)
    def draw(self, screen, fb, fm):
        surf = pygame.Surface((self.app.width, self.app.height), pygame.SRCALPHA)
        surf.fill((0, 0, 0, 120)) 
        screen.blit(surf, (0, 0))
        
        pygame.draw.rect(screen, (252, 252, 252), self.rect, border_radius=12) 
        pygame.draw.rect(screen, (200, 200, 200), self.rect, 1, border_radius=12) 
        
        screen.blit(self.font_title.render("Opening & Mates Trainer", True, (40, 40, 40)), (self.rect.x + 25, self.rect.y + 20))
        
        # Tabs
        tab_y = self.rect.y + 60
        self.btn_tab_openings = pygame.Rect(self.rect.x + 25, tab_y, 140, 35)
        col_op = THEME["accent"] if self.tab == "openings" else (220, 220, 220)
        pygame.draw.rect(screen, col_op, self.btn_tab_openings, border_radius=6)
        screen.blit(fm.render("Openings", True, (255,255,255) if self.tab=="openings" else (0,0,0)), (self.btn_tab_openings.x+35, self.btn_tab_openings.y+8))
        
        self.btn_tab_mates = pygame.Rect(self.rect.x + 175, tab_y, 140, 35)
        col_mt = THEME["accent"] if self.tab == "mates" else (220, 220, 220)
        pygame.draw.rect(screen, col_mt, self.btn_tab_mates, border_radius=6)
        screen.blit(fm.render("Mates", True, (255,255,255) if self.tab=="mates" else (0,0,0)), (self.btn_tab_mates.x+45, self.btn_tab_mates.y+8))
        
        # Search Bar
        screen.blit(self.font_group.render("Search:", True, (100, 100, 100)), (self.rect.right - 260, tab_y + 8))
        search_rect = pygame.Rect(self.rect.right - 190, tab_y + 2, 160, 30)
        pygame.draw.rect(screen, (255, 255, 255), search_rect, border_radius=4)
        pygame.draw.rect(screen, (180, 180, 180), search_rect, 1, border_radius=4)
        
        txt_surf = self.font_var.render(self.filter_text, True, (0, 0, 0))
        screen.blit(txt_surf, (search_rect.x + 8, search_rect.y + 5))
        
        self.cursor_timer += 1
        if (self.cursor_timer // 30) % 2 == 0:
            cx = search_rect.x + 10 + txt_surf.get_width()
            pygame.draw.line(screen, (0,0,0), (cx, search_rect.y + 6), (cx, search_rect.bottom - 6), 2)
        
        close_rect = pygame.Rect(self.rect.right - 40, self.rect.y + 20, 24, 24)
        if self.close_icon: screen.blit(self.close_icon, close_rect)
        else: screen.blit(self.font_group.render("X", True, (100, 100, 100)), (close_rect.x + 5, close_rect.y))
        
        self.click_zones = [((close_rect, 'close', None))]
        content_rect = pygame.Rect(self.rect.x + 10, self.rect.y + 110, self.rect.width - 20, self.rect.height - 120)
        
        if not self.groups:
            msg = "Loading Openings from ECO.pgn..." if self.tab == "openings" else "Loading Mates from file..."
            screen.blit(fm.render(msg, True, (150, 150, 150)), (self.rect.centerx - 120, self.rect.centery))
            return
        clip_rect = screen.get_clip()
        screen.set_clip(content_rect)
        
        y_off = -self.scroll_y
        f_text = self.filter_text.lower()
        
        for group in sorted(self.groups.keys()):
            matching_vars = [v for v in self.groups[group] if f_text in v['name'].lower() or f_text in group.lower()]
            if f_text and not matching_vars: continue
            
            grp_height = 45
            grp_rect = pygame.Rect(content_rect.x + 10, content_rect.y + y_off, content_rect.width - 30, grp_height)
            
            is_expanded = group in self.expanded_groups or f_text != ""
            
            if y_off + grp_height > 0 and y_off < content_rect.height:
                m_pos = pygame.mouse.get_pos()
                is_hover = grp_rect.collidepoint(m_pos)
                
                bg_col = (235, 235, 240) if is_hover else (245, 245, 245)
                pygame.draw.rect(screen, bg_col, grp_rect, border_radius=8)
                pygame.draw.rect(screen, (220, 220, 230), grp_rect, 1, border_radius=8)
                
                txt = self.font_group.render(group, True, (30, 30, 30))
                screen.blit(txt, (grp_rect.x + 35, grp_rect.y + 12))
                
                chev_pos = (grp_rect.x + 20, grp_rect.y + 22)
                self.draw_chevron(screen, (100, 100, 100), chev_pos, pointing_down=is_expanded)
                
                self.click_zones.append((grp_rect, 'group', group))
            y_off += grp_height + 5
            if is_expanded:
                for var in matching_vars:
                    moves_str = var['moves_str']
                    words = moves_str.split()
                    lines = []
                    curr_line = ""
                    max_w = content_rect.width - 70
                    
                    # --- FIX: Increased margin to prevent text overlapping the buttons! ---
                    max_w = content_rect.width - 320
                    
                    for w in words:
                        if self.font_moves.size(curr_line + w)[0] < max_w:
                            curr_line += w + " "
                        else:
                            lines.append(curr_line)
                            curr_line = w + " "
                    lines.append(curr_line)
                    
                    text_h = len(lines) * 16
                    item_h = max(55, 30 + text_h + 10)
                    
                    var_rect = pygame.Rect(content_rect.x + 25, content_rect.y + y_off, content_rect.width - 45, item_h)
                    
                    if y_off + item_h > 0 and y_off < content_rect.height:
                        m_pos = pygame.mouse.get_pos()
                        is_hover = var_rect.collidepoint(m_pos)
                        
                        bg_col = (240, 245, 255) if is_hover else (255, 255, 255)
                        pygame.draw.rect(screen, bg_col, var_rect, border_radius=6)
                        if is_hover:
                            pygame.draw.rect(screen, (180, 200, 240), var_rect, 1, border_radius=6)
                        else:
                            pygame.draw.rect(screen, (230, 230, 230), var_rect, 1, border_radius=6)
                        
                        v_name = self.font_var.render(var['name'], True, (50, 50, 50))
                        screen.blit(v_name, (var_rect.x + 10, var_rect.y + 8))
                        
                        my = var_rect.y + 32
                        for line in lines:
                            l_surf = self.font_moves.render(line, True, (100, 100, 100))
                            screen.blit(l_surf, (var_rect.x + 10, my))
                            my += 16
                            
                        # --- NEW: Tutorial & Practice Buttons ---
                        btn_tut = pygame.Rect(var_rect.right - 220, var_rect.y + (item_h - 36)//2, 95, 36)
                        col_tut = (240, 140, 50) if btn_tut.collidepoint(m_pos) else (230, 130, 40)
                        pygame.draw.rect(screen, col_tut, btn_tut, border_radius=6)
                        t_tut = self.app.font_s.render("Tutorial", True, (255,255,255))
                        screen.blit(t_tut, (btn_tut.centerx - t_tut.get_width()//2, btn_tut.centery - t_tut.get_height()//2))
                        btn_prac = pygame.Rect(var_rect.right - 110, var_rect.y + (item_h - 36)//2, 95, 36)
                        col_prac = (60, 190, 60) if btn_prac.collidepoint(m_pos) else (50, 170, 50)
                        pygame.draw.rect(screen, col_prac, btn_prac, border_radius=6)
                        t_prac = self.app.font_s.render("Practice", True, (255,255,255))
                        screen.blit(t_prac, (btn_prac.centerx - t_prac.get_width()//2, btn_prac.centery - t_prac.get_height()//2))
                        
                        self.click_zones.append((btn_tut, 'start_tut', var['data']))
                        self.click_zones.append((btn_prac, 'start_prac', var['data']))
                    y_off += item_h + 5
            
        self.max_scroll = max(0, y_off + self.scroll_y - content_rect.height)
        screen.set_clip(clip_rect)
    def handle_scroll(self, event):
        if event.button == 4: self.scroll_y = max(0, self.scroll_y - 40)
        elif event.button == 5: self.scroll_y = min(self.max_scroll, self.scroll_y + 40)
    def handle_click(self, pos):
        if self.btn_tab_openings and self.btn_tab_openings.collidepoint(pos):
            self.tab = "openings"; self.scroll_y = 0; self.load_data(); return
        if self.btn_tab_mates and self.btn_tab_mates.collidepoint(pos):
            self.tab = "mates"; self.scroll_y = 0; self.load_data(); return
            
        for rect, type_, data in self.click_zones:
            if rect.collidepoint(pos):
                if type_ == 'close':
                    self.active = False
                    self.app.mode_idx = 0
                    self.app.mode = "manual"
                    self.app.status_msg = "Mode: Manual (PvP)"
                    self.app.active_bot = None
                elif type_ == 'group':
                    if data in self.expanded_groups: self.expanded_groups.remove(data)
                    else: self.expanded_groups.add(data)
                elif type_ == 'start_tut':
                    from popups import TrainerSideSelectionPopup
                    self.app.side_popup = TrainerSideSelectionPopup(self.app, data, is_tutorial=True)
                    self.app.side_popup.active = True
                elif type_ == 'start_prac':
                    from popups import TrainerSideSelectionPopup
                    self.app.side_popup = TrainerSideSelectionPopup(self.app, data, is_tutorial=False)
                    self.app.side_popup.active = True
                return
    def handle_input(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.active = False
                self.app.mode_idx = 0
                self.app.mode = "manual"
                self.app.status_msg = "Mode: Manual (PvP)"
                self.app.active_bot = None
            elif event.key == pygame.K_BACKSPACE:
                self.filter_text = self.filter_text[:-1]
            else:
                self.filter_text += event.unicode
class ChessApp:
    def __init__(self):
        pygame.init()
        pygame.key.set_repeat(300, 40) # <-- NEW: Enables continuous key-hold typing/backspacing
        self.sound_manager = SoundManager()
        self.root = tk.Tk(); self.root.withdraw()
        
        self.running = True
        self.width, self.height = 1500, 950 
        self.screen = pygame.display.set_mode((self.width, self.height), pygame.RESIZABLE)
        pygame.display.set_caption("Chess Studio Pro")
        try: pygame.display.set_icon(pygame.image.load("assets/icons/main.png"))
        except: pass
        
        # Core State
        self.mode = "play" # play, manual, trainer, puzzle
        self.board_style = "wood"
        self.history = []
        self.view_ply = 0
        self.arrows = []
        self.user_arrows = []        # Right-Click Arrows
        self.eval_val = 0.0
        self.real_time_score = "+0.0"
        self.status_msg = "Ready"
        self.opening_name = "Starting Position"
        self.white_opening = "Starting Position"
        self.black_opening = "Starting Position"
        self.chat_log = []
        self.chat_scroll = 0
        self.show_hints = False
        self.pgn_headers = {}
        self.cached_review = None
        self.active_puzzle = None 
        self.multi_arrows = [] # NEW: To store multiple engine PV arrows
        self.show_threats = False  # Toggle for threat arrows display
        
        # Trainer State
        self.trainer_moves = []
        self.trainer_idx = 0
        self.trainer_hint_arrow = None
        
        # Config
        # 'show_threats' removed from settings (feature kept internal but no UI toggle)
        self.settings = {"sound": True, "theme": "wood", "speech": True, "live_annotations": True}
        self.active_bot = BOTS[0]
        self.playing_white = True
        self.mode_idx = 1
        self.current_engine_info = {"name": "Stockfish Default", "path": ""}
        
        # Input/UI State
        self.selected = None
        self.valid_moves = []
        self.btn_rects = {} 
        self.scroll_hist = 0
        self.move_click_zones = []
        self.ui_queue = []
        self.lock = threading.Lock()
        self.speech_queue = queue.Queue()
        
        # Engine Fail-Safe
        self.engine_crash_count = 0
        
        # Animation/Drag/RightClick
        self.dragging_piece = None
        self.drag_pos = (0, 0)
        self.threat_arrow = None
        self.right_click_start = None
        # New: Dragging temp arrow
        self.temp_arrow_start = None
        self.temp_arrow_end = None
        
        # Popups
        self.active_popup = None
        self.review_popup = None; self.bot_popup = None; self.promo_popup = None
        self.side_popup = None; self.pgn_popup = None; self.gm_move_popup = None
        self.save_popup = None; self.settings_popup = None; self.trainer_popup = None
        self.engine_popup = None; self.phase_popup = None; self.puzzle_popup = None
        self.save_brilliant_popup = None
        self.trainer_complete_popup = None
        self.fast_import_popup = None
        self.unsaved_popup = None
        self.unsaved_analysis = False
        self.current_pgn_path = None
        
        # Enhanced features initialization
        self.account_popup = None
        self.chat_messages = []
        self.current_depth = 0
        self.max_depth = 20
        self.nodes_per_second = 0
        self.engine_status = 'Ready'
        self.is_analyzing = False
        self.network_status = 'offline'
        self.last_move_analysis = None
        self.clock = pygame.time.Clock()
        self.font_s = pygame.font.SysFont("Segoe UI", 14)
        self.font_m = pygame.font.SysFont("Segoe UI", 16)
        self.font_b = pygame.font.SysFont("Segoe UI", 20, bold=True)
        self.font_chat = pygame.font.SysFont("Segoe UI", 14)
        self.font_huge = pygame.font.SysFont("Segoe UI", 60, bold=True)
        self.font_mono = pygame.font.SysFont("Consolas", 14)
        self.assets = AssetLoader()
        self.load_config()
        self.renderer = UIRenderer(self)
        self.tablebase = HybridTablebase()
        self.tb_data = None
        
        # --- ADDED: Grandmaster Database Explorer ---
        self.explorer_db = OpeningExplorer("assets/database/explorer.sqlite")
        self.explorer_ui = ExplorerUI(font_small=self.font_s, font_medium=self.font_m)
        # --- FIX: Load Stockfish Icon for the Chat Box ---
        try:
            icon_path = os.path.join("assets", "bots", "stockfish.png")
            self.stockfish_icon = pygame.transform.smoothscale(pygame.image.load(icon_path).convert_alpha(), (30, 30))
        except Exception as e:
            print(f"Could not load Stockfish icon: {e}")
            self.stockfish_icon = None
        # -------------------------------------------------
        if game_logic: self.logic = game_logic.GameLogic(); self.board = self.logic.board
        else: self.logic = None; self.board = chess.Board()
        
        # --- NEW: Profile & Archive System ---
        self.archive_dir = os.path.join("assets", "archive")
        if not os.path.exists(self.archive_dir):
            os.makedirs(self.archive_dir)
            
        self.ledger_path = os.path.join("assets", "match_history.json")
        self.match_ledger = []
        if os.path.exists(self.ledger_path):
            try:
                with open(self.ledger_path, "r", encoding="utf-8") as f:
                    self.match_ledger = json.load(f)
            except Exception as e: print(f"Ledger load error: {e}")
            
        self.practice_ledger_path = os.path.join("assets", "practice_history.json")
        self.practice_ledger = []
        if os.path.exists(self.practice_ledger_path):
            try:
                with open(self.practice_ledger_path, "r", encoding="utf-8") as f:
                    self.practice_ledger = json.load(f)
            except Exception as e: print(f"Practice Ledger load error: {e}")
            
        self.import_status = "" # For the Profile loading bar
        self.profile_popup = None # Will hold the UI
        # --- FIX: Initialize Player Elo from settings (default to 400 if new) ---
        self.player_elo = self.settings.get("player_elo", 400)
        self.settings["player_elo"] = self.player_elo
        
        # Initial Engine Setup
        self.init_engine()
        
        # Initialize enhanced managers AFTER engine is set up
        try:
            from account_manager import ChessAccountManager, GameChatAnalyzer, NetworkStatusMonitor
            self.account_manager = ChessAccountManager()
            self.chat_analyzer = GameChatAnalyzer(self.analyzer) if hasattr(self, 'analyzer') and self.analyzer else None
            self.network_monitor = NetworkStatusMonitor()
        except ImportError as e:
            print(f"Enhanced features not available: {e}")
            self.account_manager = None
            self.chat_analyzer = None
            self.network_monitor = None
        
        # Start Threads
        threading.Thread(target=self.tts_worker, daemon=True).start()
        threading.Thread(target=self.task_analysis, daemon=True).start()
        threading.Thread(target=self.task_play, daemon=True).start()
        
        self.add_chat("System", f"Welcome! Playing against {self.active_bot['name']}.")
        self.calc_layout()
        self.sound_manager.play("game_start")
        self.side_popup = SideSelectionPopup(self, BOTS[0])
    def load_config(self):
        try:
            with open("settings.json", "r") as f:
                data = json.load(f)
                self.settings.update(data) # Merge saved data into defaults
                self.board_style = self.settings.get("board_style", "wood")
        except: 
            self.board_style = "wood"
            
        # Initialize Player Elo safely right as the app starts
        self.player_elo = self.settings.get("player_elo", 400)
        
        # --- FIX: Restore Engine Configurations from settings.json ---
        self.max_depth = self.settings.get("engine_depth", 20)
        self.engine_threads = self.settings.get("engine_threads", 4)
        self.engine_hash = self.settings.get("engine_hash", 512)
        self.engine_multipv = self.settings.get("engine_multipv", 3)
        self.use_cloud_analysis = self.settings.get("use_cloud_analysis", True)
    def save_config(self):
        try:
            # Sync variables before saving
            self.settings["board_style"] = self.board_style
            self.settings["player_elo"] = getattr(self, 'player_elo', 1200)
            
            # --- FIX: Ensure Engine Configurations are synced before saving ---
            self.settings["engine_depth"] = getattr(self, 'max_depth', 20)
            self.settings["engine_threads"] = getattr(self, 'engine_threads', 4)
            self.settings["engine_hash"] = getattr(self, 'engine_hash', 512)
            self.settings["engine_multipv"] = getattr(self, 'engine_multipv', 3)
            self.settings["use_cloud_analysis"] = getattr(self, 'use_cloud_analysis', True)
            
            with open("settings.json", "w") as f: 
                json.dump(self.settings, f, indent=4)
        except Exception as e: 
            print(f"Save config error: {e}")
            
    def fast_load_pgn_to_ui(self, path, offset=0):
        """Instantly loads an already-analyzed PGN directly to the UI and Review Panel."""
        import threading
        
        # --- NEW: Launch the Loading Popup ---
        self.fast_import_popup = FastImportLoadingPopup(self)
        self.fast_import_popup.active = True
        
        def update_progress(pct, text="Fast Importing Game..."):
            if hasattr(self, 'fast_import_popup') and self.fast_import_popup:
                self.fast_import_popup.progress = pct
                self.fast_import_popup.status_text = text
        
        def worker():
            try:
                if not self.analyzer:
                    self.status_msg = "Error: Engine not loaded. Cannot analyze."
                    time.sleep(2)
                    self.status_msg = ""
                    if self.fast_import_popup: self.fast_import_popup.active = False
                    return
                    
                self.status_msg = "Running Fast Import..."
                self.current_pgn_path = path
                with open(path, "r", encoding="utf-8") as f:
                    f.seek(offset)
                    g = chess.pgn.read_game(f)
                if not g: 
                    if self.fast_import_popup: self.fast_import_popup.active = False
                    return
                
                mainline = list(g.mainline())
                
                # --- Execute the fast parser with progress tracking ---
                res = self.analyzer.fast_analyze_full_game(mainline, progress_callback=update_progress)
                if res:
                    h, s, r, graph, bf = res
                    
                    with self.lock:
                        self.board.reset()
                        for h_item in h:
                            self.board.push(h_item["move"])
                            
                        self.history = h
                        self.view_ply = len(self.history)
                        self.mode = "review" 
                        
                        # --- FIX: Switch to Manual Mode so the bot doesn't auto-play ---
                        self.mode_idx = 0
                        self.active_bot = None
                        # ---------------------------------------------------------------
                        
                        # --- FIX: Update the game headers so names change! ---
                        self.pgn_headers = dict(g.headers)
                        # -----------------------------------------------------
                        
                        self.stats = s
                        self.ratings = r
                        self.graph_surface = graph
                        self.cached_review = (h, s, r, graph, bf)
                        
                        if hasattr(self, 'logic'):
                            self.logic.board = self.board.copy()
                            self.logic.history = [dict(hi) for hi in h]
                            self.logic.view_ply = self.view_ply
                        if bf:
                            from popups import SaveBrilliantPopup
                            self.save_brilliant_popup = SaveBrilliantPopup(self, bf)
                            self.save_brilliant_popup.active = True
                            
                        self.unsaved_analysis = True 
                    self.status_msg = "Fast Import Complete"
                    self.sound_manager.play("game_start")
            except Exception as e:
                print(f"Fast Load Error: {e}")
                self.status_msg = "Import Failed"
            finally:
                if hasattr(self, 'fast_import_popup') and self.fast_import_popup:
                    self.fast_import_popup.active = False
                
        threading.Thread(target=worker, daemon=True).start()
    def init_engine(self, custom_path=None):
        # --- FIX: Prevent double/concurrent initialization ---
        if getattr(self, '_is_initializing', False): return
        self._is_initializing = True
        
        try:
            # --- FIX: Cleanup existing engines properly before restart ---
            if hasattr(self, 'analyzer') and self.analyzer:
                try: self.analyzer.stop()
                except: pass
            
            if hasattr(self, 'eng_play') and self.eng_play:
                try: 
                    self.eng_play.quit()
                    # Give it a moment to release file/process locks
                    time.sleep(0.1)
                except: pass
            self.analyzer = None
            self.eng_play = None
            self.last_bot_config = None 
            
            # 1. Determine Path
            path = custom_path
            if not path:
                 path = self.find_engine()
            
            # 2. Check if path exists (Bypass for Lichess Cloud)
            if not path or (path != "lichess_cloud" and not os.path.exists(path)):
                print("WARNING: No valid engine path found. Defaulting to Manual Mode.")
                self.mode = "manual"
                self.status_msg = "No Engine - Manual Mode"
                self.add_chat("System", "Engine not found. Switched to Manual Mode.")
                return
                
            print(f"DEBUG: Attempting to load engine from: {path}")
            self.current_engine_info["path"] = path
            
            # Properly name the virtual engine so it displays correctly in the UI
            if path == "lichess_cloud":
                self.current_engine_info["name"] = "Lichess Cloud API"
            else:
                self.current_engine_info["name"] = os.path.basename(path).replace(".exe","")
            
            # 3. Initialize Analysis Engine (Safe Mode)
            if analysis_engine:
                try:
                    self.analyzer = analysis_engine.AnalysisEngine(
                        path, 
                        opening_book=self.assets.openings,
                        book_positions=self.assets.book_positions,
                        threads=getattr(self, 'engine_threads', 4),
                        hash_size=getattr(self, 'engine_hash', 512)
                    )
                    success = self.analyzer.start()
                    if not success:
                        print("Analysis Engine failed to start.")
                        self.analyzer = None
                except Exception as e:
                    print(f"Analysis Engine Init Exception: {e}")
                    self.analyzer = None
            # 4. Initialize Playing Engine (Safe Mode)
            try:
                if path == "lichess_cloud":
                    self.eng_play = "lichess_cloud" # Safely bypass executable logic
                else:
                    # On Windows, suppress the console window
                    if sys.platform == "win32":
                        self.eng_play = chess.engine.SimpleEngine.popen_uci(path, creationflags=0x08000000)
                    else:
                        self.eng_play = chess.engine.SimpleEngine.popen_uci(path)
                    # Configure Syzygy if present
                    if self.assets.path_syzygy and os.path.isdir(self.assets.path_syzygy):
                        try: self.eng_play.configure({"SyzygyPath": self.assets.path_syzygy})
                        except: pass
                
                # Use User Settings for Live Engine
                try: 
                    self.eng_play.configure({
                        "Threads": getattr(self, 'engine_threads', 4), 
                        "Hash": getattr(self, 'engine_hash', 512)
                    })
                except: pass
                
                # --- NNUE AUTO-DETECTION (Live Engine) ---
                base_name = os.path.splitext(os.path.basename(path))[0]
                nnue_path = os.path.join(os.path.dirname(path), "nnue", f"{base_name}.nnue")
                
                if os.path.exists(nnue_path) and hasattr(self.eng_play, 'options'):
                    try:
                        opts = self.eng_play.options
                        nnue_config = {}
                        
                        # Dynamically match the engine's expected keys
                        if "Use NNUE" in opts: nnue_config["Use NNUE"] = True
                        elif "Use_NNUE" in opts: nnue_config["Use_NNUE"] = True
                        
                        if "EvalFile" in opts: nnue_config["EvalFile"] = nnue_path
                        elif "NNUENetpath" in opts: nnue_config["NNUENetpath"] = nnue_path
                        
                        if nnue_config:
                            self.eng_play.configure(nnue_config)
                            print(f"[*] Live Engine NNUE Loaded: {base_name}.nnue")
                    except Exception as e:
                        print(f"[*] Live NNUE skipped: {e}")
                
            except Exception as e:
                print(f"Playing Engine Init Error: {e}")
                self.eng_play = None
                
                # --- RECOVERY MECHANISM ---
                print("Trying to recover by asking user for a valid engine...")
                new_path = self.find_engine(force_dialog=True)
                if new_path and new_path != path:
                    # Clear initializing flag so the retry isn't blocked
                    self._is_initializing = False 
                    self.init_engine(new_path)
                    return
                else:
                    # User cancelled or same path failed; break the loop
                    self.mode = "manual"
                    self.status_msg = "Engine Load Cancelled."
                self.mode = "manual"
                self.status_msg = "Engine Failed - Manual Mode"
                self.add_chat("System", "Engine failed to load. Manual Mode active.")
        finally:
            # Always release the lock when done
            self._is_initializing = False
    def find_engine(self, force_dialog=False):
        """
        Locates the Stockfish executable.
        Priority:
        1. Common local paths.
        2. Assets folder lists.
        3. Ask the user via File Dialog.
        """
        if not force_dialog:
            # Common locations to check
            priority_list = [
                "stockfish.exe", 
                "engines/stockfish.exe", 
                "bin/stockfish.exe",
                "stockfish_16.exe",
                "engines/stockfish_16.exe",
                r"C:\stockfish\stockfish.exe" # Common Windows path
            ]
            
            # 1. Check Priority List
            for p in priority_list:
                if os.path.exists(os.path.abspath(p)): 
                    return os.path.abspath(p)
                
            # 2. Check Assets detected engines
            if self.assets.engines:
                for eng in self.assets.engines:
                    if "stockfish" in eng["name"].lower() and os.path.exists(eng["path"]):
                        return eng["path"]
                if os.path.exists(self.assets.engines[0]["path"]):
                    return self.assets.engines[0]["path"]
        
        # 3. Last Resort: Ask User
        # We ensure the root window is ready for the dialog
        try:
            if self.root:
                self.root.update() 
            print("Prompting user for Stockfish executable...")
            file_path = filedialog.askopenfilename(
                title="Select Stockfish Engine (stockfish.exe)", 
                filetypes=[("Executable", "*.exe"), ("All Files", "*.*")]
            )
            if file_path and os.path.exists(file_path):
                return file_path
        except Exception as e:
            print(f"Error opening file dialog: {e}")
        return None
    def change_engine(self, engine_data):
        self.status_msg = "Switching Engine..."
        if self.analyzer: self.analyzer.stop()
        if self.eng_play: 
            if self.eng_play != "lichess_cloud":
                try: self.eng_play.quit()
                except: pass
        
        self.last_bot_config = None # FIX: Reset configuration cache so the new engine initializes!
        
        self.init_engine(engine_data["path"])
        self.status_msg = f"Loaded {self.current_engine_info['name']}"
        self.cached_review = None
    def calc_layout(self):
        w, h = self.width, self.height
        self.r_eval = pygame.Rect(10, 20, 30, h-40)
        aw = w - 550; ah = h - 60
        self.sq_sz = min(aw//8, ah//8)
        self.bd_sz = self.sq_sz * 8
        self.bd_x = 80; self.bd_y = (h - self.bd_sz) // 2
        self.sb_x = self.bd_x + self.bd_sz + 40; self.sb_w = w - self.sb_x - 20
        self.renderer.rescale_pieces()
    def update_opening_label(self):
        if not hasattr(self.assets, 'openings') or not self.assets.openings: 
            return
        
        temp = chess.Board()
        w_book = "Starting Position"
        b_book = "Starting Position"
        
        w_in_book = True
        b_in_book = True
        
        # Trace the game to find the deepest known opening name for EACH side
        for i in range(self.view_ply):
            step = self.history[i]
            move = step["move"] if isinstance(step, dict) else step
            temp.push(move)
            
            name = self.assets.get_opening_name(temp.fen())
            
            if i % 2 == 0:  # White's turn just resulted in this position
                if name and "Unknown" not in name:
                    w_book = name
                    w_in_book = True
                else:
                    w_in_book = False
            else:           # Black's turn just resulted in this position
                if name and "Unknown" not in name:
                    b_book = name
                    b_in_book = True
                else:
                    b_in_book = False
        # Set the generic overall name
        self.opening_name = w_book if self.view_ply % 2 != 0 else b_book
        # Assign independent labels
        if self.view_ply == 0:
            self.white_opening = "Starting Position"
            self.black_opening = "Starting Position"
        elif self.view_ply == 1:
            self.white_opening = w_book if w_in_book else f"{w_book} *"
            self.black_opening = "Waiting..."
        else:
            self.white_opening = w_book if w_in_book else f"{w_book} *"
            self.black_opening = b_book if b_in_book else f"{b_book} *"
    # --- THREADS ---
    def tts_worker(self):
        """Plays TTS natively and offline using pyttsx3 with dynamic accents."""
        import time
        import queue
        try:
            import pyttsx3
        except ImportError:
            print("[AUDIO THREAD] pyttsx3 not installed. Please run: pip install pyttsx3")
            return

        print("\n[AUDIO THREAD] Starting local pyttsx3 engine loop...")

        # ---------------------------------------------------------
        #  THE BOT PERSONA MATRIX (Speed-Adjusted)
        #  Maps bot names to their specific voice index and speed
        # ---------------------------------------------------------
        bot_personas = {
            "Spark":    {"index": 11, "rate": 160},  # Mark (US) - Energetic but clear
            "Cassidy":  {"index": 2,  "rate": 140},  # Linda (CA) - Safe, friendly female
            "Byte":     {"index": 1,  "rate": 150},  # James (AU) - Confident, upbeat Australian
            "Vincent":  {"index": 0,  "rate": 125},  # David (US) - Very slow, hesitant learner
            "Oliver":   {"index": 10, "rate": 140},  # David (US) - Standard, balanced
            "Arthur":   {"index": 7,  "rate": 155},  # Sean (IE) - Aggressive, punchy Irish
            "Niles":    {"index": 4,  "rate": 155},  # George (UK) - Fast, aggressive British
            "Nova":     {"index": 5,  "rate": 135},  # Hazel (UK) - Calm, passive
            "Eleanor":  {"index": 6,  "rate": 125},  # Susan (UK) - Very measured, slow defender
            "Armando":  {"index": 3,  "rate": 145},  # Richard (CA) - Sharp, tactical
            "Veda":     {"index": 8,  "rate": 135},  # Heera (IN) - Calculating Indian female
            "Catherine":{"index": 14, "rate": 140},  # Catherine (AU) - Crisp Australian historian
            "Maximus":  {"index": 9,  "rate": 130},  # Ravi (IN) - Deep, authoritative Grandmaster
            "Stockfish":{"index": 12, "rate": 165},  # Zira (US) - Brisk, robotic female
            "Checkmate Master": {"index": 4, "rate": 160} # George (UK) - Intense assassin
        }

        while getattr(self, 'running', True):
            try:
                try: 
                    text, bot_name = self.speech_queue.get(timeout=0.1)
                except queue.Empty: 
                    continue
                
                print(f"\n[AUDIO THREAD] Speaking line: {text[:40]}...")
                
                # --- THE FIX: INITIALIZE INSIDE THE LOOP ---
                tts_engine = pyttsx3.init()
                voices = tts_engine.getProperty('voices')
                total_voices = len(voices)
                
                # Fetch persona (Default to David US if bot isn't found)
                persona = bot_personas.get(bot_name, {"index": 0, "rate": 150})
                
                # SAFETY CHECK: If someone clones your GitHub repo and only has 3 voices,
                # this prevents the app from crashing by wrapping the index back to 0.
                safe_index = persona["index"] if persona["index"] < total_voices else (persona["index"] % max(1, total_voices))
                
                # Apply the specific voice and speed
                try:
                    tts_engine.setProperty('voice', voices[safe_index].id)
                    tts_engine.setProperty('rate', persona["rate"])
                except Exception:
                    pass # Fallback to system default if property fails
                
                # Speak!
                tts_engine.say(text)
                tts_engine.runAndWait()
                
                # --- THE FIX: DESTROY ENGINE AFTER SPEAKING ---
                del tts_engine
                
            except Exception as e:
                print(f"[AUDIO ERROR] Loop crashed: {e}")
                time.sleep(1)
    
    def start_ranked_match(self):
        """Finds a bot near the player's Elo and starts a ranked match."""
        # Get BOTS directly from the global import at the top of main.py
        from assets import BOTS
        
        # Use the persistent Elo from Settings
        player_elo = getattr(self, "player_elo", 1200)
        
        # Filter for standard bots within +/- 150 Elo
        valid_bots = [b for b in BOTS if b.get("type") != "book" and abs(b.get("elo", 1200) - player_elo) <= 150]
        
        # Failsafe: If no bots perfectly match the range, pick the absolutely closest one
        if not valid_bots:
            valid_bots = [min(BOTS, key=lambda b: abs(b.get("elo", 1200) - player_elo) if b.get("type") != "book" else 9999)]
            
        selected_bot = random.choice(valid_bots)
        
        # Randomize Color (Standard Ranked Rule)
        play_as_white = random.choice([True, False])
        
        # Configure and start the game
        self.active_bot = selected_bot
        self.playing_white = play_as_white
        self.mode_idx = 1
        self.mode = "play"
        
        with self.lock:
            self.board.reset()
            if hasattr(self, 'logic') and self.logic: 
                self.logic.reset_game()
                
            self.history = []
            self.view_ply = 0
            self.chat_log = []
            self.pgn_headers = {} # <-- FIX: Clear old headers on new ranked match
            
            # Announce Match
            color_str = "White" if play_as_white else "Black"
            self.add_chat("System", f"Ranked Match found! You are {color_str} vs {selected_bot['name']} ({selected_bot.get('elo', '?')} Elo).")
            self.sound_manager.play("game_start")
    def task_analysis(self):
        last_fen = None
        while self.running:
            try:
                if self.analyzer and self.analyzer.is_active:
                    with self.lock:
                        tmp = self.board.copy()
                        while tmp.ply() > self.view_ply:
                            if not tmp.move_stack: break # <--- SAFETY CHECK
                            tmp.pop()
                        fen = tmp.fen()
                    if fen != last_fen and not tmp.is_game_over():
                        self.status_msg = "Calculating..."
                        cp, txt, arr = self.analyzer.analyze_live(tmp)
                        
                        # --- Dynamic Threat Tracking (always computed; no UI toggle) ---
                        current_threat = None
                        try:
                            t = self.analyzer.get_threat(tmp)
                            # We MUST pass them as coordinate tuples!
                            if t: current_threat = (t.from_square, t.to_square)
                        except Exception:
                            current_threat = None
                        # --- FIX: Extract MultiPV Lines, Continuation Arrows & Ghost Moves ---
                        mate_lines_san = []
                        multi_arrows = []
                        
                        if self.show_hints:
                            try:
                                eng = getattr(self.analyzer, 'engine', None) or self.eng_play
                                if eng:
                                    # Safely apply MultiPV only if the engine supports it
                                    req_mpv = self.settings.get("engine_multipv", 3)
                                    has_mpv = hasattr(eng, 'options') and "MultiPV" in eng.options
                                    
                                    if has_mpv and req_mpv > 1:
                                        info = eng.analyse(tmp, chess.engine.Limit(time=0.15), multipv=req_mpv)
                                    else:
                                        info = [eng.analyse(tmp, chess.engine.Limit(time=0.15))]
                                        
                                    info_list = info if isinstance(info, list) else [info]
                                    
                                    # Standard Engine Colors (1st: Green, 2nd: Orange, 3rd: Red)
                                    # Main arrows are a bit translucent(180)
                                    arrow_colors = [(40, 200, 80, 180), (220, 140, 40, 180), (220, 60, 60, 180)]
                                    
                                    for idx, line in enumerate(info_list):
                                        if "pv" in line and line["pv"]:
                                            base_col = arrow_colors[idx] if idx < len(arrow_colors) else arrow_colors[-1]
                                            
                                            # 1. Main Move Arrow
                                            m1 = line["pv"][0]
                                            multi_arrows.append(((m1.from_square, m1.to_square), base_col))
                                            
                                            # 2. Further Lines / Continuation Arrows (En Croissant style)
                                            if len(line["pv"]) >= 3:
                                                m2 = line["pv"][1] # Opponent reply
                                                m3 = line["pv"][2] # Our follow-up move
                                                
                                                # Opponent's anticipated reply made much fainter (Alpha 70 ~ approx 27%)
                                                multi_arrows.append(((m2.from_square, m2.to_square), (100, 100, 100, 70)))
                                                # Your follow-up remains at original continuation opacity (Alpha 110)
                                                multi_arrows.append(((m3.from_square, m3.to_square), (base_col[0], base_col[1], base_col[2], 110)))
                                            
                                            # 3. Extract Ghost Text Lines for the Sidebar
                                            san_line = []
                                            sim_board = tmp.copy()
                                            for pv_m in line["pv"][:5]:
                                                san_line.append(sim_board.san(pv_m))
                                                sim_board.push(pv_m)
                                            mate_lines_san.append(san_line)
                            except Exception as e:
                                print(f"MultiPV error: {e}")
                        # -----------------------------------------------
                        with self.lock:
                            self.eval_val = cp if self.playing_white else -cp
                            self.real_time_score = txt
                            self.arrows = multi_arrows if multi_arrows else arr
                            self.threat_arrow = current_threat 
                            self.mate_lines_san = mate_lines_san # Expose to UI renderer
                            # --- NEW: Expose Live Depth ---
                            if hasattr(self.analyzer, 'current_depth'):
                                self.current_depth = self.analyzer.current_depth
                            
                        last_fen = fen
                        self.status_msg = "Analysis Ready"
                        self.update_opening_label()
            except: pass
            time.sleep(0.1)
    def task_play(self):
        while self.running:
            try:
                if (self.board.is_game_over() or 
                    self.mode == 'review' or 
                    (self.promo_popup and self.promo_popup.active) or
                    (self.side_popup and self.side_popup.active) or
                    (self.bot_popup and self.bot_popup.active)):
                    time.sleep(0.5); continue
                
                # --- PUZZLE MODE ---
                if self.mode == "puzzle":
                    if self.board.turn != self.playing_white: 
                        self.status_msg = "Puzzle: Opponent to move..."
                        if self.eng_play:
                            try:
                                limit = chess.engine.Limit(time=0.3)
                                res = self.eng_play.play(self.board, limit)
                                if res.move:
                                    self.ui_queue.append(("move", res.move))
                                    self.status_msg = "Your Turn"
                            except (chess.IllegalMoveError, Exception) as e: 
                                print(f"Puzzle engine error: {e}")
                                self.eng_play = None # Reset on error
                    time.sleep(0.1)
                    continue
                # --- TRAINER MODE (Strict Book Play) ---
                if self.mode == "trainer":
                    if self.trainer_idx >= len(self.trainer_moves):
                        self.status_msg = "Practice Completed!"
                        time.sleep(0.5); continue
                    is_bot_turn = (self.board.turn == chess.WHITE and not self.playing_white) or \
                                  (self.board.turn == chess.BLACK and self.playing_white)
                    
                    if is_bot_turn:
                        # Auto-play correct book move
                        move = self.trainer_moves[self.trainer_idx]
                        time.sleep(random.uniform(0.6, 1.5)) 
                        self.ui_queue.append(("move", move))
                        self.status_msg = "Trainer: Bot playing book move..."
                    else:
                        self.status_msg = "Trainer: Your Turn (Follow the line)"
                    
                    time.sleep(0.2)
                    continue
                if self.mode == "manual": 
                     time.sleep(0.5); continue
                # --- STANDARD BOT PLAY ---
                with self.lock:
                    is_bot_turn = (self.board.turn == chess.WHITE and not self.playing_white) or \
                                  (self.board.turn == chess.BLACK and self.playing_white)
                    # Create a completely isolated board for the engine to use
                    search_board = self.board.copy()
                if is_bot_turn:
                    move = None
                    bot_data = self.active_bot or {} 
                    
                    # === Beginner Book Logic ===
                    if bot_data.get("group") == "Beginner":
                        try:
                            bk_path = os.path.join("assets", "bots", "books", "beginner.bin")
                            if os.path.exists(bk_path):
                                with chess.polyglot.open_reader(bk_path) as reader:
                                    entries = list(reader.find_all(search_board))
                                    if entries:
                                        entry = random.choice(entries)
                                        move = entry.move
                                        time.sleep(random.uniform(0.5, 1.0))
                        except Exception as e:
                            print(f"Book read skipped: {e}")
                    # 1. Book Check (Existing logic for GM bots & Checkmate Master)
                    if not move and bot_data.get("type") == "book":
                        
                        # --- Checkmate Master reads ALL books in the folder ---
                        if bot_data.get("name") == "Checkmate Master":
                            import glob
                            book_folder = os.path.join("assets", "bots", "books")
                            all_entries = []
                            
                            for bin_file in glob.glob(os.path.join(book_folder, "*.bin")):
                                try:
                                    with chess.polyglot.open_reader(bin_file) as reader:
                                        all_entries.extend(list(reader.find_all(search_board)))
                                except Exception: 
                                    pass
                                    
                            if all_entries:
                                all_entries.sort(key=lambda x: x.weight, reverse=True)
                                top_weight = all_entries[0].weight
                                best_moves = [e for e in all_entries if e.weight >= top_weight]
                                move = random.choice(best_moves).move
                                
                        # --- Standard GM Bot Logic (Reads single path) ---
                        elif "path" in bot_data:
                            try:
                                with chess.polyglot.open_reader(bot_data["path"]) as reader:
                                    for entry in reader.find_all(search_board): 
                                        move = entry.move
                                        break
                            except Exception: 
                                pass
                    # 2. Engine Check & Restart
                    if not move:
                        if not self.eng_play:
                            self.engine_crash_count += 1
                            if self.engine_crash_count > 3:
                                self.status_msg = "Engine Failed. Random Mode."
                            else:
                                self.status_msg = "Restarting Engine..."
                                try: self.init_engine(self.current_engine_info.get("path"))
                                except: time.sleep(1); continue
                                if not self.eng_play: time.sleep(1); continue
                    elo = bot_data.get("elo", 1200)
                    bot_style = bot_data.get("style", "Balanced")
                    self.status_msg = f"{bot_data.get('name', 'Bot')} thinking..."
                    
                    # 3. Configure Engine
                    if self.eng_play and self.eng_play != "lichess_cloud" and not move:
                        current_config_signature = (bot_data.get("name"), elo, bot_style)
                        if self.last_bot_config != current_config_signature:
                            if isinstance(elo, int):
                                try:
                                    opts = self.eng_play.options
                                    bot_config = {}
                                    if "UCI_LimitStrength" in opts:
                                        bot_config["UCI_LimitStrength"] = True
                                        if "UCI_Elo" in opts:
                                            bot_config["UCI_Elo"] = max(1350, min(2850, elo))
                                    if bot_style == "Aggressive" and "Contempt" in opts:
                                        bot_config["Contempt"] = 50
                                        
                                    if bot_config: self.eng_play.configure(bot_config)
                                    self.last_bot_config = current_config_signature
                                except Exception as e: 
                                    print(f"Config Error (Safe Skip): {e}")
                    # 4. Get Move from Engine
                    if not move and self.eng_play:
                        
                        if self.eng_play == "lichess_cloud":
                            import requests
                            try:
                                res = requests.get(f"https://lichess.org/api/cloud-eval?fen={search_board.fen()}", timeout=2).json()
                                if "pvs" in res and res["pvs"]:
                                    move = chess.Move.from_uci(res["pvs"][0]["moves"].split()[0])
                                time.sleep(0.5)
                            except Exception:
                                pass # Fallback to random if not available in cloud DB
                            
                            if not move and list(search_board.legal_moves):
                                move = random.choice(list(search_board.legal_moves))
                        else:
                            # --- LucasChess-Inspired Low-Elo Engine (Martin 250 Simulator) ---
                            if isinstance(elo, int) and elo < 1350:
                                error_rate = max(0.0, (1350 - elo) / 1300.0)
                                
                                if random.random() < error_rate:
                                    try:
                                        has_mpv = hasattr(self.eng_play, 'options') and "MultiPV" in self.eng_play.options
                                        if has_mpv:
                                            info = self.eng_play.analyse(search_board, chess.engine.Limit(time=0.1), multipv=7)
                                        else:
                                            info = [self.eng_play.analyse(search_board, chess.engine.Limit(time=0.1))]
                                            
                                        if info:
                                            legal_moves = list(search_board.legal_moves)
                                            if elo <= 400 and random.random() < 0.4:
                                                move = random.choice(legal_moves)
                                            else:
                                                options = info[2:] if len(info) > 3 else info
                                                chosen = random.choice(options)
                                                move = chosen["pv"][0] if "pv" in chosen and chosen["pv"] else random.choice(legal_moves)
                                                
                                            time.sleep(random.uniform(0.5, 1.5))
                                    except Exception as e:
                                        print(f"Low Elo Engine Error: {e}")
                                        move = random.choice(list(search_board.legal_moves))
                                        
                            # If the bot didn't make a forced blunder
                            if not move:
                                limit = chess.engine.Limit(time=0.5)
                                try:
                                    if isinstance(elo, int):
                                        if elo <= 600: limit = chess.engine.Limit(depth=1)
                                        elif elo <= 1000: limit = chess.engine.Limit(depth=2)
                                        elif elo <= 1350: limit = chess.engine.Limit(depth=4)
                                        else: limit = chess.engine.Limit(time=(0.5 if elo < 1800 else 1.0))
                                    
                                    start = time.time()
                                    
                                    # --- THE ULTIMATE ASSASSIN LOGIC V5 (Checkmate Master) ---
                                    if bot_style == "Assassin":
                                        start_think = time.time()
                                        
                                        # Force the engine to think deeply and look at multiple sharp lines
                                        assassin_limit = chess.engine.Limit(time=1.0)
                                        has_mpv = hasattr(self.eng_play, 'options') and "MultiPV" in self.eng_play.options
                                        try:
                                            if has_mpv:
                                                info = self.eng_play.analyse(search_board, assassin_limit, multipv=5)
                                            else:
                                                info = [self.eng_play.analyse(search_board, assassin_limit)]
                                        except Exception:
                                            info = [self.eng_play.analyse(search_board, assassin_limit)]
                                        
                                        if info:
                                            best_eval = info[0]["score"].pov(search_board.turn).score(mate_score=10000)
                                            chosen_move = info[0]["pv"][0] 
                                            
                                            violent_options = []
                                            shortest_mate = 999999
                                            
                                            for line in info:
                                                if "pv" not in line or not line["pv"]: continue
                                                cand_move = line["pv"][0]
                                                cand_score = line["score"].pov(search_board.turn)
                                                cand_eval = cand_score.score(mate_score=10000)
                                                
                                                if cand_score.is_mate() and cand_score.mate() > 0:
                                                    if cand_score.mate() < shortest_mate:
                                                        shortest_mate = cand_score.mate()
                                                        chosen_move = cand_move
                                                    continue
                                                
                                                if shortest_mate < 999999: continue 
                                                
                                                if best_eval is not None and cand_eval is not None:
                                                    if (best_eval - cand_eval) <= 40:
                                                        search_board.push(cand_move)
                                                        is_check = search_board.is_check()
                                                        search_board.pop()
                                                        is_capture = search_board.is_capture(cand_move)
                                                        
                                                        if is_check:
                                                            violent_options.append((cand_move, 2, cand_eval))
                                                        elif is_capture:
                                                            violent_options.append((cand_move, 1, cand_eval))
                                            
                                            if violent_options and shortest_mate == 999999:
                                                violent_options.sort(key=lambda x: (x[1], x[2]), reverse=True)
                                                chosen_move = violent_options[0][0]
                                                
                                            move = chosen_move
                                        
                                        # RULE 3: STRICT 1-SECOND DELAY
                                        elapsed = time.time() - start_think
                                        if elapsed < 1.0:
                                            time.sleep(1.0 - elapsed)
                                    else:
                                        res = self.eng_play.play(search_board, limit)
                                        move = res.move
                                        
                                    if time.time() - start < 1.0: time.sleep(random.uniform(0.8, 1.5) - (time.time() - start))
                                    self.engine_crash_count = 0 
                                except chess.IllegalMoveError as e:
                                    print(f"Bot Move Error (Illegal): {e}")
                                    if self.eng_play:
                                        try: self.eng_play.quit()
                                        except: pass
                                    self.eng_play = None
                                except Exception as e:
                                    print(f"Bot Play Error: {e}")
                                    if self.eng_play:
                                        try: self.eng_play.quit()
                                        except: pass
                                    self.eng_play = None
                    # 5. FALLBACK: Random Move
                    if not move:
                        if list(search_board.legal_moves): 
                            move = random.choice(list(search_board.legal_moves))
                            self.status_msg = "Bot (Random) Moved"
                            time.sleep(1.0)
                    if move:
                        # --- WE REMOVED THE OLD CHAT LOGIC FROM HERE ---
                        self.ui_queue.append(("move", move))
                        self.status_msg = "Your Turn"
                        
                time.sleep(0.1)
            except Exception as e: 
                print(f"Task Play Loop Error: {e}")
                time.sleep(1)
    def finish_promotion(self, move):
        self.apply_move(move)
    def apply_move(self, move):
        with self.lock:
            try:
                # 1. Basic Legality Check
                if move not in self.board.legal_moves: 
                    return 
                # 2. TRAINER MODE VALIDATION
                if self.mode == "trainer":
                    if self.trainer_idx >= len(self.trainer_moves):
                        return 
                    
                    expected_move = self.trainer_moves[self.trainer_idx]
                    
                    if move != expected_move:
                        # 3 Chances Logic
                        if not hasattr(self, 'trainer_wrong_attempts'):
                            self.trainer_wrong_attempts = 0
                        self.trainer_wrong_attempts += 1
                        chances_left = 3 - self.trainer_wrong_attempts
                        
                        self.sound_manager.play("error")
                        
                        if getattr(self, 'is_tutorial', False):
                            self.add_chat("Trainer", "Follow the arrow to learn the line!")
                            self.trainer_hint_arrow = expected_move # Ensure it stays visible
                        else:
                            if chances_left > 0:
                                self.add_chat("Trainer", f"Incorrect move! {chances_left} chances left.")
                            else:
                                self.add_chat("Trainer", "Out of chances! Follow the arrow.")
                                self.trainer_hint_arrow = expected_move
                            
                        return # Strictly reject move, do not proceed
                    else:
                        # CORRECT MOVE
                        self.trainer_idx += 1
                        self.trainer_hint_arrow = None 
                        self.trainer_wrong_attempts = 0 # Reset attempts for next move
                        
                        if self.trainer_idx == len(self.trainer_moves):
                            self.add_chat("Trainer", "Practice sequence completed !!")
                            self.sound_manager.play("win")
                            self.trainer_complete_popup = TrainerCompletePopup(self) 
                # 3. Promotion Logic Check
                if not move.promotion and self.logic:
                    check = self.logic.validate_move(move.from_square, move.to_square)
                    if check == "PROMOTION_NEEDED":
                         self.promo_popup = PromotionPopup(self, self.board.turn, move.from_square, move.to_square)
                         return
                # 4. Puzzle Logic Check
                if self.mode == "puzzle" and self.board.turn == self.playing_white:
                    is_good, best_move = self.validate_puzzle_move(move)
                    
                    if not is_good:
                        # Increment wrong attempts
                        self.puzzle_wrong_attempts += 1
                        chances_left = 3 - self.puzzle_wrong_attempts
                        
                        self.sound_manager.play("lose")
                        
                        if chances_left > 0:
                            self.add_chat("Puzzle", f"Incorrect! {chances_left} chances left.")
                        else:
                            # 3 Strikes: Show Hint Arrow
                            self.add_chat("Puzzle", "Out of chances! Follow the arrow.")
                            if best_move:
                                # Activates the "Trainer" dashed arrow
                                self.trainer_hint_arrow = best_move 
                        return 
                    
                    # If move is correct:
                    self.trainer_hint_arrow = None # Clear any hint arrows
                # 5. Apply the Move
                board_before = self.board.copy()
                prev_eval_cp = getattr(self, 'eval_val', 0)
                is_capture = self.board.is_capture(move)
                is_ep = self.board.is_en_passant(move)
                is_castle = self.board.is_castling(move)
                
                # =================================================================
                # --- NEW TACTICAL VISION EVENT GENERATOR & CENTRALIZED CHAT ---
                # =================================================================
                if getattr(self, 'active_bot', None) and getattr(self, 'logic', None):
                    try:
                        print(f"\n[🧠 BRAIN TRIGGERED] Analyzing move: {move}")
                        tactical_event = self.logic.analyze_tactical_event(move)
                        print(f"[👁️ VISION] Tactic spotted: {tactical_event}")
                        
                        chat_event = "move"
                        sub_event = ""
                        
                        if tactical_event == "checkmate": chat_event = "checkmate"
                        elif tactical_event in ["check", "double_check"]: chat_event = "check"
                        elif tactical_event == "discovered_check": chat_event = "check"; sub_event = "check_discovered"
                        elif tactical_event in ["fork", "pin", "skewer"]: chat_event = "tactic"; sub_event = tactical_event
                        elif tactical_event == "capture": 
                            chat_event = "capture"
                            target = self.board.piece_at(move.to_square)
                            if target and target.piece_type == chess.QUEEN: sub_event = "capture_queen"
                            elif target: sub_event = f"capture_{chess.piece_name(target.piece_type)}"
                        elif tactical_event == "castle": chat_event = "castle"
                        elif tactical_event == "promote": chat_event = "promotion"
                        
                        # Fallbacks if tactical_event missed a basic capture/castle
                        if chat_event == "move":
                            if is_capture: chat_event = "capture"
                            if is_castle: chat_event = "castle"
                        phase = "middlegame"
                        if getattr(self, 'analyzer', None): phase = self.analyzer.get_game_phase(self.board)
                        # Build the Brain Context
                        chat_context = {
                            "bot_name": self.active_bot.get("name"),
                            "style": self.active_bot.get("style", "GM"),
                            "elo": self.active_bot.get("elo", 1200),
                            "event": chat_event,
                            "sub_event": sub_event,
                            "eval": prev_eval_cp,
                            "opening": getattr(self, 'opening_name', None),
                            "phase": phase,
                            "material": getattr(self.logic, 'material_advantage', 0),
                            "is_white": not getattr(self, 'playing_white', True)
                        }
                        import bot_personalities
                        voice_line = bot_personalities.get_bot_chat(chat_context)
                        
                        print(f"[VOICE LINE] Generated: {voice_line}")
                        
                        if voice_line:
                            if hasattr(self, 'ui_queue'):
                                self.ui_queue.append(("chat", (self.active_bot["name"], voice_line)))
                            
                            # --- BRUTE FORCE THE QUEUE HANDOFF ---
                            try:
                                self.speech_queue.put((voice_line, self.active_bot["name"]))
                                print(f"[QUEUE] Successfully pushed to speech_queue!")
                            except AttributeError:
                                print(f"[FATAL ERROR] The speech_queue is missing from this class!")
                        else:
                            print("[!] Voice line returned None.")
                            
                    except Exception as e:
                        print(f"[TACTICAL ERROR] {e}")
                # =================================================================
                if self.logic: 
                    self.logic.apply_move(move)
                    self.board = self.logic.board # <-- FIX: Forces UI board to sync with Logic board
                else: 
                    self.board.push(move)
                
                try: san = board_before.san(move)
                except: san = str(move)
                self.history.append({
                    "move": move, 
                    "san": san, 
                    "fen": self.board.fen(),
                    "ply": self.board.ply()  # FIX: Crucial for accurate Review Stats!
                })
                self.view_ply = self.board.ply()
                
                # --- NEW: Check Tablebase if 7 or fewer pieces remain ---
                if len(self.board.piece_map()) <= 7:
                    threading.Thread(
                        target=lambda: setattr(self, 'tb_data', self.tablebase.get_evaluation(self.board)), 
                        daemon=True
                    ).start()
                else:
                    self.tb_data = None
                    
                # Clear UI artifacts on successful move
                self.user_arrows = []
                self.temp_arrow_start = None 
                self.last_move_analysis = None # <-- FIX: Clear stale analysis immediately!
                
                if self.analyzer and self.analyzer.is_active:
                    # --- FIX: Capture the actual best move BEFORE pushing the new board state ---
                    current_best_move = None
                    if getattr(self, 'arrows', None) and len(self.arrows) > 0:
                        try: current_best_move = chess.Move(self.arrows[0][0][0], self.arrows[0][0][1])
                        except Exception: pass
                        
                    # --- FIX: Create an isolated snapshot for the thread ---
                    board_after_snapshot = self.board.copy()
                    threading.Thread(target=self.live_classify_thread, args=(move, board_before, board_after_snapshot, prev_eval_cp, current_best_move), daemon=True).start()
                
                # Sounds
                if self.board.is_checkmate():
                    if self.mode_idx == 1: self.sound_manager.play("lose" if self.board.turn == self.playing_white else "win")
                    else: self.sound_manager.play("check_mate")
                    if self.mode == "puzzle": self.handle_puzzle_complete()
                elif self.board.is_game_over(): 
                    self.sound_manager.play("draw")
                    if self.mode == "puzzle": self.handle_puzzle_complete() 
                elif self.board.is_check(): self.sound_manager.play("check") 
                elif is_ep: self.sound_manager.play("en_passant")
                elif is_capture: self.sound_manager.play("capture")
                elif is_castle: self.sound_manager.play("castle")
                else: self.sound_manager.play("move_opponent" if self.board.turn == self.playing_white else "move_self")
                
                if self.board.is_repetition(3): self.sound_manager.play("draw_repetition")
                if self.mode == "puzzle": self.check_puzzle_status()
            
            except Exception as e: print(f"Move Error: {e}")
        # --- NEW: Trigger next arrow in Tutorial mode immediately! ---
        if getattr(self, 'mode', None) == "trainer" and getattr(self, 'is_tutorial', False):
            if hasattr(self, 'trainer_idx') and self.trainer_idx < len(self.trainer_moves):
                is_bot_turn = (self.board.turn == chess.WHITE and not self.playing_white) or \
                              (self.board.turn == chess.BLACK and self.playing_white)
                if not is_bot_turn:
                    self.trainer_hint_arrow = self.trainer_moves[self.trainer_idx]
                    
        self.update_opening_label()
    
    def validate_puzzle_move(self, move):
        if not self.analyzer or not self.analyzer.is_active: return True, None
        try:
            cp, txt, arrows = self.analyzer.analyze_live(self.board)
            if not arrows: return True, None
            best_move = arrows[0][0]
            if move == best_move: return True, best_move
            return False, best_move
        except: return True, None
        
    def check_puzzle_status(self):
        if self.board.is_checkmate():
            self.handle_puzzle_complete()
            return
        if self.logic and hasattr(self, 'puzzle_start_material'):
            current_mat = self.logic.material_advantage
            start_mat = self.puzzle_start_material
            gain = current_mat - start_mat if self.playing_white else start_mat - current_mat
            if gain >= 3 and not self.board.is_check():
                 if self.board.ply() > self.puzzle_start_ply:
                     self.handle_puzzle_complete()
    def handle_puzzle_complete(self):
        self.ui_queue.append(("chat", ("System", "Puzzle Solved!")))
        self.sound_manager.play("win")
        if self.active_puzzle:
            self.assets.solve_puzzle(self.active_puzzle)
            self.active_puzzle = None
            
    def delete_archived_game(self, game_id):
        """Deletes a game from the archive and recalculates Elo."""
        with self.lock:
            # 1. Remove from ledger
            self.match_ledger = [g for g in self.match_ledger if g.get("id") != game_id]
            
            # 2. Delete the actual PGN file if it exists
            pgn_path = os.path.join(self.archive_dir, f"{game_id}.pgn")
            if os.path.exists(pgn_path):
                try: os.remove(pgn_path)
                except Exception as e: print(f"File delete error: {e}")
                
            # 3. Save updated ledger
            with open(self.ledger_path, "w", encoding="utf-8") as f:
                json.dump(self.match_ledger, f, indent=4)
                
            # 4. Recalculate Global Elo
            self.recalculate_global_elo()
    def load_archived_game_to_ui(self, game_id):
        """Loads a saved game from the Profile Archive directly to the board."""
        import os
        pgn_path = os.path.join(self.archive_dir, f"{game_id}.pgn")
        
        if os.path.exists(pgn_path):
            # Use smart loader to respect existing annotations/evaluations
            try:
                # smart_load_pgn will prompt if the PGN already contains eval tags
                self.smart_load_pgn(pgn_path)
            except Exception:
                # Fallback to direct load if smart loader fails
                self.load_pgn_file(pgn_path)
            self.sound_manager.play("game_start")
            self.add_chat("System", f"Loaded archived game: {game_id}")
        else:
            print(f"Error: Archive file not found at {pgn_path}")
    def load_pgn_file(self, path, offset=0):
        """Standard deep analysis loader. Loads directly to board."""
        self.current_pgn_path = path
        try:
            with open(path, "r", encoding="utf-8") as f:
                f.seek(offset)
                g = chess.pgn.read_game(f)
            if g:
                self.trigger_auto_analysis(g)
        except Exception as e: print(f"Load Error: {e}")
    def smart_load_pgn(self, path, offset=0):
        """Checks for LucasChess evaluations before loading."""
        self.current_pgn_path = path
        try:
            with open(path, "r", encoding="utf-8") as f:
                f.seek(offset)
                g = chess.pgn.read_game(f)
            if not g: return
            
            # Look for existing eval tags (LucasChess)
            has_eval = any("[%eval" in node.comment for node in g.mainline() if node.comment)
            
            if has_eval:
                # Trigger the Yes/No prompt popup
                self.active_popup = AnalyzePromptPopup(self, path, offset=offset)
            else:
                # Normal file, load directly to board
                self.trigger_auto_analysis(g)
        except Exception as e: print(f"Smart Load Error: {e}")
    def recalculate_global_elo(self):
        """Rebuilds the user's Elo from scratch using the current ledger."""
        base_elo = 400 # Base Elo set to 400 for fresh players
        current_elo = base_elo
        elo_history = [base_elo]
        
        # Sort chronologically to replay the rating changes
        sorted_ledger = sorted(self.match_ledger, key=lambda x: x.get("date", ""))
        
        for game in sorted_ledger:
            change = game.get("elo_change", 0)
            current_elo += change
            elo_history.append(current_elo)
            
        # Update settings.json
        self.player_elo = current_elo
        self.settings["player_elo"] = current_elo
        self.settings["elo_history"] = elo_history
        self.save_config() # <--- FIXED NAME HERE
        
    def start_smart_import(self, path, user_color, offset=0):
        """Spins up a background thread to process massive pre-evaluated PGNs."""
        self.import_status = f"Initializing import ({user_color.capitalize()})..."
        t = threading.Thread(target=self._smart_import_worker, args=(path, user_color, offset), daemon=True)
        t.start()
    def _smart_import_worker(self, path, user_color, offset):
        try:
            # Check if analyzer is available
            if not self.analyzer:
                self.import_status = "Error: Engine not loaded. Cannot analyze."
                time.sleep(2)
                self.import_status = ""
                return
                
            with open(path, "r", encoding="utf-8") as f:
                f.seek(offset) # <--- FIX: Jump to the correct game!
                game = chess.pgn.read_game(f)
                
            if not game:
                self.import_status = "Error: Invalid PGN file."
                time.sleep(2)
                self.import_status = ""
                return
            opponent_name = game.headers.get("Black" if user_color == "white" else "White", "Unknown")
            
            # --- FIX 1: Safe Date Handling ---
            # Avoids the 'datetime' NameError and uses your requested "-" fallback
            date_played = game.headers.get("Date", "-")
            if "?" in date_played or date_played.strip() == "":
                date_played = "-"
            
            # Count total moves for the progress bar
            mainline = list(game.mainline())
            total_moves = len(mainline)
            
            evals = []
            
            # --- FIX 2: Safely Parse Decimals AND Mate Evals ---
            for i, node in enumerate(mainline):
                self.import_status = f"Reading evaluations... {int((i/total_moves)*40)}%"
                
                comment = node.comment
                eval_cp = None
                
                import re
                eval_match = re.search(r'\[%eval\s+([+-]?\d+\.?\d*)\]', comment)
                mate_match = re.search(r'\[%eval\s+([+-]?[#M]+\d+)\]', comment)
                
                if eval_match:
                    val = float(eval_match.group(1))
                    eval_cp = int(val * 100) # Convert to centipawns
                elif mate_match:
                    # Catch LucasChess Mates like [%eval -M4]
                    m_str = mate_match.group(1)
                    if m_str.startswith("-"): eval_cp = -9000  # Black mating
                    else: eval_cp = 9000  # White mating
                else:
                    # FALLBACK: Safely ask the live analyzer
                    if hasattr(self, 'analyzer') and self.analyzer and self.analyzer.is_active:
                         cp, _, _ = self.analyzer.analyze_live(node.board())
                         eval_cp = cp
                    else:
                         eval_cp = 0 
                
                evals.append(eval_cp)
            # --- 3. CALCULATE ACCURACY & ANNOTATIONS ---
            self.import_status = f"Generating Annotations & Accuracy... 60%"
            
            if hasattr(self, 'analyzer') and self.analyzer:
                stats = self.analyzer.calculate_game_stats(evals, mainline, user_color)
                accuracy = stats.get("accuracy", 0.0)
                perf_elo = stats.get("performance_elo", getattr(self, 'player_elo', 400))
            else:
                accuracy = 85.0 
                perf_elo = getattr(self, 'player_elo', 400)
            # Calculate Elo reward/penalty
            elo_diff = perf_elo - getattr(self, 'player_elo', 400)
            elo_change = max(-30, min(30, int(elo_diff * 0.1))) 
            # --- 4. SAVE & UPDATE LEDGER ---
            self.import_status = f"Saving to Archive... 95%"
            game_id = f"import_{int(time.time())}"
            
            # --- FIX: Re-export the freshly parsed game so we convert their annotations ---
            # into our custom [%class] tags for the PNG icons to read later!
            archive_path = os.path.join(self.archive_dir, f"{game_id}.pgn")
            with open(archive_path, "w", encoding="utf-8") as f:
                f.write(self.logic.export_pgn(
                    history=self.history, 
                    white_name=game.headers.get("White", "Unknown"), 
                    black_name=game.headers.get("Black", "Unknown")
                ))
            new_entry = {
                "id": game_id,
                "date": date_played,
                "opponent": opponent_name,
                "user_color": user_color,
                "accuracy": accuracy,
                "est_elo": perf_elo,
                "elo_change": elo_change
            }
            
            with self.lock:
                self.match_ledger.append(new_entry)
                with open(self.ledger_path, "w", encoding="utf-8") as f:
                    json.dump(self.match_ledger, f, indent=4)
                if hasattr(self, 'recalculate_global_elo'):
                    self.recalculate_global_elo()
                
            self.import_status = "Import Complete!"
            time.sleep(2)
            self.import_status = ""
            
        except Exception as e:
            self.import_status = f"Import Failed: {e}"
            print(f"Import Error: {e}")
            time.sleep(3)
            self.import_status = ""
            
    def auto_archive_bot_game(self, stats, ratings):
        """
        Silently saves a completed bot game to the Archive and Ledger 
        after the Review calculation is finished.
        """
        if self.mode != "play" or not self.active_bot or len(self.history) < 2:
            return
        import time
        game_id = f"bot_match_{int(time.time())}"
        
        # FIX: Avoids the 'datetime' dependency crash entirely
        date_played = time.strftime("%Y.%m.%d")
        
        opponent = self.active_bot.get("name", "Bot")
        user_color = "white" if self.playing_white else "black"
        
        accuracy = stats.get(user_color, {}).get("acc", 0)
        perf_elo = ratings.get(user_color, getattr(self, 'player_elo', 400))
        
        # --- FIX: Strict Win/Loss/Draw/Abandon Elo Logic ---
        bot_elo = self.active_bot.get("elo", 1200)
        p_elo = getattr(self, 'player_elo', 400)
        
        # FIX: Safe Elo check for GM bots ("Book")
        if isinstance(bot_elo, str):
            bot_elo = 2800 # Assume Grandmaster level if it's a book bot
            
        # Standard Elo Probability Math
        expected_win = 1 / (1 + 10 ** ((bot_elo - p_elo) / 400.0))
        
        if not self.board.is_game_over():
            # 1. ABANDONED GAME = Treated as a Loss
            elo_change = int(32 * (0.0 - expected_win))
            if elo_change >= 0: elo_change = -5 
        else:
            result = self.board.result()
            if result == "1/2-1/2":
                # 2. DRAW = Exactly 0 points change
                elo_change = 0
            else:
                user_won = (result == "1-0" and self.playing_white) or (result == "0-1" and not self.playing_white)
                
                if user_won:
                    # 3. WIN = Calculate standard Elo gain
                    elo_change = int(32 * (1.0 - expected_win))
                    if elo_change <= 0: elo_change = 5  # Guarantee minimum gain
                else:
                    # 4. LOSS = Calculate standard Elo loss
                    elo_change = int(32 * (0.0 - expected_win))
                    if elo_change >= 0: elo_change = -5 # Guarantee minimum loss
        # ------------------------------------------------
        
        import os
        import json
        
        pgn_path = os.path.join(self.archive_dir, f"{game_id}.pgn")
        try:
            with open(pgn_path, "w", encoding="utf-8") as f:
                w_name = "Player" if self.playing_white else opponent
                b_name = opponent if self.playing_white else "Player"
                
                # --- FIX: Pass self.history so evaluations/annotations are permanently archived! ---
                f.write(self.logic.export_pgn(history=self.history, white_name=w_name, black_name=b_name))
                
        except Exception as e:
            print(f"Archive Export Error: {e}")
            return
        new_entry = {
            "id": game_id,
            "date": date_played,
            "opponent": opponent,
            "user_color": user_color,
            "accuracy": accuracy,
            "est_elo": perf_elo,
            "elo_change": elo_change
        }
        
        with self.lock:
            if any(g.get("id") == game_id for g in self.match_ledger):
                return 
                
            self.match_ledger.append(new_entry)
            with open(self.ledger_path, "w", encoding="utf-8") as f:
                json.dump(self.match_ledger, f, indent=4)
                
            if hasattr(self, 'recalculate_global_elo'):
                self.recalculate_global_elo()
    def live_classify_thread(self, move, board_before, board_after, prev_eval_cp, best_move_before=None):
        """Background thread to classify moves without blocking the UI."""
        try:
            if not self.analyzer or not self.analyzer.is_active: return
            
            # --- FIX: Grab the properly formatted string (M2, +1.5, etc) directly from the engine! ---
            curr_eval_cp, curr_eval_txt, _ = self.analyzer.analyze_live(board_after)
            
            # 2. Pass the snapshot to the classifier with the CORRECT best move from board_before
            classification = self.analyzer.classify_move(move, board_before, board_after, prev_eval_cp, curr_eval_cp, best_move_before)
            complexity = self.analyzer.get_position_complexity(board_before)
            
            # 3. Safely merge results back into the main thread data
            with self.lock: 
                self.last_move_analysis = {"sq": move.to_square, "class": classification, "time": time.time()}
                
                if self.history and self.history[-1]["move"] == move:
                    self.history[-1]["review"] = {
                        "class": classification,
                        "eval_str": curr_eval_txt if classification != "book" else "", # <-- FIXED
                        "eval_cp": curr_eval_cp,
                        "depth": getattr(self.analyzer, 'current_depth', 0)
                    }
            
            # 4. Trigger bot trash-talk for blunders
            if self.mode == "play" and bot_personalities and getattr(self, 'active_bot', None) and classification in ["blunder", "miss"]:
                # --- FIX: Add missing 'bot_name' to context so the voice engine knows who is speaking ---
                context = {
                    "bot_name": self.active_bot.get("name", "System"),
                    "style": self.active_bot.get("style", "Blunder Master"), 
                    "event": classification, 
                    "eval": curr_eval_cp, 
                    "is_white": not self.playing_white, 
                    "complexity": complexity
                }
                msg = bot_personalities.get_bot_chat(context)
                if msg:
                    self.ui_queue.append(("chat", (self.active_bot["name"], msg)))
                    if self.settings.get("speech", True): self.ui_queue.append(("speak", msg))
                    
        except Exception as e:
            print(f"Live classification thread error safely caught: {e}")
    def add_chat(self, sender, msg):
        self.chat_log.append({"sender": sender, "msg": msg})
        if len(self.chat_log) > 5: self.chat_scroll = (len(self.chat_log)-5)*60
        
    def get_captured_pieces(self):
        initial = {chess.PAWN: 8, chess.KNIGHT: 2, chess.BISHOP: 2, chess.ROOK: 2, chess.QUEEN: 1}
        w_curr = {p: 0 for p in initial}; b_curr = {p: 0 for p in initial}
        for sq in chess.SQUARES:
            p = self.board.piece_at(sq)
            if p and p.piece_type != chess.KING:
                if p.color == chess.WHITE: w_curr[p.piece_type] += 1
                else: b_curr[p.piece_type] += 1
        
        w_captured, b_captured, w_val, b_val = [], [], 0, 0
        for p, count in initial.items():
            val = PIECE_VALS.get(p, 0)
            diff_w = count - w_curr[p]
            if diff_w > 0: w_captured.extend([p] * diff_w); b_val += (diff_w * val)
            diff_b = count - b_curr[p]
            if diff_b > 0: b_captured.extend([p] * diff_b); w_val += (diff_b * val)
            
        w_captured.sort(key=lambda x: PIECE_VALS.get(x, 0))
        b_captured.sort(key=lambda x: PIECE_VALS.get(x, 0))
        return w_captured, b_captured, w_val, b_val
    def start_trainer(self, training_data, play_as_white=True, is_tutorial=False):
        self.playing_white = play_as_white
        self.is_tutorial = is_tutorial
        self.handle_ui("reset_internal") # Reset to empty start
        
        if "moves" in training_data:
            parsed_moves = []
            for m in training_data["moves"]:
                if isinstance(m, str):
                    try: parsed_moves.append(chess.Move.from_uci(m))
                    except: pass
                else:
                    parsed_moves.append(m)
            
            self.trainer_moves = parsed_moves
            self.trainer_idx = 0
            self.mode = "trainer"
            self.opening_name = training_data.get("name", "Practice Line")
            
            practice_type = training_data.get("type", "opening")
            mode_str = "Tutorial" if self.is_tutorial else "Practice"
            self.status_msg = f"Trainer: {self.opening_name} ({mode_str})"
            self.add_chat("Trainer", f"{mode_str}: {self.opening_name}. You are {('White' if self.playing_white else 'Black')}.")
            
            # --- NEW: Immediately show the hint arrow if it's player's turn in Tutorial! ---
            if self.is_tutorial and self.trainer_moves:
                is_bot_turn = (self.board.turn == chess.WHITE and not self.playing_white) or \
                              (self.board.turn == chess.BLACK and self.playing_white)
                if not is_bot_turn:
                    self.trainer_hint_arrow = self.trainer_moves[self.trainer_idx]
            
            # Log to Practice History
            import time, json
            new_entry = {
                "id": f"prac_{int(time.time())}",
                "name": self.opening_name,
                # --- FIX: Detailed Local PC Date and Time ---
                "date": time.strftime("%d %b %Y, %I:%M %p"), 
                "color": "white" if self.playing_white else "black",
                "type": practice_type,
                "mode": mode_str, 
                "moves": training_data["moves"]
            }
            
            with self.lock:
                self.practice_ledger.insert(0, new_entry)
                if len(self.practice_ledger) > 100: self.practice_ledger = self.practice_ledger[:100]
                try:
                    with open(self.practice_ledger_path, "w", encoding="utf-8") as f:
                        json.dump(self.practice_ledger, f, indent=4)
                except Exception as e: print(f"Practice Ledger Save Error: {e}")
                
        else:
            self.add_chat("Trainer", "Error: No move data found.")
            self.mode = "play"
    
    def start_puzzle(self, puzzle):
        self.ui_queue = []
        with self.lock:
            self.handle_ui("reset_internal")
            try:
                self.logic.load_fen(puzzle["fen"])
                self.board = self.logic.board
                self.view_ply = self.board.ply() # Sync view
                
                self.active_puzzle = puzzle
                self.puzzle_start_ply = self.board.ply()
                self.puzzle_start_material = self.logic.material_advantage if self.logic else 0
                
                # --- NEW: Reset Attempts ---
                self.puzzle_wrong_attempts = 0 
                
                self.playing_white = (self.board.turn == chess.WHITE)
                turn_str = "White to Move" if self.playing_white else "Black to Move"
                
                if puzzle["name"] == "Unknown Puzzle" and self.analyzer:
                    new_name = self.analyzer.generate_puzzle_name(self.board)
                    puzzle["name"] = new_name
                    self.active_puzzle["name"] = new_name
                    self.assets.rename_puzzle(puzzle, new_name)
                    self.add_chat("System", f"Auto-Named: {new_name}")
                
                self.opening_name = puzzle["name"]
                self.mode = "puzzle"
                
                self.status_msg = f"Puzzle: {turn_str}"
                self.add_chat("System", f"Loaded: {puzzle['name']}")
                
                # --- NEW: Message with Chances ---
                self.add_chat("Trainer", f"{turn_str}! (3 chances left)") 
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load puzzle: {e}")
    def trigger_auto_analysis(self, game):
        self.board.reset(); self.history = []; self.view_ply = 0; self.pgn_headers = dict(game.headers)
        self.cached_review = None
        try:
             if "Engine" in game.headers: self.logic.pgn_metadata["Engine"] = game.headers["Engine"]
        except: pass
        # --- FIX: Preserve existing evals, format correctly, and infer missing annotations ---
        prev_eval_cp = 20 # Standard starting eval bias
        
        for node in game.mainline():
            move = node.move
            san = self.board.san(move)
            self.board.push(move)
            if self.logic: self.logic.apply_move(move)
            
            review_data = {}
            comment = node.comment
            curr_eval_cp = None
            
            if comment:
                eval_match = re.search(r"\[%eval\s([+-]?\d+\.?\d*)\]", comment)
                mate_match = re.search(r"\[%eval\s+([+-]?[#M]+\d+)\]", comment)
                class_match = re.search(r"\[%class\s(\w+)\]", comment)
                effect_match = re.search(r"\[%c_effect\s+.*?;type;([a-zA-Z]+)", comment)
                
                if eval_match:
                    try: 
                        curr_eval_cp = float(eval_match.group(1)) * 100
                        review_data["eval_str"] = f"{curr_eval_cp/100.0:+.2f}"
                    except: pass
                elif mate_match:
                    m_str = mate_match.group(1).replace("#", "M")
                    if not m_str.startswith("-") and not m_str.startswith("+"): m_str = "+" + m_str
                    if m_str.startswith("+M"): m_str = m_str.replace("+M", "M+")
                    elif m_str.startswith("-M"): m_str = m_str.replace("-M", "M-")
                    review_data["eval_str"] = m_str
                    curr_eval_cp = 9000 if "M+" in m_str else -9000
                
                if curr_eval_cp is not None:
                    review_data["eval_cp"] = curr_eval_cp
                # 1. Map Explicit Text Annotations
                if class_match: 
                    review_data["class"] = class_match.group(1).lower()
                elif effect_match:
                    eff = effect_match.group(1).lower()
                    if "great" in eff: review_data["class"] = "great"
                    elif "brilliant" in eff: review_data["class"] = "brilliant"
                    elif "blunder" in eff: review_data["class"] = "blunder"
                    elif "mistake" in eff: review_data["class"] = "mistake"
                    elif "inaccuracy" in eff: review_data["class"] = "inaccuracy"
                    elif "excellent" in eff: review_data["class"] = "excellent"
                    elif "good" in eff: review_data["class"] = "good"
                    elif "best" in eff: review_data["class"] = "best"
                    elif "miss" in eff: review_data["class"] = "miss"
                    elif "book" in eff: review_data["class"] = "book"
            # 2. Map Standard External NAGs (!, ?, !?) to Colored Text Symbols!
            # (If it has a [%class], we skip this so it loads our PNG icon instead)
            if "class" not in review_data and node.nags:
                nag_symbol_map = {1: "!", 2: "?", 3: "!!", 4: "??", 5: "!?", 6: "?!"}
                nag_class_map = {1: "good", 2: "mistake", 3: "brilliant", 4: "blunder", 5: "excellent", 6: "inaccuracy"}
                for nag in node.nags:
                    if nag in nag_symbol_map:
                        review_data["nag_symbol"] = nag_symbol_map[nag]
                        review_data["nag_class"] = nag_class_map[nag] # Saves the type for color lookup
                        break
                        
            # 3. AUTO-INFER CLASSES IF ONLY RAW SCORES ARE PRESENT
            # Only infer an icon if there is absolutely NO class and NO text annotation present!
            if "class" not in review_data and "nag_symbol" not in review_data and curr_eval_cp is not None:
                is_white_move = not self.board.turn 
                diff = curr_eval_cp - prev_eval_cp
                move_val = diff if is_white_move else -diff
                
                if move_val <= -300: review_data["class"] = "blunder"
                elif move_val <= -100: review_data["class"] = "mistake"
                elif move_val <= -40: review_data["class"] = "inaccuracy"
                elif move_val >= 50: review_data["class"] = "good"
                
            if curr_eval_cp is not None:
                prev_eval_cp = curr_eval_cp
            step = {
                "move": move, 
                "san": san, 
                "fen": self.board.fen(), 
                "ply": node.ply(),
                "clock": node.clock(), 
                "review": review_data
            }
            if node.nags:
                step["nags"] = list(node.nags)
                
            self.history.append(step)
        # Drop to Manual mode
        self.view_ply = len(self.history); self.update_opening_label()
        self.mode = "manual"
        self.mode_idx = 0
        self.active_bot = None
        self.status_msg = "Game Loaded (Manual Mode)."
        if game.headers.get("Date"): self.status_msg += f" Date: {game.headers['Date']}"
    def update_pgn_metadata(self, time, depth, engine_name):
        self.logic.pgn_metadata["TimePerMove"] = time
        self.logic.pgn_metadata["Depth"] = depth
        self.logic.pgn_metadata["Engine"] = engine_name
    # --- UI HANDLING ---
    def handle_click(self, pos, event_type="down"):
        for popup in [self.side_popup, self.save_popup, self.promo_popup, self.pgn_popup, 
                      self.gm_move_popup, self.bot_popup, self.review_popup, self.active_popup, 
                      self.settings_popup, self.trainer_popup, self.engine_popup, 
                      self.phase_popup, self.profile_popup, self.puzzle_popup, self.save_brilliant_popup,
                      self.trainer_complete_popup, self.account_popup]: # <-- ADDED account_popup
            if popup and popup.active:
                if hasattr(popup, 'handle_scroll') and event_type == "down": 
                    popup.handle_scroll(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos)) 
                if event_type == "down" and pygame.mouse.get_pressed()[0]: 
                    popup.handle_click(pos)
                elif hasattr(popup, 'handle_input') and event_type == "down":
                    pass 
                return
        for r, ply in self.move_click_zones:
            if r.collidepoint(pos):
                self.view_ply = ply; self.selected = None; self.valid_moves = []; self.arrows = []; self.update_opening_label(); return
        if self.view_ply != self.board.ply(): return
        x, y = pos
        
        # Board Check
        if 0 <= x - self.bd_x <= self.bd_sz and 0 <= y - self.bd_y <= self.bd_sz:
            c, r = (x - self.bd_x)//self.sq_sz, (y - self.bd_y)//self.sq_sz
            if self.playing_white: r = 7 - r
            else: c = 7 - c
            sq = chess.square(c, r)
            # RIGHT CLICK (ARROWS) - CRITICAL FIX HERE
            # We check if button is pressed OR if we are finishing a drag (event_type='up' & start!=None)
            if pygame.mouse.get_pressed()[2] or (event_type == "up" and self.right_click_start is not None):
                if event_type == "down":
                    self.right_click_start = sq
                    self.temp_arrow_start = sq 
                    self.temp_arrow_end = sq
                elif event_type == "up" and self.right_click_start is not None:
                    # Finalize arrow
                    if self.right_click_start != sq:
                        arrow = (self.right_click_start, sq)
                        if arrow in self.user_arrows: self.user_arrows.remove(arrow)
                        else: self.user_arrows.append(arrow)
                    else:
                        # Clicked on a square (no drag)
                        # PASS because user requested "do not disappear"
                        pass 
                    
                    self.right_click_start = None
                    self.temp_arrow_start = None
                    self.temp_arrow_end = None
                return
            # LEFT CLICK (MOVE)
            if event_type == "down":
                # --- NEW: Instantly clear all arrows on left click! ---
                self.user_arrows = []
                self.temp_arrow_start = None
                self.temp_arrow_end = None
                
                if self.selected is not None and sq != self.selected:
                    move = chess.Move(self.selected, sq)
                    is_legal_basic = move in self.board.legal_moves
                    if not is_legal_basic:
                        move_q = chess.Move(self.selected, sq, promotion=chess.QUEEN)
                        if move_q in self.board.legal_moves:
                            self.promo_popup = PromotionPopup(self, self.board.turn, self.selected, sq)
                            self.selected = None; self.valid_moves = []; return
                    if is_legal_basic:
                        self.apply_move(move)
                        self.selected = None; self.valid_moves = []; return
                
                p = self.board.piece_at(sq)
                if p and p.color == self.board.turn:
                    self.dragging_piece = (p, sq)
                    self.drag_pos = pos
                    self.selected = sq
                    self.valid_moves = [m for m in self.board.legal_moves if m.from_square == sq]
                else:
                    self.selected = None; self.valid_moves = []
            
            elif event_type == "up":
                if self.dragging_piece:
                    from_sq = self.dragging_piece[1]
                    if from_sq != sq:
                        move = chess.Move(from_sq, sq)
                        if move in self.board.legal_moves:
                            self.apply_move(move)
                        else:
                             move_q = chess.Move(from_sq, sq, promotion=chess.QUEEN)
                             if move_q in self.board.legal_moves:
                                 self.promo_popup = PromotionPopup(self, self.board.turn, from_sq, sq)
                    self.dragging_piece = None
        else:
            if event_type == "down": 
                self.selected = None; self.valid_moves = []
                # Clear arrows if clicking in the blank space outside the board
                self.user_arrows = [] 
                self.temp_arrow_start = None
                self.temp_arrow_end = None
            
    def reset_game(self):
        with self.lock: 
            self.handle_ui("reset_internal")
            self.add_chat("System", "New Game.")
            self.sound_manager.play("game_start")
            
            # --- FIX: Respect the current mode when hitting New Game ---
            if self.mode_idx == 0:
                self.mode = "manual"
                self.status_msg = "Mode: Manual (PvP)"
            elif self.mode_idx == 1:
                self.mode = "play"
                self.status_msg = "Mode: Active (vs Bot)"
            else: 
                # If reset is clicked inside Trainer, fallback to PvP safely
                self.mode_idx = 0
                self.mode = "manual"
                self.status_msg = "Mode: Manual (PvP)"
                self.active_bot = None
    def handle_ui(self, tag):
        if tag == "reset_internal":
            if self.logic: 
                self.logic.reset_game()
                self.board = self.logic.board
            else:
                self.board.reset()
            self.history = []; self.view_ply = 0; self.arrows = []; self.chat_log = []; self.pgn_headers = {}
            self.cached_review = None; self.active_puzzle = None; self.trainer_moves = []; self.trainer_hint_arrow = None
            if hasattr(self, 'last_move_analysis'): self.last_move_analysis = None
            
            # --- FIX: Wipe the active file path so 'Save' gets greyed out on new games ---
            self.current_pgn_path = None
            
            self.puzzle_wrong_attempts = 0
            
            return
        if tag == "reset":
            # FIX: Trigger if there is ANY move history, not just analyzed games
            if getattr(self, 'unsaved_analysis', False) or len(self.history) > 0:
                self.pending_action = "reset"
                from popups import UnsavedAnalysisPopup
                self.unsaved_popup = UnsavedAnalysisPopup(self)
                self.unsaved_popup.active = True
            else:
                self.reset_game()
            
        elif tag == "undo":
            if len(self.history) > 0:
                with self.lock:
                    self.user_arrows = [] # <--- Clear arrows when you takeback
                    self.last_move_analysis = None # <-- FIX: Clear stale analysis on takeback
                    
                    cnt = 2 if self.mode_idx == 1 and self.board.turn != self.playing_white else 1
                    if self.mode == "puzzle": cnt = 1 
                    for _ in range(cnt):
                        if self.history:
                             if self.logic: 
                                 self.logic.undo_last_move()
                                 self.board = self.logic.board
                             else: 
                                 self.board.pop()
                             self.history.pop()
                    self.view_ply = len(self.history)
        elif tag == "account":
            # Open account manager popup
            from account_popup import AccountPopup
            self.account_popup = AccountPopup(self)
            self.account_popup.active = True
        elif tag == "bot": self.bot_popup = BotPopup(self)
        elif tag == "flip": self.playing_white = not self.playing_white
        elif tag == "mode":
            self.mode_idx = (self.mode_idx + 1) % 3
            if self.mode_idx == 0: 
                self.mode = "manual"
                self.status_msg = "Mode: Manual (PvP)"
                self.active_bot = None
            elif self.mode_idx == 1: 
                self.mode = "play"
                self.status_msg = "Mode: Active (vs Bot)"
                self.active_bot = BOTS[0]
            else: 
                # Trainer trigger logic remains in popup, self.mode set to trainer inside start_trainer
                self.status_msg = "Mode: Trainer (Select Opening)"
                self.trainer_popup = TrainerPopup(self)
                
            self.chat_log = []; self.add_chat("System", f"Switched to {self.status_msg}")
        elif tag == "theme": self.board_style = "green" if self.board_style == "wood" else "wood"
        elif tag == "review":
            # --- FIX: Dynamically inject bot names if headers are empty ---
            headers = dict(self.pgn_headers)
            if not headers and self.mode_idx == 1 and getattr(self, 'active_bot', None):
                headers["White"] = "Player" if self.playing_white else self.active_bot["name"]
                headers["Black"] = self.active_bot["name"] if self.playing_white else "Player"
            self.review_popup = ReviewPopup(self, self.history, self.current_engine_info["path"], self.assets, headers, self.cached_review)
            # --------------------------------------------------------------
        elif tag == "gm_move": self.gm_move_popup = GMPopup(self)
        elif tag == "enginehint": self.show_hints = not self.show_hints
        elif tag == "threats": self.show_threats = not self.show_threats
        elif tag == "annotations": 
            self.settings["live_annotations"] = not self.settings.get("live_annotations", True)
            self.save_config()
            self.status_msg = f"Live Annotations: {'ON' if self.settings['live_annotations'] else 'OFF'}"
        elif tag == "save": self.save_popup = PGNSavePopup(self)
        elif tag == "save": self.save_popup = PGNSavePopup(self)
        elif tag == "copy_fen":
            # Fetch FEN of the exact ply currently being viewed
            if self.view_ply == 0:
                fen = chess.Board().fen()
            else:
                fen = self.history[self.view_ply - 1]["fen"]
                
            # Push to OS Clipboard using existing Tkinter root
            if self.root:
                self.root.clipboard_clear()
                self.root.clipboard_append(fen)
                self.root.update() # Forces OS to register the clipboard change
                
            self.sound_manager.play("click")
            self.status_msg = "FEN Copied to Clipboard!"
        elif tag == "load":
            self.sound_manager.play("click")
            from popups import LoadGamePopup
            self.active_popup = LoadGamePopup(self)
            self.active_popup.active = True
        elif tag == "settings": self.settings_popup = SettingsPopup(self)
        # 'threat' UI toggle removed — threats remain computed internally but no UI toggle
        elif tag == "engine_load": self.engine_popup = EnginePopup(self)
        elif tag == "puzzles": self.puzzle_popup = PuzzlePopup(self)
        elif tag == "more_buttons":
            # Open consolidated actions popup
            self.active_popup = ButtonsPopup(self)
        elif tag == "trainer_reopen":
            self.mode_idx = 2
            self.status_msg = "Mode: Trainer (Select Opening)"
            self.trainer_popup = TrainerPopup(self)
        elif tag == "trainer_close":
            self.mode_idx = 0
            self.mode = "manual"
            self.status_msg = "Mode: Manual (PvP)"
            self.active_bot = None
        elif tag == "profile":
            self.profile_popup = ProfilePopup(self)
            self.sound_manager.play("click")
        elif tag == "calibrate":
            import popups
            self.side_popup = popups.BatchCalibrationPopup(self)
            self.side_popup.active = True
    def run(self):
        while self.running:
            try:
                self.screen.fill(THEME["bg"])
                self.renderer.draw_board()
                self.renderer.draw_ui()
                
                # Draw Active Popups
                for popup in [self.review_popup, self.pgn_popup, self.gm_move_popup, self.bot_popup, 
                              self.promo_popup, self.save_popup, self.side_popup, self.settings_popup,
                              self.trainer_popup, self.engine_popup, self.phase_popup, self.puzzle_popup,
                              self.save_brilliant_popup, self.profile_popup, self.active_popup, self.trainer_complete_popup, 
                              self.fast_import_popup, self.unsaved_popup, self.account_popup]: 
                    if popup and popup.active:
                        if isinstance(popup, (PromotionPopup, SideSelectionPopup)): popup.draw(self.screen)
                        else: popup.draw(self.screen, self.font_b, self.font_m)
                # Draw chat commentary panel if enabled
                if getattr(self, 'show_chat_commentary', False):
                    chat_x = self.bd_x + self.bd_sz + 150
                    chat_y = self.bd_y + 300
                    chat_w = 350
                    chat_h = 200
                    self.renderer._draw_chat_commentary(chat_x, chat_y, chat_w, chat_h)
                while self.ui_queue:
                    m = self.ui_queue.pop(0)
                    if m[0] == "move": self.apply_move(m[1])
                    elif m[0] == "chat": self.add_chat(m[1][0], m[1][1])
                    elif m[0] == "speak": self.speech_queue.put((m[1], self.active_bot["name"] if self.active_bot else "Stockfish"))
                for e in pygame.event.get():
                    if e.type == pygame.QUIT:
                        # FIX: Prevent the window from closing if a game is in progress
                        if getattr(self, 'unsaved_analysis', False) or len(self.history) > 0:
                            self.pending_action = "quit"
                            from popups import UnsavedAnalysisPopup
                            self.unsaved_popup = UnsavedAnalysisPopup(self)
                            self.unsaved_popup.active = True
                        else:
                            self.running = False
                            self.save_config()
                            import sys
                            pygame.quit()
                            sys.exit()
                            
                    elif e.type == pygame.VIDEORESIZE:
                        self.width, self.height = e.w, e.h; self.screen = pygame.display.set_mode(e.size, pygame.RESIZABLE); self.calc_layout()
                        
                    # --- GRANDMASTER EXPLORER HOTKEY & EVENTS ---
                    if e.type == pygame.KEYDOWN and e.key == pygame.K_e:
                        if not any(p and getattr(p, 'active', False) for p in [self.trainer_popup]):
                            self.explorer_ui.is_open = not self.explorer_ui.is_open
                            
                            # Auto-Fetch the moment the user opens the Explorer!
                            if self.explorer_ui.is_open:
                                self.explorer_db.current_results = None # Wipe old data instantly
                                self.explorer_ui.scroll_y = 0           # Reset scroll to the top
                                
                                # Build the ghost board for the exact ply you are viewing
                                view_board = chess.Board()
                                for i in range(self.view_ply):
                                    view_board.push(self.history[i]["move"])
                                    
                                # Trigger the background database search
                                self.explorer_db.fetch_position_async(view_board)
                    
                    if getattr(self.explorer_ui, 'is_open', False):
                        if self.explorer_ui.handle_event(e, self.explorer_db, self.board):
                            continue 
                    # ---------------------------------------------
                    # Popup Event Delegation
                    current_ui_popup = None
                    for p in [self.unsaved_popup, self.fast_import_popup, self.trainer_complete_popup, self.save_brilliant_popup, self.puzzle_popup, self.phase_popup, self.engine_popup,
                              self.trainer_popup, self.settings_popup, self.save_popup, self.promo_popup,
                              self.pgn_popup, self.gm_move_popup, self.active_popup, self.bot_popup, self.review_popup, self.side_popup, self.account_popup]:
                        if p and getattr(p, 'active', False):
                            current_ui_popup = p
                            break
                    if current_ui_popup:
                        # Let the popup consume input first (keyboard or mouse)
                        if hasattr(current_ui_popup, 'handle_input'):
                            try: current_ui_popup.handle_input(e)
                            except Exception: pass
                        # Mouse down or Wheel -> scrolling or click down behaviour
                        if e.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEWHEEL):
                            if hasattr(current_ui_popup, 'handle_scroll'):
                                try: current_ui_popup.handle_scroll(e)
                                except Exception: pass
                            if hasattr(e, 'button') and e.button in (1, 3) and hasattr(current_ui_popup, 'handle_click'):
                                try: current_ui_popup.handle_click(e.pos)
                                except Exception: pass
                        # Mouse up -> Handle any specific mouse-up logic if needed in the future
                        if e.type == pygame.MOUSEBUTTONUP:
                            # FIX: Removed the duplicate handle_click(e.pos) call here.
                            # This prevents checkboxes and toggles from firing twice (auto-unclicking).
                            pass
                        continue
                    # Main
                    if e.type == pygame.KEYDOWN:
                        if e.key == pygame.K_LEFT: 
                            if self.view_ply > 0: 
                                self.view_ply -= 1
                                self.update_opening_label()
                                
                                # --- FIX: Responsive Rewind ---
                                # Play a crisp click sound so navigating backwards feels tactile
                                self.sound_manager.play("click")
                                
                                # Clear any visual arrows that belong to the later move
                                self.user_arrows = [] 
                                self.temp_arrow_start = None
                                self.temp_arrow_end = None
                                # ------------------------------
                        elif e.key == pygame.K_RIGHT: 
                            if self.view_ply < len(self.history): 
                                self.view_ply += 1
                                self.update_opening_label()
                                
                                # --- FIX: Trigger Bot Speech on Keyboard Navigation ---
                                if self.settings.get("speech", True):
                                    step = self.history[self.view_ply - 1]
                                    bot = getattr(self, 'active_bot', None) or {"name": "System", "style": "GM"}
                                    
                                    # 1. Grab move classification (blunder, great, etc.)
                                    move_class = step.get("review", {}).get("class", "move")
                                    chat_event = "blunder" if move_class in ["blunder", "miss"] else "move"
                                    
                                    # 2. Check for Checks/Mates using the FEN
                                    if step.get("fen"):
                                        tmp = chess.Board(step["fen"])
                                        if tmp.is_checkmate(): chat_event = "checkmate"
                                        elif tmp.is_check(): chat_event = "check"
                                    
                                    # 3. Build the context for the personality engine
                                    context = {
                                        "bot_name": bot.get("name", "System"),
                                        "style": bot.get("style", "GM"),
                                        "event": chat_event,
                                        "eval": step.get("review", {}).get("eval_cp", 0),
                                        "is_white": (self.view_ply % 2 != 0)
                                    }
                                    
                                    import bot_personalities
                                    voice_line = bot_personalities.get_bot_chat(context)
                                    
                                    # 4. Push to UI Chat and Audio Queue
                                    if voice_line:
                                        self.ui_queue.append(("chat", (bot.get("name", "System"), voice_line)))
                                        self.speech_queue.put((voice_line, bot.get("name", "System")))
                                # --------------------------------------------------------
                        elif e.key == pygame.K_UP: self.scroll_hist = max(0, self.scroll_hist - 25)
                        elif e.key == pygame.K_DOWN: self.scroll_hist += 25
                        if e.mod & pygame.KMOD_CTRL:
                            if e.key == pygame.K_z: self.handle_ui("undo")
                            elif e.key == pygame.K_s: self.handle_ui("save")
                            elif e.key == pygame.K_f: self.handle_ui("flip")
                            elif e.key == pygame.K_r: self.handle_ui("reset")
                    elif e.type == pygame.MOUSEBUTTONDOWN:
                        if e.button == 4: self.scroll_hist = max(0, self.scroll_hist - 40)
                        elif e.button == 5: self.scroll_hist += 40
                        elif e.button in [1, 3]: self.handle_click(e.pos, "down") # 1=left, 3=right
                    
                    elif e.type == pygame.MOUSEMOTION:
                        # Handle Arrow Dragging Visuals
                        if pygame.mouse.get_pressed()[2] and self.temp_arrow_start is not None:
                             # Check square under mouse
                             mx, my = e.pos
                             if 0 <= mx - self.bd_x <= self.bd_sz and 0 <= my - self.bd_y <= self.bd_sz:
                                 c, r = (mx - self.bd_x)//self.sq_sz, (my - self.bd_y)//self.sq_sz
                                 if self.playing_white: r = 7 - r
                                 else: c = 7 - c
                                 sq = chess.square(c, r)
                                 self.temp_arrow_end = sq
                    elif e.type == pygame.MOUSEBUTTONUP:
                        if e.button == 1:
                            ui_clicked = False
                            for tag, r in self.btn_rects.items():
                                if r.collidepoint(e.pos): self.handle_ui(tag); ui_clicked = True; break
                            if not ui_clicked: self.handle_click(e.pos, "up")
                        elif e.button == 3:
                                self.handle_click(e.pos, "up")
                # --- DRAW THE EXPLORER BOX LAST SO IT FLOATS ON TOP ---
                self.explorer_ui.draw(self.screen, self.explorer_db)
                # ------------------------------------------------------
                pygame.display.flip()
                self.clock.tick(60)
            except Exception as e: print(e)
if __name__ == "__main__":
    ChessApp().run()
