# Model evaluation — UNSW-NB15 (Phase 2)

> All numbers below are generated from the committed JSON reports in
> [`ml/reports/`](../ml/reports/) — real runs on the official UNSW-NB15 partitioned files
> (training SHA-256 `bec7dd5e…0648fa`, testing `734fe664…c0a559`), executed on a team
> member's Windows 11 laptop (8 logical CPUs, Python 3.13.15, scikit-learn 1.9.1) at commit
> `d702fce`. Each model was evaluated on the testing file **once**. Model scores are
> **uncalibrated**; no number here shows that any individual prediction is correct.

## Method in brief

- Training file: 175 341 rows, 0 rejected, ~67 600 exact duplicates removed (38.6%), then a
  stratified 80/20 train/validation split (seed 42).
- Four candidates per feature profile; the one with the highest **validation** macro-F1
  was selected (rule fixed before any test evaluation). The rule picked
  `random_forest_balanced` for all three profiles.
- Testing file: 82 332 rows, used once per selected model. Results are also shown for the
  test rows that do not duplicate a training row.

### Validation results (official training file, 20% stratified split) — used for selection

| Profile | Candidate | Macro-F1 | Attack recall | False-positive rate | Fit time |
|---|---|---|---|---|---|
| `full` | logistic_regression | 42.9% | 94.3% | 12.4% | 20.3 min |
| `full` | logistic_regression_balanced | 45.6% | 99.7% | 20.3% | 35.1 min |
| `full` | random_forest | 53.9% | 94.5% | 8.0% | 0.4 min |
| `full` | random_forest_balanced **(selected)** | 59.4% | 99.5% | 16.9% | 0.3 min |
| `full_no_ttl` | logistic_regression | 42.2% | 92.5% | 14.4% | 19.8 min |
| `full_no_ttl` | logistic_regression_balanced | 44.7% | 98.8% | 22.6% | 18.3 min |
| `full_no_ttl` | random_forest | 50.5% | 94.6% | 7.8% | 0.4 min |
| `full_no_ttl` | random_forest_balanced **(selected)** | 56.5% | 99.6% | 17.0% | 0.3 min |
| `live_compatible` | logistic_regression | 40.5% | 90.1% | 16.7% | 10.7 min |
| `live_compatible` | logistic_regression_balanced | 42.9% | 98.6% | 27.1% | 39.4 min |
| `live_compatible` | random_forest | 53.1% | 94.5% | 8.0% | 0.4 min |
| `live_compatible` | random_forest_balanced **(selected)** | 58.6% | 99.3% | 16.0% | 0.3 min |

### Test results (official testing file, evaluated once per model)

| Profile | Features | Macro-F1 | Weighted-F1 | Attack precision | Attack recall | False-positive rate | ROC-AUC* | Macro-F1, test rows not in training |
|---|---|---|---|---|---|---|---|---|
| `full` | 39 | 50.3% | 73.6% | 75.5% | 99.8% | 39.7% | 0.979 | 49.9% (78084 rows) |
| `full_no_ttl` | 36 | 49.1% | 73.2% | 75.4% | 99.6% | 39.8% | 0.977 | 48.7% (78083 rows) |
| `live_compatible` | 27 | 49.9% | 73.3% | 75.7% | 99.7% | 39.2% | 0.975 | 49.5% (78040 rows) |

\* Threshold-free ranking quality of the uncalibrated attack score (1 − score(Normal)).

### Per-class test results

| Class | Support | `full` P / R / F1 | `full_no_ttl` P / R / F1 | `live_compatible` P / R / F1 |
|---|---|---|---|---|
| Normal | 37000 | 99.6% / 60.3% / 75.1% | 99.2% / 60.2% / 75.0% | 99.3% / 60.8% / 75.4% |
| Analysis | 677 | 4.2% / 25.1% / 7.2% | 5.2% / 32.5% / 8.9% | 5.2% / 31.5% / 8.9% |
| Backdoor | 583 | 5.4% / 54.9% / 9.8% | 5.4% / 56.9% / 9.9% | 5.6% / 61.1% / 10.3% |
| DoS | 4089 | 48.9% / 14.0% / 21.7% | 46.9% / 11.7% / 18.7% | 43.3% / 12.4% / 19.3% |
| Exploits | 11132 | 79.1% / 62.9% / 70.1% | 77.3% / 62.2% / 69.0% | 76.8% / 61.5% / 68.3% |
| Fuzzers | 6062 | 25.4% / 71.0% / 37.4% | 25.3% / 69.4% / 37.1% | 25.3% / 67.3% / 36.8% |
| Generic | 18871 | 99.7% / 97.3% / 98.5% | 99.6% / 97.1% / 98.3% | 99.6% / 97.2% / 98.4% |
| Reconnaissance | 3496 | 88.0% / 83.0% / 85.4% | 87.4% / 83.1% / 85.2% | 87.1% / 82.2% / 84.6% |
| Shellcode | 378 | 25.2% / 79.4% / 38.2% | 25.3% / 78.8% / 38.3% | 24.0% / 81.5% / 37.1% |
| Worms | 44 | 64.9% / 54.5% / 59.3% | 57.1% / 45.5% / 50.6% | 64.1% / 56.8% / 60.2% |

### Latency (Windows 11, 8 logical CPUs, Random Forest with n_jobs=-1)

| Profile | Single record, median | Single record, p95 | Batch of 1000, median | Throughput |
|---|---|---|---|---|
| `full` | 100 ms | 159 ms | 170 ms | 5896 records/s |
| `full_no_ttl` | 209 ms | 685 ms | 539 ms | 1855 records/s |
| `live_compatible` | 97 ms | 127 ms | 157 ms | 6370 records/s |

### Artifacts

| Profile | Report folder | Model SHA-256 |
|---|---|---|
| `full` | [`random_forest-full-20261028T135634Z`](../ml/reports/random_forest-full-20261028T135634Z/) | `9ee6fef2710060741d4ed4d5e0cbf57fb94d8d4c6f7b3706d657435dc76f4889` |
| `full_no_ttl` | [`random_forest-full_no_ttl-20261028T143723Z`](../ml/reports/random_forest-full_no_ttl-20261028T143723Z/) | `2cf039c981fb78ffd7fbf4522bfde9f665b58e2b9bbeb1ede0dab3d476b93840` |
| `live_compatible` | [`random_forest-live_compatible-20261028T153049Z`](../ml/reports/random_forest-live_compatible-20261028T153049Z/) | `7c7627729999f79b5df4039a3f1d3f19e36a1a63e84e2354e076650520c9cf9a` |

## Findings

1. **Attacks are rarely missed, but Normal traffic is often flagged.** At the model's
   default decision (highest-scoring class), attack recall on the test file is 99.6–99.8%,
   but **39–40% of Normal test records are predicted as some attack** (`full`: 14 677 of
   37 000). The validation split showed 16.0–17.0%, so the official testing file differs
   noticeably from the training file (distribution shift between the published partitions).
2. **Most false alerts are "Fuzzers".** 11 826 Normal test records (32% of Normal) were
   predicted as Fuzzers by the `full` model; Fuzzers precision is about 25%.
3. **Category labels are reliable for some attacks, not others.** Generic (F1 ≈ 98%),
   Reconnaissance (≈ 85%) and Exploits (≈ 70%) are usable. DoS (precision ≈ 43–49%, recall
   ≈ 12–14%), Analysis and Backdoor (precision ≈ 4–6%), Fuzzers and Shellcode (≈ 24–25%) are
   not: e.g. 51% of DoS records were predicted as Backdoor. These classes overlap heavily in
   the dataset's flow features.
4. **TTL features are not a critical shortcut on these splits.** Removing them
   (`full_no_ttl`) lowers macro-F1 by about 1.2 points and leaves the binary view almost
   unchanged.
5. **The live-compatible feature set loses little on dataset values.** With 27 features,
   macro-F1 is within 0.4 points of `full`. This is measured on Argus-computed dataset
   values; it does **not** show how the model behaves on Zeek-derived live features.
6. **Train/test overlap does not inflate the results.** 4 248 test rows duplicate a
   training row; excluding them changes macro-F1 by less than 0.5 points.
7. **Class weighting trades false alerts for recall.** On validation, the selected
   balanced Random Forest had about twice the false-positive rate of the unweighted one
   (16.9% vs 8.0% for `full`) for higher macro-F1. The pre-declared selection rule was kept;
   it was not changed after seeing test results.
8. **Ranking is much better than the default decision.** ROC-AUC of the attack score is
   0.975–0.979, so a stricter alert threshold could cut false alerts at some cost in recall.
9. **Logistic Regression is a weak and slow baseline here**: validation macro-F1 40–46%,
   and 11–39 minutes per fit on the laptop, versus under 30 seconds for each Random Forest.
10. **Latency was measured with multi-threaded prediction** (`n_jobs=-1`), about 100 ms per
    single record (median), dominated by thread dispatch. The `full_no_ttl` measurement was
    noticeably slower and noisier, likely because the laptop was busy. Commit `d4efd1a`
    later switched inference to a single thread; latency should be re-measured (without
    re-scoring the test set) in Phase 3.

## Consequences for SentinelNepal

- Alerts must present the predicted category as a *suspected* category, and the UI should
  flag low-reliability categories (DoS, Analysis, Backdoor, Fuzzers, Shellcode) — the
  recommendation engine (Phase 5) should treat them as a broad "attack-like" signal.
- Alert volume will contain many false alerts at the default decision. Phase 3 should add
  an **alert threshold on the attack score, chosen on the validation split** (never on the
  test file) and stored with the model version. Any test-file figures for that threshold
  must be labelled as a post-hoc analysis.
- `live_compatible` remains behind the Phase 6 compatibility gate; these results do not
  validate live use.

## Reproducing

```bash
cd ml
sentinel-ml profile
sentinel-ml train --profile full            # likewise full_no_ttl, live_compatible
sentinel-ml evaluate artifacts/<artifact-dir>
```

Same data files (same SHA-256), seed, and library versions give the same models. A full
`train` run took about 1–1.5 hours on the laptop, almost all of it in the two Logistic
Regression candidates.
