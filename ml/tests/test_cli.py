from pathlib import Path

import pytest

from sentinel_ml.cli import feature_table_markdown, main
from sentinel_ml.schema import ALL_FEATURES

DOC = Path(__file__).resolve().parents[2] / "docs" / "feature-mapping.md"
BEGIN = "<!-- BEGIN GENERATED: sentinel-ml feature-table -->"
END = "<!-- END GENERATED -->"


def test_feature_table_lists_every_feature() -> None:
    table = feature_table_markdown()
    for name in ALL_FEATURES:
        assert f"| `{name}` |" in table


@pytest.mark.parametrize("source", ["zeek", "tshark"])
def test_feature_mapping_doc_matches_code(source: str) -> None:
    # docs/feature-mapping.md embeds the generated tables; regenerate them with
    # `sentinel-ml feature-table [--source tshark]` whenever a mapping changes.
    begin = BEGIN if source == "zeek" else BEGIN.replace("-->", "").rstrip() + " tshark -->"
    text = DOC.read_text(encoding="utf-8")
    embedded = text.split(begin, 1)[1].split(END, 1)[0].strip()
    assert embedded == feature_table_markdown(source).strip()


def test_cli_profile_train_evaluate_on_synthetic_data(
    synthetic_data_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    reports = tmp_path / "reports"
    artifacts = tmp_path / "artifacts"
    assert (
        main(["profile", "--data-dir", str(synthetic_data_dir), "--reports-dir", str(reports)]) == 0
    )
    assert "SYNTHETIC" in (reports / "data_profile.md").read_text(encoding="utf-8")

    assert (
        main(
            [
                "train",
                "--data-dir",
                str(synthetic_data_dir),
                "--artifacts-dir",
                str(artifacts),
                "--reports-dir",
                str(reports),
                "--rf-estimators",
                "5",
                "--n-jobs",
                "1",
            ]
        )
        == 0
    )
    artifact = next(artifacts.iterdir())
    assert (
        main(
            [
                "evaluate",
                str(artifact),
                "--data-dir",
                str(synthetic_data_dir),
                "--reports-dir",
                str(reports),
            ]
        )
        == 0
    )
    assert (reports / artifact.name / "evaluation.md").exists()
    assert "SHA-256" in capsys.readouterr().out


def test_profile_without_data_points_to_instructions(tmp_path: Path) -> None:
    from sentinel_ml.features.dataset import DatasetError

    with pytest.raises(DatasetError, match=r"ml/data/README.md"):
        main(["profile", "--data-dir", str(tmp_path), "--reports-dir", str(tmp_path)])


def test_training_reports_progress(
    synthetic_data_dir: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level("INFO")
    main(
        [
            "train",
            "--data-dir",
            str(synthetic_data_dir),
            "--artifacts-dir",
            str(tmp_path / "a"),
            "--reports-dir",
            str(tmp_path / "r"),
            "--rf-estimators",
            "5",
            "--n-jobs",
            "1",
        ]
    )
    messages = [r.getMessage() for r in caplog.records]
    assert any(m.startswith("Fitting candidate 1/4") for m in messages)
    assert any("validation macro-F1" in m for m in messages)
    assert any(m.startswith("Selected ") for m in messages)
