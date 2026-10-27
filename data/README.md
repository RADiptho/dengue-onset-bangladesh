# Data

No data are committed to this repository. Place the input files as follows before running the code.

## `pipeline/data_raw/` (11 files)

| File | Content |
|---|---|
| `figshare_district_week_master_audit.csv` | District-week dengue panel with audit fields (Figshare deposit) |
| `figshare_model_ready_original.csv` | Model-ready district-week panel (Figshare deposit) |
| `districts.csv` | District reference: identifier, name, division, centroid |
| `edges_static.csv` | Shared-border adjacency and centroid distances |
| `holiday_calendar.csv` | Festival calendar used for calendar predictors |
| `dghs_district_week_2026_extension.csv` | 2026 district-week extension from DGHS daily press releases |
| `dghs_required_pdfs.csv`, `verified_dghs_links.csv` | DGHS press-release inventory used by the 2026 extraction |
| `reporting_structure_dghs_2026.csv` | Reporting-structure indicators (ablation only) |
| `nasa_power_daily.csv` | Daily NASA POWER climate at district centroids |
| `opendengue_v1_3_bangladesh_rows.csv` | OpenDengue v1.3 national rows for Bangladesh |

Sources: the Figshare dataset (https://doi.org/10.6084/m9.figshare.33040637, CC BY 4.0); DGHS daily dengue press releases (https://dghs.gov.bd/); NASA POWER (https://power.larc.nasa.gov/); OpenDengue (https://opendengue.org/).

The 2026 extension and the NASA POWER file can be rebuilt with `python run_all.py --online` from `pipeline/` (requires internet access); see `pipeline/MANUAL_DOWNLOAD.md` if DGHS downloads fail. The processed analysis dataset is available from the corresponding author on reasonable request.

## `data/boundaries/`

Bangladesh administrative boundaries from OCHA/HDX COD-AB (https://data.humdata.org/dataset/cod-ab-bgd; CC BY 3.0 IGO), levels 0 to 2 as shapefiles named `bgd_admin0.shp`, `bgd_admin1.shp` and `bgd_admin2.shp` (with their `.dbf`, `.shx`, `.prj` and `.cpg` companions). Used only for maps and the spatial-autocorrelation analysis.

## `data/lookup/` (committed)

| File | Content |
|---|---|
| `district_crosswalk_panel_to_OCHA_ADM2.csv` | Mapping of the 64 panel district names to OCHA ADM2 codes |
| `adjacency_check_panel_vs_OCHA.csv` | Comparison of panel adjacency with OCHA polygon contiguity |
