"""Figures 8-10 (post hoc) from frozen predictions and event hits; h = 4, pooled development folds."""
import os as _os
def _repo_root():
    d = _os.path.dirname(_os.path.abspath(__file__))
    while not _os.path.exists(_os.path.join(d, '.repo_root')):
        parent = _os.path.dirname(d)
        if parent == d: raise RuntimeError('repository root (.repo_root) not found')
        d = parent
    return d + '/'
ROOT = _repo_root()

import numpy as np, pandas as pd, geopandas as gpd, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from base import *
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 8, 'axes.spines.top': False, 'axes.spines.right': False,
                     'axes.linewidth': 0.6, 'svg.fonttype': 'none', 'pdf.fonttype': 42})
C = {'persistence': '#7f7f7f', 'main_raw': '#d95f02', 'hhh4': '#1b9e77'}
NM = {'persistence': 'Persistence', 'main_raw': 'LightGBM', 'hhh4': 'hhh4'}
OUT = ROOT + 'figures/output/'; D = ROOT + 'robustness/output/'
P = preds(); E = hits(); E = E[E.h == 4]
OPS = pd.read_csv(D + 'B_operational.csv'); OPS = OPS[OPS.period == 'POOLED']
FROZEN_CAP10 = {'persistence': 0.920, 'main_raw': 0.862, 'hhh4': 0.920}
rng = np.random.default_rng(2026); B = 2000

def cluster_ci(x, cl):
    u = np.unique(cl); idx = {c: np.where(cl == c)[0] for c in u}
    bs = [x[np.concatenate([idx[c] for c in rng.choice(u, len(u))])].mean() for _ in range(B)]
    return np.percentile(bs, [2.5, 97.5])

# ---------------- Figure 8: capture by minimum lead time (k = 10)
R = {m: ranked(P, m).set_index(['district', 'week_start']) for m in C}
rows = []
for m in C:
    ev = E[(E.model == m) & (E.k == 10)].reset_index(drop=True)
    assert len(ev) == 87 and abs(ev.hit.mean() - FROZEN_CAP10[m]) < 1e-3
    for L in [1, 2, 3, 4]:
        x = (ev.lead.values >= L).astype(float); lo, hi = cluster_ci(x, ev.onset_week.values)
        rows.append(dict(model=m, min_lead=L, capture=x.mean(), captured=int(x.sum()), events=len(x), lo=lo, hi=hi))
# random expectation of a flag at some lag >= L (Equation 19 restricted to lags L..4)
Rp = R['persistence']; ev = E[(E.model == 'persistence') & (E.k == 10)]
for L in [1, 2, 3, 4]:
    pr = []
    for _, o in ev.iterrows():
        miss = 1.0
        for j in range(L, 5):
            key = (o.district, o.onset_week - pd.Timedelta(weeks=j))
            if key in Rp.index: miss *= max(0.0, 1 - 10 / Rp.loc[key, 'n_at_risk'])
        pr.append(1 - miss)
    rows.append(dict(model='random', min_lead=L, capture=np.mean(pr), captured=np.nan, events=len(ev), lo=np.nan, hi=np.nan))
F8 = pd.DataFrame(rows); F8.to_csv(D + 'FIG8_lead_time_data.csv', index=False)
assert abs(F8[(F8.model == 'random') & (F8.min_lead == 1)].capture.iloc[0] - OPS[(OPS.model == 'persistence') & (OPS.k == 10)].floor_any4.iloc[0]) < 1e-9
fig, ax = plt.subplots(figsize=(3.5, 2.8))
off = {'persistence': -0.12, 'main_raw': 0, 'hhh4': 0.12}
for m in C:
    g = F8[F8.model == m]
    ax.errorbar(g.min_lead + off[m], g.capture, yerr=[g.capture - g.lo, g.hi - g.capture], color=C[m], marker='o', ms=4, lw=1.2, capsize=2, elinewidth=0.8, label=NM[m])
g = F8[F8.model == 'random']; ax.plot(g.min_lead, g.capture, color='#444444', ls='--', lw=0.9, marker='x', ms=4, label='Random selection')
ax.set_xticks([1, 2, 3, 4]); ax.set_xlabel('Minimum warning lead time (weeks)'); ax.set_ylabel('Share of onsets captured (k = 10)')
ax.set_ylim(0, 1.02); ax.legend(frameon=False, fontsize=7, loc='lower left'); ax.grid(axis='y', lw=0.3, color='#dddddd')
fig.tight_layout(); [fig.savefig(OUT + f'Figure8_lead_time.{e}', dpi=600) for e in ('pdf', 'png', 'svg')]; plt.close(fig)

# ---------------- Figure 9: capture against alerts per distinct captured onset
rows = []
for m in C:
    for k in [5, 10, 20]:
        ev = E[(E.model == m) & (E.k == k)]; x = ev.hit.values.astype(float); lo, hi = cluster_ci(x, ev.onset_week.values)
        o = OPS[(OPS.model == m) & (OPS.k == k)].iloc[0]
        assert abs(o.capture - x.mean()) < 1e-9
        rows.append(dict(model=m, k=k, capture=x.mean(), lo=lo, hi=hi, alerts=o.alerts, apc=o.alerts / x.sum(), first_alert_precision=o.first_alert_precision))
    for k in [5, 10, 20]:
        o = OPS[(OPS.model == 'persistence') & (OPS.k == k)].iloc[0]
        rows.append(dict(model='random', k=k, capture=o.floor_any4, lo=np.nan, hi=np.nan, alerts=o.alerts, apc=o.alerts / (o.floor_any4 * o.events), first_alert_precision=np.nan))
F9 = pd.DataFrame(rows).drop_duplicates(['model', 'k']); F9.to_csv(D + 'FIG9_burden_data.csv', index=False)
fig, ax = plt.subplots(figsize=(3.5, 2.8))
for m in list(C) + ['random']:
    g = F9[F9.model == m].sort_values('k'); col = C.get(m, '#444444')
    if m == 'random':
        ax.plot(g.apc, g.capture, ls='--', color=col, marker='x', ms=4, lw=0.9, label='Random selection')
    else:
        ax.errorbar(g.apc, g.capture, yerr=[g.capture - g.lo, g.hi - g.capture], color=col, marker='o', ms=4, lw=1.2, capsize=2, elinewidth=0.8, label=NM[m])
    for _, r in g.iterrows():
        if m in ('hhh4', 'random'):
            ax.annotate(f'k = {r.k}', (r.apc, r.capture), textcoords='offset points', xytext=(5, -9) if m == 'random' else ((-26, 3) if r.k == 5 else (4, 4)), fontsize=6.5, color=col)
ax.set_xlabel('Alerts per distinct captured onset (district-weeks)'); ax.set_ylabel('Share of onsets captured')
ax.set_ylim(0, 1.05); ax.set_xlim(0, None); ax.legend(frameon=False, fontsize=7, loc='lower left'); ax.grid(lw=0.3, color='#dddddd')
fig.tight_layout(); [fig.savefig(OUT + f'Figure9_alert_burden.{e}', dpi=600) for e in ('pdf', 'png', 'svg')]; plt.close(fig)

# ---------------- Figure 10: district maps of captured onsets, missed onsets and false-alert rate (k = 10)
F = ROOT
a2 = gpd.read_file(F + 'data/boundaries/bgd_admin2.shp').to_crs(32646); a1 = gpd.read_file(F + 'data/boundaries/bgd_admin1.shp').to_crs(32646)
X = pd.read_csv(F + 'data/lookup/district_crosswalk_panel_to_OCHA_ADM2.csv')
G = a2.merge(X[['ocha_adm2_pcode', 'panel_district']], left_on='adm2_pcode', right_on='ocha_adm2_pcode', validate='one_to_one'); assert len(G) == 64
rows = []
for m in C:
    r = R[m].reset_index(); obs = r[r.y.notna()]
    fa = obs[(obs['rank'] <= 10) & (obs.y == 0)].groupby('district').size()
    ex = obs.groupby('district').size()
    ev = E[(E.model == m) & (E.k == 10)]
    cap = ev[ev.hit].groupby('district').size(); mis = ev[~ev.hit].groupby('district').size()
    d = pd.DataFrame({'eligible_windows': ex, 'false_alerts': fa, 'captured': cap, 'missed': mis}).fillna(0)
    d['false_alert_rate'] = d.false_alerts / d.eligible_windows; d['model'] = m; rows.append(d.reset_index().rename(columns={'index': 'district'}))
M10 = pd.concat(rows); M10.to_csv(D + 'FIG10_district_errors.csv', index=False)
for m in C:
    s = M10[M10.model == m]
    assert int(s.captured.sum() + s.missed.sum()) == 87
    assert int(s.false_alerts.sum()) == int(round(OPS[(OPS.model == m) & (OPS.k == 10)].alerts.iloc[0] * 0 + ((R[m].reset_index().query('rank <= 10 and y == 0')).shape[0])))
vmax = np.ceil(M10.false_alert_rate.max() * 20) / 20
fig, axs = plt.subplots(1, 3, figsize=(7.2, 3.6))
for ax, m in zip(axs, C):
    g = G.merge(M10[M10.model == m], left_on='panel_district', right_on='district', how='left')
    g.plot(ax=ax, column='false_alert_rate', cmap='Oranges', vmin=0, vmax=vmax, edgecolor='white', linewidth=0.25)
    a1.boundary.plot(ax=ax, color='#333333', linewidth=0.5)
    pts = g.representative_point()
    for (x, y, c, mi) in zip(pts.x, pts.y, g.captured, g.missed):
        if c > 0: ax.scatter(x, y, s=4 + 5 * c, color='#1f3b73', zorder=5, linewidths=0)
        if mi > 0: ax.scatter(x, y, s=30 + 12 * (mi - 1), facecolors='none', edgecolors='#c00000', linewidths=1.0, zorder=6)
    s = M10[M10.model == m]
    ax.set_title(f'{NM[m]}\ncaptured {int(s.captured.sum())}, missed {int(s.missed.sum())}', fontsize=8); ax.set_axis_off()
sm = plt.cm.ScalarMappable(cmap='Oranges', norm=plt.Normalize(0, vmax)); cax = fig.add_axes([0.3, 0.15, 0.4, 0.022])
cb = fig.colorbar(sm, cax=cax, orientation='horizontal'); cb.set_label('False alerts per eligible quiet district-week (k = 10)', fontsize=7); cb.ax.tick_params(labelsize=6.5)
h = [Line2D([], [], marker='o', ls='', color='#1f3b73', ms=4, label='Captured onsets (size = count)'),
     Line2D([], [], marker='o', ls='', mfc='none', mec='#c00000', ms=6, label='Missed onset')]
fig.legend(handles=h, loc='lower center', bbox_to_anchor=(0.5, 0.0), ncol=2, frameon=False, fontsize=7)
fig.subplots_adjust(left=0.01, right=0.99, top=0.86, bottom=0.25, wspace=0.02)
[fig.savefig(OUT + f'Figure10_error_maps.{e}', dpi=600) for e in ('pdf', 'png', 'svg')]; plt.close(fig)
print(F8.round(3).to_string(index=False)); print(F9.round(3).to_string(index=False))
print(M10.groupby('model')[['captured', 'missed', 'false_alerts', 'eligible_windows']].sum())
print('false-alert rate range', M10.false_alert_rate.min().round(3), M10.false_alert_rate.max().round(3))
