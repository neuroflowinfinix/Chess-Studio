import os
import io
import joblib
import random
import chess
import chess.pgn
import chess.engine
from analysis_engine import AnalysisEngine


def load_game_from_pgn(pgn_text):
    return chess.pgn.read_game(io.StringIO(pgn_text))


def generate_history(engine_path, game, multipv=3, time_before=0.06, time_after=0.02, max_plies=200, ignore_book=True):
    """God-Tier WDL History Generator. Extracts native NNUE Win% and Sharpness Gaps."""
    eng = chess.engine.SimpleEngine.popen_uci(engine_path)
    
    # --- Force NNUE & Syzygy for Calibration ---
    try:
        config = {}
        if "Use NNUE" in eng.options: config["Use NNUE"] = True
        syz = os.path.abspath(os.path.join("assets", "syzygy"))
        if "SyzygyPath" in eng.options and os.path.exists(syz):
            config["SyzygyPath"] = syz
            if "SyzygyProbeDepth" in eng.options: config["SyzygyProbeDepth"] = 1
        eng.configure(config)
    except: pass
    
    board = chess.Board()
    history = []
    count = 0
    
    for move in game.mainline_moves():
        try: info_before = eng.analyse(board, chess.engine.Limit(time=time_before), multipv=multipv)
        except Exception: info_before = None

        prev_cp = None
        best_gap = 0
        
        if info_before:
            try:
                sc0 = info_before[0]['score'].white()
                prev_cp = 10000 - (sc0.mate()*100) + 50 if sc0.is_mate() else int(sc0.score())
                
                if len(info_before) > 1 and 'score' in info_before[1]:
                    sc1 = info_before[1]['score'].white()
                    sc1_cp = 10000 - (sc1.mate()*100) + 50 if sc1.is_mate() else int(sc1.score())
                    best_gap = abs(prev_cp - sc1_cp)
            except Exception: prev_cp = None

        turn_str = 'white' if board.turn == chess.WHITE else 'black'
        board.push(move)

        try: info_after = eng.analyse(board, chess.engine.Limit(time=time_after), multipv=1)
        except Exception: info_after = None

        curr_cp = None
        win_chance = 50.0
        
        if info_after:
            try:
                sc = info_after[0]['score'] if isinstance(info_after, list) else info_after['score']
                sc_white = sc.white()
                curr_cp = 10000 - (sc_white.mate()*100) + 50 if sc_white.is_mate() else int(sc_white.score())
                
                # --- GOD-TIER UPGRADE: Extract True NNUE WDL ---
                try: win_chance = sc_white.wdl().expectation() * 100.0
                except: pass # Fallback to 50.0
            except Exception: curr_cp = None

        history.append({
            'move': move, 
            'review': {
                'prev_cp': prev_cp, 
                'curr_cp': curr_cp, 
                'best_gap': best_gap, 
                'turn': turn_str, 
                'eval_cp': curr_cp,
                'win_chance': win_chance # Store True WDL for ML Feature Extraction!
            }
        })

        count += 1
        if count >= max_plies: break

    try: eng.quit()
    except: pass
    return history


def train_and_persist_model(ae: AnalysisEngine, history, reference_labels, out_path='assets/review_model.joblib'):
    clf, le = ae.train_feature_model(history, reference_labels)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    joblib.dump({'clf': clf, 'le': le}, out_path)
    return out_path


def randomized_cp_gap_search(ae: AnalysisEngine, history, ref_tokens, iterations=3000, target=70):
    """God-Tier Simulated Annealing approach using WDL scaling bounds."""
    base_cp = ae.CP_THRESHOLDS.copy()
    base_cal = ae.CALIB_PARAMS.copy()
    best = {'exact': -1, 'params': None}
    
    for it in range(iterations):
        # Monotonic CP bounds
        be = random.randint(0, 15)
        ex = random.randint(be + 1, min(60, be + 30))
        go = random.randint(ex + 1, min(150, ex + 40))
        ina = random.randint(go + 1, min(300, go + 150))
        mi = random.randint(ina + 1, min(600, ina + 300))
        bl = random.randint(mi + 1, min(1000, mi + 400))
        
        new_cp = {'best': be, 'excellent': ex, 'good': go, 'inaccuracy': ina, 'mistake': mi, 'blunder': bl}
        
        # --- GOD-TIER UPGRADE: WDL Float-based bounds ---
        gap_great = random.uniform(100.0, 300.0)
        gap_brill = random.uniform(gap_great + 20.0, 500.0)
        miss_eq = random.uniform(30.0, 60.0)
        miss_win = random.uniform(miss_eq + 5.0, 95.0)
        
        new_cal = base_cal.copy()
        new_cal.update({'gap_great': gap_great, 'gap_brill': gap_brill, 'miss_win': miss_win, 'miss_eq': miss_eq})
        
        ae.CP_THRESHOLDS = new_cp
        ae.CALIB_PARAMS = new_cal
        
        # Ensure turn formatting is chess.WHITE / chess.BLACK to match engine expects
        preds = []
        for h in history[:len(ref_tokens)]:
            t_str = h['review'].get('turn', 'white')
            turn_c = chess.WHITE if t_str == 'white' else chess.BLACK
            pred = ae.simple_classify_by_cp_gap(h['review'].get('prev_cp'), h['review'].get('curr_cp'), turn_c, h['review'].get('best_gap', 0))
            preds.append(pred)
            
        exact = sum(1 for i in range(min(len(preds), len(ref_tokens))) if preds[i]==ref_tokens[i])
        
        if exact > best['exact']:
            best = {'exact': exact, 'params': {'CP_THRESHOLDS': new_cp, 'CALIB_PARAMS': new_cal}}
        if exact >= target:
            break
            
    ae.CP_THRESHOLDS = base_cp
    ae.CALIB_PARAMS = base_cal
    return best