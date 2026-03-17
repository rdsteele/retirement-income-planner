"""Unit tests for services/scenarios.py.

Tests use tmp_path to avoid touching profile/scenarios/ or
profile/current_scenario.json.
"""

from pathlib import Path

import pytest

from services.scenarios import (
    delete_scenario,
    get_current_scenario,
    list_scenarios,
    load_scenario,
    save_scenario,
    scenario_name_to_filename,
    set_current_scenario,
)


# ---------------------------------------------------------------------------
# 1. list_scenarios returns empty list when directory missing
# ---------------------------------------------------------------------------

def test_list_scenarios_empty_when_dir_missing(tmp_path: Path) -> None:
    missing_dir = tmp_path / "nonexistent"
    result = list_scenarios(_scenarios_dir=missing_dir)
    assert result == []


# ---------------------------------------------------------------------------
# 2. save_scenario creates file, load_scenario returns same data
# ---------------------------------------------------------------------------

def test_save_then_load_roundtrip(tmp_path: Path) -> None:
    scenarios_dir = tmp_path / "scenarios"
    data = {
        "name": "2026 Base Plan",
        "saved_at": "2026-03-16T19:00:00",
        "version": "1.0",
        "inputs": {"pension": 1596},
    }
    save_scenario("2026 Base Plan", data, _scenarios_dir=scenarios_dir)
    loaded = load_scenario("2026 Base Plan", _scenarios_dir=scenarios_dir)
    assert loaded == data


# ---------------------------------------------------------------------------
# 3. delete_scenario removes file
# ---------------------------------------------------------------------------

def test_delete_removes_file(tmp_path: Path) -> None:
    scenarios_dir = tmp_path / "scenarios"
    data = {"name": "Test", "saved_at": "2026-01-01T00:00:00", "version": "1.0"}
    save_scenario("Test", data, _scenarios_dir=scenarios_dir)

    filename = scenario_name_to_filename("Test")
    assert (scenarios_dir / filename).exists()

    delete_scenario("Test", _scenarios_dir=scenarios_dir)
    assert not (scenarios_dir / filename).exists()


# ---------------------------------------------------------------------------
# 4. delete_scenario raises ValueError for missing scenario
# ---------------------------------------------------------------------------

def test_delete_raises_for_missing(tmp_path: Path) -> None:
    scenarios_dir = tmp_path / "scenarios"
    with pytest.raises(ValueError, match="not found"):
        delete_scenario("Nonexistent", _scenarios_dir=scenarios_dir)


# ---------------------------------------------------------------------------
# 5. scenario_name_to_filename handles spaces and special characters
# ---------------------------------------------------------------------------

def test_scenario_name_to_filename_spaces() -> None:
    assert scenario_name_to_filename("2026 Base Plan") == "2026_Base_Plan.json"


def test_scenario_name_to_filename_special_chars() -> None:
    result = scenario_name_to_filename("My Plan!@#")
    assert result == "My_Plan.json"


# ---------------------------------------------------------------------------
# 6. get_current_scenario returns None when file missing
# ---------------------------------------------------------------------------

def test_get_current_returns_none_when_missing(tmp_path: Path) -> None:
    current_file = tmp_path / "current_scenario.json"
    result = get_current_scenario(_current_file=current_file)
    assert result is None


# ---------------------------------------------------------------------------
# 7. set_current_scenario persists, get_current_scenario returns it
# ---------------------------------------------------------------------------

def test_set_then_get_current(tmp_path: Path) -> None:
    current_file = tmp_path / "current_scenario.json"
    set_current_scenario("2026 Base Plan", _current_file=current_file)
    result = get_current_scenario(_current_file=current_file)
    assert result == "2026 Base Plan"


# ---------------------------------------------------------------------------
# 8. set_current_scenario(None) clears current scenario
# ---------------------------------------------------------------------------

def test_set_current_none_clears(tmp_path: Path) -> None:
    current_file = tmp_path / "current_scenario.json"
    set_current_scenario("Some Scenario", _current_file=current_file)
    set_current_scenario(None, _current_file=current_file)
    result = get_current_scenario(_current_file=current_file)
    assert result is None
