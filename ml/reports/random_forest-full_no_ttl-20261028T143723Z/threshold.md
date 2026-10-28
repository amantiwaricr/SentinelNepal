# Alert threshold — random_forest-full_no_ttl 20261028T143723Z

- Chosen on: **validation split of the training file (testing file not used)** (21548 rows, 10378 Normal)
- Score: attack_score = 1 - score(Normal); uncalibrated
- Target false-positive rate: 5.00% -> threshold **0.815000**
- On validation at that threshold: false-positive rate 4.91%, attack recall 90.27%

A record raises an alert when its attack score is at or above the threshold; its
category is then the highest-scoring attack class. Validation rows come from the same
file as the training rows, so the testing file (a shifted distribution) is likely to
show a higher false-positive rate at the same threshold.

## Operating points on the validation split

| Target FPR | Threshold | Validation FPR | Validation attack recall | Share alerted |
|---|---|---|---|---|
| 1.00% | 0.950000 | 0.94% | 74.18% | 38.91% |
| 2.00% | 0.919167 | 1.99% | 80.60% | 42.74% |
| 5.00% | 0.815000 | 4.91% | 90.27% | 49.16% |
| 10.00% | 0.705000 | 9.86% | 95.87% | 54.45% |
| 20.00% | 0.295000 | 19.97% | 99.96% | 61.44% |
| default decision (highest class) | — | 17.00% | 99.57% | 59.80% |

## Single-threaded latency (validation rows)

- Single record: median 41.83 ms, p95 75.09 ms (200 calls)
- Batch of 1000: median 196.2 ms (5096 records/s)

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
