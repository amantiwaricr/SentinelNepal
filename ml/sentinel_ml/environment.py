"""Record the software/hardware context of a run so results can be reproduced and qualified."""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


def library_versions() -> dict[str, str]:
    versions = {"python": sys.version.split()[0]}
    for package in ("numpy", "pandas", "scikit-learn", "joblib"):
        try:
            versions[package] = version(package)
        except PackageNotFoundError:
            versions[package] = "not installed"
    return versions


def environment_info() -> dict[str, str]:
    return {
        **library_versions(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or "unknown",
        "cpu_count": str(os.cpu_count()),
    }


def git_commit(start: Path | None = None) -> str | None:
    """Current commit, with '+dirty' if tracked files have uncommitted changes; None outside Git.

    Untracked files (e.g. freshly generated reports) do not count: they cannot change the code
    that produced a result.
    """
    cwd = start or Path(__file__).resolve().parent
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],  # noqa: S607 (fixed arguments, no user input)
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],  # noqa: S607
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    return f"{commit}+dirty" if dirty else commit
