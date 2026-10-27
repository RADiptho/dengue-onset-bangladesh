"""ONLINE STEP. Fetch daily NASA POWER climate for all 64 district centroids (frozen climate source).

    python scripts/02_fetch_nasa_power.py --start 2018-12-01 --end 2026-08-30 --workers 6

FROZEN (unchanged): NASA POWER daily point API, community AG, district centroids from data_raw/districts.csv,
parameters T2M, T2M_MAX, T2M_MIN, RH2M, PRECTOTCORR, fill value -999 -> missing, nothing imputed.
Output (unchanged): data_raw/nasa_power_daily.csv with columns date, t2m, t2m_max, t2m_min, rh2m, precip, district.

WHAT CHANGED (speed and robustness only):
- each district's request is split into calendar-year chunks (small responses: far fewer ReadTimeout /
  ChunkedEncodingError failures), fetched in parallel by a small thread pool;
- every successful chunk is cached immediately in data_raw/nasa_power_cache/chunks/ and never fetched again;
- earlier full-range caches (data_raw/nasa_power_cache/<district>_<start>_<end>.csv) are reused when they cover
  the requested dates, so previous successful downloads are preserved;
- retries with exponential backoff and jitter on timeouts, connection resets, broken chunked responses, HTTP 429/5xx;
- failed chunks are logged and retried in later passes; the merged file is written only when every district has
  complete daily coverage (or with --allow-incomplete, which the audit will then flag).
Splitting a point request by date range returns the same daily values as one long request (same point, same
product).
"""
import argparse, concurrent.futures as cf, datetime as dt, pathlib, random, sys, threading, time
import pandas as pd

P = 'T2M,T2M_MAX,T2M_MIN,RH2M,PRECTOTCORR'
RENAME = {'T2M': 't2m', 'T2M_MAX': 't2m_max', 'T2M_MIN': 't2m_min', 'RH2M': 'rh2m', 'PRECTOTCORR': 'precip'}
COLS = ['date', 't2m', 't2m_max', 't2m_min', 'rh2m', 'precip']
API = 'https://power.larc.nasa.gov/api/temporal/daily/point'
CACHE = pathlib.Path('data_raw/nasa_power_cache'); CHUNKS = CACHE / 'chunks'
_local = threading.local()


def slug(name):
    return name.replace(' ', '_').replace("'", '')


def year_chunks(start, end):
    out, s = [], start
    while s <= end:
        e = min(dt.date(s.year, 12, 31), end)
        out.append((s, e)); s = e + dt.timedelta(days=1)
    return out


def chunk_path(d, s, e):
    return CHUNKS / f'{slug(d)}_{s:%Y%m%d}_{e:%Y%m%d}.csv'


def session():
    if not hasattr(_local, 's'):
        import requests
        _local.s = requests.Session()
        _local.s.headers.update({'User-Agent': 'dengue-district-research (NASA POWER point requests)'})
    return _local.s


def parse_json(js):
    p = js['properties']['parameter']
    df = pd.DataFrame({k: pd.Series(v) for k, v in p.items()})
    df.index = pd.to_datetime(df.index, format='%Y%m%d')
    df = df.replace(-999, pd.NA).rename(columns=RENAME)
    return df.reset_index(names='date')[COLS]


def fetch_chunk(task, retries=8, base_wait=4.0, max_wait=180.0, get=None):
    """task = (district, lat, lon, start, end). Returns (task, path or None, error)."""
    d, lat, lon, s, e = task
    path = chunk_path(d, s, e)
    if path.exists() and path.stat().st_size > 200:
        return task, path, ''
    url = (f'{API}?parameters={P}&community=AG&longitude={lon}&latitude={lat}'
           f'&start={s:%Y%m%d}&end={e:%Y%m%d}&format=JSON')
    get = get or (lambda u: session().get(u, timeout=(20, 240)))
    err = ''
    for k in range(retries):
        try:
            r = get(url)
            if r.status_code == 200:
                df = parse_json(r.json())
                if len(df) != (e - s).days + 1:
                    raise IOError(f'expected {(e - s).days + 1} days, got {len(df)}')
                tmp = path.with_suffix('.part'); df.to_csv(tmp, index=False); tmp.replace(path)
                return task, path, ''
            if r.status_code in (400, 404, 422):
                return task, None, f'HTTP {r.status_code}: {r.text[:200]}'     # request error: retrying will not help
            err = f'HTTP {r.status_code}'
        except Exception as ex:                                                # ReadTimeout, ChunkedEncodingError, resets, bad JSON
            err = f'{type(ex).__name__}: {str(ex)[:150]}'
        time.sleep(min(max_wait, base_wait * 2 ** k) * random.uniform(0.7, 1.3))
    return task, None, err


def reuse_old_cache(d, start, end):
    """Rows from an earlier full-range cache file for district d, if one covers [start, end]."""
    for f in sorted(CACHE.glob(f'{slug(d)}_*.csv')):
        try:
            cs, ce = [dt.date.fromisoformat(x) for x in f.stem[len(slug(d)) + 1:].split('_')[:2]]
        except (ValueError, IndexError):
            continue
        if cs <= start and ce >= end and f.stat().st_size > 1000:
            df = pd.read_csv(f, parse_dates=['date'])
            df = df[(df.date >= pd.Timestamp(start)) & (df.date <= pd.Timestamp(end))]
            if df.date.nunique() == (end - start).days + 1:
                return df[COLS]
    return None


def merge(dist, have, start, end):
    frames, incomplete = [], []
    for _, r in dist.iterrows():
        if r.district in have:
            df = have[r.district]
        else:
            parts = [chunk_path(r.district, s, e) for s, e in year_chunks(start, end)]
            if not all(x.exists() for x in parts):
                incomplete.append(r.district); continue
            df = pd.concat([pd.read_csv(x, parse_dates=['date']) for x in parts])
        df = df.drop_duplicates('date').sort_values('date')
        if len(df) != (end - start).days + 1:
            incomplete.append(r.district); continue
        frames.append(df.assign(district=r.district))
    return frames, incomplete


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--start', default='2018-12-01'); ap.add_argument('--end', default='2026-08-30')
    ap.add_argument('--workers', type=int, default=6, help='parallel requests (keep modest: shared public service)')
    ap.add_argument('--passes', type=int, default=4, help='retry passes over still-missing chunks')
    ap.add_argument('--out', default='data_raw/nasa_power_daily.csv')
    ap.add_argument('--allow-incomplete', action='store_true')
    a = ap.parse_args()
    start, end = dt.date.fromisoformat(a.start), dt.date.fromisoformat(a.end)
    CHUNKS.mkdir(parents=True, exist_ok=True)
    dist = pd.read_csv('data_raw/districts.csv')
    have, tasks = {}, []
    for _, r in dist.iterrows():
        old = reuse_old_cache(r.district, start, end)
        if old is not None:
            have[r.district] = old; continue
        tasks += [(r.district, r.lat, r.lon, s, e) for s, e in year_chunks(start, end)]
    cached = sum(chunk_path(t[0], t[3], t[4]).exists() for t in tasks)
    print(f'districts reused from earlier full-range cache: {len(have)}; year-chunks needed: {len(tasks)} '
          f'({cached} already cached, {len(tasks) - cached} to fetch with {a.workers} workers)', flush=True)
    log, pending = [], [t for t in tasks if not chunk_path(t[0], t[3], t[4]).exists()]
    for p in range(1, a.passes + 1):
        if not pending:
            break
        t0, failed, done = time.time(), [], 0
        with cf.ThreadPoolExecutor(max_workers=a.workers) as ex:
            for task, path, err in ex.map(fetch_chunk, pending):
                done += 1
                if path is None:
                    failed.append(task)
                    log.append(dict(pass_no=p, district=task[0], start=task[3], end=task[4], error=err))
                if done % 25 == 0 or done == len(pending):
                    print(f'  pass {p}: {done}/{len(pending)} chunks, {len(failed)} failed, {time.time() - t0:.0f} s', flush=True)
        pending = failed
        if pending and p < a.passes:
            print(f'  {len(pending)} chunks failed in pass {p}; pausing 60 s before pass {p + 1}', flush=True)
            time.sleep(60)
    pd.DataFrame(log, columns=['pass_no', 'district', 'start', 'end', 'error']).to_csv(CACHE / 'fetch_log.csv', index=False)
    frames, incomplete = merge(dist, have, start, end)
    if incomplete and not a.allow_incomplete:
        print(f'INCOMPLETE ({len(incomplete)} districts): {", ".join(incomplete)}.\n'
              f'Re-run the same command: cached chunks are kept. Failure details: {CACHE / "fetch_log.csv"}')
        sys.exit(2)
    out = pd.concat(frames)[COLS + ['district']]
    out.to_csv(a.out, index=False)
    print(f'written {a.out}: {out.district.nunique()} districts, {out.date.min().date()}..{out.date.max().date()}, '
          f'{len(out)} rows, missing cells {int(out[COLS[1:]].isna().sum().sum())}')


if __name__ == '__main__':
    main()
