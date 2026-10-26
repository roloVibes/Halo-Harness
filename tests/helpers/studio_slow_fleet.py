"""tests.helpers.studio_slow_fleet -- the Fleet map on a slow box (Halo 3.3.0.0
R7; GitHub's Linux runner, run 40294720639: the session tree said the
implementer was `stopped`, the map node still said `running` after 60 s, one
feed listener, nothing dropped). Over tests/helpers/studio_fleet_rig.py (this
harness's real session, the implementer and the researcher mid-work), with
Studio's answers and frames `HALO_STUDIO_SLOW_MS` late
(tests/test_studio_slow_box.py sets it):

1. `floor`: the implementer is stopped while every frame that would make the
   page re-read its view is lost -- the implementer's own `agent_state` frames
   (its end among them), turn_done, subagent_end, sessions, fleet, dropped --
   and the feed stays alive (the researcher's `agent_state` every second). The
   model call is let go only after the stop's own re-read has answered, so the
   view that read said `running`: only the map's poll floor can end the node;
   `floor_s` is how long after the tree said `stopped` the node did.
2. `late`: then a late `running` frame for the stopped implementer lands (a
   frame that beat the view's answer); `late_s` is how long the node takes to
   say `stopped` again (07bb8b9 kept it `running` for good while frames came).

    python -m tests.helpers.studio_slow_fleet

The last stdout line is the JSON of what it saw (exit 2: no Chrome). No model
is called."""
from __future__ import annotations

import os
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.chrome_driver import Driver  # noqa: E402
from tests.helpers.studio_fleet import DETAIL, node, wait_node  # noqa: E402

LOST = {"permission_request", "question", "plan_review", "approval_request", "turn_done", "subagent_start", "subagent_end",
        "sessions", "fleet", "dropped"}


def _slow_s() -> float:
    try:
        return int(os.environ.get("HALO_STUDIO_SLOW_MS") or 0) / 1000
    except ValueError:
        return 0.0


def _ended(c, timeout: float) -> "tuple[str, float]":
    t0 = time.monotonic()
    try:
        return wait_node(c, "implementer", "n.dataset.state === 'stopped'", timeout), round(time.monotonic() - t0, 2)
    except TimeoutError as e:
        return f"timeout: {str(e)[-160:]}", round(time.monotonic() - t0, 2)


def slow_stop(c, rig) -> dict:
    from halo_harness.fleet.identity import harness
    from tests.helpers.studio_fleet_rig import wait_for
    out: dict = {"slow_ms": int(_slow_s() * 1000), "lost": {}}
    c.go(rig.url("fleet"))
    c.wait("document.querySelectorAll('[data-testid=\"fleet-node\"]').length === 5", 60)
    key = rig.key("Implement")
    aid = key.rsplit("|", 1)[1]
    wait_node(c, "implementer")
    c.click_on(node("implementer"))
    try:
        c.wait(f"{DETAIL}?.dataset.key === '{key}'", 15)
        out["detail_by"] = "pointer"
    except TimeoutError:  # the runner's pointer path can be lost under latency: the element's own click event
        c.js(f"{node('implementer')}.dispatchEvent(new MouseEvent('click', {{bubbles: true, cancelable: true}})); 1")
        c.wait(f"{DETAIL}?.dataset.key === '{key}'", 30)
        out["detail_by"] = "element"
    bridge, gate = rig.server.events, {"on": True}
    publish = bridge.publish

    def lossy(frame, _p=publish):
        ev, d = frame.get("event"), frame.get("data") if isinstance(frame.get("data"), dict) else {}
        if gate["on"] and (ev in LOST or (ev == "agent_state" and (frame.get("agent_id") == aid or d.get("agent_id") == aid))):
            out["lost"][ev] = out["lost"].get(ev, 0) + 1
            return None
        return _p(frame)
    bridge.publish = lossy
    stop, row = threading.Event(), rig.agent("Research")
    sid, hid = rig.act.session_id, harness()["id"]

    def beat():  # the feed stays alive: another agent's frame every second
        while not stop.wait(1.0):
            publish({"session_id": sid, "harness": hid, "event": "agent_state", "data": dict(row, state="running"),
                     "turn": None, "agent_id": row.get("agent_id"), "ts": time.time()})
    threading.Thread(target=beat, daemon=True, name="slow-fleet-beat").start()
    try:
        c.click_on("document.querySelector('[data-testid=\"fleet-stop\"]')")
        c.wait("document.querySelector('[data-testid=\"fleet-confirm\"] .dialog-title')?.textContent", 10)
        c.click_on("document.querySelector('[data-testid=\"fleet-confirm-yes\"]')")
        out["stop_ack"] = c.wait("document.querySelector('.toasts')?.textContent.includes('stopping') && 'stopping'", 30)
        time.sleep(0.4 + 3 * _slow_s() + 1.0)  # the stop's own re-read (400 ms after its answer) has answered: `running`
        out["before_release"] = c.js(f"{node('implementer')}?.dataset.state")
        rig.release("a")
        out["stopped"] = wait_for(lambda: rig.agent("Implement").get("state") == "stopped" and "stopped", 30)
        out["floor"], out["floor_s"] = _ended(c, 30)
        gate["on"] = False  # 2: a late `running` frame for the stopped agent, the frames flowing again
        publish({"session_id": sid, "harness": hid, "event": "agent_state", "data": dict(rig.agent("Implement"), state="running"),
                 "turn": None, "agent_id": aid, "ts": time.time()})
        try:
            out["late_running"] = wait_node(c, "implementer", "n.dataset.state === 'running'", 10)
        except TimeoutError:
            out["late_running"] = "never drawn"  # the page may re-read before it draws: what counts is that it ends
        out["late"], out["late_s"] = _ended(c, 30)
        out["listeners"] = bridge.listeners()
    finally:
        stop.set()
        bridge.publish = publish
    return out


class SlowFleetDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from tests.helpers.studio_fleet_rig import StudioFleetRig
        with StudioFleetRig() as rig:
            yield ((slow_stop, (c, rig)),)


if __name__ == "__main__":
    sys.exit(SlowFleetDriver(sys.argv[1:]).main())
