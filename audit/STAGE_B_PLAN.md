# Stage-B plan (written before running; exploratory, separate from pre-registered and post-hoc layers)

B1 Spatial-coupling robustness (claim: between-district coupling rose in 2023-2024).
  Same-mask data (7 Chattogram-cluster districts masked in every season). Models per season:
  M0 frozen form; M1 = M0 + week-specific endemic intercepts (absorbs any nationwide synchronous shock)
  + district endemic covariate (log population density). Inference: cluster-robust (sandwich, clustered by week) SEs.
  Official check: R surveillance::hhh4 on the 57-district network, official weight convention, endemic district random intercepts.
  Claim retained only if the 2023 vs 2022 coupling ratio stays > 1 with 95% CI excluding 1 in M1 AND the official fit agrees in direction.
B2 Within-season effect modification (claim: hhh4's advantage over persistence is linked to spatial pressure).
  Unit: at-risk district-week, development folds pooled, h = 4. Outcome: paired log-loss difference
  d = LL(persistence) - LL(hhh4) (positive = hhh4 better). Exposure: standardised log1p(max neighbour incidence at issue week).
  Model: d ~ exposure + fold fixed effects; week-cluster bootstrap (2,000). Secondary exposure: national incidence.
  Also AUPRC difference within pre-defined exposure tertiles (cut points from pooled at-risk rows).
  Claim retained only if the exposure slope is positive with CI excluding 0.
B3 Multiple testing and wording: Holm across the 16 per-fold AUPRC comparisons; ensemble described by worst-year
  performance and per-year differences, not by non-significance.
No new prediction models (nested selection and power analysis show model search cannot be validated with available events).
