"""Frozen helpers for the modelling stage. Anything that learns from data takes a training mask and uses only
those rows, so fold-specific quantities can never see test or locked data.
Metric definitions here are pre-registered: do not change after modelling starts."""
import numpy as np, pandas as pd


def climatology_anomalies(df, train_mask, cols, by='iso_week'):
    """Anomaly = value minus the training-period mean for the same district and ISO week."""
    clim = df[train_mask].groupby(['district', by])[cols].mean()
    j = df[['district', by]].join(clim, on=['district', by])
    return pd.DataFrame({f'{c}_anom': df[c].values - j[c].values for c in cols}, index=df.index)


def district_quantile_threshold(df, train_mask, q=0.90, min_inc=1.0):
    """Sensitivity definition only: district-specific incidence threshold from training weeks."""
    t = df[train_mask].groupby('district').inc_obs.quantile(q).clip(lower=min_inc)
    return df.district.map(t)


def national_seasonal_prior(national_long, before_year):
    """Mean share of annual cases by calendar month, from complete years strictly before `before_year`."""
    n = national_long.copy(); n['y'] = n.month.str[:4].astype(int); n['m'] = n.month.str[5:7].astype(int)
    n = n[n.y < before_year]
    full = n.groupby('y').m.nunique(); n = n[n.y.isin(full[full == 12].index)]
    share = n.groupby('y').apply(lambda g: g.set_index('m').cases / max(g.cases.sum(), 1))
    return share.groupby(level='m').mean()


# ------------------------------------------------------------------ decision-support metrics (retrospective)
def capture_at_k(scores, y, week, k):
    """Onset Capture@k: share of onset events (y==1 among at-risk districts) that fall inside the k highest-scored
    at-risk districts of the same issue week. Pooled over weeks (events weighted equally)."""
    d = pd.DataFrame({'s': scores, 'y': y, 'w': week}).dropna()
    d['rank'] = d.groupby('w').s.rank(ascending=False, method='first')
    sel = d['rank'] <= k
    return float(d.loc[sel, 'y'].sum() / max(d.y.sum(), 1)), int(d.y.sum())


def alerts_per_capture(scores, y, week, k):
    d = pd.DataFrame({'s': scores, 'y': y, 'w': week}).dropna()
    d['rank'] = d.groupby('w').s.rank(ascending=False, method='first')
    sel = d[d['rank'] <= k]
    return float(len(sel) / max(sel.y.sum(), 1))


def random_floor(y, week, k):
    """Expected Capture@k under random selection among at-risk districts of each week."""
    d = pd.DataFrame({'y': y, 'w': week}).dropna()
    n = d.groupby('w').y.transform('size')
    return float((d.y * np.minimum(k / n, 1)).sum() / max(d.y.sum(), 1))


def clairvoyant_ceiling(y, week, k):
    d = pd.DataFrame({'y': y, 'w': week}).dropna()
    per = d.groupby('w').y.sum().clip(upper=k)
    return float(per.sum() / max(d.y.sum(), 1))


def lead_time_weeks(df_scores, onsets, k):
    """For each onset (district, onset week), weeks between the first issue week at which the district entered the
    top-k (while at risk, within the 8 weeks before onset) and the onset week; 0 if never flagged."""
    out = []
    for _, o in onsets.iterrows():
        g = df_scores[(df_scores.district == o.district) & (df_scores.week_start < o.onset_week) &
                      (df_scores.week_start >= o.onset_week - pd.Timedelta(weeks=8))]
        flagged = g[g['rank'] <= k]
        out.append(0 if flagged.empty else int((o.onset_week - flagged.week_start.min()).days // 7))
    return np.array(out)


def brier(p, y):
    m = ~(np.isnan(p) | np.isnan(y)); return float(np.mean((p[m] - y[m]) ** 2))


def calibration_slope_intercept(p, y):
    """Logistic recalibration of logit(p): returns (intercept, slope). Ideal (0, 1)."""
    import statsmodels.api as sm
    m = ~(np.isnan(p) | np.isnan(y)); lp = np.log(np.clip(p[m], 1e-6, 1 - 1e-6) / (1 - np.clip(p[m], 1e-6, 1 - 1e-6)))
    fit = sm.GLM(y[m], sm.add_constant(lp), family=sm.families.Binomial()).fit()
    return float(fit.params[0]), float(fit.params[1])


def week_block_bootstrap(stat_fn, df, n=2000, seed=0):
    """Resample whole issue weeks with replacement (preserves within-week dependence across districts)."""
    rng = np.random.default_rng(seed); weeks = df.week_start.unique(); vals = []
    for _ in range(n):
        w = rng.choice(weeks, len(weeks), replace=True)
        vals.append(stat_fn(pd.concat([df[df.week_start == x] for x in w])))
    return np.percentile(vals, [2.5, 97.5])


def event_capture_at_k(ranked, onsets, k, window=4):
    """PRIMARY decision metric (pre-registered). Event-level Onset Capture@k with >= 1 week lead:
    an onset event (district d, onset week w) is captured if d was among the k highest-ranked at-risk districts
    in at least one issue week w-window .. w-1 (issue week = week whose data are complete at issue time).
    `ranked` has columns district, week_start, rank (rank among that week's at-risk districts)."""
    hits = []
    for _, o in onsets.iterrows():
        g = ranked[(ranked.district == o.district) & (ranked.week_start < o.onset_week) &
                   (ranked.week_start >= o.onset_week - pd.Timedelta(weeks=window))]
        hits.append(int((g['rank'] <= k).any()))
    return float(np.mean(hits)) if hits else float('nan'), len(hits)
