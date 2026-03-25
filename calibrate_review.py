"""
Calibration helper for tuning classification thresholds against a reference (e.g., like pro chess softwares)

Usage:
  python calibrate_review.py --history history.json --labels labels.txt [--apply]

- history.json: JSON array of move dicts (each must include review.eval_cp numeric)
- labels.txt: one label per ply (white then black), labels like: book, best, excellent, good, great, brilliant, mistake, inaccuracy, miss, blunder
- --apply: if provided, the script will print a suggested patch to update `CP_THRESHOLDS` in `analysis_engine.py` (autopatch not performed).

This script uses the AnalysisEngine.calibrate_thresholds_from_reference helper.
"""
import argparse
import json
import sys
from analysis_engine import AnalysisEngine

VALID_LABELS = set(['book','best','excellent','good','great','brilliant','mistake','inaccuracy','miss','blunder'])


def load_history(path):
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    # Expect list of moves; ensure each has review.eval_cp
    for i, m in enumerate(data):
        r = m.get('review', {})
        if 'eval_cp' not in r:
            raise ValueError(f"history entry {i} missing review.eval_cp")
    return data


def load_labels(path):
    with open(path, 'r', encoding='utf-8') as f:
        lines = [l.strip().lower() for l in f if l.strip()]
    # accept comma/space separated on single line
    if len(lines) == 1 and any(c in lines[0] for c in ', '):
        tokens = [t.strip() for t in lines[0].replace(',', ' ').split()]
    else:
        tokens = lines
    tokens = [t for t in tokens if t in VALID_LABELS or t == 'book']
    return tokens


def filter_book_plies(history, labels):
    if len(history) != len(labels):
        # try to align by keeping min length
        n = min(len(history), len(labels))
        history = history[:n]
        labels = labels[:n]
    filtered_hist = []
    filtered_labels = []
    for h, l in zip(history, labels):
        if l == 'book':
            continue
        filtered_hist.append(h)
        filtered_labels.append(l)
    return filtered_hist, filtered_labels


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--history', '-H', required=True, help='Path to history JSON')
    p.add_argument('--labels', '-L', required=True, help='Path to labels text file')
    p.add_argument('--apply', action='store_true', help='Print suggested code patch (manual apply)')
    args = p.parse_args()

    history = load_history(args.history)
    labels = load_labels(args.labels)
    fh, fl = filter_book_plies(history, labels)

    if not fh or not fl:
        print('No non-book plies to calibrate. Exiting.')
        sys.exit(1)

    ae = AnalysisEngine(engine_path='')
    print('Running calibration on', len(fh), 'plies...')
    
    # --- GOD-TIER UPGRADE: Use the WDL gap-aware Simulated Annealing ---
    res = ae.calibrate_thresholds_with_gap(fh, fl, time_limit=30, trials=5000)

    print('\nBest match count:', res.get('best_score'))
    
    best_params = res.get('best_params')
    if best_params:
        print('\n--- Best CP_THRESHOLDS ---')
        for k, v in best_params.get('CP_THRESHOLDS', {}).items():
            print(f'  {k}: {v}')
            
        print('\n--- Best CALIB_PARAMS (WDL Scaling) ---')
        for k, v in best_params.get('CALIB_PARAMS', {}).items():
            if k in ['gap_great', 'gap_brill', 'miss_win', 'miss_eq']:
                print(f'  {k}: {v:.2f}')

    if args.apply and best_params:
        new_cp = best_params['CP_THRESHOLDS']
        new_cal = best_params['CALIB_PARAMS']
        
        print('\n=========================================')
        print('Suggested snippet for analysis_engine.py:')
        print('=========================================')
        print('self.CP_THRESHOLDS.update({')
        for k in ['blunder','mistake','inaccuracy','good','excellent','best']:
            if k in new_cp:
                print(f"    '{k}': {new_cp[k]},")
        print('})')
        print('\nself.CALIB_PARAMS.update({')
        for k in ['gap_great','gap_brill','miss_win','miss_eq']:
            if k in new_cal:
                print(f"    '{k}': {new_cal[k]:.2f},")
        print('})')

    print('\nDone.')

if __name__ == "__main__":
    main()
