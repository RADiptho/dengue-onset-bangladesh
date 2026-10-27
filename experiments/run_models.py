"""Fit every model for a fold/horizon/definition and return long-format test predictions."""
import sys, time, json
from engine import *

def thresholds_by_district(v, T):
    pop = v.groupby('district').population.first()
    return {d: max(10.0, T * p / 1e5) for d, p in pop.items()}


def run(v, folds, fold, h, at_risk, y, groups=MAIN_GROUPS, extra=(), models=('baselines', 'hhh4', 'main'),
        hhh4_bundle=None, T=5, tag='primary', Xv=None, thr_override=None, delay=0):
    test_start = FOLD_DATES[fold][0]
    roles = fold_roles(folds, fold, h)
    tr, te = split(v, roles, at_risk, y)
    X = add_anomalies(v if Xv is None else Xv, test_start)
    rows = v.loc[te, ['district', 'week_start']].copy()
    rows['y'] = y.values[te]
    frames, infos = [], {}
    def add(name, score, prob):
        f = rows.copy(); f['model'] = name; f['score'] = score; f['prob'] = prob; frames.append(f)
    if 'baselines' in models:
        for name, (s, p) in baseline_preds(X, tr, te, y).items():
            add(name, s, p)
    if 'hhh4' in models:
        p = hhh4_preds(v, te, h, hhh4_bundle, thr_override or thresholds_by_district(v, T), delay=delay)
        add('hhh4', p, p)
    if 'main' in models:
        cols = feature_list(groups, extra)
        cal, info = main_model(X, fold, tr, te, y, cols)
        for c, p in cal.items():
            add(f'main_{c}', cal['raw'], p)          # ranking always uses the raw score (pre-specified)
        infos = info
    out = pd.concat(frames, ignore_index=True)
    out['fold'], out['h'], out['tag'] = fold, h, tag
    return out, infos, int(tr.sum()), int(te.sum())

if __name__ == '__main__':
    v, folds, labels = load()
    ob = outbreak_flags(v, 5)
    allp, log = [], []
    for fold in DEV_FOLDS:
        t0 = time.time()
        bundle = hhh4_fit(v, FOLD_DATES[fold][0])
        log.append(dict(fold=fold, model='hhh4', params=[round(x, 4) for x in bundle[0].p], converged=bool(bundle[0].opt.success)))
        for h in H:
            ar, y = make_labels(v, ob, 4, h)
            p, info, ntr, nte = run(v, folds, fold, h, ar, y, hhh4_bundle=bundle)
            allp.append(p); log.append(dict(fold=fold, h=h, n_train=ntr, n_test=nte, **info))
            print(fold, h, 'train', ntr, 'test', nte, info.get('cfg'), info.get('n_iter'), f'{time.time()-t0:.0f}s', flush=True)
    pd.concat(allp).to_csv(OUT / 'dev_predictions_primary.csv.gz', index=False, compression='gzip')
    json.dump(log, open(OUT / 'dev_fit_log.json', 'w'), indent=1, default=str)
