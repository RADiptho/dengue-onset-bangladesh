# Predictability of dengue outbreak onset across epidemic regimes in Bangladesh

Analysis code for the manuscript *Predictability of dengue outbreak onset across epidemic regimes in the districts of Bangladesh: a pre-specified evaluation of persistence, machine learning and spatial endemic-epidemic forecasts* (Diptho, Ghosh and Chowdhury).

The code builds a leakage-audited district-week panel for the 64 districts of Bangladesh (August 2019 to August 2026), defines outbreak onset in quiet districts, and compares persistence, three simple baselines, LightGBM and an hhh4 endemic-epidemic model. Evaluation uses forward validation in 2023, 2024 and 2025 and a locked 2026 test, followed by separately labelled post-hoc analyses.

## Repository structure

| Folder | Content | Analysis status |
|---|---|---|
| `pipeline/` | Data assembly, quality control, 25-check leakage audit | Pre-specified |
| `experiments/` | Models, forward validation, locked 2026 test, metrics, statistical tests, sensitivity and ablation analyses | Pre-specified |
| `posthoc/` | Updated hhh4, ensembles, season decomposition, power and calibration intervals | Post hoc (written plan in `posthoc/POSTHOC_PLAN.md`) |
| `audit/` | Recomputation of headline results, between-district coupling | Post hoc |
| `descriptive/` | Hotspot analysis (Moran's I, LISA) and district maps | Descriptive |
| `robustness/` | Moving-block bootstrap, operational metrics, masking, calibration diagnostics, regime descriptors | Post hoc |
| `figures/` | Manuscript figures | Not applicable |
| `data/` | Data instructions and two small lookup tables; no data committed | Not applicable |

## Installation

Python 3.12 is required.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Data

Place the input files as described in [`data/README.md`](data/README.md).

## Reproducing the analysis

Each step runs from its own folder and reads earlier outputs through repository-relative paths. The approximate runtimes were measured on one CPU core.

```bash
# 1. Panel, quality control and leakage audit (about 40 s)
cd pipeline && python run_all.py && cd ..

# 2. Pre-specified experiments
cd experiments
python run_models.py                 # development folds, all horizons (about 40 s)
python run_locked.py                 # locked 2026 test, scored once (about 20 s)
python evaluate.py                   # metrics and event-level capture (about 30 s)
python stats_tests.py                # bootstrap tests with Holm adjustment (about 4 min)
python ablate_sens.py sensitivity    # sensitivity analyses (about 50 s)
python ablate_sens.py ablation       # LightGBM ablations (about 25 s)
python analysis_extra.py             # hypothesis H2 and H4 analyses, SHAP groups (about 2 min)
python verify.py                     # independent checks and locked tests (about 20 s)
cd ..

# 3. Post-hoc analyses
cd posthoc
python posthoc_run.py dev            # updated hhh4 and ensembles, development (about 1 min)
python posthoc_run.py locked hhh4_online   # the same on the locked period (about 20 s)
python posthoc_eval.py               # post-hoc metrics and tests (about 3 min)
python decomposition.py              # season-specific endemic-epidemic decomposition
cd reproducible
python power_analysis.py && python calibration_ci.py && python perfold_holm.py && python b2_effect_mod.py
cd ../..

# 4. Audit and descriptive analyses
cd audit && python recompute.py && python b1_coupling.py && cd ..
cd descriptive && python prewrite_outputs.py && python make_map.py && cd ..

# 5. Robustness analyses
cd robustness
python sec_A.py 1 && python sec_A.py 4 && python sec_A.py 8   # block bootstrap (about 2 min each)
python sec_A2.py 4 && python sec_A2.py 8                      # year-specific tests, frozen test family
python sec_B.py && python sec_C.py && python sec_D.py && python sec_E.py && python sec_F.py && python sec_G.py
python figs_v7.py                                             # Figures 8 to 10
cd ..

# 6. Remaining figures
cd figures && python make_figures.py && python render_vector.py && python render_pptx.py && cd ..
```

## Outputs and the manuscript

| Manuscript item | Produced by | Output |
|---|---|---|
| Figure 1 | `figures/render_vector.py`, `render_pptx.py` | `figures/output/Figure1_study_workflow.*` |
| Figure 2 | `descriptive/make_map.py` | `figures/output/Figure2_Bangladesh_dengue_maps.*` |
| Figures 3 to 7 | `figures/make_figures.py` | `figures/output/Figure3_temporal.png` to `Figure7_capture.png` |
| Figures 8 to 10 | `robustness/figs_v7.py` | `figures/output/Figure8_lead_time.*` to `Figure10_error_maps.*` |
| Pooled and locked metrics, event-level capture | `experiments/evaluate.py` | `results/dev_metrics_primary.csv`, `results/locked_metrics.csv` |
| Year-specific AUPRC tests | `posthoc/reproducible/perfold_holm.py` | `audit/output/b3_perfold_holm.csv` |
| Table 9 | `experiments/stats_tests.py`, `robustness/sec_A.py`, `sec_A2.py` | `results/dev_stat_tests.csv`, `robustness/output/` |
| Table 10 | `robustness/sec_B.py` | `robustness/output/B_operational.csv` |
| Table 11 | `experiments/ablate_sens.py` | `results/dev_sensitivity.csv`, `results/dev_ablation.csv` |

## Verification

The repository was run end to end from a clean copy and every output was compared with the frozen results reported in the manuscript; see [`VERIFICATION.md`](VERIFICATION.md).

## Not included

Two analyses reported in the manuscript cannot be regenerated from this repository, because the code that prepared their inputs was not preserved:

- the sensitivity analysis that includes quality-controlled weeks (one row of Table 11);
- the cross-validation of the Python hhh4 implementation against the official R `surveillance` package.

## Licence and citation

Code is released under the MIT licence (see `LICENSE`). Please cite the manuscript and the Figshare dataset (https://doi.org/10.6084/m9.figshare.33040637) when using this code.
