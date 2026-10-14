"""tests.test_fleet_studio -- Halo 3.0.5.0 "Fleet" round R1, the surfaces:
Studio's routes (`GET sessions` rows carry harness / project / kind / parent
/ agents and never an endpoint or token; `GET sessions/<sid>/agents`, `.../
agents/<aid>/tail`, `POST .../agents/<aid>/command`, the session commands
shutdown / pause / resume; a private-marked row is never listed), the
EventBridge passing the new frames through with `harness`, the
`halo remote agents | steer | stop` verbs and `/agents live`, all over a
live control socket (the remote tests' fake session behind the real
Controller, opened through `runtime.start_for_controller`).
"""
from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.fleet_rig import FleetRig, wait_for
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()


def _live(rig):
    from halo_harness.controller import Controller
    from halo_harness.remote import runtime
    from tests.helpers.fake_remote_session import FakeRegistry, FakeSession
    c = Controller(session=FakeSession(), cwd=rig.cwd, registry=FakeRegistry()).start()
    rig.controllers.append(c)
    return c, runtime.start_for_controller(c)


def _req(rig, method: str, path: str, body=None, query=None):
    from halo_harness.studio.api import Request
    from halo_harness.studio.sessions_api import dispatch_sessions
    return dispatch_sessions(Request(method=method, path=path, query=query or {}, body=body or {}, cwd=rig.cwd,
                                     state_dir=rig.cwd))


@test
def test_studio_sessions_rows_and_the_agent_routes(ctx: Ctx):
    with FleetRig() as rig:
        controller, act = _live(rig)
        sid = act.session_id
        status, rows = _req(rig, "GET", "sessions")
        row = next((r for r in rows if r["session_id"] == sid), None) if status == 200 else None
        ctx.check(f"the row carries the Fleet fields, got {row}", row is not None and row["kind"] == "tui"
                  and row["harness"]["id"] and "project" in row and row["parent"] is None and row["agents"] == 0
                  and "endpoint" not in row and "token" not in row)
        status, body = _req(rig, "GET", f"sessions/{sid}/agents")
        ctx.check(f"GET agents: the tree, main first, got {status}", status == 200 and body["agents"][0]["agent_id"] == "main")
        status, body = _req(rig, "GET", f"sessions/{sid}/agents/main/tail", query={"n": "5"})
        ctx.check(f"GET tail answers, got {status} {body}", status == 200 and body["agent_id"] == "main" and "events" in body)
        ctx.check("a bad n is a 422", _req(rig, "GET", f"sessions/{sid}/agents/main/tail", query={"n": "lots"})[0] == 422)
        status, body = _req(rig, "POST", f"sessions/{sid}/agents/main/command", {"cmd": "steer", "text": "hello there"})
        ctx.check(f"steering the main agent from Studio is today's steer, got {status} {body}",
                  status == 200 and body["ok"] and body["result"]["agent_id"] == "main")
        ctx.check("the turn it started ran", wait_for(lambda: controller.session.turn_count >= 1 and not controller.session.busy))
        said = [n for n in controller.session.log.nodes() if n.get("type") == "user"]
        ctx.check("with Studio's origin on the note", said and said[-1]["content"][0]["text"].startswith("[steer from ")
                  and " via Studio] hello there" in said[-1]["content"][0]["text"])
        status, body = _req(rig, "POST", f"sessions/{sid}/agents/nobody/command", {"cmd": "stop"})
        ctx.check(f"an unknown agent is the socket's error (502), got {status} {body}", status == 502 and "no agent" in body["error"])
        ctx.check("an unknown agent cmd is a 422", _req(rig, "POST", f"sessions/{sid}/agents/main/command", {"cmd": "explode"})[0] == 422)
        ctx.check("a steer without text is a 422", _req(rig, "POST", f"sessions/{sid}/agents/main/command", {"cmd": "steer"})[0] == 422)
        status, body = _req(rig, "POST", f"sessions/{sid}/command", {"cmd": "pause"})
        ctx.check(f"POST sessions/<sid>/command pause holds the whole session, got {body}", status == 200
                  and body["result"] == {"paused": "session"})
        status, body = _req(rig, "POST", f"sessions/{sid}/command", {"cmd": "resume"})
        ctx.check("resume", status == 200 and body["result"]["was_paused"] is True)
        ctx.check("an unknown session is a 404", _req(rig, "GET", "sessions/nobody/agents")[0] == 404)
        meta = [n["fleet"] for n in controller.session.log.nodes() if n.get("type") == "meta" and n.get("fleet")]
        from halo_harness.remote.fleet_identity import fleet_name
        ctx.check("Studio's commands carry by = fleet.name and via = Studio",
                  meta and all(m["by"] == fleet_name() and m["via"] == "Studio" for m in meta))
        from halo_harness.remote import registry
        registry.register({**registry.make_entry(session_id="hiddensession1", cwd=rig.cwd, endpoint=act.endpoint,
                                                token=act.server.token), "private": True})
        ctx.check("a row marked private is never listed",
                  all(r["session_id"] != "hiddensession1" for r in _req(rig, "GET", "sessions")[1]))
        status, body = _req(rig, "POST", f"sessions/{sid}/command", {"cmd": "shutdown", "reason": "test over"})
        ctx.check("shutdown is a session command", status == 200 and body["result"] == {"shutdown": True})
        ctx.check("and the session goes", wait_for(lambda: controller.quit_called, 10))


@test
def test_event_bridge_passes_the_new_frames_with_the_harness(ctx: Ctx):
    from halo_harness.studio.events import DEFAULT_KINDS, EventBridge
    ctx.check("the bridge asks for the Fleet kinds", {"agent_state", "agent_event", "fleet"} <= set(DEFAULT_KINDS))
    ui = (Path(__file__).resolve().parent.parent / "halo_harness" / "studio" / "ui" / "src" / "lib" / "events.ts").read_text("utf-8")
    ctx.check("events.ts KNOWN_KINDS knows them", all(f'"{k}"' in ui for k in ("agent_state", "agent_event", "fleet")))
    with FleetRig() as rig:
        controller, act = _live(rig)
        bridge = EventBridge(poll_s=0.2)
        q = bridge.subscribe("all")
        try:
            got = []
            ok = wait_for(lambda: (got.append(q.get(0.1)) or any(f and f.get("event") == "fleet" for f in got)), 10)
            frame = next((f for f in got if f and f.get("event") == "fleet"), {})
            ctx.check(f"the session's fleet hello reaches the browser feed with its harness, got {frame}",
                      bool(ok) and frame.get("session_id") == act.session_id
                      and frame.get("harness") == act.entry["harness"]["id"])
        finally:
            bridge.close()


@test
def test_cli_verbs_and_agents_live(ctx: Ctx):
    from halo_harness.cli import main
    from halo_harness.commands.builtins import HeadlessFacade, _cmd_agents
    with FleetRig() as rig:
        controller, act = _live(rig)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = main(["remote", "agents", act.session_id[:10]])
        ctx.check(f"halo remote agents lists the tree, got {buf.getvalue()!r}", rc == 0 and "main" in buf.getvalue())
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            rc = main(["remote", "steer", act.session_id[:10], "--agent", "nobody", "look", "here"])
        ctx.check(f"steering an unknown agent says why (exit 1), got {err.getvalue()!r}", rc == 1 and "no agent" in err.getvalue())
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            rc = main(["remote", "stop", "zzzz-no-such", "--agent", "x"])
        ctx.check("an unknown session is exit 1", rc == 1)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = main(["remote", "stop", act.session_id[:10], "--agent", "main", "--json"])
        ctx.check(f"stop --agent main interrupts the turn, got {buf.getvalue()!r}", rc == 0 and '"interrupted": true' in buf.getvalue())
        out = _cmd_agents("live", HeadlessFacade(cwd=rig.cwd, session=controller.session))
        ctx.check(f"/agents live lists this session's own tree, got {out!r}", out.startswith("Live agents (1)") and "main" in out)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
