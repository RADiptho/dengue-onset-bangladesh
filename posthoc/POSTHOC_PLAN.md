# Post-hoc analysis plan (written before any post-hoc model was fitted)

Status: EXPLORATORY. The pre-registered results (FINAL_RESULTS_AUDIT) stand unchanged and are reported separately.

## Candidates (all evaluated; none dropped)
Benchmarks: persistence; hhh4 (frozen implementation).
- C1 hhh4_src: official surveillance weight normalisation (source-normalised power law)
- C2 hhh4_cov: hhh4 + covariates (endemic: log population density; AR: 4-week temperature anomaly lag 1 and 8-week rain anomaly lag 1; NE: log population of the receiving district)
- C3 hhh4_online: frozen hhh4 refitted every 4 weeks within the test year on all counts observed by the issue week
- C4 lgbm_online: frozen LightGBM refitted every 4 weeks within the test year on labels whose windows are complete by the issue week (fold's configuration kept)
- C5 hybrid_stack: LightGBM + hhh4 features (onset probability, expected next-week incidence); training-row hhh4 features are out-of-sample (season-wise expanding fits)
- C6 ens_hhh4_lgbm: equal-weight mean of hhh4 and LightGBM probabilities; C6b ens_hhh4_persist: equal-weight mean of hhh4 and persistence probabilities
- C7 logit_compact: L2 logistic regression (C=0.1, standardised) on compact features
- C8 lgbm_balanced: LightGBM with scale_pos_weight = negatives/positives (rare-event weighting)

Fixed settings (no tuning on test folds): equal ensemble weights; refit every 4 weeks; seeds as in the frozen engine; S = 400 simulations.

## Evaluation
Development folds F2023-F2025, h = 4 (primary); AUPRC, Brier, calibration slope, O/E, event Capture@5/10/20 and exploratory lead>=2 capture.
Comparisons with hhh4 and persistence: same bootstraps as the pre-registered analysis.

## Selection and optimism control
Nested leave-one-fold-out: for each held-out fold, choose the candidate with the highest mean AUPRC on the other two folds (tie-break Capture@10);
report its held-out performance against hhh4. The overall "strongest" model = highest pooled development AUPRC.
That single model is then scored on the 2026 locked period, labelled post hoc (2026 outcomes were already seen for the frozen models).

## Additional scientific analyses
A1 hhh4 component decomposition by season (endemic / within-district / between-district shares; spatial decay) - regime-shift mechanism
A2 metric diagnostics: random floor and ceiling per definition, stricter capture variants
A3 power analysis: onset events needed to detect the observed capture/AUPRC differences
