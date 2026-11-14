"""tests.test_map_overlay -- Halo 3.6.0.0 R4: the lit Map's overlay (routes/crew/map/overlay.ts, run in node through
tests/helpers/node_ts.py), fed a recorded stream: the agent rows and the map_hop / map_step events one session on the
ship-it-like map below sends (as crew/map_events.py publishes them).

1. each box's state (working / waiting / done / not used yet), what it does now and its cost;
2. a hand-off pulses on the line its receipt named, the label's task for PULSE_S seconds, then not; a chain box to box;
   a line not taken says why; a background hand-off is marked;
3. a workflow box's steps lit as the step runner emits them, with the repeat's rounds and checks;
4. a helper the session made up hangs under the box that started it (by its tag, and by its parent when untagged);
5. an ask: the box waits on you;
6. a row that matches nothing is a stranger (shown in the strip), never dropped; a hop on a line the map lost: gone;
7. replay equals live: the recorded events up to a moment, through the same function, give the same overlay.
No model, no browser. Run: python -m tests.test_map_overlay
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
TS = Path(__file__).resolve().parent.parent / "halo_harness" / "studio" / "ui" / "src" / "routes" / "crew" / "map" / "overlay.ts"
T0 = 1_700_000_000.0
MAP = {"boxes": [{"id": "plan", "workflow": "plan"}, {"id": "code", "agent": "coder"}, {"id": "review", "agent": "reviewer"},
                 {"id": "docs", "agent": "writer"}],
       "lines": [{"from": "main", "to": "plan"}, {"from": "plan", "to": "code"}, {"from": "code", "to": "review"},
                 {"from": "main", "to": "docs"}, {"from": "code", "to": "docs"}]}


def row(aid, name, state, parent="main", cost=0.0, **kw):
    return {"agent_id": aid, "parent": parent, "name": name, "state": state, "cost_usd": cost, "kind": "subagent", **kw}


ROWS = [
    {"agent_id": "main", "parent": None, "name": "main", "state": "running", "kind": "main", "cost_usd": 0.01, "current": "Agent: plan",
     "model": "or:v/main"},
    {"agent_id": "sq-1", "parent": "main", "name": "plan", "state": "done", "kind": "square", "square": {"name": "plan"}},
    row("p1", "planner", "done", parent="main", cost=0.02, square={"name": "plan"}, model="or:v/think"),
    row("c1", "coder", "running", cost=0.05, current="Bash: pytest -q", crew={"map": "ship", "box": "code", "line": "plan -> code"},
        model="or:v/code"),
    row("r1", "reviewer", "waiting", cost=0.01, crew={"map": "ship", "box": "review", "line": "code -> review"}),
    row("h1", "general-purpose", "running", cost=0.003, crew={"map": "ship", "box": "main", "made_up": True}, task="list the repo"),
    row("h2", "Explore", "running", parent="c1", task="find the retry"),
    row("x1", "ghost", "running", parent="nobody"),
    row("x2", "old", "done", crew={"map": "ship", "box": "pdfs"}),
]


def hop(line, state, t, **kw):
    a, b = line.split(" -> ")
    return {"event": "map_hop", "data": {"map": "ship", "line": line, "from": a, "to": b, "state": state, "t": T0 + t,
                                         "task": "fix the retry in client.py", "why": "always", **kw}}


def step(kind, t, **kw):
    return {"event": "map_step", "data": {"map": "ship", "box": "plan", "workflow": "plan", "kind": kind, "t": T0 + t, **kw}}


EVENTS = [
    hop("main -> plan", "start", 1), step("start", 1.1, steps=[{"name": "Plan"}, {"name": "Check"}]),
    step("step", 1.2, n=1, name="Plan", state="running"), step("agent", 1.3, n=1, round=1, name="planner", state="done", said="a plan"),
    step("step", 2, n=1, name="Plan", state="done", rounds=1), step("agent", 2.1, n=2, round=1, name="planner", state="done"),
    step("check", 2.2, n=2, round=1, yes=False), step("agent", 2.3, n=2, round=2, name="planner", state="done"),
    step("check", 2.4, n=2, round=2, yes=True), step("step", 2.5, n=2, name="Check", state="done", rounds=2), step("end", 2.6, state="done"),
    hop("main -> plan", "end", 2.7), hop("plan -> code", "start", 3, chain=True), hop("code -> review", "start", 10, chain=True),
    hop("code -> pdfs", "skipped", 10.1, why="the task needs none of pdf"),
    hop("code -> docs", "skipped", 10.2, why="the task says none of: docs"), hop("main -> docs", "start", 11, background=True),
]

JS = """const m = await import(%s);
const map = %s, rows = %s, evs = %s, t0 = %s;
const live = m.overlay(map, rows, evs, t0 + 12);
const later = m.overlay(map, rows, evs, t0 + 30);
const replay = m.overlay(map, rows, m.eventsAt(evs, t0 + 12), t0 + 12);
const mid = m.overlay(map, rows, m.eventsAt(evs, t0 + 3.5), t0 + 3.5);
console.log(JSON.stringify({live, later, same: JSON.stringify(live) === JSON.stringify(replay), mid}));"""


def _run() -> dict:
    from tests.helpers import node_ts
    return node_ts.run(JS % (json.dumps(TS.resolve().as_uri()), json.dumps(MAP), json.dumps(ROWS), json.dumps(EVENTS), T0))


_GOT: dict = {}


def got() -> dict:
    if not _GOT:
        _GOT.update(_run())
    return _GOT


@test
def test_each_box_says_its_state_what_it_does_and_its_cost(ctx: Ctx):
    b = got()["live"]["boxes"]
    ctx.check(f"code works, running its tool, at $0.05, got {b['code']}", b["code"]["state"] == "working" and b["code"]["doing"] == "Bash pytest -q"
              and abs(b["code"]["cost"] - 0.05) < 1e-9)
    ctx.check(f"the plan workflow's step agent and node are its box, done, got {b['plan']}", b["plan"]["state"] == "done" and
              sorted(b["plan"]["agents"]) == ["p1", "sq-1"])
    ctx.check(f"docs: not used yet, got {b['docs']}", b["docs"]["state"] == "idle" and b["docs"]["doing"] == "not used yet")
    ctx.check(f"main works and counts only its own cost, got {b['main']}", b["main"]["state"] == "working" and abs(b["main"]["cost"] - 0.01) < 1e-9)
    f = got()["live"]["facts"]
    ctx.check(f"the top sentence's facts: the whole session's cost and its models, got {f}",
              abs(f["cost"] - 0.093) < 1e-9 and f["models"] == ["or:v/main", "or:v/think", "or:v/code"] and f["hops"] == 4)


@test
def test_a_hand_off_pulses_on_the_named_line_then_its_when_again(ctx: Ctx):
    live, later = got()["live"], got()["later"]
    ctx.check(f"within {4} s the pulses on code -> review and main -> docs, got {live['pulses']}",
              [(p["from"], p["to"]) for p in live["pulses"]] == [("code", "review"), ("main", "docs")] and live["pulses"][0]["task"].startswith("fix the retry"))
    ctx.check("after it, no pulse: the label is its When again", later["pulses"] == [])
    ln = live["lines"]
    ctx.check(f"a chain seen box to box: each line fired, got {sorted(ln)}", {"main>plan", "plan>code", "code>review"} <= set(ln)
              and ln["main>plan"]["running"] is False and ln["plan>code"]["running"] is True)
    ctx.check(f"the line not taken says why, got {ln.get('code>docs')}", ln["code>docs"]["skipped"] == "the task says none of: docs")
    ctx.check(f"a background hand-off is marked, got {ln['main>docs']}", ln["main>docs"]["background"] is True)


@test
def test_a_workflow_box_lights_its_steps_and_the_repeat(ctx: Ctx):
    s = got()["live"]["steps"]["plan"]
    ctx.check(f"the workflow ran, got {s['state']}", s["state"] == "done")
    ctx.check(f"two steps, named, done, got {s['steps']}", [(x["name"], x["state"]) for x in s["steps"]] == [("Plan", "done"), ("Check", "done")])
    ctx.check(f"the repeat: two rounds and two checks on step 2, its agent, got {s['steps'][1]}",
              s["steps"][1]["rounds"] == 2 and s["steps"][1]["checks"] == 2 and s["steps"][1]["agents"] == ["planner"])
    mid = got()["mid"]["steps"]["plan"]
    ctx.check(f"at 3.5 s the workflow had ended: replayed steps, got {mid['state']}", mid["state"] == "done")


@test
def test_made_up_helpers_hang_under_the_box_that_started_them(ctx: Ctx):
    h = {x["aid"]: x["box"] for x in got()["live"]["helpers"]}
    ctx.check(f"the tagged helper under main, the untagged child of coder under code, got {h}", h == {"h1": "main", "h2": "code"})


@test
def test_an_ask_makes_its_box_wait_on_you(ctx: Ctx):
    live = got()["live"]
    ctx.check(f"review waits on you, got {live['boxes']['review']}", live["boxes"]["review"]["state"] == "waiting" and
              live["boxes"]["review"]["doing"] == "waiting on you" and live["waiting"] == ["review"] and live["facts"]["waiting"] == 1)


@test
def test_a_row_that_matches_nothing_is_shown_never_dropped(ctx: Ctx):
    s = {x["aid"]: x["why"] for x in got()["live"]["strangers"]}
    ctx.check(f"an orphan and a box the map lost, each said, got {s}", s == {"x1": "no box and no parent on this map",
                                                                          "x2": "its box pdfs is not on this map (removed since)"})
    live = got()["live"]
    n = len(live["helpers"]) + len(live["strangers"]) + sum(len(b["agents"]) for b in live["boxes"].values())
    ctx.check(f"every row is somewhere, got {n} of {len(ROWS)}", n == len(ROWS))
    ctx.check(f"a skipped line on a line the map does not have: its box is gone, got {live['gone']}", live["gone"] == ["pdfs"])


@test
def test_replay_equals_live_for_the_same_events(ctx: Ctx):
    ctx.check("the recorded events up to the moment, through the same function, give the same overlay", got()["same"] is True)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
