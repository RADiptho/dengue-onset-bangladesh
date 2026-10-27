"""Independent recomputation of headline numbers. Uses only pandas/numpy/sklearn and the saved files (no project modules)."""
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
v = pd.read_csv(B + 'pipeline/outputs/master_dataset_v2.csv', parse_dates=['week_start']).sort_values(['district', 'week_start'])
# onset events from scratch: outbreak week (inc>=5 & cases>=10) preceded by 4 observed non-outbreak weeks in the same segment
v['ob'] = np.where(v.cases_obs.isna(), np.nan, ((v.inc_obs >= 5) & (v.cases_obs >= 10)).astype(float))
ev = []
for (d, s), g in v.groupby(['district', 'segment']):
    o = g.ob.values; w = g.week_start.values
    for i in range(4, len(g)):
        if o[i] == 1 and np.all(o[i-4:i] == 0): ev.append((d, pd.Timestamp(w[i])))
ev = pd.DataFrame(ev, columns=['district', 'onset'])
print('onset events by year', ev.groupby(ev.onset.dt.year).size().to_dict())
def capture(g, k):
    hits = []
    weeks = set(g.week_start)
    for _, o in ev.iterrows():
        if o.onset - pd.Timedelta(weeks=1) not in weeks: continue
        hit = False
        for j in range(1, 5):
            gw = g[g.week_start == o.onset - pd.Timedelta(weeks=j)]
            if o.district in set(gw.district):
                top = gw.sort_values('score', ascending=False, kind='mergesort').head(k).district
                hit |= o.district in set(top)
        hits.append(hit)
    return np.mean(hits), len(hits)
out = []
for name, f in [('dev', B + 'posthoc/posthoc_dev_predictions.csv.gz'), ('locked', B + 'posthoc/posthoc_locked_predictions_ALL.csv.gz')]:
    P = pd.read_csv(f, parse_dates=['week_start'], low_memory=False)
    for m in ['persistence', 'hhh4', 'main_raw', 'ens_hhh4_persist', 'hhh4_online']:
        g = P[P.model == m]; y = g[g.y.notna()]
        r = dict(set=name, model=m, auprc=average_precision_score(y.y, y.prob), brier=np.mean((y.prob - y.y) ** 2), oe=y.y.sum() / y.prob.sum())
        for k in [5, 10, 20]:
            caps = [capture(gf, k) for _, gf in g.groupby('fold')]
            r[f'cap@{k}'] = sum(c * n for c, n in caps) / sum(n for _, n in caps); r['n_events'] = sum(n for _, n in caps)
        out.append(r)
R = pd.DataFrame(out); pd.set_option('display.width', 200); print(R.round(3).to_string(index=False)); R.to_csv(B + 'audit/output/recomputed_headline.csv', index=False)
