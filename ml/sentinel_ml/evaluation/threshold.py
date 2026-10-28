"""Choose an alert threshold on the attack score using the validation split only.

At the model's default decision (highest-scoring class) many Normal records are predicted as
attacks. A threshold on the attack score, ``1 - score(Normal)``, trades some attack recall
for fewer false alerts. It is chosen here on the validation split of the training file —
the same rows used for model selection — and never on the testing file.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from sentinel_ml.artifacts import ArtifactError, load_manifest, load_pipeline
from sentinel_ml.environment import environment_info, git_commit
from sentinel_ml.evaluation.evaluate import load_training_file
from sentinel_ml.evaluation.metrics import measure_latency
from sentinel_ml.evaluation.report import SYNTHETIC_BANNER
from sentinel_ml.preprocessing.pipeline import configure_for_inference
from sentinel_ml.schema import NORMAL, get_profile
from sentinel_ml.training.train import split_training_data

logger = logging.getLogger(__name__)

REPORTED_TARGET_FPRS = (0.01, 0.02, 0.05, 0.10, 0.20)
DEFAULT_TARGET_FPR = 0.05
THRESHOLD_FILE = "threshold.json"


def threshold_for_target(normal_scores: NDArray[np.float64], target_fpr: float) -> float:
    """Smallest threshold whose false-positive rate on these Normal scores is <= target.

    A record is alerted when ``attack_score >= threshold``.
    """
    if not 0 <= target_fpr <= 1:
        raise ValueError("target_fpr must be between 0 and 1")
    if normal_scores.size == 0:
        raise ValueError("No Normal records to set a threshold on")
    ordered = np.sort(normal_scores)[::-1]
    allowed = int(np.floor(target_fpr * ordered.size))
    if allowed >= ordered.size:
        return 0.0
    # Strictly above the (allowed + 1)-th highest Normal score, so at most `allowed` Normal
    # records reach the threshold.
    return float(np.nextafter(ordered[allowed], np.inf))


def operating_point(
    attack_scores: NDArray[np.float64], is_attack: NDArray[np.bool_], threshold: float
) -> dict[str, float]:
    flagged = attack_scores >= threshold
    normal, attack = ~is_attack, is_attack
    return {
        "threshold": threshold,
        "false_positive_rate": float(flagged[normal].mean()) if normal.any() else 0.0,
        "attack_recall": float(flagged[attack].mean()) if attack.any() else 0.0,
        "share_alerted": float(flagged.mean()),
    }


def select_threshold(
    artifact_dir: Path,
    data_dir: Path,
    reports_dir: Path,
    *,
    target_fpr: float = DEFAULT_TARGET_FPR,
    latency_calls: int = 200,
) -> Path:
    manifest = load_manifest(artifact_dir)
    pipeline = configure_for_inference(load_pipeline(artifact_dir, manifest.model_sha256))
    logger.info("Re-creating the validation split from the training file")
    dataset = load_training_file(manifest, data_dir)
    split = split_training_data(
        dataset,
        get_profile(manifest.feature_profile),
        manifest.seed,
        manifest.selection["validation_fraction"],
    )
    if len(split.x_val) != manifest.selection["validation_rows"]:
        raise ArtifactError("Could not reproduce the validation split recorded in the manifest")

    classes = [str(c) for c in pipeline.classes_]
    if NORMAL not in classes:
        raise ArtifactError("Model has no Normal class; an attack-score threshold is undefined")
    logger.info("Scoring %d validation rows", len(split.x_val))
    probabilities = pipeline.predict_proba(split.x_val)
    attack_scores = 1.0 - probabilities[:, classes.index(NORMAL)]
    is_attack = split.y_val.to_numpy() != NORMAL
    normal_scores = attack_scores[~is_attack]

    targets = sorted({*REPORTED_TARGET_FPRS, target_fpr})
    points = [
        {
            "target_fpr": t,
            **operating_point(attack_scores, is_attack, threshold_for_target(normal_scores, t)),
        }
        for t in targets
    ]
    predicted = np.asarray(classes)[probabilities.argmax(axis=1)]
    default_flagged = predicted != NORMAL
    default_point = {
        "false_positive_rate": float(default_flagged[~is_attack].mean()),
        "attack_recall": float(default_flagged[is_attack].mean()),
        "share_alerted": float(default_flagged.mean()),
    }
    chosen = next(p for p in points if p["target_fpr"] == target_fpr)

    logger.info("Measuring single-threaded latency")
    payload: dict[str, Any] = {
        "model": {
            "name": manifest.name,
            "version": manifest.version,
            "sha256": manifest.model_sha256,
        },
        "data_origin": dataset.origin,
        "selected_on": "validation split of the training file (testing file not used)",
        "validation_rows": len(split.x_val),
        "validation_normal_rows": int((~is_attack).sum()),
        "score": "attack_score = 1 - score(Normal); uncalibrated",
        "target_fpr": target_fpr,
        "threshold": chosen["threshold"],
        "chosen": chosen,
        "operating_points": points,
        "default_decision": default_point,
        "latency_single_threaded": measure_latency(
            pipeline, split.x_val, single_calls=latency_calls
        ),
        "environment": environment_info(),
        "git_commit": git_commit(),
        "created_at": datetime.now(UTC).isoformat(),
    }
    report_dir = reports_dir / artifact_dir.name
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / THRESHOLD_FILE).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (report_dir / "threshold.md").write_text(_render(payload), encoding="utf-8")
    return report_dir


def _pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def _render(payload: dict[str, Any]) -> str:
    model = payload["model"]
    out = [f"# Alert threshold — {model['name']} {model['version']}", ""]
    if payload["data_origin"] == "synthetic":
        out += [SYNTHETIC_BANNER]
    chosen = payload["chosen"]
    out += [
        f"- Chosen on: **{payload['selected_on']}** ({payload['validation_rows']} rows, "
        f"{payload['validation_normal_rows']} Normal)",
        f"- Score: {payload['score']}",
        f"- Target false-positive rate: {_pct(payload['target_fpr'])} -> threshold "
        f"**{chosen['threshold']:.6f}**",
        f"- On validation at that threshold: false-positive rate "
        f"{_pct(chosen['false_positive_rate'])}, attack recall {_pct(chosen['attack_recall'])}",
        "",
        "A record raises an alert when its attack score is at or above the threshold; its",
        "category is then the highest-scoring attack class. Validation rows come from the same",
        "file as the training rows, so the testing file (a shifted distribution) is likely to",
        "show a higher false-positive rate at the same threshold.",
        "",
        "## Operating points on the validation split",
        "",
        "| Target FPR | Threshold | Validation FPR | Validation attack recall | Share alerted |",
        "|---|---|---|---|---|",
    ]
    for p in payload["operating_points"]:
        out.append(
            f"| {_pct(p['target_fpr'])} | {p['threshold']:.6f} | {_pct(p['false_positive_rate'])} "
            f"| {_pct(p['attack_recall'])} | {_pct(p['share_alerted'])} |"
        )
    d = payload["default_decision"]
    out += [
        f"| default decision (highest class) | — | {_pct(d['false_positive_rate'])} "
        f"| {_pct(d['attack_recall'])} | {_pct(d['share_alerted'])} |",
        "",
        "## Single-threaded latency (validation rows)",
        "",
    ]
    lat = payload["latency_single_threaded"]
    out += [
        f"- Single record: median {lat['single_record_median_ms']:.2f} ms, "
        f"p95 {lat['single_record_p95_ms']:.2f} ms ({lat['single_record_calls']} calls)",
        f"- Batch of {lat['batch_size']}: median {lat['batch_median_ms']:.1f} ms "
        f"({lat['batch_throughput_records_per_s']:.0f} records/s)",
        "",
        "## Environment",
        "",
        *[f"- {k}: `{v}`" for k, v in payload["environment"].items()],
        f"- git commit: `{payload['git_commit'] or 'unknown'}`",
        "",
    ]
    return "\n".join(out)
