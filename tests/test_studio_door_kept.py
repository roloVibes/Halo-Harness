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


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
