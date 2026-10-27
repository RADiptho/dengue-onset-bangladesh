"""Extend the district-week panel beyond 29 June 2026 from DGHS daily press-release PDFs.

ONLINE STEP: run on a machine that can reach dashboard.dghs.gov.bd.
    python scripts/01_extract_dghs_district_2026.py                    # download (resumable) + extract
    python scripts/01_extract_dghs_district_2026.py --list-only        # just list the PDFs needed
    python scripts/01_extract_dghs_district_2026.py --end 2026-10-18   # fix the last Sunday explicitly
Only URLs copied verbatim from the official DGHS listing pages (data_raw/verified_dghs_links.csv) are requested;
no URL is constructed. Releases without a verified link must be placed in data_raw/dghs_pdfs_manual/.
Each PDF's printed release date must match its filename, otherwise it is rejected.
Downloads: (30 s connect, 300 s read) timeouts, 6 attempts per URL with exponential backoff (5..300 s, jitter),
write to .part then atomic rename, valid PDFs are never downloaded again, PDFs placed manually in
data_raw/dghs_pdfs_manual/ are used before any network request. Logs: dghs_download_log.csv, dghs_parse_log.csv.
Exit code 2 if any required date is still missing (so run_all.py stops before rebuilding with gaps).

Alignment rule (verified on 25 Oct 2026): the panel value for the ISO week starting Monday M equals
cum_total(press release dated M+6, Sunday) - cum_total(release dated M-1). Example: the 06/07/2026 release
minus its 24-hour column reproduced the panel cumulative of week 2026-06-29 exactly for all 64 districts
(national 6,871). If a Sunday release is missing, cum(Sunday) = cum_total(Monday) - 24h_total(Monday);
otherwise the week is left missing (never interpolated).

Every parsed PDF must pass internal checksums (components = district totals; districts = division totals;
divisions + Dhaka metro = national). Any failure stops the run for that PDF and is logged.
"""
import re, sys, json, argparse, datetime as dt, pathlib

BN = str.maketrans('০১২৩৪৫৬৭৮৯', '0123456789')

# Serial numbers printed in the district table (verified on the 06/07/2026 release).
SERIAL = {1: 'Dhaka', 2: 'Faridpur', 3: 'Faridpur', 4: 'Gazipur', 5: 'Gazipur', 6: 'Gopalganj', 7: 'Kishoreganj',
          8: 'Kishoreganj', 9: 'Madaripur', 10: 'Manikganj', 11: 'Manikganj', 12: 'Munshiganj', 13: 'Narayanganj',
          14: 'Narsingdi', 15: 'Rajbari', 16: 'Shariatpur', 17: 'Tangail', 18: 'Tangail', 19: 'Mymensingh',
          20: 'Jamalpur', 21: 'Sherpur', 22: 'Netrokona', 24: 'Chattogram', 35: 'Chattogram', 25: "Cox's Bazar",
          28: 'Bandarban', 26: 'Rangamati', 27: 'Khagrachhari', 29: 'Feni', 33: 'Noakhali', 30: 'Cumilla',
          36: 'Cumilla', 31: 'Chandpur', 32: 'Lakshmipur', 34: 'Brahmanbaria', 37: 'Khulna', 38: 'Bagerhat',
          39: 'Satkhira', 40: 'Jashore', 41: 'Jhenaidah', 42: 'Magura', 43: 'Narail', 44: 'Kushtia',
          45: 'Chuadanga', 46: 'Meherpur', 48: 'Rajshahi', 49: 'Chapainawabganj', 50: 'Naogaon', 51: 'Natore',
          52: 'Joypurhat', 53: 'Bogura', 54: 'Sirajganj', 55: 'Pabna', 59: 'Rangpur', 60: 'Lalmonirhat',
          61: 'Kurigram', 62: 'Nilphamari', 63: 'Dinajpur', 64: 'Gaibandha', 65: 'Thakurgaon', 66: 'Panchagarh',
          69: 'Barishal', 70: 'Patuakhali', 71: 'Patuakhali', 72: 'Bhola', 73: 'Pirojpur', 74: 'Barguna',
          75: 'Jhalokati', 77: 'Sylhet', 78: 'Sunamganj', 79: 'Habiganj', 80: 'Moulvibazar'}
DIVISION_ORDER = ['Dhaka', 'Mymensingh', 'Chattogram', 'Khulna', 'Rajshahi', 'Rangpur', 'Barishal', 'Sylhet']
FIELDS = ['h24_gov', 'h24_pvt', 'h24_total', 'cum_total', 'cum_death', 'discharged', 'current']


def _ints(tok):
    t = tok.translate(BN).replace(',', '')
    return int(t) if re.fullmatch(r'\d+', t) else None


def data_groups(text):
    """Yield (serial or None, 7-tuple) for every line whose trailing integer run has length exactly 7."""
    pending = None
    for raw in text.splitlines():
        if raw.lstrip().startswith('#'):
            continue
        toks = raw.split()
        if not toks:
            continue
        vals = [_ints(t) for t in toks]
        k = 0
        while k < len(vals) and vals[-1 - k] is not None:
            k += 1
        lead = vals[0] if vals and vals[0] is not None and len(toks) > 1 and vals[1] is None else None
        if k == 7:
            serial = lead if lead is not None else pending
            pending = None
            yield serial, tuple(vals[-7:])
        elif lead is not None and k == 0:
            pending = lead          # serial printed on a line of its own (numbers on a later line)


def add(a, b):
    return tuple(x + y for x, y in zip(a, b))


def parse_district_table(text):
    groups = list(data_groups(text))
    if not groups:
        raise ValueError('no 7-column data groups found')
    metro = groups[0][1]
    out, div_totals = {}, []
    comps, cur, div_sum = [], None, (0,) * 7
    div_districts = []

    def close_district():
        nonlocal comps, cur, div_sum
        if cur is not None and comps:
            tot = comps[0]
            for c in comps[1:]:
                tot = add(tot, c)
            out[cur] = tot
            div_sum = add(div_sum, tot)
            div_districts.append(cur)
        comps, cur = [], None

    for serial, g in groups[1:]:
        if serial is not None and serial in SERIAL:
            name = SERIAL[serial]
            if name != cur:
                close_district()
                cur = name
            comps.append(g)
            continue
        if serial is not None:
            raise ValueError(f'unknown serial {serial}: DGHS table layout changed')
        # non-serial: district total, division total, national totals, or an unnumbered MCH component
        if cur is not None and len(comps) >= 2:
            s = comps[0]
            for c in comps[1:]:
                s = add(s, c)
            if s == g:
                comps = [g]          # collapse to the printed total
                continue
        tentative = div_sum
        if cur is not None and comps:
            t = comps[0]
            for c in comps[1:]:
                t = add(t, c)
            tentative = add(div_sum, t)
        if cur is not None or div_districts:
            if tentative == g and len(div_totals) < 8:
                close_district()
                div_totals.append(g)
                div_sum, div_districts = (0,) * 7, []
                continue
        if cur is not None:
            comps.append(g)          # unnumbered component (e.g. medical college hospital row)
            continue
        div_totals.append(('TAIL', g))
    close_district()
    real_div = [d for d in div_totals if not (isinstance(d, tuple) and len(d) == 2 and d[0] == 'TAIL')]
    tails = [d[1] for d in div_totals if isinstance(d, tuple) and len(d) == 2 and d[0] == 'TAIL']
    if len(real_div) != 8:
        raise ValueError(f'expected 8 division totals, found {len(real_div)}')
    outside = real_div[0]
    for d in real_div[1:]:
        outside = add(outside, d)
    national = add(outside, metro)
    if not tails or tails[-1] != national:
        raise ValueError('national total does not equal divisions + Dhaka metro')
    out['Dhaka'] = add(out['Dhaka'], metro)          # panel convention: Dhaka = Dhaka metro + rest of Dhaka district
    if len(out) != 64:
        raise ValueError(f'expected 64 districts, parsed {len(out)}')
    s = (0,) * 7
    for v in out.values():
        s = add(s, v)
    if s != national:
        raise ValueError('sum of 64 districts does not equal national total')
    return {k: dict(zip(FIELDS, v)) for k, v in out.items()}, dict(zip(FIELDS, national))


def pdf_text(path):
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        return '\n'.join((p.extract_text() or '') for p in pdf.pages)


def first_district_table_line(text):
    """Return text from the first line carrying a 7-integer trailing run (the district table)."""
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        vals = [_ints(t) for t in ln.split()]
        k = 0
        while k < len(vals) and vals[-1 - k] is not None:
            k += 1
        if k == 7:
            return '\n'.join(lines[max(0, i):])
    return ''


# =====================================================================================================
# Robust downloader (v2, 25 Oct 2026). Parser above is unchanged; protocol and definitions are unchanged.
# =====================================================================================================
import csv, random, time

VERIFIED_LINKS = pathlib.Path('data_raw/verified_dghs_links.csv')


def load_verified_links(path=VERIFIED_LINKS):
    """Only URLs copied verbatim from the official DGHS listing pages are used; no URL is constructed."""
    out = {}
    if pathlib.Path(path).exists():
        with open(path, newline='') as f:
            for r in csv.DictReader(f):
                if r['verification'] == 'VERIFIED' and r['url']:
                    out[dt.date.fromisoformat(r['date'])] = r['url']
    return out


HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
           'Accept': 'application/pdf,*/*', 'Referer': 'https://dghs.gov.bd/'}
CONNECT_TIMEOUT, READ_TIMEOUT = 30, 300
MIN_BYTES = 20_000
DEBUG_DIR = pathlib.Path('data_raw/dghs_debug')


def pdf_problem(p):
    """Return None if `p` is a complete PDF, otherwise the exact reason it is not."""
    p = pathlib.Path(p)
    if not p.exists():
        return 'file not found'
    size = p.stat().st_size
    if size < MIN_BYTES:
        return f'file too small ({size} bytes)'
    with open(p, 'rb') as f:
        head = f.read(5)
        f.seek(max(0, size - 65536)); tail = f.read()
    if head != b'%PDF-':
        return f'not a PDF (file starts with {head!r}; an HTML error page was probably saved)'
    if b'%%EOF' not in tail:
        return 'PDF has no end-of-file marker in its last 64 kB (download incomplete)'
    return None


def valid_pdf(p):
    return pdf_problem(p) is None


# ---------------------------------------------------------------- text extraction (parser itself is unchanged)
def text_candidates(path):
    """Yield (extractor_name, text). pdfplumber first (as before); pypdf and pdftotext only as fallbacks.
    Whatever extractor is used, the text must pass the same parser and the same checksums."""
    errors = []
    try:
        yield 'pdfplumber', pdf_text(path)
    except Exception as e:
        errors.append(f'pdfplumber: {type(e).__name__}: {e}')
    try:
        from pypdf import PdfReader
        yield 'pypdf', '\n'.join((pg.extract_text() or '') for pg in PdfReader(str(path)).pages)
    except Exception as e:
        errors.append(f'pypdf: {type(e).__name__}: {e}')
    try:
        import subprocess
        r = subprocess.run(['pdftotext', '-layout', str(path), '-'], capture_output=True, text=True, timeout=120)
        if r.returncode == 0:
            yield 'pdftotext', r.stdout
        else:
            errors.append(f'pdftotext: exit {r.returncode}')
    except Exception as e:
        errors.append(f'pdftotext: {type(e).__name__}: {e}')
    if errors:
        yield 'ERRORS', '; '.join(errors)


def release_date_in_text(text):
    """Date printed inside the release ('তারিখ: dd/mm/yyyy' or 'dd-Mon-yyyy'); None if not found."""
    t = text.translate(BN)
    m = re.search(r'(\d{2})/(\d{2})/(\d{4})', t)
    if m:
        return dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    m = re.search(r'(\d{2})-(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-(\d{4})', t)
    if m:
        return dt.datetime.strptime(m.group(0), '%d-%b-%Y').date()
    return None


def validate_and_parse(path, expected_date):
    """Return (districts, national, extractor, None) on success or (None, None, None, exact_reason) on failure."""
    prob = pdf_problem(path)
    if prob:
        return None, None, None, prob
    reasons = []
    for name, txt in text_candidates(path):
        if name == 'ERRORS':
            reasons.append(txt); continue
        try:
            printed = release_date_in_text(txt)
            if printed is not None and printed != expected_date:
                return None, None, None, (f'wrong file: named {expected_date} but the release inside is dated {printed}')
            dd, nat = parse_district_table(first_district_table_line(txt))
            return dd, nat, name, None
        except Exception as e:
            reasons.append(f'{name}: {e}')
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / f'{expected_date:%Y%m%d}_{name}.txt').write_text(txt, encoding='utf-8')
    return None, None, None, ' | '.join(reasons) + f'  (extracted text saved in {DEBUG_DIR}/ for inspection)'


# ---------------------------------------------------------------- local files first, network only as a last resort
class Downloader:
    def __init__(self, outdir, manual_dir=None, retries=6, base_wait=5.0, max_wait=300.0, pause=2.0, session=None,
                 links=None, allow_network=True):
        self.outdir = pathlib.Path(outdir); self.outdir.mkdir(parents=True, exist_ok=True)
        self.manual_dir = pathlib.Path(manual_dir) if manual_dir else None
        self.retries, self.base_wait, self.max_wait, self.pause = retries, base_wait, max_wait, pause
        self.records, self.allow_network, self._session = [], allow_network, session
        self.links = load_verified_links() if links is None else links

    @property
    def session(self):
        if self._session is None:
            import requests
            self._session = requests.Session(); self._session.headers.update(HEADERS)
        return self._session

    def path(self, d):
        return self.outdir / f'{d:%Y%m%d}_dengue_all.pdf'

    def local(self, d):
        """Existing local copy for date d: manual folder first, then the download cache. Never touches the network.
        Returns (path, source, problem): problem is the exact reason if a local file exists but is invalid."""
        cands = []
        if self.manual_dir is not None:
            cands += [(self.manual_dir / f'{d:%Y%m%d}_dengue_all.pdf', 'manual'), (self.manual_dir / f'{d:%Y%m%d}.pdf', 'manual')]
        cands.append((self.path(d), 'cached'))
        first_problem = None
        for c, src in cands:
            if c.exists():
                prob = pdf_problem(c)
                if prob is None:
                    return c, src, None
                first_problem = first_problem or f'{c}: {prob}'
        return None, None, first_problem

    def download(self, d):
        if not self.allow_network:
            self.records.append(dict(date=str(d), status='network_disabled', url='', attempts=0, bytes=0, error='--no-network'))
            return None
        if d not in self.links:
            self.records.append(dict(date=str(d), status='no_verified_link', url='', attempts=0, bytes=0,
                                     error='place the PDF in the manual folder (see MANUAL_DOWNLOAD.md)'))
            return None
        url, p, last_err = self.links[d], self.path(d), ''
        for k in range(self.retries):
            part = p.with_suffix('.pdf.part')
            try:
                with self.session.get(url, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT), stream=True) as r:
                    if r.status_code in (403, 404):
                        last_err = f'HTTP {r.status_code} (server refused; retrying will not help)'; break
                    if r.status_code != 200:
                        raise IOError(f'HTTP {r.status_code}')
                    with open(part, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=65536):
                            if chunk:
                                f.write(chunk)
                prob = pdf_problem(part)
                if prob:
                    raise IOError(prob)
                part.replace(p)
                self.records.append(dict(date=str(d), status='downloaded', url=url, attempts=k + 1, bytes=p.stat().st_size, error=''))
                time.sleep(self.pause)
                return p
            except Exception as e:
                last_err = f'{type(e).__name__}: {e}'[:300]
                if part.exists():
                    part.unlink()
                wait = min(self.max_wait, self.base_wait * 2 ** k) * random.uniform(0.8, 1.2)
                print(f'    {d} download attempt {k + 1} failed ({last_err[:80]}); retry in {wait:.0f}s', flush=True)
                time.sleep(wait)
        if part.exists():
            part.unlink()
        self.records.append(dict(date=str(d), status='failed', url=url, attempts=k + 1, bytes=0, error=last_err))
        return None

    def get(self, d):
        """Local copy if valid, otherwise a download. Kept for backward compatibility and tests."""
        p, src, prob = self.local(d)
        if p is not None:
            self.records.append(dict(date=str(d), status=src, url=str(p), attempts=0, bytes=p.stat().st_size, error=''))
            return p
        if prob:
            print(f'    local file invalid: {prob}', flush=True)
        return self.download(d)

    def write_log(self, path):
        with open(path, 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=['date', 'status', 'url', 'attempts', 'bytes', 'error'])
            w.writeheader(); w.writerows(self.records)


def required_dates(start, end):
    """Sunday releases needed: the anchor Sunday before `start`, then the Sunday ending each extracted week."""
    sundays = [start - dt.timedelta(days=1)]
    m = start
    while m + dt.timedelta(days=6) <= end:
        sundays.append(m + dt.timedelta(days=6)); m += dt.timedelta(days=7)
    return sundays


class ParseLog:
    """Written to disk after every entry, so a later crash or network stall never loses what was already checked."""
    FIELDS = ['date', 'source_pdf', 'source', 'method', 'extractor', 'status', 'national_cum', 'error']

    def __init__(self, path):
        self.path, self.rows = pathlib.Path(path), []
        self.flush()

    def add(self, **r):
        self.rows.append({k: r.get(k, '') for k in self.FIELDS}); self.flush()

    def flush(self):
        with open(self.path, 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=self.FIELDS); w.writeheader(); w.writerows(self.rows)


def sunday_from_local(s, dl, log):
    """Step 1 (no network): validate and parse the Sunday release from local files."""
    p, src, prob = dl.local(s)
    if p is None:
        reason = prob or 'no local file for this Sunday'
        log.add(date=s, method='direct', status='missing_local', error=reason)
        print(f'  {s}  SUNDAY: not usable locally -> {reason}', flush=True)
        return None
    dd, nat, ex_name, why = validate_and_parse(p, s)
    if dd is None:
        log.add(date=s, source_pdf=p.name, source=src, method='direct', status='failed_validation', error=why)
        print(f'  {s}  SUNDAY {p.name} ({src}) FAILED VALIDATION -> {why}', flush=True)
        return None
    log.add(date=s, source_pdf=p.name, source=src, method='direct', extractor=ex_name, status='ok', national_cum=nat['cum_total'])
    print(f'  {s}  SUNDAY {p.name} ({src}) OK  national cumulative {nat["cum_total"]:,}  [{ex_name}]', flush=True)
    return {k: v['cum_total'] for k, v in dd.items()}


def sunday_via_monday(s, dl, log):
    """Step 2 (only for Sundays that failed step 1): frozen recovery rule cum(Sun) = cum(Mon) - 24h(Mon)."""
    m = s + dt.timedelta(days=1)
    p, src, prob = dl.local(m)
    if p is None:
        if prob:
            print(f'  {s}  MONDAY local file invalid -> {prob}', flush=True)
        print(f'  {s}  trying Monday release {m} from the verified DGHS link', flush=True)
        p, src = dl.download(m), 'downloaded'
    if p is None:
        log.add(date=s, method='next_day_minus_24h', status='missing', error=f'Monday {m} not available')
        print(f'  {s}  MISSING: neither the Sunday nor the Monday ({m}) release is usable', flush=True)
        return None
    dd, nat, ex_name, why = validate_and_parse(p, m)
    if dd is None:
        log.add(date=s, source_pdf=p.name, source=src, method='next_day_minus_24h', status='failed_validation', error=why)
        print(f'  {s}  MONDAY {p.name} FAILED VALIDATION -> {why}', flush=True)
        return None
    log.add(date=s, source_pdf=p.name, source=src, method='next_day_minus_24h', extractor=ex_name, status='ok',
            national_cum=nat['cum_total'] - nat['h24_total'])
    print(f'  {s}  recovered from Monday {p.name}: national cumulative {nat["cum_total"] - nat["h24_total"]:,}', flush=True)
    return {k: v['cum_total'] - v['h24_total'] for k, v in dd.items()}


def check_dependencies():
    missing = []
    for mod in ['pdfplumber']:
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    if missing:
        sys.exit(f'Missing Python package(s): {", ".join(missing)}.  Install with:  pip install {" ".join(missing)} pypdf requests')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--start', default='2026-07-06', help='first Monday to extract')
    ap.add_argument('--end', default=None, help='last Sunday to include (default: yesterday)')
    ap.add_argument('--pdfdir', default='data_raw/dghs_pdfs')
    ap.add_argument('--manual-dir', default='data_raw/dghs_pdfs_manual', help='folder with manually downloaded PDFs')
    ap.add_argument('--out', default='data_raw/dghs_district_week_2026_extension.csv')
    ap.add_argument('--retries', type=int, default=6, help='download attempts for a Monday fallback')
    ap.add_argument('--no-network', action='store_true', help='use local PDFs only; never contact DGHS')
    ap.add_argument('--list-only', action='store_true', help='only write the list of required PDFs and links, then stop')
    a = ap.parse_args()
    start = dt.date.fromisoformat(a.start)
    end = dt.date.fromisoformat(a.end) if a.end else dt.date.today() - dt.timedelta(days=1)
    sundays = required_dates(start, end)
    links = load_verified_links()
    req = pathlib.Path(a.out).with_name('dghs_required_pdfs.csv')
    with open(req, 'w', newline='') as f:
        w = csv.writer(f); w.writerow(['role', 'date', 'save_as', 'verified_link'])
        for s in sundays:
            m = s + dt.timedelta(days=1)
            w.writerow(['sunday_required', s, f'{s:%Y%m%d}_dengue_all.pdf', links.get(s, 'NO VERIFIED LINK: use the live listing page')])
            w.writerow(['monday_fallback_only', m, f'{m:%Y%m%d}_dengue_all.pdf', links.get(m, 'NO VERIFIED LINK: use the live listing page')])
    print(f'required Sunday releases: {len(sundays)} ({sundays[0]} .. {sundays[-1]}); list written to {req}')
    if a.list_only:
        return
    check_dependencies()
    dl = Downloader(a.pdfdir, a.manual_dir, retries=a.retries, links=links, allow_network=not a.no_network)
    log = ParseLog(pathlib.Path(a.out).with_name('dghs_parse_log.csv'))

    print('Step 1: validating and parsing local Sunday PDFs (no network)')
    cums = {s: sunday_from_local(s, dl, log) for s in sundays}
    failed = [s for s in sundays if cums[s] is None]
    if failed:
        print(f'Step 2: Monday recovery for {len(failed)} Sunday release(s): {", ".join(map(str, failed))}')
        for s in failed:
            cums[s] = sunday_via_monday(s, dl, log)
    else:
        print('Step 2: not needed (every Sunday release validated; no Monday release requested)')

    rows, districts = [], sorted(set(SERIAL.values()))
    for prev, cur in zip(sundays[:-1], sundays[1:]):
        monday = prev + dt.timedelta(days=1)
        for dname in districts:
            v = None if (cums[cur] is None or cums[prev] is None) else cums[cur][dname] - cums[prev][dname]
            qc = '' if v is not None and v >= 0 else ('negative_difference' if v is not None else 'missing_release')
            rows.append({'district': dname, 'week_start': str(monday), 'new_cases': v, 'qc_issue': qc})
    with open(a.out, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['district', 'week_start', 'new_cases', 'qc_issue']); w.writeheader(); w.writerows(rows)
    dl.write_log(pathlib.Path(a.out).with_name('dghs_download_log.csv'))
    neg = sum(r['qc_issue'] == 'negative_difference' for r in rows)
    ok = [s for s in sundays if cums[s] is not None]; bad = [str(s) for s in sundays if cums[s] is None]
    weeks_ok = sum(1 for p, c in zip(sundays[:-1], sundays[1:]) if cums[p] is not None and cums[c] is not None)
    print(f'Sunday cumulatives obtained: {len(ok)}/{len(sundays)}; complete weeks: {weeks_ok}/{len(sundays) - 1}; '
          f'negative district differences: {neg}; output: {a.out}')
    if bad or neg:
        if bad:
            print('MISSING dates (see dghs_parse_log.csv for the exact reasons):', ', '.join(bad))
        sys.exit(2)


if __name__ == '__main__':
    main()
