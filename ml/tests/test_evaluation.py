import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

from sentinel_ml.artifacts import ArtifactError
from sentinel_ml.evaluation.evaluate import evaluate_model
from sentinel_ml.evaluation.metrics import binary_metrics, classification_metrics
from sentinel_ml.schema import CLASS_LABELS, SYNTHETIC_MARKER_FILE, TRAIN_FILE
from sentinel_ml.training.train import TrainingResult


def test_binary_metrics_on_a_hand_checked_example() -> None:
    y_true = ["Normal", "Normal", "Normal", "Normal", "DoS", "DoS", "Exploits", "Generic"]
    y_pred = ["Normal", "Normal", "Normal", "DoS", "DoS", "Normal", "Generic", "Generic"]
    # Attacks: 4 true; predicted attack on 3 of them (DoS, Exploits->Generic, Generic) = TP 3,
    # FN 1. Normal: 4 true; one flagged (FP 1), TN 3.
    result = binary_metrics(y_true, y_pred)
    assert (result["true_positives"], result["false_negatives"]) == (3, 1)
    assert (result["false_positives"], result["true_negatives"]) == (1, 3)
    assert result["false_positive_rate"] == 0.25
    assert result["recall"] == 0.75
    assert result["precision"] == 0.75


def test_wrong_attack_category_still_counts_as_detected_in_binary_view() -> None:
    result = classification_metrics(["Exploits"], ["Generic"], CLASS_LABELS)
    assert result["binary"]["recall"] == 1.0
    assert result["per_class"]["Exploits"]["recall"] == 0.0


def test_macro_average_ignores_classes_absent_from_the_data() -> None:
    result = classification_metrics(["Normal", "DoS"], ["Normal", "DoS"], CLASS_LABELS)
    assert result["macro_f1"] == 1.0
    assert result["per_class"]["Worms"]["support"] == 0


def test_evaluation_writes_reports(
    trained: TrainingResult, synthetic_data_dir: Path, tmp_path: Path
) -> None:
    report_dir = evaluate_model(
        trained.artifact_dir, synthetic_data_dir, tmp_path, latency_calls=10
    )
    payload = json.loads((report_dir / "evaluation.json").read_text(encoding="utf-8"))
    assert payload["data_origin"] == "synthetic"
    assert payload["overlap_with_training"] == 5  # rows copied in by the synthetic generator
    assert payload["deduplicated"]["records"] == payload["all"]["records"] - 5
    assert payload["latency"]["single_record_median_ms"] > 0
    assert "SYNTHETIC DATA" in (report_dir / "evaluation.md").read_text(encoding="utf-8")
    matrix = pd.read_csv(report_dir / "confusion_matrix.csv", index_col=0)
    assert int(matrix.to_numpy().sum()) == payload["all"]["records"]


def test_evaluation_refuses_different_training_data(
    trained: TrainingResult, synthetic_data_dir: Path, tmp_path: Path
) -> None:
    data = tmp_path / "data"
    shutil.copytree(synthetic_data_dir, data)
    frame = pd.read_csv(data / TRAIN_FILE)
    frame.iloc[1:].to_csv(data / TRAIN_FILE, index=False)
    with pytest.raises(ArtifactError, match="differs"):
        evaluate_model(trained.artifact_dir, data, tmp_path / "r")


def test_evaluation_refuses_to_mix_synthetic_and_real_data(
    trained: TrainingResult, synthetic_data_dir: Path, tmp_path: Path
) -> None:
    data = tmp_path / "data"
    shutil.copytree(synthetic_data_dir, data)
    (data / SYNTHETIC_MARKER_FILE).unlink()
    with pytest.raises(ArtifactError, match="cannot be evaluated"):
        evaluate_model(trained.artifact_dir, data, tmp_path / "r")
