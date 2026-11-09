"""tests.test_pack_design_ui -- the design pack's section in a real browser (Halo 3.3.13.0 R2; headless Chrome,
skipped without one). The smallest Design check first: the shipped pack enabled in the driver's scratch home, Studio
on `?mode=design--design`, the page the pack's own module draws (studio/design.js on the shell's React) -- the Start
view with no project, then the seeded project's thread and artboards, a turn sent with Enter that streams in over the
live feed (the pack's `pack_live` frames) and is cancelled, an artboard renamed -- then the R3b run (knobs, a direct
text edit, pins, the design system, 3 directions, the device select): the checks tests/test_studio_ui.py made of the
core's Design section before the pack (tests/helpers/studio_ui_design.py, studio_design.py, studio_design_rest.py).
Run: python -m tests.test_pack_design_ui
"""

from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402,F401
from tests.helpers.studio_ui_design import register  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
_RUNS: dict = {}


def _chrome() -> "str | None":
    from tests.helpers.chrome_driver import find_chrome
    return find_chrome()


def _json_of(*args: str) -> "tuple[subprocess.CompletedProcess, dict]":
    """Run the driver with a scrubbed environment (its own scratch home), once per argument list; its last line is JSON."""
    if args not in _RUNS:
        from tests.helpers.chrome_driver import driver_env
        r = subprocess.run([sys.executable, *args], capture_output=True, encoding="utf-8", errors="replace", timeout=300,
                           env=driver_env(REPO), cwd=str(REPO))
        try:
            info = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            info = {}
        _RUNS[args] = (r, info)
    return _RUNS[args]


register(test, _json_of, _chrome)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
