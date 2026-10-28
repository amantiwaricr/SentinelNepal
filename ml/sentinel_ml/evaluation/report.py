"""Markdown rendering of training and evaluation results.

Reports only ever render numbers passed in from a real run. Runs on synthetic data carry a
banner so they cannot be mistaken for UNSW-NB15 results.
"""

from __future__ import annotations

from typing import Any

SYNTHETIC_BANNER = (
    "> **SYNTHETIC DATA — NOT UNSW-NB15.** These numbers come from generated test data and say\n"
    "> nothing about real detection performance. Do not quote them.\n"
)

METRIC_LIMITATIONS = """\
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
"""


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.2f}%"


def _per_class_table(metrics: dict[str, Any]) -> list[str]:
    lines = ["| Class | Precision | Recall | F1 | Support |", "|---|---|---|---|---|"]
    for label, row in metrics["per_class"].items():
        lines.append(
            f"| {label} | {_pct(row['precision'])} | {_pct(row['recall'])} | "
            f"{_pct(row['f1'])} | {row['support']} |"
        )
    return lines


def _binary_table(binary: dict[str, Any]) -> list[str]:
    return [
        "| Metric | Value |",
        "|---|---|",
        f"| Precision (attack) | {_pct(binary['precision'])} |",
        f"| Recall / detection rate | {_pct(binary['recall'])} |",
        f"| F1 (attack) | {_pct(binary['f1'])} |",
        f"| False-positive rate (Normal flagged) | {_pct(binary['false_positive_rate'])} |",
        f"| False-negative rate (attacks missed) | {_pct(binary['false_negative_rate'])} |",
        f"| TP / FP / TN / FN | {binary['true_positives']} / {binary['false_positives']} / "
        f"{binary['true_negatives']} / {binary['false_negatives']} |",
    ]


def _confusion_table(confusion: dict[str, Any]) -> list[str]:
    labels = confusion["labels"]
    lines = [
        "Rows: true class. Columns: predicted class.",
        "",
        "| true \\ predicted | " + " | ".join(labels) + " |",
        "|---|" + "---|" * len(labels),
    ]
    for label, row in zip(labels, confusion["matrix"], strict=True):
        lines.append(f"| **{label}** | " + " | ".join(str(v) for v in row) + " |")
    return lines


def _importance_table(importance: dict[str, float], top: int = 15) -> list[str]:
    lines = ["| Feature | Share of importance |", "|---|---|"]
    for name, value in list(importance.items())[:top]:
        lines.append(f"| `{name}` | {_pct(value)} |")
    return lines


def _environment_lines(environment: dict[str, str], commit: str | None) -> list[str]:
    lines = [f"- {key}: `{value}`" for key, value in environment.items()]
    lines.append(f"- git commit: `{commit or 'unknown'}`")
    return lines


def _sources(sources: list[dict[str, Any]]) -> list[str]:
    return [f"- `{s['name']}` — {s['size_bytes']} bytes, SHA-256 `{s['sha256']}`" for s in sources]


def render_training_markdown(payload: dict[str, Any]) -> str:
    selection = payload["selection"]
    model = payload["model"]
    out = [f"# Training report — {model['name']} {model['version']}", ""]
    if payload["data_origin"] == "synthetic":
        out += [SYNTHETIC_BANNER]
    out += [
        f"- Data origin: **{payload['data_origin']}**",
        f"- Feature profile: `{payload['feature_profile']}` ({len(payload['features'])} features)",
        f"- Seed: `{payload['seed']}`; validation fraction: {selection['validation_fraction']}",
        f"- Selection criterion: {selection['criterion']}",
        f"- Selected candidate: **{selection['selected']}**",
        f"- Model SHA-256: `{model['sha256']}`",
        "",
        "The official testing file was **not** used for training or selection.",
        "",
        "## Data",
        "",
        *_sources(payload["training_sources"]),
        "",
        f"- Rows read: {selection['rows_read']}; rejected by validation: "
        f"{selection['rows_rejected']}; exact duplicates removed: "
        f"{selection['duplicates_removed']}",
        f"- Train rows: {selection['train_rows']}; validation rows: {selection['validation_rows']}",
        f"- Rejection reasons: `{selection['rejection_counts'] or 'none'}`",
        "",
        "## Validation results per candidate",
        "",
        "| Candidate | Macro-F1 | Weighted-F1 | Attack recall | False-positive rate "
        "| Fit time (s) |",
        "|---|---|---|---|---|---|",
    ]
    for result in selection["candidates"]:
        validation = result["validation"]
        out.append(
            f"| {result['name']} | {_pct(validation['macro_f1'])} | "
            f"{_pct(validation['weighted_f1'])} | {_pct(validation['binary']['recall'])} | "
            f"{_pct(validation['binary']['false_positive_rate'])} | {result['fit_seconds']:.1f} |"
        )
    for result in selection["candidates"]:
        for warning in result.get("warnings", []):
            out.append(f"\n> Warning while fitting `{result['name']}`: {warning}")
    selected = next(r for r in selection["candidates"] if r["name"] == selection["selected"])
    out += [
        "",
        f"## Selected model on the validation split ({selection['selected']})",
        "",
        *_per_class_table(selected["validation"]),
        "",
        "## Global feature importance (top 15)",
        "",
        "What the model relies on overall. It does not explain individual predictions and does",
        "not imply causation.",
        "",
        *_importance_table(payload["feature_importance"]),
        "",
        "## Environment",
        "",
        *_environment_lines(payload["environment"], payload["git_commit"]),
        "",
        METRIC_LIMITATIONS,
    ]
    return "\n".join(out)


def render_evaluation_markdown(payload: dict[str, Any]) -> str:
    model = payload["model"]
    out = [f"# Test-set evaluation — {model['name']} {model['version']}", ""]
    if payload["data_origin"] == "synthetic":
        out += [SYNTHETIC_BANNER]
    out += [
        f"- Data origin: **{payload['data_origin']}**",
        f"- Feature profile: `{payload['feature_profile']}`",
        f"- Model SHA-256: `{model['sha256']}`",
        f"- Evaluated at: {payload['evaluated_at']}",
        "",
        "## Test data",
        "",
        *_sources(payload["test_sources"]),
        "",
        f"- Rows read: {payload['rows_read']}; rejected by validation: {payload['rows_rejected']}",
        f"- Rejection reasons: `{payload['rejection_counts'] or 'none'}`",
        f"- Test rows identical (features + label) to a training row: "
        f"{payload['overlap_with_training']}",
        "",
        "## Binary view: Normal vs any attack (all test rows)",
        "",
        *_binary_table(payload["all"]["binary"]),
        "",
        f"- ROC-AUC (uncalibrated attack score): {_pct(payload['ranking']['roc_auc'])}",
        f"- Average precision: {_pct(payload['ranking']['average_precision'])}",
        "",
        "## Per-class results (all test rows)",
        "",
        f"Macro-F1 {_pct(payload['all']['macro_f1'])}, weighted-F1 "
        f"{_pct(payload['all']['weighted_f1'])}, accuracy {_pct(payload['all']['accuracy'])}.",
        "",
        *_per_class_table(payload["all"]),
        "",
        "## Confusion matrix (all test rows)",
        "",
        *_confusion_table(payload["all"]["confusion_matrix"]),
        "",
        "## Test rows that do not duplicate a training row",
        "",
        "Published UNSW-NB15 splits share identical rows; scores on those rows reward",
        "memorisation. This subset removes them.",
        "",
        f"Records: {payload['deduplicated']['records']}; macro-F1 "
        f"{_pct(payload['deduplicated']['macro_f1'])}.",
        "",
        *_binary_table(payload["deduplicated"]["binary"]),
        "",
        "## Inference latency",
        "",
        "Wall-clock time of `predict_proba` on this machine (see Environment), single process.",
        "",
        "| Measure | Value |",
        "|---|---|",
    ]
    latency = payload["latency"]
    out += [
        f"| Single record, median ({latency['single_record_calls']} calls) | "
        f"{latency['single_record_median_ms']:.2f} ms |",
        f"| Single record, p95 | {latency['single_record_p95_ms']:.2f} ms |",
        f"| Batch of {latency['batch_size']}, median ({latency['batch_repeats']} runs) | "
        f"{latency['batch_median_ms']:.1f} ms |",
        f"| Batch per-record | {latency['batch_per_record_us']:.1f} µs |",
        f"| Batch throughput | {latency['batch_throughput_records_per_s']:.0f} records/s |",
        "",
        "## Environment",
        "",
        *_environment_lines(payload["environment"], payload["git_commit"]),
        "",
        METRIC_LIMITATIONS,
    ]
    return "\n".join(out)
