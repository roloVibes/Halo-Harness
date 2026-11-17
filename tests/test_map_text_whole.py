"""tests.test_map_text_whole -- 3.6.0.2 P8 batch 1: the owner's standing rules on the run drawings, the Map and the words of
Agents and Session (judge B's musts 1 to 6), checked on the UI source on every platform (the browser halves are in
tests/test_studio_run_parts.py, test_studio_map_takeover.py and test_studio_session_just_built.py, on the Linux VM).

1. a text is never cut: no ellipsis, no one-line `nowrap` and no line clamp on the wait link (both run drawings), the goal
   run's words beside its Open, a Map replay's rows, the pair "Running: {A} | Just built: {B}" and the Map bar's "New
   sessions run on {map}."; no slice of the words a person reads there (the goal at 80, a replay row at 197, a replay's
   title at 60);
2. the wait link has its own row, its room reserved by twins of the longest links the run can show (truth.ts waitRoom,
   node-run: each twin at least as long as narrate.ts lets a link be);
3. words that are true: nothing a person reads says the Map tab "comes in the next version"; 2 · Workflows says how a
   workflow gets on a map in ONE sentence (truthWords.ts TO_A_MAP) in its three places; Session's help says Feed and Live
   (from WORDS) and describes the drawing of today, not "one live column" and the old tree.
Run: python -m tests.test_map_text_whole
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
UI = Path(__file__).resolve().parent.parent / "halo_harness" / "studio" / "ui" / "src"
STYLES = UI / "styles"
MAP = UI / "routes" / "crew" / "map"
CUT = re.compile(r"text-overflow:\s*ellipsis|white-space:\s*nowrap|line-clamp")

# the selectors of the texts the judge found cut, and the stylesheet each lives in
WHOLE = {
    "map-down.css": [".mp-wait-link", ".mp-wait-words", ".mp-wait-row", ".mp-pair", ".mp-pair-btn"],
    "map-lit.css": ["[data-testid=map-lit-extras]", ".mpf-replay .mpf-mark", ".mp-extras-run", ".mp-extras-goal"],
    "map.css": [".mp-uses-default", ".mp-uses-slot"],
}


def _rules(css: str) -> list:
    """(selector, body) of every rule, comments dropped."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    return [(m.group(1).strip(), m.group(2)) for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css)]


@test
def test_no_text_a_person_reads_is_cut(ctx: Ctx):
    for name, sels in WHOLE.items():
        rules = _rules((STYLES / name).read_text(encoding="utf-8"))
        for sel in sels:
            cut = [(s, b.strip()) for s, b in rules if sel in s and CUT.search(b)]
            ctx.check(f"{name}: nothing cuts {sel} (no ellipsis, nowrap or line clamp), got {cut}", cut == [])
    lit = (MAP / "LitLine.tsx").read_text(encoding="utf-8")
    feed = (MAP / "FeedParts.tsx").read_text(encoding="utf-8")
    ctx.check("the goal run's words are whole (no goal_what.slice)", "goal_what.slice" not in lit)
    ctx.check("a replay's title is whole in its line and its offer (no title/what .slice)", ".slice(" not in lit)
    ctx.check("a replay row's task is whole (no slice at 197 and its dots)", "slice(0, 197)" not in feed and '+ "..."' not in feed)
    ctx.check("Open is the goal run's own item, outside the words", 'className="mp-extras-goal"' in lit
              and lit.index('className="mp-extras-goal"') < lit.index('data-testid="map-lit-run-open"'))


@test
def test_the_wait_link_has_its_own_reserved_row(ctx: Ctx):
    wait = (MAP / "runWait.tsx").read_text(encoding="utf-8")
    ctx.check("runWait.tsx draws the link inside WaitRow with its twins", "export function WaitRow" in wait and "mp-wait-twin" in wait)
    for f in (UI / "routes" / "session" / "MapDown.tsx", UI / "routes" / "agents" / "LiveDraw.tsx"):
        src = f.read_text(encoding="utf-8")
        ctx.check(f"{f.name} uses the reserved row, never the bare link", "<WaitRow world={world} />" in src and "<WaitLink" not in src)
    from tests.helpers import node_ts
    truth = (MAP / "truth.ts").resolve().as_uri()
    got = node_ts.run(f"const T = await import({json.dumps(truth)});\n"
                      "console.log(JSON.stringify([T.waitRoom([]), T.waitRoom(['main', 'a-rather-long-agent-name'])]));")
    plain, named = got
    ctx.check(f"with no names: main's link and the ask's, got {plain}", len(plain) == 2 and plain[0].startswith("waiting on: main -> "))
    # narrate.ts: "waiting on: {who} -> {short(what, 36)}", "waiting on you: {short(what, 48)} (and n more)"
    ctx.check(f"each twin is as long as the longest link it stands for, got {[len(t) for t in named]}",
              len(named[0]) >= len("waiting on: a-rather-long-agent-name -> ") + 36
              and len(named[1]) >= len("waiting on you: ") + 48 + len(" (and 9 more)") and "a-rather-long-agent-name" in named[0])


@test
def test_the_words_are_true(ctx: Ctx):
    from tests.helpers import node_ts
    words = (MAP / "truthWords.ts").resolve().as_uri()
    to_map = node_ts.run(f"const W = await import({json.dumps(words)}); console.log(JSON.stringify(W.TO_A_MAP ?? null));")
    ctx.check(f"ONE sentence says how a workflow gets on a map, got {to_map!r}",
              to_map == "To put a workflow on a map: in 3 · Map, drag it from Agents and workflows onto a box, and that box hands work to it.")
    flows = UI / "routes" / "crew" / "flows"
    for f in ("FlowList.tsx", "FlowForm.tsx", "flowStore.ts"):
        src = (flows / f).read_text(encoding="utf-8")
        ctx.check(f"{f}: says it with TO_A_MAP", "${TO_A_MAP}" in src)
    said = []
    for f in (UI / "routes").rglob("*.ts*"):
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("//")[0]
            if re.search(r"""["`'][^"`']*(next version|Map tab comes next)""", code):
                said.append(f"{f.name}:{i}")
    ctx.check(f"no string a person reads says the Map comes in the next version, got {said}", said == [])
    help_src = (UI / "routes" / "sectionHelp.ts").read_text(encoding="utf-8")
    session = help_src[help_src.index("  session: {"):help_src.index("  packs: {")]
    ctx.check("Session's help no longer says 'one live column' or 'Read the map'",
              "one live column" not in session and '"Read the map"' not in session and "Each agent sits under the one that spawned it" not in session)
    ctx.check("Session's help says the Feed and Live from WORDS, and the step 'Read Live' with the card's buttons",
              "the ${WORDS.feed} -- " in session and "[`Read ${WORDS.live}`" in session
              and "Pause, Stop, Steer and Open in Agents -> ${WORDS.live}" in session)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
