from rlib import *
V['year'] = V.week_start.dt.year; V['masked'] = V.cases_obs.isna(); key = V.set_index(['district', 'week_start'])
WH = wide(pd.concat([P, PH[PH.model == 'ens_hhh4_persist']]), ['persistence', 'main_raw', 'hhh4', 'ens_hhh4_persist'])
WHL = wide(pd.concat([PL, PHL[PHL.model == 'ens_hhh4_persist']]), ['persistence', 'main_raw', 'hhh4', 'ens_hhh4_persist'])
import sys
# G. hhh4 starting counts: issue weeks in which any district count was masked (neighbour start imputed)
mw = set(V[V.masked].week_start)
gs = []
for f, ww in list(WH.groupby('fold')) + [('LOCKED2026', WHL)]:
    s = ww[~ww.week_start.isin(mw)]
    gs.append(dict(year=YEAR[f], weeks_with_masked_start=int(ww.week_start.isin(mw).groupby(ww.week_start).first().sum()), rows_kept=len(s),
                   positives_kept=int(s.y.sum()), auprc_hhh4=AP(s.y, s.hhh4), auprc_pers=AP(s.y, s.persistence)))
pd.DataFrame(gs).to_csv(OUT + 'G_hhh4_start_counts.csv', index=False)
print('ALL DONE')
