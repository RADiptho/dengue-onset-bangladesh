"""Data dictionary, missingness, feature-availability table and frozen event counts (offline)."""
import json, numpy as np, pandas as pd, pathlib
O = pathlib.Path('outputs')
v = pd.read_csv(O / 'master_dataset_v2.csv', parse_dates=['week_start'])
man = json.load(open(O / 'build_manifest.json'))
lab = pd.read_csv(O / 'labels_all_definitions_long.csv.gz', parse_dates=['week_start'])
folds = pd.read_csv(O / 'frozen_folds_long.csv.gz', parse_dates=['week_start'])

def meta(c):
    if c in man['keys']: return 'identifier', 'n/a', 'panel'
    if c in man['qc']: return 'outcome/QC', 'n/a', 'DGHS via Figshare 33040637'
    if c.startswith(('cases_lag', 'inc_lag', 'inc_mean', 'log_inc')): return 'feature: own history', 'week t (lag0) or earlier; DGHS daily releases', 'DGHS'
    if c.startswith(('nb_', 'gravity_')): return 'feature: spatial', 'week t or t-1 of other districts', 'DGHS + adjacency/centroids + WorldPop'
    if c.startswith(('national_inc', 'dhaka_inc')): return 'feature: national/Dhaka signal', 'week t or t-1', 'DGHS'
    if c.startswith('clim_'): return 'feature: climate', 'lag >= 1 week', man['climate_source']
    if c.startswith('dev_chirps'): return 'ablation only (development)', 'lag >= 3 weeks', 'CHIRPS (package)'
    if c.startswith('dev_viirs'): return 'ablation only (development)', 'lag >= 5 weeks', 'VIIRS (package)'
    if c.startswith('dev_'): return 'ablation only (development)', 'lag >= 2 weeks', 'Sentinel-2/MODIS (package)'
    if c.startswith(('festival', 'woy_')): return 'feature: calendar', 'known in advance', 'official holiday calendar'
    if c.startswith('rep_'): return 'sensitivity covariate: reporting structure', 'static (2026 structure)', 'DGHS press-release layout'
    if c in ['log_population', 'pop_density', 'river_density', 'road_density']: return 'feature: static', 'static', 'WorldPop/OSM/HydroSHEDS (package)'
    if c.startswith(('y_', 'ob_', 'at_risk', 'hotspot', 'locked')): return 'label/outcome (never a feature)', 'future weeks t+1..t+h' if c.startswith('y_') else 'week t', 'derived'
    return 'other', '', ''
dd = pd.DataFrame([dict(column=c, dtype=str(v[c].dtype), role=meta(c)[0], available_at_issue=meta(c)[1], source=meta(c)[2],
                        missing_n=int(v[c].isna().sum()), missing_pct=round(v[c].isna().mean() * 100, 2)) for c in v.columns])
dd.to_csv(O / 'data_dictionary_v2.csv', index=False)
miss = v.groupby(v.week_start.dt.year)[man['features']].apply(lambda g: g.isna().mean().round(3)).T
miss.to_csv(O / 'missingness_by_year_v2.csv')
avail = dd[dd.role.str.startswith(('feature', 'ablation', 'sensitivity'))][['column', 'role', 'available_at_issue', 'source']]
avail.to_csv(O / 'feature_availability_table.csv', index=False)
# event counts per fold role, definition and horizon
L = lab.merge(folds, on=['district', 'week_start', 'h'])
L = L[(L.at_risk == 1) & L.y_onset.notna() & (L.role != 'excluded')]
ec = L.groupby(['fold', 'role', 'T', 'quiet_weeks', 'h']).agg(at_risk_district_weeks=('y_onset', 'size'), onset_windows=('y_onset', 'sum'),
                                                          issue_weeks=('week_start', 'nunique')).reset_index()
ec['positive_rate'] = (ec.onset_windows / ec.at_risk_district_weeks).round(4)
ec.to_csv(O / 'event_counts_frozen.csv', index=False)
# distinct onset events (district, first outbreak week after quiet) under the primary definition
v = v.sort_values(['district', 'week_start'])
g = v.groupby(['district', 'segment'])
prev4 = pd.concat([g.ob_T5.shift(k) for k in range(1, 5)], axis=1)
v['onset_event'] = ((v.ob_T5 == 1) & (prev4 == 0).all(axis=1) & prev4.notna().all(axis=1)).astype(int)
oe = v.groupby(v.week_start.dt.year).onset_event.sum()
oe.to_csv(O / 'distinct_onset_events_primary_by_year.csv')
print(ec[(ec['T'] == 5) & (ec.quiet_weeks == 4) & (ec.role == 'test')].to_string(index=False)); print(oe.to_string())
