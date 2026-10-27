"""Independent verification of the experimental pipeline."""
import json
from run_models import *
from evaluate import eval_table
from stats_tests import cluster_boot_capture, block_boot_prob
v, folds, labels = load(); ob = outbreak_flags(v, 5); ev = onset_events(v, ob); ar, y = make_labels(v, ob, 4, 4)
out = {}
# 1. determinism: refit F2025 h=4 and compare with stored predictions
dev = pd.read_csv(OUT / 'dev_predictions_primary.csv.gz', parse_dates=['week_start'])
b = hhh4_fit(v, FOLD_DATES['F2025'][0])
p, *_ = run(v, folds, 'F2025', 4, ar, y, hhh4_bundle=b)
old = dev[(dev.fold == 'F2025') & (dev.h == 4)].sort_values(['model', 'district', 'week_start']).reset_index(drop=True)
new = p.sort_values(['model', 'district', 'week_start']).reset_index(drop=True)
out['determinism_max_abs_diff'] = float(np.nanmax(np.abs(old.prob.values - new.prob.values)))
# 2. label-permutation negative control: shuffled training labels must destroy skill
rng = np.random.default_rng(5)
roles = fold_roles(folds, 'F2025', 4); tr, te = split(v, roles, ar, y)
ys = y.copy(); idx = np.where(tr)[0]; ys.iloc[idx] = rng.permutation(y.values[idx])
X = add_anomalies(v, FOLD_DATES['F2025'][0])
cal, info = main_model(X, 'F2025', tr, te, ys, feature_list(MAIN_GROUPS))
rows = v.loc[te, ['district', 'week_start']].copy(); rows['y'] = y.values[te]; rows['score'] = cal['raw']; rows['prob'] = cal['raw']
rows['fold'] = 'F2025'; rows['h'] = 4; rows['model'] = 'main_shuffled'
r, e = eval_table(rows, v, folds, ev)
out['negative_control_shuffled_labels'] = dict(auprc=float(r.auprc.iloc[0]), prevalence=float(r.prevalence.iloc[0]),
                                               cap10=float(r['event_cap@10'].iloc[0]), random_floor10=float(r['floor@10'].iloc[0]))
# 3. brute-force recomputation of event capture@10 for the main model, pooled development
evr = pd.read_csv(OUT / 'dev_event_hits_primary.csv.gz', parse_dates=['onset_week'])
hits = []
for f in DEV_FOLDS:
    g = dev[(dev.fold == f) & (dev.h == 4) & (dev.model == 'main_raw')]
    for _, o in ev.iterrows():
        if (o.onset_week - pd.Timedelta(weeks=1)) not in set(g.week_start):
            continue
        hit = False
        for j in range(1, 5):
            w = o.onset_week - pd.Timedelta(weeks=j); gw = g[g.week_start == w]
            if o.district in set(gw.district):
                top = gw.sort_values('score', ascending=False).district.head(10).tolist()
                hit |= o.district in top
        hits.append(hit)
out['bruteforce_cap10_main'] = float(np.mean(hits)); out['pipeline_cap10_main'] = float(evr[(evr.h == 4) & (evr.k == 10) & (evr.model == 'main_raw')].hit.mean())
# 4. no 2026 row in any development training or test set
for f in DEV_FOLDS:
    for h in H:
        rr = fold_roles(folds, f, h)
        assert not ((rr.index.get_level_values('week_start') >= '2026-01-05') & (rr.values != 'excluded')).any()
out['no_2026_rows_in_development'] = True
# 5. locked: training rows end before 2026 for every horizon
for h in H:
    rr = fold_roles(folds, 'LOCKED2026', h); ws = rr.index.get_level_values('week_start')
    assert (ws[rr.values == 'train'] + pd.Timedelta(weeks=h) < pd.Timestamp('2026-01-05')).all()
out['locked_training_embargo_ok'] = True
# 6. locked bootstrap (descriptive; 10 events)
lp = pd.read_csv(OUT / 'locked_predictions.csv.gz', parse_dates=['week_start']); le = pd.read_csv(OUT / 'locked_event_hits.csv.gz', parse_dates=['onset_week'])
lb = []
for a, bb in [('main_raw', 'persistence'), ('main_raw', 'hhh4'), ('hhh4', 'persistence')]:
    for k in KS:
        d, lo, hi, pv, n = cluster_boot_capture(le, a, bb, 4, k); lb.append(dict(a=a, b=bb, metric=f'cap@{k}', diff=d, lo=lo, hi=hi, p=pv, n=n))
    d, lo, hi, pv = block_boot_prob(lp, a, bb, 4, 'auprc'); lb.append(dict(a=a, b=bb, metric='auprc', diff=d, lo=lo, hi=hi, p=pv))
pd.DataFrame(lb).to_csv(OUT / 'locked_stat_tests.csv', index=False)
json.dump(out, open(OUT / 'verification.json', 'w'), indent=1, default=float)
print(json.dumps(out, indent=1, default=float)); print(pd.DataFrame(lb).round(3).to_string(index=False))
