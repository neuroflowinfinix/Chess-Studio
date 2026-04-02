import pygame
import chess
import math
import os
import csv
import time
from assets import THEME, PIECE_VALS

class UIRenderer:
    def __init__(self, app):
        self.app = app
        self.screen = app.screen
        self.assets = app.assets
        self.scaled = {}
        self.vis_eval = 0.0  # Stores the current "visual" height for smoothing
        self.eval_log = []
        
        # Performance optimization: cached surfaces
        self.cached_text_surfaces = {}
        self.last_board_fen = None
        self.needs_full_redraw = True
        
    def draw_eval_bar(self, x, y, w, h):
        """
        Ultimate Evaluation Bar using NNUE Win-Probability (WDL) and Spring Physics.
        Matches professional platforms while preserving custom telemetry and glowing pulses.
        """
        import math, csv, os
        
        # 1. GET ENGINE EVALUATION
        target_eval = getattr(self.app, 'eval_val', 0.0)
        if target_eval is None:
            target_eval = 0.0

        current_depth = getattr(self.app, 'current_depth', 0)

        # --- BULLETPROOF FIX + DEPTH STABILIZATION ---
        if hasattr(self.app, 'board') and self.app.board.board_fen() == chess.STARTING_BOARD_FEN:
            target_eval = 0.0
            target_wdl = 0.5

        elif getattr(self.app, 'is_analyzing', False) and current_depth < 5:
            # Freeze eval only while engine is actively analyzing
            target_eval = 0.0
            target_wdl = 0.5

        else:
            # --- GOD-TIER UPGRADE: True Win Probability (WDL) Extraction ---
            target_wdl_pct = getattr(self.app, 'eval_wdl', None)
            if target_wdl_pct is not None:
                target_wdl = target_wdl_pct / 100.0
            else:
                # Exact Stockfish WDL Formula fallback
                target_wdl = 1.0 / (1.0 + math.exp(-0.00368208 * float(target_eval)))

        # Forced mates override the probability curve
        if target_eval > 5000: target_wdl = 1.0
        elif target_eval < -5000: target_wdl = 0.0

        # 2. INITIALIZE PHYSICS AND INDICATOR STATE
        if not hasattr(self, 'vis_wdl'):
            self.vis_wdl = float(target_wdl)
            self.wdl_velocity = 0.0
        if not hasattr(self, 'indicator_y'):
            self.indicator_y = y + h // 2
            self.indicator_vel = 0.0
        if not hasattr(self, 'eval_log'):
            self.eval_log = []

        # 3. ADAPTIVE SPRING PHYSICS ON TRUE WDL
        delta = target_wdl - self.vis_wdl
        tension = 0.15 + min(0.3, abs(delta)) # Snaps faster for massive evaluation swings
        dampening = 0.70

        force = delta * tension
        self.wdl_velocity = (self.wdl_velocity + force) * dampening
        self.vis_wdl += self.wdl_velocity

        win_chance = max(0.0, min(1.0, self.vis_wdl))

        # 4. LEFT-SIDED BAR LAYOUT
        bar_w = max(16, int(w))
        bar_x = self.app.bd_x - 10 - bar_w
        bar_y = self.app.bd_y
        bar_h = self.app.bd_sz

        # Draw background track
        track_col = (30, 30, 34)
        pygame.draw.rect(self.screen, track_col, (bar_x, bar_y, bar_w, bar_h), border_radius=6)

        # Draw filled area: top is black (opponent), bottom is white (player)
        filled_h = int(bar_h * win_chance)
        top_h = bar_h - filled_h
        
        # Professional standard: Pure White vs Dark Grey
        top_col = (40, 40, 40)      # Dark Grey (Black's advantage)
        bot_col = (240, 240, 240)   # Off-White (White's advantage)

        # Draw black area (top)
        pygame.draw.rect(self.screen, top_col, (bar_x + 2, bar_y, bar_w - 4, top_h))
        # Draw white area (bottom)
        pygame.draw.rect(self.screen, bot_col, (bar_x + 2, bar_y + top_h, bar_w - 4, filled_h))

        # Soft center line (equality indicator)
        if 0.45 < win_chance < 0.55:
            mid_y = bar_y + bar_h // 2
            pygame.draw.line(self.screen, (140, 140, 140), (bar_x, mid_y), (bar_x + bar_w - 1, mid_y), 2)

        # 5. INDICATOR DOT (smooth vertical movement)
        target_indicator_y = bar_y + (1.0 - win_chance) * bar_h
        i_delta = target_indicator_y - self.indicator_y
        i_tension = 0.18
        i_damp = 0.6
        i_force = i_delta * i_tension
        self.indicator_vel = (self.indicator_vel + i_force) * i_damp
        self.indicator_y += self.indicator_vel

        dot_sz = max(6, int(self.app.sq_sz * 0.18))
        dot_x = bar_x + (bar_w - dot_sz) // 2
        dot_y = int(self.indicator_y - dot_sz // 2)
        
        # Dynamic dot color (Contrasts the background it is resting on)
        dot_col = (40, 40, 40) if win_chance > 0.5 else (240, 240, 240)
        pygame.draw.ellipse(self.screen, dot_col, (dot_x, dot_y, dot_sz, dot_sz))
        pygame.draw.ellipse(self.screen, (120, 120, 120), (dot_x, dot_y, dot_sz, dot_sz), 1)

        # 6. CHANGE PULSE (Retained: brief glow when evaluation changes quickly)
        if abs(self.wdl_velocity) > 0.015:  # Tuned threshold for WDL scale
            glow_alpha = int(min(180, abs(self.wdl_velocity) * 4000))
            glow = pygame.Surface((bar_w, bar_h), pygame.SRCALPHA)
            glow.fill((255, 255, 255, glow_alpha // 6))
            self.screen.blit(glow, (bar_x, bar_y))

        # 7. DRAW TEXT (Retained: Centipawn or Mate)
        font = self.app.font_s
        current_depth = getattr(self.app, 'current_depth', 0)

        if hasattr(self.app, 'board') and self.app.board.board_fen() == chess.STARTING_BOARD_FEN:
            txt_str = "0.00"
        elif getattr(self.app, 'is_analyzing', False) and current_depth < 5:
            txt_str = "0.00"
        else:
            txt_str = getattr(self.app, 'real_time_score', "0.00")
        txt_surf = font.render(txt_str, True, (220, 220, 220))
        txt_x = bar_x - 8 - txt_surf.get_width()
        txt_y = bar_y + (bar_h - txt_surf.get_height()) // 2
        self.screen.blit(txt_surf, (txt_x, txt_y))

        # 8. DRAW ENHANCED DEPTH AND ENGINE INFO
        self._draw_engine_info(bar_x, bar_y, bar_w, bar_h)

        # 9. LOG EVAL VALUES (Retained: Periodically flush telemetry to CSV)
        try:
            t = pygame.time.get_ticks()
            # Saving the Target CP and the new Visual Win Percentage!
            self.eval_log.append((t, float(target_eval), float(win_chance * 100)))
            if len(self.eval_log) >= 120:
                path = os.path.join('assets', 'eval_trace.csv')
                write_header = not os.path.exists(path)
                try:
                    with open(path, 'a', newline='') as f:
                        w = csv.writer(f)
                        if write_header:
                            w.writerow(['t_ms','target_eval_cp','vis_win_pct'])
                        for row in self.eval_log:
                            w.writerow(row)
                except Exception:
                    pass
                self.eval_log = []
        except Exception:
            pass

    def _draw_engine_info(self, bar_x, bar_y, bar_w, bar_h):
        """Draw live depth and engine information with sleek design"""
        # Get current engine state
        current_depth = getattr(self.app, 'current_depth', 0)
        max_depth = getattr(self.app, 'max_depth', 20)
        nodes_per_second = getattr(self.app, 'nodes_per_second', 0)
        engine_status = getattr(self.app, 'engine_status', 'Ready')
        is_analyzing = getattr(self.app, 'is_analyzing', False)
        
        # Create info panel background
        panel_x = bar_x - 120
        panel_y = bar_y + 10
        panel_w = 100
        panel_h = 80
        
        # Sleek background with rounded corners
        panel_surface = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        pygame.draw.rect(panel_surface, (25, 25, 28, 200), (0, 0, panel_w, panel_h), border_radius=8)
        pygame.draw.rect(panel_surface, (60, 60, 65, 100), (0, 0, panel_w, panel_h), border_radius=8, width=1)
        self.screen.blit(panel_surface, (panel_x, panel_y))
        
        # Font setup
        small_font = pygame.font.Font(None, 16)
        tiny_font = pygame.font.Font(None, 12)
        
        # Depth indicator with progress bar
        depth_text = f"Depth: {current_depth}"
        depth_surf = small_font.render(depth_text, True, (200, 200, 200))
        self.screen.blit(depth_surf, (panel_x + 5, panel_y + 5))
        
        # Depth progress bar
        progress_bar_y = panel_y + 22
        progress_bar_w = panel_w - 10
        progress_bar_h = 4
        progress_fill = min(1.0, current_depth / max_depth) if max_depth > 0 else 0
        
        # Background bar
        pygame.draw.rect(self.screen, (40, 40, 45), 
                        (panel_x + 5, progress_bar_y, progress_bar_w, progress_bar_h), 
                        border_radius=2)
        
        # Animated fill bar
        if is_analyzing:
            fill_color = (100, 200, 100) if progress_fill > 0.7 else (200, 200, 100) if progress_fill > 0.3 else (200, 100, 100)
            pygame.draw.rect(self.screen, fill_color,
                           (panel_x + 5, progress_bar_y, int(progress_bar_w * progress_fill), progress_bar_h),
                           border_radius=2)
        
        # Nodes per second
        if nodes_per_second > 1000:
            nps_text = f"{nodes_per_second//1000}k n/s"
        else:
            nps_text = f"{nodes_per_second} n/s"
        nps_surf = tiny_font.render(nps_text, True, (150, 150, 150))
        self.screen.blit(nps_surf, (panel_x + 5, panel_y + 32))
        
        # Engine status with color coding
        status_colors = {
            'Ready': (100, 200, 100),
            'Analyzing': (200, 200, 100),
            'Error': (200, 100, 100),
            'Offline': (150, 150, 150)
        }
        status_color = status_colors.get(engine_status, (150, 150, 150))
        
        # Add pulsing effect for analyzing status
        if is_analyzing:
            pulse = abs(math.sin(pygame.time.get_ticks() * 0.003)) * 0.5 + 0.5
            status_color = tuple(int(c * (0.7 + 0.3 * pulse)) for c in status_color)
        
        status_surf = tiny_font.render(engine_status, True, status_color)
        self.screen.blit(status_surf, (panel_x + 5, panel_y + 48))
        
        # Network status indicator
        network_status = getattr(self.app, 'network_status', 'offline')
        network_icon = "🟢" if network_status == 'online' else "🔴"
        network_surf = tiny_font.render(network_icon, True, (150, 150, 150))
        self.screen.blit(network_surf, (panel_x + 5, panel_y + 62))

    def _draw_chat_commentary(self, x, y, w, h):
        """Draw game-based chat commentary panel"""
        if not hasattr(self.app, 'chat_messages') or not self.app.chat_messages:
            return
        
        # Create chat panel
        panel_surface = pygame.Surface((w, h), pygame.SRCALPHA)
        panel_surface.fill((20, 20, 25, 180))
        pygame.draw.rect(panel_surface, (60, 60, 65, 100), (0, 0, w, h), border_radius=8, width=1)
        self.screen.blit(panel_surface, (x, y))
        
        # Font setup
        chat_font = pygame.font.Font(None, 14)
        header_font = pygame.font.Font(None, 16)
        
        # Header
        header_surf = header_font.render("Game Analysis", True, (200, 200, 200))
        self.screen.blit(header_surf, (x + 10, y + 5))
        
        # Display recent messages
        messages = self.app.chat_messages[-5:]  # Show last 5 messages
        msg_y = y + 25
        
        for i, msg in enumerate(messages):
            if msg_y + 20 > y + h - 10:
                break
                
            # Message category color
            category_colors = {
                'brilliant': (0, 200, 200),
                'great': (100, 150, 200),
                'good': (100, 200, 100),
                'blunder': (200, 100, 100),
                'mistake': (200, 150, 100),
                'inaccuracy': (200, 200, 100),
                'book': (150, 150, 150)
            }
            
            if isinstance(msg, dict):
                category = msg.get('category', 'book')
                move_text = msg.get('move', '')
                commentary = msg.get('commentary', '')
            else:
                category = 'book'
                move_text = ''
                commentary = str(msg)
                
            color = category_colors.get(category, (150, 150, 150))
            
            if move_text:
                move_surf = chat_font.render(f"{move_text}:", True, color)
                self.screen.blit(move_surf, (x + 10, msg_y))
                msg_y += 15
                
                # Word wrap for long commentary
                words = commentary.split(' ')
                line = ''
                for word in words:
                    test_line = line + word + ' '
                    test_surf = chat_font.render(test_line, True, (180, 180, 180))
                    if test_surf.get_width() > w - 20:
                        if line:
                            line_surf = chat_font.render(line.strip(), True, (180, 180, 180))
                            self.screen.blit(line_surf, (x + 15, msg_y))
                            msg_y += 15
                        line = word + ' '
                    else:
                        line = test_line
                
                if line:
                    line_surf = chat_font.render(line.strip(), True, (180, 180, 180))
                    self.screen.blit(line_surf, (x + 15, msg_y))
                    msg_y += 20
            else:
                # General message
                msg_surf = chat_font.render(commentary, True, (180, 180, 180))
                self.screen.blit(msg_surf, (x + 10, msg_y))
                msg_y += 18

    def rescale_pieces(self):
        t = int(self.app.sq_sz * 0.9)
        self.scaled = {}
        for k, img in self.assets.pieces.items():
            s = min(t/img.get_width(), t/img.get_height())
            scaled_img = pygame.transform.smoothscale(img, (int(img.get_width()*s), int(img.get_height()*s)))
            self.scaled[k] = scaled_img.convert_alpha()  # Pre-convert for performance

    def draw_board(self):
        # Ensure scaling is correct
        if not self.scaled: self.rescale_pieces()

        ox, oy, sq_sz = self.app.bd_x, self.app.bd_y, self.app.sq_sz
        cols = THEME[self.app.board_style]
        
        # Create a copy of the board for game state checks
        with self.app.lock:
            tmp = self.app.board.copy()
        
        # Check if board state changed for dirty rect optimization
        current_fen = self.app.board.fen()
        current_view_ply = self.app.view_ply

        # --- FIX: Also check if we just picked up or dropped a piece ---
        current_drag_sq = self.app.dragging_piece[1] if self.app.dragging_piece else None

        board_changed = current_fen != self.last_board_fen
        drag_changed = current_drag_sq != getattr(self, 'last_drag_sq', None)
        # view_ply navigation never changes board.fen(), so track it separately
        view_ply_changed = current_view_ply != getattr(self, 'last_view_ply_cache', None)

        # Invalidate the static cache if a move was made, drag changed, or user navigated history
        if board_changed or drag_changed or view_ply_changed or not self.app.static_board_surface:
            self._create_static_layers()
            self.last_board_fen = current_fen
            self.last_drag_sq = current_drag_sq
            self.last_view_ply_cache = current_view_ply
        
        # Draw static board surface
        if self.app.static_board_surface:
            self.screen.blit(self.app.static_board_surface, (ox, oy))
        
        if self.app.static_pieces_surface:
            self.screen.blit(self.app.static_pieces_surface, (ox, oy))
        
        # --- PRE-CALCULATE DRAG STATE ---
        # A drag is "active" (piece floating at cursor) whenever dragging_piece is set
        # AND the left mouse button is still physically held down.
        # Using get_pressed() here is the correct guard: the moment the button is released,
        # is_dragging_active goes False, which stops the ghost from being rendered on the
        # very next frame BEFORE handle_click("up") has had a chance to clear dragging_piece.
        is_dragging_active = False
        if self.app.dragging_piece and pygame.mouse.get_pressed()[0]:
            is_dragging_active = True
            self.app.animation_active = True
        elif not self.app.dragging_piece:
            self.app.animation_active = False

        # --- PRE-MOVE HIGHLIGHT (all queued premoves, no arrow) ---
        _pm_queue = getattr(self.app, 'pre_move_queue', None) or []
        if _pm_queue:
            _pm_alpha = {}
            for _pm_entry in _pm_queue:
                for _pm_sq in [_pm_entry[0], _pm_entry[1]]:
                    _pm_alpha[_pm_sq] = min(200, _pm_alpha.get(_pm_sq, 0) + 80)
            for _pm_sq, _alpha in _pm_alpha.items():
                _f2 = chess.square_file(_pm_sq)
                _r2 = chess.square_rank(_pm_sq)
                if self.app.playing_white: _r2 = 7 - _r2
                else: _f2 = 7 - _f2
                _ps = pygame.Surface((sq_sz, sq_sz), pygame.SRCALPHA)
                _ps.fill((70, 110, 220, _alpha))
                self.screen.blit(_ps, (ox + _f2 * sq_sz, oy + _r2 * sq_sz))

        # --- DRAW VALID MOVES (Transparent & Behind Pieces) ---
        if self.app.selected is not None:
            if not is_dragging_active:
                yellow_hl = (255, 255, 153, 120)
                self.hl_sq(self.app.selected, yellow_hl)
            dot_surface = pygame.Surface((sq_sz, sq_sz), pygame.SRCALPHA)
            pygame.draw.circle(dot_surface, (100, 100, 100, 128), (sq_sz//2, sq_sz//2), sq_sz//7)
            for m in self.app.valid_moves:
                fx = (7-chess.square_file(m.to_square)) if not self.app.playing_white else chess.square_file(m.to_square)
                fy = chess.square_rank(m.to_square) if not self.app.playing_white else (7-chess.square_rank(m.to_square))
                dot_rect = pygame.Rect(ox + fx*sq_sz, oy + fy*sq_sz, sq_sz, sq_sz)
                self.screen.blit(dot_surface, dot_rect)

        # 3.5 Arrows (Hints & User) - DRAWN FIRST SO THEY SLIDE BEHIND PIECES
        if self.app.show_hints:
            for pts, c in self.app.arrows: 
                hint_move = chess.Move(pts[0], pts[1])
                if len(c) == 4 and c[3] <= 130:
                    self.draw_dashed_arrow(hint_move, c)
                else:
                    self.draw_arrow(hint_move, c)
        
        for start, end in self.app.user_arrows:
            m = chess.Move(start, end)
            self.draw_dashed_arrow(m, THEME["trainer_arrow"])
            
        if self.app.temp_arrow_start is not None and self.app.temp_arrow_end is not None:
            if self.app.temp_arrow_start != self.app.temp_arrow_end:
                 m = chess.Move(self.app.temp_arrow_start, self.app.temp_arrow_end)
                 self.draw_dashed_arrow(m, THEME["trainer_arrow"])

        if self.app.trainer_hint_arrow:
            self.draw_dashed_arrow(self.app.trainer_hint_arrow, THEME["trainer_arrow"])

        # 5. Dragged Piece (On Top) - Use Rect for smooth movement
        if is_dragging_active and self.app.dragging_piece:
            p = self.app.dragging_piece[0]
            k = self.get_piece_key(p)
            if k in self.scaled:
                img = self.scaled[k]
                mx, my = pygame.mouse.get_pos()
                # Update Rect position for smooth sub-pixel movement
                self.app.drag_pos_Rect.x = mx - sq_sz/2
                self.app.drag_pos_Rect.y = my - sq_sz/2
                
                # By passing the float attributes directly, Pygame-CE natively handles 
                # the sub-pixel positioning for perfectly smooth 144hz tracking
                self.screen.blit(img, (self.app.drag_pos_Rect.x, self.app.drag_pos_Rect.y))
                
        # --- NEW: Draw the Perfect Eval Bar ---
        # Adjust these numbers (x, y, w, h) to fit your specific layout!
        # Example: Placing it to the RIGHT of the board
        
        bar_x = self.app.bd_x + self.app.bd_sz + 10  # 10px to the right of board
        bar_y = self.app.bd_y                        # Same Y as board top
        bar_w = 20                                   # 20px wide
        bar_h = self.app.bd_sz                       # Same height as board

        # 7. Eval Icons & Move Animations
        icon_data = None
        show_annot = self.app.settings.get("live_annotations", True)

        # Track manual move navigation to trigger animations dynamically
        if not hasattr(self, 'last_view_ply'):
            self.last_view_ply = self.app.view_ply
            self.last_view_time = time.time()
            
        if self.last_view_ply != self.app.view_ply:
            self.last_view_ply = self.app.view_ply
            self.last_view_time = time.time()

        if show_annot:
            if 0 < self.app.view_ply <= len(self.app.history):
                hist_item = self.app.history[self.app.view_ply - 1]
                if "review" in hist_item and "class" in hist_item["review"]:
                    icon_data = {"sq": hist_item["move"].to_square, "class": hist_item["review"]["class"]}
            
            if not icon_data and self.app.view_ply == self.app.board.ply():
                if hasattr(self.app, 'last_move_analysis') and self.app.last_move_analysis:
                    icon_data = self.app.last_move_analysis

        if icon_data:
            sq = icon_data["sq"]
            raw_cls = icon_data["class"]
            
            cls = "eval_book" if raw_cls == "book" and "eval_book" in self.assets.icons else raw_cls
            
            f = chess.square_file(sq); r = chess.square_rank(sq)
            if self.app.playing_white: r = 7 - r
            else: f = 7 - f
            bx = self.app.bd_x + f * self.app.sq_sz
            by = self.app.bd_y + r * self.app.sq_sz
            
            # --- FLOATING POPUP ANIMATION (Live + Manual Navigation) ---
            if raw_cls in ["great", "brilliant", "book"]:
                # Tied to view time so it works perfectly with arrow keys!
                elapsed = time.time() - self.last_view_time
                
                if elapsed < 2.0:
                    anim_colors = {
                        "brilliant": (20, 180, 160), 
                        "great": (50, 100, 250), 
                        "book": (160, 110, 90)
                    }
                    anim_labels = {
                        "brilliant": "Brilliant!", 
                        "great": "Great Move!", 
                        "book": "Book Move!"
                    }
                    
                    # Phase Math: 0.5s Fade In -> 1.0s Hold -> 0.5s Fade Out
                    if elapsed < 0.5:
                        # FADE IN: 0% to 100% over 0.5 seconds
                        alpha = int((elapsed / 0.5) * 255)
                        # Drops down 20 pixels smoothly into place
                        y_offset = 20 * (1 - (elapsed / 0.5)) 
                    elif elapsed < 1.5:
                        # HOLD STABLE: Fully visible
                        alpha = 255
                        y_offset = 0
                    else:
                        # FADE OUT: 100% to 0% over 0.5 seconds
                        alpha = int((1 - ((elapsed - 1.5) / 0.5)) * 255)
                        # Floats up 15 pixels gracefully
                        y_offset = -15 * ((elapsed - 1.5) / 0.5)
                    
                    alpha = max(0, min(255, alpha))
                    
                    if alpha > 0:
                        color = anim_colors.get(raw_cls, (100, 100, 100))
                        
                        # --- MODIFIED: Reduced opacity from 0.4 (40%) to 0.2 (20%) ---
                        highlight = pygame.Surface((self.app.sq_sz, self.app.sq_sz), pygame.SRCALPHA)
                        highlight.fill((color[0], color[1], color[2], int(alpha * 0.2))) 
                        self.screen.blit(highlight, (bx, by))
                        
                        # B. Floating Text Bubble
                        text_str = anim_labels.get(raw_cls, "Great!")
                        txt_surf = self.app.font_b.render(text_str, True, (255, 255, 255))
                        
                        pad_x, pad_y = 12, 6
                        bubble_w = txt_surf.get_width() + pad_x * 2
                        bubble_h = txt_surf.get_height() + pad_y * 2
                        
                        icon_img = self.assets.icons.get(cls)
                        if icon_img: bubble_w += 26
                        
                        bubble_x = bx + (self.app.sq_sz - bubble_w) // 2
                        bubble_y = by - bubble_h - 10 + y_offset
                        
                        bubble_surf = pygame.Surface((bubble_w, bubble_h), pygame.SRCALPHA)
                        pygame.draw.rect(bubble_surf, (*color, alpha), bubble_surf.get_rect(), border_radius=8)
                        
                        text_start_x = pad_x
                        if icon_img:
                            scaled_ic = pygame.transform.smoothscale(icon_img, (20, 20))
                            scaled_ic.set_alpha(alpha)
                            bubble_surf.blit(scaled_ic, (pad_x, pad_y + (txt_surf.get_height() - 20)//2))
                            text_start_x += 26
                            
                        txt_surf.set_alpha(alpha)
                        bubble_surf.blit(txt_surf, (text_start_x, pad_y))
                        self.screen.blit(bubble_surf, (bubble_x, bubble_y))

            # --- STANDARD STATIC ICON ---
            icon = self.assets.icons.get(cls)
            if icon:
                isz = int(self.app.sq_sz * 0.35)
                icon_scaled = pygame.transform.smoothscale(icon, (isz, isz))
                self.screen.blit(icon_scaled, (bx + self.app.sq_sz - isz + 4, by - 8))

        # 8. Game Over / Check Animations
        # Re-use the elapsed time tracker from the navigation logic
        elapsed = time.time() - getattr(self, 'last_view_time', time.time())
        
        if elapsed < 2.5: # 2.5 second duration for these alerts
            bubbles = [] # List of (square, text, color)
            
            if tmp.is_game_over():
                if tmp.is_checkmate():
                    loser = tmp.turn
                    winner = not tmp.turn
                    l_king = tmp.king(loser)
                    w_king = tmp.king(winner)
                    if l_king is not None: bubbles.append((l_king, "Checkmate", (200, 50, 50))) # Red
                    if w_king is not None: bubbles.append((w_king, "Winner", (50, 180, 50)))  # Green
                else:
                    wk = tmp.king(chess.WHITE)
                    bk = tmp.king(chess.BLACK)
                    if wk is not None: bubbles.append((wk, "Draw", (120, 120, 120))) # Grey
                    if bk is not None: bubbles.append((bk, "Draw", (120, 120, 120)))
                    
                    # Instantly update main UI status message with the specific draw reason!
                    if self.app.view_ply == len(self.app.history):
                        if tmp.is_stalemate(): self.app.status_msg = "Draw by Stalemate"
                        elif tmp.is_insufficient_material(): self.app.status_msg = "Draw (Insufficient Material)"
                        elif tmp.is_repetition(): self.app.status_msg = "Draw by Repetition"
                        elif tmp.is_fifty_moves(): self.app.status_msg = "Draw (50-Move Rule)"
                        else: self.app.status_msg = "Game Drawn"
            elif tmp.is_check():
                chk_king = tmp.king(tmp.turn)
                if chk_king is not None: bubbles.append((chk_king, "Check", (220, 120, 30))) # Orange
            
            # Animate the collected bubbles!
            if bubbles:
                # Phase Math: 0.5s Fade In -> 1.5s Hold -> 0.5s Fade Out
                if elapsed < 0.5:
                    alpha = int((elapsed / 0.5) * 255)
                    y_offset = 20 * (1 - (elapsed / 0.5))
                elif elapsed < 2.0:
                    alpha = 255
                    y_offset = 0
                else:
                    alpha = int((1 - ((elapsed - 2.0) / 0.5)) * 255)
                    y_offset = -15 * ((elapsed - 2.0) / 0.5)

                alpha = max(0, min(255, alpha))
                
                if alpha > 0:
                    for sq_king, txt_str, color in bubbles:
                        f = chess.square_file(sq_king)
                        r = chess.square_rank(sq_king)
                        if self.app.playing_white: r = 7 - r
                        else: f = 7 - f
                        bx = self.app.bd_x + f * self.app.sq_sz
                        by = self.app.bd_y + r * self.app.sq_sz
                        
                        # A. Colored Highlight behind the King
                        highlight = pygame.Surface((self.app.sq_sz, self.app.sq_sz), pygame.SRCALPHA)
                        highlight.fill((color[0], color[1], color[2], int(alpha * 0.3))) 
                        self.screen.blit(highlight, (bx, by))
                        
                        # B. Floating Status Bubble
                        txt_surf = self.app.font_b.render(txt_str, True, (255, 255, 255))
                        pad_x, pad_y = 12, 6
                        bubble_w = txt_surf.get_width() + pad_x * 2
                        bubble_h = txt_surf.get_height() + pad_y * 2
                        
                        bubble_x = bx + (self.app.sq_sz - bubble_w) // 2
                        bubble_y = by - bubble_h - 10 + y_offset
                        
                        # --- FIX: Boundary Check for Top-Row Kings ---
                        # If the bubble goes above the board, flip it to show BELOW the King
                        if bubble_y < self.app.bd_y:
                            bubble_y = by + self.app.sq_sz + 10 - y_offset
                        
                        bubble_surf = pygame.Surface((bubble_w, bubble_h), pygame.SRCALPHA)
                        pygame.draw.rect(bubble_surf, (*color, alpha), bubble_surf.get_rect(), border_radius=8)
                        
                        txt_surf.set_alpha(alpha)
                        bubble_surf.blit(txt_surf, (pad_x, pad_y))
                        self.screen.blit(bubble_surf, (bubble_x, bubble_y))

    def _create_static_layers(self):
        """Create static board and pieces surfaces for dirty rect optimization"""
        ox, oy, sq_sz = self.app.bd_x, self.app.bd_y, self.app.sq_sz
        cols = THEME[self.app.board_style]
        
        # Create static board surface
        self.app.static_board_surface = pygame.Surface((sq_sz * 8, sq_sz * 8))
        self.app.static_board_surface.convert()  # Optimize for display
        
        # Draw board squares
        for r in range(8):
            for c in range(8):
                dr = r if not self.app.playing_white else (7-r)
                dc = (7-c) if not self.app.playing_white else c
                c_sq = cols["light"] if (r+c)%2==0 else cols["dark"]
                pygame.draw.rect(self.app.static_board_surface, c_sq, (c*sq_sz, r*sq_sz, sq_sz, sq_sz))
        
        # Create static pieces surface
        self.app.static_pieces_surface = pygame.Surface((sq_sz * 8, sq_sz * 8), pygame.SRCALPHA)
        self.app.static_pieces_surface.convert_alpha()
        
        # Draw last move highlights
        if self.app.view_ply > 0 and len(self.app.history) >= self.app.view_ply:
            step = self.app.history[self.app.view_ply-1]
            if isinstance(step, dict) and "move" in step:
                m = step["move"]
                # --- FIX: Override theme with Faint Light Yellow ---
                yellow_hl = (255, 255, 153, 120)
                self._hl_sq_static(m.from_square, yellow_hl)
                self._hl_sq_static(m.to_square, yellow_hl)
        
        # Draw threat arrow if enabled
        if self.app.show_threats and getattr(self.app, 'threat_arrow', None):
            try:
                m = chess.Move(self.app.threat_arrow[0], self.app.threat_arrow[1])
                self.draw_arrow(m, (30, 160, 240, 150), target_surface=self.app.static_pieces_surface)
            except Exception:
                pass
        
        # Draw static pieces
        with self.app.lock:
            tmp = self.app.board.copy()
        
        while tmp.ply() > self.app.view_ply:
            if not tmp.move_stack: break
            tmp.pop()
        
        for s in chess.SQUARES:
            # Skip the dragged piece's origin square while button is held.
            # Once the button is released, dragging_piece may still be set for one frame
            # before handle_click clears it — so also check get_pressed() here to avoid
            # baking a ghost into the static surface prematurely.
            if self.app.dragging_piece and pygame.mouse.get_pressed()[0] and self.app.dragging_piece[1] == s:
                continue
            p = tmp.piece_at(s)
            if p:
                self._draw_piece_static(p, s)
    
    def _hl_sq_static(self, sq, col):
        """Highlight square on static surface"""
        f = chess.square_file(sq)
        r = chess.square_rank(sq)
        if self.app.playing_white: r = 7 - r
        else: f = 7 - f
        x = f * self.app.sq_sz
        y = r * self.app.sq_sz
        s = pygame.Surface((self.app.sq_sz, self.app.sq_sz), pygame.SRCALPHA)
        s.fill(col)
        self.app.static_board_surface.blit(s, (x, y))

    def hl_sq(self, sq, col):
        """Dynamically highlight a square on the active screen"""
        f = chess.square_file(sq)
        r = chess.square_rank(sq)
        if self.app.playing_white: r = 7 - r
        else: f = 7 - f
        x = self.app.bd_x + f * self.app.sq_sz
        y = self.app.bd_y + r * self.app.sq_sz
        s = pygame.Surface((self.app.sq_sz, self.app.sq_sz), pygame.SRCALPHA)
        s.fill(col)
        self.screen.blit(s, (x, y))
    
    def _draw_piece_static(self, p, sq):
        """Draw piece on static surface"""
        if p is None: return 
        sz = self.app.sq_sz
        f = chess.square_file(sq); r = chess.square_rank(sq)
        if self.app.playing_white: r = 7 - r
        else: f = 7 - f
        x, y = f*sz, r*sz
        try:
            k = ('w' if p.color else 'b') + p.symbol().lower()
            if k in self.scaled:
                img = self.scaled[k]
                self.app.static_pieces_surface.blit(img, (x+(sz-img.get_width())//2, y+(sz-img.get_height())//2))
        except: pass

    def draw_piece(self, p, sq):
        if p is None: return 
        sz = self.app.sq_sz
        f = chess.square_file(sq); r = chess.square_rank(sq)
        if self.app.playing_white: r = 7 - r
        else: f = 7 - f
        x, y = self.app.bd_x + f*sz, self.app.bd_y + r*sz
        try:
            k = ('w' if p.color else 'b') + p.symbol().lower()
            if k in self.scaled:
                img = self.scaled[k]
                self.screen.blit(img, (x+(sz-img.get_width())//2, y+(sz-img.get_height())//2))
        except: pass

    def draw_arrow(self, m, col, target_surface=None):
        self._render_arrow_geometry(m, col, is_dashed=False, target_surface=target_surface)
        
    def draw_dashed_arrow(self, m, col, target_surface=None):
        self._render_arrow_geometry(m, col, is_dashed=True, target_surface=target_surface)

    def _render_arrow_geometry(self, m, col, is_dashed, target_surface=None):
        """Draws arrow geometry, handling both straight and multi-segment knight paths."""
        sz = self.app.sq_sz; ox, oy = self.app.bd_x, self.app.bd_y
        s, e = m.from_square, m.to_square
        
        fs, rs = chess.square_file(s), chess.square_rank(s)
        fe, re = chess.square_file(e), chess.square_rank(e)
        
        df = abs(fs - fe)
        dr = abs(rs - re)
        is_knight = (df == 1 and dr == 2) or (df == 2 and dr == 1)
        
        if self.app.playing_white:
            persp_rs, persp_re = 7-rs, 7-re
            persp_fs, persp_fe = fs, fe
        else:
            persp_fs, persp_fe = 7-fs, 7-fe
            persp_rs, persp_re = rs, re
            
        sx, sy = ox + persp_fs * sz + sz // 2, oy + persp_rs * sz + sz // 2
        ex, ey = ox + persp_fe * sz + sz // 2, oy + persp_re * sz + sz // 2
        
        w_t = sz * 0.14
        if is_dashed: w_t = sz * 0.03
        w_h, l_h = sz * 0.35, sz * 0.35 
        
        surf = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        
        # --- NEW: Arrowhead Transparency Logic ---
        # If dashed, make the head color 50% more transparent than the line
        head_col = col
        if is_dashed:
            r, g, b = col[:3]
            a = col[3] if len(col) > 3 else 255
            head_col = (r, g, b, int(a * 0.5)) 
        
        if is_knight:
            # --- L-SHAPE KNIGHT ARROW ---
            if dr > df: fc, r_c = fs, chess.square_rank(e)
            else: fc, r_c = chess.square_file(e), rs
                
            corner_f, corner_r = fc, r_c
            if self.app.playing_white: corner_r = 7 - corner_r
            else: corner_f = 7 - corner_f
            cx, cy = ox + corner_f * sz + sz // 2, oy + corner_r * sz + sz // 2
            
            # --- FIX: Math for the second segment to stop it perfectly ---
            dx2, dy2 = ex - cx, ey - cy
            ang = math.atan2(dy2, dx2)
            hyp2 = math.hypot(dx2, dy2)
            
            # 1. Stop the tip of the arrow just before the center of the square
            final = max(0, hyp2 - sz * 0.25)
            tip_x = cx + math.cos(ang) * final
            tip_y = cy + math.sin(ang) * final
            
            # 2. Stop the thick line before the arrowhead so it doesn't poke out!
            line_end = max(0, final - l_h + 2) 
            lex = cx + math.cos(ang) * line_end
            ley = cy + math.sin(ang) * line_end

            if is_dashed:
                dash_len = 15; gap_len = 10; curr_dist = 0
                
                # Segment 1 (Start to Corner)
                line1_len = math.hypot(cx-sx, cy-sy)
                while curr_dist < line1_len:
                    draw_len = min(dash_len, line1_len - curr_dist)
                    start_x = sx + (cx-sx) * (curr_dist / line1_len)
                    start_y = sy + (cy-sy) * (curr_dist / line1_len)
                    end_x = sx + (cx-sx) * ((curr_dist + draw_len) / line1_len)
                    end_y = sy + (cy-sy) * ((curr_dist + draw_len) / line1_len)
                    pygame.draw.line(surf, col, (start_x, start_y), (end_x, end_y), int(w_t))
                    curr_dist += dash_len + gap_len
                    
                # Segment 2 (Corner to Arrowhead Base)
                curr_dist = 0
                while curr_dist < line_end:
                    draw_len = min(dash_len, line_end - curr_dist)
                    start_x = cx + math.cos(ang) * curr_dist
                    start_y = cy + math.sin(ang) * curr_dist
                    end_x = cx + math.cos(ang) * (curr_dist + draw_len)
                    end_y = cy + math.sin(ang) * (curr_dist + draw_len)
                    pygame.draw.line(surf, col, (start_x, start_y), (end_x, end_y), int(w_t))
                    curr_dist += dash_len + gap_len
            else:
                # Draw both thick lines
                pygame.draw.line(surf, col, (sx, sy), (cx, cy), int(w_t))
                pygame.draw.line(surf, col, (cx, cy), (lex, ley), int(w_t))
                
                # --- FIX 3: Draw a circle at the elbow to perfectly round off the jagged gap! ---
                pygame.draw.circle(surf, col, (int(cx), int(cy)), int(w_t / 2.0))
            
            # Draw the properly positioned arrowhead
            head_pts = [
                (tip_x - l_h * math.cos(ang - math.pi/7), tip_y - l_h * math.sin(ang - math.pi/7)),
                (tip_x, tip_y),
                (tip_x - l_h * math.cos(ang + math.pi/7), tip_y - l_h * math.sin(ang + math.pi/7))
            ]
            # Use semi-transparent color for dashed heads
            pygame.draw.polygon(surf, head_col if is_dashed else col, head_pts)
            
        else:
            # --- STRAIGHT ARROW LOGIC ---
            dx, dy = ex - sx, ey - sy
            ang = math.atan2(dy, dx); hyp = math.hypot(dx, dy)
            final = max(0, hyp - sz * 0.25)
            
            ux, uy = math.cos(ang), math.sin(ang)
            
            if is_dashed:
                dash_len = 15; gap_len = 10; curr_dist = 0
                while curr_dist < final:
                    draw_len = min(dash_len, final - curr_dist)
                    start_x = sx + ux * curr_dist
                    start_y = sy + uy * curr_dist
                    end_x = sx + ux * (curr_dist + draw_len)
                    end_y = sy + uy * (curr_dist + draw_len)
                    pygame.draw.line(surf, col, (start_x, start_y), (end_x, end_y), int(w_t))
                    curr_dist += dash_len + gap_len
                
                tip_x = sx + ux * final
                tip_y = sy + uy * final
                head_pts = [
                    (final - l_h, -w_h / 2),
                    (final, 0),
                    (final - l_h, w_h / 2)
                ]
                rot_head = []
                c, s_sin = ux, uy
                for x, y in head_pts:
                    rot_head.append((x * c - y * s_sin + sx, x * s_sin + y * c + sy))
                pygame.draw.polygon(surf, head_col, rot_head) # Apply semi-transparent color

            else:
                pts = [
                    (0, -w_t / 2),
                    (final - l_h, -w_t / 2),
                    (final - l_h, -w_h / 2),
                    (final, 0),
                    (final - l_h, w_h / 2),
                    (final - l_h, w_t / 2),
                    (0, w_t / 2)
                ]
                rot = []
                c, s_sin = ux, uy
                for x, y in pts:
                    rot.append((x * c - y * s_sin + sx, x * s_sin + y * c + sy))
                pygame.draw.polygon(surf, col, rot)
                
        # Draw to the requested surface, or fallback to the main screen
        target = target_surface if target_surface else self.screen
        target.blit(surf, (0,0))

    def get_sq_coords(self, sq):
        f = chess.square_file(sq); r = chess.square_rank(sq)
        if self.app.playing_white: r = 7 - r
        else: f = 7 - f
        return (self.app.bd_x + f*self.app.sq_sz, self.app.bd_y + r*self.app.sq_sz)

    def get_piece_key(self, p):
        if not p: return "" 
        return ('w' if p.color else 'b') + p.symbol().lower()

    def panel(self, x, y, w, h):
        r = pygame.Rect(x, y, w, h)
        pygame.draw.rect(self.screen, THEME["panel"], r, border_radius=8)
        pygame.draw.rect(self.screen, THEME["border"], r, 1, border_radius=8)

    def draw_multiline_text(self, text, font, color, x, y, max_width, draw=True):
        words = text.split(' ')
        lines = []
        current_line = []
        for word in words:
            test_line = ' '.join(current_line + [word])
            w, h = font.size(test_line)
            if w < max_width: current_line.append(word)
            else: lines.append(' '.join(current_line)); current_line = [word]
        lines.append(' '.join(current_line))
        line_height = font.get_height()
        total_h = len(lines) * (line_height + 2)
        if draw:
            current_y = y
            for line in lines:
                img = font.render(line, True, color)
                self.screen.blit(img, (x, current_y))
                current_y += line_height + 2
        return total_h

    def draw_btn(self, x, y, txt, tag, width=None, font=None, min_w=130): 
        if font is None: font = self.app.font_m
        s = font.render(txt, True, (0,0,0))
        w = width if width else min_w
        r = pygame.Rect(x, y, w, 40)
        
        col = (255, 255, 255)
        if tag == "enginehint" and self.app.show_hints: col = (180, 255, 180)
        elif tag == "theme" and self.app.board_style == "green": col = (200, 230, 200)
        elif tag == "mode" and self.app.mode == "trainer": col = (200, 220, 255)
        elif tag == "puzzles" and self.app.mode == "puzzle": col = (255, 240, 180)
        elif r.collidepoint(pygame.mouse.get_pos()): col = (230, 230, 240)
            
        pygame.draw.rect(self.screen, col, r, border_radius=8)
        pygame.draw.rect(self.screen, (200, 200, 200), r, 1, border_radius=8)
        
        # --- FIX: Map Custom Icons ---
        # --- FIX 2: Icon Mappings ---
        ic_key = tag
        if tag == "gm_move": ic_key = "gm_icon" 
        elif tag == "profile": ic_key = "pgnload" 
        elif tag == "settings": ic_key = "settings"
        
        icon = self.assets.icons.get(ic_key)
        
        tx = r.centerx - s.get_width()//2
        if icon:
            self.screen.blit(pygame.transform.smoothscale(icon, (24, 24)), (r.x + 10, r.centery - 12))
            tx = r.x + 45 
        self.screen.blit(s, (tx, r.centery - s.get_height()//2))
        self.app.btn_rects[tag] = r
        return w

    def draw_ui(self):
        # --- FIX: Smooth Gliding Eval Bar with Text ---
        r = self.app.r_eval.copy()
        r.width = 45 # Widen the bar for text clearance
        
        # Initialize the smoothing tracker if it doesn't exist
        if not hasattr(self, 'smooth_eval'):
            self.smooth_eval = 0.0
            
        pygame.draw.rect(self.screen, THEME["eval_bar_bg"], r)
        
        target_eval = getattr(self.app, 'eval_val', 0)
        
        # Enforce exact 0.0 start
        if self.app.view_ply == 0:
            target_eval = 0
            
        # Smooth gliding logic (Lerp)
        self.smooth_eval += (target_eval - self.smooth_eval) * 0.1
        
        # Calculate visual height using the smoothed value
        v = max(-2000, min(2000, self.smooth_eval))
        h = int(r.height * (0.5 - v / 4000))
        
        # Draw the white advantage section
        pygame.draw.rect(self.screen, THEME["eval_white"], (r.x, r.y + h, r.width, r.height - h))
        pygame.draw.rect(self.screen, (100, 100, 100), r, 2)
        
        # 1. Format the text directly from the Engine's exact string
        txt = getattr(self.app, 'real_time_score', "0.00")
            
        # 2. FIX: Always pin text to the bottom (White's side)
        # If Black is winning heavily, the dark bar covers the bottom, so flip text to white!
        if h > r.height - 40:
            txt_color = (220, 220, 220)  # Light text against dark bar
        else:
            txt_color = (40, 40, 40)     # Dark text against white bar
            
        txt_surf = self.app.font_s.render(txt, True, txt_color) 
        txt_rect = txt_surf.get_rect(center=(r.centerx, r.bottom - 20))
            
        self.screen.blit(txt_surf, txt_rect)
        # -----------------------------------------------
        
        x, y, w = self.app.sb_x, 20, self.app.sb_w

        # Compute Profile placement early so the sidebar content can avoid overlap
        left_margin = 8
        # Align profile top with the sidebar's top (bot panel y)
        top_margin = y
        avail_left = self.app.bd_x - left_margin - 20
        profile_in_sidebar = False
        if avail_left >= 60:
            prof_w = min(110, avail_left)
            prof_h = 36
            prof_x = left_margin
            prof_y = top_margin
            profile_in_sidebar = False
        else:
            prof_w = min(110, max(80, self.app.sb_w - 20))
            prof_h = 36
            prof_x = self.app.sb_x
            prof_y = top_margin
            profile_in_sidebar = True

        # If profile sits inside the sidebar, reserve left column width for it
        spacing = 8
        if profile_in_sidebar:
            reserve = prof_w + spacing
            x = self.app.sb_x + reserve
            w = max(120, self.app.sb_w - reserve)

        # Draw the Profile button (larger icon) at computed location
        # Use a slightly larger icon for profile to improve visibility
        try:
            self.draw_btn(prof_x, prof_y, "Profile", "profile", width=prof_w)
            # bump the icon size for profile specifically by re-drawing the icon overlay
            # draw_btn already registered the rect; adjust icon scale visually by overlay
            pr = self.app.btn_rects.get('profile')
            if pr:
                ic = self.assets.icons.get('pgnload')
                if ic:
                    self.screen.blit(pygame.transform.smoothscale(ic, (28, 28)), (pr.x + 8, pr.y + (pr.height - 28)//2))
        except Exception:
            pass
        
        # 1. BOT PANEL
        bot_name = "Player" if not self.app.active_bot else self.app.active_bot.get("name")
        av = self.assets.get_avatar(bot_name) if self.app.active_bot else self.assets.get_avatar("player")
        
        panel_h = 110
        self.panel(x, y, w, panel_h)
        if av: 
            scaled_av = self.assets.scale_keep_aspect(av, (80, 80))
            offset_x = (80 - scaled_av.get_width()) // 2
            offset_y = (80 - scaled_av.get_height()) // 2
            self.screen.blit(scaled_av, (x + 15 + offset_x, y + 15 + offset_y))
        self.screen.blit(self.app.font_b.render(bot_name, True, THEME["text"]), (x + 110, y + 20))
        
        # Special Green Text for Trainer Completion
        status_color = THEME["text_dim"]
        if "Completed" in self.app.status_msg: status_color = (20, 160, 20)
        
        parts = self.app.status_msg.split(". Date:", 1)
        self.screen.blit(self.app.font_m.render(parts[0], True, status_color), (x + 110, y + 50))
        if len(parts) > 1:
            self.screen.blit(self.app.font_m.render("Date: " + parts[1].strip(), True, status_color), (x + 110, y + 68))
        self.draw_btn(x + w - 95, y + 20, "Change", "bot", width=80, font=self.app.font_s)
        y += panel_h + 10

        # Align all subsequent sidebar boxes' left edge with the Profile button's left edge
        # Calculate new content area so boxes below the bot panel match profile left lining
        try:
            content_x = prof_x
        except Exception:
            content_x = x
        content_w = (x + w) - content_x
        # Use the new left-aligned content area for remaining panels
        x = content_x
        w = max(120, content_w)

        # 2. CHAT BOX
        chat_h = 160
        pygame.draw.rect(self.screen, THEME["chat_bg"], (x, y, w, chat_h), border_radius=8)
        
        # Determine the header text
        header_txt = f"{bot_name} says:" if self.app.active_bot else "Game Chat"
        
        # --- FIX: Use Stockfish icon when in Review/Analysis mode (no active bot) ---
        if not self.app.active_bot and getattr(self.app, 'stockfish_icon', None):
            self.screen.blit(self.app.stockfish_icon, (x + 10, y + 10))
        else:
            bot_av = self.assets.get_avatar(bot_name)
            if bot_av:
                icon_s = self.assets.scale_keep_aspect(bot_av, (30, 30))
                offset_x = (30 - icon_s.get_width()) // 2
                offset_y = (30 - icon_s.get_height()) // 2
                self.screen.blit(icon_s, (x + 10 + offset_x, y + 10 + offset_y))
            else:
                # Fallback blue square just in case
                pygame.draw.rect(self.screen, (50, 100, 200), (x + 10, y + 10, 30, 30))
                
        self.screen.blit(self.app.font_s.render(header_txt, True, (100,100,120)), (x + 45, y + 15))
        
        display_log = list(self.app.chat_log)
        if 0 < self.app.view_ply <= len(self.app.history):
            item = self.app.history[self.app.view_ply-1]
            if isinstance(item, dict) and "review" in item and isinstance(item["review"], dict) and item["review"].get("bot_reason"):
                display_log.append({"sender": bot_name, "msg": "[Analysis] " + item["review"]["bot_reason"]})

        content_rect = pygame.Rect(x + 10, y + 45, w - 20, chat_h - 55)
        self.screen.set_clip(content_rect)
        cy = y + 50
        msgs = display_log[-2:] 
        for m in msgs:
            is_bot = m["sender"] == bot_name
            bg = THEME["chat_bubble_bot"] if is_bot else THEME["chat_bubble_user"]
            # FIXED: Changed w-60 to w-70 so the background box height perfectly matches the text wrap!
            txt_h = self.draw_multiline_text(m["msg"], self.app.font_chat, (0,0,0), 0,0, w-70, draw=False)
            bx = x + 15 if is_bot else x + 35
            pygame.draw.rect(self.screen, bg, (bx, cy, w - 50, txt_h + 10), border_radius=8)
            self.draw_multiline_text(m["msg"], self.app.font_chat, (40,40,40), bx + 10, cy + 5, w-70)
            cy += txt_h + 20
        self.screen.set_clip(None)
        y += chat_h + 10

        # 3. OPENING (Dual Display & Text Wrapping)
        if self.app.mode in ["puzzle", "trainer"]:
            # Keep single display for specific modes
            op_title = "Mode Info:" if self.app.mode == "puzzle" else "Practice:"
            
            # Use dynamic text wrapping to prevent long names from spilling out
            txt_h = self.draw_multiline_text(self.app.opening_name, self.app.font_m, THEME["text"], x + 15, y + 25, w - 20, draw=False)
            op_h = max(50, 30 + txt_h)
            
            self.panel(x, y, w, op_h)
            self.screen.blit(self.app.font_s.render(op_title, True, THEME["text_dim"]), (x + 10, y + 5))
            self.draw_multiline_text(self.app.opening_name, self.app.font_m, THEME["text"], x + 15, y + 25, w - 20, draw=True)
            y += op_h + 10
        else:
            # Dual display for Live and Review modes
            w_name = getattr(self.app, 'white_opening', 'Starting Position')
            b_name = getattr(self.app, 'black_opening', 'Starting Position')
            
            # Calculate heights for both wrapped texts
            w_h = self.draw_multiline_text(w_name, self.app.font_m, THEME["text"], x + 60, y + 6, w - 70, draw=False)
            b_h = self.draw_multiline_text(b_name, self.app.font_m, THEME["text"], x + 60, y + max(40, 10 + w_h), w - 70, draw=False)
            
            op_h = max(75, 15 + w_h + b_h)
            self.panel(x, y, w, op_h)
            
            self.screen.blit(self.app.font_s.render("White:", True, THEME["text_dim"]), (x + 10, y + 8))
            self.draw_multiline_text(w_name, self.app.font_m, THEME["text"], x + 60, y + 6, w - 70, draw=True)
            
            b_y_start = y + max(40, 15 + w_h)
            self.screen.blit(self.app.font_s.render("Black:", True, THEME["text_dim"]), (x + 10, b_y_start + 2))
            self.draw_multiline_text(b_name, self.app.font_m, THEME["text"], x + 60, b_y_start, w - 70, draw=True)
            
            y += op_h + 10
        
        # 4. ENGINE INFO
        eng_h = 60 # Increased height slightly to fit the live depth perfectly
        self.panel(x, y, w, eng_h)
        # Engine Loaded Text
        eng_name = self.app.current_engine_info.get("name", "Unknown")
        self.screen.blit(self.app.font_s.render("Engine Loaded:", True, (100,100,100)), (x + 10, y + 12))
        self.screen.blit(self.app.font_m.render(eng_name, True, (20,20,20)), (x + 110, y + 10))
        
        # --- NEW: Live Depth Indicator ---
        depth_val = getattr(self.app, 'current_depth', 0)
        depth_color = (40, 180, 80) if depth_val > 0 else (150, 150, 150)
        self.screen.blit(self.app.font_s.render(f"Live Depth: {depth_val}", True, depth_color), (x + 110, y + 34))
        
        # Change Button (Widened to fit text and re-centered vertically)
        btn_w = 110 
        btn_x = x + w - btn_w - 15
        btn_r = pygame.Rect(btn_x, y + 15, btn_w, 30) 
        col = (255, 200, 150) # Light Orange
        if btn_r.collidepoint(pygame.mouse.get_pos()): col = (255, 220, 180)
        pygame.draw.rect(self.screen, col, btn_r, border_radius=6)
        pygame.draw.rect(self.screen, (200, 150, 100), btn_r, 1, border_radius=6)
        
        # Icon inside button
        ic = self.assets.icons.get("enginehint")
        if ic: self.screen.blit(pygame.transform.smoothscale(ic, (20, 20)), (btn_r.x + 8, btn_r.y + 5))
        self.screen.blit(self.app.font_s.render("Change", True, (0,0,0)), (btn_r.x + 35, btn_r.y + 5))
        self.app.btn_rects["engine_load"] = btn_r
        y += eng_h + 10

        # 5. CAPTURED PIECES
        cap_h = 80
        pygame.draw.rect(self.screen, THEME["panel"], (x, y, w, cap_h), border_radius=8)
        pygame.draw.rect(self.screen, THEME["border"], (x, y, w, cap_h), 1, border_radius=8)
        w_lost, b_lost, w_val, b_val = self.app.get_captured_pieces() 
        cx = x + 10
        self.screen.blit(self.app.font_s.render("White Captured:", True, (100,100,100)), (cx, y+5))
        cx += 100
        for p in b_lost: 
            k = 'b' + chess.Piece(p, chess.BLACK).symbol().lower()
            if k in self.assets.pieces:
                self.screen.blit(pygame.transform.smoothscale(self.assets.pieces[k], (20,20)), (cx, y+5))
                cx += 18
        if w_val > b_val:
            self.screen.blit(self.app.font_s.render(f"+{w_val - b_val}", True, (50,150,50)), (cx+5, y+5))

        cx = x + 10
        self.screen.blit(self.app.font_s.render("Black Captured:", True, (100,100,100)), (cx, y+40))
        cx += 100
        for p in w_lost: 
            k = 'w' + chess.Piece(p, chess.WHITE).symbol().lower()
            if k in self.assets.pieces:
                self.screen.blit(pygame.transform.smoothscale(self.assets.pieces[k], (20,20)), (cx, y+40))
                cx += 18
        if b_val > w_val:
            self.screen.blit(self.app.font_s.render(f"+{b_val - w_val}", True, (50,150,50)), (cx+5, y+40))
        y += cap_h + 10

        # 6. METADATA
        meta_h = 60
        if self.app.pgn_headers:
            self.panel(x, y, w, meta_h)
            white = self.app.pgn_headers.get("White", "?")
            black = self.app.pgn_headers.get("Black", "?")
            date = self.app.pgn_headers.get("Date", "?")
            
            self.screen.blit(self.app.font_s.render(f"White: {white}", True, (50,50,50)), (x+10, y+10))
            self.screen.blit(self.app.font_s.render(f"Black: {black}", True, (50,50,50)), (x+10, y+35))
            self.screen.blit(self.app.font_s.render(f"Date: {date}", True, (100,100,100)), (x+w//2, y+10))
            
            if self.app.logic and self.app.logic.pgn_metadata:
                md = self.app.logic.pgn_metadata
                eng = md.get("Engine", "")
                if eng:
                    txt = f"Analysis: {eng} (D:{md.get('Depth', '')}, {md.get('TimePerMove', '')}s)"
                    self.screen.blit(self.app.font_s.render(txt, True, (60, 100, 60)), (x+w//2, y+35))
            
            y += meta_h + 10

        # --- FIX: NATIVE SIDEBAR CLOCKS ---
        w_time, b_time = None, None
        
        # 1. Strictly verify if this specific game has ANY clock timestamps
        has_timestamps = any("clock" in s and s["clock"] is not None for s in self.app.history)
        
        if has_timestamps:
            for i in range(self.app.view_ply):
                step = self.app.history[i]
                if "clock" in step and step["clock"] is not None:
                    # --- FIX: Use the explicit 'color' key stored during import.
                    # Older history items (pre-fix) fall back to ply-parity as a last resort.
                    # The 'color' key is immune to Chess960/FEN-offset ply miscounts that
                    # caused chess.com complete-games imports to show increasing timestamps. ---
                    color = step.get("color")
                    if color == "white":
                        w_time = step["clock"]
                    elif color == "black":
                        b_time = step["clock"]
                    else:
                        # Legacy fallback for history items without 'color' key
                        actual_ply = step.get("ply", i + 1)
                        if actual_ply % 2 == 1:   # odd ply → White just moved
                            w_time = step["clock"]
                        else:                      # even ply → Black just moved
                            b_time = step["clock"]

            # --- FIX: Robust TimeControl fallback that handles every chess.com format ---
            # Formats seen: "600", "600+5", "0:10:00", "1800+0", "1/40" (ignored), "-"
            if w_time is None or b_time is None:
                base_secs = None
                tc = getattr(self.app, 'pgn_headers', {}).get("TimeControl", "")
                if tc and tc not in ("-", "?", ""):
                    tc_base = tc.split("+")[0].strip()
                    if tc_base.isdigit():
                        base_secs = float(tc_base)
                    elif ":" in tc_base:
                        # H:MM:SS or MM:SS  (chess.com complete games uses "0:10:00")
                        try:
                            parts = [int(p) for p in tc_base.split(":")]
                            if len(parts) == 3:
                                base_secs = parts[0] * 3600 + parts[1] * 60 + parts[2]
                            elif len(parts) == 2:
                                base_secs = parts[0] * 60 + parts[1]
                        except (ValueError, IndexError):
                            pass
                if base_secs is not None:
                    if w_time is None: w_time = base_secs
                    if b_time is None: b_time = base_secs

            if w_time is not None or b_time is not None:
                def fmt(secs):
                    if secs is None: return "0:00"
                    total_s = max(0.0, float(secs))
                    m = int(total_s // 60)
                    s = total_s % 60
                    if s == int(s): return f"{m}:{int(s):02d}"
                    return f"{m}:{s:04.1f}"

                w_text, b_text = fmt(w_time), fmt(b_time)
                
                clock_w = (w - 10) // 2
                
                # White Clock (Left)
                r_white = pygame.Rect(x, y, clock_w, 40)
                pygame.draw.rect(self.screen, (240, 240, 240), r_white, border_radius=6)
                pygame.draw.rect(self.screen, (150, 150, 150), r_white, 2, border_radius=6)
                ws = self.app.font_b.render(w_text, True, (20, 20, 20))
                self.screen.blit(ws, ws.get_rect(center=r_white.center))
                
                # Black Clock (Right)
                r_black = pygame.Rect(x + clock_w + 10, y, clock_w, 40)
                pygame.draw.rect(self.screen, (35, 35, 35), r_black, border_radius=6)
                pygame.draw.rect(self.screen, (100, 100, 100), r_black, 2, border_radius=6)
                bs = self.app.font_b.render(b_text, True, (240, 240, 240))
                self.screen.blit(bs, bs.get_rect(center=r_black.center))
                
                y += 50 # Pushes Move List down safely
        # -----------------------------------

        # 7. MOVE LIST
        # Expand moves box by reclaiming space previously used by many buttons
        # Expand moves box further to give more room for moves
        list_h = self.app.height - y - 90
        self.panel(x, y, w, list_h)
        cx = x + 10
        self.screen.blit(self.app.font_s.render("#", True, (150,150,150)), (cx, y+5))
        self.screen.blit(self.app.font_s.render("White", True, (150,150,150)), (cx+55, y+5))
        self.screen.blit(self.app.font_s.render("Black", True, (150,150,150)), (cx+280, y+5))
        
        clip = pygame.Rect(x, y+25, w, list_h-30)
        self.screen.set_clip(clip)
        row_y = y + 30 - self.app.scroll_hist
        
        self.app.move_click_zones = []
        show_annot = self.app.settings.get("live_annotations", True)
        
        # --- FIX: Take a locked shallow copy of history for thread-safe rendering ---
        with self.app.lock:
            safe_history = list(self.app.history)
            safe_view_ply = self.app.view_ply
            safe_is_game_over = self.app.board.is_game_over()
        
        for i in range(0, len(safe_history), 2):
            if row_y > clip.bottom: break
            if row_y + 25 > clip.y:
                self.screen.blit(self.app.font_mono.render(f"{i//2 + 1}.", True, (100,100,100)), (x+10, row_y+4))
                
                w_data = safe_history[i]
                wr = pygame.Rect(x+60, row_y, 130, 24)
                if safe_view_ply == i + 1: pygame.draw.rect(self.screen, (255,255,200), wr)
                
                # --- FIX: Fallback to raw move text if "san" is missing from manual moves ---
                if isinstance(w_data, dict):
                    w_san = w_data.get("san", str(w_data.get("move", "?")))
                else:
                    w_san = str(w_data)
                    
                self.screen.blit(self.app.font_m.render(w_san, True, (0,0,0)), (x+65, row_y+2))
                self.app.move_click_zones.append((wr, i+1))
                
                # --- FIX: Color Mapping for Text Symbols Only ---
                eval_color_map = {
                    "brilliant": (30, 190, 170), "great": (70, 120, 240),
                    "good": (120, 180, 100), "excellent": (120, 180, 100), "best": (120, 180, 100),
                    "inaccuracy": (220, 180, 50), "mistake": (220, 130, 40),
                    "blunder": (210, 60, 60), "miss": (210, 60, 60)
                }

                # --- WHITE MOVE MAPPING ---
                if show_annot and isinstance(w_data, dict) and "review" in w_data and isinstance(w_data["review"], dict):
                    ev_txt = w_data["review"].get("eval_str", "")
                    depth_val = w_data["review"].get("depth")
                    if ev_txt and depth_val is not None:
                        ev_txt = f"{ev_txt} | D{depth_val}"
                        
                    icon_k = w_data["review"].get("class")
                    nag_sym = w_data["review"].get("nag_symbol")
                    nag_cls = w_data["review"].get("nag_class")
                    
                    if icon_k == "book": 
                        icon_k = "eval_book" if "eval_book" in self.assets.icons else "book"
                    
                    # 1. Draw PNG Icon (Our App's format)
                    if icon_k and icon_k in self.assets.icons:
                        self.screen.blit(pygame.transform.smoothscale(self.assets.icons[icon_k], (16,16)), (x+120, row_y+4))
                    # 2. Draw Colored Text Symbol (External PGN format)
                    elif nag_sym:
                        sym_col = eval_color_map.get(nag_cls, (120, 120, 120))
                        self.screen.blit(self.app.font_b.render(nag_sym, True, sym_col), (x+120, row_y+2))
                        
                    # 3. Draw standard Grey Evaluation Score
                    if ev_txt:
                        self.screen.blit(self.app.font_s.render(ev_txt, True, (80,80,80)), (x+140, row_y+4))

                # --- BLACK MOVE MAPPING ---
                if (i+1) < len(safe_history): # FIX: Thread-safe reading using safe_history
                    b_data = safe_history[i+1]
                    br = pygame.Rect(x+285, row_y, 130, 24)
                    if safe_view_ply == i + 2: pygame.draw.rect(self.screen, (255,255,200), br)
                    
                    # --- FIX: Fallback to raw move text if "san" is missing from manual moves ---
                    if isinstance(b_data, dict):
                        b_san = b_data.get("san", str(b_data.get("move", "?")))
                    else:
                        b_san = str(b_data)
                        
                    self.screen.blit(self.app.font_m.render(b_san, True, (0,0,0)), (x+290, row_y+2))
                    self.app.move_click_zones.append((br, i+2))
                    
                    if show_annot and isinstance(b_data, dict) and "review" in b_data and isinstance(b_data["review"], dict):
                        ev_txt = b_data["review"].get("eval_str", "")
                        depth_val = b_data["review"].get("depth")
                        if ev_txt and depth_val is not None:
                            ev_txt = f"{ev_txt} | D{depth_val}"
                            
                        icon_k = b_data["review"].get("class")
                        nag_sym = b_data["review"].get("nag_symbol")
                        nag_cls = b_data["review"].get("nag_class")
                        
                        if icon_k == "book": 
                            icon_k = "eval_book" if "eval_book" in self.assets.icons else "book"
                            
                        # 1. Draw PNG Icon (Our App's format)
                        if icon_k and icon_k in self.assets.icons:
                            self.screen.blit(pygame.transform.smoothscale(self.assets.icons[icon_k], (16,16)), (x+355, row_y+4))
                        # 2. Draw Colored Text Symbol (External PGN format)
                        elif nag_sym:
                            sym_col = eval_color_map.get(nag_cls, (120, 120, 120))
                            self.screen.blit(self.app.font_b.render(nag_sym, True, sym_col), (x+355, row_y+2))
                            
                        # 3. Draw standard Grey Evaluation Score
                        if ev_txt:
                            self.screen.blit(self.app.font_s.render(ev_txt, True, (80,80,80)), (x+375, row_y+4))
            row_y += 25
            
        # --- NEW: Engine MultiPV "Ghost" Moves for Mate Sequences ---
        # FIX: Added 'not safe_is_game_over' to instantly erase ghost moves on checkmate!
        if getattr(self.app, 'show_hints', False) and getattr(self.app, 'mate_lines_san', None) and safe_view_ply == len(safe_history) and not safe_is_game_over:
            
            # If Black's turn is next, back up to draw on the incomplete White row
            if len(safe_history) % 2 != 0:
                row_y -= 25 
                
            max_depth = max(len(line) for line in self.app.mate_lines_san)
            
            # Bright colors to indicate different Engine variations
            line_colors = [(230, 130, 40), (180, 80, 220), (40, 160, 200)] # Orange, Purple, Teal
            
            for d in range(max_depth):
                if row_y > clip.bottom: break
                
                ply_idx = safe_view_ply + d
                row_idx = ply_idx // 2
                is_white = (ply_idx % 2 == 0)
                
                if is_white and row_y + 25 > clip.y:
                    self.screen.blit(self.app.font_mono.render(f"{row_idx + 1}.", True, (160,160,160)), (x+10, row_y+4))
                
                # Group unique moves at this depth (so identical overlapping lines don't print twice)
                moves_at_depth = []
                for line_idx, line in enumerate(self.app.mate_lines_san):
                    if d < len(line):
                        m_san = line[d]
                        if not any(m == m_san for m, c in moves_at_depth):
                            moves_at_depth.append((m_san, line_colors[line_idx % len(line_colors)]))
                
                col_x = x + 65 if is_white else x + 290
                
                if row_y + 25 > clip.y and row_y < clip.bottom:
                    cx = col_x
                    for idx, (m_san, col) in enumerate(moves_at_depth):
                        surf = self.app.font_m.render(m_san, True, col)
                        self.screen.blit(surf, (cx, row_y+2))
                        cx += surf.get_width()
                        
                        # Add a comma separator between different variation moves!
                        if idx < len(moves_at_depth) - 1:
                            comma = self.app.font_m.render(", ", True, (150,150,150))
                            self.screen.blit(comma, (cx, row_y+2))
                            cx += comma.get_width()
                            
                if not is_white:
                    row_y += 25
        # ------------------------------------------------------------
        
        self.screen.set_clip(None)

        # Single consolidated button to open a popup with all actions (frees space)
        btn_w = 140
        btn_h = 42
        btn_x = x + w - btn_w - 12
        btn_y = self.app.height - btn_h - 12
        more_r = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
        # Light green as requested (hover brightens)
        col = (200, 255, 180) if more_r.collidepoint(pygame.mouse.get_pos()) else (180, 230, 150)
        hover_border = (170, 215, 140) if more_r.collidepoint(pygame.mouse.get_pos()) else (140, 200, 110)
        pygame.draw.rect(self.screen, col, more_r, border_radius=8)
        pygame.draw.rect(self.screen, hover_border, more_r, 1, border_radius=8)
        txt = self.app.font_m.render("More Actions", True, (20,20,20))
        self.screen.blit(txt, (more_r.centerx - txt.get_width()//2, more_r.centery - txt.get_height()//2))
        # register for clicks
        self.app.btn_rects["more_buttons"] = more_r
        # Draw main UI buttons to the left of More Actions: save, load, review, account (Profile is top-left)
        btns_main = [("Save", "save"), ("Load", "load"), ("Review", "review"), ("Account", "account")]
        spacing = 8
        # Start placing from the left of More Actions
        cur_x = btn_x - spacing
        btn_h = more_r.height
        for txt, tag in reversed(btns_main):
            w = 120 
            cur_x -= w
            r = pygame.Rect(cur_x, btn_y, w, btn_h)
            # Use draw_btn to keep consistent icon handling
            self.draw_btn(r.x, r.y, txt, tag, width=w)
            cur_x -= spacing

        # (Profile already drawn above where we reserve sidebar space.)
        # No duplicated profile draw here — avoids mismatched placement.
        
import pygame

class ExplorerUI:
    def __init__(self, font_small, font_medium):
        self.font_small = font_small
        self.font_medium = font_medium
        self.is_open = False
        self.scroll_y = 0
        
        # UI Dimensions
        self.rect = pygame.Rect(50, 50, 400, 500) # Adjust to fit your screen
        self.request_btn = pygame.Rect(self.rect.x + 10, self.rect.y + 10, 380, 40)
        
        # Colors matching your image exactly
        self.COLOR_W = (76, 175, 80)   # Green
        self.COLOR_D = (144, 148, 151) # Grey
        self.COLOR_L = (244, 67, 54)   # Red

    def handle_event(self, event, explorer_db, current_board):
        if not self.is_open: return False
        
        if event.type == pygame.MOUSEBUTTONDOWN:
            mouse_pos = event.pos
            # 1. Handle Request Button Click
            if self.request_btn.collidepoint(mouse_pos) and explorer_db.current_results is None and not explorer_db.is_fetching:
                explorer_db.fetch_position_async(current_board)
                return True
                
            # 2. Handle Scrolling
            if self.rect.collidepoint(mouse_pos):
                if event.button == 4: self.scroll_y = max(0, self.scroll_y - 30) # Scroll Up
                if event.button == 5: self.scroll_y += 30 # Scroll Down
                return True
        return False

    def draw_wdl_bar(self, surface, x, y, width, height, w_pct, d_pct, l_pct):
        """Draws the beautiful horizontal WDL bar with rounded edges."""
        w_width = int(width * w_pct)
        d_width = int(width * d_pct)
        l_width = width - w_width - d_width # Remainder to avoid pixel gaps

        # We use border_radius=5 to make it look smooth and modern like your image
        if w_width > 0:
            pygame.draw.rect(surface, self.COLOR_W, (x, y, w_width, height), border_top_left_radius=5, border_bottom_left_radius=5)
        if d_width > 0:
            pygame.draw.rect(surface, self.COLOR_D, (x + w_width, y, d_width, height))
        if l_width > 0:
            pygame.draw.rect(surface, self.COLOR_L, (x + w_width + d_width, y, l_width, height), border_top_right_radius=5, border_bottom_right_radius=5)
            
        # Draw Text overlays inside the bar
        if w_width > 30:
            wt = self.font_small.render(f"{w_pct*100:.1f}%", True, (255,255,255))
            surface.blit(wt, (x + w_width//2 - wt.get_width()//2, y + 2))
        if d_width > 30:
            dt = self.font_small.render(f"{d_pct*100:.1f}%", True, (255,255,255))
            surface.blit(dt, (x + w_width + d_width//2 - dt.get_width()//2, y + 2))
        if l_width > 30:
            lt = self.font_small.render(f"{l_pct*100:.1f}%", True, (255,255,255))
            surface.blit(lt, (x + w_width + d_width + l_width//2 - lt.get_width()//2, y + 2))

    def draw(self, screen, explorer_db):
        if not self.is_open: return

        # Draw main floating panel background
        panel_surface = pygame.Surface((self.rect.w, self.rect.h), pygame.SRCALPHA)
        pygame.draw.rect(panel_surface, (30, 30, 35, 240), (0, 0, self.rect.w, self.rect.h), border_radius=10)
        pygame.draw.rect(panel_surface, (100, 100, 100, 255), (0, 0, self.rect.w, self.rect.h), width=2, border_radius=10)

        # Create a scrollable inner surface
        inner_h = 1000 # Max scroll height
        inner_surf = pygame.Surface((self.rect.w - 20, inner_h), pygame.SRCALPHA)
        y_offset = 10
        
        # --- THE REQUEST BUTTON ---
        if explorer_db.current_results is None:
            btn_color = (80, 80, 100) if not explorer_db.is_fetching else (50, 150, 50)
            pygame.draw.rect(inner_surf, btn_color, (10, y_offset, 360, 40), border_radius=8)
            btn_txt = "Loading Data..." if explorer_db.is_fetching else "🔍 Request Database Explorer"
            txt_surf = self.font_medium.render(btn_txt, True, (255,255,255))
            inner_surf.blit(txt_surf, (190 - txt_surf.get_width()//2, y_offset + 10))
            y_offset += 60
        else:
            # --- RENDER RESULTS ---
            res = explorer_db.current_results
            if "error" in res or res["total_games"] == 0:
                txt = self.font_medium.render("No games found in database for this setup.", True, (200, 50, 50))
                inner_surf.blit(txt, (20, y_offset))
            else:
                # 1. Header
                hdr = self.font_medium.render(f"{res['total_games']:,} Master Games Reached This Setup", True, (200, 200, 200))
                inner_surf.blit(hdr, (10, y_offset))
                y_offset += 30
                
                # 2. Candidate Moves & WDL Bars
                for move in res["moves"]:
                    m_txt = self.font_medium.render(f"{move['move']} ({move['total']:,})", True, (255, 255, 255))
                    inner_surf.blit(m_txt, (10, y_offset))
                    
                    # Draw your beautiful WDL bar right below the move text
                    self.draw_wdl_bar(inner_surf, 10, y_offset + 25, 360, 22, move["w_pct"], move["d_pct"], move["l_pct"])
                    y_offset += 60
                    
                pygame.draw.line(inner_surf, (100, 100, 100), (10, y_offset), (370, y_offset))
                y_offset += 15
                
                # 3. Top Grandmaster Games
                hdr_games = self.font_medium.render("Top Grandmaster Games", True, (255, 215, 0)) # Gold
                inner_surf.blit(hdr_games, (10, y_offset))
                y_offset += 25
                
                for g in res["top_games"]:
                    w_name, b_name, w_elo, b_elo, result, date = g
                    game_txt = f"{w_name} ({w_elo}) vs {b_name} ({b_elo})  [{result}]  {date}"
                    gt = self.font_small.render(game_txt, True, (180, 180, 180))
                    inner_surf.blit(gt, (10, y_offset))
                    y_offset += 25

        # Blit the scrolled portion of the inner surface onto the panel
        panel_surface.blit(inner_surf, (10, 10), area=pygame.Rect(0, self.scroll_y, self.rect.w - 20, self.rect.h - 20))
        
        # Finally, draw the whole panel to the main screen
        screen.blit(panel_surface, (self.rect.x, self.rect.y))
        