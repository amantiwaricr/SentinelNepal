"""The frontend's API types are generated from frontend/openapi.json; keep it current."""

from pathlib import Path

from app.cli import openapi_document

SNAPSHOT = Path(__file__).resolve().parents[3] / "frontend" / "openapi.json"


def test_committed_openapi_matches_the_api() -> None:
    assert SNAPSHOT.read_text(encoding="utf-8") == openapi_document(), (
        "API changed: run `python -m app.cli export-openapi` in backend/, then "
        "`npm run gen:api` in frontend/, and commit both"
    )
