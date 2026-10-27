"""A1 (exploratory): season-specific endemic-epidemic fits; component shares of expected cases; Hessian-based SEs."""
import sys; sys.argv = ['x', 'none']
from posthoc_run import *
from scipy.special import gammaln

def hessian(f, x, eps=1e-4):
    n = len(x); Hm = np.zeros((n, n))
    for i in range(n):
        for j in range(i, n):
            e_i = np.eye(n)[i] * eps; e_j = np.eye(n)[j] * eps
            Hm[i, j] = Hm[j, i] = (f(x + e_i + e_j) - f(x + e_i - e_j) - f(x - e_i + e_j) + f(x - e_i - e_j)) / (4 * eps * eps)
    return Hm
rows = []
for yr in [2019, 2022, 2023, 2024, 2025]:
    keep = (WK.year == yr)
    m = HHH4(O, POP).fit(YV[keep], YP[keep], WOY[keep])
    ok = ~np.isnan(YV[keep]) & ~np.isnan(YP[keep]); y = YV[keep][ok]
    def nll(p):
        mu = m._mu(p, YP[keep], WOY[keep])[ok]; th = np.exp(p[8])
        return -(gammaln(y + th) - gammaln(th) - gammaln(y + 1) + th * np.log(th / (th + mu)) + y * np.log(mu / (th + mu) + 1e-300)).sum()
    try:
        se = np.sqrt(np.diag(np.linalg.inv(hessian(nll, m.p))))
    except np.linalg.LinAlgError:
        se = np.full(9, np.nan)
    lam, phi, nu, d, th = m._parts(m.p, WOY[keep]); Yp = YP[keep]; avail = ~np.isnan(Yp); Yz = np.where(avail, Yp, 0)
    W = m.W(d); den = avail.astype(float) @ W.T; nb = np.where(den > 0, (Yz @ W.T) / np.maximum(den, 1e-12), 0)
    ar_c = (lam[:, None] * Yz)[ok].sum(); ne_c = (phi * nb)[ok].sum(); en_c = (nu[:, None] * POP[None, :] / 1e5 * np.ones_like(Yz))[ok].sum(); tot = ar_c + ne_c + en_c
    rows.append(dict(season=yr, n_obs=int(ok.sum()), cases=int(y.sum()), share_endemic=en_c / tot, share_within=ar_c / tot, share_between=ne_c / tot,
                     mean_lambda=float(lam.mean()), max_lambda=float(lam.max()), phi=float(phi), phi_se_log=se[3], decay_d=float(d), d_se_log=se[7],
                     theta=float(th), converged=bool(m.opt.success)))
D = pd.DataFrame(rows); D.to_csv(PH / 'decomposition_by_season.csv', index=False)
pd.set_option('display.width', 220); print(D.round(3).to_string(index=False))
