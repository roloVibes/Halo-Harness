"""tests.test_steer_silent_children -- a steer to main while its sub-agents'
model calls are still silent reaches them and keeps them alive (Halo
3.1.7.0). Over this harness's real session (tests/helpers/studio_fleet_rig.py:
main runs an implementer and a researcher through the real Controller; both
are held mid-call in the scripted mock, waiting for their second reply),
the steer goes in the way Studio's Session box sends it (`fleet_api.forward`,
`agent_steer`, mode nudge). Pinned:

1. main accepts it as a steer (its turn is busy) and forwards it into both
   running children (2.0.7 round 0c);
2. each child's silent call is cut and resent with the steer as its last
   user message -- the mock sees the second request within 5 s;
3. both children are still `running` afterwards and main is still busy: no
   child died of the cut (Linux raised RemoteDisconnected out of the
   force-shut socket; Windows never woke the read until the socket closed).
Run: python -m tests.test_steer_silent_children
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
SENT = "check the tax rule before the discount"
_RUN: dict = {}


def _run() -> dict:
    if _RUN:
        return _RUN
    from tests.helpers.fleet_rig import wait_for
    from tests.helpers.studio_fleet_rig import StudioFleetRig
    out: dict = {}
    with StudioFleetRig() as rig:
        from halo_harness.studio import fleet_api
        out["before"] = {a.get("agent_id"): a.get("state") for a in rig.agents()}
        out["seen_before"] = (len(rig.seen["a"]), len(rig.seen["b"]))
        t0 = time.monotonic()
        out["forward"] = fleet_api.forward(rig.act.session_id, "steer", {"agent_id": "main", "text": SENT, "mode": "nudge", **fleet_api.caller()})
        ok = wait_for(lambda: len(rig.seen["a"]) >= 2 and len(rig.seen["b"]) >= 2, 5)
        out["resent_s"] = round(time.monotonic() - t0, 2)
        out["resent"] = bool(ok)
        out["seen_after"] = (len(rig.seen["a"]), len(rig.seen["b"]))

        def last_user(body) -> str:
            msgs = (body or {}).get("messages") or []
            return json.dumps(msgs[-1]) if msgs else ""
        out["last_a"] = last_user(rig.seen["a"][-1]) if rig.seen["a"] else ""
        out["last_b"] = last_user(rig.seen["b"][-1]) if rig.seen["b"] else ""
        time.sleep(1.0)
        rows = rig.agents()
        out["after"] = {(a.get("task") or a.get("agent_id") or "")[:9]: a.get("state") for a in rows}
        out["children_running"] = [a.get("state") for a in rows if a.get("agent_id") != "main"]
        from halo_harness.remote.client import ControlClient
        c = ControlClient(rig.act.endpoint, rig.act.server.token, timeout=5)
        try:
            out["main_busy"] = bool((c.call("status").get("result") or {}).get("busy"))
        finally:
            c.close()
    _RUN.update(out)
    return _RUN


@test
def test_main_takes_the_steer_and_forwards_it_into_its_silent_children(ctx: Ctx):
    got = _run()
    ctx.check(f"the rig started with two running children, got {got['before']}", list(got["before"].values()).count("running") >= 3)
    ctx.check(f"main's turn was busy, so the text went in as a steer, got {got['forward']}", got["forward"][0] == 200 and (got["forward"][1] or {}).get("steered") is True)
    ctx.check(f"each child's silent call was cut and resent within 5 s, got {got['seen_after']} in {got['resent_s']} s", got["resent"] and got["seen_after"] == (2, 2))
    ctx.check(f"the resent requests carry the steer as the last user message, got {got['last_a'][:120]!r}",
              SENT in got["last_a"] and SENT in got["last_b"] and '"role": "user"' in got["last_a"])


@test
def test_no_child_dies_of_the_cut_on_this_platform(ctx: Ctx):
    got = _run()
    ctx.check(f"both children still running on {sys.platform}, got {got['after']}", got["children_running"] == ["running", "running"])
    ctx.check(f"main still mid-turn (its batch waits on them), got busy={got['main_busy']}", got["main_busy"] is True)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
