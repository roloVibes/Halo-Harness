"""tests.test_studio_start -- Halo 3.1.1.0 R1 in a real browser (headless Chrome
through the driver base, tests/helpers/studio_start.py; skipped without one).

1. a fresh home opens on Start here (no welcome card over it) with the guided
   first run's card above its button (3.2.2.0 R2); Run the guided first run runs it on the fake model calls (HALO_START_FAKE=1 in
   Studio's process): the seven steps done in the panel, the `start` frames
   on the live feed, the outcome; a reload shows no overlay (the home has a
   lineup of its own and a start now)
2. the ? menu's Glossary lists every glossary word; a section help's word link
   opens the Glossary on that word; the Start view's Next footer goes to
   the next section of the story (Roles -> Orchestra)
Run: python -m tests.test_studio_start
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent


def _driver(*argv: str) -> "tuple[subprocess.CompletedProcess, dict]":
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (the Start here scenario needs headless Chrome)")
    r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_start", *argv], capture_output=True, encoding="utf-8",
                       errors="replace", timeout=300, env=driver_env(REPO), cwd=str(REPO))
    try:
        info = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        info = {}
    if info.get("skip"):
        raise SkipTest(info["skip"])
    return r, info


@test
def test_the_guided_first_run_runs_from_start_here(ctx: Ctx):
    r, got = _driver("run")
    ctx.check(f"the driver ran, got {r.returncode} {r.stdout[-300:]!r} {r.stderr[-400:]!r}", r.returncode == 0 and "failed" not in got)
    ctx.check(f"the overlay offers the start, no welcome card over it, got {got}", got.get("offer") == 1 and got.get("welcome_with_offer") == 0)
    card = str(got.get("card") or "")
    ctx.check(f"the button and the card above it, got {got.get('button')!r} {card[:120]!r}", got.get("button") == "Run the guided first run"
              and card.startswith("The guided first run") and "Estimated cost: free" in card and "Writes:" in card)
    keys = ["lineup", "repo", "goal", "plan", "run", "report", "next"]
    ctx.check(f"the seven steps done, in order, got {got.get('steps')}", got.get("steps") == [f"{k}:done" for k in keys])
    ctx.check(f"the outcome names the lineup, got {got.get('done_text')!r}", got.get("done_ok") == "true"
              and "my-halo-dev-cycle" in (got.get("done_text") or ""))
    ctx.check(f"`start` frames for every step and the summary, one session, got {got.get('frame_keys')} {got.get('frame_session')}",
              got.get("frame_keys") == sorted(keys + ["summary"]) and got.get("frame_session") == ["start:"] and got.get("frames", 0) >= 15)
    ctx.check(f"a reload: no overlay, the Roles Start view gone (a lineup of your own), got {got}",
              got.get("overlay_after_reload") == 0 and got.get("roles_start_after") == 0)


@test
def test_glossary_word_links_and_the_next_footer(ctx: Ctx):
    r, got = _driver("glossary")
    ctx.check(f"the driver ran, got {r.returncode} {r.stdout[-300:]!r} {r.stderr[-400:]!r}", r.returncode == 0 and "failed" not in got)
    ctx.check(f"?tour=off keeps Start here shut, got {got.get('overlay_quiet')}", got.get("overlay_quiet") == 0)
    from halo_harness.glossary import TERMS
    ctx.check(f"the ? menu's Glossary: {len(TERMS)} words, lineup first, got {got.get('words')} {got.get('first')}",
              got.get("words") == len(TERMS) and got.get("first") == "lineup")
    ctx.check(f"How Roles works names its words, got {got.get('terms')}", got.get("terms") == ["lineup", "bio", "role", "tier"])
    ctx.check(f"a word link opens the Glossary on it and closes the help, got {got.get('opened_on')}",
              got.get("opened_on") == "tier" and got.get("help_closed") is True)
    ctx.check(f"Roles' Next footer goes to Orchestra, got {got.get('next')} {got.get('went_to')}",
              got.get("next") == "orchestra" and str(got.get("went_to") or "").startswith("Orchestra"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
