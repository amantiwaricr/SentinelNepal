"""Every text file read or written by this package must name its encoding.

Without it, Python uses the platform's locale encoding (cp1252 on most Windows machines), so
reports written on Windows were not valid UTF-8. Ruff's PLW1514 only catches calls on a
literal ``Path(...)``, so this test checks every call site via the AST.
"""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCES = sorted([*ROOT.glob("sentinel_ml/**/*.py"), *ROOT.glob("tests/**/*.py")])
TEXT_METHODS = {"read_text", "write_text"}


def _binary_mode(call: ast.Call) -> bool:
    modes = [a for a in call.args if isinstance(a, ast.Constant) and isinstance(a.value, str)]
    modes += [
        k.value
        for k in call.keywords
        if k.arg == "mode" and isinstance(k.value, ast.Constant) and isinstance(k.value.value, str)
    ]
    return any("b" in str(m.value) for m in modes)


def _missing_encoding(path: Path) -> list[str]:
    problems = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
        if name not in TEXT_METHODS | {"open"}:
            continue
        if name == "open" and _binary_mode(node):
            continue
        if not any(k.arg == "encoding" for k in node.keywords):
            problems.append(f"{path.relative_to(ROOT)}:{node.lineno} {name}() without encoding")
    return problems


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: str(p.relative_to(ROOT)))
def test_text_io_names_its_encoding(path: Path) -> None:
    assert _missing_encoding(path) == []
