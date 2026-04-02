import pygame
import os
import sys
import chess
import chess.pgn
import threading
import shutil

# =============================================================================
#  THEME & CONFIGURATION
# =============================================================================
THEME = {
    "bg": (240, 240, 245),
    "panel": (255, 255, 255),
    "text": (20, 20, 20),
    "text_dim": (100, 100, 100),
    "border": (200, 200, 200),
    "accent": (60, 100, 220),  # Royal Blue
    "dark_mode": False,
    
    # Chat
    "chat_bg": (245, 247, 250),
    "chat_bubble_bot": (230, 230, 230),
    "chat_bubble_user": (210, 230, 255),
    
    # Boards
    "wood": {"light": (240, 217, 181), "dark": (181, 136, 99), "highlight": (255, 255, 50, 160), "select": (100, 255, 100, 180)},
    "green": {"light": (235, 236, 208), "dark": (118, 150, 86), "highlight": (245, 246, 130, 120), "select": (186, 202, 68, 150)},
    
    # Arrows
    "arrow_1": (0, 200, 0, 180),    # Best (Green)
    "arrow_2": (255, 165, 0, 180),  # Good (Orange)
    "arrow_3": (255, 50, 50, 180),  # Risky (Red)
    "arrow_book": (0, 100, 255, 180), # Book (Blue)
    "user_arrow": (40, 220, 40, 220), # LimeGreen (Opaque)
    "temp_arrow": (40, 220, 40, 150), # LimeGreen (Semi-transparent for dragging)
    "trainer_arrow": (20, 20, 20, 200), # Black for trainer hint
    
    "eval_bar_bg": (50, 50, 50),
    "eval_white": (255, 255, 255),

    # Review Icons (RGB Colors)
    "brilliant": (20, 180, 160), 
    "great": (50, 100, 250), 
    "best": (34, 139, 34),
    "excellent": (156, 204, 101), 
    "good": (140, 190, 140), 
    "miss": (255, 107, 107),      
    "inaccuracy": (240, 220, 80), 
    "mistake": (230, 140, 20),
    "blunder": (200, 50, 50), 
    "book": (160, 110, 90)
}

BOT_VOICE_MAP = {
    "Spark": "male", "Cassidy": "female", "Byte": "male", "Vincent": "male",
    "Oliver": "male", "Arthur": "male", "Niles": "male", "Nova": "female",
    "Eleanor": "female", "Armando": "male", "Veda": "female", "Catherine": "female",
    "Maximus": "male", "Stockfish": "male", "Checkmate Master": "male"
}

BOTS = [
    {"name": "Spark", "elo": 250, "style": "Blunder Master", "type": "engine", "group": "Beginner"},
    {"name": "Cassidy", "elo": 400, "style": "Safe", "type": "engine", "group": "Beginner"},
    {"name": "Byte", "elo": 600, "style": "Self declared master", "type": "engine", "group": "Beginner"},
    {"name": "Vincent", "elo": 700, "style": "Learner", "type": "engine", "group": "Beginner"},
    {"name": "Oliver", "elo": 1000, "style": "Less blunder", "type": "engine", "group": "Intermediate"},
    {"name": "Arthur", "elo": 1100, "style": "Aggressive", "type": "engine", "group": "Intermediate"},
    {"name": "Niles", "elo": 1300, "style": "Aggressive player", "type": "engine", "group": "Intermediate"}, 
    {"name": "Nova", "elo": 1400, "style": "Passive", "type": "engine", "group": "Intermediate"},
    {"name": "Eleanor", "elo": 1500, "style": "Passive defender", "type": "engine", "group": "Intermediate"},
    {"name": "Armando", "elo": 2000, "style": "Tactical", "type": "engine", "group": "Advanced"},
    {"name": "Veda", "elo": 2200, "style": "Passive attacker", "type": "engine", "group": "Advanced"},
    {"name": "Catherine", "elo": 2300, "style": "Historian", "type": "engine", "group": "Advanced"},
    {"name": "Maximus", "elo": 2500, "style": "Grandmaster", "type": "engine", "group": "Master"},
    {"name": "Stockfish", "elo": 3200, "style": "God Mode", "type": "engine", "group": "Master"},
    {"name": "Checkmate Master", "elo": 3200, "style": "Assassin", "type": "book", "group": "Master", "description": "A ruthless tactical monster. It will sacrifice everything to mate you under 20 moves.", "avatar": "assets/bots/checkmate_master.png"},
]

PIECE_VALS = {chess.PAWN:1, chess.KNIGHT:3, chess.BISHOP:3, chess.ROOK:5, chess.QUEEN:9, chess.KING:0}

# =============================================================================
#  SOUND MANAGER
# =============================================================================
class SoundManager:
    def __init__(self):
        # Increased buffer and frequency for high-quality MP3 playback
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512) 
        pygame.mixer.set_num_channels(16) # Expand available audio channels
        self.sounds = {}
        self.load_sounds()

    def load_sounds(self):
        files = {
            "game_start": "game_start.mp3", "game_end": "game_end.mp3",
            "move_self": "self_move.mp3", "move_opponent": "opponent_move.mp3",
            "capture": "capture.mp3", "castle": "castle.mp3",
            "check_mate": "check_mate.mp3", "check": "move_self.mp3", 
            "promote": "pawn_promotion.mp3", "draw": "draw.mp3",
            "draw_repetition": "draw_by_repetition.mp3", "en_passant": "en_passant.mp3",
            "win": "game_win.mp3", "lose": "game_lose.mp3",
            "error": "game_lose.mp3" 
        }
        base_path = "assets/sounds"
        if not os.path.exists(base_path): return
        for key, fname in files.items():
            path = os.path.join(base_path, fname)
            if os.path.exists(path):
                try: 
                    snd = pygame.mixer.Sound(path)
                    # Drop SFX volume to 90% so voices stand out clearly!
                    snd.set_volume(0.9) 
                    self.sounds[key] = snd
                except: pass

    def play(self, key):
        if key in self.sounds:
            try: 
                # Play sound effects on any available channel EXCEPT Channel 7 (Voice Channel)
                ch = pygame.mixer.find_channel()
                if ch and ch != pygame.mixer.Channel(7):
                    ch.play(self.sounds[key])
            except: pass

# =============================================================================
#  ASSET MANAGER
# =============================================================================
class AssetLoader:
    def __init__(self, piece_set_name="infinix"):
        self.pieces = {}
        self.icons = {}
        self.piece_set_name = piece_set_name
        # --- DYNAMIC AVATAR LOADER (Matched to standard icon pathing) ---
        self.avatars = {}
        av_path = os.path.join("assets", "avatars")
        
        if os.path.exists(av_path):
            for f in os.listdir(av_path):
                if f.lower().endswith((".png", ".jpg", ".jpeg")):
                    bot_name = os.path.splitext(f)[0] 
                    img_path = os.path.join(av_path, f)
                    try:
                        self.avatars[bot_name] = pygame.image.load(img_path).convert_alpha()
                    except Exception as e:
                        print(f"Failed to load avatar {f}: {e}")
        self.openings = {}
        self.book_positions = set()
        self.opening_list = [] # For Trainer Popup
        self.mate_list = [] # NEW: For Mates Trainer
        self.gm_books = []
        self.engines = []
        
        # Puzzle Stores
        self.puzzles_unsolved = []
        self.puzzles_solved = []
        self.appmade_puzzles = []
        
        # Ensure Paths
        self.puzzle_base = os.path.abspath("assets/puzzles")
        self.path_unsolved = os.path.join(self.puzzle_base, "puzzles_unsolved")
        self.path_solved = os.path.join(self.puzzle_base, "puzzles_solved")
        self.path_appmade = os.path.join(self.puzzle_base, "appmade_puzzles")
        self.path_syzygy = os.path.abspath("assets/syzygy")

        for p in [self.path_unsolved, self.path_solved, self.path_appmade, self.path_syzygy]:
            os.makedirs(p, exist_ok=True)
        
        self.load_images()
        self.load_books()
        self.load_engines()
        self.refresh_puzzles()
        threading.Thread(target=self.load_eco, daemon=True).start()
        threading.Thread(target=self.load_mates, daemon=True).start()

    def load_mates(self):
        self.mate_list.clear()
        path = os.path.abspath("assets/mates_comprehensive.pgn")
        if os.path.exists(path):
            try: self._threaded_mates_load(path)
            except: pass

    def _threaded_mates_load(self, path):
        try:
            with open(path, encoding="utf-8") as f:
                while True:
                    g = chess.pgn.read_game(f)
                    if not g: break
                    
                    name = g.headers.get("Event", "Unknown Mate")
                    if name == "?" or name == "Unknown Mate":
                        name = g.headers.get("White", "Mate Sequence")
                        
                    moves = list(g.mainline_moves())
                    self.mate_list.append({
                        'name': name,
                        'moves': [m.uci() for m in moves],
                        'type': 'mate'
                    })
            self.mate_list.sort(key=lambda x: x.get("name", ""))
        except Exception as e:
            print(f"Mates Load Error: {e}")

    def load_piece_set(self, set_name="infinix"):
        """
        Load pieces from a named subfolder under assets/pieces/.
        Supports: .png, .svg, and .html (containing inline SVG or base64 PNG).
        Falls back to root assets/pieces/ .png files if nothing else works.
        set_name examples: "infinix", "staunty", "default"
        """
        self.pieces = {}
        base = os.path.join("assets", "pieces")

        # Determine folder
        if set_name and set_name != "default":
            folder = os.path.join(base, set_name)
            if not os.path.exists(folder):
                print(f"[PieceSet] Subfolder '{set_name}' not found, falling back to default.")
                folder = base
        else:
            folder = base

        # SVG renderer: try cairosvg, then svglib, then None
        def _svg_bytes_to_surface(svg_bytes, size=128):
            # --- Method 1: cairosvg ---
            try:
                import cairosvg, io
                png_data = cairosvg.svg2png(
                    bytestring=svg_bytes,
                    output_width=size,
                    output_height=size
                )
                return pygame.image.load(io.BytesIO(png_data)).convert_alpha()
            except Exception:
                pass
            # --- Method 2: svglib + reportlab ---
            try:
                import io
                from svglib.svglib import svg2rlg
                from reportlab.graphics import renderPM
                drawing = svg2rlg(io.BytesIO(svg_bytes))
                if drawing:
                    png_data = renderPM.drawToString(drawing, fmt="PNG")
                    return pygame.image.load(io.BytesIO(png_data)).convert_alpha()
            except Exception:
                pass
            return None

        # File name mapping: board uses lowercase keys like 'wp', 'bn', etc.
        # SVG files are typically named like wP.svg / wN.svg (mixed case) or wp.svg (lower)
        # We try both casings automatically.
        def _find_file(folder, key, ext):
            """Try lowercase, then Title-case second letter (e.g. wn → wN)."""
            for name in [f"{key}{ext}", f"{key[0]}{key[1].upper()}{ext}"]:
                p = os.path.join(folder, name)
                if os.path.exists(p):
                    return p
            return None

        for c in ['w', 'b']:
            for p in ['p', 'n', 'b', 'r', 'q', 'k']:
                key = c + p
                loaded = False

                # 1. PNG — direct load
                png_path = _find_file(folder, key, ".png")
                if png_path:
                    try:
                        self.pieces[key] = pygame.image.load(png_path).convert_alpha()
                        loaded = True
                    except Exception as e:
                        print(f"[PieceSet] PNG load failed for {key}: {e}")

                # 2. SVG — render to surface
                if not loaded:
                    svg_path = _find_file(folder, key, ".svg")
                    if svg_path:
                        try:
                            with open(svg_path, "rb") as sf:
                                svg_bytes = sf.read()
                            surf = _svg_bytes_to_surface(svg_bytes)
                            if surf:
                                self.pieces[key] = surf
                                loaded = True
                            else:
                                print(f"[PieceSet] SVG render returned None for {key}. Install cairosvg: pip install cairosvg")
                        except Exception as e:
                            print(f"[PieceSet] SVG load failed for {key}: {e}")

                # 3. HTML — extract inline SVG or base64 PNG
                if not loaded:
                    html_path = _find_file(folder, key, ".html")
                    if html_path:
                        try:
                            import re, io, base64
                            with open(html_path, "r", encoding="utf-8") as hf:
                                content = hf.read()

                            # 3a. Try embedded base64 PNG
                            m = re.search(r'data:image/png;base64,([A-Za-z0-9+/=]+)', content)
                            if m:
                                img_data = base64.b64decode(m.group(1))
                                self.pieces[key] = pygame.image.load(io.BytesIO(img_data)).convert_alpha()
                                loaded = True

                            # 3b. Try inline SVG block
                            if not loaded:
                                m = re.search(r'(<svg[\s\S]*?</svg>)', content, re.IGNORECASE)
                                if m:
                                    svg_bytes = m.group(1).encode("utf-8")
                                    surf = _svg_bytes_to_surface(svg_bytes)
                                    if surf:
                                        self.pieces[key] = surf
                                        loaded = True

                            # 3c. Try embedded base64 SVG
                            if not loaded:
                                m = re.search(r'data:image/svg\+xml;base64,([A-Za-z0-9+/=]+)', content)
                                if m:
                                    svg_bytes = base64.b64decode(m.group(1))
                                    surf = _svg_bytes_to_surface(svg_bytes)
                                    if surf:
                                        self.pieces[key] = surf
                                        loaded = True
                        except Exception as e:
                            print(f"[PieceSet] HTML load failed for {key}: {e}")

                # 4. Fallback: root assets/pieces/<key>.png
                if not loaded and folder != base:
                    fallback = os.path.join(base, f"{key}.png")
                    if os.path.exists(fallback):
                        try:
                            self.pieces[key] = pygame.image.load(fallback).convert_alpha()
                            loaded = True
                        except Exception as e:
                            print(f"[PieceSet] Fallback PNG failed for {key}: {e}")

                if not loaded:
                    print(f"[PieceSet] WARNING: Could not load piece '{key}' from set '{set_name}'")

    @staticmethod
    def get_available_piece_sets():
        """Returns list of available piece set names from subfolders inside assets/pieces/."""
        sets = []
        base = os.path.join("assets", "pieces")
        if os.path.exists(base):
            for entry in sorted(os.listdir(base)):
                if os.path.isdir(os.path.join(base, entry)):
                    sets.append(entry)
        return sets

    def load_images(self):
        # Load pieces using the set_name stored on self (set during __init__ via settings)
        set_name = getattr(self, 'piece_set_name', 'default')
        self.load_piece_set(set_name)

        keys = ["brilliant", "great", "best", "excellent", "good", "miss", "inaccuracy", "mistake", "blunder", "book",
                "reset", "flip", "mode", "theme", "review", "save", "load", "hint", "undo", 
                "icon_search", "analyze", "pgnpopup", "pgnload", "gm_icon", "pgnsave", "enginehint", "main",
                "eval_book", "puzzles", "close_btn", "lichess", "chess_com"]
        for k in keys:
            found = False
            for prefix in ["", "icon_", "eval_"]:
                path = f"assets/icons/{prefix}{k}.png"
                if os.path.exists(path):
                    try: 
                        self.icons[k] = pygame.image.load(path).convert_alpha()
                        found = True
                        break
                    except: pass
            
            # Fallbacks
            if not found and k == "mode":
                 if os.path.exists("assets/icons/analyze.png"):
                     try: self.icons[k] = pygame.image.load("assets/icons/analyze.png").convert_alpha()
                     except: pass

        folders = ["assets/bots", "assets/avatars"]
        if hasattr(sys, '_MEIPASS'): folders = [os.path.join(sys._MEIPASS, f) for f in folders]

        for b in BOTS:
            # 1. Check for explicitly defined avatar path first
            if "avatar" in b and os.path.exists(b["avatar"]):
                try: 
                    self.avatars[b['name']] = pygame.image.load(b["avatar"]).convert_alpha()
                    continue
                except: pass
                
            # 2. Fallback to name-based guessing (handles spaces vs underscores)
            fname1 = b['name'].lower() + ".png"
            fname2 = b['name'].lower().replace(" ", "_") + ".png"
            
            loaded = False
            for d in folders:
                for fname in [fname1, fname2]:
                    path = os.path.join(d, fname)
                    if os.path.exists(path):
                        try: 
                            self.avatars[b['name']] = pygame.image.load(path).convert_alpha()
                            loaded = True
                            break
                        except: pass
                if loaded: break
        
        for d in folders:
            p = os.path.join(d, "player.png")
            if not os.path.exists(p): p = os.path.join(d, "player_default.png")
            if os.path.exists(p):
                try: self.avatars["player"] = pygame.image.load(p).convert_alpha(); break
                except: pass

    def get_avatar(self, name):
        # 1. Check if they have a specific custom photo first
        if name in self.avatars: return self.avatars[name]
        
        # 2. FIX: If it's a Grandmaster and they don't have a photo, return the GM Icon!
        if str(name).startswith("GM "):
            gm_icon = self.icons.get("gm_icon")
            if gm_icon: return gm_icon
            
        # 3. Fallback to the blue square only if all else fails
        s = pygame.Surface((60, 60)); s.fill(THEME["accent"]); return s

    def load_books(self):
        book_dir = os.path.join("assets", "books")
        if os.path.exists(book_dir):
            for f in os.listdir(book_dir):
                if f.endswith(".bin"):
                    n = f.replace(".bin","").replace("gm_", "").replace("_", " ").title()
                    file_path = os.path.join(book_dir, f)
                    
                    self.gm_books.append({"name": n, "path": file_path})
                    if not any(b['name'] == f"GM {n}" for b in BOTS):
                        BOTS.append({
                            "name": f"GM {n}", "elo": "Book", "style": "GM", 
                            "type": "book", "group": "Master", "path": file_path
                        })
                    
                    base_name = f.replace(".bin", "")
                    icon_path = os.path.join("assets/icons", base_name + ".png")
                    if os.path.exists(icon_path):
                        try:
                            self.avatars[f"GM {n}"] = pygame.image.load(icon_path).convert_alpha()
                        except: pass

    def load_engines(self):
        """Scans the engine/ folder for executables."""
        self.engines = []
        possible_paths = ["engine", "engines", "bin"]
        
        # Files to explicitly ignore
        ignore_exts = [".dll", ".bin", ".txt", ".ini", ".config"]
        
        for d in possible_paths:
            if os.path.exists(d):
                for f in os.listdir(d):
                    lower_f = f.lower()
                    # 1. Check if it's an executable (or no extension on Mac/Linux)
                    is_exe = f.endswith(".exe") or (sys.platform != "win32" and "." not in f)
                    
                    # 2. Ensure it's not a helper file (like a .dll)
                    is_valid_ext = not any(lower_f.endswith(ext) for ext in ignore_exts)

                    if is_exe and is_valid_ext:
                        self.engines.append({"name": f, "path": os.path.join(d, f)})
        
        # Ensure default is available if nothing found
        if not self.engines:
             # Check root
             if os.path.exists("stockfish.exe"): 
                 self.engines.append({"name": "Stockfish Default", "path": os.path.abspath("stockfish.exe")})
             elif os.path.exists("engines/stockfish.exe"): 
                 self.engines.append({"name": "Stockfish Default", "path": os.path.abspath("engines/stockfish.exe")})

    def load_eco(self):
        self.openings.clear()
        self.book_positions.clear()
        
        start_fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq"
        start_key = " ".join(start_fen.split(" ")[:3])
        self.openings[start_key] = "Starting Position"
        self.book_positions.add(start_key)
        
        path = os.path.abspath("assets/ECO.pgn")
        if os.path.exists(path):
            try: self._threaded_eco_load(path)
            except: pass

    def _threaded_eco_load(self, path):
        try:
            with open(path, encoding="utf-8") as f:
                while True:
                    g = chess.pgn.read_game(f)
                    if not g: break
                    
                    base_op = g.headers.get("Opening", "Unknown")
                    var_op = g.headers.get("Variation", "")
                    if "Unknown" in base_op and not var_op: continue
                    opening = f"{base_op}: {var_op}" if var_op else base_op
                    
                    temp_board = g.board()
                    self.book_positions.add(" ".join(temp_board.fen().split(" ")[:3]))
                    
                    moves = list(g.mainline_moves())
                    
                    for i, move in enumerate(moves):
                        temp_board.push(move)
                        move_key = " ".join(temp_board.fen().split(" ")[:3])
                        
                        # 1. ENGINE: Always add to book_positions for the blue icon
                        self.book_positions.add(move_key)
                        
                        # 2. UI: Only name the position if it's the end of this specific PGN line
                        # This prevents 1. e4 from being called "Sicilian Najdorf" prematurely
                        if i == len(moves) - 1:
                            # Only store the longest name found for this specific position
                            if len(opening) > len(self.openings.get(move_key, "")):
                                self.openings[move_key] = opening
                    
                    # FIX: Add the opening to the list so the Trainer UI can receive it!
                    # This must be aligned exactly with the "for" loop above it.
                    self.opening_list.append({
                        'name': opening,
                        'moves': [m.uci() for m in moves]
                    })
                                
            self.opening_list.sort(key=lambda x: x.get("name", ""))
        except Exception as e:
            print(f"ECO Load Error: {e}")

    def get_opening_name(self, fen):
        # KEY FIX: Use the same 3-part key for lookup
        parts = fen.split(" ")
        clean_key = " ".join(parts[:3])
        return self.openings.get(clean_key, None)
        
    def scale_keep_aspect(self, img, target_size):
        """Scales an image to fit within target_size while keeping aspect ratio."""
        if not img: return None
        iw, ih = img.get_size()
        tw, th = target_size
        scale = min(tw / iw, th / ih)
        new_w = max(1, int(iw * scale))
        new_h = max(1, int(ih * scale))
        return pygame.transform.smoothscale(img, (new_w, new_h))

    # =========================================================================
    # PUZZLE MANAGEMENT
    # =========================================================================
    def refresh_puzzles(self):
        """Reloads all puzzle lists from disk."""
        self.puzzles_unsolved = self._load_puzzles_from_dir(self.path_unsolved)
        self.puzzles_solved = self._load_puzzles_from_dir(self.path_solved)
        self.appmade_puzzles = self._load_puzzles_from_dir(self.path_appmade)
        
    def _load_puzzles_from_dir(self, directory):
        puzzles = []
        if not os.path.exists(directory): 
            print(f"Directory not found: {directory}")
            return []
            
        for f in os.listdir(directory):
            full_path = os.path.join(directory, f)
            
            # --- 1. HANDLE .FEN and .TXT (Existing Logic) ---
            if f.lower().endswith(".fen") or f.lower().endswith(".txt"):
                try:
                    with open(full_path, "r", encoding="utf-8-sig") as file:
                        lines = file.readlines()
                        for line in lines:
                            line = line.strip()
                            if len(line) < 10: continue
                            
                            if ";" in line:
                                fen, name = line.split(";", 1)
                            else:
                                fen, name = line, "Unknown Puzzle"
                            
                            puzzles.append({
                                "fen": fen.strip(), 
                                "name": name.strip(), 
                                "file": full_path, 
                                "raw": line,
                                "type": "text" # Mark as text/line-based
                            })
                except Exception as e: 
                    print(f"Error loading text puzzle {f}: {e}")

            # --- 2. NEW: HANDLE .PGN FILES ---
            elif f.lower().endswith(".pgn"):
                try:
                    with open(full_path, encoding="utf-8") as pgn_f:
                        while True:
                            # Read one game at a time
                            game = chess.pgn.read_game(pgn_f)
                            if game is None: break 
                            
                            # Get the starting FEN (Handles 'FEN' header or Start Pos)
                            # Note: For puzzles, the FEN header usually defines the setup.
                            fen = game.board().fen()
                            
                            # Try to find a good name
                            name = game.headers.get("Event", "?")
                            if name == "?" or name == " ":
                                name = game.headers.get("White", "PGN Puzzle")
                            
                            puzzles.append({
                                "fen": fen,
                                "name": name,
                                "file": full_path,
                                "raw": None, # PGNs don't use line-based raw data
                                "type": "pgn" # Mark as PGN
                            })
                except Exception as e:
                    print(f"Error loading PGN puzzle {f}: {e}")
                    
        return puzzles

    def rename_puzzle(self, puzzle_obj, new_name):
        try:
            with open(puzzle_obj["file"], "r", encoding="utf-8-sig") as f:
                lines = f.readlines()
            
            with open(puzzle_obj["file"], "w", encoding="utf-8") as f:
                for line in lines:
                    if line.strip() == puzzle_obj["raw"]:
                        new_line = f"{puzzle_obj['fen']};{new_name}\n"
                        f.write(new_line)
                    else:
                        f.write(line)
            
            self.refresh_puzzles()
            return True
        except Exception as e: 
            print(f"Rename failed: {e}")
            return False

    def solve_puzzle(self, puzzle_obj):
        # --- NEW: PGN Handling ---
        # We don't delete puzzles from PGN files (too complex to rewrite safely).
        # We just add them to the 'solved' log so the UI knows.
        if puzzle_obj.get("type") == "pgn":
            target_file = os.path.join(self.path_solved, "solved_puzzles.fen")
            with open(target_file, "a", encoding="utf-8") as f:
                f.write(f"{puzzle_obj['fen']};{puzzle_obj['name']} (PGN)\n")
            return True

        # --- EXISTING: Text/FEN Handling ---
        try:
            with open(puzzle_obj["file"], "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            with open(puzzle_obj["file"], "w", encoding="utf-8") as f:
                for line in lines:
                    if line.strip() != puzzle_obj["raw"]:
                        f.write(line)
            
            target_file = os.path.join(self.path_solved, "solved_puzzles.fen")
            with open(target_file, "a", encoding="utf-8") as f:
                f.write(f"{puzzle_obj['fen']};{puzzle_obj['name']}\n")
            
            self.refresh_puzzles()
            return True
        except Exception as e:
            print(f"Error solving puzzle: {e}")
            return False

    def save_appmade_puzzle(self, fen, name="Brilliant Move"):
        try:
            target_file = os.path.join(self.path_appmade, "generated.fen")
            with open(target_file, "a", encoding="utf-8") as f:
                f.write(f"{fen};{name}\n")
            self.refresh_puzzles()
            return True
        except: return False

    def save_lichess_puzzle(self, fen, name, solution_uci, rating):
        """Save a Lichess puzzle to the unsolved directory with a JSON sidecar."""
        import json
        try:
            target_fen = os.path.join(self.path_unsolved, "lichess_attraction.fen")
            with open(target_fen, "a", encoding="utf-8") as f:
                f.write(f"{fen};{name}\n")
            sidecar_path = os.path.join(self.path_unsolved, "lichess_sidecar.json")
            sidecar = {}
            if os.path.exists(sidecar_path):
                try:
                    with open(sidecar_path, "r", encoding="utf-8") as sf:
                        sidecar = json.load(sf)
                except Exception:
                    sidecar = {}
            key = " ".join(fen.split()[:3])
            sidecar[key] = {"rating": rating, "solution": solution_uci, "name": name}
            with open(sidecar_path, "w", encoding="utf-8") as sf:
                json.dump(sidecar, sf, indent=2)
            return True
        except Exception as e:
            print(f"Lichess puzzle save error: {e}")
            return False

    def get_lichess_sidecar(self):
        """Load rating/solution metadata for all saved Lichess puzzles."""
        import json
        path = os.path.join(self.path_unsolved, "lichess_sidecar.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def get_existing_lichess_fens(self):
        """Return set of FEN keys already saved to avoid duplicates."""
        return set(self.get_lichess_sidecar().keys())