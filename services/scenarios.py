"""Scenario persistence service.

Stores named scenario files under profile/scenarios/ and tracks the
currently-loaded scenario in profile/current_scenario.json.
"""

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

_SCENARIOS_DIR = Path(__file__).parent.parent / "profile" / "scenarios"
_CURRENT_FILE = Path(__file__).parent.parent / "profile" / "current_scenario.json"


@dataclass
class ScenarioMeta:
    name: str
    saved_at: datetime
    filename: str


def scenario_name_to_filename(name: str) -> str:
    """Convert a scenario name to a safe filename.

    Spaces become underscores; characters outside [a-zA-Z0-9_.-] are removed.
    Example: "2026 Base Plan" → "2026_Base_Plan.json"
    """
    slug = name.strip().replace(" ", "_")
    slug = re.sub(r"[^\w\-.]", "", slug)
    return slug + ".json"


def list_scenarios(
    _scenarios_dir: Path = _SCENARIOS_DIR,
) -> list[ScenarioMeta]:
    """Return metadata for all saved scenarios, sorted by saved_at descending."""
    if not _scenarios_dir.exists():
        return []
    results: list[ScenarioMeta] = []
    for path in _scenarios_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text())
            saved_at = datetime.fromisoformat(data["saved_at"])
            results.append(
                ScenarioMeta(
                    name=data["name"],
                    saved_at=saved_at,
                    filename=path.name,
                )
            )
        except Exception:
            continue
    results.sort(key=lambda m: m.saved_at, reverse=True)
    return results


def load_scenario(
    name: str,
    _scenarios_dir: Path = _SCENARIOS_DIR,
) -> dict:
    """Load and return scenario JSON dict. Raises ValueError if not found."""
    filename = scenario_name_to_filename(name)
    path = _scenarios_dir / filename
    if not path.exists():
        raise ValueError(f"Scenario not found: {name!r}")
    return json.loads(path.read_text())


def save_scenario(
    name: str,
    data: dict,
    _scenarios_dir: Path = _SCENARIOS_DIR,
) -> None:
    """Save scenario data, creating the directory if needed. Overwrites if exists."""
    _scenarios_dir.mkdir(parents=True, exist_ok=True)
    filename = scenario_name_to_filename(name)
    path = _scenarios_dir / filename
    path.write_text(json.dumps(data, indent=2))


def delete_scenario(
    name: str,
    _scenarios_dir: Path = _SCENARIOS_DIR,
) -> None:
    """Delete scenario file. Raises ValueError if not found."""
    filename = scenario_name_to_filename(name)
    path = _scenarios_dir / filename
    if not path.exists():
        raise ValueError(f"Scenario not found: {name!r}")
    path.unlink()


def get_current_scenario(
    _current_file: Path = _CURRENT_FILE,
) -> str | None:
    """Return the name of the currently-loaded scenario, or None."""
    if not _current_file.exists():
        return None
    try:
        data = json.loads(_current_file.read_text())
        return data.get("name") or None
    except Exception:
        return None


def set_current_scenario(
    name: str | None,
    _current_file: Path = _CURRENT_FILE,
) -> None:
    """Set (or clear) the current scenario name."""
    _current_file.parent.mkdir(parents=True, exist_ok=True)
    _current_file.write_text(json.dumps({"name": name}))
