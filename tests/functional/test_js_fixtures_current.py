"""The JavaScript page-boot tests run against saved real API responses.

This test fails when the live API output no longer matches those files, so the
JavaScript tests cannot silently drift from the real response shapes.
Regenerate the fixtures with: python3 tests/js/fixtures.py
"""

import importlib.util
import json
from pathlib import Path

_JS_DIR = Path(__file__).resolve().parent.parent / "js"


def _load_fixture_builder():
    spec = importlib.util.spec_from_file_location("js_fixtures", _JS_DIR / "fixtures.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_saved_fixtures_match_live_api_responses():
    builder = _load_fixture_builder()
    stale = []
    for name, live in builder.build_fixtures().items():
        saved = json.loads((builder.FIXTURE_DIR / f"{name}.json").read_text())
        if saved != live:
            stale.append(name)
    assert stale == [], f"stale fixtures {stale}; run: python3 tests/js/fixtures.py"


def test_every_saved_fixture_is_still_generated():
    builder = _load_fixture_builder()
    saved = {p.stem for p in builder.FIXTURE_DIR.glob("*.json")}
    assert saved == set(builder.build_fixtures())
