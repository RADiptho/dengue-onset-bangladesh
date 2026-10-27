"""LOCKED2026: single run with the frozen procedure. No choice below depends on 2026 outcomes."""
import json
from run_models import *
from evaluate import eval_table
v, folds, labels = load()
ob = outbreak_flags(v, 5); ev = onset_events(v, ob)
bundle = hhh4_fit(v, FOLD_DATES['LOCKED2026'][0])
allp, log = [], [dict(model='hhh4', params=[round(x, 4) for x in bundle[0].p], converged=bool(bundle[0].opt.success))]
for h in H:
    ar, y = make_labels(v, ob, 4, h)
    p, info, ntr, nte = run(v, folds, 'LOCKED2026', h, ar, y, hhh4_bundle=bundle)
    allp.append(p); log.append(dict(h=h, n_train=ntr, n_test=nte, **info)); print(h, ntr, nte, info.get('cfg'), info.get('n_iter'), flush=True)
P = pd.concat(allp); P.to_csv(OUT / 'locked_predictions.csv.gz', index=False, compression='gzip')
json.dump(log, open(OUT / 'locked_fit_log.json', 'w'), indent=1, default=str)
res, evr = eval_table(P, v, folds, ev)
res.to_csv(OUT / 'locked_metrics.csv', index=False); evr.to_csv(OUT / 'locked_event_hits.csv.gz', index=False, compression='gzip')
pd.set_option('display.width', 250)
show = ['h', 'model', 'n_events', 'positives', 'auprc', 'brier', 'cal_slope', 'oe_ratio', 'event_cap@5', 'event_cap@10', 'event_cap@20', 'floor@10', 'ceiling@10', 'lead@10']
print(res[show].round(3).to_string(index=False))
