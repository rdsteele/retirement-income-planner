"""Guard: the project forbids hardcoded tax values in code.

Per CLAUDE.md, tax years, filing statuses, and rates must come from data files
(backend) or the API (frontend). This test scans the application source so a
violation fails CI instead of relying on review.
"""

import ast
import json
import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).parent.parent.parent
_SOURCE_DIRS = ["services", "api"]
_CONFIG = json.loads((_ROOT / "data" / "config.json").read_text())
_FILING_STATUSES = {s["value"] for s in _CONFIG["filing_statuses"]}

# Structural constants that are not tax rates (rounding precision).
_ALLOWED_DECIMAL_LITERALS = {"0.01", "0.0001"}


def _source_files() -> list[Path]:
    files: list[Path] = []
    for directory in _SOURCE_DIRS:
        files += [p for p in (_ROOT / directory).rglob("*.py") if "static" not in p.parts]
    return sorted(files)


def _docstring_nodes(tree: ast.AST) -> set[int]:
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                ids.add(id(body[0].value))
    return ids


def _violations(path: Path) -> list[str]:
    tree = ast.parse(path.read_text())
    docstrings = _docstring_nodes(tree)
    found: list[str] = []
    for node in ast.walk(tree):
        where = f"{path.relative_to(_ROOT)}:{getattr(node, 'lineno', '?')}"
        if isinstance(node, ast.Constant) and id(node) not in docstrings:
            if isinstance(node.value, str) and node.value in _FILING_STATUSES:
                found.append(f"{where} filing status literal {node.value!r}")
            if isinstance(node.value, int) and not isinstance(node.value, bool):
                if 1900 <= node.value <= 2100:
                    found.append(f"{where} year literal {node.value}")
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "Decimal":
            arg = node.args[0] if node.args else None
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                if (
                    re.fullmatch(r"0\.\d+", arg.value)
                    and arg.value not in _ALLOWED_DECIMAL_LITERALS
                ):
                    found.append(f"{where} rate literal Decimal({arg.value!r})")
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            positional = args.posonlyargs + args.args
            defaults = [None] * (len(positional) - len(args.defaults)) + list(args.defaults)
            pairs = list(zip(positional, defaults)) + list(zip(args.kwonlyargs, args.kw_defaults))
            for param, default in pairs:
                if param.arg == "filing_status" and default is not None:
                    found.append(f"{where} filing_status has a default value")
    return found


@pytest.mark.parametrize("path", _source_files(), ids=lambda p: str(p.relative_to(_ROOT)))
def test_no_hardcoded_tax_values(path: Path):
    assert _violations(path) == []


# ---------------------------------------------------------------------------
# Frontend: pages and shared scripts must take statuses and years from the API
# ---------------------------------------------------------------------------

_STATIC_DIR = _ROOT / "api" / "static"
_SVG_NAMESPACE = "http://www.w3.org/2000/svg"  # a URL, not a year (inline favicon)


def _frontend_files() -> list[Path]:
    pages = sorted(_STATIC_DIR.glob("*.html"))
    shared = sorted((_STATIC_DIR / "js").glob("*.js"))
    return pages + shared


def _frontend_violations(path: Path) -> list[str]:
    found: list[str] = []
    for number, raw_line in enumerate(path.read_text().splitlines(), start=1):
        line = raw_line.replace(_SVG_NAMESPACE, "")
        where = f"{path.relative_to(_ROOT)}:{number}"
        for status in _FILING_STATUSES:
            if re.search(rf"""['"]{re.escape(status)}['"]""", line):
                found.append(f"{where} filing status literal {status!r}")
        if re.search(r"\b(19|20)\d\d\b", line):
            found.append(f"{where} year literal: {line.strip()[:60]}")
    return found


@pytest.mark.parametrize("path", _frontend_files(), ids=lambda p: str(p.relative_to(_ROOT)))
def test_no_hardcoded_values_in_frontend(path: Path):
    assert _frontend_violations(path) == []
