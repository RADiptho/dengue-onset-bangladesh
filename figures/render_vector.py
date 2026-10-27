import os as _os
def _repo_root():
    d = _os.path.dirname(_os.path.abspath(__file__))
    while not _os.path.exists(_os.path.join(d, '.repo_root')):
        parent = _os.path.dirname(d)
        if parent == d: raise RuntimeError('repository root (.repo_root) not found')
        d = parent
    return d + '/'
ROOT = _repo_root()

import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle, Polygon
import geopandas as gpd
from spec import *
plt.rcParams.update({'font.family': 'DejaVu Sans', 'svg.fonttype': 'none', 'pdf.fonttype': 42})
fig = plt.figure(figsize=(7.2, 2.99)); ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, W); ax.set_ylim(0, H); ax.axis('off')
for k, (x, y, w, h, st, title, lines) in B.items():
    fc, ec = PAL[st]
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0,rounding_size=1.0', fc=fc, ec=ec, lw=0.9, ls=(0, (3, 1.6)) if st == 'post' else '-', zorder=2))
    if k == 'valid':
        ax.text(x + w / 2, y + h - 1.6, title, ha='center', va='top', fontsize=7.4, fontweight='bold', color='#1a1a1a', zorder=4)
        continue
    big = st != 'model'
    ty = y + h - (1.8 if big else 1.4)
    nl = title.count('\n')
    ax.text(x + w / 2, ty, title, ha='center', va='top', fontsize=7.4 if big else 7.2, linespacing=1.05, fontweight='bold', color='#1a1a1a', zorder=4)
    if lines:
        ax.text(x + w / 2, ty - (4.2 + 2.0 * nl if big else 3.6), '\n'.join(lines), ha='center', va='top', fontsize=5.4, color='#3a3a3a', linespacing=1.35, zorder=4)
# small Bangladesh map in the data box
g = gpd.read_file(ROOT + 'data/boundaries/bgd_admin2.shp').to_crs(32646); x0, y0, x1, y1 = g.total_bounds
bx, by, bw, bh = B['data'][:4]; sc = 2.6 / (x1 - x0); ox, oy = bx + bw - 3.4, by + 0.9
for geom in g.geometry.simplify(2500):
    for p in getattr(geom, 'geoms', [geom]):
        xx, yy = p.exterior.xy; ax.add_patch(Polygon(list(zip([ox + (a - x0) * sc for a in xx], [oy + (b - y0) * sc for b in yy])), fc='#C9D6E6', ec='white', lw=0.1, zorder=5))
ax.text(bx + 1.0, by + 1.2, '64 districts', ha='left', va='bottom', fontsize=5.2, color=PAL['pre'][1], zorder=5)
# arrows
for pts, st, dashed in ARROWS:
    c = PAL[st][1]; xs, ys = zip(*pts)
    ax.plot(xs, ys, color=c, lw=0.8, ls=(0, (3, 1.6)) if dashed else '-', zorder=1, solid_capstyle='butt')
    if dashed is not None:
        ax.annotate('', xy=pts[-1], xytext=(pts[-1][0] - 0.01, pts[-1][1]), arrowprops=dict(arrowstyle='-|>,head_length=0.4,head_width=0.2', color=c, lw=0.8), zorder=3)
# fold timeline
t = TL
for r, (lab, test) in enumerate(t['rows']):
    yy = t['y_top'] - r * (t['rh'] + t['gap'])
    lock = test == 5
    ax.text(t['x0'] - 0.6, yy + t['rh'] / 2, lab, ha='right', va='center', fontsize=5.4, color=PAL['lock'][1] if lock else '#333333', fontweight='bold' if lock else 'normal', zorder=4)
    for c in range(test + 1):
        col = '#C8CED6' if c < test else (PAL['lock'][1] if lock else PAL['pre'][1])
        ax.add_patch(Rectangle((t['x0'] + c * t['cw'] + 0.1, yy), t['cw'] - 0.2, t['rh'], fc=col, ec='none', zorder=4))
    ax.plot([t['x0'] + test * t['cw']] * 2, [yy - 0.3, yy + t['rh'] + 0.3], color='black', lw=0.8, zorder=5)
yb = t['y_top'] - 3 * (t['rh'] + t['gap']) - 0.6
for c, yr in enumerate(t['years']):
    ax.text(t['x0'] + c * t['cw'] + t['cw'] / 2, yb, yr, ha='center', va='top', fontsize=4.8, color='#555555', zorder=4)
# legend (single compact row)
lx, ly = 1.0, 0.9
for st, lab, dashed in LEGEND:
    fc, ec = PAL[st]
    ax.add_patch(FancyBboxPatch((lx, ly), 2.6, 1.6, boxstyle='round,pad=0,rounding_size=0.4', fc=fc, ec=ec, lw=0.8, ls=(0, (2.5, 1.2)) if dashed else '-'))
    ax.text(lx + 3.4, ly + 0.8, lab, va='center', fontsize=5.6, color='#333333'); lx += 4.6 + 0.62 * len(lab)
ax.add_patch(Rectangle((lx, ly), 2.6, 1.6, fc='#C8CED6', ec='none')); ax.text(lx + 3.4, ly + 0.8, 'Training years', va='center', fontsize=5.6, color='#333333'); lx += 4.6 + 0.62 * 14
ax.plot([lx + 0.6, lx + 0.6], [ly - 0.2, ly + 1.8], color='black', lw=0.8); ax.text(lx + 1.6, ly + 0.8, 'h-week embargo', va='center', fontsize=5.6, color='#333333')
for e in ('pdf', 'svg'): fig.savefig(ROOT + f'figures/output/Figure1_study_workflow.{e}')
fig.savefig(ROOT + 'figures/output/Figure1_study_workflow.png', dpi=600); print('saved')
