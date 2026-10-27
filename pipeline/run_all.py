"""Reproduce the pre-modelling package.
  python run_all.py            offline: build V2, national layer, reports, audit (development layer)
  python run_all.py --online [--end 2026-10-18]   also extract the 2026 district extension (DGHS PDFs) and refetch NASA POWER climate,
                               then rebuild and re-audit. Requires internet access to dashboard.dghs.gov.bd and
                               power.larc.nasa.gov, plus: pip install pdfplumber requests pandas numpy statsmodels
"""
import subprocess, sys
# If script 01 exits with code 2, some DGHS dates are still missing: the run stops BEFORE rebuilding.
# Re-run later (valid PDFs are kept and never re-downloaded) or follow MANUAL_DOWNLOAD.md.
S = [sys.executable]
online = '--online' in sys.argv
steps = []
if online:
    end = [sys.argv[sys.argv.index('--end') + 1]] if '--end' in sys.argv else []
    steps += [['scripts/01_extract_dghs_district_2026.py'] + (['--end'] + end if end else []),
              ['scripts/02_fetch_nasa_power.py'] + (['--end'] + end if end else [])]
steps = [['tests/test_extractor.py'], ['tests/test_downloader.py'], ['tests/test_local_first.py'], ['tests/test_power_fetch.py']] + steps
steps += [ ['scripts/03_build_master_v2.py'], ['scripts/04_build_national_long.py'],
          ['scripts/05_reports.py'], ['scripts/07_rowlevel_diff.py'], ['scripts/06_premodel_audit.py']]
for s in steps:
    print('>>', s[0]); subprocess.run(S + s, check=True)
