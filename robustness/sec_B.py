from rlib import *
import sys
# B. operational early warning (frozen rankings; persistence, LightGBM, hhh4)
def operational(p, e, model, k):
    r = ranked(p, model); r = r.sort_values(['district', 'week_start'])
    sel = r[r['rank'] <= k].copy(); R = r.set_index(['district', 'week_start'])
    ev = e[(e.model == model) & (e.k == k)]
    lead = ev.lead.values; cap = ev.hit.values.astype(bool)
    # single weekly decision at a fixed lag j (no repeated chances) and its random floor
    single = {}
    for j in range(1, 5):
        h_, fl = [], []
        for _, o in ev.iterrows():
            key = (o.district, o.onset_week - pd.Timedelta(weeks=j))
            if key in R.index: h_.append(R.loc[key, 'rank'] <= k); fl.append(min(1.0, k / R.loc[key, 'n_at_risk']))
            else: h_.append(False); fl.append(0.0)
        single[j] = (np.mean(h_), np.mean(fl))
    # random floor of the any-of-4 rule (Equation 19)
    fl4 = []
    for _, o in ev.iterrows():
        miss = 1.0
        for j in range(1, 5):
            key = (o.district, o.onset_week - pd.Timedelta(weeks=j))
            if key in R.index: miss *= max(0.0, 1 - k / R.loc[key, 'n_at_risk'])
        fl4.append(1 - miss)
    # alert episodes: first selection after a week not selected
    sel['prev'] = sel.groupby('district').week_start.shift(1)
    first = sel[(sel.prev.isna()) | ((sel.week_start - sel.prev) != pd.Timedelta(weeks=1))]
    fo = first[first.y.notna()]
    return dict(model=model, k=k, events=len(ev), capture=cap.mean(), capture_lead2=(lead >= 2).mean(), capture_lead3=(lead >= 3).mean(),
                missed=(~cap).sum(), mean_lead=lead[cap].mean() if cap.any() else np.nan, median_lead=np.median(lead[cap]) if cap.any() else np.nan,
                floor_any4=np.mean(fl4), single_lag1=single[1][0], single_lag1_floor=single[1][1], single_lag4=single[4][0], single_lag4_floor=single[4][1],
                alerts=len(sel), alerts_per_captured_onset=len(sel) / max(cap.sum(), 1), first_alerts=len(first),
                first_alert_precision=fo.y.mean(), window_precision=sel.y.dropna().mean(), prevalence=r.y.dropna().mean())
ops = []
for fold in ['F2023', 'F2024', 'F2025', 'POOLED', 'LOCKED2026']:
    for m in ['persistence', 'main_raw', 'hhh4']:
        for k in [5, 10, 20]:
            if fold == 'LOCKED2026': d = operational(PL, EL, m, k)
            elif fold == 'POOLED': d = operational(P, E, m, k)
            else: d = operational(P[P.fold == fold], E[E.fold == fold], m, k)
            d['period'] = fold; ops.append(d)
OPS = pd.DataFrame(ops); OPS.to_csv(OUT + 'B_operational.csv', index=False); print('B done', flush=True)

