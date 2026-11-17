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



AGENTS_DOC = DOC.parent / "STUDIO-agents.md"
SWITCH = DOC.parent.parent / "halo_harness" / "studio" / "ui" / "src" / "routes" / "agents" / "ViewSwitch.tsx"
REPLAY_OPEN = DOC.parent.parent / "halo_harness" / "replay_verbs.py"


@test
def test_agents_docs_say_the_four_tabs_and_where_each_door_lands(ctx: Ctx):
    """R52 R55 R56 (P4 batch 10): the docs say what the registry (ViewSwitch.tsx VIEWS) and lib/agentsDoor.ts do now --
    four tabs, Alt+2 on Live while a session he has talked to is open, a page load reading the sessions first,
    `view=live` on Live, a replay (`halo replay open`: `view=map&replay=`) on the Map. No doc says the old rule."""
    import re
    flat = lambda p: " ".join(p.read_text(encoding="utf-8").split())  # noqa: E731
    tabs = re.findall(r'\["(\w+)", (?:`)?"?(\d) · ', SWITCH.read_text(encoding="utf-8"))
    words = [w for w in re.findall(r'"\d · ([A-Za-z]+)"|`4 · \$\{WORDS\.(live)\}`', SWITCH.read_text(encoding="utf-8"))]
    labels = [f"{n} · {a or b.capitalize()}" for n, (a, b) in zip("1234", words)]
    agents = flat(AGENTS_DOC)
    ctx.check(f"the registry has four tabs, got {labels} {tabs}", labels == ["1 · Agents", "2 · Workflows", "3 · Map", "4 · Live"])
    ctx.check(f"STUDIO-agents.md names each tab, got {[l for l in labels if l not in agents]}", all(l in agents for l in labels))
    for want in ("four tabs", "| Live while a session you have talked to is open, else the tab used last |",
                 '"Reading the sessions."', "`workflows`, `map` or `live` | that tab"):
        ctx.check(f"STUDIO-agents.md says {want!r}", want in agents)
    ctx.check("STUDIO-agents.md no longer says three tabs or the Map while a session runs",
              "three tabs" not in agents and "the Map while a session runs" not in agents)
    docs = {p.name: flat(p) for p in sorted(DOC.parent.glob("*.md"))}
    stale = [n for n, t in docs.items() if re.search(r"`?\?mode=agents&view=live`? lands on the Map|`&view=live`, lands on the Map", t)]
    ctx.check(f"no doc says view=live lands on the Map, got {stale}", not stale)
    ctx.check("REPLAY.md: open starts at view=map&replay=", "`?mode=agents&view=map&replay=<id>`" in docs.get("REPLAY.md", ""))
    ctx.check("replay_verbs.py opens view=map&replay=", "view=map&replay=" in REPLAY_OPEN.read_text(encoding="utf-8"))

if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
