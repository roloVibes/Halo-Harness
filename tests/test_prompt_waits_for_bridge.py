"""tests.test_prompt_waits_for_bridge -- fx studio batch 2 (5): a prompt typed into Studio's Prompt panel reaches the
session only once Studio's event bridge listens to it. The page draws replies from live frames only; the bridge found
a new session on a 2 s registry scan (helped by sessions_new_api._nudge_bridge), and `sessions/<sid>/command` talked
to the session's socket directly, so a first prompt answered inside that gap was streamed to nobody (realcheck studio
on Linux, CI run 43766557996: the answer never showed). No real session: a fake registry row, a fake socket client,
the bridge's pump replaced.
Run: python -m tests.test_prompt_waits_for_bridge
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once  # noqa: E402

ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()

SID = "fx2prompt0000000000000000000000a"
ENTRY = {"session_id": SID, "endpoint": "nowhere", "pid": 1, "started": 1.0}


@test
def test_the_bridge_attaches_a_session_on_demand_and_says_when_it_listens(ctx: Ctx):
    from halo_harness.studio.events import EventBridge
    bridge = EventBridge(list_live=lambda: [])

    def slow_pump(entry, stop):  # the subscribe takes a moment, like a real socket
        time.sleep(0.15)
        with bridge._lock:
            bridge._attached[entry["session_id"]] = {"session_id": entry["session_id"]}
        stop.wait(5)
    bridge._pump = slow_pump
    t = time.monotonic()
    ok = bridge.ensure_attached(dict(ENTRY), timeout_s=3.0)
    took = time.monotonic() - t
    ctx.check(f"attached, after the subscribe and not before, got {ok} in {took:.2f}s", ok is True and 0.1 <= took < 2.0)
    t = time.monotonic()
    ctx.check("already listening: at once", bridge.ensure_attached(dict(ENTRY)) is True and time.monotonic() - t < 0.1)
    never = EventBridge(list_live=lambda: [])
    never._pump = lambda entry, stop: stop.wait(5)
    t = time.monotonic()
    ok = never.ensure_attached({**ENTRY, "session_id": "other"}, timeout_s=0.3)
    ctx.check(f"a session that never subscribes: False after the bound, got {ok}", ok is False and time.monotonic() - t < 1.5)
    bridge.close() if hasattr(bridge, "close") else None


@test
def test_a_subscribe_that_fails_does_not_hold_the_turn_for_the_whole_bound(ctx: Ctx):
    """fx studio batch 2 repair: when the session refuses the subscribe, the pump ends at once (and cools down); the
    wait ends with it instead of holding the first submit or steer for the full timeout."""
    from halo_harness.studio.events import EventBridge
    bridge = EventBridge(list_live=lambda: [])

    def refused_pump(entry, stop):  # the subscribe answers not-ok: the real pump's finally block, nothing attached
        time.sleep(0.05)
        with bridge._lock:
            bridge._stops.pop(entry["session_id"], None)
            bridge._cooldown[entry["session_id"]] = time.monotonic() + 30
    bridge._pump = refused_pump
    t = time.monotonic()
    ok = bridge.ensure_attached(dict(ENTRY), timeout_s=3.0)
    took = time.monotonic() - t
    ctx.check(f"False as soon as the pump has ended, got {ok} in {took:.2f}s", ok is False and took < 1.0)


@test
def test_a_submit_waits_for_the_bridge_before_the_session_hears_it(ctx: Ctx):
    from halo_harness.studio import sessions_api as S
    from halo_harness.studio.api import Request, dispatch
    order: list = []

    class Bridge:
        def ensure_attached(self, entry, timeout_s=3.0):
            order.append(("listen", entry.get("session_id")))
            return True

    class Client:
        def call(self, cmd, **fields):
            order.append(("send", cmd))
            return {"ok": True, "result": {"accepted": True}}

        def close(self):
            pass
    real = (S._list_live, S._client)
    S._list_live = lambda: [dict(ENTRY)]
    S._client = lambda entry, timeout: Client()
    try:
        server = SimpleNamespace(events=Bridge())
        req = Request(method="POST", path=f"sessions/{SID}/command", query={},
                      body={"cmd": "submit", "text": "say RC-ANSWER-42", "client_id": "pp-fx2-1"},
                      cwd=Path.cwd(), state_dir=Path.cwd(), server=server, owner=True)
        status, obj = dispatch(req)
        ctx.check(f"the bridge listens first, then the turn is sent, got {status} {order}",
                  order[:1] == [("listen", SID)] and ("send", "submit") in order and order.index(("listen", SID)) < order.index(("send", "submit")))
        order.clear()
        req.body = {"cmd": "slash", "text": "/help"}
        dispatch(req)
        ctx.check(f"a /command's output comes back in its answer: no wait, got {order}", ("listen", SID) not in order)
    finally:
        S._list_live, S._client = real


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
