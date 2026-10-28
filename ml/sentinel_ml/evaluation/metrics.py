"""Classification metrics, including the binary Normal-vs-attack view and latency."""

from __future__ import annotations

import time
from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline

from sentinel_ml.schema import NORMAL


def binary_metrics(y_true: Sequence[str], y_pred: Sequence[str]) -> dict[str, float | int]:
    """Treat every non-Normal class as 'attack'. FPR = Normal records flagged as attack."""
    true_attack = np.asarray(y_true) != NORMAL
    pred_attack = np.asarray(y_pred) != NORMAL
    tp = int(np.sum(true_attack & pred_attack))
    fp = int(np.sum(~true_attack & pred_attack))
    tn = int(np.sum(~true_attack & ~pred_attack))
    fn = int(np.sum(true_attack & ~pred_attack))

    def ratio(numerator: int, denominator: int) -> float:
        return numerator / denominator if denominator else 0.0

    precision = ratio(tp, tp + fp)
    recall = ratio(tp, tp + fn)
    return {
        "true_positives": tp,
        "false_positives": fp,
        "true_negatives": tn,
        "false_negatives": fn,
        "precision": precision,
        "recall": recall,
        "f1": ratio(2 * tp, 2 * tp + fp + fn),
        "false_positive_rate": ratio(fp, fp + tn),
        "false_negative_rate": ratio(fn, fn + tp),
    }


def classification_metrics(
    y_true: Sequence[str], y_pred: Sequence[str], labels: Sequence[str]
) -> dict[str, Any]:
    labels = list(labels)
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=labels, zero_division=0
    )
    per_class = {
        label: {
            "precision": float(precision[i]),
            "recall": float(recall[i]),
            "f1": float(f1[i]),
            "support": int(support[i]),
        }
        for i, label in enumerate(labels)
    }
    present = [label for label in labels if per_class[label]["support"] > 0]
    return {
        "records": len(y_true),
        "per_class": per_class,
        # Macro averages only over classes present in y_true, so absent classes do not count
        # as zero scores.
        "macro_f1": float(
            f1_score(y_true, y_pred, labels=present, average="macro", zero_division=0)
        ),
        "weighted_f1": float(
            f1_score(y_true, y_pred, labels=present, average="weighted", zero_division=0)
        ),
        "accuracy": float(np.mean(np.asarray(y_true) == np.asarray(y_pred))),
        "binary": binary_metrics(y_true, y_pred),
        "confusion_matrix": {
            "labels": labels,
            "matrix": confusion_matrix(y_true, y_pred, labels=labels).tolist(),
        },
    }


def ranking_metrics(
    y_true: Sequence[str], proba: np.ndarray, classes: Sequence[str]
) -> dict[str, float | None]:
    """Threshold-free binary view using attack score = 1 - score(Normal). Uncalibrated."""
    true_attack = (np.asarray(y_true) != NORMAL).astype(int)
    if len(set(true_attack.tolist())) < 2:
        return {"roc_auc": None, "average_precision": None}
    normal_index = list(classes).index(NORMAL)
    attack_score = 1.0 - proba[:, normal_index]
    return {
        "roc_auc": float(roc_auc_score(true_attack, attack_score)),
        "average_precision": float(average_precision_score(true_attack, attack_score)),
    }


def measure_latency(
    pipeline: Pipeline,
    features: pd.DataFrame,
    *,
    single_calls: int = 200,
    batch_size: int = 1000,
    batch_repeats: int = 5,
    seed: int = 42,
) -> dict[str, float | int]:
    """Wall-clock prediction latency for one record per call and for batches."""
    if features.empty:
        raise ValueError("Cannot measure latency on an empty frame")
    rng = np.random.default_rng(seed)
    pipeline.predict_proba(features.iloc[:1])  # warm-up, excluded from timings

    single_ms = []
    for index in rng.integers(0, len(features), size=single_calls):
        row = features.iloc[[int(index)]]
        start = time.perf_counter()
        pipeline.predict_proba(row)
        single_ms.append((time.perf_counter() - start) * 1000)

    size = min(batch_size, len(features))
    batch_ms = []
    for _ in range(batch_repeats):
        rows = features.iloc[rng.choice(len(features), size=size, replace=False)]
        start = time.perf_counter()
        pipeline.predict_proba(rows)
        batch_ms.append((time.perf_counter() - start) * 1000)

    median_batch = float(np.median(batch_ms))
    return {
        "single_record_calls": single_calls,
        "single_record_median_ms": float(np.median(single_ms)),
        "single_record_p95_ms": float(np.percentile(single_ms, 95)),
        "batch_size": size,
        "batch_repeats": batch_repeats,
        "batch_median_ms": median_batch,
        "batch_per_record_us": median_batch * 1000 / size,
        "batch_throughput_records_per_s": size / (median_batch / 1000) if median_batch else 0.0,
    }
