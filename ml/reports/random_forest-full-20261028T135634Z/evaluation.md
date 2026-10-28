# Test-set evaluation — random_forest-full 20261028T135634Z

- Data origin: **unsw-nb15**
- Feature profile: `full`
- Model SHA-256: `9ee6fef2710060741d4ed4d5e0cbf57fb94d8d4c6f7b3706d657435dc76f4889`
- Evaluated at: 2026-10-28T13:57:27.293729+00:00

## Test data

- `UNSW_NB15_testing-set.csv` — 15380800 bytes, SHA-256 `734fe6642edf758f7c94d7d9149426b49d202fe8e7bf0bef47392489c3c0a559`

- Rows read: 82332; rejected by validation: 0
- Rejection reasons: `none`
- Test rows identical (features + label) to a training row: 4248

## Binary view: Normal vs any attack (all test rows)

| Metric | Value |
|---|---|
| Precision (attack) | 75.50% |
| Recall / detection rate | 99.79% |
| F1 (attack) | 85.97% |
| False-positive rate (Normal flagged) | 39.67% |
| False-negative rate (attacks missed) | 0.21% |
| TP / FP / TN / FN | 45238 / 14677 / 22323 / 94 |

- ROC-AUC (uncalibrated attack score): 97.90%
- Average precision: 98.29%

## Per-class results (all test rows)

Macro-F1 50.28%, weighted-F1 73.62%, accuracy 68.36%.

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| Normal | 99.58% | 60.33% | 75.14% | 37000 |
| Analysis | 4.21% | 25.11% | 7.21% | 677 |
| Backdoor | 5.38% | 54.89% | 9.81% | 583 |
| DoS | 48.89% | 13.96% | 21.72% | 4089 |
| Exploits | 79.10% | 62.94% | 70.11% | 11132 |
| Fuzzers | 25.37% | 70.98% | 37.38% | 6062 |
| Generic | 99.69% | 97.33% | 98.49% | 18871 |
| Reconnaissance | 88.04% | 82.95% | 85.42% | 3496 |
| Shellcode | 25.19% | 79.37% | 38.24% | 378 |
| Worms | 64.86% | 54.55% | 59.26% | 44 |

## Confusion matrix (all test rows)

Rows: true class. Columns: predicted class.

| true \ predicted | Normal | Analysis | Backdoor | DoS | Exploits | Fuzzers | Generic | Reconnaissance | Shellcode | Worms |
|---|---|---|---|---|---|---|---|---|---|---|
| **Normal** | 22323 | 1860 | 5 | 142 | 565 | 11826 | 9 | 22 | 246 | 2 |
| **Analysis** | 1 | 170 | 370 | 7 | 57 | 72 | 0 | 0 | 0 | 0 |
| **Backdoor** | 0 | 158 | 320 | 12 | 10 | 76 | 0 | 1 | 6 | 0 |
| **DoS** | 2 | 644 | 2081 | 571 | 524 | 161 | 15 | 31 | 58 | 2 |
| **Exploits** | 12 | 783 | 2147 | 290 | 7007 | 374 | 27 | 311 | 176 | 5 |
| **Fuzzers** | 78 | 339 | 748 | 52 | 213 | 4303 | 4 | 22 | 303 | 0 |
| **Generic** | 0 | 17 | 26 | 50 | 318 | 62 | 18367 | 3 | 24 | 4 |
| **Reconnaissance** | 1 | 67 | 246 | 32 | 134 | 37 | 1 | 2900 | 78 | 0 |
| **Shellcode** | 0 | 0 | 0 | 12 | 14 | 47 | 1 | 4 | 300 | 0 |
| **Worms** | 0 | 0 | 0 | 0 | 16 | 3 | 1 | 0 | 0 | 24 |

## Test rows that do not duplicate a training row

Published UNSW-NB15 splits share identical rows; scores on those rows reward
memorisation. This subset removes them.

Records: 78084; macro-F1 49.88%.

| Metric | Value |
|---|---|
| Precision (attack) | 74.57% |
| Recall / detection rate | 99.78% |
| F1 (attack) | 85.35% |
| False-positive rate (Normal flagged) | 40.17% |
| False-negative rate (attacks missed) | 0.22% |
| TP / FP / TN / FN | 42184 / 14385 / 21421 / 94 |

## Inference latency

Wall-clock time of `predict_proba` on this machine (see Environment), single process.

| Measure | Value |
|---|---|
| Single record, median (200 calls) | 99.91 ms |
| Single record, p95 | 159.04 ms |
| Batch of 1000, median (5 runs) | 169.6 ms |
| Batch per-record | 169.6 µs |
| Batch throughput | 5896 records/s |

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
