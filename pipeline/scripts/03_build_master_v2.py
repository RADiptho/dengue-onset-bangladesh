"""Build Master Dataset V2 (offline). Deterministic; no randomness.

Inputs (data_raw/):
  figshare_district_week_master_audit.csv   original panel + QC flags (Figshare 33040637 derivative, CC BY 4.0)
  edges_static.csv, districts.csv            adjacency and centroids (same Figshare deposit)
  holiday_calendar.csv                       official holiday dates (festival windows rebuilt by one rule)
  reporting_structure_dghs_2026.csv          DGHS reporting-table structure (sensitivity covariate)
  dghs_district_week_2026_extension.csv      OPTIONAL, from script 01 (locked-test extension)
  nasa_power_daily.csv                       OPTIONAL, from script 02 (uniform climate for all years)

Forecast-issue convention: the issue moment is the Monday after ISO week t ends. Cases for week t are known
(DGHS daily releases). Targets concern weeks t+1 ... t+h.
"""
import json, os, warnings, numpy as np, pandas as pd, pathlib
warnings.simplefilter('ignore')

R = pathlib.Path(os.environ.get('DENGUE_RAW', 'data_raw')); O = pathlib.Path(os.environ.get('DENGUE_OUT', 'outputs')); O.mkdir(parents=True, exist_ok=True)
log = []                                   # correction log entries
def note(kind, n, detail): log.append({'correction': kind, 'rows_affected': int(n), 'detail': detail})

THRESH = [2, 5, 10]; QUIET = [4, 6, 8]; H = [1, 2, 4, 6, 8]; MINCASES = 10
PRIMARY = dict(T=5, q=4)
BANNED = ['new_deaths', 'currently_admitted', 'cumulative_cases', 'cumulative_deaths', 'incidence', 'eligible',
          'ignition', 'upstream_pressure', 'nbr_cases', 'eligible_loose', 'naive', 'ignition_loose',
          'gtrends_dengue', 'gtrends_dengue_nat', 'gtrends_dengue_bn_nat', 'gtrends_fever_bn_nat', 'ndvi_filled',
          'upstream_pressure_lag1', 'upstream_pressure_lag2', 'nbr_cases_lag1', 'nbr_cases_lag2',
          'rain_lag2', 'rain_lag3', 'rain_lag4', 'temp_mean_lag2', 'temp_mean_lag3', 'temp_mean_lag4',
          'humidity_lag2', 'humidity_lag3', 'humidity_lag4', 'viirs_change', 'festival_window', 'festival_influx']

# ---------------------------------------------------------------- 1. load and append extension
a = pd.read_csv(R / 'figshare_district_week_master_audit.csv', parse_dates=['week_start'])
dist = pd.read_csv(R / 'districts.csv')
static_cols = ['district_id', 'division', 'population', 'pop_density', 'river_density', 'road_density']
static = a.groupby('district')[static_cols].first()
# festival influx profile (per-district constant during festival windows in the original data)
infl = a[a.festival_influx != 0].groupby('district').festival_influx.agg(lambda s: s.round(6).mode().iloc[0])
a['source'] = 'figshare_33040637'
ext_path = R / 'dghs_district_week_2026_extension.csv'
if ext_path.exists():
    e = pd.read_csv(ext_path, parse_dates=['week_start'])
    e = e[e.week_start > a.week_start.max()].copy()
    e = e.join(static, on='district')
    e['year'] = e.week_start.dt.isocalendar().year.astype(int); e['iso_week'] = e.week_start.dt.isocalendar().week.astype(int)
    e['qc_issue'] = e.qc_issue.fillna(''); e['primary_target_usable'] = (e.qc_issue == '').astype(int)
    e['sensitivity_only'] = 1 - e.primary_target_usable; e['source'] = 'dghs_press_release_extension'
    a = pd.concat([a, e], ignore_index=True)
    note('locked_extension_appended', len(e), f'{e.week_start.min().date()} to {e.week_start.max().date()}')
EXTENSION = ext_path.exists()
a = a.sort_values(['district', 'week_start']).reset_index(drop=True)
assert not a.duplicated(['district', 'week_start']).any()

# ---------------------------------------------------------------- 2. segments
a['segment'] = np.where(a.week_start.dt.year == 2019, 'S2019', 'S2022on')
for s, g in a.groupby(['district', 'segment']):
    d = g.week_start.diff().dt.days.dropna()
    assert (d == 7).all(), f'non-contiguous weeks inside segment {s}'
note('segment_assignment', len(a), 'S2019 = 2019-08-26..2019-12-30; S2022on = 2022-01-03 onward; no feature crosses segments')

# ---------------------------------------------------------------- 3. QC masking of the outcome
a['cases_obs'] = a.new_cases.where(a.primary_target_usable == 1)
note('qc_target_masked', (a.primary_target_usable == 0).sum(),
     'cases set to missing before any lag/rolling/label construction (year-boundary resets, first 2019 week, Nov-2025 shift, 2022 Chattogram allocation; locked extension: negative cumulative differences and missing releases)')
if 'source' in a and (a.source == 'dghs_press_release_extension').any():
    ex = a[(a.source == 'dghs_press_release_extension') & (a.primary_target_usable == 0)]
    for _, r in ex.iterrows():
        note('extension_qc_masked', 1, f"{r.district} week {r.week_start.date()}: {r.qc_issue} (raw value {r.new_cases}); masked, not corrected or redistributed")
a['inc_obs'] = a.cases_obs / a.population * 1e5
G = a.groupby(['district', 'segment'], sort=False)

def lag(col, k): return G[col].shift(k)
def roll(col, w, how='mean', shift=0):
    s = G[col].shift(shift) if shift else a[col]
    return s.groupby([a.district, a.segment]).transform(lambda x: getattr(x.rolling(w, min_periods=w), how)())

# ---------------------------------------------------------------- 4. own epidemic history (known at issue)
F = {}
for k in [0, 1, 2, 3, 4, 8, 12]:
    F[f'cases_lag{k}'] = a.cases_obs if k == 0 else lag('cases_obs', k)
    F[f'inc_lag{k}'] = a.inc_obs if k == 0 else lag('inc_obs', k)
for w in [4, 8, 12]:
    F[f'inc_mean{w}_to_lag0'] = roll('inc_obs', w)
F['log_inc_growth_1w'] = np.log1p(F['inc_lag0']) - np.log1p(F['inc_lag1'])
F['log_inc_growth_4w'] = np.log1p(F['inc_lag0']) - np.log1p(F['inc_lag4'])
for c, v in F.items(): a[c] = v
old = pd.read_csv(R / 'figshare_district_week_master_audit.csv', parse_dates=['week_start'])
bad_cross = ((a.week_start >= '2022-01-03') & (a.week_start <= '2022-03-21')).sum()
note('lag_segment_fix', bad_cross, 'case/rolling lags in Jan-Mar 2022 now missing instead of taken from Aug-Dec 2019')

# ---------------------------------------------------------------- 5. outbreak flags (observed weeks only)
for T in THRESH:
    a[f'ob_T{T}'] = np.where(a.cases_obs.isna(), np.nan, ((a.inc_obs >= T) & (a.cases_obs >= MINCASES)).astype(float))

# ---------------------------------------------------------------- 6. spatial: adjacency and gravity proxy
ed = pd.read_csv(R / 'edges_static.csv'); ed = ed[ed.adjacency == 1]
id2d = dist.set_index('district_id').district
ed['s'] = ed.source_id.map(id2d); ed['t'] = ed.target_id.map(id2d)
nbrs = ed.groupby('t').s.apply(lambda x: sorted(set(x))).to_dict()
assert set(nbrs) == set(a.district), 'every district must have at least one neighbour'
pinc = a.pivot(index='week_start', columns='district', values='inc_obs')
pob = a.pivot(index='week_start', columns='district', values='ob_T5')
seg = a.drop_duplicates('week_start').set_index('week_start').segment
def nb_stat(P, f):
    return pd.DataFrame({d: f(P[nbrs[d]]) for d in P.columns})
S = {'nb_inc_mean_lag0': nb_stat(pinc, lambda x: x.mean(axis=1)),
     'nb_inc_max_lag0': nb_stat(pinc, lambda x: x.max(axis=1)),
     'nb_n_outbreak_T5_lag0': nb_stat(pob, lambda x: x.sum(axis=1, min_count=1))}
# gravity weights: population_j / distance_ij^2 (static, from centroids and WorldPop population)
lat = dist.set_index('district').lat; lon = dist.set_index('district').lon; pop = static.population
D = pd.DataFrame(index=pinc.columns, columns=pinc.columns, dtype=float)
for i in pinc.columns:
    dlat = np.radians(lat[pinc.columns] - lat[i]); dlon = np.radians(lon[pinc.columns] - lon[i])
    h = np.sin(dlat / 2) ** 2 + np.cos(np.radians(lat[i])) * np.cos(np.radians(lat[pinc.columns])) * np.sin(dlon / 2) ** 2
    D.loc[i] = 6371 * 2 * np.arcsin(np.sqrt(h))
W = (pop[pinc.columns].values[None, :] / np.where(D.values == 0, np.inf, D.values) ** 2)
W = W / W.sum(axis=1, keepdims=True)
gv = np.nan_to_num(pinc.values) @ W.T
avail = (~pinc.isna()).values @ W.T
S['gravity_inc_lag0'] = pd.DataFrame(np.where(avail > 0.5, gv / np.maximum(avail, 1e-9), np.nan), index=pinc.index, columns=pinc.columns)
pd.DataFrame(W, index=pinc.columns, columns=pinc.columns).to_csv(O / 'gravity_weights_matrix.csv')
nat = a.groupby('week_start').apply(lambda g: g.cases_obs.sum(min_count=1) / g.population[g.cases_obs.notna()].sum() * 1e5)
S['national_inc_lag0'] = pd.DataFrame({d: nat for d in pinc.columns})
S['dhaka_inc_lag0'] = pd.DataFrame({d: pinc['Dhaka'] for d in pinc.columns})
for name, M in S.items():
    lag1 = M.groupby(seg).shift(1)
    for nm, MM in [(name, M), (name.replace('lag0', 'lag1'), lag1)]:
        MM = MM.copy(); MM.index.name = 'week_start'; MM.columns.name = None
        a = a.merge(MM.reset_index().melt(id_vars='week_start', var_name='district', value_name=nm),
                    on=['week_start', 'district'], how='left')
note('spatial_rebuilt', len(a), 'neighbour and gravity features rebuilt from QC-masked incidence of week t and t-1 within segment; original nbr_cases/upstream_pressure fields dropped')

# ---------------------------------------------------------------- 7. climate with availability lags
a = a.sort_values(['district', 'week_start']).reset_index(drop=True)
G = a.groupby(['district', 'segment'], sort=False)
pw = R / 'nasa_power_daily.csv'
if pw.exists():
    c = pd.read_csv(pw, parse_dates=['date'])
    c['week_start'] = c.date - pd.to_timedelta(c.date.dt.weekday, unit='D')
    wk = c.groupby(['district', 'week_start']).agg(t2m=('t2m', 'mean'), t2m_max=('t2m_max', 'mean'),
                                                   t2m_min=('t2m_min', 'mean'), rh2m=('rh2m', 'mean'),
                                                   precip=('precip', 'sum'), ndays=('t2m', 'count')).reset_index()
    wk.loc[wk.ndays < 7, ['t2m', 't2m_max', 't2m_min', 'rh2m', 'precip']] = np.nan
    wk = wk.sort_values(['district', 'week_start'])
    gw = wk.groupby('district')
    cl = wk[['district', 'week_start']].copy()
    for v in ['t2m', 't2m_max', 't2m_min', 'rh2m', 'precip']:      # continuous calendar: climate is not the target
        cl[f'clim_{v}_lag1'] = gw[v].shift(1)
        cl[f'clim_{v}_mean4_lag1'] = gw[v].transform(lambda x: x.shift(1).rolling(4, min_periods=4).mean())
    cl['clim_precip_sum8_lag1'] = gw['precip'].transform(lambda x: x.shift(1).rolling(8, min_periods=8).sum())
    a = a.merge(cl, on=['district', 'week_start'], how='left'); CLIM_SOURCE = 'nasa_power_refetch_centroid'
else:
    m = {'temp_mean': 't2m', 'temp_max': 't2m_max', 'temp_min': 't2m_min', 'humidity': 'rh2m', 'precip_power': 'precip'}
    for src, v in m.items():
        a[f'clim_{v}_lag1'] = G[src].shift(1)
        a[f'clim_{v}_mean4_lag1'] = G[src].transform(lambda x: x.shift(1).rolling(4, min_periods=4).mean())
    a['clim_precip_sum8_lag1'] = G['precip_power'].transform(lambda x: x.shift(1).rolling(8, min_periods=8).sum())
    CLIM_SOURCE = 'package_nasa_power_columns_segment_bounded'
note('climate_availability_lag', len(a), f'climate source = {CLIM_SOURCE}; lag >= 1 week; 4-week means over t-1..t-4')
# development-only environmental ablation layers (cannot be extended to the locked test with the same pipeline)
a['dev_chirps_rain_sum4_lag3'] = G['rain'].transform(lambda x: x.shift(3).rolling(4, min_periods=4).sum())
for v, L in [('ndvi', 2), ('ndwi', 2), ('lst', 2), ('viirs', 5)]:
    a[f'dev_{v}_lag{L}'] = G[v].shift(L)
note('satellite_availability_lag', len(a), 'CHIRPS lag 3 (final-product latency); NDVI/NDWI/LST lag 2; VIIRS lag 5; development-only ablation')

# ---------------------------------------------------------------- 8. calendar (known in advance) and static
hol = pd.read_csv(R / 'holiday_calendar.csv', parse_dates=['date'])
hol_ws = (hol.date - pd.to_timedelta(hol.date.dt.weekday, unit='D'))
fest_weeks = set()
for w in hol_ws:
    fest_weeks |= {w - pd.Timedelta(days=7), w, w + pd.Timedelta(days=7)}
a['festival_window_t'] = a.week_start.isin(fest_weeks).astype(int)
for h in [4, 8]:
    a[f'festival_in_next{h}w'] = sum(a.week_start.add(pd.Timedelta(days=7 * j)).isin(fest_weeks).astype(int) for j in range(1, h + 1)).clip(upper=1)
a['festival_influx_t'] = a.festival_window_t * a.district.map(infl).fillna(0.0)
orig = a.get('festival_window', a.festival_window_t)
chg = (orig.notna() & (a.festival_window_t != orig)).sum()
note('festival_calendar_rebuilt', chg, 'one rule for all years: week before, week containing, week after each Eid ul-Fitr, Eid ul-Adha and Durga Puja; corrects 2019 Durga Puja (1 week coded originally)')
a['woy_sin'] = np.sin(2 * np.pi * a.iso_week / 52.18); a['woy_cos'] = np.cos(2 * np.pi * a.iso_week / 52.18)
a['log_population'] = np.log(a.population)
rep = pd.read_csv(R / 'reporting_structure_dghs_2026.csv').set_index('district')
a['rep_mch_row'] = a.district.map(rep.dghs_separate_mch_row).fillna(0).astype(int)
a['rep_dhaka_metro_list'] = a.district.map(rep.dghs_dhaka_metro_hospital_list).fillna(0).astype(int)

# ---------------------------------------------------------------- 9. labels
a = a.sort_values(['district', 'week_start']).reset_index(drop=True)
G = a.groupby(['district', 'segment'], sort=False)
lab_rows = []
for T in THRESH:
    ob = f'ob_T{T}'
    fut = {j: G[ob].shift(-j) for j in range(1, 9)}
    for q in QUIET:
        past = pd.concat([G[ob].shift(k) for k in range(q)], axis=1)
        at_risk = ((past == 0).all(axis=1) & past.notna().all(axis=1)).astype(int)
        for h in H:
            fw = pd.concat([fut[j] for j in range(1, h + 1)], axis=1)
            pos = (fw == 1).any(axis=1)
            neg = (fw == 0).all(axis=1) & fw.notna().all(axis=1)
            y = np.where(pos, 1.0, np.where(neg, 0.0, np.nan))
            y = np.where(at_risk == 1, y, np.nan)
            lab_rows.append(pd.DataFrame({'district': a.district, 'week_start': a.week_start, 'T': T, 'quiet_weeks': q,
                                          'h': h, 'at_risk': at_risk, 'y_onset': y}))
            if T == PRIMARY['T'] and q == PRIMARY['q']:
                a[f'y_onset_h{h}'] = y
        if T == PRIMARY['T'] and q == PRIMARY['q']:
            a['at_risk_primary'] = at_risk
labels = pd.concat(lab_rows, ignore_index=True)
fc = pd.concat([G['cases_obs'].shift(-j) for j in range(1, 5)], axis=1)
a['y_future_cases_4w'] = fc.sum(axis=1).where(fc.notna().all(axis=1))
a['y_future_inc_4w'] = a.y_future_cases_4w / a.population * 1e5
# hotspot emergence (secondary): above T5 and in the national top decile of incidence that week
a['hotspot'] = np.where(a.ob_T5.isna(), np.nan, ((a.ob_T5 == 1) & (a.inc_obs >= a.groupby('week_start').inc_obs.transform(lambda s: s.quantile(0.9)))).astype(float))
G = a.groupby(['district', 'segment'], sort=False)
hp = pd.concat([G['hotspot'].shift(k) for k in range(8)], axis=1)
hf = pd.concat([G['hotspot'].shift(-j) for j in range(1, 5)], axis=1)
not_hot = (hp == 0).all(axis=1) & hp.notna().all(axis=1)
a['y_hotspot_emergence_h4'] = np.where(not_hot, np.where((hf == 1).any(axis=1), 1.0, np.where((hf == 0).all(axis=1) & hf.notna().all(axis=1), 0.0, np.nan)), np.nan)

# ---------------------------------------------------------------- 10. frozen folds (issue-week based, with label embargo)
FOLDS = [('F2023', '2023-01-02', '2024-01-01'), ('F2024', '2024-01-01', '2024-12-30'),
         ('F2025', '2024-12-30', '2026-01-05'), ('LOCKED2026', '2026-01-05', '2027-01-04')]
fold_rows = []
for name, ts, te in FOLDS:
    ts, te = pd.Timestamp(ts), pd.Timestamp(te)
    for h in H:
        win_end = a.week_start + pd.to_timedelta(7 * h, unit='D')
        train = (win_end < ts)                           # label fully observed before test start (embargo of h weeks)
        test = (a.week_start >= ts) & (a.week_start < te)
        if name == 'LOCKED2026':      # protocol s.5: locked issue weeks must have their whole h-week window inside the extracted data
            test &= win_end <= a.week_start.max()
        fold_rows.append(pd.DataFrame({'district': a.district, 'week_start': a.week_start, 'fold': name, 'h': h,
                                       'role': np.where(test, 'test', np.where(train, 'train', 'excluded'))}))
folds = pd.concat(fold_rows, ignore_index=True)
a['locked_test'] = (a.week_start >= '2026-01-05').astype(int)

# ---------------------------------------------------------------- 11. write outputs
keys = ['district_id', 'district', 'division', 'year', 'iso_week', 'week_start', 'segment', 'source']
qc = ['new_cases', 'qc_issue', 'primary_target_usable', 'sensitivity_only', 'cases_obs', 'inc_obs', 'population']
feat = [c for c in a.columns if c.startswith(('cases_lag', 'inc_lag', 'inc_mean', 'log_inc_growth', 'nb_', 'gravity_',
                                               'national_inc', 'dhaka_inc', 'clim_', 'dev_', 'festival_in_next',
                                               'festival_window_t', 'festival_influx_t', 'woy_', 'rep_'))] + \
       ['log_population', 'pop_density', 'river_density', 'road_density']
outc = ['ob_T2', 'ob_T5', 'ob_T10', 'at_risk_primary'] + [f'y_onset_h{h}' for h in H] + \
       ['y_future_cases_4w', 'y_future_inc_4w', 'hotspot', 'y_hotspot_emergence_h4', 'locked_test']
assert not set(BANNED) & set(feat)
v2 = a[keys + qc + feat + outc]
v2.to_csv(O / 'master_dataset_v2.csv', index=False)
labels.to_csv(O / 'labels_all_definitions_long.csv.gz', index=False, compression='gzip')
folds.to_csv(O / 'frozen_folds_long.csv.gz', index=False, compression='gzip')
pd.DataFrame(log).to_csv(O / 'correction_log_v2.csv', index=False)
LOCKED_LAST = str((v2.week_start.max() - pd.Timedelta(weeks=4)).date())   # last issue week whose 4-week window is inside the data
LOCKED_LAST_BY_H = {h: str((v2.week_start.max() - pd.Timedelta(weeks=h)).date()) for h in H}
json.dump({'locked_period_first_issue_week': '2026-01-05', 'locked_period_last_issue_week_with_complete_h4_label': LOCKED_LAST,
           'locked_period_last_issue_week_by_h': LOCKED_LAST_BY_H,
           'data_last_week': str(v2.week_start.max().date()), 'features': feat, 'outcomes': outc, 'keys': keys, 'qc': qc, 'climate_source': CLIM_SOURCE,
           'locked_extension_present': EXTENSION, 'primary_definition': PRIMARY, 'thresholds': THRESH,
           'quiet_windows': QUIET, 'horizons': H, 'min_cases': MINCASES, 'folds': FOLDS},
          open(O / 'build_manifest.json', 'w'), indent=1, default=str)
print('V2 rows', len(v2), 'features', len(feat), 'climate', CLIM_SOURCE, 'extension', EXTENSION)
