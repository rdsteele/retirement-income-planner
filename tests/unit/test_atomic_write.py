"""Unit tests for services.common.write_text_atomic.

A crash or I/O error during a save must never leave a partial or empty file, and
must never lose the previous contents. Tests use tmp_path only.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from services.common import write_text_atomic


def test_creates_file_with_content(tmp_path: Path) -> None:
    path = tmp_path / "data.json"
    write_text_atomic(path, '{"a": 1}')
    assert path.read_text() == '{"a": 1}'


def test_overwrites_existing_file(tmp_path: Path) -> None:
    path = tmp_path / "data.json"
    path.write_text("old")
    write_text_atomic(path, "new")
    assert path.read_text() == "new"


def test_creates_missing_parent_directories(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "dir" / "data.json"
    write_text_atomic(path, "x")
    assert path.read_text() == "x"


def test_round_trips_unicode(tmp_path: Path) -> None:
    path = tmp_path / "data.json"
    write_text_atomic(path, "Café — plan ✓")
    assert path.read_text(encoding="utf-8") == "Café — plan ✓"


def test_leaves_no_temp_file_after_success(tmp_path: Path) -> None:
    write_text_atomic(tmp_path / "data.json", "x")
    assert [p.name for p in tmp_path.iterdir()] == ["data.json"]


def test_failed_replace_keeps_original_and_cleans_up(tmp_path: Path) -> None:
    path = tmp_path / "data.json"
    path.write_text("original")
    with patch("services.common.os.replace", side_effect=OSError("disk full")):
        with pytest.raises(OSError):
            write_text_atomic(path, "new")
    assert path.read_text() == "original"
    assert [p.name for p in tmp_path.iterdir()] == ["data.json"]


def test_failed_write_keeps_original_and_cleans_up(tmp_path: Path) -> None:
    path = tmp_path / "data.json"
    path.write_text("original")
    with patch("services.common.os.fsync", side_effect=OSError("io error")):
        with pytest.raises(OSError):
            write_text_atomic(path, "new")
    assert path.read_text() == "original"
    assert [p.name for p in tmp_path.iterdir()] == ["data.json"]


def test_failed_first_write_leaves_no_file(tmp_path: Path) -> None:
    path = tmp_path / "data.json"
    with patch("services.common.os.replace", side_effect=OSError("disk full")):
        with pytest.raises(OSError):
            write_text_atomic(path, "new")
    assert list(tmp_path.iterdir()) == []


def test_preserves_existing_file_permissions(tmp_path: Path) -> None:
    path = tmp_path / "data.json"
    path.write_text("old")
    path.chmod(0o644)
    write_text_atomic(path, "new")
    assert path.stat().st_mode & 0o777 == 0o644
