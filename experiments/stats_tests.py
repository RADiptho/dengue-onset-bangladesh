"""Pre-registered tests on pooled development folds: cluster bootstrap (onset weeks) for event capture,
issue-week block bootstrap for AUPRC/Brier, Holm correction."""
from engine import *
from statsmodels.stats.multitest import multipletests
B = 2000
rng = np.random.default_rng(2026)

def cluster_boot_capture(evr, a, b, h, k):
    e = evr[(evr.h == h) & (evr.k == k) & evr.model.isin([a, b])]
    w = e.pivot_table(index=['fold', 'district', 'onset_week'], columns='model', values='hit').reset_index()
    d = (w[a].astype(float) - w[b].astype(float)).values
    cl = w.onset_week.values; ucl = np.unique(cl); idx = {c: np.where(cl == c)[0] for c in ucl}
    boots = []
    for _ in range(B):
        pick = np.concatenate([idx[c] for c in rng.choice(ucl, len(ucl))])
        boots.append(d[pick].mean())
    boots = np.array(boots)
    p = min(1.0, 2 * min((boots <= 0).mean(), (boots >= 0).mean()))
    return d.mean(), np.percentile(boots, 2.5), np.percentile(boots, 97.5), p, len(d)

def block_boot_prob(pred, a, b, h, metric):
    g = pred[(pred.h == h) & pred.model.isin([a, b]) & pred.y.notna()]
    w = g.pivot_table(index=['fold', 'district', 'week_start', 'y'], columns='model', values='prob').reset_index()
    wk = (w.fold + '_' + w.week_start.astype(str)).values; uw = np.unique(wk); idx = {x: np.where(wk == x)[0] for x in uw}
    def f(ix):
        yy = w.y.values[ix]
        if metric == 'auprc':
            return average_precision_score(yy, w[a].values[ix]) - average_precision_score(yy, w[b].values[ix])
        return np.mean((w[a].values[ix] - yy) ** 2) - np.mean((w[b].values[ix] - yy) ** 2)
    obs = f(np.arange(len(w)))
    boots = np.array([f(np.concatenate([idx[x] for x in rng.choice(uw, len(uw))])) for _ in range(B)])
    p = min(1.0, 2 * min((boots <= 0).mean(), (boots >= 0).mean()))
    return obs, np.percentile(boots, 2.5), np.percentile(boots, 97.5), p

if __name__ == '__main__':
    pred = pd.read_csv(OUT / 'dev_predictions_primary.csv.gz', parse_dates=['week_start'])
    evr = pd.read_csv(OUT / 'dev_event_hits_primary.csv.gz', parse_dates=['onset_week'])
    MAIN = 'main_isotonic'      # protocol: choose Platt vs isotonic on development folds -> isotonic (pooled Brier); raw reported too
    comps = [(MAIN, b) for b in ['persistence', 'seasonal_climatology', 'endemic_only', 'neighbour_only', 'hhh4']] + [('hhh4', 'persistence')]
    rows = []
    for h in H:
        for a, b in comps:
            for k in KS:
                d, lo, hi, p, n = cluster_boot_capture(evr, a, b, h, k)
                rows.append(dict(h=h, a=a, b=b, metric=f'event_cap@{k}', diff=d, lo=lo, hi=hi, p=p, n=n))
            for metric in ['auprc', 'brier']:
                a2 = 'main_raw' if a == MAIN and metric == 'auprc' else a       # AUPRC is rank-based: isotonic ties distort it
                d, lo, hi, p = block_boot_prob(pred, a2, b, h, metric)
                rows.append(dict(h=h, a=a2, b=b, metric=metric, diff=d, lo=lo, hi=hi, p=p))
        print('h', h, 'done', flush=True)
    t = pd.DataFrame(rows)
    # Holm within each horizon x metric family (protocol: Holm across horizons and k)
    t['p_holm'] = np.nan
    for (h, fam), g in t.groupby(['h', t.metric.str.split('@').str[0]]):
        t.loc[g.index, 'p_holm'] = multipletests(g.p, method='holm')[1]
    t['p_holm_all_h'] = np.nan
    for fam, g in t.groupby(t.metric.str.split('@').str[0]):
        t.loc[g.index, 'p_holm_all_h'] = multipletests(g.p, method='holm')[1]
    t.to_csv(OUT / 'dev_stat_tests.csv', index=False)
    pd.set_option('display.width', 220)
    print(t[t.h == 4].round(3).to_string(index=False))
