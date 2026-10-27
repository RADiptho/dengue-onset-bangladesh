"""Single layout specification for Figure 1 (shared by the vector and PowerPoint renderers). Units: 100 x 48."""
W, H = 100, 41.5
PAL = {'pre': ('#EEF3F9', '#3B5B82'), 'model': ('#FFFFFF', '#3B5B82'), 'lock': ('#F1ECF8', '#5D4391'), 'post': ('#FDF3E6', '#B4702A')}
# box: key -> (x, y, w, h, style, title, lines)
B = {
 'data':  (1.0, 15.0, 13.5, 15.0, 'pre', 'Data sources', ['DGHS weekly cases', 'NASA POWER climate', 'Connectivity, population']),
 'qc':    (17.5, 15.0, 12.5, 15.0, 'pre', 'Quality control', ['743 weeks masked', '25 leakage checks']),
 'target':(33.0, 15.0, 13.0, 15.0, 'pre', 'Onset target', ['After 4 quiet weeks', 'Horizons 1 to 8 weeks', 'Primary: 4 weeks']),
 'pers':  (49.5, 30.5, 12.5, 8.5, 'model', 'Persistence', ['+ 3 simple baselines']),
 'lgbm':  (49.5, 18.25, 12.5, 8.5, 'model', 'LightGBM', ['gradient boosting']),
 'hhh4':  (49.5, 6.0, 12.5, 8.5, 'model', 'hhh4', ['endemic-epidemic']),
 'valid': (65.2, 10.5, 17.0, 24.0, 'pre', 'Temporal validation', []),
 'pre':   (85.0, 23.5, 14.5, 13.0, 'pre', 'Pre-specified\nevaluation', ['Capture@k, k = 5, 10, 20', 'AUPRC, Brier, calibration']),
 'post':  (85.0, 6.0, 14.5, 14.5, 'post', 'Post-hoc\nanalyses', ['Block bootstrap', 'Lead time, alert burden', 'Regimes, error maps']),
}
mid = lambda k: B[k][1] + B[k][3] / 2
right = lambda k: B[k][0] + B[k][2]
busA = 48.0; busB = 63.6; busC = 83.6
ARROWS = [
 ([(right('data'), mid('data')), (B['qc'][0], mid('qc'))], 'pre', False),
 ([(right('qc'), mid('qc')), (B['target'][0], mid('target'))], 'pre', False),
 ([(right('target'), mid('target')), (busA, mid('target'))], 'pre', None),          # trunk, no head
 ([(busA, mid('hhh4')), (busA, mid('pers'))], 'pre', None),                           # vertical bus
] + [([(busA, mid(k)), (B[k][0], mid(k))], 'pre', False) for k in ('pers', 'lgbm', 'hhh4')] + \
 [([(right(k), mid(k)), (busB, mid(k))], 'pre', None) for k in ('pers', 'lgbm', 'hhh4')] + [
 ([(busB, mid('hhh4')), (busB, mid('pers'))], 'pre', None),
 ([(busB, mid('valid')), (B['valid'][0], mid('valid'))], 'pre', False),
 ([(right('valid'), mid('valid')), (busC, mid('valid'))], 'pre', None),
 ([(busC, mid('post')), (busC, mid('pre'))], 'pre', None),
 ([(busC, mid('pre')), (B['pre'][0], mid('pre'))], 'pre', False),
 ([(busC, mid('post')), (B['post'][0], mid('post'))], 'post', True),
]
# fold timeline inside the validation box
TL = dict(x0=B['valid'][0] + 5.0, y_top=B['valid'][1] + B['valid'][3] - 7.2, cw=1.75, rh=2.3, gap=0.7,
          rows=[('2023', 2), ('2024', 3), ('2025', 4), ('2026', 5)], years=['19', '22', '23', '24', '25', '26'])
LEGEND = [('pre', 'Pre-specified', False), ('lock', 'Locked 2026 test (scored once)', False), ('post', 'Post hoc (after locked scoring)', True)]
