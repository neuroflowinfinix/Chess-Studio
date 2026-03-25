import requests
import json
import chess
import chess.pgn
import io
import time
from typing import List, Dict, Optional, Tuple
import re
from datetime import datetime

class ChessAccountManager:
    """Manages chess.com and Lichess account integration"""
    
    def __init__(self):
        self.chess_com_base = "https://api.chess.com/pub"
        self.lichess_base = "https://lichess.org/api"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'ChessAnalysisApp/1.0 (Contact: your-email@example.com)'
        })
        
    def validate_chess_com_username(self, username: str) -> dict:
        """Validate chess.com username and return game count"""
        try:
            res = self.session.get(f"{self.chess_com_base}/player/{username}", timeout=10)
            if res.status_code == 200:
                stats_res = self.session.get(f"{self.chess_com_base}/player/{username}/stats", timeout=10)
                total = 0
                if stats_res.status_code == 200:
                    data = stats_res.json()
                    for key in ['chess_rapid', 'chess_blitz', 'chess_bullet', 'chess_daily']:
                        if key in data and 'record' in data[key]:
                            rec = data[key]['record']
                            total += rec.get('win', 0) + rec.get('loss', 0) + rec.get('draw', 0)
                return {"valid": True, "count": total}
            return {"valid": False}
        except:
            return {"valid": False}
    
    def validate_lichess_username(self, username: str) -> dict:
        """Validate Lichess username and return game count"""
        try:
            res = self.session.get(f"{self.lichess_base}/user/{username}", timeout=10)
            if res.status_code == 200:
                data = res.json()
                return {"valid": True, "count": data.get("count", {}).get("all", 0)}
            return {"valid": False}
        except:
            return {"valid": False}

    def download_from_url(self, url: str) -> dict:
        """Download games from a generic URL (like chess.com master games)"""
        try:
            # Mask as a standard browser so websites don't block the request
            self.session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            res = self.session.get(url, timeout=15)
            res.raise_for_status()
            
            # Unescape JSON unicode and newlines often found in web-embedded PGNs
            text = res.text.replace("\\n", "\n").replace('\\"', '"')
            
            # Regex to find all PGN blocks (Starts with [Event and ends with game result)
            pgns = re.findall(r'(\[Event\s+".*?(?:1-0|0-1|1/2-1/2|\*))', text, re.DOTALL)
            
            valid_pgns = []
            for p in pgns:
                if "[Site" in p and "1." in p:
                    valid_pgns.append(p.strip())
            
            if valid_pgns:
                return {'games': valid_pgns}
            return {'error': 'No PGNs found on the given page'}
        except Exception as e:
            return {'error': str(e)}
    
    def get_chess_com_games(self, username: str, max_games: int = 50) -> List[Dict]:
        """Download games from chess.com"""
        try:
            # Get player archives
            archives_url = f"{self.chess_com_base}/player/{username}/games/archives"
            archives_response = self.session.get(archives_url, timeout=15)
            
            if archives_response.status_code != 200:
                return {"error": "User not found or no games available"}
            
            archives = archives_response.json().get('archives', [])
            games = []
            
            # Get games from recent archives
            for archive_url in reversed(archives[-12:]):  # Last 12 months
                if len(games) >= max_games:
                    break
                    
                try:
                    games_response = self.session.get(archive_url, timeout=15)
                    if games_response.status_code == 200:
                        archive_games = games_response.json().get('games', [])
                        
                        for game_data in archive_games:
                            if len(games) >= max_games:
                                break
                                
                            # Convert to our format
                            game = self._parse_chess_com_game(game_data, username)
                            if game:
                                games.append(game)
                                
                except Exception as e:
                    print(f"Error loading archive {archive_url}: {e}")
                    continue
            
            return {"games": games, "total": len(games)}
            
        except Exception as e:
            return {"error": f"Failed to download games: {str(e)}"}
    
    def get_lichess_games(self, username: str, max_games: int = 50) -> List[Dict]:
        """Download games from Lichess"""
        try:
            games_url = f"{self.lichess_base}/games/user/{username}"
            params = {
                'max': max_games,
                'perfType': 'blitz,rapid,classical'  # Focus on standard time controls
            }
            
            response = self.session.get(games_url, params=params, timeout=20)
            
            if response.status_code != 200:
                return {"error": "User not found or no games available"}
            
            games_text = response.text
            games = []
            
            # Each game is on a separate line
            for line in games_text.split('\n'):
                if len(games) >= max_games:
                    break
                    
                if line.strip():
                    try:
                        game_data = json.loads(line)
                        game = self._parse_lichess_game(game_data, username)
                        if game:
                            games.append(game)
                    except json.JSONDecodeError:
                        continue
            
            return {"games": games, "total": len(games)}
            
        except Exception as e:
            return {"error": f"Failed to download games: {str(e)}"}
    
    def _parse_chess_com_game(self, game_data: Dict, username: str) -> Optional[Dict]:
        """Parse chess.com game data"""
        try:
            if game_data.get('pgn') is None:
                return None
                
            pgn = game_data['pgn']
            
            # Parse PGN
            pgn_game = chess.pgn.read_game(io.StringIO(pgn))
            if not pgn_game:
                return None
            
            # Extract metadata
            white = pgn_game.headers.get('White', '')
            black = pgn_game.headers.get('Black', '')
            result = pgn_game.headers.get('Result', '*')
            date = pgn_game.headers.get('UTCDate', '')
            time_control = pgn_game.headers.get('TimeControl', '')
            
            # Determine if user played as white or black
            user_color = None
            if username.lower() in white.lower():
                user_color = 'white'
            elif username.lower() in black.lower():
                user_color = 'black'
            
            return {
                'pgn': pgn,
                'white': white,
                'black': black,
                'result': result,
                'date': date,
                'time_control': time_control,
                'user_color': user_color,
                'source': 'chess.com',
                'url': game_data.get('url', ''),
                'accuracy': game_data.get('accuracy', {}),
                'end_time': game_data.get('end_time', 0)
            }
            
        except Exception as e:
            print(f"Error parsing chess.com game: {e}")
            return None
    
    def _parse_lichess_game(self, game_data: Dict, username: str) -> Optional[Dict]:
        """Parse Lichess game data"""
        try:
            players = game_data.get('players', {})
            white_player = players.get('white', {})
            black_player = players.get('black', {})
            
            white = white_player.get('user', {}).get('name', 'White')
            black = black_player.get('user', {}).get('name', 'Black')
            result = game_data.get('status', '')
            
            # Convert Lichess status to standard result
            if result == 'draw':
                result = '1/2-1/2'
            elif white_player.get('winner'):
                result = '1-0'
            elif black_player.get('winner'):
                result = '0-1'
            else:
                result = '*'
            
            # Create PGN
            pgn_headers = {
                'Event': 'Lichess Game',
                'Site': 'https://lichess.org',
                'White': white,
                'Black': black,
                'Result': result,
                'UTCDate': game_data.get('createdAt', '').split('T')[0].replace('-', '.'),
                'UTCTime': game_data.get('createdAt', '').split('T')[1].split('.')[0] if 'T' in game_data.get('createdAt', '') else '',
                'TimeControl': f"{game_data.get('clock', {}).get('initial', 0)}+{game_data.get('clock', {}).get('increment', 0)}",
                'WhiteElo': str(white_player.get('rating', 1500)),
                'BlackElo': str(black_player.get('rating', 1500)),
                'WhiteRatingDiff': str(white_player.get('ratingDiff', 0)),
                'BlackRatingDiff': str(black_player.get('ratingDiff', 0))
            }
            
            # Create game object
            game = chess.pgn.Game()
            for key, value in pgn_headers.items():
                game.headers[key] = value
            
            # Add moves
            moves = game_data.get('moves', '').split(' ')
            board = chess.Board()
            
            node = game
            for move_str in moves:
                if move_str:
                    try:
                        move = board.push_san(move_str)
                        node = node.add_variation(move)
                    except ValueError:
                        continue
            
            # Determine user color
            user_color = None
            if username.lower() in white.lower():
                user_color = 'white'
            elif username.lower() in black.lower():
                user_color = 'black'
            
            return {
                'pgn': game,
                'white': white,
                'black': black,
                'result': result,
                'date': pgn_headers['UTCDate'],
                'time_control': pgn_headers['TimeControl'],
                'user_color': user_color,
                'source': 'lichess',
                'url': f"https://lichess.org/{game_data.get('id', '')}",
                'accuracy': game_data.get('analysis', {}),
                'opening': game_data.get('opening', {})
            }
            
        except Exception as e:
            print(f"Error parsing Lichess game: {e}")
            return None

class GameChatAnalyzer:
    """Analyzes games and generates chat-style commentary"""
    
    def __init__(self, analysis_engine):
        self.engine = analysis_engine
        self.templates = {
            'blunder': [
                "Ouch! You hung your {piece} there. That's a costly mistake.",
                "Big blunder! Your {piece} was completely exposed.",
                "That's a serious error. Your {piece} is now under attack.",
                "Oh no! You just dropped your {piece} for free."
            ],
            'mistake': [
                "That's a mistake. Your {piece} position is weakened.",
                "Not the best move. Your {piece} is now vulnerable.",
                "Slight error there. Your {piece} could have been safer.",
                "That move loses some advantage. Watch your {piece}."
            ],
            'inaccuracy': [
                "Slightly inaccurate. Your {piece} could be better placed.",
                "Not terrible, but your {piece} positioning isn't ideal.",
                "Small inaccuracy. Consider your {piece} development.",
                "Acceptable, but your {piece} could be more active."
            ],
            'good': [
                "Nice move! Your {piece} is well-placed now.",
                "Good developing move. Your {piece} is active.",
                "Solid play. Your {piece} controls important squares.",
                "Well done! Your {piece} placement is strong."
            ],
            'brilliant': [
                "Brilliant! Your {piece} move is exceptional!",
                "Wow! That {piece} sacrifice is incredible!",
                "Outstanding! Your {piece} creates amazing threats!",
                "Genius! Your {piece} play is world-class!"
            ],
            'great': [
                "Great move! Your {piece} creates powerful threats.",
                "Excellent! Your {piece} dominates the position.",
                "Fantastic! Your {piece} initiative is huge.",
                "Superb! Your {piece} coordination is beautiful."
            ],
            'miss': [
                "You missed a great opportunity with your {piece}.",
                "There was a better {piece} move available.",
                "Your {piece} could have done more damage there.",
                "Missed chance! Your {piece} had a stronger move."
            ],
            'book': [
                "Solid book move. Your {piece} development is standard.",
                "Good opening theory. Your {piece} follows main line.",
                "Classical approach. Your {piece} placement is theoretical.",
                "Standard development. Your {piece} follows principles."
            ]
        }
    
    def analyze_move_for_chat(self, board_before, move, eval_before, eval_after):
        """Generate chat commentary for a move"""
        move_str = board_before.san(move)
        piece = board_before.piece_at(move.from_square)
        piece_name = self._get_piece_name(piece) if piece else "pawn"
        
        # Calculate evaluation change
        eval_change = eval_after - eval_before
        is_white = not board_before.turn
        
        if not is_white:
            eval_change = -eval_change
        
        # Classify the move
        category = self._classify_move(eval_change)
        
        # Get template and fill it
        templates = self.templates.get(category, ["Interesting move with your {piece}."])
        import random
        template = random.choice(templates)
        
        commentary = template.format(piece=piece_name)
        
        # Add context
        if board_before.is_capture(move):
            captured_piece = board_before.piece_at(move.to_square)
            captured_name = self._get_piece_name(captured_piece) if captured_piece else "pawn"
            commentary += f" Capturing the {captured_name} is {category}."
        
        if board_before.gives_check(move):
            commentary += " Nice check!"
        
        return {
            'move': move_str,
            'category': category,
            'commentary': commentary,
            'piece': piece_name,
            'eval_change': eval_change,
            'eval_after': eval_after
        }
    
    def _get_piece_name(self, piece):
        """Get piece name in friendly format"""
        if not piece:
            return "pawn"
        
        names = {
            chess.PAWN: "pawn",
            chess.KNIGHT: "knight",
            chess.BISHOP: "bishop",
            chess.ROOK: "rook",
            chess.QUEEN: "queen",
            chess.KING: "king"
        }
        return names.get(piece.piece_type, "piece")
    
    def _classify_move(self, eval_change):
        """Classify move based on evaluation change"""
        if eval_change >= 200:
            return "brilliant"
        elif eval_change >= 100:
            return "great"
        elif eval_change >= 50:
            return "good"
        elif eval_change >= 20:
            return "book"
        elif eval_change >= -20:
            return "inaccuracy"
        elif eval_change >= -100:
            return "mistake"
        else:
            return "blunder"
    
    def generate_game_summary(self, game_history):
        """Generate overall game summary"""
        if not game_history:
            return "No moves to analyze."
        
        white_moves = 0
        black_moves = 0
        white_errors = 0
        black_errors = 0
        best_moves = 0
        
        for move_data in game_history:
            if 'review' in move_data and 'class' in move_data['review']:
                ply = move_data.get('ply', 0)
                category = move_data['review']['class']
                
                if ply % 2 == 1:  # White's move
                    white_moves += 1
                    if category in ['blunder', 'mistake', 'inaccuracy']:
                        white_errors += 1
                    elif category in ['brilliant', 'great', 'best']:
                        best_moves += 1
                else:  # Black's move
                    black_moves += 1
                    if category in ['blunder', 'mistake', 'inaccuracy']:
                        black_errors += 1
                    elif category in ['brilliant', 'great', 'best']:
                        best_moves += 1
        
        summary = []
        
        if white_errors > 3:
            summary.append("White made several critical errors.")
        elif white_errors > 0:
            summary.append("White played solidly with minor inaccuracies.")
        else:
            summary.append("White played an excellent game.")
        
        if black_errors > 3:
            summary.append("Black made several critical errors.")
        elif black_errors > 0:
            summary.append("Black played solidly with minor inaccuracies.")
        else:
            summary.append("Black played an excellent game.")
        
        if best_moves > 5:
            summary.append("Some brilliant moves were played!")
        
        return " ".join(summary)

class NetworkStatusMonitor:
    """Monitors network connectivity and provides fallback messages"""
    
    def __init__(self):
        self.is_connected = True
        self.last_check = 0
        self.check_interval = 30  # Check every 30 seconds
        
    def check_connection(self):
        """Check if internet is available"""
        current_time = time.time()
        if current_time - self.last_check < self.check_interval:
            return self.is_connected
        
        try:
            # Simple connectivity check
            response = requests.get("https://www.google.com", timeout=5)
            self.is_connected = response.status_code == 200
        except:
            self.is_connected = False
        
        self.last_check = current_time
        return self.is_connected
    
    def get_fallback_message(self, feature):
        """Get appropriate fallback message for offline mode"""
        messages = {
            'cloud_analysis': "📵 Network unavailable. Using local engine analysis only.",
            'account_download': "📵 Cannot download games. Check your internet connection.",
            'opening_explorer': "📵 Opening database unavailable. Using local book only.",
            'live_evaluation': "📵 Cloud evaluation unavailable. Local engine active.",
            'general': "📵 Offline mode: Some features may be limited."
        }
        return messages.get(feature, "📵 Network features unavailable.")
    
    def get_status_icon(self):
        """Get status icon for UI display"""
        if self.is_connected:
            return "🟢"
        else:
            return "🔴"
