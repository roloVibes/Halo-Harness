"""tests.test_browser_find -- the browser finder realcheck and the suite's Chrome driver use (halo_harness/browser_find.py;
3.6.0.3 moved it out of the replay clip's live/clip_chrome.py with no change of behaviour): HALO_CHROME first (that one
alone), then the install paths, then PATH; the one line said when none is found. Run: python -m tests.test_browser_find
"""
from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
MOVED = ("CANDIDATES", "NAMES", "named_browser", "find_chrome", "none_found")


@test
def test_a_halo_chrome_that_names_nothing_never_films_in_the_installed_chrome(ctx: Ctx):
    """3.6.0.1: `halo replay clip` / Studio's Export a clip with a HALO_CHROME that names no browser fell through to
    the person's own installed Chrome. Now it finds none, and the error names the variable and its value."""
    import tempfile
    from unittest import mock
    from halo_harness import browser_find as cc
    tmp = Path(tempfile.mkdtemp(prefix="clip-find-"))
    installed = tmp / "installed-chrome"
    installed.write_text("", encoding="utf-8")
    missing = str(tmp / "no-such-chrome")
    with mock.patch.object(cc, "CANDIDATES", (str(installed),)), \
            mock.patch("shutil.which", lambda name, *a, **k: str(installed)):
        with mock.patch.dict(os.environ, {"HALO_CHROME": missing}):
            ctx.check(f"never the installed Chrome, got {cc.find_chrome()!r}", cc.find_chrome() is None)
            why = getattr(cc, "none_found", lambda: "")()
            ctx.check(f"the error names HALO_CHROME and its value, got {why!r}", "HALO_CHROME" in why and missing in why)
        with mock.patch.dict(os.environ, {"HALO_CHROME": ""}):
            ctx.check("an unset HALO_CHROME still finds the installed Chrome", cc.find_chrome() == str(installed))
    with mock.patch.dict(os.environ, {"HALO_CHROME": "my-chromium"}), \
            mock.patch("shutil.which", lambda name, *a, **k: "/opt/bin/my-chromium" if name == "my-chromium" else None):
        ctx.check("a bare command name resolves through PATH", cc.find_chrome() == "/opt/bin/my-chromium")


def _imports(path: Path) -> list:
    out = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.module:
            out += [(node.module, a.name) for a in node.names]
        elif isinstance(node, ast.Import):
            out += [(a.name, "") for a in node.names]
    return out


@test
def test_the_finder_moved_whole_and_its_users_import_it_from_its_own_module(ctx: Ctx):
    """3.6.0.3 (R-B6): the five names live in halo_harness.browser_find (file 06 deleted the clip's module that
    re-exported them); realcheck and the suite's Chrome driver import from there; the finder opens no socket and
    starts no process, so tests.test_offline_mode needs no entry for it."""
    from halo_harness import browser_find
    for name in MOVED:
        ctx.check(f"browser_find.{name} is there", hasattr(browser_find, name))
    for rel in ("scripts/realcheck.py", "scripts/realcheck/core.py", "tests/helpers/chrome_driver.py"):
        got = _imports(ROOT / rel)
        ctx.check(f"{rel} imports named_browser from halo_harness.browser_find",
                  ("halo_harness.browser_find", "named_browser") in got
                  and not any(m.startswith("halo_harness.live.") for m, _n in got))
    mods = {m.split(".")[0] for m, _n in _imports(ROOT / "halo_harness" / "browser_find.py")}
    ctx.check(f"no network and no process in the finder, got {sorted(mods)}",
              not mods & {"socket", "urllib", "subprocess", "http"} and not any(
                  "subprocess" in m for m, _n in _imports(ROOT / "halo_harness" / "browser_find.py")))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
