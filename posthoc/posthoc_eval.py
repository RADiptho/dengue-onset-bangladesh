import os as _os
def _repo_root():
    d = _os.path.dirname(_os.path.abspath(__file__))
    while not _os.path.exists(_os.path.join(d, '.repo_root')):
        parent = _os.path.dirname(d)
        if parent == d: raise RuntimeError('repository root (.repo_root) not found')
        d = parent
    return d + '/'
ROOT = _repo_root()

import sys, json, pathlib
sys.path.insert(0, ROOT + 'experiments')
from engine import *
from evaluate import eval_table
import stats_tests as stt
PH = pathlib.Path(ROOT + 'posthoc')
v, folds, labels = load(); ev = onset_events(v, outbreak_flags(v, 5))
which = sys.argv[1] if len(sys.argv) > 1 else 'dev'
P = pd.read_csv(PH / ('posthoc_dev_predictions.csv.gz' if which == 'dev' else 'posthoc_locked_predictions_ALL.csv.gz'), parse_dates=['week_start'])
res, evr = eval_table(P, v, folds, ev)
evr['onset_week'] = pd.to_datetime(evr.onset_week)
def lead2(g, k):
    R = rank_table(g, g.score.values).set_index(['district', 'week_start']); E = evaluable_events(ev, g.week_start.unique(), 4); hits = []
    for _, o in E.iterrows():
        hits.append(any((o.district, o.onset_week - pd.Timedelta(weeks=j)) in R.index and R.loc[(o.district, o.onset_week - pd.Timedelta(weeks=j)), 'rank'] <= k for j in range(2, 5)))
    return hits
rows = []
for m, g in P.groupby('model'):
    pm = prob_metrics(g.prob.values.astype(float), g.y.values.astype(float)); e = evr[evr.model == m]
    r = dict(model=m, n_events=int((e.k == 10).sum()), auprc=pm.get('auprc'), brier=pm.get('brier'), slope=pm.get('cal_slope'), oe=pm.get('oe_ratio'))
    for k in KS:
        r[f'cap@{k}'] = e[e.k == k].hit.mean()
        r[f'lead2@{k}'] = np.mean(sum([lead2(gg, k) for _, gg in g.groupby('fold')], []))
    rows.append(r)
T = pd.DataFrame(rows).sort_values('auprc', ascending=False)
T.to_csv(PH / f'posthoc_{which}_pooled.csv', index=False); res.to_csv(PH / f'posthoc_{which}_perfold.csv', index=False)
evr.to_csv(PH / f'posthoc_{which}_event_hits.csv.gz', index=False, compression='gzip')
pd.set_option('display.width', 250); print(T.round(3).to_string(index=False))
if which == 'dev':
    pf = res.pivot(index='model', columns='fold', values='auprc'); print('\nper-fold AUPRC\n', pf.round(3))
    tests = []
    for m in T.model:
        for ref in ['hhh4', 'persistence']:
            if m == ref: continue
            for k in KS:
                d, lo, hi, p, n = stt.cluster_boot_capture(evr, m, ref, 4, k); tests.append(dict(model=m, ref=ref, metric=f'cap@{k}', diff=d, lo=lo, hi=hi, p=p))
            for met in ['auprc', 'brier']:
                d, lo, hi, p = stt.block_boot_prob(P, m, ref, 4, met); tests.append(dict(model=m, ref=ref, metric=met, diff=d, lo=lo, hi=hi, p=p))
    TT = pd.DataFrame(tests)
    from statsmodels.stats.multitest import multipletests
    TT['p_holm'] = np.nan
    for (ref, met), g in TT.groupby(['ref', TT.metric.str.split('@').str[0]]): TT.loc[g.index, 'p_holm'] = multipletests(g.p, method='holm')[1]
    TT.to_csv(PH / 'posthoc_dev_tests.csv', index=False)
    print('\nvs hhh4 (post-hoc, Holm within metric family):'); print(TT[TT.ref == 'hhh4'].round(3).to_string(index=False))
    # nested leave-one-fold-out selection (criterion: mean AUPRC on the other two folds; tie-break Capture@10)
    cap = res.pivot(index='model', columns='fold', values='event_cap@10'); nested = []
    for held in DEV_FOLDS:
        others = [f for f in DEV_FOLDS if f != held]
        crit = pf[others].mean(axis=1) + 1e-6 * cap[others].mean(axis=1)
        sel = crit.idxmax()
        nested.append(dict(held_out=held, selected=sel, sel_auprc=pf.loc[sel, held], hhh4_auprc=pf.loc['hhh4', held],
                           sel_cap10=cap.loc[sel, held], hhh4_cap10=cap.loc['hhh4', held], persist_auprc=pf.loc['persistence', held]))
    N = pd.DataFrame(nested); N.to_csv(PH / 'posthoc_nested_selection.csv', index=False); print('\nnested selection\n', N.round(3).to_string(index=False))
