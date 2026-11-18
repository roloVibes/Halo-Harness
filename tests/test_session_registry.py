"""tests.test_session_registry -- Halo 3.0.5.0 "Fleet" round R1, the session
half: `shutdown` ends a REAL session after its current tool call (the TUI's
hook gets the line; without one the Controller quits and the registry entry
goes); `--private` / `control.private` register nothing and `/private on|off`
closes and reopens; `control.enabled: false` opens nothing while
`remote.enabled` no longer gates the socket; the registry entry's harness /
project / kind / parent (a stable fleet-id, a git-aware project, the
Orchestra and Paperclip kinds, HALO_SESSION_PARENT); an entry written before
those fields existed still loads; print mode's shutdown ends its input.
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.session_rig import SessionRig, gated, text_step, tool_step, wait_for
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()


def _fake_controller(rig):
    from halo_harness.controller import Controller
    from tests.helpers.fake_remote_session import FakeRegistry, FakeSession
    c = Controller(session=FakeSession(), cwd=rig.cwd, registry=FakeRegistry()).start()
    rig.controllers.append(c)
    return c


@test
def test_shutdown_ends_a_real_session_after_the_current_tool_call(ctx: Ctx):
    gate = threading.Event()
    with SessionRig() as rig:
        try:
            model = rig.script("fleet-shut", [gated(gate, tool_step(("Glob", {"pattern": "*.md"}, "call_s1"))),
                                              text_step("never")])
            session = rig.session(model)
            controller = rig.controller(session)
            said: list = []
            controller.on_control_shutdown = said.append
            from halo_harness.remote import runtime
            act = runtime.start_for_controller(controller)
            c = rig.client(act)
            controller.submit("start")
            ctx.check("the turn is running", wait_for(lambda: session.busy, 10))
            r = c.call("shutdown", reason="done for today", by="tester")
            ctx.check(f"shutdown answers at once, got {r}", r["ok"] and r["result"] == {"shutdown": True})
            gate.set()
            ctx.check("the TUI hook gets the line once the turn is over",
                      wait_for(lambda: said, 15) == ["shut down from Studio: done for today"])
            results = [str(n.get("content")) for n in session.log.nodes() if n.get("type") == "tool_result"]
            ctx.check(f"the pending tool call was left unrun, got {results}",
                      results and "not run: stopped from Studio" in results[0])
            notes = []
            while not controller.events.empty():
                ev = controller.events.get_nowait()
                if ev is not None and ev.kind == "system_note":
                    notes.append(ev.data["text"])
            ctx.check(f"the transcript shows the line, got {notes[-3:]}",
                      any("shut down from Studio: done for today" in t for t in notes))
            meta = [n["control"] for n in session.log.nodes() if n.get("type") == "meta" and n.get("control")]
            ctx.check("the command is recorded in the main transcript with its origin",
                      any(m["cmd"] == "shutdown" and "by" not in m and m["via"] == "Studio" for m in meta))
            plain = _fake_controller(rig)
            act2 = runtime.start_for_controller(plain)
            sid2 = act2.session_id
            rig.client(act2).call("shutdown", reason="bye")
            from halo_harness.remote import registry
            ctx.check("without a TUI hook the Controller quits and leaves the registry",
                      wait_for(lambda: plain.quit_called and registry.entry_for(sid2) is None, 10))
        finally:
            gate.set()


@test
def test_private_and_the_two_switches(ctx: Ctx):
    from halo_harness.commands.builtins import HeadlessFacade, _cmd_private
    from halo_harness.remote import registry, runtime
    from halo_harness.theme import set_config_value
    with SessionRig() as rig:
        ctrl = _fake_controller(rig)
        set_config_value("control.enabled", False)
        ctx.check("control.enabled false: nothing opens", runtime.start_for_controller(ctrl) is None
                  and runtime.start_for_print(ctrl.session, rig.cwd) is None and registry.list_live() == [])
        ctx.check("and /remote says why", "control.enabled is false" in runtime.status_line())
        set_config_value("control.enabled", True)
        os.environ["HALO_PRIVATE"] = "1"  # what `halo --private` sets for its own process
        ctx.check("--private: no socket, no registry entry", runtime.start_for_controller(ctrl) is None
                  and registry.list_live() == [] and runtime.private_chip())
        ctx.check("/private shows the state", _cmd_private("", HeadlessFacade(cwd=rig.cwd)).startswith("Private: on."))
        out = _cmd_private("off", HeadlessFacade(cwd=rig.cwd))
        ctx.check(f"/private off opens it and lists it, got {out!r}", out.startswith("Private: off. The control socket")
                  and registry.entry_for(ctrl.session.log.session_id) is not None and not runtime.private_chip())
        out = _cmd_private("on", HeadlessFacade(cwd=rig.cwd))
        ctx.check(f"/private on closes it again, got {out!r}", out.startswith("Private: on.")
                  and registry.list_live() == [] and runtime.active() is None and runtime.private_chip())
        ctx.check("/private nonsense is a usage line", _cmd_private("maybe", HeadlessFacade(cwd=rig.cwd)).startswith("Usage"))
        runtime._private_flag = None
        set_config_value("control.private", True)
        os.environ.pop("HALO_PRIVATE", None)
        ctx.check("control.private in config: private too", runtime.private() and not runtime.enabled())
        set_config_value("control.private", False)
        runtime._reopeners[:] = []
        ctx.check("remote.enabled false (the Signal switch) and the socket opens",
                  runtime.remote_enabled() is False and runtime.start_for_controller(ctrl) is not None)
        from halo_harness.cli import _build_parser
        ctx.check("halo --private parses", _build_parser().parse_args(["--private"]).private is True)


@test
def test_registry_identity_project_kind_and_parent(ctx: Ctx):
    from halo_harness.config.paths import bridge_home
    from halo_harness.remote import session_identity as FI, registry, runtime
    from halo_harness.theme import set_config_value
    with SessionRig() as rig:
        fid = FI.harness_id()
        ctx.check("a stable per-home harness-id", len(fid) == 16 and FI.harness_id() == fid
                  and (bridge_home() / "harness-id").read_text(encoding="utf-8").strip() == fid)
        ctx.check("harness.name defaults to user@host", "@" in FI.harness_name())
        set_config_value("harness.name", "lab-box")
        h = FI.harness()
        ctx.check(f"the harness block, got {h}", h["name"] == "lab-box" and h["id"] == fid and h["version"]
                  and h["os"] and h["host"] and h["user"])
        repo = rig.cwd / "repo"
        repo.mkdir()
        git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com"]
        for args in (["init", "-q", "-b", "fleet-branch"], ["remote", "add", "origin", "https://example.com/me/myrepo.git"]):
            subprocess.run(git + args, cwd=repo, capture_output=True, check=True)
        (repo / "a.txt").write_text("1\n", encoding="utf-8")
        subprocess.run(git + ["add", "a.txt"], cwd=repo, capture_output=True, check=True)
        subprocess.run(git + ["commit", "-q", "-m", "x"], cwd=repo, capture_output=True, check=True)
        p = FI.project(repo)
        ctx.check(f"project: root, repo from origin, branch, clean, got {p}", Path(p["root"]) == repo.resolve()
                  and p["repo"] == "myrepo" and p["branch"] == "fleet-branch" and p["dirty"] is False)
        (repo / "a.txt").write_text("2\n", encoding="utf-8")
        ctx.check("a change makes it dirty", FI.project(repo, refresh=True)["dirty"] is True)
        ctx.check("outside a repo: the folder, nothing else", FI.project(rig.cwd)["repo"] is None)
        os.environ["HALO_ORCHESTRA_RUN"] = "run1"
        ctx.check("an Orchestra worker's kind", FI.session_kind("print") == "orchestra-worker")
        os.environ.pop("HALO_ORCHESTRA_RUN")
        os.environ["PAPERCLIP_AGENT_ID"] = "ag1"
        ctx.check("a leftover Paperclip variable changes nothing (3.1.4.0)", FI.session_kind("print") == "print")
        os.environ.pop("PAPERCLIP_AGENT_ID")
        ctx.check("otherwise the default", FI.session_kind("print") == "print")
        os.environ["HALO_SESSION_PARENT"] = "parentsession01"
        ctrl = _fake_controller(rig)
        act = runtime.start_for_controller(ctrl)
        row = registry.entry_for(act.session_id)
        ctx.check(f"the entry carries harness, project, kind and parent, got {sorted(row)}",
                  row["harness"]["id"] == fid and row["harness"]["name"] == "lab-box" and row["kind"] == "tui"
                  and row["parent"] == "parentsession01" and row["project"]["root"] == str(rig.cwd))
        ctx.check("FIELDS grew", {"kind", "harness", "project", "parent"} <= set(registry.FIELDS))
        old = {"session_id": "oldsession0001", "cwd": str(rig.cwd), "pid": os.getpid(), "endpoint": act.endpoint,
               "token_env": None, "started": 1.0, "title": "old", "mode": "default"}
        registry.register(old)
        got = next((r for r in registry.list_live() if r["session_id"] == "oldsession0001"), None)
        pub = registry.public_entry(got or {})
        ctx.check(f"an entry from before the new fields still loads, got {pub}", got is not None and pub["kind"] == "tui"
                  and pub["harness"] == {} and pub["project"]["root"] == str(rig.cwd) and pub["parent"] is None
                  and "endpoint" not in pub)


@test
def test_print_mode_shutdown_ends_its_input_and_the_wire_lists_the_commands(ctx: Ctx):
    from halo_harness.headless import _TurnLineQueue
    from halo_harness.remote.print_handle import PrintModeHandle
    from halo_harness.remote.protocol import CMDS
    from tests.helpers.fake_remote_session import FakeSession
    q = _TurnLineQueue()
    q.put({"text": "a later turn", "images": None})
    h = PrintModeHandle(FakeSession(), Path("."), input_queue=q)
    h.control_shutdown("shut down from Studio: bye")
    ctx.check("print mode reads no further turn after a shutdown", q.get() is None)
    ctx.check("the wire's agent commands", {"agents", "agent_tail", "agent_steer", "agent_stop", "pause", "resume",
                                            "shutdown", "agent_follow"} <= set(CMDS))


def _rows():
    from halo_harness.remote import registry
    return {r["session_id"]: r for r in registry._load(registry.registry_path())}


@test
def test_a_session_puts_its_missing_row_back_and_an_ended_one_never_does(ctx: Ctx):
    """3.6.0.4 S3: a session whose row left the file (an older Halo's list_live after one refused probe, or 30 s of
    a paused terminal) was gone from Studio until /clear. It puts its own row back at its next status event (at most
    one file read a second, no thread of its own); a session that has ENDED never writes it back."""
    from halo_harness.events import Event
    from halo_harness.remote import runtime
    from halo_harness.remote import registry
    with SessionRig() as rig:
        clock = [1000.0]
        real_clock = getattr(runtime, "_clock", None)
        runtime._clock = lambda: clock[0]
        try:
            act = runtime.start_for_controller(_fake_controller(rig))
            sid = act.session_id
            first = dict(_rows()[sid])

            def status():
                act.handle.hub.publish(Event("status", {"session_id": act.session_id, "permission_mode": act.mode}))
            registry.unregister(sid)  # what a 3.6.0.3 reader did after one refused probe
            status()
            back = _rows().get(sid)
            ctx.check(f"the row is back after the next status event, got {back and sorted(back)}", back is not None
                      and all(back.get(k) == first.get(k) for k in ("session_id", "pid", "endpoint", "started")))
            registry.unregister(sid)
            clock[0] += 0.5
            status()
            ctx.check("within the same second no second read: still missing", sid not in _rows())
            clock[0] += 1.0
            status()
            ctx.check("a second later it is back", sid in _rows())
            runtime.stop_one(act)
            ctx.check("an ended session's row leaves", sid not in _rows())
            clock[0] += 5.0
            status()
            ctx.check("and an ended session never writes it back", sid not in _rows())
        finally:
            if real_clock is not None:
                runtime._clock = real_clock
            else:
                del runtime._clock


@test
def test_a_session_ending_while_it_looks_for_its_row_never_writes_it_back(ctx: Ctx):
    """3.6.0.4 S3 repair: the race _keep_listed guards. The session ends (stop_one) after its read found the row
    missing and before it registers: the check under `_lock` that it is still in `_actives` stops the write."""
    from halo_harness.events import Event
    from halo_harness.remote import registry, runtime
    with SessionRig() as rig:
        clock = [1000.0]
        real_clock, real_listed = runtime._clock, registry.listed
        runtime._clock = lambda: clock[0]
        try:
            act = runtime.start_for_controller(_fake_controller(rig))
            sid = act.session_id
            registry.unregister(sid)
            seen = []

            def listed_then_ended(session_id):
                seen.append(session_id)
                runtime.stop_one(act)  # the terminal closes right here
                return False
            registry.listed = listed_then_ended
            clock[0] += 5.0
            act.handle.hub.publish(Event("status", {"session_id": sid, "permission_mode": act.mode}))
            ctx.check(f"the session looked for its row, got {seen}", seen == [sid])
            ctx.check("it ended in between", act not in runtime._actives)
            ctx.check("and its row was never written back", sid not in _rows())
        finally:
            registry.listed = real_listed
            runtime._clock = real_clock


@test
def test_a_session_putting_its_row_back_never_holds_up_its_own_end(ctx: Ctx):
    """3.6.0.4 S4-2: _keep_listed registered while it held runtime._lock; register waits for the list's file lock (up
    to 30 s while another Halo holds it), so stop_one on another thread, which needs runtime._lock to take the
    session out, waited behind it and the session's end with it. Here register is held on an event: stop_one must
    return while it is held, and when the register then lands for the ended session, its row leaves again."""
    import threading
    from halo_harness.events import Event
    from halo_harness.remote import registry, runtime
    with SessionRig() as rig:
        clock = [1000.0]
        real_clock, real_register = runtime._clock, registry.register
        runtime._clock = lambda: clock[0]
        entered, release = threading.Event(), threading.Event()
        try:
            act = runtime.start_for_controller(_fake_controller(rig))
            sid = act.session_id
            registry.unregister(sid)

            def held_register(entry):
                entered.set()
                release.wait(30.0)  # the file lock another Halo holds
                real_register(entry)
            registry.register = held_register
            clock[0] += 5.0
            pub = threading.Thread(target=act.handle.hub.publish, daemon=True,
                                   args=(Event("status", {"session_id": sid, "permission_mode": act.mode}),))
            pub.start()
            ctx.check("the session went to put its row back", entered.wait(10.0))
            stopper = threading.Thread(target=runtime.stop_one, args=(act,), daemon=True)
            stopper.start()
            stopper.join(5.0)
            ctx.check("stop_one returned while the register was held", not stopper.is_alive())
            ctx.check("the session ended", act not in runtime._actives)
            release.set()
            pub.join(10.0)
            stopper.join(10.0)
            ctx.check("the status event's thread finished", not pub.is_alive())
            ctx.check("the ended session's row is not in the file", sid not in _rows())
        finally:
            release.set()
            registry.register = real_register
            runtime._clock = real_clock


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
