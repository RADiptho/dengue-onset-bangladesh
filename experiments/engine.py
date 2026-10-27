"""Modelling engine. All learning uses training-role rows of the given fold only (frozen folds, h-week embargo)."""
import numpy as np, pandas as pd, lightgbm as lgb, warnings
from sklearn.linear_model import LogisticRegression
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import average_precision_score, log_loss
from common import *
from hhh4py import HHH4, graph_order
warnings.filterwarnings('ignore')

INNER_VAL_START = {'F2023': pd.Timestamp('2022-07-04'), 'F2024': pd.Timestamp('2023-01-02'),
                   'F2025': pd.Timestamp('2024-01-01'), 'LOCKED2026': pd.Timestamp('2024-12-30')}
GRID = [dict(num_leaves=7, min_child_samples=20), dict(num_leaves=7, min_child_samples=60),
        dict(num_leaves=15, min_child_samples=20), dict(num_leaves=15, min_child_samples=60)]
DEFAULT_CFG = dict(num_leaves=7, min_child_samples=60)
BASE = dict(objective='binary', learning_rate=0.05, feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1,
            lambda_l2=1.0, verbose=-1, num_threads=1, deterministic=True, seed=20261025, force_col_wise=True)


def split(v, roles, at_risk, y):
    r = roles.reindex(pd.MultiIndex.from_frame(v[['district', 'week_start']])).values
    tr = (r == 'train') & (at_risk.values == 1) & y.notna().values
    te = (r == 'test') & (at_risk.values == 1)                 # all at-risk test rows are ranked; y may be missing
    return tr, te


def add_anomalies(v, test_start):
    X = v.copy()
    clim = X[X.week_start < test_start].groupby(['district', 'iso_week'])[ANOM_SRC].mean()
    j = X[['district', 'iso_week']].join(clim, on=['district', 'iso_week'])
    for c in ANOM_SRC:
        X[c + '_anom'] = X[c] - j[c].values
    return X


def feature_list(groups, extra=()):
    cols = [c for g in groups for c in GROUPS[g]]
    if 'climate' in groups:
        cols += [c + '_anom' for c in ANOM_SRC]
    return cols + list(extra)


# ------------------------------------------------------------------ baselines
def logistic_on(score, tr, te, y):
    s = np.log1p(np.nan_to_num(score, nan=0.0).clip(min=0)).reshape(-1, 1)
    m = LogisticRegression(C=1e6, max_iter=1000).fit(s[tr], y[tr])
    return m.predict_proba(s[te])[:, 1]


def persistence_score(v):
    return v.inc_mean4_to_lag0.fillna(v.inc_lag0).fillna(0.0).values


def baseline_preds(v, tr, te, y):
    yv = y.values
    out = {}
    out['persistence'] = (persistence_score(v)[te], logistic_on(persistence_score(v), tr, te, yv))
    nb = v.nb_inc_max_lag0.fillna(0.0).values
    out['neighbour_only'] = (nb[te], logistic_on(nb, tr, te, yv))
    # seasonal climatology: training onset rate by district x ISO week, shrunk to the pooled ISO-week rate (+-1 week)
    T = pd.DataFrame({'d': v.district.values[tr], 'w': v.iso_week.values[tr], 'y': yv[tr]})
    pw = {w: T[T.w.isin([(w - 2) % 53 + 1, w, w % 53 + 1])].y.mean() for w in range(1, 54)}
    gm = T.y.mean()
    dw = T.groupby(['d', 'w']).y.agg(['sum', 'count'])
    m_ = 5.0
    def clim(d, w):
        p0 = pw.get(w, gm); p0 = gm if np.isnan(p0) else p0
        if (d, w) in dw.index:
            s_, n_ = dw.loc[(d, w)]; return (s_ + m_ * p0) / (n_ + m_)
        return p0
    cp = np.array([clim(d, w) for d, w in zip(v.district.values[te], v.iso_week.values[te])])
    out['seasonal_climatology'] = (cp, cp)
    # endemic-only: district effects + seasonality, no epidemic terms
    D = pd.get_dummies(v.district).values.astype(float)
    Xe = np.column_stack([D, v.woy_sin.values, v.woy_cos.values])
    lr = LogisticRegression(C=1.0, max_iter=2000).fit(Xe[tr], yv[tr])
    pe = lr.predict_proba(Xe[te])[:, 1]
    out['endemic_only'] = (pe, pe)
    return out


# ------------------------------------------------------------------ hhh4-type endemic-epidemic model
_O = None
def hhh4_fit(v, test_start):
    global _O
    dist = sorted(v.district.unique())
    if _O is None:
        e = pd.read_csv(PKG / 'data_raw/edges_static.csv'); e = e[e.adjacency == 1]
        ids = pd.read_csv(PKG / 'data_raw/districts.csv').set_index('district_id').district
        _O = graph_order(dist, list(zip(e.source_id.map(ids), e.target_id.map(ids))))
    pop = v.groupby('district').population.first()[dist].values
    Y = v.pivot(index='week_start', columns='district', values='cases_obs')[dist]
    seg = v.drop_duplicates('week_start').set_index('week_start').segment.reindex(Y.index)
    woy = v.drop_duplicates('week_start').set_index('week_start').iso_week.reindex(Y.index).values
    Yp = Y.groupby(seg).shift(1)
    keep = (Y.index < test_start)
    m = HHH4(_O, pop).fit(Y.values[keep], Yp.values[keep], woy[keep])
    return m, Y, seg, woy, dist, pop


def hhh4_preds(v, te, h, model_bundle, thr_by_district, S=400, delay=0):
    m, Y, seg, woy, dist, pop = model_bundle
    Yf = Y.groupby(seg).ffill(limit=4)                      # start state: last observed count within 4 weeks (QC gaps)
    rows = v.loc[te, ['district', 'week_start']]
    out = pd.Series(np.nan, index=rows.index)
    thr = np.array([thr_by_district[d] for d in dist])
    rng = np.random.default_rng(7)
    for wk, g in rows.groupby('week_start'):
        i = Y.index.get_loc(wk) - delay
        P = m.simulate_onset(Yf.values[i], woy[i], h, thr, S=S, rng=rng, skip=delay)
        pmap = dict(zip(dist, P))
        out.loc[g.index] = g.district.map(pmap).values
    return out.values


# ------------------------------------------------------------------ LightGBM main model
def lgb_fit(X, y, cfg, n_iter=None, Xv=None, yv=None):
    params = {**BASE, **cfg}
    dtr = lgb.Dataset(X, y, free_raw_data=False)
    if Xv is not None:
        dv = lgb.Dataset(Xv, yv, reference=dtr)
        b = lgb.train(params, dtr, num_boost_round=400, valid_sets=[dv], callbacks=[lgb.early_stopping(50, verbose=False)])
        return b, b.best_iteration
    b = lgb.train(params, dtr, num_boost_round=n_iter)
    return b, n_iter


def main_model(v, fold, tr, te, y, cols, return_model=False):
    ivs = INNER_VAL_START[fold]
    yv = y.values
    ws = v.week_start
    # inner split inside the training role: inner-train windows end before inner-val start
    inner_tr = tr & (ws.values < ivs)
    inner_va = tr & (ws.values >= ivs)
    X = v[cols].astype(float)
    info = dict(inner_train_n=int(inner_tr.sum()), inner_val_n=int(inner_va.sum()), inner_val_pos=int(np.nansum(yv[inner_va])))
    best = None
    if info['inner_val_pos'] >= 5 and np.nansum(yv[inner_tr]) >= 5:
        for cfg in GRID:
            b, it = lgb_fit(X[inner_tr], yv[inner_tr], cfg, Xv=X[inner_va], yv=yv[inner_va])
            p = b.predict(X[inner_va], num_iteration=it)
            ll = log_loss(yv[inner_va], np.clip(p, 1e-6, 1 - 1e-6))
            if best is None or ll < best[0]:
                best = (ll, cfg, it, p)
        cfg, it, pin = best[1], max(best[2], 20), best[3]
    else:
        cfg, it = DEFAULT_CFG, 150
        b, _ = lgb_fit(X[inner_tr], yv[inner_tr], cfg, n_iter=it) if np.nansum(yv[inner_tr]) >= 1 else (None, None)
        pin = b.predict(X[inner_va]) if b is not None and inner_va.any() else None
    info.update(cfg=str(cfg), n_iter=int(it))
    final, _ = lgb_fit(X[tr], yv[tr], cfg, n_iter=it)
    raw = final.predict(X[te])
    cal = {'raw': raw}
    if pin is not None and np.nansum(yv[inner_va]) >= 2 and (1 - yv[inner_va]).sum() >= 2:
        lp = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6))).reshape(-1, 1)
        pl = LogisticRegression(C=1e6, max_iter=1000).fit(lp(pin), yv[inner_va])
        cal['platt'] = pl.predict_proba(lp(raw))[:, 1]
        iso = IsotonicRegression(out_of_bounds='clip', y_min=1e-4, y_max=1 - 1e-4).fit(pin, yv[inner_va])
        cal['isotonic'] = iso.predict(raw)
    else:
        cal['platt'] = raw; cal['isotonic'] = raw; info['calibration_note'] = 'inner validation too small; raw used'
    if return_model:
        return cal, info, final
    return cal, info


# ------------------------------------------------------------------ metrics (pre-registered, as in fold_utils)
def prob_metrics(p, y):
    m = ~np.isnan(y) & ~np.isnan(p)
    p, y = p[m], y[m]
    out = dict(n=int(m.sum()), positives=int(y.sum()))
    if y.sum() == 0 or y.sum() == len(y):
        return out
    out['auprc'] = average_precision_score(y, p)
    out['brier'] = float(np.mean((p - y) ** 2))
    out['prevalence'] = float(y.mean())
    out['oe_ratio'] = float(y.sum() / max(p.sum(), 1e-9))
    lp = np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
    try:
        import statsmodels.api as sm
        f = sm.GLM(y, sm.add_constant(lp), family=sm.families.Binomial()).fit()
        out['cal_intercept'], out['cal_slope'] = float(f.params[0]), float(f.params[1])
    except Exception:
        pass
    return out


def rank_table(rows, score):
    """rows: DataFrame (district, week_start) of at-risk test rows; returns ranks within week (1 = highest)."""
    r = rows[['district', 'week_start']].copy()
    rng = np.random.default_rng(11)
    r['s'] = np.asarray(score, float) + rng.uniform(0, 1e-9, len(r))       # deterministic tie-break
    r['rank'] = r.groupby('week_start').s.rank(ascending=False, method='first')
    r['n_at_risk'] = r.groupby('week_start').s.transform('size')
    return r


def evaluable_events(events, test_weeks, h):
    """Onset events whose immediately preceding issue week (w-1) is a test issue week of this fold/horizon."""
    tw = set(test_weeks)
    return events[(events.onset_week - pd.Timedelta(weeks=1)).isin(tw)].reset_index(drop=True)


def event_capture(ranked, events, k, window):
    hits, lead = [], []
    R = ranked.set_index(['district', 'week_start'])
    for _, o in events.iterrows():
        best = None
        for j in range(window, 0, -1):                          # earliest flag first -> lead time
            key = (o.district, o.onset_week - pd.Timedelta(weeks=j))
            if key in R.index and R.loc[key, 'rank'] <= k:
                best = j; break
        hits.append(best is not None); lead.append(best if best else 0)
    return np.array(hits), np.array(lead)


def random_floor_events(ranked, events, k, window):
    R = ranked.set_index(['district', 'week_start'])
    probs = []
    for _, o in events.iterrows():
        miss = 1.0
        for j in range(1, window + 1):
            key = (o.district, o.onset_week - pd.Timedelta(weeks=j))
            if key in R.index:
                miss *= max(0.0, 1 - k / R.loc[key, 'n_at_risk'])
        probs.append(1 - miss)
    return np.array(probs)
