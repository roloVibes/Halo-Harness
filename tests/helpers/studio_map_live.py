"""tests.helpers.studio_map_live -- Agents -> 3 · Map lit while a session runs, and History replayed on it (Halo 3.6.0.0
R4), in headless Chrome as a first-time user, over tests/helpers/studio_session_rig.py (this harness's real session:
main, an implementer and a researcher mid-work) and tests/helpers/studio_live_rig.py (extra agent rows, the session
row's `map`, and the map frames a session on a map sends: map_hop, map_step). Studio's command route to the session
is recorded (studio_session_steer.record_forward), so Steer and Stop are seen reaching it. The map `shop` and a past
session that ran on it (its log holding the map receipts) are seeded in the rig's scratch home. No model is called.

    lit       the tab's dot; the top line (started, the sentence, when an edit takes effect); each box's state, what it
              does, its cost, a row per fact, nothing cut; the session's stray agent in the strip, tagged
    hop       a hand-off moves on the line the frame names: the label shows the task, then its When again; a chain box
              to box; reduced motion: no travel, the line lit
    steps     a workflow box opened: its steps lit, the agent in a step, a repeat's rounds and checks
    helper    the made-up helper beside main, dashed, tagged, Save as an agent: the Agents form with its body, nothing
              written
    feed      R57: on 4 · Live, the Feed opened from its button; a click on a box sets it to that box; THINK / SAY / TALK
              rows; an ask shows its answers and the box waits on you; Steer and Stop reach the route; the keyboard
              (Enter on a box of Live) sets it too
    amber     another map shown: the amber line and Show the running map
    nomap     the session's row with no map: "Show it" -- main and every agent as a made-up helper, no lines
    room      at 1280 / 1500 / 1920: no sideways scroll, nothing under 12 px in the lit boxes and the drawer, controls >= 28 px
    zoom      a zoom step while frames arrive keeps his zoom (no re-fit under a hand zoom)
    panel     Session's Map panel: the same lit map, compact and read-only, with a link to the Map tab

    python -m tests.helpers.studio_map_live [DIR]     DIR: also save the pictures for docs/STUDIO-map.md
"""
from __future__ import annotations

import json
import sys
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.helpers.chrome_driver import Driver  # noqa: E402

MAP = """format: map/1
name: shop
boxes:
- {id: code, agent: implementer}
- {id: research, agent: researcher}
- {id: review, agent: reviewer}
- {id: check, workflow: review}
- {id: notes, agent: writer}
lines:
- {from: main, to: code, when: always}
- {from: main, to: research, when: main-decides}
- {from: main, to: review, when: ask}
- {from: code, to: check, when: always}
- {from: main, to: notes, when: {says: [docs]}}
"""
EXTRA = (("h3lp3r01", "general-purpose", "general-purpose", "or:mock/glm-5-coder", "List what the shop repo holds for the release notes"),
         ("r3v1e2w0", "reviewer", "reviewer", "or:mock/kimi-k3-research", "Review: the basket diff"),
         ("x0rph4n1", "stray", "stray", "or:mock/glm-5-coder", "Something nobody on this map started"))


def seed(rig) -> None:
    """The map `shop`, and the past session's log saying it ran on it (a hop to a box the map no longer has)."""
    from halo_harness.crew import store
    from halo_harness.live import history
    from tests.helpers.studio_session_parts import PAST_SID
    store.write_text(store.path_for("map", "shop", state_dir=rig.state), MAP)
    path = history.find(rig.state, PAST_SID)
    t0 = json.loads(path.read_text(encoding="utf-8").splitlines()[0])["ts"]

    def hop(line, t, state="start"):
        a, b = line.split(" -> ")
        return {"type": "receipt", "kind": "map", "event": "map_hop", "ts": t0 + t,
                "data": {"map": "shop", "line": line, "from": a, "to": b, "state": state, "t": t0 + t, "task": "Review basket.py", "why": "named by main"}}
    rows = [{"type": "receipt", "kind": "map", "event": "map_start", "ts": t0, "data": {"map": "shop", "t": t0}},
            hop("main -> review", 60), hop("main -> review", 540, "end"), hop("main -> pdfs", 20)]
    with open(path, "a", encoding="utf-8") as f:
        f.write("".join(json.dumps(r) + "\n" for r in rows))


class MapLiveDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}
    width, height = 1500, 900

    @contextmanager
    def session(self, c):
        from tests.helpers.studio_live_rig import Live
        from tests.helpers.studio_session_rig import StudioSessionRig
        from tests.helpers.studio_session_steer import record_forward
        from tests.helpers import studio_map_live_steps as S
        from tests.helpers import studio_map_live_more as M
        S.SHOTS[:] = self.argv[:1]
        with StudioSessionRig() as rig:
            seed(rig)
            lv = Live(rig, extra=EXTRA)
            lv.rows["h3lp3r01"]["crew"] = {"map": "shop", "box": "main", "made_up": True}
            lv.rows["r3v1e2w0"]["square"] = {"name": "review", "engine": "steps"}
            lv.rows["x0rph4n1"]["parent"] = "nobody"
            lv.refresh(map="shop")
            sent = record_forward(rig)
            yield tuple((fn, (c, rig, lv, sent)) for fn in (S.lit, S.hop_step, S.steps, S.helper, S.feed, M.amber, M.nomap,
                                                               M.zoom, M.room, M.panel))


if __name__ == "__main__":
    sys.exit(MapLiveDriver(sys.argv[1:]).main())
