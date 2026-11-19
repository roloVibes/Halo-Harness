"""tests.test_map_groups -- Halo 3.6.0.5 (package b, batch 4): Auto's own groups on the page, run in node through
tests/helpers/node_ts.py (no browser, no model; runs anywhere).

1. ONE name for a group (routes/crew/live/groups.ts `groupName`, B5 B24): "workflow {W}", else the task main gave the
   member registered first, as written, else titleOf's words, else "Task {n}"; the Timeline's "by group" (laneGroups.ts
   byGroup) and the glance page (liveModel.ts withGroups) group main's children by their `spawn.group` key and name each
   group with it.
2. Which group every row is in (routes/crew/map/overlayGroups.ts `autoGroups`, B2 B3 B4 B11 B22, R14 R15 R17 on Auto):
   every child of main in exactly one group, a lone child a group of one joined in place, a helper's helpers in its
   group, rows from before grouped by the reply that started them, a workflow run's steps from ITS OWN rows.
3. The view on Auto (routes/crew/map/litView.ts `autoView`, `groupBox`, B8 B9 B10 B12): main and one block per group in
   n order, placed by layoutDown.ts and layout.ts unedited; a map of his draws exactly as before (guard).
Run: python -m tests.test_map_groups
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
SRC = Path(__file__).resolve().parent.parent / "halo_harness" / "studio" / "ui" / "src"
MODS = {
    "groups": "routes/crew/live/groups.ts", "lane": "routes/crew/live/laneGroups.ts", "record": "lib/work/record.ts",
    "og": "routes/crew/map/overlayGroups.ts", "ov": "routes/crew/map/overlay.ts", "lit": "routes/crew/map/litView.ts",
    "view": "routes/crew/map/view.ts", "ld": "routes/crew/map/layoutDown.ts", "lay": "routes/crew/map/layout.ts",
}
T0 = 1_700_000_000.0
# the Linux VM rig's map of his (tests/helpers/studio_session_run.py HOPS)
HOPS = {"format": "map/1", "name": "hops", "main": {"agent": "main"},
        "boxes": [{"id": "code", "agent": "coder"}, {"id": "review", "agent": "reviewer"}, {"id": "docs", "agent": "writer"}],
        "lines": [{"from": "main", "to": "code", "when": "always"}, {"from": "code", "to": "review", "when": "always"},
                  {"from": "main", "to": "docs", "when": "main-decides"}]}
MAIN = {"agent_id": "main", "parent": None, "name": "main", "state": "running", "kind": "main", "since": T0}


def _run(mods: list, body: str, data) -> dict:
    """`body` runs with M.<name> = the imported modules and D = `data`; it prints one JSON line."""
    from tests.helpers import node_ts
    head = "".join(f"M.{m} = await import({json.dumps((SRC / MODS[m]).resolve().as_uri())});\n" for m in mods)
    return node_ts.run(f"const M = {{}};\n{head}const D = {json.dumps(data)};\n{body}")


def kid(aid: str, t: float, *, parent: str = "main", step: str = "", task: str = "", key: str = "", n: int = 0, by: str = "task",
        desc: str = "", lead: str = "", **kw) -> dict:
    spawn = {"step": step, "description": desc, "lead": lead, "task": task}
    if key:
        spawn["group"] = {"key": key, "n": n, "by": by}
    return {"agent_id": aid, "parent": parent, "name": kw.pop("name", "general-purpose"), "state": kw.pop("state", "running"),
            "kind": "subagent", "since": T0 + t, "spawn": spawn, **kw}


# ---------------------------------------------------------------------------------------------- 1. the one name

@test
def test_group_name_order_and_task_n(ctx: Ctx):
    cases = {
        "workflow": [kid("a", 1, step="1", key="workflow:review#tu1", n=1, by="workflow")],
        "hash": [kid("a", 1, step="1", key="workflow:re#view#tu1", n=1, by="workflow")],
        "first": [kid("b2", 5, step="2", task="other", key="task:x", n=2), kid("b1", 2, step="1", task="compare the three reports", key="task:x", n=2)],
        "grandchild": [kid("c1", 1, step="1", desc="read report A"), kid("c2", 3, parent="c1", step="1", task="x")],
        "grandchild_bare": [kid("c1", 1, step="1"), kid("c2", 3, parent="c1", step="1", task="x")],
        "descs": [kid("d1", 1, step="1", desc="read report A"), kid("d2", 2, step="1", desc="read report B"),
                  kid("d3", 3, step="1", desc="read report C")],
        "none": [kid("e1", 1, step="1")],
        "old_flow": [kid("f1", 1, step="1", crew={"workflow": "ship", "step": 1})],
    }
    js = """const out = {};
for (const [k, rows] of Object.entries(D)) out[k] = M.groups.groupName(rows, k === "none" ? 4 : 3);
out.titled = M.groups.titleOf(["read report A", "read report B", "read report C"], "");
console.log(JSON.stringify(out));"""
    got = _run(["groups"], js, cases)
    ctx.check(f"a workflow run's key names it 'workflow review', got {got.get('workflow')!r}", got.get("workflow") == "workflow review")
    ctx.check(f"a W holding '#' keeps it (the LAST '#' splits), got {got.get('hash')!r}", got.get("hash") == "workflow re#view")
    ctx.check(f"the task of the member registered first, as written, got {got.get('first')!r}",
              got.get("first") == "compare the three reports")
    ctx.check(f"a later member's own task never names a reply group: titleOf's words, got {got.get('grandchild')!r}",
              got.get("grandchild") == "read report A")
    ctx.check(f"... and with no description at all: 'Task 3', got {got.get('grandchild_bare')!r}", got.get("grandchild_bare") == "Task 3")
    ctx.check(f"no task: titleOf's answer {got.get('titled')!r}, got {got.get('descs')!r}",
              got.get("descs") == got.get("titled") == "read report")
    ctx.check(f"no task, description or lead: 'Task 4' (never '1 agents'), got {got.get('none')!r}", got.get("none") == "Task 4")
    ctx.check(f"rows from before groups: a step of W reads 'workflow ship', got {got.get('old_flow')!r}", got.get("old_flow") == "workflow ship")


@test
def test_timeline_and_glance_use_group_name(ctx: Ctx):
    rows = [MAIN,
            kid("k1", 1, step="1", task="fix the parser", key="task:fix the parser", n=1, desc="parse"),
            kid("k2", 2, step="1", task="write docs", key="task:write docs", n=2, desc="docs"),
            kid("k3", 3, step="2", task="Fix the parser.", key="task:fix the parser", n=1, desc="parse again"),
            kid("k4", 4, step="2", task="write docs", key="task:write docs", n=2, desc="docs again")]
    # lib/work/record.ts imports react and the fleet store, so laneGroups.ts (byGroup) cannot be loaded in node: the record
    # is built here as recordOf builds it (key, parent, row) and the nodes as laneGroups.ts tagsOf builds them; byGroup and
    # Glance read nothing but withGroups' tags (pinned on their source below)
    js = """const rec = {id: "r1", agents: D.map((a) => ({id: a.agent_id, key: `h1|s1|${a.agent_id}`, parent: a.parent || null,
  name: a.name, role: "", model: "", state: a.state, reason: "", orphan: false, row: a}))};
const nodes = rec.agents.map((a) => ({id: a.id, key: a.key, parent: a.orphan ? null : a.parent, name: a.name, role: a.role, model: a.model, state: a.state, card: ""}));
const all = M.groups.withGroups(nodes, rec);
const tagged = all.filter((n) => n.parent === "main").map((n) => ({id: n.id, title: n.group?.title, gid: n.group?.id}));
// byGroup's order (laneGroups.ts): the lanes in no box first, then each box's head and its lanes, boxes in first-seen order
const seen = new Map();
for (const n of all) if (n.group) seen.set(n.group.id, [...(seen.get(n.group.id) || []), n]);
const rows = [...all.filter((n) => n.id !== "main" && !n.group).map((n) => ({id: n.id}))];
for (const [, ns] of seen) rows.push({head: ns[0].group.title, n: ns.length}, ...ns.map((n) => ({id: n.id})));
const by = {};
for (const a of D) if (a.spawn?.group) (by[a.spawn.group.key] = by[a.spawn.group.key] || []).push(a);
const names = Object.fromEntries(Object.entries(by).map(([k, rs]) => [k, M.groups.groupName(rs, rs[0].spawn.group.n)]));
console.log(JSON.stringify({rows, tagged, names}));"""
    got = _run(["groups"], js, rows)
    names = got.get("names") or {}
    ctx.check(f"groupName: as written by the first registered, got {names}",
              names == {"task:fix the parser": "fix the parser", "task:write docs": "write docs"})
    want = [{"head": "fix the parser", "n": 2}, {"id": "k1"}, {"id": "k3"}, {"head": "write docs", "n": 2}, {"id": "k2"}, {"id": "k4"}]
    ctx.check(f"the Timeline's by group: two heads named by groupName, members by key across two replies, got {got.get('rows')}",
              got.get("rows") == want)
    lane = (SRC / MODS["lane"]).read_text(encoding="utf-8")
    model = (SRC / "routes/crew/live/liveModel.ts").read_text(encoding="utf-8")
    glance = (SRC / "routes/glance/Glance.tsx").read_text(encoding="utf-8")
    ctx.check("byGroup's heads are withGroups' tags; Glance's group title comes from liveModel's withGroups",
              "withGroups(nodes, rec)" in lane and "head: tags.get(" in lane and "withGroups(" in model and "group?.title" in glance)
    tagged = {t["id"]: t for t in got.get("tagged") or []}
    ctx.check(f"withGroups (Glance, Live): each child of main titled groupName of its group, got {tagged}",
              all(tagged.get(a, {}).get("title") == names["task:fix the parser"] for a in ("k1", "k3"))
              and all(tagged.get(a, {}).get("title") == names["task:write docs"] for a in ("k2", "k4"))
              and tagged.get("k1", {}).get("gid", "").endswith("|task:fix the parser"))


# ---------------------------------------------------------------------------------------------- 2. which group

def _groups(rows: list, blocks_events: list | None = None) -> list:
    js = """const ov = M.ov.overlay({boxes: [], lines: []}, D.rows, D.events, %s, {plain: true});
const gs = M.og.autoGroups(D.rows, ov.blocks);
console.log(JSON.stringify({gs, off: ov.offCount}));""" % (T0 + 60)
    return _run(["ov", "og"], js, {"rows": rows, "events": blocks_events or []})


def _brief(gs: list) -> list:
    return [(g.get("n"), g.get("key"), g.get("by"), g.get("name"), [m.get("aid") for m in g.get("members") or []]) for g in gs]


@test
def test_rows_without_group_on_auto_group_by_reply(ctx: Ctx):
    rows = [MAIN, kid("a", 1, step="1", desc="read A"), kid("b", 2, step="1", desc="read B"), kid("c", 3, step="2"),
            kid("w", 4, step="3", crew={"workflow": "W", "step": 1}), kid("z", 5)]
    got = _brief(_groups(rows).get("gs") or [])
    want = [(1, "reply:1", "reply", "read A and 1 more", ["a", "b"]), (2, "reply:2", "reply", "Task 2", ["c"]),
            (3, "workflow:W#", "workflow", "workflow W", ["w"]), (4, "agent:z", "reply", "Task 4", ["z"])]
    ctx.check(f"rows with no group: one group per reply, n by first start; a step of W its workflow; a bare row its own, got {got}",
              got == want)


@test
def test_lone_child_is_a_group_of_one_then_joined_in_place(ctx: Ctx):
    one = [MAIN, kid("x1", 1, step="1", task="x", key="task:x", n=1)]
    two = one + [kid("x2", 2, step="2", task="x", key="task:x", n=1)]
    a, b = _brief(_groups(one).get("gs") or []), _brief(_groups(two).get("gs") or [])
    ctx.check(f"a lone child: one group, n 1, one member, got {a}", a == [(1, "task:x", "task", "x", ["x1"])])
    ctx.check(f"a second with the same key joins it in place: one group, same n and key, two members in start order, got {b}",
              b == [(1, "task:x", "task", "x", ["x1", "x2"])])
    ids = _run(["lit"], "console.log(JSON.stringify([M.lit.groupId(1), M.lit.groupId(1)]))", None)
    ctx.check(f"its block's id is the same before and after (groupId of its n), got {ids}", ids == ["group:1", "group:1"])


@test
def test_one_group_per_child_of_main(ctx: Ctx):
    rows = [MAIN, kid("a", 1, step="1", task="t", key="task:t", n=1), kid("b", 2, step="2"), kid("c", 3, parent="a", key="task:t", n=1),
            kid("d", 4, parent="b"), kid("e", 5, step="3", crew={"workflow": "W", "step": 1}), kid("f", 6),
            kid("g", 7, step="4", key="workflow:Q#tu9", n=2, by="workflow")]
    gs = _groups(rows).get("gs") or []
    seen = [m.get("aid") for g in gs for m in g.get("members") or []]
    ctx.check(f"every row but main is in exactly one group, got {sorted(seen)}", sorted(seen) == list("abcdefg"))
    ns = [g.get("n") for g in gs]
    ctx.check(f"groups in n order, engine n's kept, the rest after the largest in start order, got {ns}",
              ns == sorted(ns) and len(set(ns)) == len(ns) and ns[:2] == [1, 2])


@test
def test_child_of_child_joins_its_parents_group(ctx: Ctx):
    rows = [MAIN, kid("p", 1, step="1", task="p", key="task:p", n=1), kid("g1", 2, parent="p", step="7", key="task:p", n=1),
            kid("g2", 3, parent="p", step="8"), kid("q", 4, step="5"), kid("q1", 5, parent="q", step="9")]
    gs = _groups(rows).get("gs") or []
    got = _brief(gs)
    ctx.check(f"a grandchild with its parent's group and one from before with none: both in the parent's group, got {got}",
              got == [(1, "task:p", "task", "p", ["p", "g1", "g2"]), (2, "reply:5", "reply", "Task 2", ["q", "q1"])])
    by = {m["aid"]: m.get("by") for g in gs for m in g.get("members") or []}
    ctx.check(f"each grandchild's by is its parent member's agent id, a child of main has none, got {by}",
              by == {"p": None, "g1": "p", "g2": "p", "q": None, "q1": "q"})


@test
def test_workflow_run_group_steps_per_run(ctx: Ctx):
    start = {"event": "map_step", "data": {"map": "auto", "box": "workflow:W", "workflow": "W", "kind": "start", "steps": ["code", "review"], "t": T0}}
    rows = [MAIN,
            kid("s1", 1, step="1", key="workflow:W#tu1", n=1, by="workflow", name="coder", model="or:v/m1", state="done",
                crew={"workflow": "W", "step": 1, "agent": "coder"}),
            kid("s2", 2, step="1", key="workflow:W#tu1", n=1, by="workflow", name="reviewer", model="or:v/m3",
                crew={"workflow": "W", "step": 2, "agent": "reviewer"}),
            kid("t1", 3, step="2", key="workflow:W#tu2", n=2, by="workflow", name="coder", model="or:v/m2",
                crew={"workflow": "W", "step": 1, "agent": "coder"}),
            # a square session run (workflows/receipts.py rows): no crew tag, no map_step frame, so no blocks.Q
            kid("q1", 4, step="3", key="workflow:Q#tu3", n=3, by="workflow", square={"name": "Q"}),
            kid("q2", 5, step="3", key="workflow:Q#tu3", n=3, by="workflow", square={"name": "Q"})]
    gs = _groups(rows, [start]).get("gs") or []
    steps = {g.get("key"): [(s["n"], s["step"], s["agent"], s["model"], s["state"]) for s in g.get("steps") or []] for g in gs}
    ctx.check(f"run 1's steps from ITS rows, got {steps.get('workflow:W#tu1')}",
              steps.get("workflow:W#tu1") == [(1, "code", "coder", "or:v/m1", "done"), (2, "review", "reviewer", "or:v/m3", "working")])
    ctx.check(f"run 2's steps from ITS rows, 'next' with the list's agent where it has none, got {steps.get('workflow:W#tu2')}",
              steps.get("workflow:W#tu2") == [(1, "code", "coder", "or:v/m2", "working"), (2, "review", "reviewer", "", "next")])
    q = next((g for g in gs if g.get("key") == "workflow:Q#tu3"), {})
    ctx.check(f"a run with no block (a square run): no steps, its members in start order, got {q}",
              "steps" not in q and [m["aid"] for m in q.get("members") or []] == ["q1", "q2"] and q.get("workflow") == "Q")
    ctx.check(f"both runs of W are named 'workflow W', got {[g.get('name') for g in gs]}",
              [g.get("name") for g in gs] == ["workflow W", "workflow W", "workflow Q"])


@test
def test_made_up_child_on_auto_is_a_member(ctx: Ctx):
    rows = [MAIN,
            kid("gp", 1, step="1", key="task:a", n=1, role="general-purpose", crew={"map": "auto", "box": "main", "made_up": True}),
            kid("rs", 2, step="2", key="task:b", n=2, name="researcher", role="researcher"),
            kid("sv", 3, step="3", key="task:c", n=3, name="x", crew={"agent": "reviewer", "saved": True})]
    got = _groups(rows)
    ms = {m["aid"]: (m.get("who"), m.get("made")) for g in got.get("gs") or [] for m in g.get("members") or []}
    ctx.check(f"a made-up general-purpose child: who 'agent', made; a routed role its role; a saved agent its name, got {ms}",
              ms == {"gp": ("agent", True), "rs": ("researcher", False), "sv": ("reviewer", False)})
    ctx.check(f"on Auto no hand-off is counted off the map, got offCount {got.get('off')}", got.get("off") == 0)


# ---------------------------------------------------------------------------------------------- 3. the view on Auto

AUTO = {"format": "map/1", "name": "auto", "main": {"agent": "main"}, "boxes": [{"id": "x", "agent": "coder"}],
        "lines": [{"from": "main", "to": "x"}]}


def _g(n: int) -> dict:
    return {"n": n, "key": f"task:t{n}", "by": "task", "name": f"t{n}", "members": [{"aid": f"a{n}"}], "first": n}


@test
def test_auto_draws_main_alone_before_anyone(ctx: Ctx):
    js = """const v = M.lit.autoView(M.view.view(D, [], []), []);
console.log(JSON.stringify({v, band: M.ld.layoutDown(v, () => 80, 432).band}));"""
    got = _run(["view", "lit", "ld"], js, AUTO)
    v = got.get("v") or {}
    ctx.check(f"before anyone: main alone, no line, no strip, got {v}",
              [b.get("id") for b in v.get("boxes") or []] == ["main"] and v.get("lines") == [] and v.get("strip") == [])
    ctx.check(f"no unreached band on Auto, got {got.get('band')}", got.get("band") is None)


@test
def test_group_block_numbers_432_424_400_399(ctx: Ctx):
    js = """const v = M.lit.autoView(M.view.view(D, [], []), [{n: 2, key: "task:b", by: "task", name: "b", members: [], first: 2},
                                                        {n: 1, key: "task:a", by: "task", name: "a", members: [], first: 1}]);
const out = {};
for (const cw of [432, 424, 400, 399]) {
  const d = M.ld.layoutDown(v, () => 80, cw);
  const g = (n) => d.boxes.find((b) => b.id === M.lit.groupId(n));
  out[cw] = {pad: d.pad, g1: [g(1).x, g(1).w, g(1).y, g(1).h], g2: [g(2).x, g(2).w, g(2).y], colours: [g(1).group.colour, g(2).group.colour]};
}
out.box = [M.lit.groupBox(384), M.lit.groupBox(200)];
out.order = v.boxes.map((b) => b.id);
console.log(JSON.stringify(out));"""
    got = _run(["view", "lit", "ld"], js, AUTO)
    ctx.check(f"main, then the groups in n order, got {got.get('order')}", got.get("order") == ["main", "group:1", "group:2"])
    for cw, (pad, w) in {"432": (12, 384), "424": (12, 384), "400": (8, 384), "399": (12, 200)}.items():
        r = got.get(cw) or {}
        g1, g2 = r.get("g1") or [0, 0, 0, 0], r.get("g2") or [0, 0, 0]
        ctx.check(f"at {cw}: each group at x = pad {pad}, {w} wide, got g1 {g1} g2 {g2}",
                  r.get("pad") == pad and g1[:2] == [pad, w] and g2[:2] == [pad, w])
        ctx.check(f"at {cw}: the band between the two blocks is at least 16, got {g2[2] - g1[2] - g1[3]}", g2[2] - g1[2] - g1[3] >= 16)
        ctx.check(f"at {cw}: colours 1 and 2, got {r.get('colours')}", r.get("colours") == [1, 2])
    ctx.check(f"groupBox(384) = inner 360, two a row of 176; groupBox(200) = inner 176, one a row, got {got.get('box')}",
              got.get("box") == [{"inner": 360, "per": 2, "member": 176}, {"inner": 176, "per": 1, "member": 176}])


@test
def test_agents_group_248_column_1_line_enters_30(ctx: Ctx):
    js = """const v = M.lit.autoView(M.view.view(D.map, [], []), D.gs);
const p = M.lay.layout(v.boxes, v.lines, () => 120);
const at = (id) => p.boxes.find((b) => b.id === id);
console.log(JSON.stringify({main: at("main").x, g: [1, 2, 5].map((n) => [at(M.lit.groupId(n)).x, at(M.lit.groupId(n)).y, at(M.lit.groupId(n)).h]),
  lines: p.lines.map((l) => [l.to, l.d]), box: M.lit.groupBox(248), w: M.lay.BOX_W, colour: at(M.lit.groupId(5)).group.colour}));"""
    got = _run(["view", "lit", "lay"], js, {"map": AUTO, "gs": [_g(1), _g(2), _g(5)]})
    g = got.get("g") or []
    ctx.check(f"main in column 0 at x 24, got {got.get('main')}", got.get("main") == 24)
    ctx.check(f"every group in column 1 (x 484), in n order, stacked 28 apart, got {g}",
              len(g) == 3 and all(x[0] == 484 for x in g) and all(g[i + 1][1] == g[i][1] + g[i][2] + 28 for i in range(2)))
    ends = {to: d for to, d in got.get("lines") or []}
    ctx.check(f"each line enters its group 30 px below its top, got {ends}",
              all(ends.get(f"group:{n}", "").endswith(f"V{y + 30} H{x}") for n, (x, y, _h) in zip((1, 2, 5), g)))
    ctx.check(f"a 248 px box: inner 224, one member a row of 224, got {got.get('box')} (BOX_W {got.get('w')})",
              got.get("box") == {"inner": 224, "per": 1, "member": 224} and got.get("w") == 248)
    ctx.check(f"group 5's colour is ((5-1) mod 4)+1 = 1, got {got.get('colour')}", got.get("colour") == 1)


@test
def test_new_group_goes_last_nothing_moves(ctx: Ctx):
    js = """const at = (gs) => {
  const v = M.lit.autoView(M.view.view(D.map, [], []), gs);
  const d = M.ld.layoutDown(v, () => 90, 432), p = M.lay.layout(v.boxes, v.lines, () => 110);
  const f = (bs, id) => { const b = bs.find((x) => x.id === id); return [b.x, b.y]; };
  return {down: [1, 2].map((n) => f(d.boxes, M.lit.groupId(n))), across: [1, 2].map((n) => f(p.boxes, M.lit.groupId(n))),
          last: [f(d.boxes, v.boxes[v.boxes.length - 1].id), v.boxes[v.boxes.length - 1].id]};
};
console.log(JSON.stringify({two: at(D.two), three: at(D.three)}));"""
    got = _run(["view", "lit", "ld", "lay"], js, {"map": AUTO, "two": [_g(1), _g(2)], "three": [_g(1), _g(2), _g(3)]})
    two, three = got.get("two") or {}, got.get("three") or {}
    ctx.check(f"adding group 3 leaves groups 1 and 2 where they were, down and across, got {two} vs {three}",
              two.get("down") == three.get("down") and two.get("across") == three.get("across"))
    ctx.check(f"the new group is drawn last, below the others, got {three.get('last')}",
              (three.get("last") or [[0, 0], ""])[1] == "group:3" and three["last"][0][1] > max(y for _x, y in three.get("down") or [[0, 0]]))


@test
def test_session_line_enters_the_block_top(ctx: Ctx):
    js = """const v = M.lit.autoView(M.view.view(D.map, [], []), D.gs);
const d = M.ld.layoutDown(v, () => 80, 432);
console.log(JSON.stringify(d.lines.map((l) => { const t = d.boxes.find((b) => b.id === l.to);
  return {to: l.to, solid: !l.helper && !l.off, entry: l.entry, cx: t.x + t.w / 2, d: l.d, y: t.y}; })));"""
    got = _run(["view", "lit", "ld"], js, {"map": AUTO, "gs": [_g(1), _g(2), _g(3)]})
    ctx.check(f"one solid line from main per group, got {[x.get('to') for x in got]}",
              [x.get("to") for x in got] == ["group:1", "group:2", "group:3"] and all(x.get("solid") for x in got))
    ctx.check(f"each ends at its block's top edge at the block's centre, got {got}",
              all(x["entry"] == x["cx"] and x["d"].endswith(f"V{x['y']}") for x in got))


@test
def test_rows_without_group_on_his_map_draw_as_3604(ctx: Ctx):
    """Guard (green before and after): on a map of his the rows' `spawn.group` changes nothing -- withRun over the overlay of
    rows that carry it equals withRun over the same rows stripped of it."""
    rows = [MAIN,
            kid("c1", 1, step="1", task="fix", key="task:fix", n=1, name="coder", crew={"map": "hops", "box": "code", "line": "main -> code"}),
            kid("r1", 2, step="1", task="fix", key="task:fix", n=1, name="reviewer", state="waiting",
                crew={"map": "hops", "box": "review", "line": "code -> review"}),
            kid("h1", 3, step="2", task="look", key="task:look", n=2, crew={"map": "hops", "box": "main", "made_up": True}),
            kid("s1", 4, step="3", key="workflow:W#tu1", n=3, by="workflow", name="coder", crew={"workflow": "W", "step": 1, "agent": "coder"})]
    bare = [{**r, "spawn": {k: v for k, v in (r.get("spawn") or {}).items() if k not in ("group", "task")}} if r.get("spawn") else r for r in rows]
    js = """const v = M.view.view(D.map, [], []);
const run = (rows) => { const ov = M.ov.overlay(D.map, rows, [], %s); return {ov, drawn: M.lit.withRun(v, ov, null, false)}; };
console.log(JSON.stringify({a: run(D.rows), b: run(D.bare)}));""" % (T0 + 60)
    got = _run(["view", "ov", "lit"], js, {"map": HOPS, "rows": rows, "bare": bare})
    a, b = got.get("a") or {}, got.get("b") or {}
    ctx.check("his map: the drawing with groups on the rows equals the drawing without them", a.get("drawn") == b.get("drawn") and a.get("drawn"))
    ctx.check("his map: the overlay too", a.get("ov") == b.get("ov"))
    ctx.check(f"his map: no box is a group, got {[x.get('id') for x in (a.get('drawn') or {}).get('boxes') or [] if x.get('group')]}",
              not any(x.get("group") for x in (a.get("drawn") or {}).get("boxes") or []))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
