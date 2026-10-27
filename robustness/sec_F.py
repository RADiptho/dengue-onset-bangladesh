from rlib import *
V['year'] = V.week_start.dt.year; V['masked'] = V.cases_obs.isna(); key = V.set_index(['district', 'week_start'])
WH = wide(pd.concat([P, PH[PH.model == 'ens_hhh4_persist']]), ['persistence', 'main_raw', 'hhh4', 'ens_hhh4_persist'])
WHL = wide(pd.concat([PL, PHL[PHL.model == 'ens_hhh4_persist']]), ['persistence', 'main_raw', 'hhh4', 'ens_hhh4_persist'])
import sys
# F. regime descriptors (where onsets came from)
F_ = []
evs = pd.concat([E[(E.model == 'persistence') & (E.k == 10)][['fold', 'district', 'onset_week']],
                 EL[(EL.model == 'persistence') & (EL.k == 10)][['fold', 'district', 'onset_week']]])
for f, g in evs.groupby('fold'):
    k1 = key.reindex(pd.MultiIndex.from_arrays([g.district, g.onset_week - pd.Timedelta(weeks=1)]))
    own = (k1.cases_obs.values > 0); nb = (k1.nb_n_outbreak_T5_lag0.values >= 1)
    pr = (WHL if f == 'LOCKED2026' else WH[WH.fold == f])
    def ci(x): s = int(np.nansum(x)); n = int(np.isfinite(x.astype(float)).sum()); lo, hi = proportion_confint(s, n, method='wilson'); return s, n, lo, hi
    a = ci(own); b = ci(nb)
    F_.append(dict(year=YEAR[f], eligible_windows=len(pr), positives=int(pr.y.sum()), prevalence=pr.y.mean(), onsets=len(g),
                   own_cases_prev_week=a[0] / a[1], own_lo=a[2], own_hi=a[3], neighbour_outbreak_prev_week=b[0] / b[1], nb_lo=b[2], nb_hi=b[3],
                   median_own_inc_prev_week=np.nanmedian(k1.inc_obs.values)))
pd.DataFrame(F_).to_csv(OUT + 'F_regime_descriptors.csv', index=False)

