"""Shared loaders for the v6 robustness analyses. Uses only frozen predictions and frozen definitions."""
import os as _os
def _repo_root():
    d = _os.path.dirname(_os.path.abspath(__file__))
    while not _os.path.exists(_os.path.join(d, '.repo_root')):
        parent = _os.path.dirname(d)
        if parent == d: raise RuntimeError('repository root (.repo_root) not found')
        d = parent
    return d + '/'
ROOT = _repo_root()

import sys, numpy as np, pandas as pd
sys.path.insert(0, ROOT + 'experiments')
R = ROOT + 'results/'
MODELS = ['persistence', 'main_isotonic', 'main_raw', 'hhh4']
def preds(h=4, locked=False):
    p = pd.read_csv(R + ('locked_predictions.csv.gz' if locked else 'dev_predictions_primary.csv.gz'), parse_dates=['week_start'])
    return p[p.h == h]
def hits(locked=False):
    return pd.read_csv(R + ('locked_event_hits.csv.gz' if locked else 'dev_event_hits_primary.csv.gz'), parse_dates=['onset_week'])
def ranked(p, model):
    """Weekly ranks among at-risk test rows exactly as engine.rank_table (seed 11 tie-break, rows in file order)."""
    q = p[p.model == model].copy()
    out = []
    for f, g in q.groupby('fold', sort=False):
        rng = np.random.default_rng(11)
        g = g.copy(); g['s'] = g.score.values + rng.uniform(0, 1e-9, len(g))
        g['rank'] = g.groupby('week_start').s.rank(ascending=False, method='first')
        g['n_at_risk'] = g.groupby('week_start').s.transform('size'); out.append(g)
    return pd.concat(out)
