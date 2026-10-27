"""Reproduces posthoc/power_analysis.csv (Equation 23 and the AUPRC scaling rule)."""
import os as _os
def _repo_root():
    d = _os.path.dirname(_os.path.abspath(__file__))
    while not _os.path.exists(_os.path.join(d, '.repo_root')):
        parent = _os.path.dirname(d)
        if parent == d: raise RuntimeError('repository root (.repo_root) not found')
        d = parent
    return d + '/'
ROOT = _repo_root()

import numpy as np, pandas as pd, pathlib
from scipy.stats import norm
PH=pathlib.Path(ROOT + 'posthoc')
evr=pd.read_csv(PH/'posthoc_dev_event_hits.csv.gz'); T=pd.read_csv(PH/'posthoc_dev_tests.csv')
za,zb=norm.ppf(0.975),norm.ppf(0.8); rows=[]
for a,b in [('hhh4','persistence'),('main_raw','persistence'),('hhh4','main_raw'),('ens_hhh4_persist','persistence')]:
    for k in [5,10]:
        e=evr[(evr.k==k)&evr.model.isin([a,b])].pivot_table(index=['fold','district','onset_week'],columns='model',values='hit')
        p10=((e[a]==1)&(e[b]==0)).mean(); p01=((e[a]==0)&(e[b]==1)).mean(); pdisc=p10+p01; d=p10-p01
        n=np.inf if d==0 else (za*np.sqrt(pdisc)+zb*np.sqrt(pdisc-d**2))**2/d**2
        rows.append(dict(comparison=f'{a} vs {b}', metric=f'cap@{k}', observed_diff=d, discordant=pdisc, events_needed_80pct=np.ceil(n)))
    t=T[(T.model==a)&(T.ref==b)&(T.metric=='auprc')] if b in ('hhh4','persistence') else T[(T.model==b)&(T.ref==a)&(T.metric=='auprc')]
    if len(t):
        d=abs(t['diff'].iloc[0]); se=(t.hi.iloc[0]-t.lo.iloc[0])/(2*1.96)
        rows.append(dict(comparison=f'{a} vs {b}', metric='auprc', observed_diff=d, discordant=np.nan, events_needed_80pct=np.ceil(87*((za+zb)*se/d)**2)))
P=pd.DataFrame(rows); P.to_csv(PH/'power_analysis.csv', index=False)
print(P.to_string(index=False))
