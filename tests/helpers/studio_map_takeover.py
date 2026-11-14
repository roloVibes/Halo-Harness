"""tests.helpers.studio_map_takeover -- Halo 3.6.0.0 R4b "the lit Map takes over what the old Live view still does", in
headless Chrome over the same rigs as the lit Map's driver (tests/helpers/studio_map_live.py: this harness's real
session, the extra agent rows, the map `shop`, Studio's command route recorded). No model is called.

    facts     a clicked box's facts in the drawer's head (its model and why, what it may use, tokens, cost, how long);
              Pause / Resume reach the route Live's node menu calls; a failed agent's Dismiss
    clocks    the seconds on "what it does now" ("Bash pytest -q · 3 s", "waiting on you · 2 s"); the box the session
              waits on outlined; the sentence's wait brings it into view and opens it in the drawer
    talk      a TALK between two boxes: a dashed pulse and its label (no line added); reduced motion: the boxes marked
    depth     a helper's own helper: "+1 under it", not drawn; the drawer lists who started whom; a row filters to it
    plan      the session's todo plan: "plan: 1 of 3 done", its rows in the drawer
    keys      J / K between the working boxes
    hover     a summary card on a lit box (by a pointer's move only, never over the box's controls)
    ask       a real pending ask with its Attention row: its answer pressed in the drawer reaches the session
    two       two sessions run on the map: the picker switches which is lit
    goal      Run a goal from the Map's bar opens the goal form in the drawer
    replay    with nothing running, "Replay the last session" replays it on the map; the drawer shows its rows

    python -m tests.helpers.studio_map_takeover
"""
from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.helpers.chrome_driver import Driver  # noqa: E402

TWO_SID = "5eed0000two000000000000000000002"


def second_session(rig, lv) -> None:
    """A second session of this harness running on the map (one more row in GET fleet), restored on close."""
    import time
    from halo_harness.peers import local_view
    orig = local_view.sessions

    def sessions(list_live=None):
        rows = orig(list_live)
        if lv.fields.get("two"):
            rows.append({"session_id": TWO_SID, "title": "the second session", "kind": "tui", "cwd": str(rig.proj), "started": time.time() + 5,
                         "map": "shop", "busy": True, "agents": [{"agent_id": "main", "name": "main", "role": "main", "kind": "main",
                                                                  "state": "running", "current": "thinking", "model": "or:mock/qwen3-lead"}]})
        return rows
    local_view.sessions = sessions
    rig.closers.append(lambda: setattr(local_view, "sessions", orig))


def record_answers(rig, sent: list) -> None:
    """A session command Studio sends (an ask's answer goes this way: live/attention/answer -> the session's socket),
    recorded beside the agent commands with what the session said."""
    from halo_harness.studio import sessions_api
    orig = sessions_api.post_command

    def post_command(req):
        status, body = orig(req)
        sent.append({"sid": req.params.get("sid"), "cmd": str(req.body.get("cmd") or ""), "fields": dict(req.body), "status": status, "result": body})
        return status, body
    sessions_api.post_command = post_command
    rig.closers.append(lambda: setattr(sessions_api, "post_command", orig))


class TakeoverDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}
    width, height = 1500, 900

    @contextmanager
    def session(self, c):
        from tests.helpers.studio_live_rig import Live
        from tests.helpers.studio_session_rig import StudioSessionRig
        from tests.helpers.studio_session_steer import record_forward
        from tests.helpers.studio_map_live import EXTRA, seed
        from tests.helpers import studio_map_takeover_steps as S
        from tests.helpers import studio_map_takeover_more as M
        with StudioSessionRig() as rig:
            seed(rig)
            lv = Live(rig, extra=EXTRA)
            lv.rows["h3lp3r01"]["crew"] = {"map": "shop", "box": "main", "made_up": True}
            lv.rows["r3v1e2w0"]["square"] = {"name": "review", "engine": "steps"}
            lv.rows["x0rph4n1"]["parent"] = "nobody"
            lv.refresh(map="shop")
            second_session(rig, lv)
            sent = record_forward(rig)
            record_answers(rig, sent)
            yield tuple((fn, (c, rig, lv, sent)) for fn in (S.facts, M.goal, S.clocks, S.talk, S.depth, S.plan, M.keys, M.hover, M.ask,
                                                               M.two, M.replay))


if __name__ == "__main__":
    sys.exit(TakeoverDriver(sys.argv[1:]).main())
