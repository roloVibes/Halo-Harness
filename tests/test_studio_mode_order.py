"""tests.test_studio_mode_order -- Session's mode word whatever order its sources land in (Halo 3.4.1.0 R6), the page's
half: routes/fleet/modeOrder.ts run under node (skipped without a node that runs .ts), and its wiring in the fleet
store (sync.ts notes each status frame's mode, fresh.ts merges each GET answer through it). The server's half (GET
fleet never answers from before a registry change) is tests/test_studio_session_figures.py; the whole path in Chrome is
tests/test_studio_report_card.py.

1. a GET answer asked BEFORE the newest status frame landed keeps that frame's mode (it may have been read before the
   registry moved); one asked after it wins, frame or not (the registry is the truth then);
2. a status frame older than one already applied (the session's own ts) never puts its mode back, whichever order
   they arrive in;
3. with no frame at all (the mode moved before the session's feed was attached) the answer's mode is the word.
Run: python -m tests.test_studio_mode_order
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
FLEET = Path(__file__).resolve().parent.parent / "halo_harness" / "studio" / "ui" / "src" / "routes" / "fleet"

# Each case: the calls in arrival order, then what the word is. ("frame", mode, ts, at) / ("answer", mode, asked).
CASES = {
    "a frame, then an answer asked before it landed": ([("frame", "plan", 20.0, 1000), ("answer", "auto", 900)], "plan"),
    "a frame, then an answer asked after it landed": ([("frame", "plan", 20.0, 1000), ("answer", "plan", 1100)], "plan"),
    "an answer asked after the frame wins over it": ([("frame", "plan", 20.0, 1000), ("answer", "auto", 1100)], "auto"),
    "a newer frame, then an older one": ([("frame", "plan", 20.0, 1000), ("frame", "auto", 10.0, 1050), ("answer", "auto", 900)], "plan"),
    "an older frame, then a newer one": ([("frame", "auto", 10.0, 1000), ("frame", "plan", 20.0, 1050), ("answer", "auto", 900)], "plan"),
    "no frame: the answer's word": ([("answer", "plan", 900)], "plan"),
}

JS = """
const m = await import(%s);
const out = {};
for (const [name, [calls]] of Object.entries(%s)) {
  let seen, word = null;
  for (const c of calls) {
    if (c[0] === 'frame') { const r = m.frameMode(seen, c[1], c[2], c[3]); seen = r.seen; if (r.apply) word = c[1]; }
    else word = m.answerMode(c[1], seen, c[2]);
  }
  out[name] = word;
}
console.log(JSON.stringify(out));
"""


@test
def test_the_word_whatever_order_its_sources_land_in(ctx: Ctx):
    from tests.helpers import node_ts  # 3.4.1.1: a node without TypeScript (Debian's) transpiles with the UI's tsc
    js = JS % (json.dumps((FLEET / "modeOrder.ts").resolve().as_uri()), json.dumps(CASES))
    got = node_ts.run(js) or {}
    for name, (_calls, want) in CASES.items():
        ctx.check(f"{name}: {want}, got {got.get(name)!r}", got.get(name) == want)


@test
def test_the_fleet_store_merges_through_it(ctx: Ctx):
    sync = (FLEET / "sync.ts").read_text(encoding="utf-8")
    fresh = (FLEET / "fresh.ts").read_text(encoding="utf-8")
    ctx.check("a status frame's mode goes through noteMode, dropped when older",
              "if (fig.mode && !noteMode(h, sid, fig.mode, Number(f.ts))) delete fig.mode;" in sync)
    ctx.check("every GET answer's modes go through answerMode before anything else is merged",
              "const next = withModes(answer, asked);" in fresh and "answerMode(s.mode," in fresh
              and "frameMode(modeSeen.get(k), mode, ts, at)" in fresh)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="studio mode order"))
