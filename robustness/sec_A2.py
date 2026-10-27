from rlib import *
import sys
L = int(sys.argv[1])
WH = wide(pd.concat([P, PH[PH.model == 'ens_hhh4_persist']]), ['persistence', 'main_raw', 'hhh4', 'ens_hhh4_persist'])
WHL = wide(pd.concat([PL, PHL[PHL.model == 'ens_hhh4_persist']]), ['persistence', 'main_raw', 'hhh4', 'ens_hhh4_persist'])
yr = []
for f, ww in list(WH.groupby('fold')) + [('LOCKED2026', WHL)]:
    for j, (a, b) in enumerate([('hhh4', 'persistence'), ('ens_hhh4_persist', 'hhh4'), ('ens_hhh4_persist', 'persistence'), ('main_raw', 'persistence')]):
        d, lo, hi, p = boot_prob(ww, a, b, 'auprc', L, 400 + j)
        yr.append(dict(L=L, year=YEAR[f], a=a, b=b, diff=d, lo=lo, hi=hi, p=p))
YR = pd.DataFrame(yr); YR['p_holm'] = multipletests(YR.p, method='holm')[1]
YR.to_csv(OUT + f'A_year_specific_frozenfamily_L{L}.csv', index=False); print(YR.round(3).to_string(index=False))
