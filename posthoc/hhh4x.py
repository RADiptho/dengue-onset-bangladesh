"""POST-HOC: endemic-epidemic NB model with covariates in all three components (hhh4 class, target-normalised power law,
frozen missing-data handling). Parameters: AR [a, sin, cos, betas_ar], NE [a, betas_ne], END [a, sin, cos, betas_end], log d, log theta."""
import os as _os
def _repo_root():
    d = _os.path.dirname(_os.path.abspath(__file__))
    while not _os.path.exists(_os.path.join(d, '.repo_root')):
        parent = _os.path.dirname(d)
        if parent == d: raise RuntimeError('repository root (.repo_root) not found')
        d = parent
    return d + '/'
ROOT = _repo_root()

import numpy as np
from scipy.optimize import minimize
from scipy.special import gammaln
import sys; sys.path.insert(0, ROOT + 'experiments')
from hhh4py import HHH4


class HHH4X(HHH4):
    def __init__(self, O, pop, Xar, Xne, Xend):
        """Xar, Xend: (T, N, k) covariates aligned with the predicted week; Xne: (T, N, k)."""
        super().__init__(O, pop, norm='target')
        self.Xar, self.Xne, self.Xend = Xar, Xne, Xend
        self.ka, self.kn, self.ke = Xar.shape[2], Xne.shape[2], Xend.shape[2]

    def unpack(self, p):
        i = 0; ar = p[i:i + 3 + self.ka]; i += 3 + self.ka
        ne = p[i:i + 1 + self.kn]; i += 1 + self.kn
        en = p[i:i + 3 + self.ke]; i += 3 + self.ke
        return ar, ne, en, np.exp(p[i]), np.exp(p[i + 1])

    def comps(self, p, woy, rows):
        ar, ne, en, d, th = self.unpack(p)
        s, c = np.sin(2 * np.pi * woy / 52.18)[:, None], np.cos(2 * np.pi * woy / 52.18)[:, None]
        lam = np.exp(ar[0] + ar[1] * s + ar[2] * c + self.Xar[rows] @ ar[3:])
        phi = np.exp(ne[0] + self.Xne[rows] @ ne[1:])
        nu = np.exp(en[0] + en[1] * s + en[2] * c + self.Xend[rows] @ en[3:])
        return lam, phi, nu, d, th

    def mu_rows(self, p, Yprev, woy, rows):
        lam, phi, nu, d, _ = self.comps(p, woy, rows)
        W = self.W(d); avail = ~np.isnan(Yprev); Yz = np.where(avail, Yprev, 0.0)
        den = avail.astype(float) @ W.T
        nb = np.where(den > 0, (Yz @ W.T) / np.maximum(den, 1e-12), 0.0)
        return lam * Yz + phi * nb + nu * self.pop[None, :] / 1e5

    def fit(self, Y, Yprev, woy, rows):
        ok = ~np.isnan(Y) & ~np.isnan(Yprev); y = Y[ok]
        def nll(p):
            mu = self.mu_rows(p, Yprev, woy, rows)[ok]; th = np.exp(p[-1])
            return -(gammaln(y + th) - gammaln(th) - gammaln(y + 1) + th * np.log(th / (th + mu)) + y * np.log(mu / (th + mu) + 1e-300)).sum()
        p0 = np.concatenate([[np.log(0.5), 0, 0], np.zeros(self.ka), [np.log(0.05)], np.zeros(self.kn),
                             [np.log(0.5), 0, 0], np.zeros(self.ke), [np.log(1.5), 0.0]])
        bounds = ([(-8, 2), (-3, 3), (-3, 3)] + [(-3, 3)] * self.ka + [(-12, 2)] + [(-3, 3)] * self.kn +
                  [(-12, 8), (-4, 4), (-4, 4)] + [(-5, 5)] * self.ke + [(np.log(0.05), np.log(10)), (-6, 6)])
        self.opt = minimize(nll, p0, method='L-BFGS-B', bounds=bounds); self.p = self.opt.x
        return self

    def simulate_onset_x(self, Y0, woy0, row_next, h, thr, S=400, rng=None):
        """Covariates for all future steps held at their values for week t+1 (known at the issue week)."""
        rng = rng or np.random.default_rng(0)
        ar, ne, en, d, th = self.unpack(self.p); W = self.W(d)
        Y = np.repeat(np.nan_to_num(Y0, nan=0.0)[None, :], S, axis=0); hit = np.zeros_like(Y, dtype=bool)
        xa, xn, xe = self.Xar[row_next], self.Xne[row_next], self.Xend[row_next]
        for j in range(1, h + 1):
            w = (woy0 + j - 1) % 52 + 1; s, c = np.sin(2 * np.pi * w / 52.18), np.cos(2 * np.pi * w / 52.18)
            lam = np.exp(ar[0] + ar[1] * s + ar[2] * c + xa @ ar[3:]); phi = np.exp(ne[0] + xn @ ne[1:])
            nu = np.exp(en[0] + en[1] * s + en[2] * c + xe @ en[3:])
            mu = lam * Y + phi * (Y @ W.T) + nu * self.pop[None, :] / 1e5
            Y = rng.poisson(rng.gamma(th, np.maximum(mu, 1e-12) / th)); hit |= Y >= thr[None, :]
        return hit.mean(axis=0)
