# DGHS 2026 district data: verified download list

Nothing here changes the frozen protocol, the outcome definitions or the Sunday/Monday recovery rule.
The extractor now requests only links copied verbatim from the official DGHS listing pages; it never builds a URL.

## 1. What was verified (25 October 2026)

**Archive page (releases up to 03/09/2026):** https://dghs.gov.bd/pages/static-pages/dengue-press-release-gxrgtg-6a9eb4cc7a024513d1b8c896
was re-read today. Every link below is copied verbatim from it. Three releases were opened in full:
- 05/07/2026: national cumulative 6,871, identical to the panel's week 2026-06-29;
- 06/07/2026: all 64 district values reproduced;
- 30/08/2026: district table present, national cumulative 34,683.

**Live listing (releases from 04/09/2026):** https://dghs.gov.bd/pages/miscellaneous-infos?filters=%7B%22miscellaneous_info_type%22%3A%226a9cf0471fa8cd87d1f50227%22%7D
could not be retrieved from the verification environment. Links for those dates are therefore **not** given.
The `/webportal/osource/...` path you tried is not a link I can verify, and it should not be guessed.

## 2. Required Sunday releases (save into data_raw/dghs_pdfs_manual/)

| Release date | Save as (exact filename) | Verified link | Verification |
|---|---|---|---|
| 2026-07-05 | 20260705_dengue_all.pdf | https://dashboard.dghs.gov.bd/osource/images/docs/vpr/20260705_dengue_all.pdf | opened; district table parsed; national cumulative 6,871 (= panel week 2026-06-29) |
| 2026-07-12 | 20260712_dengue_all.pdf | https://dashboard.dghs.gov.bd/osource/images/docs/vpr/20260712_dengue_all.pdf | listed verbatim on official DGHS archive page (re-checked 25 Oct 2026) |
| 2026-07-19 | 20260719_dengue_all.pdf | https://dashboard.dghs.gov.bd/osource/images/docs/vpr/20260719_dengue_all.pdf | listed verbatim on official DGHS archive page (re-checked 25 Oct 2026) |
| 2026-07-26 | 20260726_dengue_all.pdf | https://dashboard.dghs.gov.bd/osource/images/docs/vpr/20260726_dengue_all.pdf | listed verbatim on official DGHS archive page (re-checked 25 Oct 2026) |
| 2026-08-02 | 20260802_dengue_all.pdf | https://dashboard.dghs.gov.bd/osource/images/docs/vpr/20260802_dengue_all.pdf | listed verbatim on official DGHS archive page (re-checked 25 Oct 2026) |
| 2026-08-09 | 20260809_dengue_all.pdf | https://dashboard.dghs.gov.bd/osource/images/docs/vpr/20260809_dengue_all.pdf | listed verbatim on official DGHS archive page (re-checked 25 Oct 2026) |
| 2026-08-16 | 20260816_dengue_all.pdf | https://dashboard.dghs.gov.bd/osource/images/docs/vpr/20260816_dengue_all.pdf | listed verbatim on official DGHS archive page (re-checked 25 Oct 2026) |
| 2026-08-23 | 20260823_dengue_all.pdf | https://dashboard.dghs.gov.bd/osource/images/docs/vpr/20260823_dengue_all.pdf | listed verbatim on official DGHS archive page (re-checked 25 Oct 2026) |
| 2026-08-30 | 20260830_dengue_all.pdf | https://dashboard.dghs.gov.bd/osource/images/docs/vpr/20260830_dengue_all.pdf | opened; district table present; national cumulative 34,683 |
| 2026-09-06 | 20260906_dengue_all.pdf | not verified: copy from the live listing page | release after 03/09/2026; listed only on the live page, which could not be retrieved; take the link from the page |
| 2026-09-13 | 20260913_dengue_all.pdf | not verified: copy from the live listing page | release after 03/09/2026; listed only on the live page, which could not be retrieved; take the link from the page |
| 2026-09-20 | 20260920_dengue_all.pdf | not verified: copy from the live listing page | release after 03/09/2026; listed only on the live page, which could not be retrieved; take the link from the page |
| 2026-09-27 | 20260927_dengue_all.pdf | not verified: copy from the live listing page | release after 03/09/2026; listed only on the live page, which could not be retrieved; take the link from the page |
| 2026-10-04 | 20261004_dengue_all.pdf | not verified: copy from the live listing page | release after 03/09/2026; listed only on the live page, which could not be retrieved; take the link from the page |
| 2026-10-11 | 20261011_dengue_all.pdf | not verified: copy from the live listing page | release after 03/09/2026; listed only on the live page, which could not be retrieved; take the link from the page |
| 2026-10-18 | 20261018_dengue_all.pdf | not verified: copy from the live listing page | release after 03/09/2026; listed only on the live page, which could not be retrieved; take the link from the page |

## 3. Monday releases (only needed if a Sunday release is missing or fails its checks)

Frozen recovery rule: cumulative(Sunday) = cumulative(Monday) minus the Monday release's 24-hour column.

| Release date | Save as (exact filename) | Verified link | Verification |
|---|---|---|---|
| 2026-07-06 | 20260706_dengue_all.pdf | https://dashboard.dghs.gov.bd/osource/images/docs/vpr/20260706_dengue_all.pdf | opened; district table parsed; reproduced all 64 panel districts |
| 2026-07-13 | 20260713_dengue_all.pdf | https://dashboard.dghs.gov.bd/osource/images/docs/vpr/20260713_dengue_all.pdf | listed verbatim on official DGHS archive page (re-checked 25 Oct 2026) |
| 2026-07-20 | 20260720_dengue_all.pdf | https://dashboard.dghs.gov.bd/osource/images/docs/vpr/20260720_dengue_all.pdf | listed verbatim on official DGHS archive page (re-checked 25 Oct 2026) |
| 2026-07-27 | 20260727_dengue_all.pdf | https://dashboard.dghs.gov.bd/osource/images/docs/vpr/20260727_dengue_all.pdf | listed verbatim on official DGHS archive page (re-checked 25 Oct 2026) |
| 2026-08-03 | 20260803_dengue_all.pdf | https://dashboard.dghs.gov.bd/osource/images/docs/vpr/20260803_dengue_all.pdf | listed verbatim on official DGHS archive page (re-checked 25 Oct 2026) |
| 2026-08-10 | 20260810_dengue_all.pdf | https://dashboard.dghs.gov.bd/osource/images/docs/vpr/20260810_dengue_all.pdf | listed verbatim on official DGHS archive page (re-checked 25 Oct 2026) |
| 2026-08-17 | 20260817_dengue_all.pdf | https://dashboard.dghs.gov.bd/osource/images/docs/vpr/20260817_dengue_all.pdf | listed verbatim on official DGHS archive page (re-checked 25 Oct 2026) |
| 2026-08-24 | 20260824_dengue_all.pdf | https://dashboard.dghs.gov.bd/osource/images/docs/vpr/20260824_dengue_all.pdf | listed verbatim on official DGHS archive page (re-checked 25 Oct 2026) |
| 2026-08-31 | 20260831_dengue_all.pdf | https://dashboard.dghs.gov.bd/osource/images/docs/vpr/20260831_dengue_all.pdf | listed verbatim on official DGHS archive page (re-checked 25 Oct 2026) |
| 2026-09-07 | 20260907_dengue_all.pdf | not verified: copy from the live listing page | release after 03/09/2026; listed only on the live page, which could not be retrieved; take the link from the page |
| 2026-09-14 | 20260914_dengue_all.pdf | not verified: copy from the live listing page | release after 03/09/2026; listed only on the live page, which could not be retrieved; take the link from the page |
| 2026-09-21 | 20260921_dengue_all.pdf | not verified: copy from the live listing page | release after 03/09/2026; listed only on the live page, which could not be retrieved; take the link from the page |
| 2026-09-28 | 20260928_dengue_all.pdf | not verified: copy from the live listing page | release after 03/09/2026; listed only on the live page, which could not be retrieved; take the link from the page |
| 2026-10-05 | 20261005_dengue_all.pdf | not verified: copy from the live listing page | release after 03/09/2026; listed only on the live page, which could not be retrieved; take the link from the page |
| 2026-10-12 | 20261012_dengue_all.pdf | not verified: copy from the live listing page | release after 03/09/2026; listed only on the live page, which could not be retrieved; take the link from the page |
| 2026-10-19 | 20261019_dengue_all.pdf | not verified: copy from the live listing page | release after 03/09/2026; listed only on the live page, which could not be retrieved; take the link from the page |

## 4. How to obtain the releases dated 06/09/2026 to 18/10/2026

1. **Live listing page.** Open the live listing above in a desktop browser. Each row has a title such as
   "ডেঙ্গু প্রেস রিলিজ (০৬/০৯/২০২৬)", a file link and a publish date. Click the file link in that row (do not type a URL).
   If it opens a PDF, save it under the exact filename in the table (e.g. `20260906_dengue_all.pdf`).
   If the row's own link returns "not found", record that date as unavailable from the live page and go to step 2.
2. **Internet Archive.** Search https://web.archive.org for the live listing page URL and for the exact file link shown in
   the listing row. Use a snapshot only if it is the original PDF; it must pass the same checks below.
3. **DGHS directly.** Request the daily press-release PDFs for the missing dates from the DGHS Health Emergency Operation
   Centre & Control Room (controlroomdghs@yahoo.com; 02-222285933 / 02-222297353, as printed on every release).

Every PDF, from any source, is accepted only if:
- its printed release date equals the date in its filename (wrong files are rejected automatically);
- its 64 district values sum exactly to the division totals and to the national total.

## 5. Run

    pip install pdfplumber pypdf requests
    python scripts/01_extract_dghs_district_2026.py --end 2026-08-30 --no-network   # 9 verified Sundays, local only
    python scripts/01_extract_dghs_district_2026.py --end 2026-10-18                # once all 16 Sundays are in the folder

Step 1 validates and parses every local Sunday PDF with no network access and prints OK or the exact reason for failure.
Step 2 (Monday recovery) runs only for Sundays that failed step 1. With --no-network it never contacts DGHS.

Logs: `data_raw/dghs_download_log.csv` and `data_raw/dghs_parse_log.csv`.

## 6. If the September–October releases cannot be obtained

Do not interpolate. Run with `--end 2026-08-30`. This uses the 9 verified Sunday releases (8 complete weeks,
6 July to 30 August 2026). Under the frozen protocol, the locked period then ends at the last issue week whose
outcome window lies inside the extracted data; `build_manifest.json` records this automatically before any modelling.

Report it as a truncated locked test, with the reason, in the paper. The peak months, September and October, would then be
outside the locked test, and that limitation must be stated.
