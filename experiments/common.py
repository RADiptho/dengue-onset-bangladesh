"""Shared data layer for the final experiments. Frozen definitions only (protocol sections 3-5)."""
import os as _os
def _repo_root():
    d = _os.path.dirname(_os.path.abspath(__file__))
    while not _os.path.exists(_os.path.join(d, '.repo_root')):
        parent = _os.path.dirname(d)
        if parent == d: raise RuntimeError('repository root (.repo_root) not found')
        d = parent
    return d + '/'
ROOT = _repo_root()

import json, numpy as np, pandas as pd, pathlib
PKG = pathlib.Path(ROOT + 'pipeline')
OUT = pathlib.Path(ROOT + 'results'); OUT.mkdir(exist_ok=True)
MAN = json.load(open(PKG / 'outputs/build_manifest.json'))
H = [1, 2, 4, 6, 8]; KS = [5, 10, 20]
DEV_FOLDS = ['F2023', 'F2024', 'F2025']
FOLD_DATES = {f: (pd.Timestamp(s), pd.Timestamp(e)) for f, s, e in MAN['folds']}

GROUPS = {
    'own': ['cases_lag0', 'cases_lag1', 'cases_lag2', 'cases_lag3', 'cases_lag4', 'cases_lag8', 'cases_lag12', 'inc_lag0',
            'inc_lag1', 'inc_lag2', 'inc_lag3', 'inc_lag4', 'inc_lag8', 'inc_lag12', 'inc_mean4_to_lag0', 'inc_mean8_to_lag0',
            'inc_mean12_to_lag0', 'log_inc_growth_1w', 'log_inc_growth_4w'],
    'adjacency': ['nb_inc_mean_lag0', 'nb_inc_max_lag0', 'nb_n_outbreak_T5_lag0', 'nb_inc_mean_lag1', 'nb_inc_max_lag1',
                  'nb_n_outbreak_T5_lag1'],
    'gravity': ['gravity_inc_lag0', 'gravity_inc_lag1'],
    'national': ['national_inc_lag0', 'national_inc_lag1', 'dhaka_inc_lag0', 'dhaka_inc_lag1'],
    'climate': ['clim_t2m_lag1', 'clim_t2m_mean4_lag1', 'clim_t2m_max_lag1', 'clim_t2m_max_mean4_lag1', 'clim_t2m_min_lag1',
                'clim_t2m_min_mean4_lag1', 'clim_rh2m_lag1', 'clim_rh2m_mean4_lag1', 'clim_precip_lag1',
                'clim_precip_mean4_lag1', 'clim_precip_sum8_lag1'],
    'calendar': ['woy_sin', 'woy_cos', 'festival_window_t', 'festival_in_next4w', 'festival_in_next8w', 'festival_influx_t'],
    'static': ['log_population', 'pop_density', 'river_density', 'road_density'],
    'satellite_dev': ['dev_chirps_rain_sum4_lag3', 'dev_ndvi_lag2', 'dev_ndwi_lag2', 'dev_lst_lag2', 'dev_viirs_lag5'],
    'reporting': ['rep_mch_row', 'rep_dhaka_metro_list'],
}
ANOM_SRC = ['clim_t2m_mean4_lag1', 'clim_rh2m_mean4_lag1', 'clim_precip_sum8_lag1']
MAIN_GROUPS = ['own', 'adjacency', 'gravity', 'national', 'climate', 'calendar', 'static']


def load():
    v = pd.read_csv(PKG / 'outputs/master_dataset_v2.csv', parse_dates=['week_start']).sort_values(['district', 'week_start']).reset_index(drop=True)
    folds = pd.read_csv(PKG / 'outputs/frozen_folds_long.csv.gz', parse_dates=['week_start'])
    labels = pd.read_csv(PKG / 'outputs/labels_all_definitions_long.csv.gz', parse_dates=['week_start'])
    for g, cols in GROUPS.items():
        missing = [c for c in cols if c not in v.columns]
        assert not missing, (g, missing)
    return v, folds, labels


def outbreak_flags(v, thr_inc, mincases=10):
    """thr_inc: scalar or per-row Series. Missing (QC) weeks stay missing."""
    ob = ((v.inc_obs >= thr_inc) & (v.cases_obs >= mincases)).astype(float)
    return ob.where(v.cases_obs.notna())


def make_labels(v, ob, q=4, h=4):
    """Independent re-implementation of the frozen at-risk / onset-window labels (protocol s.4)."""
    g = ob.groupby([v.district, v.segment])
    past = pd.concat([g.shift(k) for k in range(q)], axis=1)
    at_risk = ((past == 0).all(axis=1) & past.notna().all(axis=1)).astype(int)
    fw = pd.concat([g.shift(-j) for j in range(1, h + 1)], axis=1)
    y = np.where((fw == 1).any(axis=1), 1.0, np.where((fw == 0).all(axis=1) & fw.notna().all(axis=1), 0.0, np.nan))
    return at_risk, pd.Series(np.where(at_risk == 1, y, np.nan), index=v.index)


def onset_events(v, ob, q=4):
    """Distinct onset events: an outbreak week preceded by q observed non-outbreak weeks in the same segment."""
    g = ob.groupby([v.district, v.segment])
    prev = pd.concat([g.shift(k) for k in range(1, q + 1)], axis=1)
    flag = (ob == 1) & (prev == 0).all(axis=1) & prev.notna().all(axis=1)
    return v.loc[flag, ['district', 'week_start']].rename(columns={'week_start': 'onset_week'}).reset_index(drop=True)


def fold_roles(folds, fold, h):
    f = folds[(folds.fold == fold) & (folds.h == h)]
    return f.set_index(['district', 'week_start']).role
