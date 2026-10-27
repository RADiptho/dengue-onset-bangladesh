from rlib import *
import sys
# A. dependence-aware inference (pooled development, h = 4), same families as the frozen tests
wbf = {f: sorted(P[P.fold == f].week_start.unique()) for f in ['F2023', 'F2024', 'F2025']}
comps = [('main_isotonic', b) for b in ['persistence', 'seasonal_climatology', 'endemic_only', 'neighbour_only', 'hhh4']] + [('hhh4', 'persistence')]
allm = sorted(set(sum(([a, b] for a, b in comps), [])) | {'main_raw'})
W = wide(P, allm)
rows = []
for L in [int(sys.argv[1])]:
    for i, (a, b) in enumerate(comps):
        for k in [5, 10, 20]:
            d, lo, hi, p, n = boot_cap(E, a, b, k, wbf, L, 100 + i)
            rows.append(dict(L=L, a=a, b=b, metric=f'capture@{k}', diff=d, lo=lo, hi=hi, p=p))
        a2 = 'main_raw' if a == 'main_isotonic' else a
        d, lo, hi, p = boot_prob(W, a2, b, 'auprc', L, 200 + i); rows.append(dict(L=L, a=a2, b=b, metric='auprc', diff=d, lo=lo, hi=hi, p=p))
        d, lo, hi, p = boot_prob(W, a, b, 'brier', L, 300 + i); rows.append(dict(L=L, a=a, b=b, metric='brier', diff=d, lo=lo, hi=hi, p=p))
    print('A done L', L, flush=True)
A = pd.DataFrame(rows); A['family'] = A.metric.str.split('@').str[0]
A['p_holm'] = A.groupby(['L', 'family']).p.transform(lambda s: multipletests(s, method='holm')[1])
A.to_csv(OUT + f'A_block_bootstrap_pooled_L{sys.argv[1]}.csv', index=False)

# year-specific AUPRC (16 tests, Holm across 16), original week bootstrap (L=1) and blocks of 4 and 8 weeks
WH = wide(pd.concat([P, PH[PH.model == 'ens_hhh4_persist']]), ['persistence', 'main_raw', 'hhh4', 'ens_hhh4_persist'])
WHL = wide(pd.concat([PL, PHL[PHL.model == 'ens_hhh4_persist']]), ['persistence', 'main_raw', 'hhh4', 'ens_hhh4_persist'])
yr = []
for L in [int(sys.argv[1])]:
    for f, ww in list(WH.groupby('fold')) + [('LOCKED2026', WHL)]:
        for j, (a, b) in enumerate([('hhh4', 'persistence'), ('main_raw', 'persistence'), ('ens_hhh4_persist', 'persistence'), ('hhh4', 'main_raw')]):
            d, lo, hi, p = boot_prob(ww, a, b, 'auprc', L, 400 + j)
            yr.append(dict(L=L, year=YEAR[f], a=a, b=b, diff=d, lo=lo, hi=hi, p=p))
YR = pd.DataFrame(yr); YR['p_holm'] = YR.groupby('L').p.transform(lambda s: multipletests(s, method='holm')[1])
YR.to_csv(OUT + f'A_year_specific_block_L{sys.argv[1]}.csv', index=False); print('A year done', flush=True)

