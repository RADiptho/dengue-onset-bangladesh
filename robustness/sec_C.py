from rlib import *
WH = wide(pd.concat([P, PH[PH.model == 'ens_hhh4_persist']]), ['persistence', 'main_raw', 'hhh4', 'ens_hhh4_persist'])
WHL = wide(pd.concat([PL, PHL[PHL.model == 'ens_hhh4_persist']]), ['persistence', 'main_raw', 'hhh4', 'ens_hhh4_persist'])
import sys
# C. masking: inventory, eligibility effects and evaluation-subset sensitivity
V['year'] = V.week_start.dt.year; V['masked'] = V.cases_obs.isna()
inv = V[V.masked].assign(cat=V.qc_issue.str.split(';').str[0]).groupby(['cat', 'year']).size().unstack(fill_value=0)
inv.to_csv(OUT + 'C_mask_inventory_category_year.csv')
bydist = V[V.masked].groupby('district').size().sort_values(ascending=False); bydist.to_csv(OUT + 'C_mask_by_district.csv')
V = V.sort_values(['district', 'week_start'])
def near(flag, back, fwd):
    g = flag.groupby(V.district); out = pd.Series(False, index=V.index)
    for s in range(-fwd, back + 1):
        if s != 0: out |= g.shift(s).fillna(False).astype(bool)
    return out | flag
V['mask_near'] = near(V.masked, 4, 4)
V['flag2023'] = V.qc_issue.fillna('').str.startswith('2023_district_total')
V['flag2023_near'] = near(V.flag2023, 4, 4)
CHAT = ['Bandarban', 'Brahmanbaria', 'Chandpur', 'Chattogram', "Cox's Bazar", 'Cumilla', 'Feni', 'Khagrachhari', 'Lakshmipur', 'Noakhali', 'Rangamati']
key = V.set_index(['district', 'week_start'])
elig = []
for yv in [2023, 2024, 2025, 2026]:
    s = V[V.year == yv]
    elig.append(dict(year=yv, masked=int(s.masked.sum()), district_weeks=len(s), within4_of_mask=int(s.mask_near.sum())))
pd.DataFrame(elig).to_csv(OUT + 'C_mask_eligibility.csv', index=False)
def subset(w, rule):
    k = key.reindex(pd.MultiIndex.from_frame(w[['district', 'week_start']]))
    if rule == 'exclude_near_mask': keep = ~k.mask_near.values
    elif rule == 'exclude_near_mask_and_2023_flags': keep = ~(k.mask_near.values | k.flag2023_near.values)
    elif rule == 'exclude_chattogram_division': keep = ~w.district.isin(CHAT).values
    return w[keep]
sens = []
for rule in ['exclude_near_mask', 'exclude_near_mask_and_2023_flags', 'exclude_chattogram_division']:
    for f, ww in list(WH.groupby('fold')) + [('LOCKED2026', WHL)]:
        s = subset(ww, rule)
        d, lo, hi, p = boot_prob(s, 'hhh4', 'persistence', 'auprc', 4, 500)
        sens.append(dict(rule=rule, year=YEAR[f], rows=len(s), positives=int(s.y.sum()), auprc_hhh4=AP(s.y, s.hhh4), auprc_pers=AP(s.y, s.persistence),
                         auprc_lgbm=AP(s.y, s.main_raw), diff_hhh4_pers=d, lo=lo, hi=hi, p=p))
pd.DataFrame(sens).to_csv(OUT + 'C_mask_sensitivity.csv', index=False); print('C done', flush=True)

