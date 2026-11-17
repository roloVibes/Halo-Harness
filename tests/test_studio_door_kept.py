"""tests.test_studio_door_kept -- Halo 3.6.0.2 P4 batch 9, "a door never leads nowhere", the pure half (node, every
platform, through tests/helpers/node_ts.py); the browser half is tests/test_studio_doors.py (the Linux VM and CI).

1. lib/workspace/kept.ts: a door that switches section and asks a panel to open in the same step, before that section has
   laid out, has its ask KEPT and applied at the first layout (persist.ts patchPanel / showPanel keep it): one ask per
   panel, the last wins, in the order asked, each taken once;
2. crew/map/stepInTarget.ts `placeOf`: where the asking agent of an ask is drawn -- main's box, the box its row belongs
   to (a box's own rows or its named children), else its workflow's block -- so an alert's Open selects THAT box.
Run: python -m tests.test_studio_door_kept
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
SRC = Path(__file__).resolve().parent.parent / "halo_harness" / "studio" / "ui" / "src"


def node(mod: str, body: str):
    from tests.helpers import node_ts
    js = f"const M = await import({json.dumps((SRC / mod).resolve().as_uri())});\nconst out = {{}};\n{body}\nconsole.log(JSON.stringify(out));"
    return node_ts.run(js)


@test
def test_an_ask_before_the_layout_is_kept_and_the_last_wins(ctx: Ctx):
    got = node("lib/workspace/kept.ts", """
const ran = [];
M.keepAsk('agents-map', 'map-drawer', () => ran.push('drawer-1'));
M.keepAsk('agents-map', 'plan', () => ran.push('plan'));
M.keepAsk('agents-map', 'map-drawer', () => ran.push('drawer-2'));
M.keepAsk('session', 'session-attention', () => ran.push('attention'));
out.kept = M.keptFor('agents-map');
for (const go of M.takeAsks('agents-map')) go();
out.ran = ran.slice();
out.again = M.takeAsks('agents-map').length;
out.other = M.keptFor('session');
""")
    ctx.check(f"one ask per panel, the last one last, got {got.get('kept')}", got.get("kept") == ["plan", "map-drawer"])
    ctx.check(f"applied at the layout in the order asked, the last ask for a panel wins, got {got.get('ran')}",
              got.get("ran") == ["plan", "drawer-2"])
    ctx.check(f"each ask runs once, got {got.get('again')}", got.get("again") == 0)
    ctx.check(f"another section's asks wait for its own layout, got {got.get('other')}", got.get("other") == ["session-attention"])


@test
def test_the_asking_agents_box_is_found_on_the_drawing(ctx: Ctx):
    got = node("routes/crew/map/stepInTarget.ts", """
const box = (agents) => ({ state: 'working', doing: '', cost: 0, agents, models: [] });
const ov = { boxes: { main: box(['main']), check: box(['r3v1e2w0']), code: box([]) },
             kids: { code: [{ aid: 'h3lp3r01', made: true, agent: 'helper', model: '', task: '', state: 'waiting', unlined: false, off: false }] },
             blocks: {}, lines: {}, pulses: [], helpers: [], strangers: [], steps: {}, waiting: [], gone: [], off: [], offCount: 0 };
const rows = [{ id: 't7e5s1t0', key: 'h|s|t7e5s1t0', name: 'tester', state: 'waiting', row: { crew: { workflow: 'review', step: 2 } } }];
out.main = M.placeOf('main', null, []);
out.own = M.placeOf('r3v1e2w0', ov, rows);
out.kid = M.placeOf('h3lp3r01', ov, rows);
out.step = M.placeOf('t7e5s1t0', ov, rows);
out.none = M.placeOf('nobody', ov, rows);
""")
    ctx.check(f"main's ask: main's box, got {got.get('main')}", got.get("main") == {"box": "main"})
    ctx.check(f"a box's own agent: that box, got {got.get('own')}", got.get("own") == {"box": "check"})
    ctx.check(f"a named child under a box: that box, got {got.get('kid')}", got.get("kid") == {"box": "code"})
    ctx.check(f"a workflow's step agent: its block, got {got.get('step')}", got.get("step") == {"workflow": "review"})
    ctx.check(f"an agent the drawing does not hold: nothing, got {got.get('none')}", got.get("none") is None)


@test
def test_the_doors_ask_is_in_the_feed_at_once_and_once(ctx: Ctx):
    """P9 batch 2 (CI on the candidate, the coordinator's ruling): the door of an ask from an agent on no box says "its
    question is in the Feed", so it hands the ask itself to the Feed (shared/liveFeed.ts `handAsk` over the pure
    shared/liveAsk.ts: `askOfRow`, the attention row it was opened with -- the agent, the question; its choices are the
    row's keys) -- the row is there before any frame of it reached the page; the frame that brings the same ask later
    (`askOfFrame`) fills that row instead of drawing a second (`withAsk`: matched by the ask's id; a row with none -- an
    agent that waits -- takes that agent's first ask), and an ask already in the Feed is not handed twice."""
    got = node("routes/shared/liveAsk.ts", """
let lines = [], n = 0;
const put = (key, a) => { lines = M.withAsk(lines, key, a, () => ({ n: ++n, t0: 0 })); };
const row = (kind, what, detail, rid) => M.askOfRow({ kind, what, detail, since: 100, target: rid ? { request_id: rid } : {} });
const frame = (id, command) => M.askOfFrame('permission_request', { id, name: 'Bash', input: { command } }, 101);
const asks = (key) => lines.filter((l) => l.kind === 'ask' && l.key === key).map((l) => [l.text, l.id]);
const waits = row('waiting', 'lookout waits on you', 'Lookout: watch the basket', '');
put('h|s|look', waits);
out.waits = asks('h|s|look');
put('h|s|look', waits); // the door pressed again
out.again = asks('h|s|look').length;
put('h|s|look', frame('perm-held', 'ls')); // the frames that were held back come
out.filled = asks('h|s|look');
put('h|s|look', frame('perm-next', 'pwd')); // its next ask is a row of its own
out.next = asks('h|s|look').length;
put('h|s|card', row('permission', 'Permission: Bash', 'git status', 'perm-c'));
put('h|s|card', frame('perm-c', 'git status'));
out.card = asks('h|s|card');
put('h|s|early', frame('perm-e', 'make')); // the frame came first: the door adds nothing
put('h|s|early', row('permission', 'Permission: Bash', 'make', 'perm-e'));
out.early = asks('h|s|early');
out.events = M.ASK_EVENTS;
""")
    ctx.check(f"the door's row is in the Feed at once, in the attention row's words, got {got.get('waits')}",
              got.get("waits") == [["lookout waits on you · Lookout: watch the basket", ""]])
    ctx.check(f"pressed again: still one row, got {got.get('again')}", got.get("again") == 1)
    ctx.check(f"the held frame fills that row (no second row), got {got.get('filled')}",
              got.get("filled") == [["asks to run: ls", "perm-held"]])
    ctx.check(f"the agent's next ask is its own row, got {got.get('next')}", got.get("next") == 2)
    ctx.check(f"a card's frame (same ask id) fills its row, got {got.get('card')}", got.get("card") == [["asks to run: git status", "perm-c"]])
    ctx.check(f"an ask already in the Feed is not handed twice, got {got.get('early')}", got.get("early") == [["asks to run: make", "perm-e"]])
    ctx.check(f"the four ask frames are still read, got {got.get('events')}",
              got.get("events") == ["permission_request", "question", "plan_review", "approval_request"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
