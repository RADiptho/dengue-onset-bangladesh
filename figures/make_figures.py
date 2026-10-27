"""Main figures 1 and 3-8 from frozen outputs (Figure 2 = audited map)."""
import os as _os
def _repo_root():
    d = _os.path.dirname(_os.path.abspath(__file__))
    while not _os.path.exists(_os.path.join(d, '.repo_root')):
        parent = _os.path.dirname(d)
        if parent == d: raise RuntimeError('repository root (.repo_root) not found')
        d = parent
    return d + '/'
ROOT = _repo_root()

import sys, json, numpy as np, pandas as pd, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
sys.path.insert(0, ROOT + 'experiments')
from engine import rank_table, evaluable_events, event_capture, random_floor_events
from common import load, onset_events, outbreak_flags, FOLD_DATES
F = ROOT; O = ROOT + 'figures/output/'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 8, 'axes.spines.top': False, 'axes.spines.right': False, 'axes.linewidth': 0.6})
C = {'persistence': '#7f7f7f', 'LightGBM': '#d95f02', 'hhh4': '#1b9e77', 'ensemble': '#7570b3', 'hhh4 updated': '#66a61e'}
v, folds, labels = load(); ev = onset_events(v, outbreak_flags(v, 5))
reg = {}
# ---------------- Figure 3: national weekly incidence, onsets, evaluation periods
nat = v.groupby('week_start').agg(c=('cases_obs', 'sum'), p=('population', 'sum'), seg=('segment', 'first')).reset_index()
nat['inc'] = nat.c / nat.p * 1e5
fig, ax = plt.subplots(figsize=(7.1, 2.8))
for s, g in nat.groupby('seg'): ax.plot(g.week_start, g.inc, color='#333333', lw=0.8)
shade = {'F2023': '#fde0dd', 'F2024': '#e5f5e0', 'F2025': '#deebf7', 'LOCKED2026': '#efedf5'}
for f, (s, e) in FOLD_DATES.items():
    e2 = min(e, v.week_start.max()); ax.axvspan(s, e2, color=shade[f], zorder=0)
    ax.text(s + (e2 - s) / 2, nat.inc.max() * 1.02, {'LOCKED2026': 'Locked 2026'}.get(f, f.replace('F', 'Test ')), ha='center', fontsize=7)
ax.axvspan(pd.Timestamp('2020-01-01'), pd.Timestamp('2021-12-31'), color='white', hatch='///', ec='#bbbbbb', lw=0, zorder=0)
ax.text(pd.Timestamp('2021-01-01'), nat.inc.max() * 0.5, 'No data\n2020-2021', ha='center', fontsize=7, color='#666666')
evw = ev.groupby('onset_week').size()
ax.vlines(evw.index, -0.06 * nat.inc.max(), -0.06 * nat.inc.max() + 0.03 * nat.inc.max() * evw.values, color='#b2182b', lw=1)
ax.set_ylabel('Weekly cases per 100,000'); ax.set_ylim(-0.08 * nat.inc.max(), nat.inc.max() * 1.1)
ax.text(nat.week_start.min(), -0.075 * nat.inc.max(), 'Onset events (tick height = number per week)', fontsize=6.5, color='#b2182b', va='top')
fig.savefig(O + 'Figure3_temporal.png', dpi=400, bbox_inches='tight'); plt.close(fig)
reg['national_peak_weekly_incidence'] = (round(nat.inc.max(), 2), str(nat.loc[nat.inc.idxmax(), 'week_start'].date()))
# ---------------- Figure 4: primary comparison forest plot (paired differences vs persistence, pooled development, h = 4)
st = pd.read_csv(F + 'results/dev_stat_tests.csv'); st = st[(st.h == 4) & (st.b == 'persistence') & st.a.isin(['main_isotonic', 'main_raw', 'hhh4'])]
items = [('auprc', 'AUPRC'), ('brier', 'Brier score'), ('event_cap@5', 'Capture@5'), ('event_cap@10', 'Capture@10'), ('event_cap@20', 'Capture@20')]
fig, ax = plt.subplots(figsize=(7.1, 3.0)); plt.subplots_adjust(right=0.74); y = 0; yt = []
for met, lab in items:
    for mname, col, key in [('hhh4', C['hhh4'], 'hhh4'), ('LightGBM', C['LightGBM'], 'main_raw' if met == 'auprc' else 'main_isotonic')]:
        r = st[(st.a == key) & (st.metric == met)].iloc[0]
        ax.errorbar(r['diff'], y, xerr=[[r['diff'] - r.lo], [r.hi - r['diff']]], fmt='o', color=col, ms=4, capsize=2, lw=1)
        ax.text(1.02, y, f"{r['diff']:+.3f}  [{r.lo:+.3f}, {r.hi:+.3f}]  Holm p={(f"{r.p_holm:.3f}" if r.p_holm >= 0.001 else "<0.001")}", fontsize=6.0, va='center', transform=ax.get_yaxis_transform(), clip_on=False)
        yt.append((y, f'{lab}: {mname}')); y -= 1
    y -= 0.5
ax.axvline(0, color='black', lw=0.6); ax.set_yticks([a for a, b in yt]); ax.set_yticklabels([b for a, b in yt], fontsize=7)
ax.set_xlabel('Difference from persistence (95% bootstrap CI); for Brier score, negative = better')
fig.savefig(O + 'Figure4_primary.png', dpi=400, bbox_inches='tight'); plt.close(fig)
# ---------------- Figure 5: year-specific AUPRC differences vs persistence
b3 = pd.read_csv(F + 'audit/output/b3_perfold_holm.csv')
fig, ax = plt.subplots(figsize=(7.1, 2.9)); yrsn = {'F2023': '2023', 'F2024': '2024', 'F2025': '2025', 'LOCKED2026': '2026 (locked)'}
for j, (comp, lab, col) in enumerate([('hhh4 - persistence', 'hhh4', C['hhh4']), ('main_raw - persistence', 'LightGBM', C['LightGBM']),
                                      ('ens_hhh4_persist - persistence', 'Ensemble (post hoc)', C['ensemble'])]):
    for i, f in enumerate(yrsn):
        r = b3[(b3.fold == f) & (b3.comparison == comp)].iloc[0]; x = i + (j - 1) * 0.22
        ax.errorbar(x, r['diff'], yerr=[[r['diff'] - r.lo], [r.hi - r['diff']]], fmt='o' if j < 2 else 's', color=col, ms=4, capsize=2, lw=1,
                    label=lab if i == 0 else None, mfc=col if r.p_holm_16 < 0.05 else 'white')
ax.axhline(0, color='black', lw=0.6); ax.set_xticks(range(4)); ax.set_xticklabels(yrsn.values())
ax.set_ylabel('AUPRC difference from persistence'); ax.legend(fontsize=6.8, frameon=False, ncol=3, loc='upper right')
ax.text(3.45, ax.get_ylim()[0] * 0.95, 'Filled: Holm-adjusted p < 0.05 (16 comparisons)', fontsize=6.3, ha='right')
fig.savefig(O + 'Figure5_regimes.png', dpi=400, bbox_inches='tight'); plt.close(fig)
# ---------------- Figure 7: Capture@k allocation curves (pooled development, h = 4)
P = pd.read_csv(F + 'results/dev_predictions_primary.csv.gz', parse_dates=['week_start']); P = P[P.h == 4]
ks = list(range(1, 31)); curves = {}
for name, key in [('persistence', 'persistence'), ('LightGBM', 'main_raw'), ('hhh4', 'hhh4')]:
    hits = {k: [] for k in ks}; floors = {k: [] for k in ks}; ceil = {k: [] for k in ks}
    for f, g in P[P.model == key].groupby('fold'):
        R = rank_table(g, g.score.values); Ro = rank_table(g, np.nan_to_num(g.y.values.astype(float), nan=0.0)); E = evaluable_events(ev, g.week_start.unique(), 4)
        for k in ks:
            hits[k] += list(event_capture(R, E, k, 4)[0]); floors[k] += list(random_floor_events(R, E, k, 4)); ceil[k] += list(event_capture(Ro, E, k, 4)[0])
    curves[name] = [np.mean(hits[k]) for k in ks]; curves['random'] = [np.mean(floors[k]) for k in ks]; curves['ceiling'] = [np.mean(ceil[k]) for k in ks]
for nm, key in [('persistence', 'persistence'), ('LightGBM', 'main_raw'), ('hhh4', 'hhh4')]:
    for k in [5, 10, 20]: reg[f'fig7_{nm}_cap{k}'] = round(curves[nm][k - 1], 3)
fig, ax = plt.subplots(figsize=(7.1, 3.0))
ax.fill_between(ks, curves['random'], curves['ceiling'], color='#f0f0f0', label='Range between random selection and clairvoyant ceiling')
ax.plot(ks, curves['random'], '--', color='#999999', lw=1, label='Random selection'); ax.plot(ks, curves['ceiling'], ':', color='black', lw=1, label='Clairvoyant ceiling')
for nm in ['persistence', 'LightGBM', 'hhh4']: ax.plot(ks, curves[nm], color=C[nm], lw=1.5, label=nm)
for k in [5, 10, 20]: ax.axvline(k, color='#cccccc', lw=0.5, zorder=0)
ax.set_xlabel('Districts prioritised per week (k)'); ax.set_ylabel('Share of 87 onset events captured'); ax.set_ylim(0, 1.02); ax.legend(fontsize=6.6, frameon=False, loc='lower right')
fig.savefig(O + 'Figure7_capture.png', dpi=400, bbox_inches='tight'); plt.close(fig)
reg['fig7_random_cap10'] = round(curves['random'][9], 3); reg['fig7_ceiling_cap10'] = round(curves['ceiling'][9], 3)
reg['fig7_random_cap5'] = round(curves['random'][4], 3); reg['fig7_random_cap20'] = round(curves['random'][19], 3)
# ---------------- Figure 6: reliability curves (development, h = 4)
Q = pd.read_csv(F + 'posthoc/posthoc_dev_predictions.csv.gz', parse_dates=['week_start'], low_memory=False); Q = Q[Q.y.notna()]
fig, ax = plt.subplots(figsize=(4.6, 4.2)); mx = 0
for nm, key, mk in [('hhh4', 'hhh4', 'o'), ('hhh4 updated', 'hhh4_online', '^'), ('ensemble', 'ens_hhh4_persist', 's'), ('persistence', 'persistence', 'D')]:
    g = Q[Q.model == key].copy(); g['bin'] = pd.qcut(g.prob.rank(method='first'), 10, labels=False)
    b = g.groupby('bin').agg(p=('prob', 'mean'), o=('y', 'mean'), n=('y', 'size'))
    lab = {'ensemble': 'hhh4 + persistence ensemble (post hoc)', 'hhh4 updated': 'hhh4 refitted every 4 weeks (post hoc)'}.get(nm, nm)
    ax.plot(b.p, b.o, marker=mk, ms=3.5, lw=1, color=C[nm], label=lab); mx = max(mx, b.p.max(), b.o.max())
ax.plot([0, mx * 1.05], [0, mx * 1.05], color='black', lw=0.6, ls='--'); ax.set_xlabel('Mean predicted probability (decile groups)'); ax.set_ylabel('Observed onset frequency')
ax.legend(fontsize=6.3, frameon=False, loc='upper left')
fig.savefig(O + 'Figure6_calibration.png', dpi=400, bbox_inches='tight'); plt.close(fig)
json.dump(reg, open(O + 'figure_values.json', 'w'), indent=1, default=str); print(json.dumps(reg, indent=1, default=str))
