"""tests.test_studio_session_figures -- Session's figures keep up with the
terminal (Halo 3.1.8.0 R6), the server half, over a REAL session
(tests/helpers/fleet_rig.py: the real Session, Controller and control
socket, a scripted mock model whose usage chunks carry tokens and a cost)
and Studio's real event bridge (studio/events.py):

1. each model call's `message_end` carries the running cost and token totals
   the terminal shows (`status` on the control socket, the figures the TUI's
   status bar reads), and the turn's closing `status` frame the same;
2. the Studio row (GET fleet's local snapshot, fleet/local_view.py) matches
   the frame within 1 s of the bridge publishing it, even with the snapshot
   cache warm from before the event (the bridge drops it on a local
   session's turn_done / message_end / status); the main agent's row carries
   the meter's own tokens from message_end;
3. a member's frame (not a session the bridge pumps) leaves the cache alone;
   a snapshot read while forget() ran is never cached;
4. an agent row's text and cost changed inside the 1.0 s quiet window go
   out when the window ends (the trailing flush), never dropped.
No model is called beyond the local mock. Run: python -m tests.test_studio_session_figures
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.fleet_rig import FleetRig, gated, text_step, tool_step, wait_for  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
FIGS = ("cost_usd", "total_input_tokens", "total_output_tokens")


def _usage(chunks: list, tin: int, tout: int, cost: float) -> list:
    """The step's chunks with an OpenAI usage block (tokens and the provider's cost) on its finish chunk."""
    last = dict(chunks[-1], usage={"prompt_tokens": tin, "completion_tokens": tout, "cost": cost})
    return chunks[:-1] + [last]


class _Feed:
    """The browser's side of the bridge: one queue, every frame kept with the time it came out."""

    def __init__(self, bridge) -> None:
        self.q, self.frames = bridge.subscribe("all"), []

    def next(self, pred, timeout: float = 15.0):
        for at, f in self.frames:
            if pred(f):
                self.frames.remove((at, f))
                return at, f
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            f = self.q.get(0.1)
            if f is None:
                continue
            at = time.monotonic()
            if pred(f):
                return at, f
            self.frames.append((at, f))
        return None, None


def _row(sid: str) -> dict:
    from halo_harness.fleet import local_view
    return next((r for r in local_view.snapshot().get("sessions") or [] if r.get("session_id") == sid), {})


def _main(row: dict) -> dict:
    return next((a for a in row.get("agents") or [] if a.get("agent_id") == "main"), {})


def _own(sid: str, kind: str):
    return lambda f: f.get("session_id") == sid and f.get("event") == kind and not f.get("agent_id")


@test
def test_each_message_end_is_the_terminals_figure_and_the_studio_row_follows(ctx: Ctx):
    g1, g2 = threading.Event(), threading.Event()
    seen1: list = []
    seen2: list = []
    with FleetRig() as rig:
        from halo_harness.fleet import local_view
        from halo_harness.remote import runtime
        from halo_harness.studio.events import EventBridge
        keep = local_view.CACHE_S
        local_view.CACHE_S = 30.0  # a snapshot from before the event would be served for 30 s unless the bridge drops it
        bridge = EventBridge(poll_s=0.2)
        try:
            model = rig.script("figures-main", [
                gated(g1, _usage(tool_step(("Glob", {"pattern": "*.md"}, "call_f1")), 1000, 50, 0.0012), seen1),
                gated(g2, _usage(text_step("one note file"), 1500, 80, 0.0021), seen2)])
            controller = rig.controller(rig.session(model))
            act = runtime.start_for_controller(controller)
            sid, client, feed = act.session_id, rig.client(act), _Feed(bridge)
            at, hello = feed.next(lambda f: f.get("event") == "sessions" and (f.get("data") or {}).get("attached") == sid)
            ctx.check("the bridge attached the session", hello is not None)
            controller.submit("count the note files")
            ctx.check("the first model call is in flight", wait_for(lambda: seen1, 10))
            warm = _row(sid)  # the cache is warm with the row from before the call's end
            ctx.check(f"before the call ends the row has no tokens yet, got {warm.get('tokens_in')!r}", not warm.get("tokens_in"))
            g1.set()
            t1, me1 = feed.next(_own(sid, "message_end"))
            d1 = (me1 or {}).get("data") or {}
            st1 = client.call("status")["result"]  # call 2 is gated: the terminal's figure stands still
            ctx.check(f"message_end 1 carries the running totals, got {[d1.get(k) for k in FIGS]}",
                      [d1.get(k) for k in FIGS] == [0.0012, 1000, 50] and (me1 or {}).get("turn") == 1)
            ctx.check(f"and they are the terminal's (status), got {[st1.get(k) for k in FIGS]}", [st1.get(k) for k in FIGS] == [d1.get(k) for k in FIGS])
            row = wait_for(lambda: (lambda r: r if r.get("cost_usd") == d1.get("cost_usd") else None)(_row(sid)), 1.0)
            took = time.monotonic() - (t1 or 0)
            ctx.check(f"the Studio row matches within 1 s of the bridge (the warm snapshot dropped), took {took:.2f}s, got {row and row.get('cost_usd')}",
                      bool(row) and took <= 1.0 and row.get("tokens_in") == 1000 and row.get("tokens_out") == 50)
            m = _main(row or {})
            ctx.check(f"the main agent's row carries its meter's tokens, got {m.get('tokens_in')!r} / {m.get('tokens_out')!r}",
                      m.get("tokens_in") == 1000 and m.get("tokens_out") == 50 and m.get("turns") == 1)
            ctx.check("the second model call is in flight", wait_for(lambda: seen2, 10))
            g2.set()
            t2, me2 = feed.next(_own(sid, "message_end"))
            d2 = (me2 or {}).get("data") or {}
            _, st_end = feed.next(lambda f: _own(sid, "status")(f) and (f.get("data") or {}).get("phase") == "idle")
            _, done = feed.next(_own(sid, "turn_done"))
            st2 = client.call("status")["result"]
            ctx.check(f"message_end 2: the totals rose by call 2, got {[d2.get(k) for k in FIGS]}",
                      abs((d2.get("cost_usd") or 0) - 0.0033) < 1e-9 and [d2.get(k) for k in FIGS[1:]] == [2500, 130] and (me2 or {}).get("turn") == 1)
            ctx.check(f"the turn's end: status and the terminal agree, got {(st_end or {}).get('data', {}).get('cost_usd')} {[st2.get(k) for k in FIGS]}",
                      done is not None and (st_end or {}).get("data", {}).get("cost_usd") == d2.get("cost_usd")
                      and [st2.get(k) for k in FIGS] == [d2.get(k) for k in FIGS] and st2.get("turn") == 1)
            row2 = wait_for(lambda: (lambda r: r if r.get("cost_usd") == d2.get("cost_usd") else None)(_row(sid)), 1.0)
            ctx.check(f"the Studio row follows again within 1 s, got {row2 and [row2.get('cost_usd'), row2.get('tokens_in'), row2.get('turns')]}",
                      bool(row2) and row2.get("tokens_in") == 2500 and row2.get("turns") == 1 and _main(row2).get("tokens_in") == 2500)
        finally:
            g1.set()
            g2.set()
            bridge.close()
            local_view.CACHE_S = keep
            local_view.forget()


@test
def test_only_a_local_session_drops_the_snapshot_and_a_read_during_forget_is_not_cached(ctx: Ctx):
    from halo_harness.fleet import local_view
    from halo_harness.studio.events import EventBridge
    bridge = EventBridge(list_live=lambda: [])
    real = local_view.sessions
    try:
        bridge._attached["s-local"] = {"session_id": "s-local"}
        for kind, sid, gone in (("message_end", "s-member", False), ("text_chunk", "s-local", False), ("message_end", "s-local", True),
                                ("status", "s-local", True), ("turn_done", "s-local", True)):
            local_view._cache["local"] = (time.monotonic(), {"sessions": []})
            bridge.publish({"session_id": sid, "event": kind, "data": {}, "turn": 1, "agent_id": None, "ts": time.time()})
            ctx.check(f"{kind} of {sid}: the snapshot {'dropped' if gone else 'kept'}", ("local" not in local_view._cache) == gone)
        local_view.forget()

        def moving(list_live=None):
            local_view.forget()  # an event lands while the sessions are read
            return []
        local_view.sessions = moving
        local_view.snapshot()
        ctx.check("a snapshot read while forget() ran is not cached", "local" not in local_view._cache)
    finally:
        local_view.sessions = real
        local_view.forget()
        bridge.close()


@test
def test_a_quiet_change_goes_out_when_the_window_ends(ctx: Ctx):
    from types import SimpleNamespace
    from halo_harness.agent.agent_registry import QUIET_S, AgentTree
    root = SimpleNamespace(agent_id=None, model_ref=None, log=None)
    tree = AgentTree(root)
    got: list = []
    tree.add_listener(lambda kind, aid, row: got.append((time.monotonic(), kind, row.get("last_text"), row.get("cost_usd"))))
    tree.started("main", root, "hello")
    t0 = time.monotonic()
    for text in ("a", "b", "c"):
        tree.observe("main", SimpleNamespace(kind="text_delta", data={"text": text}))
    ctx.check(f"inside the window nothing more goes out at once, got {len(got)}", len(got) == 1)
    ctx.check("the held text goes out when the window ends", wait_for(lambda: len(got) >= 2, QUIET_S + 1.0))
    at, kind, text, _ = got[-1] if len(got) >= 2 else (0, "", "", None)
    ctx.check(f"once, with the whole text, at about {QUIET_S}s, got {text!r} at {at - t0:.2f}s",
              kind == "agent_state" and text == "abc" and QUIET_S - 0.1 <= at - t0 <= QUIET_S + 0.6)
    tree.observe("main", SimpleNamespace(kind="message_end", data={"cost_usd": 0.01, "total_input_tokens": 120, "total_output_tokens": 9}))
    row = tree.row("main") or {}
    ctx.check(f"message_end goes out at once with the meter's tokens, got {row.get('tokens_in')} / {row.get('tokens_out')}",
              len(got) == 3 and row.get("tokens_in") == 120 and row.get("tokens_out") == 9 and row.get("turns") == 1)
    time.sleep(QUIET_S + 0.3)
    ctx.check(f"nothing was held, nothing more goes out, got {len(got)}", len(got) == 3)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
