"""POST-HOC candidates (see POSTHOC_PLAN.md). Usage: python posthoc_run.py dev | locked"""
import os as _os
def _repo_root():
    d = _os.path.dirname(_os.path.abspath(__file__))
    while not _os.path.exists(_os.path.join(d, '.repo_root')):
        parent = _os.path.dirname(d)
        if parent == d: raise RuntimeError('repository root (.repo_root) not found')
        d = parent
    return d + '/'
ROOT = _repo_root()

import sys, json, pathlib, time
sys.path.insert(0, ROOT + 'experiments')
import engine
from engine import *
from hhh4py import HHH4, graph_order
from hhh4x import HHH4X
from run_models import thresholds_by_district
PH = pathlib.Path(ROOT + 'posthoc'); H4 = 4
v, folds, labels = load()
ob = outbreak_flags(v, 5); AR, Y4 = make_labels(v, ob, 4, H4)
DIST = sorted(v.district.unique()); POP = v.groupby('district').population.first()[DIST].values
THR = np.array([thresholds_by_district(v, 5)[d] for d in DIST])
e = pd.read_csv(PKG / 'data_raw/edges_static.csv'); e = e[e.adjacency == 1]
ids = pd.read_csv(PKG / 'data_raw/districts.csv').set_index('district_id').district
O = graph_order(DIST, list(zip(e.source_id.map(ids), e.target_id.map(ids))))
YM = v.pivot(index='week_start', columns='district', values='cases_obs')[DIST]
WK = YM.index; SEG = v.drop_duplicates('week_start').set_index('week_start').segment.reindex(WK)
WOY = v.drop_duplicates('week_start').set_index('week_start').iso_week.reindex(WK).values
YP = YM.groupby(SEG).shift(1).values; YV = YM.values
YF = YM.groupby(SEG).ffill(limit=4).values
ROWS = np.arange(len(WK))


def fit_hhh4(upto_idx, norm='target'):
    keep = ROWS <= upto_idx
    return HHH4(O, POP, norm=norm).fit(YV[keep], YP[keep], WOY[keep])


def test_rows(fold):
    roles = fold_roles(folds, fold, H4); tr, te = split(v, roles, AR, Y4)
    return tr, te


def frame(te, prob, name, fold, score=None):
    f = v.loc[te, ['district', 'week_start']].copy(); f['y'] = Y4.values[te]
    f['prob'] = prob; f['score'] = prob if score is None else score; f['model'] = name; f['fold'] = fold; f['h'] = H4
    return f


def hhh4_predict(model_for_week, te, sim=None):
    rows = v.loc[te, ['district', 'week_start']]; out = pd.Series(np.nan, index=rows.index); rng = np.random.default_rng(7)
    for wk, g in rows.groupby('week_start'):
        i = WK.get_loc(wk); m = model_for_week(wk)
        P = sim(m, i, rng) if sim else m.simulate_onset(YF[i], WOY[i], H4, THR, S=400, rng=rng)
        out.loc[g.index] = g.district.map(dict(zip(DIST, P))).values
    return out.values


def covariates(test_start):
    """AR: temperature (4w) and rain (8w) anomalies, lag 1, vs climatology before test start, standardised;
    NE: log population of receiving district; END: log population density. Aligned with the predicted week."""
    X = v.copy(); tr = X.week_start < test_start
    for c in ['clim_t2m_mean4_lag1', 'clim_precip_sum8_lag1']:
        clim = X[tr].groupby(['district', 'iso_week'])[c].mean()
        a = X[c] - X[['district', 'iso_week']].join(clim, on=['district', 'iso_week'])[c].values
        X[c + '_z'] = (a / a[tr].std()).fillna(0.0)
    piv = lambda c: X.pivot(index='week_start', columns='district', values=c)[DIST].reindex(WK).values
    Xar = np.stack([piv('clim_t2m_mean4_lag1_z'), piv('clim_precip_sum8_lag1_z')], axis=2)
    lp = np.log(POP); lp = (lp - lp.mean()) / lp.std()
    dens = np.log(v.groupby('district').pop_density.first()[DIST].values); dens = (dens - dens.mean()) / dens.std()
    Xne = np.repeat(lp[None, :, None], len(WK), 0); Xend = np.repeat(dens[None, :, None], len(WK), 0)
    return Xar, Xne, Xend


def season_hhh4_features(cache=PH / 'hhh4_oos_features.csv.gz'):
    """Out-of-sample hhh4 features for every district-week from 2022 on: model fitted on all weeks before the
    calendar year of the row (2019 rows: missing). Columns: hhh4_p4 (onset probability, h=4), hhh4_mu1 (expected
    next-week incidence per 100k)."""
    if cache.exists():
        return pd.read_csv(cache, parse_dates=['week_start'])
    out = []
    for yr in range(2022, 2027):
        start = WK[WK.year == yr].min(); idx = WK.get_loc(start) - 1
        m = fit_hhh4(idx); rng = np.random.default_rng(yr)
        W = m.W(np.exp(m.p[7]))
        for wk in WK[WK.year == yr]:
            i = WK.get_loc(wk)
            P = m.simulate_onset(YF[i], WOY[i], H4, THR, S=400, rng=rng)
            mu1 = m._mu(m.p, np.nan_to_num(YF[i])[None, :], np.array([(WOY[i]) % 52 + 1]))[0] / POP * 1e5
            out.append(pd.DataFrame({'district': DIST, 'week_start': wk, 'hhh4_p4': P, 'hhh4_mu1': mu1}))
        print('  oos hhh4 features', yr, flush=True)
    F = pd.concat(out); F.to_csv(cache, index=False, compression='gzip'); return F


def blocks(weeks, size=4):
    w = sorted(set(weeks)); return [w[i:i + size] for i in range(0, len(w), size)]


def run_fold(fold, fitlog):
    t0 = time.time(); ts = FOLD_DATES[fold][0]; tr, te = test_rows(fold); outs = []
    X = add_anomalies(v, ts); cols = feature_list(MAIN_GROUPS)
    test_idx_start = WK.get_loc(WK[WK >= ts].min()) - 1
    # C1 official weight normalisation
    m1 = fit_hhh4(test_idx_start, norm='source')
    outs.append(frame(te, hhh4_predict(lambda wk: m1, te), 'hhh4_src', fold))
    # C2 covariates
    Xar, Xne, Xend = covariates(ts); keep = ROWS <= test_idx_start
    m2 = HHH4X(O, POP, Xar, Xne, Xend).fit(YV[keep], YP[keep], WOY[keep], ROWS[keep])
    outs.append(frame(te, hhh4_predict(lambda wk: m2, te, sim=lambda m, i, rng: m.simulate_onset_x(YF[i], WOY[i], i + 1, H4, THR, 400, rng)),
                      'hhh4_cov', fold))
    json.dump({'fold': fold, 'hhh4_cov_params': m2.p.round(4).tolist()}, open(PH / f'hhh4_cov_params_{fold}.json', 'w'))
    # C3 hhh4 online (refit every 4 weeks on counts observed by the issue week)
    tw = v.loc[te, 'week_start']; online = {}
    for b in blocks(tw):
        mb = fit_hhh4(WK.get_loc(b[0]))
        for wk in b: online[wk] = mb
    outs.append(frame(te, hhh4_predict(lambda wk: online[wk], te), 'hhh4_online', fold))
    print(fold, 'hhh4 variants', f'{time.time() - t0:.0f}s', flush=True)
    # C4 LightGBM online, fold's frozen configuration
    cfg = eval(fitlog['cfg']); nit = fitlog['n_iter']
    yv = Y4.values; ok = (AR.values == 1) & ~np.isnan(yv); p4 = pd.Series(np.nan, index=v.index)
    for b in blocks(tw):
        trb = ok & (v.week_start.values <= (b[0] - pd.Timedelta(weeks=H4)).to_datetime64())
        mdl, _ = lgb_fit(X.loc[trb, cols].astype(float), yv[trb], cfg, n_iter=nit)
        sel = te & v.week_start.isin(b).values
        p4[sel] = mdl.predict(X.loc[sel, cols].astype(float))
    outs.append(frame(te, p4[te].values, 'lgbm_online', fold))
    # C5 hybrid stack
    F = season_hhh4_features(); Xh = X.merge(F, on=['district', 'week_start'], how='left'); Xh.index = X.index
    cal, info = main_model(Xh, fold, tr, te, Y4, cols + ['hhh4_p4', 'hhh4_mu1'])
    outs.append(frame(te, cal['raw'], 'hybrid_stack', fold))
    # C7 compact penalised logistic regression
    lc = ['inc_lag0', 'inc_mean4_to_lag0', 'inc_mean12_to_lag0', 'nb_inc_mean_lag0', 'nb_inc_max_lag0', 'gravity_inc_lag0',
          'national_inc_lag0']
    Z = np.column_stack([np.log1p(X[lc].clip(lower=0)).values, X[[c + '_anom' for c in ANOM_SRC]].values,
                         X[['woy_sin', 'woy_cos', 'log_population']].values])
    med = np.nanmedian(Z[tr], axis=0); Z = np.where(np.isnan(Z), med, Z); mu_, sd_ = Z[tr].mean(0), Z[tr].std(0) + 1e-9; Z = (Z - mu_) / sd_
    lr = LogisticRegression(C=0.1, max_iter=5000).fit(Z[tr], yv[tr])
    outs.append(frame(te, lr.predict_proba(Z[te])[:, 1], 'logit_compact', fold))
    # C8 rare-event weighting
    spw = float((yv[tr] == 0).sum() / max((yv[tr] == 1).sum(), 1))
    old = dict(engine.BASE); engine.BASE['scale_pos_weight'] = spw
    try:
        cal8, _ = main_model(X, fold, tr, te, Y4, cols)
    finally:
        engine.BASE.clear(); engine.BASE.update(old)
    outs.append(frame(te, cal8['raw'], 'lgbm_balanced', fold))
    print(fold, 'all candidates', f'{time.time() - t0:.0f}s', flush=True)
    return pd.concat(outs, ignore_index=True)


def add_ensembles(P):
    sub = P[P.model.isin(['hhh4', 'main_raw', 'persistence'])]
    base = sub.pivot(index=['fold', 'district', 'week_start'], columns='model', values='prob').reset_index()
    base = base.merge(sub[sub.model == 'hhh4'][['fold', 'district', 'week_start', 'y']], on=['fold', 'district', 'week_start'], validate='one_to_one')
    outs = []
    for name, a, b in [('ens_hhh4_lgbm', 'hhh4', 'main_raw'), ('ens_hhh4_persist', 'hhh4', 'persistence')]:
        f = base[['fold', 'district', 'week_start', 'y']].copy(); f['prob'] = (base[a] + base[b]) / 2; f['score'] = f.prob
        f['model'] = name; f['h'] = H4; outs.append(f)
    return pd.concat(outs, ignore_index=True)


if __name__ == '__main__':
    mode = sys.argv[1]
    if mode == 'dev':
        fl = {(d['fold'], d['h']): d for d in json.load(open(OUT / 'dev_fit_log.json')) if 'h' in d}
        frozen = pd.read_csv(OUT / 'dev_predictions_primary.csv.gz', parse_dates=['week_start'])
        frozen = frozen[(frozen.h == H4) & frozen.model.isin(['hhh4', 'main_raw', 'persistence'])]
        cand = pd.concat([run_fold(f, fl[(f, H4)]) for f in DEV_FOLDS])
        P = pd.concat([frozen, cand, add_ensembles(frozen)], ignore_index=True)
        P.to_csv(PH / 'posthoc_dev_predictions.csv.gz', index=False, compression='gzip')
    else:
        name = sys.argv[2]
        fl = {d['h']: d for d in json.load(open(OUT / 'locked_fit_log.json')) if 'h' in d}
        frozen = pd.read_csv(OUT / 'locked_predictions.csv.gz', parse_dates=['week_start'])
        frozen = frozen[(frozen.h == H4) & frozen.model.isin(['hhh4', 'main_raw', 'persistence'])]
        cand = run_fold('LOCKED2026', fl[H4])
        P = pd.concat([frozen, cand, add_ensembles(frozen)], ignore_index=True)
        P.to_csv(PH / 'posthoc_locked_predictions_ALL.csv.gz', index=False, compression='gzip')
        print('locked candidate predictions written; selected model for the confirmatory-style report:', name)
