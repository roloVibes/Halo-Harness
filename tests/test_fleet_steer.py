"""tests.test_fleet_steer -- Halo 3.0.5.0 "Fleet" round R1, the two steer
modes in detail over a REAL session: a `redirect` leaves the rest of the
child's current tool round unrun ("not run: redirected by ...") and its
next model call reads the new task; a steer to a finished agent, a steer
with an unknown mode and a steer to a background job are refused, and a
background job is a leaf under main that agent_stop kills.
"""
from __future__ import annotations

import json
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.fleet_rig import FleetRig, agent_call, gated, recorded, text_step, tool_step, wait_for
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()
BY = {"by": "tester"}


@test
def test_redirect_cuts_the_round_and_the_next_call_reads_the_new_task(ctx: Ctx):
    gate = threading.Event()
    seen: list = []
    with FleetRig() as rig:
        try:
            m_d = rig.script("fleet-d", [gated(gate, tool_step(("Glob", {"pattern": "*.md"}, "call_d1"),
                                                              ("Glob", {"pattern": "*.txt"}, "call_d2")), seen),
                                         recorded(text_step("D done"), seen)])
            m_main = rig.script("fleet-main2", [tool_step(agent_call("d", "D: list everything", m_d)),
                                                text_step("main done")])
            session = rig.session(m_main)
            controller = rig.controller(session)
            from halo_harness.remote import runtime
            c = rig.client(runtime.start_for_controller(controller))
            controller.submit("go")
            row = wait_for(lambda: next((r for r in c.call("agents")["result"]["agents"] if r["kind"] == "subagent"), None))
            did = row["agent_id"]
            ctx.check("the child's first model call is in flight", wait_for(lambda: len(seen) == 1, 10))
            r = c.call("agent_steer", agent_id=did, text="only the markdown files", mode="redirect", **BY)
            ctx.check(f"redirect accepted, got {r}", r["ok"] and r["result"]["mode"] == "redirect")
            ctx.check("bad mode refused", not c.call("agent_steer", agent_id=did, text="x", mode="shout", **BY)["ok"])
            gate.set()
            ctx.check("the child finishes", wait_for(lambda: next(x for x in c.call("agents")["result"]["agents"]
                                                                  if x["agent_id"] == did)["state"] == "done", 15))
            ctx.check("the session's turn ends", wait_for(lambda: not session.busy, 15))
            tool_msgs = [m for m in (seen[1] if len(seen) > 1 else {}).get("messages") or [] if m.get("role") == "tool"]
            ctx.check(f"both calls of the round were left unrun with the redirect, got {tool_msgs}",
                      len(tool_msgs) == 2 and all("not run: redirected by tester from Studio" in json.dumps(m)
                                                  for m in tool_msgs))
            ctx.check("the next model call reads the new task",
                      "Redirect: the rest of your current task is replaced. Your task is now: only the markdown files"
                      in json.dumps(seen[1]["messages"][-1]))
            r = c.call("agent_steer", agent_id=did, text="more", **BY)
            ctx.check(f"a finished agent takes no steer, got {r}", not r["ok"] and "has finished" in r["error"])
            r = c.call("agent_steer", agent_id="main", text=" ", **BY)
            ctx.check("an empty steer is refused", not r["ok"] and "empty" in r["error"])
        finally:
            gate.set()


@test
def test_jobs(ctx: Ctx):
    from halo_harness.agent.agent_registry import tree_for
    from halo_harness.controller import Controller
    from halo_harness.remote import runtime
    from tests.helpers.fake_remote_session import FakeRegistry, FakeSession
    with FleetRig() as rig:
        session = FakeSession()
        controller = Controller(session=session, cwd=rig.cwd, registry=FakeRegistry()).start()
        rig.controllers.append(controller)
        c = rig.client(runtime.start_for_controller(controller))
        tree_for(session)
        jobs = SimpleNamespace(list_jobs=lambda: [{"id": "j1", "description": "build", "command": "make all",
                                                   "status": "running", "started_at": 1.0}],
                               kill=lambda job_id: (True, f"Killed {job_id}"), kill_all=lambda: None)
        session.job_registry = jobs
        rows = {r["agent_id"]: r for r in c.call("agents")["result"]["agents"]}
        ctx.check(f"a background Bash job is a leaf under main, got {rows.get('job:j1')}",
                  rows.get("job:j1", {}).get("kind") == "job" and rows["job:j1"]["parent"] == "main"
                  and rows["job:j1"]["state"] == "running")
        ctx.check("a job takes no steer", not c.call("agent_steer", agent_id="job:j1", text="hi", **BY)["ok"])
        r = c.call("agent_stop", agent_id="job:j1", **BY)
        ctx.check(f"agent_stop on a job kills it, got {r}", r["ok"] and r["result"]["stopped"] is True)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
