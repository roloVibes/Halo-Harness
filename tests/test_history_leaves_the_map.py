"""tests.test_history_leaves_the_map -- Halo 3.6.0.3 package B, the Studio cut's Map tab (R-B1, R-B8, B1+, L-B6, Z8),
the pure half (source checks and node through tests/helpers/node_ts.py; every platform). The browser half is on the
Linux VM and CI: tests/helpers/studio_map_quiet.py (the top line has no Replay slot), tests/test_studio_ui.py (no
History strip), tests/test_studio_panels_menu.py (the drawer's page is Run a goal).

1. History leaves Agents -> 3 · Map: the strip under the map, the drawer's History page and its lists, Open a file and
   a past session's report card (MapHistory.tsx, live/History.tsx, live/historyStore.ts, map/mapRuns.ts) are gone and
   nothing imports them; the drawer's page is `goal` by default and no page is titled History;
2. the scrubber, Save, Export a clip and Compare leave Studio (Scrubber.tsx, ReplaySave.tsx, Compare.tsx,
   compareStore.ts, styles/live-compare.css) with their test ids;
3. the Map never draws the past: useLit is always off (with `all` and `away`), its Lit has no replay mode or field,
   overlay.ts has no eventsAt, nothing of the Map (nor useLiveNodes) reads a replay, the top line has no Replay slot.
Run: python -m tests.test_history_leaves_the_map
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
MAP = CREW / "map"


def node(mod: str, body: str):
    from tests.helpers import node_ts
    js = f"const M = await import({json.dumps((SRC / mod).resolve().as_uri())});\nconst out = {{}};\n{body}\nconsole.log(JSON.stringify(out));"
    return node_ts.run(js)


def _code(text: str) -> str:
    """The source without its comments (a `//` inside a quoted string or after a colon -- a URL -- is kept)."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"(?<![:\"'`])//[^\n]*", "", text)


def _sources() -> "dict[str, str]":
    return {str(p.relative_to(SRC)).replace("\\", "/"): p.read_text(encoding="utf-8")
            for p in SRC.rglob("*") if p.suffix in (".ts", ".tsx", ".css") and p.is_file()}


def _importers(srcs: "dict[str, str]", pattern: str) -> "list[str]":
    rx = re.compile(r"""(?:from|import)\s*["'][^"']*""" + pattern + r"""["']""")
    return sorted(rel for rel, text in srcs.items() if rx.search(text))


@test
def test_history_and_its_lists_left_the_map(ctx: Ctx):
    gone = [MAP / "MapHistory.tsx", CREW / "live" / "History.tsx", CREW / "live" / "historyStore.ts", MAP / "mapRuns.ts"]
    ctx.check(f"History's files are gone: {[p.name for p in gone if p.exists()]}", not any(p.exists() for p in gone))
    srcs = _sources()
    users = _importers(srcs, r"/(?:MapHistory|History|historyStore|mapRuns)")
    ctx.check(f"nothing imports them: {users}", not users)
    feed = _code((MAP / "feedOpen.ts").read_text(encoding="utf-8"))
    ctx.check("the drawer's page is Run a goal's form by default", 'createStore<{ page: string }>({ page: "goal" })' in feed)
    got = node("routes/crew/map/drawerTitle.ts", """
out.goal = M.mapPageTitle('goal');
out.history = M.mapPageTitle('history');
out.run = M.mapPageTitle('run:r-1');
""")
    ctx.check(f"no page is titled History any more, got {got}",
              got.get("goal") == "Run a goal" and got.get("history") == "Run a goal" and got.get("run") == "Goal run")
    css = srcs.get("styles/map-lit.css", "")
    ctx.check("map-lit.css has no .mp-history rule", ".mp-history" not in css)
    drawer = _code((MAP / "MapDrawer.tsx").read_text(encoding="utf-8")) + _code((MAP / "MapView.tsx").read_text(encoding="utf-8"))
    ctx.check("the Map's drawer and view name no history page", '"history"' not in drawer and "HistoryDrawer" not in drawer)


@test
def test_the_scrubber_save_the_clip_and_compare_left_studio(ctx: Ctx):
    live = CREW / "live"
    gone = [live / "Scrubber.tsx", live / "ReplaySave.tsx", live / "Compare.tsx", live / "compareStore.ts",
            SRC / "styles" / "live-compare.css"]
    ctx.check(f"their files are gone: {[p.name for p in gone if p.exists()]}", not any(p.exists() for p in gone))
    srcs = _sources()
    users = _importers(srcs, r"/(?:Scrubber|ReplaySave|Compare|compareStore|live-compare\.css)")
    ctx.check(f"nothing imports them: {users}", not users)
    ids = ["replay-scrub", "replay-play", "replay-save", "replay-clip", "replay-bar"]
    held = sorted({f"{rel}: {i}" for rel, text in srcs.items() for i in ids if re.search(r"['\"`]" + i + r"['\"`-]", text)})
    ctx.check(f"no file holds their test ids: {held}", not held)
    time_css = SRC / "styles" / "live-time.css"
    ctx.check("live-time.css keeps no scrubber rule (.scr)", not time_css.exists() or ".scr" not in time_css.read_text(encoding="utf-8"))


@test
def test_the_map_never_draws_the_past(ctx: Ctx):
    lit = _code((MAP / "useLit.ts").read_text(encoding="utf-8"))
    ctx.check("useLit's Lit has no replay mode and no replay field", '"replay"' not in lit and not re.search(r"\breplay\s*:", lit))
    ctx.check("useLit is always off, with all and away", "return { ...OFF, all, away };" in lit and "useLiveReplay" not in lit)
    ov = _code((MAP / "overlay.ts").read_text(encoding="utf-8"))
    ctx.check("overlay.ts exports no eventsAt", "eventsAt" not in ov)
    srcs = _sources()
    readers = [rel for rel in _importers(srcs, r"/(?:live/)?(?:replay|timeline)")
               if rel.startswith("routes/crew/map/") or rel == "routes/crew/live/useLiveNodes.ts"]
    ctx.check(f"nothing of the Map nor useLiveNodes reads a replay: {readers}", not readers)
    words = {rel: _code(text) for rel, text in srcs.items() if rel.startswith("routes/crew/map/")}
    said = sorted(rel for rel, text in words.items()
                  if re.search(r"Replay the last session|Back to now|Replaying|map-lit-replay-last|map-replay-close|map-drawer-replay|map-feed-replay|mp-slot", text))
    ctx.check(f"no Replay slot, replay line or replay rows on the Map: {said}", not said)
    ctx.check("no part of the Map tests for a replay", not any('mode === "replay"' in t or "L.replay" in t for t in words.values()))
    css = srcs.get("styles/map-lit.css", "")
    ctx.check("map-lit.css has no quiet replay colours, replay rows or Replay slot",
              '[data-lit="replay"]' not in css and ".mpf-replay" not in css and ".mp-slot" not in css)
    nodes = _code((CREW / "live" / "useLiveNodes.ts").read_text(encoding="utf-8"))
    ctx.check("useLiveNodes has no replay branch", "replay" not in nodes)
    head = _code((MAP / "BoxHead.tsx").read_text(encoding="utf-8"))
    ctx.check("BoxHead's Dismiss names no History", "History" not in head)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
