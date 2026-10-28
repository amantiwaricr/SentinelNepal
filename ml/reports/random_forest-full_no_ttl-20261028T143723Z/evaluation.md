# Test-set evaluation — random_forest-full_no_ttl 20261028T143723Z

- Data origin: **unsw-nb15**
- Feature profile: `full_no_ttl`
- Model SHA-256: `2cf039c981fb78ffd7fbf4522bfde9f665b58e2b9bbeb1ede0dab3d476b93840`
- Evaluated at: 2026-10-28T14:38:23.306146+00:00

## Test data

- `UNSW_NB15_testing-set.csv` — 15380800 bytes, SHA-256 `734fe6642edf758f7c94d7d9149426b49d202fe8e7bf0bef47392489c3c0a559`

- Rows read: 82332; rejected by validation: 0
- Rejection reasons: `none`
- Test rows identical (features + label) to a training row: 4249

## Binary view: Normal vs any attack (all test rows)

| Metric | Value |
|---|---|
| Precision (attack) | 75.43% |
| Recall / detection rate | 99.62% |
| F1 (attack) | 85.85% |
| False-positive rate (Normal flagged) | 39.76% |
| False-negative rate (attacks missed) | 0.38% |
| TP / FP / TN / FN | 45161 / 14710 / 22290 / 171 |

- ROC-AUC (uncalibrated attack score): 97.73%
- Average precision: 98.15%

## Per-class results (all test rows)

Macro-F1 49.10%, weighted-F1 73.18%, accuracy 68.01%.

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| Normal | 99.24% | 60.24% | 74.97% | 37000 |
| Analysis | 5.15% | 32.50% | 8.89% | 677 |
| Backdoor | 5.44% | 56.95% | 9.93% | 583 |
| DoS | 46.87% | 11.71% | 18.74% | 4089 |
| Exploits | 77.35% | 62.23% | 68.97% | 11132 |
| Fuzzers | 25.35% | 69.35% | 37.12% | 6062 |
| Generic | 99.61% | 97.08% | 98.33% | 18871 |
| Reconnaissance | 87.39% | 83.09% | 85.19% | 3496 |
| Shellcode | 25.25% | 78.84% | 38.25% | 378 |
| Worms | 57.14% | 45.45% | 50.63% | 44 |

## Confusion matrix (all test rows)

Rows: true class. Columns: predicted class.

| true \ predicted | Normal | Analysis | Backdoor | DoS | Exploits | Fuzzers | Generic | Reconnaissance | Shellcode | Worms |
|---|---|---|---|---|---|---|---|---|---|---|
| **Normal** | 22290 | 1835 | 2 | 123 | 639 | 11822 | 18 | 24 | 244 | 3 |
| **Analysis** | 2 | 220 | 379 | 2 | 55 | 19 | 0 | 0 | 0 | 0 |
| **Backdoor** | 0 | 204 | 332 | 8 | 9 | 21 | 0 | 1 | 8 | 0 |
| **DoS** | 5 | 659 | 2126 | 479 | 587 | 114 | 19 | 35 | 63 | 2 |
| **Exploits** | 61 | 841 | 2215 | 284 | 6928 | 262 | 26 | 325 | 183 | 7 |
| **Fuzzers** | 96 | 432 | 772 | 44 | 198 | 4204 | 4 | 25 | 287 | 0 |
| **Generic** | 4 | 16 | 27 | 35 | 382 | 57 | 18320 | 4 | 23 | 3 |
| **Reconnaissance** | 3 | 63 | 253 | 31 | 125 | 41 | 1 | 2905 | 74 | 0 |
| **Shellcode** | 0 | 0 | 0 | 15 | 14 | 44 | 2 | 5 | 298 | 0 |
| **Worms** | 0 | 0 | 0 | 1 | 20 | 2 | 1 | 0 | 0 | 20 |

## Test rows that do not duplicate a training row

Published UNSW-NB15 splits share identical rows; scores on those rows reward
memorisation. This subset removes them.

Records: 78083; macro-F1 48.67%.

| Metric | Value |
|---|---|
| Precision (attack) | 74.49% |
| Recall / detection rate | 99.60% |
| F1 (attack) | 85.23% |
| False-positive rate (Normal flagged) | 40.27% |
| False-negative rate (attacks missed) | 0.40% |
| TP / FP / TN / FN | 42106 / 14418 / 21388 / 171 |

## Inference latency

Wall-clock time of `predict_proba` on this machine (see Environment), single process.

| Measure | Value |
|---|---|
| Single record, median (200 calls) | 208.91 ms |
| Single record, p95 | 685.01 ms |
| Batch of 1000, median (5 runs) | 539.0 ms |
| Batch per-record | 539.0 µs |
| Batch throughput | 1855 records/s |

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
