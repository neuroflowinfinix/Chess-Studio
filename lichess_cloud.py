import requests
import json
import time
from typing import Optional, Dict, List, Tuple
import chess

class LichessCloudAPI:
    """Interface to Lichess cloud analysis database"""
    
    def __init__(self):
        self.base_url = "https://lichess.org/api"
        self.cloud_url = "https://lichess.org/cloud-eval"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'ChessAnalysisApp/1.0'
        })
    
    def get_cloud_evaluation(self, fen: str, variant: str = "standard", 
                           multiPv: int = 2, depth: int = 65) -> Optional[Dict]:
        """
        Get evaluation from Lichess cloud database
        depth=65 is maximum supported by Lichess
        """
        try:
            params = {
                'fen': fen,
                'variant': variant,
                'multiPv': multiPv,
                'depth': min(depth, 65)  # Lichess max depth is 65
            }
            
            response = self.session.get(self.cloud_url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            return {
                'evaluation': data.get('eval'),
                'depth': data.get('depth'),
                'nodes': data.get('nodes'),
                'best_move': data.get('pvs', [{}])[0].get('moves', '').split()[0] if data.get('pvs') else None,
                'pv': data.get('pvs', [{}])[0].get('moves', '') if data.get('pvs') else '',
                'time': data.get('time', 0)
            }
        except Exception as e:
            print(f"Lichess cloud API error: {e}")
            return None
    
    def get_opening_explorer(self, fen: str, variant: str = "standard", 
                           speeds: List[str] = None, ratings: List[str] = None) -> Optional[Dict]:
        """Get opening statistics from Lichess database"""
        try:
            params = {
                'fen': fen,
                'variant': variant,
                'speeds': ','.join(speeds or ['blitz', 'rapid', 'classical']),
                'ratings': ','.join(ratings or ['1600', '1800', '2000', '2200', '2500'])
            }
            
            response = self.session.get(f"{self.base_url}/opening-explorer", params=params, timeout=15)
            response.raise_for_status()
            
            return response.json()
        except Exception as e:
            print(f"Lichess opening explorer error: {e}")
            return None
    
    def get_master_games(self, fen: str) -> Optional[Dict]:
        """Get master game statistics for position"""
        try:
            params = {'fen': fen}
            response = self.session.get(f"{self.base_url}/master", params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Lichess master games error: {e}")
            return None

class EnhancedAnalysisEngine:
    """Enhanced analysis engine combining local engine with Lichess cloud"""
    
    def __init__(self, local_engine_path, use_cloud=True):
        from analysis_engine import AnalysisEngine
        self.local_engine = AnalysisEngine(local_engine_path)
        self.lichess_api = LichessCloudAPI() if use_cloud else None
        self.use_cloud = use_cloud
        
    def get_comprehensive_analysis(self, board, depth=20, use_cloud_depth=65):
        """Combine local and cloud analysis"""
        results = {}
        
        # Local engine analysis
        try:
            local_result = self.local_engine.analyze_position(board, depth=depth)
            results['local'] = local_result
        except Exception as e:
            print(f"Local engine error: {e}")
        
        # Cloud analysis
        if self.use_cloud and self.lichess_api:
            try:
                cloud_result = self.lichess_api.get_cloud_evaluation(
                    board.fen(), depth=use_cloud_depth, multiPv=3
                )
                results['cloud'] = cloud_result
            except Exception as e:
                print(f"Cloud analysis error: {e}")
        
        # Opening explorer data
        if self.use_cloud and self.lichess_api:
            try:
                opening_data = self.lichess_api.get_opening_explorer(board.fen())
                results['opening'] = opening_data
            except Exception as e:
                print(f"Opening explorer error: {e}")
        
        return results
    
    def evaluate_sacrifice_with_cloud(self, board, move, depth=20):
        """Evaluate sacrifice using both local and cloud analysis"""
        # Make the move on a copy of the board
        board_copy = board.copy()
        board_copy.push(move)
        
        # Get comprehensive analysis
        analysis = self.get_comprehensive_analysis(board_copy, depth=depth)
        
        # Evaluate sacrifice quality
        sacrifice_eval = {
            'move': move.uci(),
            'is_sacrifice': self.is_material_sacrifice(board, move),
            'local_eval': analysis.get('local'),
            'cloud_eval': analysis.get('cloud'),
            'opening_stats': analysis.get('opening'),
            'recommendation': self.get_sacrifice_recommendation(analysis)
        }
        
        return sacrifice_eval
    
    def is_material_sacrifice(self, board, move):
        """Check if move involves material sacrifice"""
        if board.is_capture(move):
            captured_piece = board.piece_at(move.to_square)
            moving_piece = board.piece_at(move.from_square)
            
            if captured_piece and moving_piece:
                # Simple material comparison
                material_values = {
                    chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
                    chess.ROOK: 5, chess.QUEEN: 9
                }
                
                return (material_values.get(moving_piece.piece_type, 0) > 
                       material_values.get(captured_piece.piece_type, 0))
        
        return False
    
    def get_sacrifice_recommendation(self, analysis):
        """Generate sacrifice recommendation based on analysis"""
        cloud_eval = analysis.get('cloud')
        local_eval = analysis.get('local')
        
        if not cloud_eval and not local_eval:
            return "insufficient_data"
        
        # Prefer cloud evaluation if available (depth 65)
        eval_score = None
        if cloud_eval:
            eval_score = cloud_eval.get('evaluation')
        elif local_eval:
            eval_score = local_eval.get('score')
        
        if eval_score is None:
            return "insufficient_data"
        
        # Convert evaluation to numeric score
        if isinstance(eval_score, str):
            if 'M' in eval_score:  # Mate in X
                return "brilliant_sacrifice"
            eval_score = float(eval_score)
        
        # Sacrifice evaluation logic
        if eval_score > 200:
            return "brilliant_sacrifice"
        elif eval_score > 100:
            return "good_sacrifice"
        elif eval_score > -50:
            return "speculative_sacrifice"
        else:
            return "poor_sacrifice"
