"""End-to-end test of the local-first flow with real PDF files (built from the 06/07/2026 fixture table), --no-network."""
import subprocess, sys, tempfile, pathlib, shutil, csv, re
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
FIX = pathlib.Path('tests/fixture_20260706_district_table.txt').read_text().splitlines()
TABLE = [l for l in FIX if l and not l.startswith('#')]

def make_pdf(path, date_ddmmyyyy, bump=0):
    c = canvas.Canvas(str(path), pagesize=A4); y = 800
    c.drawString(40, y, f'Date {date_ddmmyyyy} Daily Dengue Press Release'); y -= 14
    c.drawString(40, y, 'Age Group Male Female Total'); y -= 14
    for line in TABLE:
        toks = line.split()
        if bump:  # add `bump` to cum_total (4th of the trailing 7 numbers) everywhere: keeps every checksum valid
            nums = [t for t in toks if re.fullmatch(r'\d+', t)]
            if len(nums) >= 7:
                lead = toks[:len(toks) - 7]; tail = [int(x) for x in toks[-7:]]
                n_rows = 1
                tail[3] += bump
                toks = lead + [str(x) for x in tail]
        c.drawString(40, y, ' '.join(toks)); y -= 12
        if y < 40: c.showPage(); y = 800
    c.drawString(40, 20, 'x' * 2000); c.save()
    data = path.read_bytes()
    if len(data) < 20000:  # pad (after %%EOF stays within last 64 kB) so the size check reflects real releases
        path.write_bytes(data + b'\n%' + b' ' * (20000 - len(data)) + b'\n%%EOF\n')

t = pathlib.Path(tempfile.mkdtemp()); man = t / 'manual'; man.mkdir()
shutil.copytree('data_raw', t / 'data_raw', ignore=shutil.ignore_patterns('dghs_pdfs*'))
make_pdf(man / '20260705_dengue_all.pdf', '05/07/2026')
make_pdf(man / '20260712_dengue_all.pdf', '12/07/2026')
(man / '20260719_dengue_all.pdf').write_bytes(b'<html>403 Forbidden</html>' + b' ' * 30000)   # bad Sunday
make_pdf(man / '20260726_dengue_all.pdf', '19/07/2026')                                        # wrong date inside
script = pathlib.Path('scripts/01_extract_dghs_district_2026.py').resolve()
r = subprocess.run([sys.executable, str(script), '--end', '2026-07-26', '--no-network', '--manual-dir', str(man),
                    '--pdfdir', str(t / 'pdfs'), '--out', str(t / 'data_raw' / 'ext.csv')], cwd=t, capture_output=True, text=True)
print(r.stdout)
assert r.returncode == 2
log = list(csv.DictReader(open(t / 'data_raw' / 'dghs_parse_log.csv')))
st = {(x['date'], x['method']): x for x in log}
assert st[('2026-07-05', 'direct')]['status'] == 'ok' and st[('2026-07-12', 'direct')]['status'] == 'ok'
assert 'not a PDF' in st[('2026-07-19', 'direct')]['error']
assert 'wrong file' in st[('2026-07-26', 'direct')]['error']
assert ('2026-07-05', 'next_day_minus_24h') not in st and ('2026-07-12', 'next_day_minus_24h') not in st  # no Monday for good Sundays
dl = list(csv.DictReader(open(t / 'data_raw' / 'dghs_download_log.csv')))
assert {x['date'] for x in dl} == {'2026-07-20', '2026-07-27'} and all(x['status'] == 'network_disabled' for x in dl)
rows = list(csv.DictReader(open(t / 'data_raw' / 'ext.csv')))
w1 = [x for x in rows if x['week_start'] == '2026-07-06']
assert len(w1) == 64 and all(x['new_cases'] == '0' and x['qc_issue'] == '' for x in w1)
print('local-first tests passed: valid Sundays parsed without any network call; invalid Sunday reasons reported; Monday requested only for failed Sundays')
shutil.rmtree(t)
