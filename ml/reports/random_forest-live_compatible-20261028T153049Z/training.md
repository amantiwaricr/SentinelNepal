# Training report — random_forest-live_compatible 20261028T153049Z

- Data origin: **unsw-nb15**
- Feature profile: `live_compatible` (27 features)
- Seed: `42`; validation fraction: 0.2
- Selection criterion: validation macro-F1, ties broken by lower false-positive rate
- Selected candidate: **random_forest_balanced**
- Model SHA-256: `7c7627729999f79b5df4039a3f1d3f19e36a1a63e84e2354e076650520c9cf9a`

The official testing file was **not** used for training or selection.

## Data

- `UNSW_NB15_training-set.csv` — 32293018 bytes, SHA-256 `bec7dd5ec88dc2a0ccc7a07879d338395ed7421750f675fd0339e07dfe0648fa`

- Rows read: 175341; rejected by validation: 0; exact duplicates removed: 67800
- Train rows: 86032; validation rows: 21509
- Rejection reasons: `none`

## Validation results per candidate

| Candidate | Macro-F1 | Weighted-F1 | Attack recall | False-positive rate | Fit time (s) |
|---|---|---|---|---|---|
| logistic_regression | 40.53% | 70.89% | 90.10% | 16.68% | 640.8 |
| logistic_regression_balanced | 42.92% | 69.03% | 98.59% | 27.08% | 2366.7 |
| random_forest | 53.09% | 80.65% | 94.48% | 7.95% | 21.8 |
| random_forest_balanced | 58.65% | 81.00% | 99.29% | 16.02% | 17.3 |

## Selected model on the validation split (random_forest_balanced)

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| Normal | 99.10% | 83.98% | 90.92% | 10339 |
| Analysis | 8.82% | 19.44% | 12.13% | 319 |
| Backdoor | 6.74% | 18.24% | 9.84% | 307 |
| DoS | 35.08% | 27.20% | 30.64% | 761 |
| Exploits | 85.23% | 79.06% | 82.03% | 3969 |
| Fuzzers | 64.06% | 87.18% | 73.85% | 3230 |
| Generic | 94.80% | 82.89% | 88.45% | 836 |
| Reconnaissance | 79.85% | 77.67% | 78.75% | 1505 |
| Shellcode | 54.57% | 79.36% | 64.67% | 218 |
| Worms | 48.48% | 64.00% | 55.17% | 25 |

## Global feature importance (top 15)

What the model relies on overall. It does not explain individual predictions and does
not imply causation.

| Feature | Share of importance |
|---|---|
| `sbytes` | 11.64% |
| `smean` | 9.60% |
| `service` | 7.25% |
| `sload` | 6.27% |
| `dload` | 5.51% |
| `sinpkt` | 5.21% |
| `dur` | 5.03% |
| `dbytes` | 4.66% |
| `dmean` | 4.55% |
| `dinpkt` | 4.47% |
| `proto` | 4.42% |
| `ct_srv_dst` | 4.40% |
| `ct_dst_src_ltm` | 4.27% |
| `ct_srv_src` | 3.59% |
| `dpkts` | 3.09% |

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
