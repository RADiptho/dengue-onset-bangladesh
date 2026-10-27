"""B1: coupling robustness. M0 frozen form; M1 adds week-specific endemic intercepts + district endemic covariate.
Cluster-robust (week-clustered sandwich) SEs. Same-mask data in every season."""
import os as _os
def _repo_root():
    d = _os.path.dirname(_os.path.abspath(__file__))
    while not _os.path.exists(_os.path.join(d, '.repo_root')):
        parent = _os.path.dirname(d)
        if parent == d: raise RuntimeError('repository root (.repo_root) not found')
        d = parent
    return d + '/'
ROOT = _repo_root()

import sys; sys.path.insert(0, ROOT + 'posthoc'); sys.path.insert(0, ROOT + 'experiments'); sys.argv = ['x', 'none']
from posthoc_run import YV, YP, WOY, WK, O, POP, DIST, v
import numpy as np, pandas as pd
from scipy.optimize import minimize
from scipy.special import gammaln
from scipy.stats import norm
k22 = WK.year == 2022
MI = [i for i in range(64) if np.isnan(YV[k22][:, i]).mean() > 0.5]
dens = np.log(v.groupby('district').pop_density.first()[DIST].values); dens = (dens - dens.mean()) / dens.std()
def W(d):
    with np.errstate(divide='ignore'): M = np.where(O > 0, O ** (-d), 0.0)
    return M / M.sum(axis=1, keepdims=True)
def season(yr):
    k = WK.year == yr; Y = YV[k].copy(); Yp = YP[k].copy(); Y[:, MI] = np.nan; Yp[:, MI] = np.nan
    return Y, Yp, WOY[k]
def obs_ll(p, Y, Yp, woy, model):
    T = len(woy); s, c = np.sin(2*np.pi*woy/52.18)[:, None], np.cos(2*np.pi*woy/52.18)[:, None]
    lam = np.exp(p[0] + p[1]*s + p[2]*c); phi = np.exp(p[3]); d = np.exp(p[4]); th = np.exp(p[5])
    if model == 'M0': nu = np.exp(p[6] + p[7]*s + p[8]*c) * np.ones((1, 64))
    else: nu = np.exp(p[7:7+T][:, None] + p[6]*dens[None, :])
    av = ~np.isnan(Yp); Yz = np.where(av, Yp, 0); Wm = W(d); den = av.astype(float) @ Wm.T
    nb = np.where(den > 0, (Yz @ Wm.T) / np.maximum(den, 1e-12), 0)
    mu = lam*Yz + phi*nb + nu*POP[None, :]/1e5
    ok = ~np.isnan(Y) & av; y = np.where(ok, Y, 0)
    ll = gammaln(y+th) - gammaln(th) - gammaln(y+1) + th*np.log(th/(th+mu)) + y*np.log(mu/(th+mu) + 1e-300)
    return np.where(ok, ll, 0.0)
def fit(yr, model):
    Y, Yp, woy = season(yr); T = len(woy)
    p0 = [np.log(0.5), 0, 0, np.log(0.05), np.log(1.5), 0.0] + ([np.log(0.5), 0, 0] if model == 'M0' else [0.0] + [np.log(0.3)]*T)
    bnd = [(-8, 2), (-3, 3), (-3, 3), (-12, 2), (np.log(0.05), np.log(10)), (-6, 6)] + ([(-12, 8), (-4, 4), (-4, 4)] if model == 'M0' else [(-3, 3)] + [(-15, 8)]*T)
    f = lambda p: -obs_ll(p, Y, Yp, woy, model).sum()
    r = minimize(f, np.array(p0, float), method='L-BFGS-B', bounds=bnd, options={'maxiter': 3000, 'maxfun': 200000})
    p = r.x; n = len(p); eps = 1e-4
    # week-cluster scores
    S = np.zeros((T, n))
    for j in range(n):
        e = np.zeros(n); e[j] = eps
        S[:, j] = (obs_ll(p+e, Y, Yp, woy, model).sum(1) - obs_ll(p-e, Y, Yp, woy, model).sum(1)) / (2*eps)
    # Hessian from finite differences of the total score
    g = lambda q: np.array([(f(q + np.eye(n)[j]*eps) - f(q - np.eye(n)[j]*eps)) / (2*eps) for j in range(n)])
    Hm = np.zeros((n, n))
    for j in range(n):
        e = np.zeros(n); e[j] = 1e-3; Hm[:, j] = (g(p+e) - g(p-e)) / 2e-3
    Hm = (Hm + Hm.T) / 2; Hi = np.linalg.pinv(Hm)
    V_model = Hi; V_rob = Hi @ (S.T @ S) * T/(T-1) @ Hi
    return dict(season=yr, model=model, phi=np.exp(p[3]), d=np.exp(p[4]), se_model=np.sqrt(V_model[3, 3]), se_robust=np.sqrt(V_rob[3, 3]),
                converged=bool(r.success), nll=r.fun, n_par=n)
rows = [fit(yr, m) for m in ['M0', 'M1'] for yr in [2022, 2023, 2024, 2025]]
R = pd.DataFrame(rows); print(R.round(4).to_string(index=False))
cmp = []
for m in ['M0', 'M1']:
    base = R[(R.model == m) & (R.season == 2022)].iloc[0]
    for yr in [2023, 2024, 2025]:
        r = R[(R.model == m) & (R.season == yr)].iloc[0]
        for se in ['se_model', 'se_robust']:
            s = np.hypot(r[se], base[se]); lr = np.log(r.phi / base.phi)
            cmp.append(dict(model=m, contrast=f'{yr} vs 2022', se_type=se, ratio=np.exp(lr), lo=np.exp(lr - 1.96*s), hi=np.exp(lr + 1.96*s), p=2*norm.sf(abs(lr/s))))
C = pd.DataFrame(cmp); print(C.round(4).to_string(index=False))
R.to_csv(ROOT + 'audit/output/b1_season_fits.csv', index=False); C.to_csv(ROOT + 'audit/output/b1_coupling_contrasts.csv', index=False)
