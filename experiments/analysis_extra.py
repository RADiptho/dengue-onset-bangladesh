import json
from run_models import *
from evaluate import eval_table
import hhh4py
v, folds, labels = load()
ob5 = outbreak_flags(v, 5); ar, y = make_labels(v, ob5, 4, 4); ev = onset_events(v, ob5)
rng = np.random.default_rng(99)
cols = feature_list(MAIN_GROUPS); spatial = GROUPS['adjacency'] + GROUPS['gravity']
res = {}

# ---- historically low/high districts per fold (bottom/top half of training-period per-capita incidence)
def low_high(f):
    tr = v[v.week_start < FOLD_DATES[f][0]]
    burden = tr.groupby('district').cases_obs.sum() / tr.groupby('district').population.first()
    return set(burden[burden <= burden.median()].index)

# ---- 1. spatial permutation test + SHAP (main model, h=4, refit identically to the primary run)
perm_auprc, perm_cap, obs = [], [], {}
shap_rows, fold_models = [], {}
base_preds = []
for f in DEV_FOLDS:
    roles = fold_roles(folds, f, 4); tr, te = split(v, roles, ar, y)
    X = add_anomalies(v, FOLD_DATES[f][0])
    cal, info, model = main_model(X, f, tr, te, y, cols, return_model=True)
    fold_models[f] = (model, X, tr, te)
    rows = v.loc[te, ['district', 'week_start']].copy(); rows['y'] = y.values[te]; rows['score'] = cal['raw']; rows['prob'] = cal['raw']
    rows['fold'] = f; rows['h'] = 4; rows['model'] = 'main_raw'; base_preds.append(rows)
    contrib = model.predict(X.loc[te, cols].astype(float), pred_contrib=True)[:, :-1]
    for g in MAIN_GROUPS:
        gi = [cols.index(c) for c in feature_list([g]) if c in cols]
        shap_rows.append(dict(fold=f, group=g, mean_abs=float(np.abs(contrib[:, gi].sum(axis=1)).mean()),
                              mean_abs_low=float(np.abs(contrib[v.loc[te, 'district'].isin(low_high(f)).values][:, gi].sum(axis=1)).mean()),
                              mean_abs_high=float(np.abs(contrib[~v.loc[te, 'district'].isin(low_high(f)).values][:, gi].sum(axis=1)).mean())))
BP = pd.concat(base_preds)
r0, e0 = eval_table(BP, v, folds, ev, ks=[10])
obs_cap = e0.hit.mean(); obs_auprc = prob_metrics(BP.prob.values, BP.y.values.astype(float))['auprc']
assert abs(obs_cap - 0.862) < 1e-3, 'refit does not reproduce primary main model'
NPERM = 200
for it in range(NPERM):
    ps = []
    for f in DEV_FOLDS:
        model, X, tr, te = fold_models[f]
        Xp = X.loc[te, cols].astype(float).copy()
        wk = v.loc[te, 'week_start'].values
        for w in np.unique(wk):
            ix = np.where(wk == w)[0]; perm = rng.permutation(ix)
            Xp.iloc[ix, [cols.index(c) for c in spatial]] = Xp.iloc[perm, [cols.index(c) for c in spatial]].values
        p = BP[BP.fold == f].copy(); p['score'] = model.predict(Xp); p['prob'] = p.score; ps.append(p)
    P = pd.concat(ps); _, e = eval_table(P, v, folds, ev, ks=[10])
    perm_cap.append(e.hit.mean()); perm_auprc.append(prob_metrics(P.prob.values, P.y.values.astype(float))['auprc'])
res['spatial_permutation'] = dict(observed_cap10=obs_cap, perm_mean_cap10=float(np.mean(perm_cap)),
                                  p_cap10=(1 + sum(c >= obs_cap for c in perm_cap)) / (NPERM + 1),
                                  observed_auprc=obs_auprc, perm_mean_auprc=float(np.mean(perm_auprc)),
                                  p_auprc=(1 + sum(a >= obs_auprc for a in perm_auprc)) / (NPERM + 1), n_perm=NPERM)
print('permutation', res['spatial_permutation'], flush=True)
S = pd.DataFrame(shap_rows); S['share'] = S.mean_abs / S.groupby('fold').mean_abs.transform('sum')
S.to_csv(OUT / 'dev_shap_groups.csv', index=False)
piv = S.pivot(index='group', columns='fold', values='share')
from scipy.stats import spearmanr
res['shap_stability_spearman'] = {f'{a}-{b}': float(spearmanr(piv[a], piv[b])[0]) for a, b in [('F2023', 'F2024'), ('F2023', 'F2025'), ('F2024', 'F2025')]}
print(piv.round(3)); print(res['shap_stability_spearman'], flush=True)

# ---- 2. exploratory: hhh4 without the neighbourhood component (phi fixed ~0)
class HHH4noNE(hhh4py.HHH4):
    def _mu(self, p, Yprev, woy):
        q = p.copy(); q[3] = -30.0
        return super()._mu(q, Yprev, woy)
    def simulate_onset(self, *a, **k):
        self.p = self.p.copy(); self.p[3] = -30.0
        return super().simulate_onset(*a, **k)
ps = []
for f in DEV_FOLDS:
    b = list(hhh4_fit(v, FOLD_DATES[f][0]))
    Yv, Yp = b[1].values, b[1].groupby(b[2]).shift(1).values
    keep = b[1].index < FOLD_DATES[f][0]
    m = HHH4noNE(b[0].O, b[0].pop).fit(Yv[keep], Yp[keep], b[3][keep]); b[0] = m
    roles = fold_roles(folds, f, 4); tr, te = split(v, roles, ar, y)
    p = v.loc[te, ['district', 'week_start']].copy(); p['y'] = y.values[te]
    p['prob'] = hhh4_preds(v, te, 4, tuple(b), thresholds_by_district(v, 5)); p['score'] = p.prob
    p['fold'] = f; p['h'] = 4; p['model'] = 'hhh4_no_neighbour'; ps.append(p)
PN = pd.concat(ps); PN.to_csv(OUT / 'dev_predictions_hhh4_noNE.csv.gz', index=False, compression='gzip')
_, eN = eval_table(PN, v, folds, ev)
res['hhh4_no_neighbour'] = {f'cap@{k}': float(eN[eN.k == k].hit.mean()) for k in KS}
res['hhh4_no_neighbour']['auprc'] = prob_metrics(PN.prob.values, PN.y.values.astype(float))['auprc']
print('hhh4 no neighbour', res['hhh4_no_neighbour'], flush=True)

# ---- 3. H2: capture in historically low vs high districts (spatial vs no-spatial; hhh4 vs hhh4 without neighbourhood)
abl = pd.read_csv(OUT / 'dev_event_hits_ablation.csv.gz', parse_dates=['onset_week'])
prim = pd.read_csv(OUT / 'dev_event_hits_primary.csv.gz', parse_dates=['onset_week'])
allh = pd.concat([abl, prim[prim.model == 'hhh4'], eN])
allh['low'] = [d in low_high(f) for d, f in zip(allh.district, allh.fold)]
h2 = allh[(allh.h == 4) & allh.model.isin(['main_full', 'main_no_spatial', 'hhh4', 'hhh4_no_neighbour'])].groupby(['model', 'k', 'low']).hit.agg(['mean', 'size']).reset_index()
h2.to_csv(OUT / 'dev_H2_low_high.csv', index=False); print(h2.round(3).to_string(index=False), flush=True)

# ---- 4. H4: count vs per-capita vs onset-risk prioritisation (k = 5, 10, 20; all districts are candidates)
import lightgbm as lgb
rows = []
for f in DEV_FOLDS:
    roles = fold_roles(folds, f, 4)
    r = roles.reindex(pd.MultiIndex.from_frame(v[['district', 'week_start']])).values
    X = add_anomalies(v, FOLD_DATES[f][0])
    trc = (r == 'train') & v.y_future_cases_4w.notna().values; tec = (r == 'test') & v.y_future_cases_4w.notna().values
    reg = lgb.train({**BASE, 'objective': 'tweedie', 'tweedie_variance_power': 1.3, 'num_leaves': 15, 'min_child_samples': 20},
                    lgb.Dataset(X.loc[trc, cols].astype(float), v.y_future_cases_4w.values[trc]), num_boost_round=200)
    T = v.loc[tec, ['district', 'week_start', 'population', 'y_future_cases_4w', 'y_future_inc_4w', 'at_risk_primary']].copy()
    T['pred_cases'] = reg.predict(X.loc[tec, cols].astype(float)); T['pred_inc'] = T.pred_cases / T.population * 1e5
    T['persist_cases'] = v.loc[tec, 'inc_mean4_to_lag0'].fillna(0).values * T.population / 1e5
    onset = BP[BP.fold == f].set_index(['district', 'week_start']).score
    T['onset_risk'] = T.set_index(['district', 'week_start']).index.map(onset).astype(float)
    for k in KS:
        for obj in ['pred_cases', 'pred_inc', 'persist_cases', 'onset_risk']:
            for wk, g in T.groupby('week_start'):
                gg = g.dropna(subset=[obj]); sel = gg.nlargest(k, obj)
                rows.append(dict(fold=f, k=k, objective=obj, week=wk, burden=sel.y_future_cases_4w.sum(), burden_tot=g.y_future_cases_4w.sum(),
                                 inc=sel.y_future_inc_4w.sum(), inc_tot=g.y_future_inc_4w.sum(), sel=set(sel.district)))
R = pd.DataFrame(rows)
summ = R.groupby(['k', 'objective']).apply(lambda g: pd.Series(dict(burden_capture=g.burden.sum() / g.burden_tot.sum(),
                                                               percapita_capture=g.inc.sum() / g.inc_tot.sum()))).reset_index()
ov = []
for k in KS:
    a = R[(R.k == k) & (R.objective == 'pred_cases')].set_index(['fold', 'week']).sel
    b = R[(R.k == k) & (R.objective == 'pred_inc')].set_index(['fold', 'week']).sel
    ov.append(dict(k=k, mean_overlap_count_vs_percapita=float(np.mean([len(a[i] & b[i]) / k for i in a.index]))))
summ.to_csv(OUT / 'dev_H4_objectives.csv', index=False); res['H4_overlap'] = ov
print(summ.round(3).to_string(index=False)); print(ov)
json.dump(res, open(OUT / 'dev_extra_results.json', 'w'), indent=1, default=float)
