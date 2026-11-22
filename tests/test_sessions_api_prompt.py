"""tests.test_sessions_api_prompt -- Halo 3.3.11.0 R1: Studio's routes for the Prompt panel
(studio/sessions_api.py, studio/sessions_prompt_api.py) over a live control socket (the remote tests' fake
session behind the real Controller, opened through `runtime.start_for_controller`).

1. GET sessions/<sid>/slash: the builtins table (name, group, help, args) and the project's own commands;
2. a slash command's output comes back as its lines (`slash` joins COMMANDS); `tail` too;
3. `submit` from Studio carries origin {via: studio, by}; with `when_busy: refuse` while a turn runs it answers
   200 {busy: true, line} and the receipt is failed(busy); `queue` holds the turn (200) and a second `queue`
   answers 409 with the line; a bad when_busy is a 422;
4. GET sessions/<sid>/receipts lists the rows.
No model is called.
Run: python -m tests.test_sessions_api_prompt
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.session_rig import SessionRig, wait_for  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _live(rig):
    from halo_harness.controller import Controller
    from halo_harness.remote import runtime
    from tests.helpers.fake_remote_session import FakeRegistry, FakeSession
    session = FakeSession()
    session.cwd = rig.cwd
    c = Controller(session=session, cwd=rig.cwd, registry=FakeRegistry()).start()
    rig.controllers.append(c)
    return session, c, runtime.start_for_controller(c)


def _req(rig, method: str, path: str, body=None):
    from halo_harness.studio.api import Request
    from halo_harness.studio.sessions_api import dispatch_sessions
    return dispatch_sessions(Request(owner=True, method=method, path=path, query={}, body=body or {}, cwd=rig.cwd, state_dir=rig.cwd))


@test
def test_the_slash_list_and_a_slash_commands_lines(ctx: Ctx):
    with SessionRig() as rig:
        (rig.cwd / ".claude" / "commands").mkdir(parents=True)
        (rig.cwd / ".claude" / "commands" / "pp-hello.md").write_text("---\ndescription: say hello to the panel\n"
                                                                      "argument-hint: <name>\n---\nSay hello to $ARGUMENTS\n", encoding="utf-8")
        session, controller, act = _live(rig)
        sid = act.session_id
        status, rows = _req(rig, "GET", f"sessions/{sid}/slash")
        names = {r["name"]: r for r in rows} if status == 200 else {}
        ctx.check(f"200 and the builtins, got {status} {len(names)}", status == 200 and {"cost", "help", "model", "effort"} <= set(names))
        ctx.check(f"each row has name, group, help, args, got {names.get('effort')}",
                  set(names.get("effort") or {}) >= {"name", "group", "help", "args"} and names["effort"]["args"] == "[level]")
        ctx.check(f"the project's own command is listed, got {names.get('pp-hello')}",
                  (names.get("pp-hello") or {}).get("help") == "say hello to the panel" and names["pp-hello"]["args"] == "<name>")
        ctx.check("an unknown session is a 404", _req(rig, "GET", "sessions/nobody/slash")[0] == 404)
        status, body = _req(rig, "POST", f"sessions/{sid}/command", {"cmd": "slash", "line": "/cost --all"})
        ctx.check(f"a slash's output comes back as its lines, got {status} {body}", status == 200
                  and body["result"]["output"] == "ran /cost --all" and body["result"]["lines"] == ["ran /cost --all"])
        ctx.check("a slash with nothing to run is a 422", _req(rig, "POST", f"sessions/{sid}/command", {"cmd": "slash", "line": "cost"})[0] == 422)
        status, body = _req(rig, "POST", f"sessions/{sid}/command", {"cmd": "submit", "text": "hello the panel"})
        ctx.check("a turn ran", status == 200 and wait_for(lambda: session.turn_count == 1 and not session.busy, 8))
        status, body = _req(rig, "POST", f"sessions/{sid}/command", {"cmd": "tail", "n": 4})
        ctx.check(f"tail answers its Markdown, got {status}", status == 200 and "hello the panel" in body["result"]["markdown"])


@test
def test_refuse_and_queue_while_busy(ctx: Ctx):
    with SessionRig() as rig:
        session, controller, act = _live(rig)
        sid = act.session_id
        _req(rig, "POST", f"sessions/{sid}/command", {"cmd": "submit", "text": "please ask first"})
        ctx.check("the turn parks on its card", wait_for(lambda: "perm_1" in session._permission_waiters, 8))
        ctx.check("a bad when_busy is a 422", _req(rig, "POST", f"sessions/{sid}/command", {"cmd": "submit", "text": "x", "when_busy": "soon"})[0] == 422)
        status, body = _req(rig, "POST", f"sessions/{sid}/command", {"cmd": "submit", "text": "not yet", "when_busy": "refuse", "client_id": "pp-r1"})
        ctx.check(f"refuse: 200 busy with the line, got {status} {body}", status == 200 and body.get("busy") is True
                  and "queue" in body.get("line", "").lower() and body["receipt"]["state"] == "failed" and body["receipt"]["reason"] == "busy")
        ctx.check("refuse took nothing", session.steered == [])
        status, body = _req(rig, "POST", f"sessions/{sid}/command", {"cmd": "submit", "text": "after this one", "when_busy": "queue"})
        ctx.check(f"queue: 200, held, delivered, got {status} {body}", status == 200 and body["result"].get("queued") is True
                  and body["receipt"]["state"] == "delivered")
        status, body = _req(rig, "POST", f"sessions/{sid}/command", {"cmd": "submit", "text": "and another", "when_busy": "queue"})
        ctx.check(f"a second queue: 409 with the line, got {status} {body}", status == 409 and body.get("held") is True
                  and "already queued" in body.get("error", "") and body["receipt"]["reason"] == "held")
        _req(rig, "POST", f"sessions/{sid}/command", {"cmd": "answer", "kind": "permission", "request_id": "perm_1", "action": "allow"})
        ctx.check("the held turn runs after the first", wait_for(lambda: session.turn_count == 2 and not session.busy, 8))
        rows = _req(rig, "GET", f"sessions/{sid}/receipts")[1]["receipts"]
        kinds = [(r["kind"], r["state"]) for r in rows]
        ctx.check(f"the receipts list every send, got {kinds}", kinds == [("prompt", "replied"), ("prompt", "failed"),
                  ("prompt", "replied"), ("prompt", "failed"), ("answer", "replied")])


@test
def test_halo_studio_session_prompt_names_the_prompt(ctx: Ctx):
    import contextlib
    import io
    from halo_harness.studio.launch import _query
    from halo_harness.studio.session_open import SectionTarget, cli_target
    with SessionRig() as rig:
        session, controller, act = _live(rig)
        sid = act.session_id
        t, note = cli_target(sid[:10], prompt=True)
        ctx.check(f"a prefix finds the session, the Prompt asked for, got {t} {note!r}", t.session == sid and t.prompt and not note)
        ctx.check(f"the URL asks for it, got {t.query()}", t.query() == f"?mode=session&session={sid}&prompt=1")
        ctx.check(f"so does the focus frame, got {t.focus()}", t.focus() == {"edit": "", "mode": "session", "session": sid, "prompt": True})
        ctx.check("the text rides through launch's query", _query("session", t.text) == t.query()
                  and SectionTarget.from_text(t.text) == t and _query("session", sid) == f"?mode=session&session={sid}")
        ctx.check(f"the one-line outcome names the flag, got {t.cli!r}", t.cli == f"halo studio --session {sid} --prompt")
        bare, _ = cli_target("", prompt=True)
        ctx.check("--prompt alone: the newest live session", bare.session == sid and bare.prompt)
        from halo_harness.studio.api import Request
        from halo_harness.studio.focus_api import post_focus
        status, body = post_focus(Request(owner=True, method="POST", path="focus", query={}, body=t.focus(), cwd=rig.cwd, state_dir=rig.cwd))
        ctx.check(f"POST focus keeps prompt, got {status} {body}", status == 200 and body.get("prompt") is True)
        from halo_harness.studio.server import cmd_studio
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.suppress(SystemExit):
            cmd_studio(["--help"])
        ctx.check("`halo studio --help` lists --prompt", "--prompt" in buf.getvalue())


def _bang_rig(rig):
    """3.6.0.12 BS: the live session, a tap on the Controller's events (what Studio's feed reads), a socket client,
    and a permission engine that allows `echo` and asks for anything else (the fake session has none of its own)."""
    from halo_harness.permissions import Decision
    from halo_harness.remote.client import ControlClient
    session, controller, act = _live(rig)
    session.permission_engine.decide = lambda name, inp, tool=None: Decision(
        "allow" if str((inp or {}).get("command", "")).startswith("echo") else "ask", "asks first")
    tapped: list = []
    controller.add_event_tap(tapped.append)
    return session, controller, tapped, ControlClient(act.endpoint, act.server.token, timeout=10.0)


def _pair(tapped) -> tuple:
    return ([e.data.get("id") for e in tapped if e.kind == "tool_use_start"],
            [e.data.get("id") for e in tapped if e.kind == "tool_result"])


@test
def test_a_bang_line_through_the_slash_door_runs_as_in_the_terminal(ctx: Ctx):
    with SessionRig() as rig:
        session, controller, tapped, client = _bang_rig(rig)
        try:
            reply = client.call("slash", line="!echo hi-from-the-door")
            result = reply.get("result") or {}
            ctx.check(f"slash with a ! line answers ran with the output, got {reply}", reply.get("ok") is True
                      and result.get("state") == "ran" and "hi-from-the-door" in str(result.get("output"))
                      and result.get("ran") is True and str(result.get("id", "")).startswith("inline_"))
            ctx.check(f"it started NO turn, got {session.turn_count}", session.turn_count == 0)
            ctx.check("the tap carries one tool_use_start / tool_result pair",
                      wait_for(lambda: _pair(tapped)[1] == [result.get("id")], 5) and _pair(tapped)[0] == [result.get("id")])
            reply = client.call("slash", name="!echo", args="named-door")
            result = reply.get("result") or {}
            ctx.check(f"a `name` that starts with ! takes the same path, got {reply}",
                      result.get("state") == "ran" and "named-door" in str(result.get("output")))
        finally:
            client.close()


@test
def test_a_bang_ask_over_the_socket_runs_after_an_allow(ctx: Ctx):
    with SessionRig() as rig:
        session, controller, tapped, client = _bang_rig(rig)
        try:
            reply = client.call("slash", line="!touch made-by-the-door.txt")
            result = reply.get("result") or {}
            ctx.check(f"an asking ! answers asked, got {reply}", result.get("state") == "asked" and result.get("id"))
            asks = [e.data for e in tapped if e.kind == "permission_request"]
            ctx.check(f"a permission_request is on the tap, got {asks}", len(asks) == 1 and asks[0].get("id") == result.get("id")
                      and asks[0].get("name") == "Bash" and asks[0].get("own") is False)
            ctx.check("nothing ran yet", not (rig.cwd / "made-by-the-door.txt").exists())
            reply = client.call("answer", kind="permission", request_id=result.get("id"), action="allow")
            ctx.check(f"the answer was taken, got {reply}", reply.get("ok") is True)
            ctx.check("the command RAN after the allow", wait_for(lambda: (rig.cwd / "made-by-the-door.txt").exists(), 8))
            ctx.check("its tool rows reach the tap", wait_for(lambda: len(_pair(tapped)[1]) == 1, 5))
            ctx.check(f"no turn, got {session.turn_count}", session.turn_count == 0)
        finally:
            client.close()


@test
def test_a_bang_line_on_a_print_run_says_it_needs_a_session(ctx: Ctx):
    from halo_harness.remote import protocol
    from halo_harness.remote.base import HandleError
    from halo_harness.remote.print_handle import PrintModeHandle
    from tests.helpers.fake_remote_session import FakeSession
    with SessionRig() as rig:
        handle = PrintModeHandle(FakeSession(), rig.cwd)
        said = ""
        try:
            protocol.run_cmd(handle, {"cmd": "slash", "line": "!echo hi"}, None)
        except HandleError as e:
            said = str(e)
        ctx.check(f"the sentence, got {said!r}", said == "a ! command needs a session in the terminal app or one Studio started")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
