# Pre-Modelling Package: Frozen Protocol and Audit

Study: *Anticipating Where Dengue Outbreaks Begin: Capacity-Constrained District Onset Forecasting in Bangladesh Before, During and After the Unprecedented 2023 Epidemic.* Frozen 25 October 2026, before any model was fitted. No model has been trained and no performance has been looked at on any fold.

## 1. Readiness verdict

**Development layer (2019, 2022–2025; folds F2023, F2024, F2025): ready.** All 18 automated checks pass. These cover banned columns, segment boundaries, QC masking, future-perturbation invariance, availability lags, fold embargo, brute-force label verification and outcome integrity.

**Locked test (2026): not yet ready.** Two items remain, and both need internet access that the build environment did not have.

1. The district panel ends on 29 June 2026. January to June 2026 contains only 3 primary onset events, so a locked test limited to that period would be uninformative. The July to October 2026 district data exist in DGHS daily press releases. An extractor has been built and validated: it reproduces the panel's week-2026-06-29 cumulative counts exactly for all 64 districts. It still has to be run.
2. The package's climate columns cannot be extended past June 2026 with a known identical method. A uniform NASA POWER refetch for all years has been scripted so that training and locked test share one climate pipeline.

Running `python run_all.py --online` performs both steps, rebuilds V2 and re-runs the audit. Modelling may start on the development folds now. Locked-test scoring may happen only after `outputs/AUDIT_STATUS.json` reports `locked_test_ready: true`.

## 2. Corrections made in Master Dataset V2

| Correction | Rows | Detail |
|---|---|---|
| QC targets masked before feature construction | 741 | Year-boundary reset weeks, the first 2019 week, the November 2025 shift and the 2022 Chattogram misallocation are missing, not zero |
| Case lags no longer bridge 2019 to 2022 | 64 × k per lag k (768 for lag 12) | Rebuilt within segments S2019 and S2022on |
| Lags referencing QC weeks | 741 per lag | Now missing (previously artefact zeros entered predictors) |
| Rolling means | all | Require every week in the window to be observed |
| Neighbour and network features | all | Rebuilt from QC-masked incidence of weeks t and t−1; original nbr_cases and upstream_pressure dropped |
| Climate | all | Lag of at least 1 week, segment-bounded until the refetch |
| CHIRPS, NDVI, NDWI, LST, VIIRS | all | Lags of 3, 2, 2, 2 and 5 weeks; restricted to development-only ablations |
| Festival calendar | 128 | Rebuilt by one rule (week before, of and after each Eid ul-Fitr, Eid ul-Adha and Durga Puja); fixes 2019 Durga Puja, which was coded as one week |

The row-level record is in correction_log_rowlevel_lags.csv. The summary is in correction_log_v2.csv.

## 3. Forecast-issue convention

The issue moment is the Monday after ISO week t ends. Cases of week t are known, because DGHS publishes daily. Climate enters with a lag of at least 1 week, and satellite products with the lags above. Calendar variables, including festival windows in coming weeks, are known in advance. Targets refer to weeks t+1 to t+h. A sensitivity run adds one extra week of reporting delay to every case-derived feature.

## 4. Frozen outcome definitions

**Outbreak week:** weekly incidence of at least 5 per 100,000 and at least 10 cases, in an observed (non-QC) week.

**At risk (quiet) at t:** weeks t−3 to t are observed non-outbreak weeks in the same segment.

**Primary outcome:** for at-risk districts, an outbreak in any of weeks t+1 to t+4. The label is 0 only if all four weeks are observed non-outbreak weeks within the segment; otherwise it is missing.

**Horizons:** 1, 2, 4, 6 and 8 weeks. Primary h = 4; h = 1 is reported but has few events.

**Sensitivity definitions (pre-specified, not tuned):** thresholds of 2 and 10 per 100,000; quiet windows of 6 and 8 weeks; a district-specific 90th-percentile threshold computed on training weeks only (fold_utils). All 45 threshold × quiet-window × horizon combinations are in labels_all_definitions_long.csv.gz.

**Secondary outcomes:**
- hotspot emergence within 4 weeks (outbreak and national top decile of incidence, not a hotspot in the preceding 8 weeks);
- 4-week future cases and incidence, used for burden capture.

**Distinct primary onset events by year:** 2019: 1; 2022: 11; 2023: 48; 2024: 18; 2025: 21; 2026 (to June): 3.

## 5. Frozen folds

Folds are defined by issue week. A training row is admitted only if its entire label window ends before the test period starts (an h-week embargo).

| Fold | Training issue weeks | Test issue weeks | At-risk district-weeks (h=4) | Onset windows (h=4) |
|---|---|---|---|---|
| F2023 (unprecedented year) | 2019 and 2022, embargoed | 2023 | 2,329 | 188 |
| F2024 | to end 2023 | 2024 | 2,891 | 72 |
| F2025 | to end 2024 | 2025 | 2,303 | 81 |
| LOCKED2026 | to end 2025 | 2026-01-05 onward | 1,214 now; extension pending | 12 now |

**Locked period definition.** The locked period runs from 2026-01-05 to the last issue week whose h-week window lies within the extracted data. It is written to build_manifest.json at extraction time, before any modelling.

**2026 is never used for** feature selection, hyperparameters, model selection, thresholds, calibration-method choice or changes to the research question. It is scored once, after everything else is frozen.

**Disclosure.** Earlier descriptive work, including this project's feasibility check and a public GitHub analysis of the same panel, has seen 2026 case counts. No model in this study has been evaluated on 2026.

## 6. Decision-support task (retrospective)

Each issue week, rank the at-risk districts by predicted onset probability. A team can prioritise k = 5, 10 or 20 districts.

**Primary metric: event-level Onset Capture@k.** An onset event counts as captured if its district was in the weekly top k in at least one of the 4 issue weeks preceding onset, which guarantees a lead of at least 1 week (fold_utils.event_capture_at_k).

**Secondary metrics:**
- window-level capture;
- lead time;
- alerts per captured onset;
- false-alert burden (top-k selections with no onset within 4 weeks);
- AUPRC and Brier score;
- calibration slope and intercept;
- an allocation-style curve over k from 1 to 30;
- a random-selection floor and a clairvoyant ceiling.

**Count versus per-capita objective.** Rankings by predicted probability (onset risk) are compared with rankings by expected 4-week cases (burden), using burden capture and per-capita burden capture.

All results are described as retrospective decision-support evaluation. Nothing is claimed about cases prevented.

## 7. Baselines (must be beaten)

1. **Persistence:** rank by inc_mean4_to_lag0.
2. **Seasonal climatology:** training-period onset rate by district and ISO week.
3. **Endemic-only:** logistic regression on district effects plus seasonality, with no epidemic terms.
4. **Neighbour-only rule:** rank by nb_inc_max_lag0.
5. **hhh4 endemic–epidemic model** (R package surveillance), with autoregressive, power-law spatial and endemic seasonal components, fitted on weekly counts. Onset probability is derived by simulation from its predictive distribution.

## 8. Main model

A pooled gradient-boosted classifier (LightGBM), one per horizon. Feature groups:
- own history;
- neighbour and gravity spatial signals;
- national and Dhaka signals;
- climate, with anomalies against training-only climatology;
- calendar;
- static covariates.

Hyperparameters are chosen on an inner forward split inside each training set (the last training season as validation), with a fixed small grid recorded before fitting. A spatiotemporal graph model is admitted only if it beats both hhh4 and the pooled model on the development folds' inner validation; otherwise it is not reported as a main model.

## 9. Calibration and reliability

Platt and isotonic recalibration are fitted on the most recent training season only. The choice between them is made on development folds and frozen before the locked test.

Reported by fold, horizon and regime (2023 vs other years; historically low vs high districts):
- Brier score and its decomposition;
- calibration slope and intercept;
- reliability diagrams.

**Maximum useful warning horizon:** the largest h at which event-level Capture@10 exceeds persistence and the calibration slope lies within 0.8 to 1.2.

## 10. Pre-specified ablations

Each ablation answers one scientific question:
- no spatial features (does spatial information add anything?);
- adjacency only versus adjacency plus gravity (does connectivity beyond borders help?);
- no climate;
- development-only satellite layer added (is satellite information worth its deployment cost?);
- with versus without reporting-structure covariates (is "emergence" partly a reporting artefact?);
- with versus without the national long-layer seasonal prior;
- count versus per-capita ranking objective.

## 11. Sensitivity analyses

- thresholds of 2 and 10 per 100,000;
- quiet windows of 6 and 8 weeks;
- district-specific threshold;
- Dhaka excluded;
- one extra week of reporting delay;
- QC-flagged weeks included;
- Faizunnesa division totals used to check 2019 and 2022 allocations.

## 12. Statistics

- **Differences versus each baseline:** paired week-block bootstrap (2,000 resamples of issue weeks) for differences in Capture@k, AUPRC and Brier score.
- **Contribution of spatial and connectivity features:** permutation test that shuffles the group within week.
- **Multiplicity:** Holm correction across horizons and k.
- **Small samples:** per-fold results are secondary because events are few (18 to 48 per fold); the primary estimate pools the three development folds (87 distinct onset events).

## 13. Datasets obtained versus unavailable

See DATASET_REGISTER.md. In short:
- **SCI:** not usable at district level (published only for 8 divisions); replaced by a documented gravity proxy.
- **Facility counts:** not verifiable from the build environment; replaced by DGHS reporting-structure covariates, with the caveat that the 2026 layout is applied to earlier years.
- **OpenDengue national layer:** built for 2008–2026 (August 2019 digit error corrected).
- **2026 district extension and climate refetch:** scripted and validated, pending the online run.

## 14. Remaining limitations

- Hospitalised cases only.
- No serotype or vector data.
- About five district seasons.
- The 2022 Chattogram-division allocation is unresolved and excluded from primary targets.
- Rows 2019 and 2022 provide little training signal for the 2023 fold (12 onset events). This is intended: the fold tests a system trained on ordinary periods.
- Prior work in the literature (verify Shiddik et al. 2026, cited in a public analysis of this panel) must be checked before novelty claims are finalised.
