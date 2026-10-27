"""Offline test of the downloader (verified links only) with a simulated unreliable server. No network used."""
import importlib.util, datetime as dt, tempfile, pathlib
spec = importlib.util.spec_from_file_location('ex', 'scripts/01_extract_dghs_district_2026.py'); ex = importlib.util.module_from_spec(spec); spec.loader.exec_module(ex)
GOOD = b'%PDF-1.4\n' + b'x' * 30000 + b'\n%%EOF\n'

class Resp:
    def __init__(self, code, body): self.status_code, self.body = code, body
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def iter_content(self, chunk_size): yield self.body

class FlakySession:
    def __init__(self, script): self.script, self.calls = script, []
    def get(self, url, timeout, stream):
        assert timeout == (30, 300), timeout
        self.calls.append(url)
        r = self.script[url].pop(0) if self.script.get(url) else Resp(404, b'')
        if isinstance(r, Exception): raise r
        return r

links = ex.load_verified_links()
d1, d2, d3, d9 = dt.date(2026, 7, 5), dt.date(2026, 7, 12), dt.date(2026, 7, 19), dt.date(2026, 9, 6)
assert d1 in links and d2 in links and d3 in links and d9 not in links       # post-03/09 releases have no verified link
script = {links[d1]: [TimeoutError('Read timed out'), TimeoutError('Read timed out'), Resp(200, GOOD)],
          links[d2]: [Resp(200, b'%PDF-1.4 truncated'), Resp(200, GOOD)],
          links[d3]: [ConnectionError('reset')] * 3}
with tempfile.TemporaryDirectory() as t:
    t = pathlib.Path(t); s = FlakySession(script)
    dl = ex.Downloader(t / 'pdfs', t / 'manual', retries=3, base_wait=0.01, max_wait=0.02, pause=0, session=s, links=links)
    assert dl.get(d1) and dl.get(d2)
    assert dl.get(d3) is None and dl.get(d9) is None
    assert all(u in links.values() for u in s.calls)               # only verified URLs were ever requested
    n = len(s.calls)
    assert dl.get(d1) and len(s.calls) == n                         # cached, no new request
    (t / 'manual').mkdir(); (t / 'manual' / f'{d9:%Y%m%d}_dengue_all.pdf').write_bytes(GOOD)
    assert dl.get(d9) and len(s.calls) == n                         # manual file accepted, no network
    st = [r['status'] for r in dl.records]
    assert st == ['downloaded', 'downloaded', 'failed', 'no_verified_link', 'cached', 'manual'], st
assert ex.release_date_in_text('তারিখ: ০৫/০৭/২০২৬') == d1 and ex.release_date_in_text('05-Jul-2026 Government') == d1
print('downloader tests passed: verified-links only, retry/backoff, truncated-body rejection, graceful failure, cache skip, manual override, release-date check')
