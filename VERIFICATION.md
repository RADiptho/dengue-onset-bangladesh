# Verification record

The repository was copied to a clean directory with the input data and run end to end. Each output was compared numerically with the frozen output used in the manuscript.

| Stage | Outputs compared | Result |
|---|---|---|
| Panel and leakage audit | Master panel (16,768 rows, 88 columns); 25 audit checks | Identical content; all checks passed |
| Development models | 319,600 predictions, 8 models, 5 horizons | Identical (largest difference 8e-15) |
| Locked 2026 test | Predictions and event hits | Identical |
| Metrics and statistical tests | Development and locked metrics, bootstrap tests | No value changed at three decimals (largest AUPRC difference 1.5e-4, from floating-point ties) |
| Sensitivity and ablation | 21 sensitivity rows, 7 ablation rows | Identical |
| Hypotheses H2 and H4, SHAP groups, locked tests | Five tables, two JSON files | Identical |
| Post-hoc models | 95,880 development and 20,268 locked predictions | Identical (largest difference 3e-14) |
| Post-hoc evaluation | Pooled, per-fold, tests, nested selection, decomposition | No value changed at three decimals |
| Power analysis, calibration intervals, per-year Holm | Three tables | Identical |
| Audit and coupling | Recomputed headline, season fits, coupling contrasts | Identical |
| Hotspots and maps | Hotspot classification, map values | Identical; map counts for all 64 districts checked against an independent recomputation |
| Robustness | Block bootstrap (4-week blocks), operational, masking, calibration, regimes, start counts | Identical, except pooled block bootstrap (largest difference 5.9e-5, from floating-point ties) |
| Figures | Figures 3 to 7 | Pixel-identical to the manuscript versions; data for Figures 8 to 10 identical |

Block-bootstrap runs with 1-week and 8-week blocks use the same code as the verified 4-week run.

The sensitivity analysis including quality-controlled weeks and the comparison with the R `surveillance` package are not included, because the code that prepared their inputs was not preserved (see README).
