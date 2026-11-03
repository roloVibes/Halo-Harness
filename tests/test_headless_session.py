"""tests.test_headless_session -- Halo 3.3.11.0 R2, a session with no terminal (`halo --headless --session-for
studio`, halo_harness/headless_session.py): a real child under a scratch home over the fake upstream
(tests/helpers/headless_rig.py); no model call, every child ended by the teardown and checked gone.

1. its registry row says `kind: headless` and `parent: studio:<pid>`; its status says the same;
2. a `submit` through the socket runs a turn; the reply is in its tail and in the session log on disk;
3. an ask parks: the Write call waits on a permission card, the status lists it under `parked`; an `answer`
   through the socket releases it and the turn ends;
4. `shutdown` ends the child (exit 0) and its registry row goes;
5. the TUI's builder (`tui/bootstrap.build_controller`, what `halo --resume <id>` runs) opens its log;
6. `/quit` through the handle ends it (in-process, the scripted session) and the slash never reaches the registry.
Run: python -m tests.test_headless_session
"""
from __future__ import annotations

import os
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


@test
def test_a_session_with_no_terminal_end_to_end(ctx: Ctx):
    from tests.helpers.fleet_rig import wait_for
    from tests.helpers.headless_rig import ASK_TEXT, MODEL, REPLY, HeadlessRig
    with HeadlessRig() as rig:
        proc = rig.start()
        entry = rig.entry()
        ctx.check(f"the child registered, got {entry!r}\n{rig.child_log()}", entry is not None)
        if entry is None:
            return
        ctx.check(f"kind headless, parent studio:<pid>, got {entry.get('kind')} {entry.get('parent')}",
                  entry.get("kind") == "headless" and str(entry.get("parent") or "").startswith("studio:")
                  and str(entry.get("parent")).split(":", 1)[1].isdigit())
        sid = entry["session_id"]
        c = rig.client(entry)
        st = c.call("status")["result"]
        ctx.check(f"the status says headless, takes turns, nothing parked, got {st.get('kind')} {st.get('parked')}",
                  st.get("kind") == "headless" and st.get("accepts_turns") is True and st.get("parked") == [])
        c.call("subscribe")
        r = c.call("submit", text="hello from nowhere", when_busy="refuse")
        ctx.check(f"submit took the turn, got {r!r}", r.get("ok") is True)
        done = c.wait_event("turn_done", 40)
        ctx.check("the turn ran to its end", done is not None)
        ctx.check("the reply is in the tail", REPLY in c.call("tail", n=4)["result"]["markdown"])
        log = wait_for(lambda: REPLY in rig.log_text(sid) and rig.log_text(sid), 10)
        ctx.check("the session log on disk holds the turn", bool(log) and "hello from nowhere" in log)

        rig.idle(c)
        c.call("submit", text=f"{ASK_TEXT} for a folder", when_busy="refuse")
        ask = c.wait_event("permission_request", 40)
        ctx.check(f"the Write call asks, got {ask!r}", ask is not None and ask["data"].get("name") == "Write")
        rid = (ask or {}).get("data", {}).get("id")
        parked = wait_for(lambda: c.call("status")["result"].get("parked"), 10) or []
        ctx.check(f"the ask is parked in the status, got {parked}",
                  len(parked) == 1 and parked[0]["id"] == rid and parked[0]["kind"] == "permission"
                  and isinstance(parked[0]["since"], float))
        ctx.check("the status says waiting on it", rid in (c.call("status")["result"]["pending"]["permission"] or []))
        a = c.call("answer", kind="permission", request_id=rid, action="allow")
        ctx.check(f"the answer through the socket released it, got {a!r}", a.get("ok") is True)
        ctx.check("the turn ended after the tool ran", c.wait_event("turn_done", 40) is not None)
        ctx.check("the tool ran in the project", wait_for(lambda: (rig.proj / "headless-made.txt").is_file(), 10) is True)
        ctx.check("nothing parked after the answer", wait_for(lambda: c.call("status")["result"].get("parked") == [], 10) is True)

        rig.idle(c)
        s = c.call("shutdown", by="test", via="test", reason="the end")
        ctx.check(f"shutdown taken, got {s!r}", s.get("ok") is True)
        try:
            code = proc.wait(40)
        except Exception:
            code = None
        ctx.check(f"the child ended with 0, got {code}\n{rig.child_log()}", code == 0)
        ctx.check("its registry row is gone", wait_for(lambda: not any(x.get("session_id") == sid for x in rig.rows()), 10) is True)

        saved = {k: os.environ.get(k) for k in ("BRIDGE_OPENROUTER_BASE_URL", "OPENROUTER_API_KEY")}
        os.environ.update(BRIDGE_OPENROUTER_BASE_URL=rig.mock.base_url, OPENROUTER_API_KEY="test-key")
        try:
            from halo_harness.tui.bootstrap import build_controller
            controller, _r, _f = build_controller(SimpleNamespace(cwd=str(rig.proj), resume=sid, model=MODEL))
            users = [b.get("text") for n in controller.session.log.nodes() if n.get("type") == "user"
                     for b in n.get("content") or [] if isinstance(b, dict) and b.get("type") == "text"]
            ctx.check(f"--resume <id> opens its log, got {controller.session.log.session_id} {users[:2]}",
                      controller.session.log.session_id == sid and "hello from nowhere" in users)
            for fn in (lambda: controller.mcp_manager and controller.mcp_manager.close_all(), controller.session.close_runtimes):
                try:
                    fn()
                except Exception:
                    pass
        finally:
            for k, v in saved.items():
                os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
    ctx.check(f"no headless child survives, got {rig.survivors()}", rig.survivors() == [])


@test
def test_quit_through_the_handle_ends_it(ctx: Ctx):
    from tests.helpers.remote_rig import Rig
    from halo_harness.headless_session import HeadlessHandle
    with Rig(serve=False) as rig:
        done = threading.Event()
        h = HeadlessHandle(rig.controller, done)
        ctx.check("kind is headless", h.kind == "headless")
        out = h.run_slash("quit")
        ctx.check(f"/quit ends it, got {out!r}", done.is_set() and "Ending this session" in out)
        done.clear()
        ctx.check("/exit too", "Ending" in h.run_slash("/exit") and done.is_set())
        ctx.check("another slash runs as in the TUI", h.run_slash("cost", "x") == "ran /cost x")
        h._close_after_shutdown("shut down")
        ctx.check("shutdown sets the same end", done.is_set())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
