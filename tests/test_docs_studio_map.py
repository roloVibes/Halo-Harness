"""tests.test_docs_studio_map -- docs/STUDIO-map.md says what each Agents view is for in 3.6.0.2 (R47, R52, R55, R57):
3 · Map is the plan, 4 · Live is the run (the session's drawing, with the Feed in its drawer), and the Workflows tab's
head line. The words of 3.6.0.0's lit Map ("My sessions use this", the drawer "What they think and say", the amber
"another map" line) are gone from it. Plain: no browser, no process.
Run: python -m tests.test_docs_studio_map
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
DOC = Path(__file__).resolve().parent.parent / "docs" / "STUDIO-map.md"
HEAD = "Workflows are fixed lists of steps. A session runs a map, and a box on a map can run a workflow: see Map."
FEED = "Feed"  # truthWords.ts WORDS.feed: the drawer on Live


@test
def test_the_map_doc_says_map_is_the_plan_and_live_the_run(ctx: Ctx):
    text = " ".join(DOC.read_text(encoding="utf-8").split())  # a sentence may wrap across the doc's lines
    for want in ("4 · Live", "New sessions run on this", HEAD, f"**{FEED}**"):
        ctx.check(f"the doc says {want!r}", want in text)
    for gone in ("My sessions use this", "What they think and say", "A session is running on another map", "helpers main made up"):
        ctx.check(f"the doc no longer says {gone!r}", gone not in text)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
