import shutil
import subprocess
from pathlib import Path

import pytest

from sentinel_ml.environment import environment_info, git_commit

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")


def _git(repo: Path, *args: str) -> None:
    # Test-only helper with fixed git sub-commands chosen in this file.
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)  # noqa: S603, S607


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "test@example.invalid")
    _git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "code.py").write_text("x = 1\n", encoding="utf-8")
    _git(tmp_path, "add", "code.py")
    _git(tmp_path, "commit", "-q", "-m", "init")
    return tmp_path


def test_clean_checkout_reports_plain_commit(repo: Path) -> None:
    commit = git_commit(repo)
    assert commit is not None and len(commit) == 40


def test_untracked_files_do_not_mark_the_commit_dirty(repo: Path) -> None:
    (repo / "data_profile.md").write_text("generated report\n", encoding="utf-8")
    commit = git_commit(repo)
    assert commit is not None and not commit.endswith("+dirty")


def test_modified_tracked_file_marks_the_commit_dirty(repo: Path) -> None:
    (repo / "code.py").write_text("x = 2\n", encoding="utf-8")
    commit = git_commit(repo)
    assert commit is not None and commit.endswith("+dirty")


def test_outside_a_repository_returns_none(tmp_path: Path) -> None:
    assert git_commit(tmp_path) is None


def test_environment_info_lists_library_versions() -> None:
    info = environment_info()
    for key in ("python", "numpy", "pandas", "scikit-learn", "joblib", "cpu_count"):
        assert info[key]
