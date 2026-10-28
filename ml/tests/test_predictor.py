import json
import math
import shutil
from pathlib import Path
from typing import Any

import pytest

from sentinel_ml.artifacts import ArtifactError, load_pipeline
from sentinel_ml.features.cleaning import clean_frame
from sentinel_ml.inference import Predictor
from sentinel_ml.inference.predictor import MAX_BATCH_RECORDS
from sentinel_ml.schema import CLASS_LABELS, NORMAL
from sentinel_ml.training.train import TrainingResult
from tests.synthetic import make_partitioned_frame


@pytest.fixture(scope="module")
def predictor(trained: TrainingResult) -> Predictor:
    return Predictor.load(trained.artifact_dir, trained.manifest.model_sha256)


def _records(n: int = 5) -> list[dict[str, Any]]:
    """SYNTHETIC records with native Python types, as the API would receive them."""
    frame = make_partitioned_frame(max(n, 40), seed=3).head(n)
    return [
        {k: (v.item() if hasattr(v, "item") else v) for k, v in row.items()}
        for row in frame.to_dict(orient="records")
    ]


def test_valid_records_get_supported_labels_and_scores(predictor: Predictor) -> None:
    batch = predictor.predict_records(_records())
    assert not batch.rejected
    assert [p.index for p in batch.predictions] == list(range(5))
    assert batch.model_name == predictor.manifest.name
    for prediction in batch.predictions:
        assert prediction.predicted_category in CLASS_LABELS
        assert prediction.is_suspicious == (prediction.predicted_category != NORMAL)
        assert math.isclose(sum(prediction.class_scores.values()), 1.0, rel_tol=1e-6)
        assert prediction.model_score == max(prediction.class_scores.values())


def test_predictor_uses_the_saved_pipeline_unchanged(
    predictor: Predictor, trained: TrainingResult
) -> None:
    # Training sees CSV text passed through clean_frame; so must the reference prediction.
    raw = make_partitioned_frame(100, seed=11).astype(str)
    cleaned = clean_frame(raw, predictor.features, require_labels=False).features
    pipeline = load_pipeline(trained.artifact_dir, trained.manifest.model_sha256)
    expected = pipeline.predict(cleaned).tolist()
    batch = predictor.predict_frame(raw)
    assert [p.predicted_category for p in batch.predictions] == expected


def test_category_case_and_whitespace_match_training(predictor: Predictor) -> None:
    # The dataset writes states in upper case ("FIN"); cleaning lower-cases them for both
    # training and inference, so callers may send either form.
    base = _records(1)[0]
    records = [{**base, "state": " FIN "}, {**base, "state": "fin"}]
    batch = predictor.predict_records(records)
    assert [p.unknown_categories for p in batch.predictions] == [{}, {}]
    assert batch.predictions[0].class_scores == batch.predictions[1].class_scores


def test_aliased_column_names_are_accepted(predictor: Predictor) -> None:
    frame = make_partitioned_frame(40, seed=5).rename(
        columns={"smean": "smeansz", "dmean": "dmeansz", "response_body_len": "res_bdy_len"}
    )
    assert len(predictor.predict_frame(frame).predictions) == 40


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("sbytes", "123", "invalid_type:sbytes"),
        ("sbytes", True, "invalid_type:sbytes"),
        ("proto", 6, "invalid_type:proto"),
        ("dur", None, "missing_value:dur"),
        ("dur", float("nan"), "missing_value:dur"),
        ("dur", float("inf"), "invalid_value:dur"),
        ("proto", "", "missing_value:proto"),
    ],
)
def test_malformed_records_are_rejected_individually(
    predictor: Predictor, field: str, value: object, reason: str
) -> None:
    records = _records(3)
    records[1][field] = value
    batch = predictor.predict_records(records)
    assert [r.index for r in batch.rejected] == [1]
    assert batch.rejected[0].reasons == [reason]
    assert [p.index for p in batch.predictions] == [0, 2]


def test_missing_field_is_rejected_not_imputed(predictor: Predictor) -> None:
    records = _records(2)
    del records[0]["ct_flw_http_mthd"]
    batch = predictor.predict_records(records)
    assert batch.rejected[0].reasons == ["missing_field:ct_flw_http_mthd"]


def test_null_in_nullable_feature_is_imputed_and_reported(predictor: Predictor) -> None:
    records = _records(1)
    records[0]["ct_flw_http_mthd"] = None
    batch = predictor.predict_records(records)
    assert batch.predictions[0].imputed_features == ["ct_flw_http_mthd"]


def test_unseen_category_is_flagged(predictor: Predictor) -> None:
    records = _records(1)
    records[0]["service"] = "gopher"
    batch = predictor.predict_records(records)
    assert batch.predictions[0].unknown_categories == {"service": "gopher"}


def test_empty_and_oversized_input(predictor: Predictor) -> None:
    empty = predictor.predict_records([])
    assert empty.predictions == [] and empty.rejected == []
    with pytest.raises(ValueError, match="At most"):
        predictor.predict_records([{}] * (MAX_BATCH_RECORDS + 1))


def test_global_importance_is_normalised(predictor: Predictor) -> None:
    importance = predictor.global_feature_importance()
    assert set(importance) == set(predictor.features)
    assert math.isclose(sum(importance.values()), 1.0)
    assert len(predictor.global_feature_importance(top=5)) == 5


def test_wrong_trusted_hash_is_refused(trained: TrainingResult) -> None:
    with pytest.raises(ArtifactError, match="trusted"):
        Predictor.load(trained.artifact_dir, "0" * 64)


def test_tampered_model_file_is_refused(trained: TrainingResult, tmp_path: Path) -> None:
    copy = tmp_path / "artifact"
    shutil.copytree(trained.artifact_dir, copy)
    with (copy / "model.joblib").open("ab") as handle:
        handle.write(b"tampered")
    with pytest.raises(ArtifactError, match="Integrity check failed"):
        Predictor.load(copy, trained.manifest.model_sha256)


def test_feature_schema_version_mismatch_is_refused(
    trained: TrainingResult, tmp_path: Path
) -> None:
    copy = tmp_path / "artifact"
    shutil.copytree(trained.artifact_dir, copy)
    manifest = json.loads((copy / "manifest.json").read_text())
    manifest["feature_schema_version"] = 999
    (copy / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ArtifactError, match="schema"):
        Predictor.load(copy, trained.manifest.model_sha256)


def test_missing_or_malformed_manifest_is_refused(trained: TrainingResult, tmp_path: Path) -> None:
    copy = tmp_path / "artifact"
    shutil.copytree(trained.artifact_dir, copy)
    (copy / "manifest.json").write_text("{not json")
    with pytest.raises(ArtifactError, match="Malformed"):
        Predictor.load(copy, trained.manifest.model_sha256)
    (copy / "manifest.json").unlink()
    with pytest.raises(ArtifactError, match="No manifest"):
        Predictor.load(copy, trained.manifest.model_sha256)


def test_artifact_from_another_scikit_learn_version_is_refused(
    trained: TrainingResult, tmp_path: Path
) -> None:
    copy = tmp_path / "artifact"
    shutil.copytree(trained.artifact_dir, copy)
    manifest = json.loads((copy / "manifest.json").read_text())
    manifest["environment"]["scikit-learn"] = "0.24.2"
    (copy / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ArtifactError, match="Retrain"):
        Predictor.load(copy, trained.manifest.model_sha256)
