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

    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except AppError as exc:
        print(f"Error: {exc.message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
