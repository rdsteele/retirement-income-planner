"""Shared helpers for the services layer."""

import os
import shutil
import tempfile
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

_DOLLAR = Decimal("1")
_FOUR_PLACES = Decimal("0.0001")


def round_tax(amount: Decimal) -> Decimal:
    """Round a tax amount to the nearest whole dollar using ROUND_HALF_UP."""
    return amount.quantize(_DOLLAR, rounding=ROUND_HALF_UP)


def round_rate(amount: Decimal) -> Decimal:
    """Round a rate to 4 decimal places using ROUND_HALF_UP."""
    return amount.quantize(_FOUR_PLACES, rounding=ROUND_HALF_UP)


def write_text_atomic(path: Path, text: str) -> None:
    """Write text to path so a crash or I/O error never loses the previous contents.

    The text goes to a temporary file in the same directory, is flushed to disk,
    and then replaces the target in a single step. On any failure the temporary
    file is removed and the original file is left untouched. An existing file keeps
    its permissions; a new file is created owner-only.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    tmp_path = Path(tmp_name)
    try:
        if path.exists():
            shutil.copymode(path, tmp_path)
        with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
            tmp_file.write(text)
            tmp_file.flush()
            os.fsync(tmp_file.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise
