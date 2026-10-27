"""Automated pre-modelling audit. Writes outputs/leakage_audit.csv and outputs/AUDIT_STATUS.json.
Every check is mechanical; a single FAIL blocks modelling."""
import json, os, shutil, subprocess, sys, tempfile, numpy as np, pandas as pd, pathlib

O = pathlib.Path('outputs'); R = pathlib.Path('data_raw')
v = pd.read_csv(O / 'master_dataset_v2.csv', parse_dates=['week_start'])
man = json.load(open(O / 'build_manifest.json'))
folds = pd.read_csv(O / 'frozen_folds_long.csv.gz', parse_dates=['week_start'])
res = []
def check(name, ok, detail=''):
    res.append({'check': name, 'result': 'PASS' if ok else 'FAIL', 'detail': detail}); print(('PASS ' if ok else 'FAIL ') + name, detail)

feat = man['features']
BANNED = ['new_deaths', 'currently_admitted', 'cumulative_cases', 'cumulative_deaths', 'incidence', 'eligible', 'ignition',
          'upstream_pressure', 'nbr_cases', 'naive', 'gtrends', 'ndvi_filled']
check('A1 banned target-derived columns absent from features', not [f for f in feat if any(b == f or f.startswith(b) for b in BANNED)])
check('A2 no feature name refers to a future week', not [f for f in feat if 'lead' in f or 'future' in f or f.startswith('y_')])

# B: segment boundaries
s22 = v[v.segment == 'S2022on'].sort_values(['district', 'week_start'])
first = s22.groupby('district').head(12).copy(); first['k'] = first.groupby('district').cumcount()
viol = []
for k_lag, col in [(1, 'cases_lag1'), (2, 'cases_lag2'), (4, 'cases_lag4'), (8, 'cases_lag8'), (12, 'cases_lag12'),
                   (1, 'inc_lag1'), (3, 'inc_mean4_to_lag0'), (7, 'inc_mean8_to_lag0'), (11, 'inc_mean12_to_lag0'),
                   (1, 'nb_inc_mean_lag1'), (1, 'gravity_inc_lag1')]:
    bad = first[(first.k < k_lag) & first[col].notna()]
    if len(bad): viol.append(f'{col}:{len(bad)}')
check('B1 no case-derived lag bridges 2019 -> 2022', not viol, ';'.join(viol))
if man['climate_source'].endswith('segment_bounded'):
    bad = first[(first.k < 1) & first.clim_t2m_lag1.notna()]
    check('B2 package climate lags do not bridge the gap (segment-bounded source)', len(bad) == 0, str(len(bad)))
else:
    check('B2 climate from continuous refetched series (gap bridging legitimate: not target-derived)', True)

# C: QC masking
v = v.sort_values(['district', 'week_start'])
prevqc = v.groupby(['district', 'segment']).primary_target_usable.shift(1)
bad = v[(prevqc == 0) & v.cases_lag1.notna()]
check('C1 lag-1 features missing whenever week t-1 is QC-excluded', len(bad) == 0, str(len(bad)))
bad = v[(v.primary_target_usable == 0) & v.cases_obs.notna()]
check('C2 QC-excluded targets are missing', len(bad) == 0, str(len(bad)))
roll_bad = v[(v.groupby(['district', 'segment']).primary_target_usable.transform(lambda s: s.rolling(4, min_periods=1).min()) == 0) & v.inc_mean4_to_lag0.notna()]
check('C3 4-week rolling means missing when any of the 4 weeks is QC-excluded', len(roll_bad) == 0, str(len(roll_bad)))

# D: future-perturbation invariance (rebuild from altered future outcomes; features up to cutoff must be identical)
cut = pd.Timestamp('2023-07-03')
tmp = pathlib.Path(tempfile.mkdtemp()); shutil.copytree(R, tmp / 'raw')
src = pd.read_csv(tmp / 'raw' / 'figshare_district_week_master_audit.csv', parse_dates=['week_start'])
rng = np.random.default_rng(0)
m = src.week_start > cut
src.loc[m, 'new_cases'] = (src.loc[m, 'new_cases'] * rng.uniform(0, 5, m.sum())).round()
for c in ['temp_mean', 'humidity', 'precip_power', 'rain', 'ndvi', 'lst', 'viirs']:
    src.loc[m, c] = src.loc[m, c] * rng.uniform(0.5, 1.5, m.sum())
src.to_csv(tmp / 'raw' / 'figshare_district_week_master_audit.csv', index=False)
pw = tmp / 'raw' / 'nasa_power_daily.csv'
if pw.exists():
    c = pd.read_csv(pw, parse_dates=['date']); mm = c.date > cut
    for col in ['t2m', 't2m_max', 't2m_min', 'rh2m', 'precip']:
        c.loc[mm, col] = c.loc[mm, col] * rng.uniform(0.5, 1.5, mm.sum())
    c.to_csv(pw, index=False)
ex = tmp / 'raw' / 'dghs_district_week_2026_extension.csv'
if ex.exists():
    e = pd.read_csv(ex); e['new_cases'] = (e.new_cases * rng.uniform(0, 5, len(e))).round(); e.to_csv(ex, index=False)
env = dict(os.environ, DENGUE_RAW=str(tmp / 'raw'), DENGUE_OUT=str(tmp / 'out'))
subprocess.run([sys.executable, 'scripts/03_build_master_v2.py'], env=env, check=True, capture_output=True)
p = pd.read_csv(tmp / 'out' / 'master_dataset_v2.csv', parse_dates=['week_start'])
A = v.set_index(['district', 'week_start']).sort_index(); B = p.set_index(['district', 'week_start']).sort_index()
idx = A.index[A.index.get_level_values('week_start') <= cut]
diff = [f for f in feat if not np.allclose(A.loc[idx, f].astype(float).values, B.loc[idx, f].astype(float).values, equal_nan=True)]
check('D1 features at or before the cutoff unchanged when all future cases and covariates are altered', not diff, ';'.join(diff))
lab_idx = A.index[A.index.get_level_values('week_start') <= cut - pd.Timedelta(weeks=8)]
ych = [f'y_onset_h{h}' for h in man['horizons'] if not np.allclose(A.loc[lab_idx, f'y_onset_h{h}'].values, B.loc[lab_idx, f'y_onset_h{h}'].values, equal_nan=True)]
check('D2 labels whose windows end before the cutoff unchanged', not ych, ';'.join(ych))
shutil.rmtree(tmp)

# E: availability lags. Expected values are re-derived independently from the RAW inputs for the full panel
# (original panel + locked extension, if present) and compared with V2 row by row on (district, week_start).
KEYS = ['district', 'week_start']
src0 = pd.read_csv(R / 'figshare_district_week_master_audit.csv', parse_dates=['week_start'])
raw = src0[KEYS + ['temp_mean', 'viirs', 'ndvi']].copy()
ext_p = R / 'dghs_district_week_2026_extension.csv'
if ext_p.exists():                       # extension weeks carry no package covariates: they enter as missing
    ext = pd.read_csv(ext_p, parse_dates=['week_start'])
    ext = ext[ext.week_start > src0.week_start.max()][KEYS]
    raw = pd.concat([raw, ext], ignore_index=True)
raw = raw.sort_values(KEYS).reset_index(drop=True)
raw['seg'] = np.where(raw.week_start.dt.year == 2019, 0, 1)
check('E0 raw reference panel has exactly the V2 district-weeks', len(raw) == len(v) and
      raw.set_index(KEYS).index.equals(v.sort_values(KEYS).set_index(KEYS).index), f'raw {len(raw)} vs V2 {len(v)}')
gr = raw.groupby(['district', 'seg'])
raw['exp_viirs_lag5'] = gr.viirs.shift(5)
raw['exp_ndvi_lag2'] = gr.ndvi.shift(2)
if man['climate_source'].endswith('segment_bounded'):
    raw['exp_clim_t2m_lag1'] = gr.temp_mean.shift(1)
else:                                    # refetched NASA POWER: weekly means of complete Monday-Sunday weeks, lag 1
    c = pd.read_csv(R / 'nasa_power_daily.csv', parse_dates=['date'])
    c['week_start'] = c.date - pd.to_timedelta(c.date.dt.weekday, unit='D')
    w = c.groupby(KEYS).agg(t=('t2m', 'mean'), n=('t2m', 'count')).reset_index().sort_values(KEYS)
    w.loc[w.n < 7, 't'] = np.nan
    w['exp_clim_t2m_lag1'] = w.groupby('district').t.shift(1)
    raw = raw.merge(w[KEYS + ['exp_clim_t2m_lag1']], on=KEYS, how='left')
M = v.merge(raw, on=KEYS, how='left', validate='one_to_one')
def same(a_, b_):
    return bool(np.allclose(M[a_].astype(float), M[b_].astype(float), equal_nan=True))
check(f'E1 climate enters with exactly a 1-week lag ({man["climate_source"]})', same('clim_t2m_lag1', 'exp_clim_t2m_lag1'))
check('E2 VIIRS enters with a 5-week lag (full panel incl. extension)', same('dev_viirs_lag5', 'exp_viirs_lag5'))
check('E3 NDVI enters with a 2-week lag (full panel incl. extension)', same('dev_ndvi_lag2', 'exp_ndvi_lag2'))
ext_rows = M[M.source == 'dghs_press_release_extension']
check('E4 extension rows never carry same-week or future satellite values (lags only reach back into observed weeks)',
      bool(ext_rows.empty or (ext_rows.dev_viirs_lag5.notna().sum() <= 5 * 64 and ext_rows.dev_ndvi_lag2.notna().sum() <= 2 * 64)),
      f'viirs lag5 non-missing {ext_rows.dev_viirs_lag5.notna().sum()}, ndvi lag2 non-missing {ext_rows.dev_ndvi_lag2.notna().sum()}')

# F: folds
for (fname, h), g in folds.groupby(['fold', 'h']):
    test_start = g[g.role == 'test'].week_start.min()
    tr = g[g.role == 'train']
    if (tr.week_start + pd.to_timedelta(7 * h, unit='D') >= test_start).any():
        check(f'F1 embargo {fname} h{h}', False); break
else:
    check('F1 every training label window ends before its test period begins (h-week embargo)', True)
dev = folds[folds.fold.isin(['F2023', 'F2024', 'F2025'])]
leak = dev[(dev.week_start >= '2026-01-05') & (dev.role != 'excluded')]
check('F2 no 2026 (locked) issue week used as train or test in development folds', len(leak) == 0, str(len(leak)))
check('F3 locked flag covers every 2026 row', bool((v[v.week_start >= '2026-01-05'].locked_test == 1).all()))
last = v.week_start.max()
lk = folds[(folds.fold == 'LOCKED2026') & (folds.role == 'test')]
bad = lk[lk.week_start + pd.to_timedelta(7 * lk.h, unit='D') > last]
check('F4 every locked test issue week has its whole h-week outcome window inside the extracted data (protocol s.5)',
      len(bad) == 0, f'{len(bad)} truncated-window rows')
check('F5 manifest locked end equals data end minus 4 weeks',
      man['locked_period_last_issue_week_with_complete_h4_label'] == str((last - pd.Timedelta(weeks=4)).date()),
      man['locked_period_last_issue_week_with_complete_h4_label'])

# G: brute-force label verification on a sample
v2 = v.sort_values(['district', 'week_start']).reset_index(drop=True)
rs = v2.sample(400, random_state=1)
errs = 0
for i, r in rs.iterrows():
    g = v2[(v2.district == r.district) & (v2.segment == r.segment)].set_index('week_start')
    t = r.week_start
    past = [g.ob_T5.get(t - pd.Timedelta(weeks=k), np.nan) for k in range(4)]
    risk = all(x == 0 for x in past)
    if int(risk) != r.at_risk_primary: errs += 1; continue
    if not risk: continue
    futv = [g.ob_T5.get(t + pd.Timedelta(weeks=j), np.nan) for j in range(1, 5)]
    y = 1.0 if any(x == 1 for x in futv) else (0.0 if all(x == 0 for x in futv) else np.nan)
    if not (np.isnan(y) and np.isnan(r.y_onset_h4)) and y != r.y_onset_h4: errs += 1
check('G1 primary at-risk and onset labels match brute-force recomputation (400 sampled rows)', errs == 0, f'{errs} mismatches')

# H: outcome integrity
check('H1 no negative or non-integer observed cases', bool(((v.cases_obs.dropna() >= 0) & (v.cases_obs.dropna() % 1 == 0)).all()))
check('H2 no duplicated district-weeks', not v.duplicated(['district', 'week_start']).any())
yr = v.groupby(v.week_start.dt.year).new_cases.sum()
off = {2022: 62382, 2023: 321179, 2024: 101214, 2025: 102861}
rel = {y: round((yr[y] - off[y]) / off[y] * 100, 2) for y in off}
check('H3 annual raw totals within 1% of official DGHS totals', all(abs(x) < 1 for x in rel.values()), str(rel))
ext = man['locked_extension_present']
check('H4 locked 2026 extension (July onward) present', ext, 'run scripts 01 and 02 online, then rebuild' if not ext else '')
check('H5 climate source identical for training and locked test', man['climate_source'] == 'nasa_power_refetch_centroid',
      man['climate_source'])

out = pd.DataFrame(res); out.to_csv(O / 'leakage_audit.csv', index=False)
core = out[~out.check.str.startswith(('H4', 'H5'))]
status = {'development_layer_ready': bool((core.result == 'PASS').all()),
          'locked_test_ready': bool((out.result == 'PASS').all()),
          'n_fail': int((out.result == 'FAIL').sum())}
json.dump(status, open(O / 'AUDIT_STATUS.json', 'w'), indent=1); print(status)
