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


def cmd_create_collector(args: argparse.Namespace) -> int:
    from app.services.live.collectors import create_collector

    with default_sessionmaker()() as db:
        collector, token = create_collector(db, AuditContext.system("cli"), args.name)
    print(f"Created collector '{collector.name}' (id {collector.id}) in observation mode.")
    print("Its token is shown only once. Put it in .env as COLLECTOR_TOKEN:")
    print(token)
    return 0


def cmd_rotate_collector_token(args: argparse.Namespace) -> int:
    from app.services.live.collectors import rotate_token

    with default_sessionmaker()() as db:
        token = rotate_token(db, AuditContext.system("cli"), args.collector_id)
    print("New token (the old one stops working now; shown only once):")
    print(token)
    return 0


def openapi_document() -> str:
    """The API schema as committed in ``frontend/openapi.json`` (frontend types come from it)."""
    import json

    from app.core.config import Settings
    from app.main import create_app

    # Fixed development settings: the schema must not depend on the caller's environment.
    settings = Settings(environment="development", database_url="postgresql://unused/unused")
    return json.dumps(create_app(settings).openapi(), indent=2) + "\n"


def cmd_export_openapi(args: argparse.Namespace) -> int:
    from pathlib import Path

    Path(args.output).write_text(openapi_document(), encoding="utf-8")
    print(f"Wrote {args.output}")
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

    p_col = sub.add_parser("create-collector", help="Register a live collector; prints its token")
    p_col.add_argument("--name", required=True)
    p_col.set_defaults(handler=cmd_create_collector)

    p_rot = sub.add_parser("rotate-collector-token", help="Replace a collector's token")
    p_rot.add_argument("collector_id", type=int)
    p_rot.set_defaults(handler=cmd_rotate_collector_token)

    p_api = sub.add_parser(
        "export-openapi", help="Write the API schema used to generate the frontend types"
    )
    p_api.add_argument("--output", default="../frontend/openapi.json")
    p_api.set_defaults(handler=cmd_export_openapi)

    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except AppError as exc:
        print(f"Error: {exc.message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
