"""tests.test_studio_edit_route -- `halo studio --edit` in a real browser (Halo
3.1.1.0 R3: Studio is the one editor of bios and lineups; headless Chrome
through the driver base, tests/helpers/studio_edit.py; skipped without one).

1. the URL: a page opened on `?mode=roles&edit=bio:coder` lands on Roles with
   coder's bio form open (no Start here, no welcome over it); the form has
   every field the terminal's bio view shows, each with field_help.py's line
   (GET /api/field-help), the efforts up to xhigh and max, and the YAML
   toggle; fields typed into the form and saved land in the bio's file
   (tags, context files, acceptance, the schedule, environment.offline);
2. the focus of a running Studio: with a page open, what `halo studio
   --edit` runs (studio/edit_open.open_edit) focuses it -- lineup:<name>
   opens that lineup with the Inspector on its Lineup tab (a section's line
   from field_help.py; a section edited there and saved lands in the file),
   team opens the Team section, bio:<name> the bio form -- and opens no new
   browser tab.
The no-browser half (the targets, the URL, the focus API, the CLI verbs) is
tests/test_studio_edit_target.py.
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
def test_the_edit_url_opens_the_bio_form_on_that_bio(ctx: Ctx):
    r, got = _driver("bio")
    ctx.check(f"the driver ran, got {r.returncode} {r.stdout[-300:]!r} {r.stderr[-400:]!r}", r.returncode == 0 and "failed" not in got)
    ctx.check(f"Roles, coder's bio form, nothing over it, got {got.get('section')} {got.get('form')} {got.get('overlays')}",
              got.get("form") == "coder" and str(got.get("section") or "").startswith("Roles") and got.get("overlays") == 0)
    ctx.check(f"every field the terminal view shows is in the form; missing: {got.get('missing')}", got.get("missing") == [])
    ctx.check(f"the help lines are field_help.py's, got {got.get('help_from_source')}", got.get("help_from_source") == [True] * 6)
    ctx.check(f"effort offers xhigh and max, got {got.get('efforts')}", got.get("efforts") == ["", "low", "medium", "high", "xhigh", "max"])
    ctx.check("the YAML toggle shows the draft as the file would hold it", "every: 30m" in str(got.get("yaml") or "")
              and "- alpha" in str(got.get("yaml") or ""))
    ctx.check(f"the typed fields saved through the form, got {got.get('saved')} {got.get('problems')!r}", got.get("saved") == {
        "tags": ["alpha", "beta"], "files": ["CLAUDE.md", "plans/STATUS.md"], "accept": "say ok",
        "schedule": {"every": "30m", "prompt": "check the inbox"}, "offline": True})


@test
def test_a_running_studio_is_focused_on_the_target(ctx: Ctx):
    from halo_harness import field_help
    r, got = _driver("focus")
    ctx.check(f"the driver ran, got {r.returncode} {r.stdout[-300:]!r} {r.stderr[-400:]!r}", r.returncode == 0 and "failed" not in got)
    ctx.check(f"one page listening, focused, got {got.get('listeners')} {got.get('lineup_how')} {got.get('lineup_pages')}",
              got.get("listeners") == 1 and got.get("lineup_how") == "focused" and got.get("lineup_pages") == 1)
    ctx.check(f"lineup:<name> opens its Lineup tab, got {got.get('lineup_tab')} {got.get('lineup_selected')}",
              got.get("lineup_tab") == "halo-dev-cycle" and got.get("lineup_selected") == "true")
    ctx.check(f"the section's line is field_help.py's, got {got.get('about')!r}", got.get("about") == field_help.LINEUP_SECTIONS["delegation"])
    ctx.check(f"a section edited in the inspector is saved, got {got.get('delegation_saved')}", got.get("delegation_saved") == "round-robin")
    ctx.check(f"team opens the Team section, got {got.get('team_how')} {got.get('team_section')}",
              got.get("team_how") == "focused" and str(got.get("team_section") or "").startswith("Team"))
    ctx.check(f"bio:<name> opens the bio form back on Roles, got {got.get('bio_form')} {got.get('bio_section')}",
              got.get("bio_how") == "focused" and got.get("bio_form") == "reviewer" and str(got.get("bio_section") or "").startswith("Roles"))
    ctx.check(f"no browser tab was opened, got {got.get('tabs_opened')}", got.get("tabs_opened") == 0)
    ctx.check(f"the URL it reports names the target, got {got.get('url')}", str(got.get("url") or "").endswith("/?mode=roles&edit=bio:reviewer"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
