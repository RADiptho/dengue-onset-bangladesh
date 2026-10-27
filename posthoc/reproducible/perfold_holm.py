"""Reproduces audit/output/b3_perfold_holm.csv (year-specific AUPRC differences, Equation 22, Holm across 16 tests, seed 101)."""
import os as _os
def _repo_root():
    d = _os.path.dirname(_os.path.abspath(__file__))
    while not _os.path.exists(_os.path.join(d, '.repo_root')):
        parent = _os.path.dirname(d)
        if parent == d: raise RuntimeError('repository root (.repo_root) not found')
        d = parent
    return d + '/'
ROOT = _repo_root()

import numpy as np, pandas as pd
from sklearn.metrics import average_precision_score
from statsmodels.stats.multitest import multipletests
B=ROOT + 'posthoc/'
A=pd.concat([pd.read_csv(B+'posthoc_dev_predictions.csv.gz',parse_dates=['week_start'],low_memory=False),pd.read_csv(B+'posthoc_locked_predictions_ALL.csv.gz',parse_dates=['week_start'],low_memory=False)])
rng=np.random.default_rng(101); rows=[]
for fold,g in A[A.y.notna()].groupby('fold'):
    w=g.pivot_table(index=['district','week_start','y'],columns='model',values='prob').reset_index()
    wk=w.week_start.values; uw=np.unique(wk); idx={x:np.where(wk==x)[0] for x in uw}
    for a,b in [('hhh4','persistence'),('ens_hhh4_persist','hhh4'),('ens_hhh4_persist','persistence'),('main_raw','persistence')]:
        f=lambda ix: average_precision_score(w.y.values[ix],w[a].values[ix])-average_precision_score(w.y.values[ix],w[b].values[ix])
        bs=[]
        while len(bs)<2000:
            ix=np.concatenate([idx[x] for x in rng.choice(uw,len(uw))])
            if w.y.values[ix].sum()>0: bs.append(f(ix))
        bs=np.array(bs); rows.append(dict(fold=fold,comparison=f'{a} - {b}',diff=f(np.arange(len(w))),lo=np.percentile(bs,2.5),hi=np.percentile(bs,97.5),p=min(1,2*min((bs<=0).mean(),(bs>=0).mean()))))
R=pd.DataFrame(rows); R['p_holm_16']=multipletests(R.p,method='holm')[1]
R.to_csv(ROOT + 'audit/output/b3_perfold_holm.csv', index=False); print(R.round(3).to_string(index=False))
