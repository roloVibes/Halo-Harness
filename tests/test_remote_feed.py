"""tests.test_remote_feed -- Halo 2.0.9 round 2: the control socket's event
feed and shutdown behaviour: a permission_request reaches a subscriber and
`answer` resolves it, "always" writes the local rule, the TUI's own queue
still receives every event (the feed is a tee), a stalled subscriber is
dropped without stalling the session, and the socket / registry entry go
away on quit. Same fixture as test_remote_control_socket.py."""
from __future__ import annotations

import os
import queue
import socket
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.remote_rig import Rig
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()


def _drain_kinds(q) -> list:
    out = []
    while True:
        try:
            item = q.get_nowait()
        except queue.Empty:
            return out
        if item is not None:
            out.append(item.kind)


@test
def test_feed_delivers_permission_request_and_answer_resolves_it(ctx: Ctx):
    with Rig() as rig:
        c = rig.client()
        c.call("subscribe")
        c.call("submit", text="please ask first")
        ev = c.wait_event("permission_request", 5)
        ctx.check("permission_request frame arrived", ev is not None and ev["data"]["id"] == "perm_1")
        ctx.check("payload carried through as-is", ev["data"]["suggested_rule"] == "Bash(echo:*)"
                  and ev["data"]["name"] == "Bash")
        ctx.check("status lists the pending card", "perm_1" in c.call("status")["result"]["pending"]["permission"])
        r = c.call("answer", kind="permission", request_id="perm_1", action="allow", scope="session")
        ctx.check("answer resolves the waiter", r["ok"] and r["result"]["resolved"] is True)
        frames = []
        while True:
            ev = c.next_event(5)
            if ev is None:
                break
            frames.append(ev)
            if ev["event"] == "turn_done":
                break
        ctx.check("turn finished after the answer", bool(frames) and frames[-1]["event"] == "turn_done")
        d = rig.session.permission_decisions["perm_1"]
        ctx.check("Session saw an allow with the suggested rule (session scope)",
                  d.action == "allow" and d.rule == "Bash(echo:*)")
        ctx.check("a second answer finds nothing pending",
                  c.call("answer", kind="permission", request_id="perm_1", action="allow")["ok"] is False)
        kinds = [e["event"] for e in frames]
        chunks = [e["data"]["text"] for e in frames if e["event"] == "text_chunk"]
        ctx.check("one coalesced text_chunk, never raw text_delta",
                  "text_delta" not in kinds and chunks == ["hello from the fake session"])
        ctx.check("text is flushed before message_end (order kept)",
                  kinds.index("text_chunk") < kinds.index("message_end") < kinds.index("turn_done"))


@test
def test_question_plan_and_approval_answers(ctx: Ctx):
    with Rig() as rig:
        c = rig.client()
        c.call("subscribe")
        cases = (("ask-question", "question", "q_1", {"answer": "blue"}, ("answer", "blue")),
                 ("ask-plan", "plan_review", "plan_1", {"approved": True, "feedback": "go", "mode_after": "auto"},
                  ("decision", {"approved": True, "feedback": "go", "mode_after": "auto"})),
                 ("ask-approval", "approval_request", "appr_1", {"action": "edit", "instruction": "tighter"},
                  ("decision", {"action": "edit", "instruction": "tighter"})))
        for text, ev_kind, rid, fields, (slot_key, want) in cases:
            c.call("submit", text=text)
            ev = c.wait_event(ev_kind, 5)
            ctx.check(f"{ev_kind} frame arrived", ev is not None and ev["data"]["id"] == rid)
            kind = {"question": "question", "plan_review": "plan", "approval_request": "approval"}[ev_kind]
            r = c.call("answer", kind=kind, request_id=rid, **fields)
            ctx.check(f"{kind} answer resolved", r["ok"] and r["result"]["resolved"])
            c.wait_event("turn_done", 5)
            ctx.check(f"{kind} answer reached the session verbatim", rig.session.answers[rid].get(slot_key) == want)


@test
def test_always_scope_writes_the_local_rule(ctx: Ctx):
    with Rig() as rig:
        c = rig.client()
        c.call("subscribe")
        c.call("submit", text="ask me")
        c.wait_event("permission_request", 5)
        r = c.call("answer", kind="permission", request_id="perm_1", action="allow", scope="always")
        ctx.check("answered", r["ok"])
        c.wait_event("turn_done", 5)
        local = rig.cwd / ".claude" / "settings.local.json"
        ctx.check("always wrote .claude/settings.local.json", local.exists() and "Bash(echo:*)" in local.read_text("utf-8"))


@test
def test_tee_leaves_the_tui_queue_whole(ctx: Ctx):
    """The TUI drains Controller.events as its single consumer; the feed is a tee."""
    with Rig(serve=False) as base:
        base.controller.submit("plain")
        base.wait_idle()
        baseline = _drain_kinds(base.controller.events)
    with Rig() as rig:
        c = rig.client()
        c.call("subscribe")
        c.call("submit", text="plain")
        rig.wait_idle()
        c.wait_event("turn_done", 5)
        seen = [k for k in _drain_kinds(rig.controller.events) if k != "system_note"]
    base_core = [k for k in baseline if k != "status"]
    ctx.check("same event kinds reach the TUI queue with the socket on",
              [k for k in seen if k != "status"] == base_core)
    ctx.check("all five raw text_deltas still reach the TUI", seen.count("text_delta") == 5)


@test
def test_slow_subscriber_dropped_without_stalling(ctx: Ctx):
    import threading
    with Rig(sndbuf=2048) as rig:
        slow = rig.client()
        slow.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 2048)
        slow.call("subscribe")  # ... and never reads again
        fast = rig.client()
        fast.call("subscribe")
        got = []
        done = threading.Event()

        def _reader():
            while not done.is_set():
                try:
                    ev = fast.next_event(0.3)
                except (ConnectionError, OSError):
                    return
                if ev is not None:
                    got.append(ev)
                    if ev["data"].get("marker") == "last":
                        return
        t = threading.Thread(target=_reader, daemon=True)
        t.start()
        from halo_harness import events
        t0 = time.monotonic()
        blob = "x" * 4000
        for i in range(900):
            rig.controller.events.put(events.Event("notification", {"text": blob, "level": "info", "i": i}))
            time.sleep(0.001)
        rig.controller.events.put(events.Event("notification", {"text": "end", "level": "info", "marker": "last"}))
        ctx.check("publishing 900 events never stalled on the stuck client", time.monotonic() - t0 < 20)
        t.join(10)
        done.set()
        ctx.check("the well-behaved subscriber got the last event", bool(got) and got[-1]["data"].get("marker") == "last")
        time.sleep(0.5)
        ctx.check("the stuck subscriber was dropped", rig.handle.hub.subscriber_count == 1)
        ctx.check("other clients still served", rig.client().call("ping")["ok"])


@test
def test_endpoint_disappears_on_quit_and_registry_entry_goes(ctx: Ctx):
    from halo_harness.remote import client as rclient, registry, runtime
    from halo_harness.theme import set_config_value
    with Rig(serve=False) as rig:
        ctx.check("remote.enabled defaults to false: nothing opened", runtime.start_for_controller(rig.controller) is None
                  and runtime.active() is None)
        ctx.check("/remote says off", runtime.status_line().startswith("control socket: off"))
        set_config_value("remote.enabled", True)
        act = runtime.start_for_controller(rig.controller)
        ctx.check("enabled: socket opened", act is not None and runtime.active() is act)
        endpoint = act.endpoint
        ctx.check("endpoint accepts a connection", rclient.probe(endpoint))
        ctx.check("registered", registry.endpoint_for(rig.session.log.session_id) == endpoint)
        ctx.check("/remote says on + the endpoint", runtime.status_line().startswith(f"control socket: on {endpoint}"))
        rig.controller.quit()
        ctx.check("runtime cleared", runtime.active() is None)
        ctx.check("endpoint refuses after quit", not rclient.probe(endpoint))
        ctx.check("registry entry gone after quit", registry.endpoint_for(rig.session.log.session_id) is None)
        if os.name != "nt":
            ctx.check("socket file gone after quit", not Path(endpoint[5:]).exists())


@test
def test_listener_never_non_loopback(ctx: Ctx):
    src = (Path(__file__).resolve().parent.parent / "halo_harness" / "remote" / "control_socket.py").read_text("utf-8")
    ctx.check("only the loopback address is ever bound",
              '"0.0.0.0"' not in src and "bind((LOOPBACK, 0))" in src and 'LOOPBACK = "127.0.0.1"' in src)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
