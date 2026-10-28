# Alert threshold — random_forest-live_compatible 20261028T153049Z

- Chosen on: **validation split of the training file (testing file not used)** (21509 rows, 10339 Normal)
- Score: attack_score = 1 - score(Normal); uncalibrated
- Target false-positive rate: 5.00% -> threshold **0.819583**
- On validation at that threshold: false-positive rate 4.99%, attack recall 90.43%

A record raises an alert when its attack score is at or above the threshold; its
category is then the highest-scoring attack class. Validation rows come from the same
file as the training rows, so the testing file (a shifted distribution) is likely to
show a higher false-positive rate at the same threshold.

## Operating points on the validation split

| Target FPR | Threshold | Validation FPR | Validation attack recall | Share alerted |
|---|---|---|---|---|
| 1.00% | 0.950000 | 0.99% | 73.97% | 38.89% |
| 2.00% | 0.920000 | 1.91% | 80.04% | 42.48% |
| 5.00% | 0.819583 | 4.99% | 90.43% | 49.36% |
| 10.00% | 0.695000 | 9.80% | 96.26% | 54.70% |
| 20.00% | 0.285000 | 19.97% | 99.94% | 61.50% |
| default decision (highest class) | — | 16.02% | 99.29% | 59.26% |

## Single-threaded latency (validation rows)

- Single record: median 48.09 ms, p95 76.90 ms (200 calls)
- Batch of 1000: median 217.2 ms (4604 records/s)

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
- git commit: `9f7f84fbd7abf38bfe22fed7bba26039661e662c`
