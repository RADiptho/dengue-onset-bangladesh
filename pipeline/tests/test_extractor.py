import importlib.util, pandas as pd, pathlib, re
spec = importlib.util.spec_from_file_location('ex', 'scripts/01_extract_dghs_district_2026.py'); ex = importlib.util.module_from_spec(spec); spec.loader.exec_module(ex)
txt = pathlib.Path('tests/fixture_20260706_district_table.txt').read_text()
d, nat = ex.parse_district_table(txt)
assert nat['cum_total'] == 7110 and nat['h24_total'] == 239
# variant: serial printed on its own line, numbers on the next line (as in the real PDF for MCH rows)
lines = []
for ln in txt.splitlines():
    m = re.match(r'^(3|4|8|11|18|35|36|71) X X (.*)$', ln)
    if m: lines += [f'{m.group(1)} X', 'X X', m.group(2)]
    else: lines.append(ln)
d2, _ = ex.parse_district_table('\n'.join(lines))
assert d2 == d, 'split-serial layout parsed differently'
# Bangla digits
assert ex._ints('৭১১০') == 7110 and ex._ints('7,110') == 7110
# reproduce the panel's 2026-06-29 cumulative (= release 06/07 minus its 24h column) for all 64 districts
panel = pd.read_csv('data_raw/figshare_district_week_master_audit.csv', parse_dates=['week_start'])
p = panel[panel.week_start == '2026-06-29'].set_index('district').cumulative_cases
mism = {k: (v['cum_total'] - v['h24_total'], int(p[k])) for k, v in d.items() if v['cum_total'] - v['h24_total'] != p[k]}
assert not mism, mism
print('extractor tests passed: 64/64 districts reproduce the panel cumulative of week 2026-06-29; national 6871')
