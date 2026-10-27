# Descriptive hotspot analysis: definitions (fixed before the final computation)

Status: descriptive epidemiology, added after the forecasting results were frozen; it does not use or change any forecast.
Data: frozen master_dataset_v2.csv; cases_obs (QC-masked weeks excluded); full seasons 2022, 2023, 2024, 2025.

1. Incidence. Annualised incidence per 100,000 = mean weekly incidence over each district's observed weeks in 2022-2025 x 52.18.
   (Correction to the earlier preview: total cases / 4 understated the 7 districts masked throughout 2022.)
2. Season incidence. The same annualised measure computed within each full season.
3. Recurrent high-incidence district. In the top quintile (13 highest of 64) of season incidence in at least 3 of the full seasons in which
   the district was observed.
4. Onset events. Count of distinct onset events under the frozen primary definition (5/100,000 and at least 10 cases, preceded by 4 observed
   non-outbreak weeks in the same segment), whole panel 2019-08-26 to 2026-08-24. Also reported per 100 at-risk district-weeks.
5. Spatial autocorrelation. Global Moran's I and local Moran's I (LISA) on log(1 + annualised incidence); row-standardised weights
   from the modelling adjacency graph; 9,999 conditional permutations, seed 20261025; Benjamini-Hochberg FDR at 0.05.
   Classes: high-high, low-low, high-low, low-high, not significant.
   Robustness: the same analysis with OCHA polygon contiguity (adds Barishal-Chandpur and Barishal-Lakshmipur).
