"""Administrative commands run on the server: ``python -m app.cli <command>``.

These are for operators with shell access to the backend host (e.g. creating the first
administrator, registering a trained model). They are never exposed over HTTP.
"""

import argparse
import getpass
import os
import sys

from app.core.errors import AppError
from app.db.session import default_sessionmaker
from app.services.audit import AuditContext


def _read_password(env_var: str | None) -> str:
    if env_var:
        value = os.environ.get(env_var)
        if not value:
            raise SystemExit(f"Environment variable {env_var} is not set")
        return value
    first = getpass.getpass("Password: ")
    if first != getpass.getpass("Repeat password: "):
        raise SystemExit("Passwords do not match")
    return first


def cmd_create_user(args: argparse.Namespace) -> int:
    from app.services.users import create_user

    password = _read_password(args.password_env)
    with default_sessionmaker()() as db:
        user = create_user(db, AuditContext.system("cli"), args.username, password, args.role)
    print(f"Created {user.role} '{user.username}' (id {user.id})")
    return 0


def cmd_register_model(args: argparse.Namespace) -> int:
    from pathlib import Path

    from app.core.config import get_settings
    from app.services.models import register_model

    with default_sessionmaker()() as db:
        model = register_model(
            db,
            get_settings(),
            AuditContext.system("cli"),
            Path(args.artifact_dir),
            reports_dir=Path(args.reports_dir) if args.reports_dir else None,
            activate=args.activate,
            allow_synthetic=args.allow_synthetic,
        )
    threshold = (
        f"alert threshold {model.alert_threshold:.6f}"
        if model.alert_threshold is not None
        else "no threshold.json found: alerts use the model's default decision"
    )
    print(f"Registered model {model.id}: {model.name} {model.version} ({threshold})")
    print(f"Active: {model.is_active}; SHA-256 {model.artifact_sha256}")
    return 0


def cmd_activate_model(args: argparse.Namespace) -> int:
    from app.services.models import activate_model

    with default_sessionmaker()() as db:
        model = activate_model(db, AuditContext.system("cli"), args.model_id)
    print(f"Activated model {model.id}: {model.name} {model.version}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_user = sub.add_parser("create-user", help="Create a user (e.g. the first administrator)")
    p_user.add_argument("--username", required=True)
    p_user.add_argument("--role", choices=["admin", "analyst"], required=True)
    p_user.add_argument(
        "--password-env",
        metavar="VAR",
        help="Read the password from this environment variable instead of prompting",
    )
    p_user.set_defaults(handler=cmd_create_user)

    p_reg = sub.add_parser(
        "register-model", help="Register a trained artifact (from ml/artifacts) for use"
    )
    p_reg.add_argument("artifact_dir", help="Directory inside MODEL_ARTIFACTS_DIR")
    p_reg.add_argument(
        "--reports-dir",
        help="ml/reports directory; evaluation.json and threshold.json are read from it",
    )
    p_reg.add_argument("--activate", action="store_true", help="Make it the active model")
    p_reg.add_argument(
        "--allow-synthetic",
        action="store_true",
        help="Permit models trained on synthetic test data (testing only)",
    )
    p_reg.set_defaults(handler=cmd_register_model)

    p_act = sub.add_parser("activate-model", help="Make a registered model active")
    p_act.add_argument("model_id", type=int)
    p_act.set_defaults(handler=cmd_activate_model)

    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except AppError as exc:
        print(f"Error: {exc.message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
