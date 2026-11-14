"""tests.test_crew_flow_api -- Halo 3.6.0.0 R2: the Workflows tab's routes (studio/crew_flow_api.py), Try it for a
workflow (crew/trial_flow.py, crew/try_flow.py) on the repo's fake provider, and a session's Workflow tool running a
crew workflow by name (crew/flow_door.py):

1. GET crew/workflows (yours tagged with the maps they are on, the starters); POST / PUT / GET / DELETE a workflow;
   a starter is copied, never saved over; a workflow on a map is not deleted (409 names the map); 422 with the lines;
2. the cost band before a run (POST crew/workflow-cost, the form as it stands): low / high from the catalog prices, the
   repeat counted, an Auto agent "unknown until the first run", the agents a step names that do not exist, what it writes;
3. Try it: the band in the record first; a real run in a throwaway worktree, each step's result, the agents that ran,
   the check's rounds (yes on round 2), the copy gone after; an unseen end is an Attention row opening the Workflows tab;
   Stop ends a run whose agent waits on its model (the running step stopped, the next not run);
4. a step naming an agent that does not exist: 422 before any run;
5. the Workflow tool: a crew workflow's name runs on the step runner (each agent spawned as a child by its name), the
   receipt line says so; a square's name still goes to the squares.
Run: python -m tests.test_crew_flow_api
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.crew_rig import CrewRig  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _agent(name: str, model: str) -> dict:
    return {"format": "agent/1", "name": name, "does": f"{name} does its part.", "model": model, "uses": ["read"], "careful": "ask-changes"}


def _wf(name="ship", maker="maker", checker="checker") -> dict:
    return {"format": "workflow/1", "name": name, "for": "Make the change, then check it.", "steps": [
        {"name": "Make", "agents": [maker], "gets": "the task", "hands": "the diff"},
        {"name": "Check", "agents": [checker], "gets": "the diff", "hands": "failures", "repeat": {"until": "the tests pass", "max": 3}}]}


def _save(rig, kind, raw):
    from halo_harness.crew import store
    store.write_text(store.path_for(kind, raw["name"], state_dir=rig.state), store.dump(raw))


def _wait(rig, tid: str, timeout: float = 120) -> dict:
    end, rec = time.time() + timeout, {}
    while time.time() < end:
        rec = rig.api("GET", f"crew/try/{tid}")[1].get("try") or {}
        if rec.get("state") not in ("running", "stopping"):
            return rec
        time.sleep(0.3)
    return rec


@test
def test_the_routes(ctx: Ctx):
    with CrewRig() as rig:
        rig.studio()
        st, r = rig.api("POST", "crew/workflow/ship", {"workflow": _wf()})
        ctx.check(f"a new workflow, got {st} {r.get('error')}", st == 200 and r["path"].endswith("ship.yaml"))
        ctx.check("the same name again: 409", rig.api("POST", "crew/workflow/ship", {"workflow": _wf()})[0] == 409)
        bad = {**_wf(), "steps": [{"name": "x", "agents": ["maker"], "repeat": {"until": "y", "max": 20}}]}
        st, r = rig.api("PUT", "crew/workflow/ship", {"workflow": bad})
        ctx.check(f"422 with the problem line, got {st} {r.get('error')!r}", st == 422 and "repeat" in r["error"])
        ctx.check("a starter is not saved over: 409", rig.api("PUT", "crew/workflow/review", {"workflow": {**_wf(), "name": "review"}})[0] == 409)
        st, r = rig.api("GET", "crew/workflows")
        ctx.check(f"yours, then the starters (code, plan, review, research, media), got {[w['name'] for w in r['workflows']]} "
                  f"{sorted(w['name'] for w in r['starters'])}", [w["name"] for w in r["workflows"]] == ["ship"] and
                  sorted(w["name"] for w in r["starters"]) == ["code", "media", "plan", "research", "review"])
        ctx.check("not on a map yet", r["workflows"][0]["maps"] == [])
        _save(rig, "map", {"format": "map/1", "name": "everyday", "boxes": [{"id": "s", "workflow": "ship"}], "lines": [{"from": "main", "to": "s", "when": "always"}]})
        st, r = rig.api("GET", "crew/workflow/ship")
        ctx.check(f"its record: the map it is on, the agents it names that do not exist, got {st} {r.get('maps')} {r.get('missing')}",
                  st == 200 and r["maps"] == ["everyday"] and r["missing"] == ["maker", "checker"] and r["writable"])
        st, r = rig.api("DELETE", "crew/workflow/ship")
        ctx.check(f"on a map: not deleted, the map named, got {st} {r.get('error')!r}", st == 409 and "everyday" in r["error"])
        (rig.state / "crew" / "maps" / "everyday.yaml").unlink()
        ctx.check("off the map: deleted", rig.api("DELETE", "crew/workflow/ship")[0] == 200 and rig.api("GET", "crew/workflow/ship")[0] == 404)
        ctx.check("without the owner's proof: 403", rig.api("POST", "crew/workflow/x", {"workflow": _wf("x")}, owner=False)[0] == 403)


@test
def test_the_cost_band(ctx: Ctx):
    from halo_harness.crew import flow_cost
    priced = {"maker": {"model": "m1"}, "checker": {"model": "m2"}, "auto-one": {"model": "auto"}}
    import halo_harness.crew.trial as T
    saved = T.estimate
    T.estimate = lambda raw, state_dir=None: {"usd": {"m1": 0.02, "m2": 0.01}.get(raw.get("model")), "line": ""}
    try:
        got = flow_cost.band(_wf(), priced.get)
        ctx.check(f"low: each always step once at half a task; high: each round + its check, got {got}",
                  got["low"] == 0.015 and got["high"] == round(0.02 + 0.01 * 3 + 0.01 * 3, 4) and got["line"] == "about $0.01 to $0.08 a run")
        got = flow_cost.band(_wf(checker="auto-one"), priced.get)
        ctx.check(f"an Auto agent: unknown until the first run, got {got['line']!r}",
                  got["unknown"] == ["auto-one"] and "unknown until the first run: Auto picks the model (auto-one)" in got["line"])
        got = flow_cost.band({**_wf(), "max_usd": 0.05}, priced.get)
        ctx.check(f"a workflow's own cap holds the high end and is said, got {got['line']!r}", got["high"] == 0.05 and got["line"].endswith("it stops at $0.05 a run"))
    finally:
        T.estimate = saved
    with CrewRig() as rig:
        rig.studio()
        _save(rig, "agent", {**_agent("maker", "auto"), "uses": ["read", "edit"]})
        st, r = rig.api("POST", "crew/workflow-cost", {"workflow": _wf()})
        ctx.check(f"the form's band, the missing agent, what it writes, got {st} {r}", st == 200 and r["missing"] == ["checker"]
                  and r["writes"][0] == "Save writes ~/.halo/crew/workflows/ship.yaml (nothing else)."
                  and "maker (Change files)" in r["writes"][1] and "checker (not an agent yet)" in r["writes"][1])


def _checker(state: dict):
    """The checker's model: a step's turn says what failed; the check says no once, then yes."""
    from tests.helpers.mock_openai import _finish
    from tests.helpers.session_rig import text_step

    def scn(handler, body):
        last = str(((body or {}).get("messages") or [{}])[-1].get("content") or "")
        if "A check after the step" in last:
            state["checks"] += 1
            return _finish(handler, text_step("yes: all 4 pass" if state["checks"] >= 2 else "no: 1 test fails"))
        _finish(handler, text_step("ran the tests: see above"))
    return scn


@test
def test_try_it_on_a_workflow(ctx: Ctx):
    from tests.helpers.mock_openai import SCENARIOS, ScriptedTurns
    from tests.helpers.session_rig import text_step
    state = {"checks": 0}
    SCENARIOS["flow-make"] = ScriptedTurns([text_step("the diff: basket.py +2 -1")])
    SCENARIOS["flow-check"] = _checker(state)
    try:
        with CrewRig() as rig:
            rig.studio()
            _save(rig, "agent", _agent("maker", "or:mock/flow-make"))
            _save(rig, "agent", _agent("checker", "or:mock/flow-check"))
            st, r = rig.api("POST", "crew/try", {"kind": "workflow", "body": _wf(), "request": "fix the basket"})
            ctx.check(f"it starts with the band said first, got {st} {r.get('try', {}).get('estimate')}",
                      st == 200 and r["try"]["kind"] == "workflow" and r["try"]["estimate"]["line"].startswith("unknown until the first run"))
            rec = _wait(rig, r["try"]["id"])
            steps = rec.get("steps") or []
            ctx.check(f"done, got {rec.get('state')} {rec.get('line')!r} {rec.get('error')!r}", rec.get("state") == "done")
            ctx.check(f"each step's result and the agent that ran, got {[(s['name'], s['state'], [a['name'] for a in s['agents']]) for s in steps]}",
                      [(s["name"], s["state"]) for s in steps] == [("Make", "done"), ("Check", "done")]
                      and steps[0]["agents"][0]["text"] == "the diff: basket.py +2 -1")
            ctx.check(f"the check said no, then yes: two rounds, got {steps[1].get('rounds')} {steps[1].get('stop')!r} {rec.get('checks')}",
                      steps[1]["rounds"] == 2 and steps[1]["stop"].startswith("the check said yes after round 2") and len(rec["checks"]) == 2)
            ctx.check(f"where it ran, got {rec.get('where')!r}", rec.get("where", "").startswith("a throwaway copy of shop"))
            trees = subprocess.run(["git", "worktree", "list"], cwd=str(rig.proj), capture_output=True, text=True).stdout.strip().splitlines()
            ctx.check(f"the copy is gone, got {trees}", len(trees) == 1)
            time.sleep(1.2)
            rows = [x for x in rig.api("GET", "live/attention")[1]["rows"] if x["kind"] == "crew_try"]
            ctx.check(f"unseen: an Attention row naming the workflow, got {[x['what'] for x in rows]}",
                      len(rows) == 1 and rows[0]["what"].startswith("Try it finished: workflow ship"))
            _st, got = rig.api("POST", "live/attention/answer", {"id": rows[0]["id"], "key": "o"})
            ctx.check(f"open lands on the Workflows tab, got {got.get('open')}",
                      got.get("open") == {"section": "agents", "view": "flows", "agent": "ship", "try": rec["id"]})
            bad = _wf(checker="nobody-here")
            st, r = rig.api("POST", "crew/try", {"kind": "workflow", "body": bad, "request": "x"})
            ctx.check(f"an agent that does not exist: 422 before any run, got {st} {r.get('error')!r}", st == 422 and "nobody-here" in r["error"])
    finally:
        SCENARIOS.pop("flow-make", None)
        SCENARIOS.pop("flow-check", None)


@test
def test_the_workflow_tool_runs_a_crew_workflow(ctx: Ctx):
    from tests.helpers.workflow_fakes import FakeRuntime, child_row, run_tool
    from types import SimpleNamespace
    with CrewRig() as rig:
        _save(rig, "agent", _agent("maker", "auto"))
        _save(rig, "agent", _agent("checker", "auto"))
        _save(rig, "workflow", _wf())
        rt = FakeRuntime(rig.proj)
        spawned: list = []

        def spawn(*, runtime, tool_id, tool_input, tool_name, on_child=None):
            spawned.append((tool_input["subagent_type"], sorted(getattr(runtime, "agents", {}) or {})))
            child = child_row(rt, f"a{len(spawned)}", cost_usd=0.002)
            if on_child:
                on_child(child)
            yes = tool_input["prompt"].startswith("A check")
            return [], SimpleNamespace(content="<task_result task_id=\"x\">\nyes, they pass\n</task_result>" if yes else "done it", is_error=False)
        res = run_tool(rt, {"task": "fix the basket", "name": "ship"}, spawn=spawn)
        ctx.check(f"each agent spawned as a child by its name, with its crew spec, got {spawned}",
                  [s[0] for s in spawned] == ["maker", "checker", "checker"] and "maker" in spawned[0][1] and "checker" in spawned[1][1])
        ctx.check(f"the receipt line says the step runner ran it, got {res.content.splitlines()[0]!r}",
                  res.content.startswith("crew workflow ship · ran on the step runner · done") and not res.is_error)
        ctx.check("the receipt has a line per step", "step 2 Check: done · checker · 1 round(s), the check said yes" in res.content)
        rec = rt.parent.log.receipts()
        ctx.check(f"a receipt node in the log (engine steps), got {[(r.get('square'), r.get('engine')) for r in rec]}",
                  [(r.get("square"), r.get("engine")) for r in rec] == [("ship", "steps")])
        rows = {aid: row for _k, aid, row in rt.frames}
        ctx.check("each child is drawn as the workflow's on Live", rows.get("a1", {}).get("square", {}).get("name") == "ship")
        from halo_harness.crew.flow_door import named
        ctx.check("a starter's name is not a crew workflow here (the squares keep it)", named("review", rig.proj) is None)


@test
def test_stop_ends_a_workflow_run(ctx: Ctx):
    import threading
    from tests.helpers.mock_openai import SCENARIOS, _finish
    from tests.helpers.session_rig import text_step
    gate = threading.Event()

    def held(handler, body):
        gate.wait(60)
        _finish(handler, text_step("late"))
    SCENARIOS["flow-hold"] = held
    try:
        with CrewRig() as rig:
            rig.studio()
            _save(rig, "agent", _agent("maker", "or:mock/flow-hold"))
            _save(rig, "agent", _agent("checker", "or:mock/flow-hold"))
            _st, r = rig.api("POST", "crew/try", {"kind": "workflow", "body": _wf(), "request": "wait"})
            tid = r["try"]["id"]
            end = time.time() + 60
            while time.time() < end and not any(s.get("state") == "running" for s in rig.api("GET", f"crew/try/{tid}")[1]["try"].get("steps") or []):
                time.sleep(0.2)
            st, _got = rig.api("POST", f"crew/try/{tid}/stop")
            rec = _wait(rig, tid, 60)
            ctx.check(f"Stop: stopped by you, the running step marked stopped, got {st} {rec.get('state')} {[s['state'] for s in rec.get('steps') or []]}",
                      st == 200 and rec.get("state") == "stopped" and [s["state"] for s in rec["steps"]] == ["stopped", "not run"])
            trees = subprocess.run(["git", "worktree", "list"], cwd=str(rig.proj), capture_output=True, text=True).stdout.strip().splitlines()
            ctx.check(f"the copy is gone, got {trees}", len(trees) == 1)
    finally:
        gate.set()
        SCENARIOS.pop("flow-hold", None)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
