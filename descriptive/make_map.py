import os as _os
def _repo_root():
    d = _os.path.dirname(_os.path.abspath(__file__))
    while not _os.path.exists(_os.path.join(d, '.repo_root')):
        parent = _os.path.dirname(d)
        if parent == d: raise RuntimeError('repository root (.repo_root) not found')
        d = parent
    return d + '/'
ROOT = _repo_root()

import geopandas as gpd, pandas as pd, numpy as np, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm, BoundaryNorm, ListedColormap
from matplotlib.patches import Patch, Rectangle, FancyArrow
from matplotlib.lines import Line2D
F = ROOT; P = F + 'pipeline/'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 7.5, 'axes.linewidth': 0.4})
a2 = gpd.read_file(F + 'data/boundaries/bgd_admin2.shp').to_crs(32646); a1 = gpd.read_file(F + 'data/boundaries/bgd_admin1.shp').to_crs(32646)
a0 = gpd.read_file(F + 'data/boundaries/bgd_admin0.shp').to_crs(32646)
X = pd.read_csv(F + 'data/lookup/district_crosswalk_panel_to_OCHA_ADM2.csv'); H = pd.read_csv(F + 'descriptive/output/district_hotspots_final.csv')
G = a2.merge(X[['ocha_adm2_pcode', 'panel_district']], left_on='adm2_pcode', right_on='ocha_adm2_pcode', validate='one_to_one')
G = G.merge(H, left_on='panel_district', right_on='district', validate='one_to_one'); assert len(G) == 64
# ---- independent verification of mapped values against the frozen panel (different code path)
v = pd.read_csv(P + 'outputs/master_dataset_v2.csv', parse_dates=['week_start'])
f = v[v.week_start.dt.year.between(2022, 2025) & v.cases_obs.notna()]
inc2 = f.groupby('district').apply(lambda g: g.cases_obs.sum() / (g.population.iloc[0] * len(g)) * 1e5 * 52.18, include_groups=False)
assert v.groupby('district').population.nunique().max() == 1, 'population varies within district'
chk = G.set_index('district')
assert np.allclose(chk.annualised_incidence_2022_2025, inc2.reindex(chk.index), rtol=1e-9), 'incidence mismatch'
ev = pd.read_csv(F + 'audit/output/recomputed_headline.csv')  # (exists; events re-derived below for counts)
import sys; sys.path.insert(0, F + 'experiments'); from common import onset_events, outbreak_flags
evc = onset_events(v.sort_values(['district', 'week_start']).reset_index(drop=True), outbreak_flags(v.sort_values(['district', 'week_start']).reset_index(drop=True), 5)).groupby('district').size()
assert (chk.onset_events == evc.reindex(chk.index, fill_value=0)).all(), 'onset count mismatch'
print('verified: incidence and onset counts for all 64 polygons match independent recomputation')
# ---- figure
fig, axs = plt.subplots(2, 2, figsize=(7.1, 8.4)); axs = axs.ravel()
def base(ax, title, letter):
    ax.set_axis_off(); ax.set_title(r'$\bf{' + letter + '}$   ' + title, fontsize=8.5, loc='left', pad=3)
    a1.boundary.plot(ax=ax, color='#222222', linewidth=0.7, zorder=4)
# A study area
ax = axs[0]; G.plot(ax=ax, color='#eeeeee', edgecolor='#777777', linewidth=0.3); base(ax, 'Study area: 64 districts and 8 divisions', 'A')
name = a1.columns[[c.startswith('adm1_name') for c in a1.columns]][0]
for _, r in a1.iterrows():
    p = r.geometry.representative_point(); ax.text(p.x, p.y, r[name], fontsize=6.5, ha='center', va='center', color='#111111', fontweight='bold',
                                                    bbox=dict(boxstyle='round,pad=0.15', fc='white', ec='none', alpha=0.7), zorder=6)
d = G[G.district == 'Dhaka'].geometry.centroid.iloc[0]; ax.plot(d.x, d.y - 12000, marker='*', color='#b2182b', markersize=7, zorder=7)
ax.legend(handles=[Line2D([0], [0], marker='*', color='w', markerfacecolor='#b2182b', markersize=8, label='Dhaka district (capital)')], loc='lower right', fontsize=6, frameon=False)
xmin, ymin, xmax, ymax = a0.total_bounds
ax.add_patch(Rectangle((xmin + 5000, ymin + 15000), 100000, 6000, color='black')); ax.text(xmin + 55000, ymin + 26000, '100 km', ha='center', fontsize=6)
ax.annotate('', xy=(xmax - 25000, ymax - 10000), xytext=(xmax - 25000, ymax - 70000), arrowprops=dict(arrowstyle='-|>', color='black', lw=1))
ax.text(xmax - 25000, ymax - 2000, 'N', ha='center', fontsize=8, fontweight='bold')
# B incidence
ax = axs[1]; vals = G.annualised_incidence_2022_2025
G.plot(ax=ax, column='annualised_incidence_2022_2025', cmap='YlOrRd', norm=LogNorm(vmin=max(vals.min(), 1), vmax=vals.max()), edgecolor='white', linewidth=0.25,
       legend=True, legend_kwds={'shrink': 0.55, 'label': 'Cases per 100,000 per year (log scale)', 'orientation': 'horizontal', 'pad': 0.01})
base(ax, 'Annualised incidence, 2022-2025', 'B')
cb = fig.axes[-1]; tk = [t for t in [3, 10, 30, 100, 300] if vals.min() <= t <= vals.max()]
cb.set_xticks(tk); cb.set_xticklabels([str(t) for t in tk]); cb.minorticks_off()
# C onsets
ax = axs[2]; mx = int(G.onset_events.max()); cm = plt.get_cmap('PuBu', mx + 1)
G.plot(ax=ax, column='onset_events', cmap=cm, norm=BoundaryNorm(np.arange(-0.5, mx + 1.5), cm.N), edgecolor='#999999', linewidth=0.25,
       legend=True, legend_kwds={'shrink': 0.55, 'label': 'Outbreak-onset events, Aug 2019 to Aug 2026', 'orientation': 'horizontal', 'pad': 0.01, 'ticks': range(mx + 1)})
base(ax, 'Outbreak-onset events per district', 'C')
# D hotspots
ax = axs[3]; colors = {'High-high': '#c51b1b', 'Low-low': '#2c6fbb', 'High-low': '#f4a6a6', 'Low-high': '#a6c8ee', 'Not significant': '#e6e6e6'}
G.plot(ax=ax, color=G.lisa_class.map(colors), edgecolor='white', linewidth=0.25)
G[G.recurrent_high_incidence].boundary.plot(ax=ax, color='black', linewidth=1.3, zorder=5)
base(ax, 'Spatial clusters (local Moran\'s I, FDR < 0.05)', 'D')
present = [c for c in colors if (G.lisa_class == c).any()]
hand = [Patch(fc=colors[c], ec='none', label=c) for c in present] + [Line2D([0], [0], color='black', lw=1.3, label='Recurrent high incidence (top quintile, 3+ seasons)')]
ax.legend(handles=hand, loc='lower left', fontsize=5.8, frameon=False, bbox_to_anchor=(-0.02, -0.02))
plt.subplots_adjust(wspace=0.02, hspace=0.12, left=0.03, right=0.99, top=0.96, bottom=0.03)
fig.savefig(F + 'figures/output/Figure2_Bangladesh_dengue_maps.pdf'); fig.savefig(F + 'figures/output/Figure2_Bangladesh_dengue_maps.png', dpi=600)
G.drop(columns='geometry').to_csv(F + 'descriptive/output/map_values_joined.csv', index=False)
print('legend classes:', present)
