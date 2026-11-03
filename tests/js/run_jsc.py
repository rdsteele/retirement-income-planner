"""Run the JavaScript tests on macOS without Node, using the built-in JavaScript engine.

Usage: python3 tests/js/run_jsc.py

CI runs the same tests under Node (tests/js/run-node.js). This runner exists so the
tests can also be run on a Mac that has no Node installed. It concatenates the same
files in the same order and evaluates them with `osascript -l JavaScript`.
"""

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SHARED_DIR = ROOT / "api" / "static" / "js"
TESTS_DIR = ROOT / "tests" / "js"
TIMEOUT_SECONDS = 60

_RUNNER = """
ObjC.import('Foundation');
function __finish(results, error) {
  var lines = [], failed = 0;
  (results || []).forEach(function (r) {
    if (r.ok) { lines.push('PASS ' + r.name); }
    else { failed++; lines.push('FAIL ' + r.name + '\\n     ' + r.error); }
  });
  if (error) { failed++; lines.push('FAIL harness error: ' + error); }
  lines.push('\\n' + ((results || []).length - failed) + ' passed, ' + failed + ' failed');
  lines.push('EXIT ' + (failed === 0 ? 0 : 1));
  $.NSString.stringWithString(lines.join('\\n')).writeToFileAtomicallyEncodingError(
    '__RESULT_PATH__', true, $.NSUTF8StringEncoding, null);
}
__runAll().then(function (r) { __finish(r, null); }, function (e) { __finish([], e); });
'started';
"""


def _parse_page(html: str) -> dict:
    """Return the shared scripts a page loads (in order) and its inline script text."""
    scripts = [
        (SHARED_DIR / name).read_text()
        for name in re.findall(r'<script src="/static/js/([^"]+)"></script>', html)
    ]
    inline = "\n".join(re.findall(r"<script(?![^>]*\bsrc\b)[^>]*>([\s\S]*?)</script>", html))
    return {"scripts": scripts, "inline": inline}


def _page_and_fixture_globals() -> str:
    pages = {
        path.stem: _parse_page(path.read_text())
        for path in (ROOT / "api" / "static").glob("*.html")
    }
    fixtures = {
        path.stem: json.loads(path.read_text()) for path in (TESTS_DIR / "fixtures").glob("*.json")
    }
    return f"const __PAGES = {json.dumps(pages)};\nconst __FIXTURES = {json.dumps(fixtures)};\n"


def _script_files() -> list[Path]:
    shared = sorted(SHARED_DIR.glob("*.js"))
    tests = sorted(TESTS_DIR.glob("*.test.js"))
    return [*shared, TESTS_DIR / "harness.js", *tests]


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        result_path = Path(tmp) / "results.txt"
        script = _page_and_fixture_globals()
        script += "\n".join(f.read_text() for f in _script_files())
        script += _RUNNER.replace("__RESULT_PATH__", str(result_path))
        script_path = Path(tmp) / "run.js"
        script_path.write_text(script)
        proc = subprocess.run(
            ["osascript", "-l", "JavaScript", str(script_path)],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )
        if not result_path.exists():
            print("No results produced.\n", proc.stdout, proc.stderr)
            return 1
        report = result_path.read_text()
    print(report.rsplit("\nEXIT", 1)[0])
    return int(report.rsplit("EXIT ", 1)[1].strip())


if __name__ == "__main__":
    sys.exit(main())
