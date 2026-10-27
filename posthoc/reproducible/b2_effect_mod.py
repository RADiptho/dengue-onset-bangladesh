import os as _os
def _repo_root():
    d = _os.path.dirname(_os.path.abspath(__file__))
    while not _os.path.exists(_os.path.join(d, '.repo_root')):
        parent = _os.path.dirname(d)
        if parent == d: raise RuntimeError('repository root (.repo_root) not found')
        d = parent
    return d + '/'
ROOT = _repo_root()

import numpy as np, pandas as pd
from sklearn.metrics import average_precision_score
B = ROOT
v = pd.read_csv(B + 'pipeline/outputs/master_dataset_v2.csv', parse_dates=['week_start'])
P = pd.read_csv(B + 'posthoc/posthoc_dev_predictions.csv.gz', parse_dates=['week_start'], low_memory=False)
W = P[P.model.isin(['hhh4', 'persistence']) & P.y.notna()].pivot_table(index=['fold', 'district', 'week_start', 'y'], columns='model', values='prob').reset_index()
W = W.merge(v[['district', 'week_start', 'nb_inc_max_lag0', 'national_inc_lag0']], on=['district', 'week_start'])
eps = 0.5 / 400                                  # Monte Carlo resolution of hhh4 (S = 400); same clip for both models
ll = lambda p, y: y * np.log(np.clip(p, eps, 1 - eps)) + (1 - y) * np.log(np.clip(1 - p, eps, 1 - eps))
W['d'] = ll(W.hhh4, W.y) - ll(W.persistence, W.y)     # > 0: hhh4 better
rng = np.random.default_rng(2027); clusters = (W.fold + '_' + W.week_start.astype(str)).values; uc = np.unique(clusters); idx = {c: np.where(clusters == c)[0] for c in uc}
res = {}
for expo in ['nb_inc_max_lag0', 'national_inc_lag0']:
    x = np.log1p(W[expo].fillna(0).values); z = (x - x.mean()) / x.std()
    F = pd.get_dummies(W.fold).values.astype(float); X = np.column_stack([z, F])
    beta = lambda ix: np.linalg.lstsq(X[ix], W.d.values[ix], rcond=None)[0][0]
    b0 = beta(np.arange(len(W))); bs = np.array([beta(np.concatenate([idx[c] for c in rng.choice(uc, len(uc))])) for _ in range(2000)])
    res[expo] = dict(slope=b0, lo=np.percentile(bs, 2.5), hi=np.percentile(bs, 97.5), p=2 * min((bs <= 0).mean(), (bs >= 0).mean()))
    # within-fold slopes (does the gradient hold inside each season?)
    for f in sorted(W.fold.unique()):
        m = (W.fold == f).values; Xf = np.column_stack([z[m], np.ones(m.sum())])
        res[expo][f'slope_{f}'] = np.linalg.lstsq(Xf, W.d.values[m], rcond=None)[0][0]
    # tertile AUPRC (cut points from pooled at-risk rows)
    t = pd.qcut(x, 3, labels=['low', 'mid', 'high'], duplicates='drop') if len(np.unique(x)) > 3 else None
    W['tert'] = t
    for lev, g in W.groupby('tert', observed=True):
        if g.y.sum() > 0:
            res[expo][f'auprc_{lev}'] = (round(average_precision_score(g.y, g.hhh4), 3), round(average_precision_score(g.y, g.persistence), 3), int(g.y.sum()), len(g))
pd.set_option('display.width', 250)
for k, r in res.items(): print(k, {a: (round(b, 4) if isinstance(b, float) else b) for a, b in r.items()})
pd.DataFrame(res).T.to_csv('b2_effect_modification.csv')
print('mean d overall', W.d.mean().round(4), ' by fold', W.groupby('fold').d.mean().round(4).to_dict())
