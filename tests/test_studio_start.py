"""tests.test_studio_start -- Halo 3.1.1.0 R1 in a real browser (headless Chrome
through the driver base, tests/helpers/studio_start.py; skipped without one).

1. a fresh home opens on Start here (no welcome card over it); 3.3.15.0 R5: it runs the Auto
   lineup, so the offer has the line in place of Run; with a custom lineup the palette's overlay
   has the guided first run's card above its button (3.2.2.0 R2); Run the guided first run runs it on the fake model calls (HALO_START_FAKE=1 in
   Studio's process): the seven steps done in the panel, the `start` frames
   on the live feed, the outcome; a reload shows no overlay (the home has a
   lineup of its own and a start now; 3.3.2.0 R1: and this browser answered
   the offer, `halo.studio.start`, so it never comes back on its own)
2. the ? menu's Glossary lists every glossary word; a section help's word link
   opens the Glossary on that word (3.6.0.0 R5: the Next footer went with Cast)
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
def test_glossary_and_a_word_link(ctx: Ctx):
    r, got = _driver("glossary")
    ctx.check(f"the driver ran, got {r.returncode} {r.stdout[-300:]!r} {r.stderr[-400:]!r}", r.returncode == 0 and "failed" not in got)
    ctx.check(f"?tour=off keeps Start here shut, got {got.get('overlay_quiet')}", got.get("overlay_quiet") == 0)
    from halo_harness.glossary import TERMS
    ctx.check(f"the ? menu's Glossary: {len(TERMS)} words, agent first (3.6.0.0), got {got.get('words')} {got.get('first')}",
              got.get("words") == len(TERMS) and got.get("first") == "agent")
    ctx.check(f"How Agents works names its words (3.6.0.0 R5: the three tabs' words), got {got.get('terms')}",
              got.get("terms") == ["step", "hand-off", "when", "live map", "report card", "waiting path", "orchestra run", "gate"])
    ctx.check(f"a word link opens the Glossary on it and closes the help, got {got.get('opened_on')}",
              got.get("opened_on") == "report card" and got.get("help_closed") is True)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
