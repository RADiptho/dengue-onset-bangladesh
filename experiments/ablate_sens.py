"""Pre-registered ablations (main model) and sensitivity analyses (main, persistence, hhh4), h=4, development folds."""
import time, sys
from run_models import *
from evaluate import eval_table

def national_seasonal_prior(national_long, before_year):
    """Mean share of annual cases by calendar month, complete years strictly before `before_year` (frozen definition)."""
    n = national_long.copy(); n['y'] = n.month.str[:4].astype(int); n['m'] = n.month.str[5:7].astype(int)
    n = n[n.y < before_year]; full = n.groupby('y').m.nunique(); n = n[n.y.isin(full[full == 12].index)]
    n['share'] = n.cases / n.groupby('y').cases.transform('sum').clip(lower=1)
    return n.groupby('m').share.mean()
v, folds, labels = load()
ob5 = outbreak_flags(v, 5); ar5, y5 = make_labels(v, ob5, 4, 4); ev5 = onset_events(v, ob5)
H4 = 4
bundles = {f: hhh4_fit(v, FOLD_DATES[f][0]) for f in DEV_FOLDS}
nat = pd.read_csv(PKG / 'outputs/national_monthly_long_2008_2026.csv')
results = []

def collect(preds, events, tag, Vref=None):
    r, e = eval_table(preds, Vref if Vref is not None else v, folds, events)
    for m, g in e[(e.h == H4)].groupby('model'):
        row = dict(tag=tag, model=m)
        for k in KS:
            row[f'cap@{k}'] = g[g.k == k].hit.mean(); row['n_events'] = (g.k == k).sum()
        pp = preds[preds.model == m]
        pm = prob_metrics(pp.prob.values.astype(float), pp.y.values.astype(float))
        row.update(auprc=pm.get('auprc'), brier=pm.get('brier'), slope=pm.get('cal_slope'))
        results.append(row)
    return e

mode = sys.argv[1]
if mode == 'ablation':
    specs = {'full': (MAIN_GROUPS, ()),
             'no_spatial': ([g for g in MAIN_GROUPS if g not in ('adjacency', 'gravity')], ()),
             'adjacency_only': ([g for g in MAIN_GROUPS if g != 'gravity'], ()),
             'no_climate': ([g for g in MAIN_GROUPS if g != 'climate'], ()),
             'plus_satellite': (MAIN_GROUPS + ['satellite_dev'], ()),
             'plus_reporting': (MAIN_GROUPS + ['reporting'], ()),
             'plus_national_prior': (MAIN_GROUPS, ('nat_prior',))}
    allp, allev = [], []
    for name, (groups, extra) in specs.items():
        ps = []
        for f in DEV_FOLDS:
            Xv = v.copy()
            if extra:
                prior = national_seasonal_prior(nat, FOLD_DATES[f][0].year)
                Xv['nat_prior'] = Xv.week_start.dt.month.map(prior).astype(float)
            p, info, *_ = run(v, folds, f, H4, ar5, y5, groups=groups, extra=extra, models=('main',), Xv=Xv)
            p = p[p.model == 'main_raw'].assign(model=f'main_{name}'); ps.append(p)
        P = pd.concat(ps); allp.append(P); allev.append(collect(P, ev5, 'ablation'))
        print(name, 'done', flush=True)
    pd.concat(allp).to_csv(OUT / 'dev_predictions_ablation.csv.gz', index=False, compression='gzip')
    pd.concat(allev).to_csv(OUT / 'dev_event_hits_ablation.csv.gz', index=False, compression='gzip')
    pd.DataFrame(results).to_csv(OUT / 'dev_ablation.csv', index=False)
elif mode == 'sensitivity':
    def three(tag, ar, y, events, T=5, thr=None, delay=0, Vuse=None, Xv=None, evaluate_mask=None):
        Vu = v if Vuse is None else Vuse
        ps = []
        for f in DEV_FOLDS:
            b = bundles[f] if Vuse is None else hhh4_fit(Vu, FOLD_DATES[f][0])
            p, *_ = run(Vu, folds, f, H4, ar, y, models=('baselines', 'hhh4', 'main'), hhh4_bundle=b, T=T,
                        thr_override=thr, delay=delay, Xv=Xv)
            ps.append(p[p.model.isin(['persistence', 'hhh4', 'main_raw'])])
        P = pd.concat(ps)
        if evaluate_mask is not None:
            P = P[evaluate_mask(P)]; events = events[evaluate_mask(events.rename(columns={'onset_week': 'week_start'}))]
        collect(P, events, tag, Vu); print(tag, 'done', flush=True)
    for T in [2, 10]:
        obT = outbreak_flags(v, T); a, y = make_labels(v, obT, 4, 4); three(f'threshold_T{T}', a, y, onset_events(v, obT), T=T)
    for q in [6, 8]:
        a, y = make_labels(v, ob5, q, 4); three(f'quiet_q{q}', a, y, onset_events(v, ob5, q))
    # district-specific threshold: training-only 90th percentile of weekly incidence (min 1/100k), per fold
    for f in DEV_FOLDS:
        pass
    ps_dt = []
    pop = v.groupby('district').population.first()
    for f in DEV_FOLDS:
        trmask = v.week_start < FOLD_DATES[f][0]
        q90 = v[trmask].groupby('district').inc_obs.quantile(0.9).clip(lower=1.0)
        thr_row = v.district.map(q90)
        obD = outbreak_flags(v, thr_row); a, y = make_labels(v, obD, 4, 4)
        thr_c = {d: max(10.0, q90[d] * pop[d] / 1e5) for d in pop.index}
        p, *_ = run(v, folds, f, H4, a, y, models=('baselines', 'hhh4', 'main'), hhh4_bundle=bundles[f], thr_override=thr_c)
        evD = onset_events(v, obD)
        r, e = eval_table(p[p.model.isin(['persistence', 'hhh4', 'main_raw'])], v, folds, evD)
        ps_dt.append(e)
    E = pd.concat(ps_dt)
    for m, g in E[E.h == H4].groupby('model'):
        results.append(dict(tag='district_q90_threshold', model=m, n_events=(g.k == 10).sum(), **{f'cap@{k}': g[g.k == k].hit.mean() for k in KS}))
    print('district threshold done', flush=True)
    # Dhaka excluded from ranking and events
    three('dhaka_excluded', ar5, y5, ev5, evaluate_mask=lambda d: d.district != 'Dhaka')
    # one extra week of reporting delay for all case-derived information
    Xd = v.copy()
    case_cols = GROUPS['own'] + GROUPS['adjacency'] + GROUPS['gravity'] + GROUPS['national']
    Xd[case_cols] = Xd.groupby(['district', 'segment'])[case_cols].shift(1)
    three('reporting_delay_plus1', ar5, y5, ev5, delay=1, Xv=Xd)
    pd.DataFrame(results).to_csv(OUT / 'dev_sensitivity.csv', index=False)
