# Training report — random_forest-full 20261028T135634Z

- Data origin: **unsw-nb15**
- Feature profile: `full` (39 features)
- Seed: `42`; validation fraction: 0.2
- Selection criterion: validation macro-F1, ties broken by lower false-positive rate
- Selected candidate: **random_forest_balanced**
- Model SHA-256: `9ee6fef2710060741d4ed4d5e0cbf57fb94d8d4c6f7b3706d657435dc76f4889`

The official testing file was **not** used for training or selection.

## Data

- `UNSW_NB15_training-set.csv` — 32293018 bytes, SHA-256 `bec7dd5ec88dc2a0ccc7a07879d338395ed7421750f675fd0339e07dfe0648fa`

- Rows read: 175341; rejected by validation: 0; exact duplicates removed: 67601
- Train rows: 86192; validation rows: 21548
- Rejection reasons: `none`

## Validation results per candidate

| Candidate | Macro-F1 | Weighted-F1 | Attack recall | False-positive rate | Fit time (s) |
|---|---|---|---|---|---|
| logistic_regression | 42.86% | 74.95% | 94.28% | 12.45% | 1216.6 |
| logistic_regression_balanced | 45.61% | 72.68% | 99.75% | 20.27% | 2105.4 |
| random_forest | 53.85% | 80.81% | 94.48% | 7.98% | 26.4 |
| random_forest_balanced | 59.37% | 81.27% | 99.51% | 16.85% | 20.3 |

## Selected model on the validation split (random_forest_balanced)

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| Normal | 99.37% | 83.15% | 90.54% | 10378 |
| Analysis | 8.89% | 20.38% | 12.38% | 319 |
| Backdoor | 7.23% | 19.54% | 10.55% | 307 |
| DoS | 40.59% | 30.88% | 35.07% | 761 |
| Exploits | 86.73% | 80.85% | 83.69% | 3969 |
| Fuzzers | 63.24% | 88.08% | 73.62% | 3230 |
| Generic | 93.57% | 83.49% | 88.24% | 836 |
| Reconnaissance | 80.68% | 77.73% | 79.17% | 1504 |
| Shellcode | 52.79% | 73.85% | 61.57% | 218 |
| Worms | 60.00% | 57.69% | 58.82% | 26 |

## Global feature importance (top 15)

What the model relies on overall. It does not explain individual predictions and does
not imply causation.

| Feature | Share of importance |
|---|---|
| `sbytes` | 9.53% |
| `smean` | 8.46% |
| `service` | 6.24% |
| `sload` | 4.62% |
| `ct_dst_src_ltm` | 4.23% |
| `ct_srv_dst` | 4.07% |
| `proto` | 4.05% |
| `sttl` | 3.78% |
| `dbytes` | 3.47% |
| `dur` | 3.37% |
| `ct_srv_src` | 3.36% |
| `dmean` | 3.30% |
| `sinpkt` | 3.17% |
| `dload` | 3.16% |
| `sjit` | 2.54% |

## Environment

- python: `3.13.15`
- numpy: `2.5.4`
- pandas: `3.1.0`
- scikit-learn: `1.9.1`
- joblib: `1.6.0`
- platform: `Windows-11-10.0.26200-SP0`
- machine: `AMD64`
- processor: `AMD64 Family 23 Model 160 Stepping 0, AuthenticAMD`
- cpu_count: `8`
- git commit: `d702fceb41d306b9ca380fd07b60f41ac9e6cdbb`

## How to read these metrics

- **Precision** (per class): of the records predicted as a class, the share that truly were.
  Depends on how common the class is in this test set, so it will differ on other traffic.
- **Recall** (per class): of the records truly in a class, the share that were found. A high
  recall on rare classes (e.g. Worms) rests on very few records and is statistically fragile.
- **F1**: harmonic mean of precision and recall. Macro-F1 weights every class equally;
  weighted-F1 is dominated by the large classes.
- **False-positive rate**: share of Normal records predicted as any attack class. Even a small
  rate produces many false alerts at high traffic volumes (base-rate effect).
- **Accuracy** is shown for completeness only; with imbalanced classes it is misleading.
- **ROC-AUC / average precision** use 1 - score(Normal) as an attack score. The scores are
  **uncalibrated** and must not be read as probabilities.
- All numbers describe UNSW-NB15's 2015 testbed traffic. They do not predict performance on
  other networks, and they do not show that any individual prediction is correct.
