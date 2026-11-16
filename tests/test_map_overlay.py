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


# -- 3.6.0.2 batch 4 (P3d): the run drawn as it is (R14 R16 R17 R48 R49) ---------------------------------------------------
HOPS = TS.parent / "overlayHops.ts"
FLOW_MAP = {"boxes": [{"id": "review", "agent": "reviewer"}, {"id": "tester", "agent": "tester"}], "lines": [{"from": "main", "to": "review"}]}
STEP_AGENTS = ("planner", "coder", "tester", "reviewer")
SIX = ["plan", "code", "test", "review", "fix", "ship"]


def _flow_rows(states=("done", "done", "running", "queued")) -> list:
    out = [{"agent_id": "main", "parent": None, "name": "main", "state": "running", "kind": "main", "current": "Workflow: W"}]
    for i, (agent, st) in enumerate(zip(STEP_AGENTS, states), start=1):
        out.append(row(f"w{i}", agent, st, model=f"or:v/{agent}", crew={"map": "N", "workflow": "W", "step": i, "agent": agent, "saved": True}))
    return out


def _node(js: str, *args) -> dict:
    from tests.helpers import node_ts
    return node_ts.run(js % tuple(json.dumps(a) for a in args))


@test
def test_overlay_reads_workflow_tags_first(ctx: Ctx):
    start = {"event": "map_step", "data": {"map": "N", "box": "workflow:W", "workflow": "W", "kind": "start", "steps": SIX, "t": T0}}
    boxed = {**FLOW_MAP, "boxes": [*FLOW_MAP["boxes"], {"id": "w", "workflow": "W"}]}
    js = """const m = await import(%s);
const rows = %s, map = %s, boxed = %s, evs = [%s];
const a = m.overlay(map, rows, evs, %s), b = m.overlay(boxed, rows, evs, %s);
console.log(JSON.stringify({a: {blocks: a.blocks, boxes: a.boxes, helpers: a.helpers, strangers: a.strangers}, b: {blocks: b.blocks, boxes: b.boxes}}));"""
    got = _node(js, TS.resolve().as_uri(), _flow_rows(), FLOW_MAP, boxed, start, T0 + 5, T0 + 5)
    a, b = got.get("a", {}), got.get("b", {})
    blk = (a.get("blocks") or {}).get("W") or {}
    steps = [(s.get("n"), s.get("step"), s.get("agent"), s.get("state")) for s in blk.get("steps") or []]
    ctx.check(f"R14: W (no box here) is a block of six steps in order, done done working next next next, got {blk.get('box')!r} {steps}",
              "box" in blk and blk["box"] is None and steps == [(1, "plan", "planner", "done"), (2, "code", "coder", "done"),
                                                                 (3, "test", "tester", "working"), (4, "review", "reviewer", "next"),
                                                                 (5, "fix", "", "next"), (6, "ship", "", "next")])
    ctx.check(f"R14: a step's model is its row's, got {[s.get('model') for s in blk.get('steps') or []][:4]}",
              [s.get("model") for s in blk.get("steps") or []][:4] == [f"or:v/{x}" for x in STEP_AGENTS])
    bx = a.get("boxes") or {}
    ctx.check(f"R14: the boxes named like the steps' agents stay calm, got tester={bx.get('tester')} review={bx.get('review')}",
              (bx.get("tester") or {}).get("state") == "idle" and (bx.get("review") or {}).get("state") == "idle")
    ctx.check(f"R14: a step is never a helper nor a stranger, got {a.get('helpers')} {a.get('strangers')}",
              a.get("helpers") == [] and a.get("strangers") == [])
    wb = (b.get("blocks") or {}).get("W") or {}
    ctx.check(f"R14: where W is a box, that box is the block and it works, got {wb.get('box')!r} {(b.get('boxes') or {}).get('w')}",
              wb.get("box") == "w" and ((b.get("boxes") or {}).get("w") or {}).get("state") == "working")


@test
def test_overlay_keeps_off_hops(ctx: Ctx):
    m = {"boxes": [{"id": "code", "agent": "coder"}, {"id": "review", "agent": "reviewer"}], "lines": [{"from": "main", "to": "code"}]}
    rows = [{"agent_id": "main", "parent": None, "name": "main", "state": "running", "kind": "main"},
            row("c1", "coder", "running", crew={"map": "N", "box": "code", "line": "main -> code", "agent": "coder", "saved": True}),
            row("a1", "general-purpose", "running", crew={"map": "N", "box": "main", "made_up": True}, task="list the repo"),
            row("r1", "reviewer", "running", parent="c1", crew={"map": "N", "box": "review", "agent": "reviewer", "saved": True})]

    def hop(frm, to, st, t, **kw):
        return {"event": "map_hop", "data": {"map": "N", "from": frm, "to": to, "state": st, "t": T0 + t, "task": "list the repo", **kw}}
    evs = [hop("main", "code", "start", 1, line="main -> code", off=False), hop("main", "made-up:a1", "start", 2, off=True, aid="a1"),
           hop("code", "review", "start", 3, off=True)]
    js = """const m = await import(%s);
const map = %s, rows = %s, evs = %s, now = %s;
const his = m.overlay(map, rows, evs, now, {plain: false}), plain = m.overlay(map, rows, evs, now, {plain: true});
const bare = m.overlay(map, rows, evs.slice(0, 1), now);
console.log(JSON.stringify({his: {off: his.off, n: his.offCount, lines: his.lines, pulses: his.pulses, gone: his.gone, kids: his.kids},
  plain: {n: plain.offCount, kids: plain.kids}, bare: {lines: bare.lines, pulses: bare.pulses}}));"""
    got = _node(js, TS.resolve().as_uri(), m, rows, evs, T0 + 4)
    his = got.get("his") or {}
    off = sorted((o.get("from"), o.get("to"), o.get("n"), o.get("sender")) for o in his.get("off") or [])
    ctx.check(f"R48: both hand-offs on no line are kept with their sender, got {off}",
              off == [("code", "review", 1, "code"), ("main", "made-up:a1", 1, "main")])
    ctx.check(f"R48: neither is taken for a removed box, got {his.get('gone')}", his.get("gone") == [])
    ctx.check(f"R17: on a map of his two children are off it (counted by rows), got {his.get('n')}", his.get("n") == 2)
    ctx.check(f"R17: on the default map none is counted, got {(got.get('plain') or {}).get('n')}", (got.get("plain") or {}).get("n") == 0)
    kid = {k["aid"]: (k["made"], k["off"], k["unlined"]) for ks in (his.get("kids") or {}).values() for k in ks}
    pk = {k["aid"]: (k["off"], k["unlined"]) for ks in ((got.get("plain") or {}).get("kids") or {}).values() for k in ks}
    ctx.check(f"R15 R17: a1 made up and off, r1 saved and off, c1 on its line, got {kid}",
              kid == {"c1": (False, False, False), "a1": (True, True, True), "r1": (False, True, True)})
    ctx.check(f"R17: on the default map the unlined rows are plain (not off), got {pk}",
              pk == {"c1": (False, False), "a1": (False, True), "r1": (False, True)})
    bare = got.get("bare") or {}
    ctx.check(f"R48: the real line's lighting is unchanged by the off hops, got {his.get('lines')} {his.get('pulses')}",
              his.get("lines") == bare.get("lines") and his.get("pulses") == bare.get("pulses") and "main>code" in (his.get("lines") or {}))


@test
def test_trace_totals_survive_the_window(ctx: Ctx):
    js = """const m = await import(%s);
const T0 = %s, f = [];
const hop = (st, t) => ({event: 'map_hop', data: {from: 'main', to: 'code', state: st, t: T0 + t, task: 'fix the retry'}});
for (let i = 0; i < 3; i++) f.push(hop('start', i));
for (let i = 0; i < 694; i++) f.push({event: 'map_step', data: {box: 'plan', kind: 'step', n: 1, t: T0 + 3 + i}});
f.push(hop('start', 900), hop('end', 901), {event: 'map_step', data: {box: 'plan', kind: 'end', t: T0 + 902}});
const all = m.foldAll(f), win = m.foldAll(f.slice(-600));
console.log(JSON.stringify({n: f.length, all: all.lines['main>code'], win: win.lines['main>code'], flight: all.flight, last: all.last}));"""
    got = _node(js, HOPS.resolve().as_uri(), T0)
    a, w = got.get("all") or {}, got.get("win") or {}
    ctx.check(f"R49: 700 frames folded: main>code carried 4 hand-offs, the last at +900, got {got.get('n')} {a}",
              got.get("n") == 700 and a.get("n") == 4 and abs((a.get("last") or 0) - (T0 + 900)) < 1e-6 and a.get("task") == "fix the retry")
    ctx.check(f"R49: the 600-frame replay window alone would count 1, got {w}", w.get("n") == 1)
    ctx.check(f"R49: the newest hand-off is marked and its end leaves nothing in flight, got "
              f"{got.get('flight')} {got.get('last')!r}", got.get("last") == "main>code" and set(got.get("flight") or {}) == set())


@test
def test_line_live_cleared_when_no_live_row(ctx: Ctx):
    js = """const m = await import(%s);
const t = m.foldAll([{event: 'map_hop', data: {from: 'main', to: 'code', state: 'start', t: 1}},
                     {event: 'map_hop', data: {from: 'main', to: 'workflow:W', state: 'start', t: 2}}]);
const kid = (st, crew) => ({agent_id: 'c1', parent: 'main', state: st, crew});
const line = {line: 'main -> code'}, flow = {workflow: 'W', step: 1};
console.log(JSON.stringify({
  running: [...m.inFlight(t, [kid('running', line)], true)], done: [...m.inFlight(t, [kid('done', line)], true)],
  none: [...m.inFlight(t, [], false)], idle: [...m.inFlight(t, [kid('running', line)], false)],
  flow: [...m.inFlight(t, [kid('running', flow)], true)],
  ended: [...m.inFlight(m.foldHop(t, {event: 'map_hop', data: {from: 'main', to: 'code', state: 'end', t: 3}}), [kid('running', line)], true)]}));"""
    got = _node(js, HOPS.resolve().as_uri())
    ctx.check(f"R16: a start with no end and a running row on that line: live, got {got.get('running')}", got.get("running") == ["main>code"])
    ctx.check(f"R16: no live row carries the line: not live, got {got.get('done')}", got.get("done") == [])
    ctx.check(f"R16: a fleet load where the session is not busy: nothing live, got {got.get('none')} {got.get('idle')}",
              got.get("none") == [] and got.get("idle") == [])
    ctx.check(f"R16: a workflow's door hop is live while a step of W runs, got {got.get('flow')}", got.get("flow") == ["main>workflow:W"])
    ctx.check(f"R16: its end ends it, got {got.get('ended')}", got.get("ended") == [])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
