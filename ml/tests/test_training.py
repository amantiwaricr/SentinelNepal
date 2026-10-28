import json
from pathlib import Path

import pandas as pd
import pytest

from sentinel_ml.artifacts import ArtifactError, load_manifest, load_pipeline, save_artifact
from sentinel_ml.features.dataset import DatasetError, sha256_file
from sentinel_ml.schema import CLASS_LABELS, TEST_FILE, TRAIN_FILE, get_profile
from sentinel_ml.training.train import CANDIDATES, CandidateSpec, TrainingResult, train_model
from tests.synthetic import make_partitioned_frame, write_synthetic_partitioned

FAST_RF = (CandidateSpec("random_forest", "random_forest", None),)


def test_artifact_and_manifest_describe_the_model(trained: TrainingResult) -> None:
    manifest = load_manifest(trained.artifact_dir)
    profile = get_profile("full")
    assert manifest.features == list(profile.features)
    assert manifest.data_origin == "synthetic"
    assert manifest.model_sha256 == sha256_file(trained.artifact_dir / "model.joblib")
    assert set(manifest.class_labels) <= set(CLASS_LABELS)
    assert [c["name"] for c in manifest.selection["candidates"]] == [c.name for c in CANDIDATES]
    assert manifest.selection["selected"] in {c.name for c in CANDIDATES}
    assert manifest.training_sources[0]["name"] == TRAIN_FILE
    assert abs(sum(manifest.feature_importance.values()) - 1) < 1e-9
    assert any("uncalibrated" in note for note in manifest.notes)


def test_pipeline_inputs_match_feature_definitions(trained: TrainingResult) -> None:
    pipeline = load_pipeline(trained.artifact_dir, trained.manifest.model_sha256)
    fitted = list(pipeline.named_steps["preprocess"].feature_names_in_)
    assert fitted == list(get_profile("full").features)
    for forbidden in ("id", "rate", "label", "attack_cat", "src_ip", "stcpb"):
        assert forbidden not in fitted


def test_training_reports_are_written_and_marked_synthetic(trained: TrainingResult) -> None:
    markdown = (trained.report_dir / "training.md").read_text(encoding="utf-8")
    assert "SYNTHETIC DATA" in markdown
    payload = json.loads((trained.report_dir / "training.json").read_text(encoding="utf-8"))
    assert payload["data_origin"] == "synthetic"


def test_training_never_needs_the_testing_file(tmp_path: Path) -> None:
    data = write_synthetic_partitioned(tmp_path / "data", train_rows=400, test_rows=60)
    (data / TEST_FILE).unlink()
    result = train_model(
        data, tmp_path / "a", tmp_path / "r", candidates=FAST_RF, rf_estimators=5, n_jobs=1
    )
    assert result.artifact_dir.exists()


def test_same_seed_gives_identical_results(tmp_path: Path) -> None:
    data = write_synthetic_partitioned(tmp_path / "data", train_rows=500, test_rows=60)
    runs = [
        train_model(
            data,
            tmp_path / f"a{i}",
            tmp_path / f"r{i}",
            candidates=FAST_RF,
            rf_estimators=10,
            n_jobs=1,
            version="v",
        )
        for i in range(2)
    ]
    first, second = (r.manifest.selection["candidates"][0]["validation"] for r in runs)
    assert first == second
    sample = make_partitioned_frame(200, seed=99)[list(get_profile("full").features)]
    predictions = [
        load_pipeline(r.artifact_dir, r.manifest.model_sha256).predict_proba(sample) for r in runs
    ]
    assert (predictions[0] == predictions[1]).all()


def test_duplicates_are_removed_before_splitting(tmp_path: Path) -> None:
    data = write_synthetic_partitioned(tmp_path / "data", train_rows=300, test_rows=60)
    frame = pd.read_csv(data / TRAIN_FILE)
    duplicated = pd.concat([frame, frame.iloc[:50].assign(id=range(10_000, 10_050))])
    duplicated.to_csv(data / TRAIN_FILE, index=False)
    result = train_model(
        data, tmp_path / "a", tmp_path / "r", candidates=FAST_RF, rf_estimators=5, n_jobs=1
    )
    assert result.manifest.selection["duplicates_removed"] == 50


def test_live_compatible_profile_trains_without_unavailable_features(tmp_path: Path) -> None:
    data = write_synthetic_partitioned(tmp_path / "data", train_rows=400, test_rows=60)
    result = train_model(
        data,
        tmp_path / "a",
        tmp_path / "r",
        profile_name="live_compatible",
        candidates=FAST_RF,
        rf_estimators=5,
        n_jobs=1,
    )
    assert result.manifest.name == "random_forest-live_compatible"
    assert "sttl" not in result.manifest.features
    assert result.manifest.features == list(get_profile("live_compatible").features)


def test_class_with_a_single_record_cannot_be_split(tmp_path: Path) -> None:
    data = write_synthetic_partitioned(tmp_path / "data", train_rows=300, test_rows=60)
    frame = pd.read_csv(data / TRAIN_FILE)
    worms = frame.index[frame["attack_cat"] == "Worms"]
    frame.drop(index=worms[1:]).to_csv(data / TRAIN_FILE, index=False)
    with pytest.raises(DatasetError, match="Worms"):
        train_model(data, tmp_path / "a", tmp_path / "r", candidates=FAST_RF, n_jobs=1)


def test_existing_artifact_is_never_overwritten(trained: TrainingResult) -> None:
    pipeline = load_pipeline(trained.artifact_dir, trained.manifest.model_sha256)
    with pytest.raises(ArtifactError, match="overwrite"):
        save_artifact(pipeline, trained.manifest, trained.artifact_dir.parent)


def test_empty_candidate_list_rejected(synthetic_data_dir: Path, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="candidate"):
        train_model(synthetic_data_dir, tmp_path, tmp_path, candidates=())


def test_fit_warnings_are_recorded_not_hidden(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sklearn.linear_model import LogisticRegression

    import sentinel_ml.preprocessing.pipeline as pipeline_module

    # Force non-convergence: one iteration is never enough.
    monkeypatch.setattr(
        pipeline_module, "build_estimator", lambda *a, **k: LogisticRegression(max_iter=1)
    )
    data = write_synthetic_partitioned(tmp_path / "data", train_rows=400, test_rows=60)
    result = train_model(data, tmp_path / "a", tmp_path / "r", candidates=CANDIDATES[:1], n_jobs=1)
    warnings = result.manifest.selection["candidates"][0]["warnings"]
    assert any(w.startswith("ConvergenceWarning") for w in warnings)
    assert "ConvergenceWarning" in (result.report_dir / "training.md").read_text(encoding="utf-8")
