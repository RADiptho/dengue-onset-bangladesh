"""Endemic-epidemic negative-binomial model (hhh4 class; Held, Hohle & Hofmann 2005; Meyer & Held 2014),
re-implemented in Python because R/surveillance is unavailable in this environment.
  Y_it ~ NB(mu_it, theta)
  mu_it = lambda_t * Y_i,t-1 + phi * sum_j w_ij Y_j,t-1 + exp(nu_t) * pop_i / 1e5
  log lambda_t = a_l + g_l sin(2 pi w/52.18) + d_l cos(.)       (autoregressive, seasonal)
  log nu_t     = a_n + g_n sin(.) + d_n cos(.)                   (endemic, population offset, seasonal)
  log phi      = a_p                                              (neighbourhood)
  w_ij = o_ij^(-d) / sum_k o_ik^(-d), o = graph order (power-law spatial coupling, hhh4 W_powerlaw-style)
Missing (QC) counts are excluded from the likelihood; neighbour sums use available neighbours with renormalised weights."""
import numpy as np, pandas as pd
from scipy.optimize import minimize
from scipy.special import gammaln
from collections import deque


def graph_order(districts, edges):
    idx = {d: i for i, d in enumerate(districts)}; n = len(districts)
    adj = [[] for _ in range(n)]
    for a, b in edges:
        adj[idx[a]].append(idx[b]); adj[idx[b]].append(idx[a])
    O = np.zeros((n, n))
    for s in range(n):
        dist = [-1] * n; dist[s] = 0; q = deque([s])
        while q:
            u = q.popleft()
            for w in adj[u]:
                if dist[w] < 0:
                    dist[w] = dist[u] + 1; q.append(w)
        O[s] = dist
    assert (O >= 0).all(), 'graph not connected'
    return O


class HHH4:
    def __init__(self, O, pop, norm='target'):
        # norm='target' (frozen protocol): weights into each district sum to 1 (neighbour average)
        # norm='source' (surveillance::W_powerlaw(normalize=TRUE) convention): weights out of each district sum to 1
        self.O, self.pop, self.norm = O, np.asarray(pop, float), norm

    def W(self, d):
        with np.errstate(divide='ignore'):
            M = np.where(self.O > 0, self.O ** (-d), 0.0)
        if self.norm == 'source':
            return (M / M.sum(axis=1, keepdims=True)).T      # W[i, j] = w_ji with sum_i w_ji = 1
        return M / M.sum(axis=1, keepdims=True)

    def _parts(self, p, woy):
        s, c = np.sin(2 * np.pi * woy / 52.18), np.cos(2 * np.pi * woy / 52.18)
        lam = np.exp(p[0] + p[1] * s + p[2] * c)
        nu = np.exp(p[4] + p[5] * s + p[6] * c)
        return lam, np.exp(p[3]), nu, np.exp(p[7]), np.exp(p[8])

    def _mu(self, p, Yprev, woy):
        lam, phi, nu, d, _ = self._parts(p, woy)
        W = self.W(d)
        avail = ~np.isnan(Yprev)
        Yz = np.where(avail, Yprev, 0.0)
        num = Yz @ W.T
        if self.norm == 'source':
            nb = num                                            # no renormalisation (official convention)
        else:
            den = avail.astype(float) @ W.T
            nb = np.where(den > 0, num / np.maximum(den, 1e-12), 0.0)
        return lam[:, None] * Yz + phi * nb + nu[:, None] * self.pop[None, :] / 1e5

    def fit(self, Y, Yprev, woy):
        """Y, Yprev: (T, N) arrays (NaN = missing); woy: (T,) ISO week of Y."""
        ok = ~np.isnan(Y) & ~np.isnan(Yprev)
        y = Y[ok]

        def nll(p):
            mu = self._mu(p, Yprev, woy)[ok]
            th = np.exp(p[8])
            ll = gammaln(y + th) - gammaln(th) - gammaln(y + 1) + th * np.log(th / (th + mu)) + y * np.log(mu / (th + mu) + 1e-300)
            return -ll.sum()
        p0 = np.array([np.log(0.5), 0, 0, np.log(0.05), np.log(0.5), 0, 0, np.log(1.5), 0.0])
        best = None
        for start in [p0, p0 + np.array([0.5, 0, 0, 0.5, -1, 0, 0, 0, 0])]:
            r = minimize(nll, start, method='L-BFGS-B',
                         bounds=[(-8, 2), (-3, 3), (-3, 3), (-12, 2), (-12, 8), (-4, 4), (-4, 4), (np.log(0.05), np.log(10)), (-6, 6)])
            if best is None or r.fun < best.fun:
                best = r
        self.p, self.opt = best.x, best
        return self

    def simulate_onset(self, Y0, woy0, h, thr, S=400, rng=None, skip=0):
        """P(any week t+1..t+h has Y >= thr) per district, from state Y0 (N,), by Monte Carlo (S paths)."""
        rng = rng or np.random.default_rng(0)
        lam_all = lambda w: self._parts(self.p, np.array([w]))
        Y = np.repeat(np.nan_to_num(Y0, nan=0.0)[None, :], S, axis=0)
        hit = np.zeros_like(Y, dtype=bool)
        th = np.exp(self.p[8]); W = self.W(np.exp(self.p[7]))
        for j in range(1, h + skip + 1):
            w = (woy0 + j - 1) % 52 + 1
            lam, phi, nu, _, _ = lam_all(w)
            mu = lam[0] * Y + phi * (Y @ W.T) + nu[0] * self.pop[None, :] / 1e5
            Y = rng.poisson(rng.gamma(th, np.maximum(mu, 1e-12) / th))
            if j > skip:
                hit |= Y >= thr[None, :]
        return hit.mean(axis=0)
