"""Frozen metrics for any long-format prediction table (one model x fold x h at a time)."""
from engine import *

def eval_table(pred, v, folds, events_all, ks=KS, models=None):
    res, ev_rows = [], []
    models = models or pred.model.unique()
    for (fold, h, model), g in pred[pred.model.isin(models)].groupby(['fold', 'h', 'model']):
        pm = prob_metrics(g.prob.values.astype(float), g.y.values.astype(float))
        ranked = rank_table(g, g.score.values)
        orc = rank_table(g, np.nan_to_num(g.y.values.astype(float), nan=0.0))
        ev = evaluable_events(events_all, g.week_start.unique(), h)
        row = dict(fold=fold, h=h, model=model, n_events=len(ev), **pm)
        for k in ks:
            hit, lead = event_capture(ranked, ev, k, h)
            row[f'event_cap@{k}'] = hit.mean() if len(ev) else np.nan
            row[f'lead@{k}'] = lead[hit].mean() if hit.any() else np.nan
            row[f'floor@{k}'] = random_floor_events(ranked, ev, k, h).mean() if len(ev) else np.nan
            row[f'ceiling@{k}'] = event_capture(orc, ev, k, h)[0].mean() if len(ev) else np.nan
            sel = ranked[ranked['rank'] <= k].merge(g[['district', 'week_start', 'y']], on=['district', 'week_start'])
            row[f'window_cap@{k}'] = sel.y.sum() / max(np.nansum(g.y), 1)
            row[f'alerts_per_capture@{k}'] = len(sel) / max(sel.y.sum(), 1)
            row[f'false_alert_share@{k}'] = float((sel.y == 0).sum() / max(sel.y.notna().sum(), 1))
            for i, (_, o) in enumerate(ev.iterrows()):
                ev_rows.append(dict(fold=fold, h=h, model=model, k=k, district=o.district, onset_week=o.onset_week,
                                    hit=bool(hit[i]), lead=int(lead[i])))
        res.append(row)
    return pd.DataFrame(res), pd.DataFrame(ev_rows)


def pooled(res_events, models, h, k):
    e = res_events[(res_events.h == h) & (res_events.k == k) & res_events.model.isin(models)]
    return e.groupby('model').hit.agg(['mean', 'size'])

if __name__ == '__main__':
    v, folds, labels = load()
    events = onset_events(v, outbreak_flags(v, 5))
    pred = pd.read_csv(OUT / 'dev_predictions_primary.csv.gz', parse_dates=['week_start'])
    res, evr = eval_table(pred, v, folds, events)
    res.to_csv(OUT / 'dev_metrics_primary.csv', index=False); evr.to_csv(OUT / 'dev_event_hits_primary.csv.gz', index=False, compression='gzip')
    show = ['fold', 'model', 'n_events', 'positives', 'auprc', 'brier', 'cal_slope', 'event_cap@5', 'event_cap@10', 'event_cap@20', 'floor@10', 'ceiling@10']
    pd.set_option('display.width', 250)
    print(res[res.h == 4][show].round(3).to_string(index=False))
    print('\nPOOLED DEV (h=4) event capture:')
    for k in KS:
        e = evr[(evr.h == 4) & (evr.k == k)]
        print(k, e.groupby('model').hit.mean().round(3).to_dict(), 'n events', e.groupby('model').size().iloc[0])
