import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from sentinel_ml.artifacts import ArtifactError
from sentinel_ml.evaluation.threshold import (
    operating_point,
    select_threshold,
    threshold_for_target,
)
from sentinel_ml.schema import TEST_FILE, TRAIN_FILE
from sentinel_ml.training.train import TrainingResult


def test_threshold_bounds_the_false_positive_rate() -> None:
    normal = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95])
    for target in (0.0, 0.1, 0.25, 0.5):
        threshold = threshold_for_target(normal, target)
        assert (normal >= threshold).mean() <= target
    # 10% of 10 Normal records = 1 allowed false positive: only 0.95 may reach the threshold.
    assert 0.9 < threshold_for_target(normal, 0.1) <= 0.95
    assert threshold_for_target(normal, 1.0) == 0.0


def test_threshold_input_validation() -> None:
    with pytest.raises(ValueError, match="between 0 and 1"):
        threshold_for_target(np.array([0.5]), 1.5)
    with pytest.raises(ValueError, match="No Normal"):
        threshold_for_target(np.array([]), 0.05)


def test_operating_point() -> None:
    scores = np.array([0.9, 0.2, 0.8, 0.1])
    is_attack = np.array([True, False, True, False])
    point = operating_point(scores, is_attack, 0.5)
    assert point == {
        "threshold": 0.5,
        "false_positive_rate": 0.0,
        "attack_recall": 1.0,
        "share_alerted": 0.5,
    }


def test_select_threshold_uses_only_the_validation_split(
    trained: TrainingResult, synthetic_data_dir: Path, tmp_path: Path
) -> None:
    data = tmp_path / "data"
    shutil.copytree(synthetic_data_dir, data)
    (data / TEST_FILE).unlink()  # must not be needed
    report_dir = select_threshold(
        trained.artifact_dir, data, tmp_path / "reports", target_fpr=0.05, latency_calls=10
    )
    payload = json.loads((report_dir / "threshold.json").read_text(encoding="utf-8"))
    assert payload["validation_rows"] == trained.manifest.selection["validation_rows"]
    assert payload["chosen"]["false_positive_rate"] <= 0.05
    assert payload["threshold"] == payload["chosen"]["threshold"]
    fprs = [p["false_positive_rate"] for p in payload["operating_points"]]
    assert fprs == sorted(fprs)  # looser targets never give fewer false positives
    assert payload["latency_single_threaded"]["single_record_median_ms"] > 0
    markdown = (report_dir / "threshold.md").read_text(encoding="utf-8")
    assert "SYNTHETIC DATA" in markdown and "testing file not used" in markdown


def test_select_threshold_refuses_changed_training_data(
    trained: TrainingResult, synthetic_data_dir: Path, tmp_path: Path
) -> None:
    data = tmp_path / "data"
    shutil.copytree(synthetic_data_dir, data)
    frame = pd.read_csv(data / TRAIN_FILE)
    frame.iloc[1:].to_csv(data / TRAIN_FILE, index=False)
    with pytest.raises(ArtifactError, match="differs"):
        select_threshold(trained.artifact_dir, data, tmp_path / "reports")
