"""Reproduces posthoc/posthoc_dev_calibration_ci.csv (Equations 15 and 16, week-block bootstrap, 1,000 resamples, seed 31)."""
import os as _os
def _repo_root():
    d = _os.path.dirname(_os.path.abspath(__file__))
    while not _os.path.exists(_os.path.join(d, '.repo_root')):
        parent = _os.path.dirname(d)
        if parent == d: raise RuntimeError('repository root (.repo_root) not found')
        d = parent
    return d + '/'
ROOT = _repo_root()

import numpy as np, pandas as pd, statsmodels.api as sm, pathlib
PH=pathlib.Path(ROOT + 'posthoc')
P=pd.read_csv(PH/'posthoc_dev_predictions.csv.gz',parse_dates=['week_start'],low_memory=False)
models=['hhh4','hhh4_online','ens_hhh4_persist','persistence','main_raw']
W=P[P.model.isin(models)&P.y.notna()].pivot_table(index=['fold','district','week_start','y'],columns='model',values='prob').reset_index()
wk=(W.fold+W.week_start.astype(str)).values; uw=np.unique(wk); idx={x:np.where(wk==x)[0] for x in uw}
def slope_oe(ix,m):
    p=np.clip(W[m].values[ix],1e-6,1-1e-6); y=W.y.values[ix]; lp=np.log(p/(1-p))
    return sm.GLM(y,sm.add_constant(lp),family=sm.families.Binomial()).fit().params[1], y.sum()/p.sum()
rng=np.random.default_rng(31); boots={m:[] for m in models}
for b in range(1000):
    ix=np.concatenate([idx[x] for x in rng.choice(uw,len(uw))])
    for m in models: boots[m].append(slope_oe(ix,m))
rows=[]
for m in models:
    a=np.array(boots[m]); s0,o0=slope_oe(np.arange(len(W)),m)
    dsl = a[:,0] - np.array(boots['hhh4'])[:,0]   # paired slope difference against hhh4, same resamples
    rows.append(dict(model=m, slope=s0, slope_lo=np.percentile(a[:,0],2.5), slope_hi=np.percentile(a[:,0],97.5), oe=o0, oe_lo=np.percentile(a[:,1],2.5), oe_hi=np.percentile(a[:,1],97.5),
                     slope_diff_vs_hhh4_lo=np.percentile(dsl,2.5), slope_diff_vs_hhh4_hi=np.percentile(dsl,97.5)))
R=pd.DataFrame(rows); R.to_csv(PH/'posthoc_dev_calibration_ci.csv', index=False); print(R.round(3).to_string(index=False))
