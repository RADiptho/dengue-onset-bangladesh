from rlib import *
import sys
# D. calibration (development folds and locked; raw, Platt, isotonic)
cal = []
for nm, pp in [('dev', P), ('locked', PL)]:
    for f in list(pp.fold.unique()) + (['POOLED'] if nm == 'dev' else []):
        for m in ['main_raw', 'main_platt', 'main_isotonic', 'persistence', 'hhh4']:
            q = pp[(pp.model == m) & pp.y.notna()] if f == 'POOLED' else pp[(pp.model == m) & (pp.fold == f) & pp.y.notna()]
            d = cal_stats(q.prob.values, q.y.values); d.update(period=f, model=m, n=len(q), distinct=q.prob.round(6).nunique(),
                                                                  share_at_max=(q.prob >= q.prob.max() - 1e-9).mean(), auprc=AP(q.y, q.prob))
            cal.append(d)
CAL = pd.DataFrame(cal); CAL.to_csv(OUT + 'D_calibration.csv', index=False)
fl = json.load(open(R + 'dev_fit_log.json')) + json.load(open(R + 'locked_fit_log.json'))
pd.DataFrame([x for x in fl if x.get('h') == 4 and 'inner_val_pos' in x]).to_csv(OUT + 'D_inner_validation.csv', index=False)
print('D done', flush=True)

