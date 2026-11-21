"""tests.test_doctor_browser_row -- 3.6.0.6 W batch 2 entry 4: `halo doctor` has a row `browser` that says which
browser the built-in Browser tool will use ("Halo will use {name} ({path}) for the Browser tool"), or, with none on
the machine, the one line that says what to install; it starts nothing. The finder is injected.
Run: python -m tests.test_doctor_browser_row
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("BRIDGE_TEST_HOME", tempfile.mkdtemp(prefix="doctor-browser-home-"))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


@test
def test_a_found_browser_is_named_with_its_path(ctx: Ctx):
    from halo_harness import doctor as D
    with mock.patch("halo_harness.browser_find.find_browser", lambda **k: ("Microsoft Edge", "/opt/edge/msedge")):
        row = D._check_browser()
    ctx.check(f"OK and the line, got {row!r}",
              row == f"{D.OK} Halo will use Microsoft Edge (/opt/edge/msedge) for the Browser tool")


@test
def test_no_browser_is_the_one_line(ctx: Ctx):
    from halo_harness import doctor as D
    with mock.patch("halo_harness.browser_find.find_browser", lambda **k: None):
        row = D._check_browser()
    ctx.check(f"a warning that says what to install, got {row!r}", row == (
        f"{D.WARN} No browser found: install Google Chrome, Chromium, Microsoft Edge or Brave, or set HALO_CHROME to a "
        f"browser's path. Halo downloads none."))


@test
def test_the_row_is_in_the_report_before_the_chrome_row(ctx: Ctx):
    src = (ROOT / "halo_harness" / "doctor.py").read_text(encoding="utf-8")
    i, j = src.find('entries.append(("browser", _row("browser", _check_browser)))'), src.find('entries.append(("chrome",')
    ctx.check("the browser row is listed, right before chrome", 0 < i < j)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
