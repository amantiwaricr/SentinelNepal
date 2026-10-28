"""Command-line entry point: ``python -m sentinel_ml.cli <command>`` or ``sentinel-ml``."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from sentinel_ml.schema import LIVE_FEATURE_MAP, PROFILES

ML_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ML_ROOT / "data"
DEFAULT_ARTIFACTS = ML_ROOT / "artifacts"
DEFAULT_REPORTS = ML_ROOT / "reports"


def feature_table_markdown() -> str:
    lines = [
        "| Dataset feature | Live source (Zeek) | Transformation | Availability | Limitation | "
        "In `live_compatible` |",
        "|---|---|---|---|---|---|",
    ]
    live = set(PROFILES["live_compatible"].features)
    for name, mapping in LIVE_FEATURE_MAP.items():
        lines.append(
            f"| `{name}` | {mapping.source} | {mapping.transformation} | "
            f"{mapping.availability.value} | {mapping.limitation} | "
            f"{'yes' if name in live else 'no'} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sentinel-ml", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_profile = sub.add_parser("profile", help="Inspect the dataset files and write a report")
    p_profile.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    p_profile.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS)

    p_train = sub.add_parser("train", help="Train candidates and select on the validation split")
    p_train.add_argument("--profile", choices=sorted(PROFILES), default="full")
    p_train.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    p_train.add_argument("--artifacts-dir", type=Path, default=DEFAULT_ARTIFACTS)
    p_train.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS)
    p_train.add_argument("--seed", type=int, default=42)
    p_train.add_argument("--rf-estimators", type=int, default=200)
    p_train.add_argument("--n-jobs", type=int, default=-1)

    p_eval = sub.add_parser("evaluate", help="Evaluate an artifact once on the testing file")
    p_eval.add_argument("artifact_dir", type=Path)
    p_eval.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    p_eval.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS)

    p_threshold = sub.add_parser(
        "threshold", help="Choose an alert threshold on the validation split (not the test file)"
    )
    p_threshold.add_argument("artifact_dir", type=Path)
    p_threshold.add_argument("--target-fpr", type=float, default=0.05)
    p_threshold.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    p_threshold.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS)

    sub.add_parser("feature-table", help="Print the dataset-to-Zeek feature mapping table")

    args = parser.parse_args(argv)
    # Progress goes to stderr so long runs never look stuck; results stay on stdout.
    # (No-op when logging is already configured, e.g. under pytest.)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    # Imported lazily so `feature-table` and `--help` stay fast.
    if args.command == "profile":
        from sentinel_ml.features.profile import write_profile

        print(f"Wrote {write_profile(args.data_dir, args.reports_dir)}")
    elif args.command == "train":
        from sentinel_ml.training.train import train_model

        result = train_model(
            args.data_dir,
            args.artifacts_dir,
            args.reports_dir,
            profile_name=args.profile,
            seed=args.seed,
            rf_estimators=args.rf_estimators,
            n_jobs=args.n_jobs,
        )
        print(f"Selected {result.manifest.selection['selected']}")
        print(f"Artifact: {result.artifact_dir}")
        print(f"SHA-256:  {result.manifest.model_sha256}")
        print(f"Report:   {result.report_dir / 'training.md'}")
    elif args.command == "evaluate":
        from sentinel_ml.evaluation.evaluate import evaluate_model

        report_dir = evaluate_model(args.artifact_dir, args.data_dir, args.reports_dir)
        print(f"Report: {report_dir / 'evaluation.md'}")
    elif args.command == "threshold":
        from sentinel_ml.evaluation.threshold import select_threshold

        report_dir = select_threshold(
            args.artifact_dir, args.data_dir, args.reports_dir, target_fpr=args.target_fpr
        )
        print(f"Report: {report_dir / 'threshold.md'}")
    else:
        sys.stdout.write(feature_table_markdown())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
