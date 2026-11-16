"""tests.test_map_s13_three_places -- Halo 3.6.0.2 R21: S13 ("This session keeps running on {old}, as it started. Start a
new session to run on {new}.") is ONE sentence in three places: the Builder card's use row, the result tail main repeats,
and Studio's truth block. The card and the tail come from crew/map_facts.py through the Builder (crew/session_tool.py,
in a scratch home: tests/helpers/crew_rig.py); the truth block's line from routes/crew/map/truth.ts in node
(tests/helpers/node_ts.py), the same facts Session's truth block renders (TruthBlock.tsx reads only truthLines). The pin
keeps the Python and the TypeScript templates from drifting apart. No model, no browser.
Run: python -m tests.test_map_s13_three_places
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
TRUTH = Path(__file__).resolve().parent.parent / "halo_harness" / "studio" / "ui" / "src" / "routes" / "crew" / "map" / "truth.ts"
S13_RF = "This session keeps running on starter (the default), as it started. Start a new session to run on review-flow."
TAIL = "In the terminal: quit and run halo again; /clear keeps starter (the default)."
USE_PREFIX = "New sessions run on review-flow. "
WORD = "Tell the person, word for word: "

TS = """const T = await import(%s);
const f = { title: 's', a: 'starter', plain: true, b: 'review-flow', bSince: 2000, started: 1000, turns: 1, studio: false,
  ended: null, machine: null, unreadable: null, changed: null, workflow: null, busy: false };
const lines = T.truthLines(f);
console.log(JSON.stringify({ first: lines[0], s13: T.s13(T.mapName('starter', true), 'review-flow'),
  term: T.s13(T.mapName('starter', true), 'review-flow', true) }));"""


def _card_and_tail() -> tuple:
    """The use row and the result tail of one Builder card that makes the map review-flow in a plain session."""
    import time
    from tests.helpers.crew_rig import CrewRig
    from tests.test_builder_map import _S, _box, _line, _uses
    with CrewRig() as rig:
        from halo_harness.crew import session_tool
        s = _S(rig)
        s._map_started_at = time.time()
        pv = session_tool.preview(s, {"changes": [
            {"tool": "agent_make", "args": {"name": "my-reviewer", "does": "Reviews.", "uses": ["read"]}},
            _box("review-flow", "my-reviewer"), _line("review-flow", "my-reviewer")]})
        use = [u["summary"] for u in _uses(pv["rows"])]
        out = session_tool.finish(pv, "Apply them", s)
    return use, out


@test
def test_the_same_sentence_in_three_places(ctx: Ctx):
    from tests.helpers import node_ts
    use, out = _card_and_tail()
    row = use[0] if len(use) == 1 else ""
    ctx.check(f"(1) the card has one use row starting {USE_PREFIX!r}, got {use}", row.startswith(USE_PREFIX))
    card = row[len(USE_PREFIX):].split(" In the terminal:")[0]
    tail = out.split(WORD, 1)[1] if WORD in out else ""
    said = tail.split(" In the terminal:")[0]
    ts = node_ts.run(TS % json.dumps(TRUTH.resolve().as_uri()))
    studio = ts["first"].get("text", "")
    ctx.check(f"(1) the card's S13, got {card!r}", card == S13_RF)
    ctx.check(f"(2) the tail main repeats, got {said!r}", said == S13_RF)
    ctx.check(f"(3) Studio's truth block line, got {studio!r}", studio == S13_RF)
    ctx.check(f"the three are one string: {card == said == studio}", card == said == studio)
    ctx.check(f"Studio's line carries [New session] and never the terminal's words, got {ts['first']}",
              ts["first"].get("act") == "new-session" and ts["first"].get("label") == "New session" and "In the terminal" not in studio)
    ctx.check(f"the terminal tail of (2), got {tail!r}", tail == f"{S13_RF} {TAIL}")
    ctx.check(f"the card's row ends with the same terminal tail, got {row!r}", row.endswith(f"{S13_RF} {TAIL}"))
    ctx.check(f"truth.ts's terminal form is the card's, got {ts['term']!r}", ts["term"] == f"{S13_RF} {TAIL}" and ts["s13"] == S13_RF)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
