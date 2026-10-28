from pathlib import Path

import pytest

from sentinel_ml.testing import write_synthetic_partitioned
from sentinel_ml.training.train import CANDIDATES, TrainingResult, train_model


@pytest.fixture(scope="session")
def synthetic_data_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return write_synthetic_partitioned(tmp_path_factory.mktemp("synthetic_data"))


@pytest.fixture(scope="session")
def trained(synthetic_data_dir: Path, tmp_path_factory: pytest.TempPathFactory) -> TrainingResult:
    """One small model trained on SYNTHETIC data, shared by tests that only read it."""
    out = tmp_path_factory.mktemp("training")
    return train_model(
        synthetic_data_dir,
        out / "artifacts",
        out / "reports",
        rf_estimators=20,
        n_jobs=1,
        candidates=CANDIDATES,
        version="test",
    )
