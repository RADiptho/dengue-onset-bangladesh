from rlib import *
WH = wide(pd.concat([P, PH[PH.model == 'ens_hhh4_persist']]), ['persistence', 'main_raw', 'hhh4', 'ens_hhh4_persist'])
WHL = wide(pd.concat([PL, PHL[PHL.model == 'ens_hhh4_persist']]), ['persistence', 'main_raw', 'hhh4', 'ens_hhh4_persist'])
import sys
# E. locked 2026 uncertainty (post hoc)
loc = []
for m in ['persistence', 'main_raw', 'hhh4']:
    for k in [5, 10, 20]:
        x = EL[(EL.model == m) & (EL.k == k)]; n = len(x); s = int(x.hit.sum()); lo, hi = proportion_confint(s, n, method='beta')
        loc.append(dict(model=m, k=k, captured=s, events=n, capture=s / n, cp_lo=lo, cp_hi=hi))
pd.DataFrame(loc).to_csv(OUT + 'E_locked_capture_exact.csv', index=False)

