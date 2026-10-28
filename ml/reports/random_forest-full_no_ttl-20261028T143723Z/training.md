# Training report — random_forest-full_no_ttl 20261028T143723Z

- Data origin: **unsw-nb15**
- Feature profile: `full_no_ttl` (36 features)
- Seed: `42`; validation fraction: 0.2
- Selection criterion: validation macro-F1, ties broken by lower false-positive rate
- Selected candidate: **random_forest_balanced**
- Model SHA-256: `2cf039c981fb78ffd7fbf4522bfde9f665b58e2b9bbeb1ede0dab3d476b93840`

The official testing file was **not** used for training or selection.

## Data

- `UNSW_NB15_training-set.csv` — 32293018 bytes, SHA-256 `bec7dd5ec88dc2a0ccc7a07879d338395ed7421750f675fd0339e07dfe0648fa`

- Rows read: 175341; rejected by validation: 0; exact duplicates removed: 67602
- Train rows: 86191; validation rows: 21548
- Rejection reasons: `none`

## Validation results per candidate

| Candidate | Macro-F1 | Weighted-F1 | Attack recall | False-positive rate | Fit time (s) |
|---|---|---|---|---|---|
| logistic_regression | 42.17% | 73.18% | 92.50% | 14.39% | 1187.6 |
| logistic_regression_balanced | 44.74% | 71.08% | 98.83% | 22.58% | 1099.7 |
| random_forest | 50.53% | 80.55% | 94.58% | 7.81% | 27.0 |
| random_forest_balanced | 56.49% | 80.75% | 99.57% | 17.00% | 20.3 |

## Selected model on the validation split (random_forest_balanced)

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| Normal | 99.45% | 83.00% | 90.48% | 10378 |
| Analysis | 8.19% | 18.81% | 11.41% | 319 |
| Backdoor | 6.72% | 18.24% | 9.82% | 307 |
| DoS | 35.81% | 25.36% | 29.69% | 761 |
| Exploits | 85.06% | 80.20% | 82.56% | 3969 |
| Fuzzers | 63.01% | 88.24% | 73.52% | 3230 |
| Generic | 94.53% | 82.66% | 88.19% | 836 |
| Reconnaissance | 79.90% | 77.67% | 78.77% | 1505 |
| Shellcode | 52.82% | 72.94% | 61.27% | 218 |
| Worms | 42.86% | 36.00% | 39.13% | 25 |

## Global feature importance (top 15)

What the model relies on overall. It does not explain individual predictions and does
not imply causation.

| Feature | Share of importance |
|---|---|
| `sbytes` | 10.19% |
| `smean` | 8.56% |
| `service` | 7.15% |
| `sload` | 4.87% |
| `ct_srv_dst` | 4.24% |
| `proto` | 3.99% |
| `ct_dst_src_ltm` | 3.96% |
| `dload` | 3.83% |
| `dmean` | 3.79% |
| `dur` | 3.71% |
| `dbytes` | 3.67% |
| `sinpkt` | 3.38% |
| `ct_srv_src` | 3.26% |
| `sjit` | 2.91% |
| `dinpkt` | 2.90% |

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
