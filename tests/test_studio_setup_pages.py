"""tests.test_studio_setup_pages -- Setup one page at a time (Halo 3.3.1.0 R1,
the owner on 3.3.0.0: "I hate the pop up ... Have it go thru pages"). Headless
Chrome through tests/helpers/studio_setup_pages.py (skipped without one), over a
fresh scratch home with no provider; no provider request, no model call:

1. nothing opens on its own: `?mode=setup` and `?mode=setup&first=1` show no
   help, no Start here, no dialog after 2 s; `first=1` only leads the rail's
   line with "set up this box"; Roles still gets the offer; the help is one
   click away;
2. no panels, no panel list, no Arrange on Setup;
3. the rail: the wizard's order, each step current / done / todo;
4. Next walks Providers to the Summary (the last Next says Summary), Back
   walks back (off on Providers); a rail jump; Ctrl+Right is Next;
5. Enter in a block's choice is its Save;
6. `?block=team` opens Team; the Summary's rows, a Change jump and its button
   to the Check page;
7. the page is remembered for the home, and `?block=` wins;
8. the Ollama finders are a disclosure, closed until opened.
Run: python -m tests.test_studio_setup_pages
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
_RUN: dict = {}
ORDER = ["providers", "local", "model", "permissions", "theme", "team", "check", "summary"]


def _got(ctx: Ctx) -> dict:
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (the Setup pages checks need headless Chrome)")
    if "r" not in _RUN:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_setup_pages"], capture_output=True, encoding="utf-8",
                           errors="replace", timeout=300, env=driver_env(REPO), cwd=str(REPO), stdin=subprocess.DEVNULL)
        try:
            info = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            info = {}
        _RUN["r"] = (r, info)
    r, info = _RUN["r"]
    if info.get("skip"):
        raise SkipTest(info["skip"])
    ctx.check(f"the driver ran, got {r.returncode} {info.get('failed')!r} {r.stderr[-600:]!r}", r.returncode == 0 and "failed" not in info)
    return info


def _steps(rows) -> list:
    """The rail's steps without Linux fixes (a step only on a box that needs them: some Linux runners do)."""
    return [r for r in (rows or []) if r[0] != "linux"]


@test
def test_nothing_opens_on_its_own(ctx: Ctx):
    got = _got(ctx)
    for name in ("plain", "first"):
        ctx.check(f"?{name}: no help, no Start here, no dialog after 2 s, got {got.get('open_' + name)}", got.get(f"open_{name}") == [False, False, 0])
        ctx.check(f"?{name}: the first page is Providers, got {got.get('page_' + name)!r}", got.get(f"page_{name}") == "providers")
    ctx.check(f"first=1 leads the rail's line with set up this box, got {got.get('first_line')!r}", str(got.get("first_line")).startswith("set up this box"))
    ctx.check(f"the help is one click away in the header, got {got.get('help_title')!r}", got.get("help_title") == "How Setup works")
    ctx.check("the other sections of a fresh home still get Start here", got.get("roles_overlay") is True)


@test
def test_no_panel_machinery_on_setup(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"no panel in Setup, got {got.get('setup_panels')}", got.get("setup_panels") == 0)
    ctx.check(f"no panel list and no Arrange in the rail, got {got.get('rail_lists')}", got.get("rail_lists") == [False, False])


@test
def test_the_rail_and_its_states(ctx: Ctx):
    got = _got(ctx)
    want = [["providers", "current"], ["local", "done"], ["model", "todo"], ["permissions", "todo"], ["theme", "todo"],
            ["team", "done"], ["check", "todo"], ["summary", "todo"]]
    ctx.check(f"the wizard's order and the states of a fresh home, got {got.get('rail')}", _steps(got.get("rail")) == want)
    titles = [t for t in got.get("rail_titles") or [] if t != "Linux fixes"]
    ctx.check(f"the wizard's words, got {titles}", titles == ["Providers", "Local models", "Default model", "Permissions", "Theme", "Team",
                                                             "Check", "Summary"])


@test
def test_next_and_back_walk_the_pages(ctx: Ctx):
    got = _got(ctx)
    walk = [s for s in got.get("walk") or [] if s != "linux"]
    ctx.check(f"Next from Providers to the Summary, got {got.get('walk')}", walk == ORDER)
    labels = got.get("next_labels") or []
    ctx.check(f"Next, and Summary on the page before it, got {labels}", labels and labels[-1] == "Summary" and set(labels[:-1]) == {"Next"})
    ctx.check("no Next on the Summary", got.get("summary_next") is False)
    back = [s for s in got.get("back_walk") or [] if s != "linux"]
    ctx.check(f"Back to Providers, got {got.get('back_walk')}", back == ORDER[::-1])
    ctx.check("Back is off on the first page", got.get("back_off_first") is True)
    ctx.check(f"a rail jump opens Theme, got {got.get('jump')}", got.get("jump") == ["theme", "current"])
    ctx.check(f"Ctrl+Right is Next, got {got.get('ctrl_right')!r}", got.get("ctrl_right") == "team")


@test
def test_enter_is_the_blocks_save(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"Enter on the picked mode saved it, got {got.get('enter_word')!r} {got.get('enter_config')!r}",
              got.get("enter_word") == "saved" and got.get("enter_config") == "plan")
    ctx.check(f"the rail ticks Permissions, got {got.get('permissions_after')!r}", got.get("permissions_after") == "done")


@test
def test_block_door_and_the_summary(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"?block=team opens Team, the word leaves the address, got {got.get('block_page')!r} {got.get('block_search')!r}",
              got.get("block_page") == "team" and "block=" not in str(got.get("block_search")))
    rows = _steps(got.get("summary_rows"))
    ctx.check(f"one row per step, in order, got {rows}", [r[0] for r in rows] == ORDER[:-1])
    vals = {r[0]: r for r in rows}
    ctx.check(f"the rows say what is set, got {vals}", vals.get("providers", [None, "", ""])[1:] == ["todo", "no provider set"]
              and vals.get("permissions", [None, "", ""])[1:] == ["done", "plan"] and vals.get("model", [None, "", ""])[2] == "not set"
              and vals.get("check", [None, "", ""])[2] == "not run")
    ctx.check(f"Run the ticked checks with the ticks named, got {got.get('summary_run')!r} {got.get('summary_ticked')!r}",
              got.get("summary_run") == "Run the ticked checks" and "doctor, catalog, hello" in str(got.get("summary_ticked")))
    ctx.check("the last check and the guided first run's button", got.get("summary_last") == "not run" and got.get("summary_start") is True)
    ctx.check(f"Change jumps to the step's page, got {got.get('change_page')!r}", got.get("change_page") == "model")
    ctx.check(f"the Summary's button opens the Check page, got {got.get('to_check_page')!r}", got.get("to_check_page") == "check")


@test
def test_the_page_is_remembered(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"a reload opens the page last open, got {got.get('remembered')!r}", got.get("remembered") == "permissions")
    ctx.check(f"?block= wins, then is remembered, got {got.get('block_wins')!r} {got.get('door_remembered')!r}",
              got.get("block_wins") == "check" and got.get("door_remembered") == "check")


@test
def test_the_ollama_finders_are_a_closed_disclosure(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"closed by default, Find not drawn, got {got.get('more_closed')} {got.get('find_hidden')}",
              got.get("more_closed") is True and got.get("find_hidden") is True)
    ctx.check(f"a click opens it, got {got.get('more_open')} {got.get('find_shown')}", got.get("more_open") is True and got.get("find_shown") is True)


@test
def test_the_source_keeps_the_shape(ctx: Ctx):
    """No Chrome needed: the files the round names, each under the cap, and Setup is paged in the registry."""
    ui = REPO / "halo_harness" / "studio" / "ui" / "src"
    for name in ("SetupRail.tsx", "SetupPage.tsx", "Summary.tsx", "pages.ts"):
        p = ui / "routes" / "setup" / name
        ctx.check(f"{name} exists and is under 250 lines", p.is_file() and len(p.read_text(encoding="utf-8").splitlines()) < 250)
    routes = (ui / "routes" / "index.tsx").read_text(encoding="utf-8")
    ctx.check("Setup's entry is paged with no panels", 'id: "setup"' in routes and "panels: [], paged: true, view: SetupView" in routes)
    door = (ui / "routes" / "setup" / "door.ts").read_text(encoding="utf-8")
    ctx.check("the door opens no help", "openHelp" not in door)
    store = (ui / "lib" / "store.ts").read_text(encoding="utf-8")
    ctx.check("no welcome for Setup", 'section === "setup"' in store and 'first === "setup"' in store)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
