# Test-set evaluation — random_forest-live_compatible 20261028T153049Z

- Data origin: **unsw-nb15**
- Feature profile: `live_compatible`
- Model SHA-256: `7c7627729999f79b5df4039a3f1d3f19e36a1a63e84e2354e076650520c9cf9a`
- Evaluated at: 2026-10-28T15:31:41.771033+00:00

## Test data

- `UNSW_NB15_testing-set.csv` — 15380800 bytes, SHA-256 `734fe6642edf758f7c94d7d9149426b49d202fe8e7bf0bef47392489c3c0a559`

- Rows read: 82332; rejected by validation: 0
- Rejection reasons: `none`
- Test rows identical (features + label) to a training row: 4292

## Binary view: Normal vs any attack (all test rows)

| Metric | Value |
|---|---|
| Precision (attack) | 75.68% |
| Recall / detection rate | 99.66% |
| F1 (attack) | 86.03% |
| False-positive rate (Normal flagged) | 39.24% |
| False-negative rate (attacks missed) | 0.34% |
| TP / FP / TN / FN | 45180 / 14517 / 22483 / 152 |

- ROC-AUC (uncalibrated attack score): 97.46%
- Average precision: 97.90%

## Per-class results (all test rows)

Macro-F1 49.93%, weighted-F1 73.28%, accuracy 68.06%.

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| Normal | 99.33% | 60.76% | 75.40% | 37000 |
| Analysis | 5.19% | 31.46% | 8.91% | 677 |
| Backdoor | 5.63% | 61.06% | 10.31% | 583 |
| DoS | 43.28% | 12.45% | 19.34% | 4089 |
| Exploits | 76.80% | 61.49% | 68.30% | 11132 |
| Fuzzers | 25.29% | 67.32% | 36.76% | 6062 |
| Generic | 99.59% | 97.19% | 98.37% | 18871 |
| Reconnaissance | 87.07% | 82.24% | 84.58% | 3496 |
| Shellcode | 23.99% | 81.48% | 37.06% | 378 |
| Worms | 64.10% | 56.82% | 60.24% | 44 |

## Confusion matrix (all test rows)

Rows: true class. Columns: predicted class.

| true \ predicted | Normal | Analysis | Backdoor | DoS | Exploits | Fuzzers | Generic | Reconnaissance | Shellcode | Worms |
|---|---|---|---|---|---|---|---|---|---|---|
| **Normal** | 22483 | 1782 | 1 | 133 | 714 | 11565 | 13 | 26 | 281 | 2 |
| **Analysis** | 4 | 213 | 404 | 2 | 43 | 11 | 0 | 0 | 0 | 0 |
| **Backdoor** | 0 | 197 | 356 | 9 | 11 | 2 | 0 | 1 | 7 | 0 |
| **DoS** | 5 | 621 | 2178 | 509 | 556 | 102 | 20 | 36 | 60 | 2 |
| **Exploits** | 40 | 802 | 2277 | 378 | 6845 | 239 | 37 | 319 | 189 | 6 |
| **Fuzzers** | 91 | 413 | 828 | 55 | 218 | 4081 | 3 | 33 | 340 | 0 |
| **Generic** | 10 | 15 | 25 | 45 | 339 | 63 | 18341 | 5 | 24 | 4 |
| **Reconnaissance** | 2 | 59 | 256 | 29 | 162 | 38 | 1 | 2875 | 74 | 0 |
| **Shellcode** | 0 | 0 | 0 | 15 | 11 | 36 | 1 | 7 | 308 | 0 |
| **Worms** | 0 | 0 | 0 | 1 | 14 | 2 | 1 | 0 | 1 | 25 |

## Test rows that do not duplicate a training row

Published UNSW-NB15 splits share identical rows; scores on those rows reward
memorisation. This subset removes them.

Records: 78040; macro-F1 49.48%.

| Metric | Value |
|---|---|
| Precision (attack) | 74.76% |
| Recall / detection rate | 99.64% |
| F1 (attack) | 85.42% |
| False-positive rate (Normal flagged) | 39.77% |
| False-negative rate (attacks missed) | 0.36% |
| TP / FP / TN / FN | 42125 / 14224 / 21539 / 152 |

## Inference latency

Wall-clock time of `predict_proba` on this machine (see Environment), single process.

| Measure | Value |
|---|---|
| Single record, median (200 calls) | 96.73 ms |
| Single record, p95 | 127.27 ms |
| Batch of 1000, median (5 runs) | 157.0 ms |
| Batch per-record | 157.0 µs |
| Batch throughput | 6370 records/s |

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
