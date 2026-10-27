"""Offline test of the parallel NASA POWER fetcher with a simulated unreliable server (no network)."""
import importlib.util, os, sys, tempfile, pathlib, threading, datetime as dt, re
import pandas as pd
here = pathlib.Path.cwd()
spec = importlib.util.spec_from_file_location('pw', here / 'scripts/02_fetch_nasa_power.py'); pw = importlib.util.module_from_spec(spec); spec.loader.exec_module(pw)

def value(lat, day):  # deterministic synthetic "truth" per point and day
    return round(25 + lat / 10 + (day.toordinal() % 7) / 10, 3)

class Resp:
    def __init__(self, code, js=None): self.status_code, self._js, self.text = code, js, ''
    def json(self): return self._js

calls, lock, fails = [], threading.Lock(), {}
class FakeSession:
    def get(self, url, timeout):
        assert timeout == (20, 240)
        q = dict(x.split('=') for x in url.split('?')[1].split('&'))
        assert q['community'] == 'AG' and q['parameters'] == pw.P
        key = (q['latitude'], q['start'])
        with lock:
            calls.append(key); n = fails.get(key, 0); fails[key] = n + 1
        if float(q['latitude']) < 22.5 and n < 2:            # southern points fail twice (ReadTimeout / broken chunk)
            raise [TimeoutError('ReadTimeout'), ConnectionError('ChunkedEncodingError')][n]
        s, e = dt.datetime.strptime(q['start'], '%Y%m%d').date(), dt.datetime.strptime(q['end'], '%Y%m%d').date()
        days = [s + dt.timedelta(i) for i in range((e - s).days + 1)]
        lat = float(q['latitude'])
        par = {k: {f'{d:%Y%m%d}': value(lat, d) for d in days} for k in ['T2M', 'T2M_MAX', 'T2M_MIN', 'RH2M', 'PRECTOTCORR']}
        par['PRECTOTCORR'][f'{days[0]:%Y%m%d}'] = -999
        return Resp(200, {'properties': {'parameter': par}})

pw.session = lambda: FakeSession()
pw.time.sleep = lambda s: None
with tempfile.TemporaryDirectory() as t:
    os.chdir(t); pathlib.Path('data_raw').mkdir()
    pd.DataFrame({'district_id': [1, 2, 3], 'district': ["Cox's Bazar", 'Noakhali', 'Dhaka'], 'division': ['C', 'C', 'D'],
                  'dghs_report_name': ['a', 'b', 'c'], 'lat': [21.45, 22.87, 23.81], 'lon': [92.0, 91.1, 90.4]}).to_csv('data_raw/districts.csv', index=False)
    # earlier full-range cache from the old script for Dhaka: must be reused, never re-fetched
    cdir = pathlib.Path('data_raw/nasa_power_cache'); cdir.mkdir(parents=True)
    days = pd.date_range('2018-12-01', '2026-08-30')
    pd.DataFrame({'date': days, 't2m': [value(23.81, d.date()) for d in days], 't2m_max': 30, 't2m_min': 20, 'rh2m': 80,
                  'precip': 1.0, 'district': 'Dhaka'}).to_csv(cdir / 'Dhaka_2018-12-01_2026-08-30.csv', index=False)
    sys.argv = ['x', '--start', '2018-12-01', '--end', '2026-08-30', '--workers', '4', '--passes', '2']
    pw.main()
    out = pd.read_csv('data_raw/nasa_power_daily.csv', parse_dates=['date'])
    assert set(out.district) == {"Cox's Bazar", 'Noakhali', 'Dhaka'} and len(out) == 3 * len(days)
    assert not any(k[0] == '23.81' for k in calls), 'old cache not reused'
    cx = out[out.district == "Cox's Bazar"].set_index('date')
    assert all(abs(cx.t2m[d] - value(21.45, d.date())) < 1e-9 for d in days[::97])   # chunked == truth for every sampled day
    assert cx.precip.isna().sum() == 9                                              # one -999 per year-chunk -> missing, not imputed
    n = len(calls)
    pw.main()                                                                       # second run: everything cached
    assert len(calls) == n, 'cached chunks were re-fetched'
    os.chdir(here)
print('NASA POWER fetcher tests passed: parallel year-chunks, retry on ReadTimeout/ChunkedEncodingError, old cache reused, resume without refetch, -999 kept missing')
