"""tests.test_goal_run_report_page -- Halo 3.6.0.3 package B batch 1, "a finished goal run's report gets its own page",
the pure half (node through tests/helpers/node_ts.py, and source checks; every platform). The browser half is
tests/test_studio_report_card.py (the doors: `&run=<id>`, the palette; the drawer's title and its button) and
tests/test_studio_ui.py's plan run (a run that ends with its page open offers "Open its report"), on the Linux VM and CI.

1. the Map drawer's titles: `goal` = "Run a goal"; a goal run's `run:<id>` and `report:<id>` = "Goal run"; `history`
   keeps "History" while History is there;
2. what stays when History leaves (the goal run's doors, the goal form, the report, the report card) imports neither
   History's store nor Compare's: the cut can take them without breaking what stays;
3. no sentence of the goal run's pages sends him to History.
Run: python -m tests.test_goal_run_report_page
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
SRC = Path(__file__).resolve().parent.parent / "halo_harness" / "studio" / "ui" / "src"
CREW = SRC / "routes" / "crew"

# What stays when History is cut (B2+ and its build judge): none of these may import History's store or Compare's.
STAYS = ["run/door.ts", "run/GoalDrawer.tsx", "run/goalStore.ts", "run/RunReport.tsx", "run/reportStore.ts",
         "live/ReportCard.tsx", "live/cardData.ts"]
# The words a person reads that may still say History in routes/crew/run/, each with its reason (data, not code).
SKIP = {
    'group: "History"': "the palette line's GROUP stays History until the cut (batch 1's ruling 4); the cut removes it",
}


def node(mod: str, body: str):
    from tests.helpers import node_ts
    js = f"const M = await import({json.dumps((SRC / mod).resolve().as_uri())});\nconst out = {{}};\n{body}\nconsole.log(JSON.stringify(out));"
    return node_ts.run(js)


def _code(text: str) -> str:
    """The source without its comments (a `//` inside a quoted string or after a colon -- a URL -- is kept)."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"(?<![:\"'`])//[^\n]*", "", text)


@test
def test_the_map_drawers_titles(ctx: Ctx):
    got = node("routes/crew/map/drawerTitle.ts", """
out.goal = M.mapPageTitle('goal');
out.run = M.mapPageTitle('run:20261117-101500-ab12');
out.report = M.mapPageTitle('report:20261117-101500-ab12');
out.history = M.mapPageTitle('history');
""")
    ctx.check(f"the goal form's page is 'Run a goal', got {got.get('goal')!r}", got.get("goal") == "Run a goal")
    ctx.check(f"a goal run's pages are 'Goal run', got {got.get('run')!r} / {got.get('report')!r}",
              got.get("run") == "Goal run" and got.get("report") == "Goal run")
    ctx.check(f"History's page keeps its name while History is there, got {got.get('history')!r}", got.get("history") == "History")


@test
def test_what_stays_imports_neither_historys_store_nor_compares(ctx: Ctx):
    hits = []
    for rel in STAYS:
        f = CREW / rel
        ctx.check(f"{rel} is there", f.is_file())
        if not f.is_file():
            continue
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"""from\s+["'][./]*(?:live/)?(historyStore|compareStore)["']""", line):
                hits.append(f"{rel}:{n}: {line.strip()}")
    ctx.check(f"none of what stays imports historyStore or compareStore, got {hits}", not hits)
    card = (CREW / "live" / "cardData.ts").read_text(encoding="utf-8")
    ctx.check("the card's Cell is defined in cardData.ts", re.search(r"export type Cell\s*=", card) is not None)
    report = (CREW / "live" / "ReportCard.tsx").read_text(encoding="utf-8")
    ctx.check("History's own card page (CardPage) left ReportCard.tsx for History", "CardPage" not in _code(report))


@test
def test_no_goal_run_sentence_sends_him_to_history(ctx: Ctx):
    hits = []
    for f in sorted((CREW / "run").glob("*.ts*")):
        code = _code(f.read_text(encoding="utf-8"))
        for why in SKIP:
            code = code.replace(why, "")
        for n, line in enumerate(code.splitlines(), 1):
            # a word "history" a person reads: not an identifier (historyStore, toggleHistory, lane.history), not a testid
            if re.search(r"(?i)(?<![.\w-])history(?![\w.-])", line):
                hits.append(f"{f.name}: {line.strip()[:140]}")
    ctx.check(f"no sentence of a goal run's pages names History, got {hits}", not hits)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
