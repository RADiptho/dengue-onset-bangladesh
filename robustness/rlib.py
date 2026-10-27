"""v6 post-hoc robustness analyses on frozen predictions (no retraining, no change to frozen results).
A: moving-block bootstrap; B: operational early warning; C: masking; D: calibration; E: locked uncertainty;
F: regime descriptors; G: hhh4 start-count sensitivity."""
import os as _os
def _repo_root():
    d = _os.path.dirname(_os.path.abspath(__file__))
    while not _os.path.exists(_os.path.join(d, '.repo_root')):
        parent = _os.path.dirname(d)
        if parent == d: raise RuntimeError('repository root (.repo_root) not found')
        d = parent
    return d + '/'
ROOT = _repo_root()

import json, numpy as np, pandas as pd
from sklearn.metrics import average_precision_score as AP
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.proportion import proportion_confint
from base import *
OUT = ROOT + 'robustness/output/'
V = pd.read_csv(ROOT + 'pipeline/outputs/master_dataset_v2.csv', parse_dates=['week_start'])
P = preds(); PL = preds(locked=True)
PH = pd.read_csv(ROOT + 'posthoc/posthoc_dev_predictions.csv.gz', parse_dates=['week_start'], low_memory=False); PH = PH[PH.h == 4]
PHL = pd.read_csv(ROOT + 'posthoc/posthoc_locked_predictions_ALL.csv.gz', parse_dates=['week_start'], low_memory=False); PHL = PHL[PHL.h == 4]
E = hits(); E = E[E.h == 4]; EL = hits(locked=True); EL = EL[EL.h == 4]
YEAR = {'F2023': 2023, 'F2024': 2024, 'F2025': 2025, 'LOCKED2026': 2026}
B = 2000

def wide(p, models):
    w = p[p.model.isin(models)].pivot_table(index=['fold', 'district', 'week_start'], columns='model', values='prob').reset_index()
    y = p[p.model == models[0]].set_index(['fold', 'district', 'week_start']).y
    w['y'] = y.reindex(pd.MultiIndex.from_frame(w[['fold', 'district', 'week_start']])).values
    return w[w.y.notna()].reset_index(drop=True)

def block_index(weeks_by_fold, L, rng):
    """Circular moving-block bootstrap of consecutive issue weeks, stratified by fold; L=1 gives the original week bootstrap."""
    pick = []
    for f, wk in weeks_by_fold.items():
        n = len(wk); nb = int(np.ceil(n / L)); starts = rng.integers(0, n, nb)
        sel = np.concatenate([(s + np.arange(L)) % n for s in starts])[:n]
        pick.append([(f, wk[i]) for i in sel])
    return [x for sub in pick for x in sub]

def pval(boots):
    return min(1.0, 2 * min((boots <= 0).mean(), (boots >= 0).mean()))

def boot_prob(w, a, b, metric, L, seed):
    rng = np.random.default_rng(seed)
    w = w.copy(); key = list(zip(w.fold, w.week_start))
    groups = {}
    for i, k in enumerate(key): groups.setdefault(k, []).append(i)
    wbf = {f: sorted(w.loc[w.fold == f, 'week_start'].unique()) for f in w.fold.unique()}
    def f(ix):
        yy = w.y.values[ix]
        if metric == 'auprc': return AP(yy, w[a].values[ix]) - AP(yy, w[b].values[ix])
        return np.mean((w[a].values[ix] - yy) ** 2) - np.mean((w[b].values[ix] - yy) ** 2)
    obs = f(np.arange(len(w)))
    bs = np.array([f(np.concatenate([groups[k] for k in block_index(wbf, L, rng) if k in groups])) for _ in range(B)])
    return obs, *np.percentile(bs, [2.5, 97.5]), pval(bs)

def boot_cap(e, a, b, k, weeks_by_fold, L, seed):
    rng = np.random.default_rng(seed)
    x = e[(e.k == k) & e.model.isin([a, b])].pivot_table(index=['fold', 'district', 'onset_week'], columns='model', values='hit').reset_index()
    x['iw'] = x.onset_week - pd.Timedelta(weeks=1); d = (x[a].astype(float) - x[b].astype(float)).values
    groups = {}
    for i, kk in enumerate(zip(x.fold, x.iw)): groups.setdefault(kk, []).append(i)
    bs = []
    for _ in range(B):
        ix = [i for kk in block_index(weeks_by_fold, L, rng) for i in groups.get(kk, [])]
        bs.append(d[ix].mean() if ix else 0.0)
    bs = np.array(bs)
    return d.mean(), *np.percentile(bs, [2.5, 97.5]), pval(bs), len(d)

def cal_stats(p, y):
    from sklearn.linear_model import LogisticRegression
    pc = np.clip(p, 1e-6, 1 - 1e-6); lg = np.log(pc / (1 - pc)).reshape(-1, 1)
    m = LogisticRegression(C=1e6, max_iter=1000).fit(lg, y)
    return dict(brier=np.mean((p - y) ** 2), slope=m.coef_[0][0], intercept=m.intercept_[0], oe=y.sum() / p.sum())

