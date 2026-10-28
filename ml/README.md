# ml/ — SentinelNepal machine-learning package (`sentinel_ml`)

Reproducible network-intrusion classification on the public **UNSW-NB15** dataset:
preprocessing, training, evaluation, and the prediction service that the backend (and later
the live collector) imports. Feature handling exists only here (`AGENTS.md`).

> **Status (Phase 2):** pipeline implemented and tested on **synthetic** data only. The real
> dataset has not been downloaded in the development environment yet, so **no model has been
> trained on UNSW-NB15 and no real metrics exist**. Follow the commands below once the files are
> in `ml/data/` (see [data/README.md](data/README.md)).

## Layout

| Path | Contents |
|---|---|
| `sentinel_ml/schema.py` | Canonical columns, class labels, feature profiles, live (Zeek) availability table |
| `sentinel_ml/features/cleaning.py` | Validation and type coercion shared by every entry point |
| `sentinel_ml/features/dataset.py` | Locate, detect, and read both UNSW-NB15 file families (chunked) |
| `sentinel_ml/features/profile.py` | Data profiling report |
| `sentinel_ml/preprocessing/pipeline.py` | scikit-learn pipelines and global feature importance |
| `sentinel_ml/training/train.py` | Candidate training and validation-based selection |
| `sentinel_ml/evaluation/` | Metrics, latency, one-off test evaluation, Markdown reports |
| `sentinel_ml/inference/predictor.py` | `Predictor`: load (hash-checked), validate, predict |
| `sentinel_ml/artifacts.py` | Artifact layout, manifest, integrity checks |
| `sentinel_ml/cli.py` | `sentinel-ml` command |
| `tests/` | 90+ tests on **synthetic** fixtures (`tests/synthetic.py`) |

## Setup

```bash
cd ml
python3 -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
pip install -e .
```

## Reproducing the results

With the dataset in `ml/data/`:

```bash
sentinel-ml profile                              # 1. inspect the real files
sentinel-ml train --profile full                 # 2. primary model for dataset analysis
sentinel-ml train --profile full_no_ttl          # 3. ablation without TTL features
sentinel-ml train --profile live_compatible      # 4. features obtainable from Zeek only
sentinel-ml evaluate artifacts/<artifact-dir>    # 5. once per trained artifact
```

Each `train` prints the artifact directory and its SHA-256. Reports go to
`ml/reports/<artifact-dir>/` (`training.md/json`, `evaluation.md/json`,
`confusion_matrix.csv`) and `ml/reports/data_profile.md`. Commit the reports; artifacts stay
git-ignored and are re-created by the same commands. With the same data files (same hashes),
seed, and library versions, training gives identical results (a test checks this).

Measured on synthetic data of the same size as the real training file (4 CPU cores, Linux):
training all four candidates took about 1.5 minutes, test evaluation about 40 seconds, peak
memory about 1 GB. Real-data timings will differ.

## Pipeline and decisions

1. **Loading.** Both file families are supported: the partitioned files (header row) and the
   full-record files (no header; column names from `NUSW-NB15_features.csv`, or the built-in
   list, which is checked against that file when present). Column names are normalised
   (`smeansz` → `smean`, `res_bdy_len` → `response_body_len`, …).
2. **Validation** (`clean_frame`, shared by training, evaluation, profiling, and inference).
   Every value is read as text and validated. Non-numeric, infinite, or boolean numbers,
   blank required values, over-long or non-text categories, unknown attack categories,
   invalid labels, and records whose `label` contradicts `attack_cat` are **rejected with a
   reason** and counted in the reports. Only `ct_flw_http_mthd`, `is_ftp_login`, and
   `ct_ftp_cmd` (legitimately blank for non-HTTP/FTP flows) may be missing; the pipeline
   imputes them with the training median and the predictor reports which were imputed.
3. **Labels.** Whitespace is stripped, `Backdoors` → `Backdoor`, and a blank category with
   `label = 0` becomes `Normal`. Target: 10 classes (Normal + 9 attack categories). Binary
   "suspicious" = predicted class ≠ Normal.
4. **Leakage prevention.** Never used as features: `id`, `label`, `attack_cat`, IP addresses,
   ports, timestamps, `rate` (missing from the full-record files), and the random TCP
   sequence numbers `stcpb`/`dtcpb` (reasons in `schema.EXCLUDED_COLUMNS`). Tests assert that
   no profile contains them and that the fitted pipeline's input columns equal the profile.
5. **Splits.** Training and model selection use only `UNSW_NB15_training-set.csv`: exact
   duplicate rows are removed, then a stratified 80/20 train/validation split (seed 42). The
   testing file is read only by `evaluate`, which also reports results on test rows that do
   not duplicate any training row.
6. **Preprocessing.** Numeric: median imputation (plus signed log1p and standardisation for
   Logistic Regression). Categorical (`proto`, `service`, `state`): lower-cased,
   one-hot encoded; categories seen fewer than 20 times, or never, map to an "infrequent"
   bucket instead of failing. Preprocessing and model are saved as **one** scikit-learn
   `Pipeline`, so inference cannot diverge from training.
7. **Models.** Logistic Regression (baseline) and Random Forest (200 trees), each with and
   without `class_weight="balanced"` — class imbalance is addressed this way, not by
   resampling. Selection: highest validation macro-F1, ties broken by lower false-positive
   rate. Fit warnings (e.g. non-convergence) are recorded in the report.
8. **Feature profiles.** `full` (39 features, dataset analysis), `full_no_ttl` (ablation:
   TTL features are strongly tied to the 2015 testbed), `live_compatible` (27 features
   obtainable from Zeek; see [docs/feature-mapping.md](../docs/feature-mapping.md)).

## Evaluation outputs

Per class: precision, recall, F1, support; macro/weighted F1; confusion matrix; binary view
(Normal vs attack) with false-positive and false-negative rates; ROC-AUC and average
precision from the uncalibrated score; latency (single record median/p95 and batch
throughput) with the hardware and library versions used. Each report explains the limits of
each metric. Reports from synthetic data carry a banner and must not be quoted.

**Scores are not probabilities.** No calibration has been done; the UI and API must call
them "model scores".

## Prediction service

```python
from pathlib import Path
from sentinel_ml.inference import Predictor

predictor = Predictor.load(Path("artifacts/<dir>"), expected_sha256="<trusted hash>")
batch = predictor.predict_records([{...feature values...}])   # or predict_frame(df)
for p in batch.predictions:
    p.predicted_category, p.is_suspicious, p.model_score, p.imputed_features
for r in batch.rejected:
    r.index, r.reasons          # e.g. ["invalid_type:sbytes"]
```

- `load` refuses the artifact unless the model file's SHA-256 equals the trusted value
  (the backend will keep it in its database), the feature-schema version matches, and the
  installed scikit-learn version is the one it was trained with.
- Malformed records are rejected individually with reasons; a missing *required column*
  in a DataFrame raises `SchemaError`. At most 10 000 records per call.
- `global_feature_importance()` shows what the model relies on overall. It does not explain
  an individual prediction and does not imply causation.

## Versioning

| Item | Scheme |
|---|---|
| Feature schema | `FEATURE_SCHEMA_VERSION` in `schema.py`; bump when feature names, order, or meaning change. Artifacts with another version are refused. |
| Model | Name `<model_kind>-<profile>`, version = UTC training timestamp (`20261101T093000Z`); directory `<name>-<version>`; never overwritten. |
| Manifest | Data file SHA-256s, seed, hyperparameters, all candidates' validation results, library versions, git commit (`+dirty` if uncommitted changes), model SHA-256. |
| Library upgrades | Pickled models are tied to the scikit-learn version; after upgrading, retrain. |

## Tests

```bash
cd ml && ruff format --check . && ruff check . && mypy && pytest
```

All fixtures are synthetic (`tests/synthetic.py`) and written to temporary directories with
the synthetic marker file.

## Known limitations

- UNSW-NB15 is 2015 laboratory traffic generated with the IXIA PerfectStorm tool; results do
  not transfer automatically to other networks (including networks in Nepal).
- The published splits contain duplicate and overlapping rows; reports show both raw and
  de-duplicated test results.
- Some features (notably TTL-based ones) may act as shortcuts specific to the testbed; the
  `full_no_ttl` ablation measures how much the model depends on them.
- Classes such as Worms and Analysis are rare; their per-class metrics are fragile.
- There is no brute-force class in UNSW-NB15; the model cannot predict one.
- Global feature importance is not a per-record explanation.
