"""tests.test_studio_edit_route -- `halo studio --edit` in a real browser (Halo 3.1.1.0 R3; 3.6.0.0 R5: Studio is the
one editor of agents, workflows and maps; headless Chrome through the driver base, tests/helpers/studio_edit.py;
skipped without one).

1. the URL: a page opened on `?edit=agent:coder` lands on Agents -> 1 · Agents with coder's form open, nothing over it;
2. the focus of a running Studio: with a page open, what `halo studio --edit` runs (studio/edit_open.open_edit) focuses
   it -- map:<name> opens the Map on that map, workflow:<name> the Workflows tab on it, an old bio:<name> 1 · Agents
   with the old files' line -- and opens no new browser tab.
The no-browser half (the targets, the URL, the focus API, the CLI verbs) is tests/test_studio_edit_target.py.
Run: python -m tests.test_studio_edit_route
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent


def _driver(*argv: str) -> "tuple[subprocess.CompletedProcess, dict]":
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (the edit route needs headless Chrome)")
    r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_edit", *argv], capture_output=True, encoding="utf-8",
                       errors="replace", timeout=300, env=driver_env(REPO), cwd=str(REPO))
    try:
        info = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        info = {}
    if info.get("skip"):
        raise SkipTest(info["skip"])
    return r, info


@test
def test_the_edit_url_opens_the_agent_form(ctx: Ctx):
    r, got = _driver("url")
    ctx.check(f"the driver ran, got {r.returncode} {r.stdout[-300:]!r} {r.stderr[-400:]!r}", r.returncode == 0 and "failed" not in got)
    ctx.check(f"Agents (1 · Agents), coder's form, nothing over it, got {got.get('section')} {got.get('form')} {got.get('overlays')}",
              str(got.get("section") or "").startswith("Agents") and got.get("form") == "coder" and got.get("overlays") == 0)


@test
def test_a_running_studio_is_focused_on_the_target(ctx: Ctx):
    r, got = _driver("focus")
    ctx.check(f"the driver ran, got {r.returncode} {r.stdout[-300:]!r} {r.stderr[-400:]!r}", r.returncode == 0 and "failed" not in got)
    ctx.check(f"one page listening, focused, got {got.get('listeners')} {got.get('map_how')} {got.get('map_pages')}",
              got.get("listeners") == 1 and got.get("map_how") == "focused" and got.get("map_pages") == 1)
    ctx.check(f"map:<name> opens the Map on it, got {got.get('map')!r}", got.get("map") == "ship-it")
    ctx.check(f"workflow:<name> opens the Workflows tab on it, got {got.get('flow')!r}", got.get("flow") == "code")
    ctx.check(f"an old bio:<name> opens 1 · Agents with the old files' line, got {got.get('old_how')} {got.get('old_view')} {got.get('old_line')!r}",
              got.get("old_how") == "focused" and got.get("old_view") == "crew" and "no longer read" in str(got.get("old_line")))
    ctx.check(f"no browser tab was opened, got {got.get('tabs_opened')}", got.get("tabs_opened") == 0)
    ctx.check(f"the URL it reports names the target, got {got.get('url')}", str(got.get("url") or "").endswith("/?mode=agents&view=crew&edit=bio:reviewer"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
