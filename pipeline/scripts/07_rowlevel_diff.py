"""Row-level record of every feature value changed between the original model-ready table and Master V2."""
import pandas as pd, numpy as np, pathlib
O = pathlib.Path('outputs')
old = pd.read_csv('data_raw/figshare_model_ready_original.csv', parse_dates=['week_start']).set_index(['district', 'week_start'])
new = pd.read_csv(O / 'master_dataset_v2.csv', parse_dates=['week_start']).set_index(['district', 'week_start'])
pairs = {'cases_lag1': 'cases_lag1', 'cases_lag2': 'cases_lag2', 'cases_lag3': 'cases_lag3', 'cases_lag4': 'cases_lag4',
         'cases_lag8': 'cases_lag8', 'cases_lag12': 'cases_lag12'}
rows = []
pos = new.groupby([new.index.get_level_values(0), new.segment]).cumcount()
for o, n in pairs.items():
    common = new.index.intersection(old.index)          # only district-weeks present in the original table can 'change'
    a, b = old[o].reindex(common), new[n].reindex(common)
    ch = ~((a.isna() & b.isna()) | (np.isclose(a.fillna(-1), b.fillna(-1))))
    ch = pd.Series(ch.values, index=common)
    for idx in common[ch.values]:
        k = int(n.replace('cases_lag', ''))
        reason = 'crosses_2019_2022_gap' if (new.segment[idx] == 'S2022on' and pos[idx] < k) else 'references_QC_excluded_week'
        rows.append({'district': idx[0], 'week_start': idx[1].date(), 'feature': n, 'old_value': a[idx], 'new_value': b[idx], 'reason': reason})
d = pd.DataFrame(rows); d.to_csv(O / 'correction_log_rowlevel_lags.csv', index=False)
print(d.groupby(['feature', 'reason']).size().unstack(fill_value=0))
