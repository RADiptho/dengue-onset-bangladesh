"""Pre-writing outputs: (1) neighbour-pressure robustness (re-run of Stage-B code, saved to file), (2) final hotspot analysis."""
import os as _os
def _repo_root():
    d = _os.path.dirname(_os.path.abspath(__file__))
    while not _os.path.exists(_os.path.join(d, '.repo_root')):
        parent = _os.path.dirname(d)
        if parent == d: raise RuntimeError('repository root (.repo_root) not found')
        d = parent
    return d + '/'
ROOT = _repo_root()

import numpy as np, pandas as pd, geopandas as gpd, json
from sklearn.metrics import roc_auc_score
from esda.moran import Moran, Moran_Local
from libpysal.weights import W
from statsmodels.stats.multitest import multipletests
F = ROOT; P = F + 'pipeline/'; O = F + 'descriptive/output/'
v = pd.read_csv(P + 'outputs/master_dataset_v2.csv', parse_dates=['week_start'])
# ---------------- (1) neighbour-pressure robustness: identical code and seed to the Stage-B console run
Pd = pd.read_csv(F + 'posthoc/posthoc_dev_predictions.csv.gz', parse_dates=['week_start'], low_memory=False)
L = pd.read_csv(F + 'posthoc/posthoc_locked_predictions_ALL.csv.gz', parse_dates=['week_start'], low_memory=False)
def prep(Pq):
    Wd = Pq[Pq.model.isin(['hhh4', 'persistence']) & Pq.y.notna()].pivot_table(index=['fold', 'district', 'week_start', 'y'], columns='model', values='prob').reset_index()
    return Wd.merge(v[['district', 'week_start', 'nb_inc_max_lag0']], on=['district', 'week_start'])
eps = 0.5 / 400; ll = lambda p, y: y * np.log(np.clip(p, eps, 1 - eps)) + (1 - y) * np.log(np.clip(1 - p, eps, 1 - eps))
D = prep(Pd); D['d'] = ll(D.hhh4, D.y) - ll(D.persistence, D.y)
x = np.log1p(D.nb_inc_max_lag0.fillna(0)); mu, sd = x.mean(), x.std(); D['z'] = (x - mu) / sd
rng = np.random.default_rng(9)
def slope_ci(S, scaled=False):
    F_ = pd.get_dummies(S.fold).values.astype(float); X = np.column_stack([S.z.values, F_])
    cl = (S.fold + S.week_start.astype(str)).values; uc = np.unique(cl); idx = {c: np.where(cl == c)[0] for c in uc}
    b = lambda ix: np.linalg.lstsq(X[ix], (S.d.values[ix] / (S.y.values[ix].mean()) if scaled else S.d.values[ix]), rcond=None)[0][0]
    bs = np.array([b(np.concatenate([idx[c] for c in rng.choice(uc, len(uc))])) for _ in range(2000)])
    return b(np.arange(len(S))), np.percentile(bs, 2.5), np.percentile(bs, 97.5)
rows = []
for name, S, sc in [('development, all folds', D, False), ('development, excluding 2023', D[D.fold != 'F2023'], False), ('development, prevalence-scaled outcome', D, True)]:
    s, lo, hi = slope_ci(S, sc); rows.append(dict(analysis=name, slope=s, lo=lo, hi=hi, n_rows=len(S), positives=int(S.y.sum())))
Lk = prep(L); Lk['d'] = ll(Lk.hhh4, Lk.y) - ll(Lk.persistence, Lk.y); Lk['z'] = (np.log1p(Lk.nb_inc_max_lag0.fillna(0)) - mu) / sd
X = np.column_stack([Lk.z, np.ones(len(Lk))]); b = np.linalg.lstsq(X, Lk.d, rcond=None)[0][0]
cl = Lk.week_start.astype(str).values; uc = np.unique(cl); idx = {c: np.where(cl == c)[0] for c in uc}
bs = [np.linalg.lstsq(X[ix], Lk.d.values[ix], rcond=None)[0][0] for ix in [np.concatenate([idx[c] for c in rng.choice(uc, len(uc))]) for _ in range(2000)]]
rows.append(dict(analysis='locked 2026 (descriptive)', slope=b, lo=np.percentile(bs, 2.5), hi=np.percentile(bs, 97.5), n_rows=len(Lk), positives=int(Lk.y.sum())))
D['tert'] = pd.qcut(D.z, 3, labels=['low', 'mid', 'high'])
for t, g in D.groupby('tert', observed=True):
    rows.append(dict(analysis=f'AUROC tertile {t}: hhh4 / persistence', slope=roc_auc_score(g.y, g.hhh4) if g.y.sum() >= 5 else np.nan,
                     lo=roc_auc_score(g.y, g.persistence) if g.y.sum() >= 5 else np.nan, hi=np.nan, n_rows=len(g), positives=int(g.y.sum())))
R1 = pd.DataFrame(rows); R1.to_csv(O + 'neighbour_pressure_robustness.csv', index=False); print(R1.round(4).to_string(index=False))
# ---------------- (2) hotspot analysis
full = v[v.week_start.dt.year.isin([2022, 2023, 2024, 2025])].copy(); full['season'] = full.week_start.dt.year
dist = sorted(v.district.unique())
ann = (full.groupby('district').inc_obs.mean() * 52.18)[dist]
seas = (full.groupby(['district', 'season']).inc_obs.mean() * 52.18).unstack()[[2022, 2023, 2024, 2025]].reindex(dist)
obs_seasons = seas.notna().sum(axis=1)
topq = pd.DataFrame({s: seas[s].rank(ascending=False) <= 13 for s in seas.columns}).where(seas.notna(), False).sum(axis=1)
ob = np.where(v.cases_obs.isna(), np.nan, ((v.inc_obs >= 5) & (v.cases_obs >= 10)).astype(float)); v['ob'] = ob
v = v.sort_values(['district', 'week_start']); g = v.groupby(['district', 'segment']).ob
prev = pd.concat([g.shift(k) for k in range(1, 5)], axis=1)
v['onset'] = (v.ob == 1) & (prev == 0).all(axis=1) & prev.notna().all(axis=1)
on = v.groupby('district').onset.sum().reindex(dist).astype(int); arw = v.groupby('district').at_risk_primary.sum().reindex(dist)
assert on.sum() == 115, on.sum()
e = pd.read_csv(P + 'data_raw/edges_static.csv'); e = e[e.adjacency == 1]; ids = pd.read_csv(P + 'data_raw/districts.csv').set_index('district_id').district
def wfrom(pairs):
    nb = {d: [] for d in dist}
    for a, b in pairs:
        if b not in nb[a]: nb[a].append(b)
        if a not in nb[b]: nb[b].append(a)
    w = W(nb, id_order=dist); w.transform = 'r'; return w
w_model = wfrom(zip(e.source_id.map(ids), e.target_id.map(ids)))
adjc = pd.read_csv(F + 'data/lookup/adjacency_check_panel_vs_OCHA.csv'); w_ocha = wfrom([tuple(p.split('|')) for p in adjc[adjc.in_ocha_contiguity].pair])
y = np.log1p(ann.values); quad = {1: 'High-high', 2: 'Low-high', 3: 'Low-low', 4: 'High-low'}
def lisa(w):
    gm = Moran(y, w, permutations=9999); lm = Moran_Local(y, w, permutations=9999, seed=20261025)
    q = multipletests(lm.p_sim, method='fdr_bh')[1]
    return gm, lm, q, np.array([quad[lm.q[i]] if q[i] < 0.05 else 'Not significant' for i in range(len(dist))])
np.random.seed(20261025); gm, lm, q, cls = lisa(w_model); np.random.seed(20261025); gm2, lm2, q2, cls2 = lisa(w_ocha)
H = pd.DataFrame({'district': dist, 'annualised_incidence_2022_2025': ann.values, 'observed_full_seasons': obs_seasons.values,
                  'seasons_in_top_quintile': topq.values, 'recurrent_high_incidence': (topq >= 3).values,
                  'onset_events': on.values, 'at_risk_weeks': arw.values, 'onsets_per_100_at_risk_weeks': (on / arw * 100).values,
                  'lisa_I': lm.Is, 'lisa_p_perm': lm.p_sim, 'lisa_q_fdr': q, 'lisa_class': cls, 'lisa_class_ocha_contiguity': cls2})
for s in seas.columns: H[f'incidence_{s}'] = seas[s].values
H.to_csv(O + 'district_hotspots_final.csv', index=False)
json.dump({'global_moran_I': gm.I, 'p_perm': gm.p_sim, 'permutations': 9999, 'weights': 'modelling adjacency, row-standardised',
           'global_moran_I_ocha_contiguity': gm2.I, 'p_perm_ocha': gm2.p_sim,
           'lisa_agreement_model_vs_ocha': float((cls == cls2).mean())}, open(O + 'global_moran.json', 'w'), indent=1)
print(f'Global Moran I {gm.I:.3f} (p {gm.p_sim}); OCHA contiguity {gm2.I:.3f} (p {gm2.p_sim}); LISA class agreement {(cls == cls2).mean():.3f}')
print(H.sort_values('annualised_incidence_2022_2025', ascending=False).head(10)[['district', 'annualised_incidence_2022_2025', 'seasons_in_top_quintile', 'onset_events', 'lisa_class']].round(1).to_string(index=False))
for c in ['High-high', 'Low-low', 'High-low', 'Low-high']: print(c, H[H.lisa_class == c].district.tolist())
print('recurrent:', H[H.recurrent_high_incidence].district.tolist()); print('zero onsets:', int((H.onset_events == 0).sum()))
print('changed vs OCHA weights:', H[H.lisa_class != H.lisa_class_ocha_contiguity][['district', 'lisa_class', 'lisa_class_ocha_contiguity']].to_string(index=False))
