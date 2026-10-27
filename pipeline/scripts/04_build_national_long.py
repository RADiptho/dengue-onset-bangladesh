"""Long national monthly dengue layer for the historical-prior ablation (offline).
2008-01..2021-12: OpenDengue v1.3 (CC BY 4.0; Clarke et al. 2024, doi:10.1038/s41597-024-03120-7).
  Correction: August 2019 = 52,636 (OpenDengue 56,236 is a digit transposition; with it 2019 sums to 104,954,
  whereas the official DGHS 2019 total is 101,354).
2022-01..latest: aggregated from the district panel (raw new_cases; weeks assigned to the month of their Thursday,
  ISO convention). Months touched by known year-boundary or date-shift QC weeks are flagged.
Never used to create district values."""
import pandas as pd, numpy as np, pathlib
R = pathlib.Path('data_raw'); O = pathlib.Path('outputs')
od = pd.read_csv(R / 'opendengue_v1_3_bangladesh_rows.csv')
m = od[od.T_res == 'Month'].copy(); m['month'] = pd.to_datetime(m.calendar_start_date).dt.to_period('M')
m = m[m.month <= pd.Period('2021-12', 'M')][['month', 'dengue_total', 'UUID']].rename(columns={'dengue_total': 'cases', 'UUID': 'source'})
m['flag'] = ''
m.loc[m.month == pd.Period('2019-08', 'M'), ['cases', 'flag']] = [52636, 'corrected_digit_transposition_from_56236']
m.loc[m.source.str.startswith('WHO'), 'flag'] = 'WHO_block_monthly_allocation_may_differ_from_DGHS_daily'
p = pd.read_csv(R / 'figshare_district_week_master_audit.csv', parse_dates=['week_start'])
p = p[p.year >= 2022]
p['month'] = (p.week_start + pd.Timedelta(days=3)).dt.to_period('M')
nm = p.groupby('month').agg(cases=('new_cases', 'sum'), qc=('primary_target_usable', lambda s: int((s == 0).any()))).reset_index()
nm['source'] = 'figshare_33040637_district_panel_aggregated'
nm['flag'] = np.where(nm.qc == 1, 'month_contains_QC_flagged_weeks', '')
out = pd.concat([m, nm.drop(columns='qc')], ignore_index=True).sort_values('month')
out['month'] = out.month.astype(str)
full = pd.period_range('2008-01', out.month.max(), freq='M').astype(str)
missing = sorted(set(full) - set(out.month))
out.to_csv(O / 'national_monthly_long_2008_2026.csv', index=False)
ann = out.assign(y=out.month.str[:4]).groupby('y').cases.sum()
print('months', len(out), 'missing months', missing); print(ann.to_string())
