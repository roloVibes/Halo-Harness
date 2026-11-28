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
4. (batch 5) A group's words (groupWords.ts, section 3 (b), B11 B13 B30), its colour, main's line into it lit from its
   rows (overlayHops.ts groupTotals / groupLive, B12a), the cards on a member and a group (stepInTarget.ts, runFrame.ts
   selected), the default's names one map in litStore.ts (chosen, ownsMap), no fetch or timer in the group files (B25).
Run: python -m tests.test_map_groups
"""
from __future__ import annotations

import json
import re
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
    "gw": "routes/crew/map/groupWords.ts", "hops": "routes/crew/map/overlayHops.ts", "sit": "routes/crew/map/stepInTarget.ts",
    "tw": "routes/crew/map/truthWords.ts", "tb": "routes/crew/map/truthBits.ts", "df": "routes/session/downFit.ts",
    "slot": "routes/agents/liveSlot.ts", "now": "routes/crew/map/nowLine.ts", "room": "routes/crew/map/nowRoom.ts",
    "turn": "routes/crew/map/turnWords.ts", "rings": "routes/crew/map/rings.ts", "fold": "routes/crew/map/foldRule.ts",
    "fmt": "routes/orchestra/format.ts", "pf": "routes/fleet/pauseFact.ts", "pw": "routes/crew/map/planWords.ts",
}
T0 = 1_700_000_000.0
# the Linux VM rig's map of his (tests/helpers/studio_session_run.py HOPS)
HOPS = {"format": "map/1", "name": "hops", "main": {"agent": "main"},
        "boxes": [{"id": "code", "agent": "coder"}, {"id": "review", "agent": "reviewer"}, {"id": "docs", "agent": "writer"}],
        "lines": [{"from": "main", "to": "code", "when": "always"}, {"from": "code", "to": "review", "when": "always"},
                  {"from": "main", "to": "docs", "when": "main-decides"}]}
NB = "\u00a0"  # r/batch04 entry 3: a number and its unit are held by a no-break space
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


_NODES = """const rec = {id: "r1", agents: D.map((a) => ({id: a.agent_id, key: `h1|s1|${a.agent_id}`, parent: a.parent || null,
  name: a.name, role: "", model: "", state: a.state, reason: "", orphan: !!a.parent && !D.some((b) => b.agent_id === a.parent), row: a}))};
const nodes = rec.agents.map((a) => ({id: a.id, key: a.key, parent: a.orphan ? null : a.parent, name: a.name, role: a.role, model: a.model, state: a.state, card: ""}));
const tags = Object.fromEntries(M.groups.withGroups(nodes, rec).filter((n) => n.group).map((n) => [n.id, [n.group.id, n.group.title]]));
"""


@test
def test_old_rows_get_one_task_number_everywhere(ctx: Ctx):
    """b/batch07 entry 2 (1): a group with no engine n has ONE number (the drawing's: after the largest engine n, over
    every fallback group in start order) in the Live tree, the Timeline (withGroups) and the drawing (autoGroups)."""
    old = [MAIN, kid("c1", 1, step="s1"), kid("c1b", 2, step="s1"), kid("c2", 3), kid("c3", 4, step="s2"), kid("c3b", 5, step="s2")]
    mixed = [MAIN, kid("e1", 1, step="s0", key="task:e", n=2), kid("e2", 2, step="s0", key="task:e", n=2),
             kid("d1", 3, step="s1"), kid("d1b", 4, step="s1"), kid("d2", 5, step="s2"), kid("d2b", 6, step="s2")]
    js = _NODES + """const gs = M.og.autoGroups(D);
const drawn = Object.fromEntries(gs.flatMap((g) => g.members.map((m) => [m.aid, g.name])));
console.log(JSON.stringify({tags, drawn}));"""
    a, b = _run(["groups", "og"], js, old), _run(["groups", "og"], js, mixed)
    ta, da = a.get("tags") or {}, a.get("drawn") or {}
    ctx.check(f"the drawing: s1 'Task 1', the lone row 'Task 2', s2 'Task 3', got {da}",
              da.get("c1") == "Task 1" and da.get("c2") == "Task 2" and da.get("c3") == da.get("c3b") == "Task 3")
    ctx.check(f"the Live tree and the Timeline give each group the drawing's name, got {ta}",
              (ta.get("c1") or [0, ""])[1] == "Task 1" and (ta.get("c3") or [0, ""])[1] == (ta.get("c3b") or [0, ""])[1] == "Task 3")
    tb, db = b.get("tags") or {}, b.get("drawn") or {}
    ctx.check(f"an engine n stays; the old groups number after it (3, 4) in both places, got {tb} {db}",
              [(tb.get(x) or [0, ""])[1] for x in ("e1", "d1", "d2")] == [db.get(x) for x in ("e1", "d1", "d2")] == ["Task 2", "Task 3", "Task 4"])


@test
def test_orphan_roots_children_group_as_before(ctx: Ctx):
    """b/batch07 entry 2 (2): only the children of the session's MAIN are grouped by spawn.group and named by groupName;
    the children of an orphan root (its parent row missing) are grouped by spawn.step and titled by titleOf, as before."""
    rows = [MAIN, kid("p", 1, parent="gone", step="x"),
            kid("o1", 2, parent="p", step="s", task="do the thing", key="task:do the thing", n=1, desc="read A"),
            kid("o2", 3, parent="p", step="s", task="do the thing", key="task:do the thing", n=1, desc="read B"),
            kid("k1", 4, step="1", task="fix it", key="task:fix it", n=2, desc="one"),
            kid("k2", 5, step="2", task="fix it", key="task:fix it", n=2, desc="two")]
    got = _run(["groups"], _NODES + "console.log(JSON.stringify(tags));", rows)
    ctx.check(f"the orphan root's children: one box by spawn.step, titled by titleOf, got {got.get('o1')} {got.get('o2')}",
              got.get("o1") == got.get("o2") == ["t:r1|s", "read A and 1 more"])
    ctx.check(f"main's children: grouped by spawn.group across two replies, named by groupName, got {got.get('k1')} {got.get('k2')}",
              got.get("k1") == got.get("k2") == ["t:r1|task:fix it", "fix it"])


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
def test_group_box_three_a_row_at_200(ctx: Ctx):
    """L9b: three a row when (inner - 16) / 3 is at least 200, each member floor((inner - 16) / 3) wide; else two or one
    a row exactly as before (Agents -> Live's Auto column of L9a is the only one wide enough)."""
    widths = [760, 640, 650, 639, 352, 248, 384, 200]
    got = _run(["lit"], "console.log(JSON.stringify(D.map((w) => M.lit.groupBox(w))));", widths)
    want = [{"inner": 736, "per": 3, "member": 240}, {"inner": 616, "per": 3, "member": 200},
            {"inner": 626, "per": 3, "member": 203}, {"inner": 615, "per": 2, "member": 303.5},
            {"inner": 328, "per": 2, "member": 160}, {"inner": 224, "per": 1, "member": 224},
            {"inner": 360, "per": 2, "member": 176}, {"inner": 176, "per": 1, "member": 176}]
    for w, a, b in zip(widths, got if isinstance(got, list) else [None] * len(widths), want):
        ctx.check(f"groupBox({w}) = {b}, got {a}", a == b)


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


# ---------------------------------------------------------------------------------------------- 4. words, lines, cards

def _m(aid: str, state: str = "working", *, who: str = "researcher", desc: str = "", model: str = "kimi-k3", cost: float = 0.0,
       reason: str = "", made: bool = False, t: float = 0.0, ended: float = 0.0, by: str = "", raw: str = "") -> dict:
    """A stand-in member; `raw` (3.6.0.13 L1: the row's own state) defaults from its BoxState."""
    raw = raw or {"working": "running", "waiting": "waiting", "done": "done", "failed": "failed"}.get(state, state)
    m = {"aid": aid, "parent": by or "main", "who": who, "description": desc, "model": model, "state": state, "cost": cost,
         "reason": reason, "made": made, "started": T0 + t if t else 0, "ended": T0 + ended if ended else 0, "raw": raw}
    if by:
        m["by"] = by
    return m


def _grp(n: int, members: list, name: str = "compare the three reports") -> dict:
    return {"n": n, "key": f"task:{name}", "by": "task", "name": name, "members": members, "first": T0 + 1}


def _rec(rows: list) -> list:
    return [{"id": r["agent_id"], "key": f"h|S|{r['agent_id']}", "name": r["name"], "state": r["state"], "row": r} for r in rows]


@test
def test_group_words(ctx: Ctx):
    three = _grp(1, [_m("a", desc="read report A", cost=0.01, t=1), _m("b", desc="read report B", cost=0.01, t=2),
                     _m("c", desc="read report C", cost=0.02, t=3)])
    each = _grp(2, [_m("a", "working"), _m("b", "waiting"), _m("c", "done"), _m("d", "failed", cost=0.5)], name="x")
    one = _grp(3, [_m("a", "working")], name="fix the login bug")
    done = _grp(4, [_m("a", "done", cost=0.03, t=1, ended=60), _m("b", "done", cost=0.03, t=5, ended=100),
                    _m("c", "done", cost=0.03, t=10, ended=126)], name="d")
    js = """const g = M.gw, out = {};
for (const [k, x] of Object.entries(D.groups)) out[k] = {line: g.countsLine(x), parts: g.countParts(x)};
out.member = [g.memberLine(D.m1), g.memberState(D.m1)];
out.bare = [g.memberLine(D.m2), g.memberState(D.m2)];
out.third = g.startedBy("researcher", "read report A");
out.more = g.moreMembers(2);
out.span = [g.span(59), g.span(60), g.span(125), M.fmt.cost(0.1)];
console.log(JSON.stringify(out));"""
    got = _run(["gw", "fmt"], js, {"groups": {"three": three, "each": each, "one": one, "done": done},
                            "m1": _m("a", desc="read report A"), "m2": _m("b", "done", who="agent", model="")})
    ctx.check(f"3 working at $0.0400, got {got['three']['line']!r}", got["three"]["line"] == "3 agents · 3 working · $0.0400")
    ctx.check(f"every part in order, failed its own (--bad) part, got {got['each']}",
              got["each"]["line"] == "4 agents · 1 working · 1 waiting on you · 1 done · 1 failed · $0.5000"
              and [p.get("bad", False) for p in got["each"]["parts"]] == [False, False, False, False, True, False]
              and [p.get("warn", False) for p in got["each"]["parts"]] == [False, False, True, False, False, False])
    ctx.check(f"one member: '1 agent', zero parts and a zero cost left out, got {got['one']['line']!r}",
              got["one"]["line"] == "1 agent · 1 working")
    ctx.check(f"all done over 125 s: the done form, got {got['done']['line']!r}", got["done"]["line"] == f"3 agents · all done · $0.0900 · 2{NB}min")
    ctx.check(f"a member's two lines, got {got['member']}", got["member"] == ["researcher · Goal: read report A", "kimi-k3 · working"])  # 3.6.0.23 PV: "Goal"
    ctx.check(f"no description: who alone; no model: the state alone, got {got['bare']}", got["bare"] == ["agent", "done"])
    ctx.check(f"the third line, got {got['third']!r}", got["third"] == "started by researcher: read report A")
    ctx.check(f"+2 more, got {got['more']!r}", got["more"] == "+2 more")
    ctx.check(f"span, and an amount as the box heads write it, got {got['span']}", got["span"] == [f"59{NB}s", f"1{NB}min", f"2{NB}min", "$0.1000"])


@test
def test_workflow_block_takes_a_group_colour(ctx: Ctx):
    rows = [MAIN, kid("w1", 1, step="1", key="workflow:review#tu1", n=3, by="workflow", name="coder",
                      crew={"workflow": "review", "step": 1, "agent": "coder"})]
    ev = [{"event": "map_step", "data": {"map": "auto", "box": "workflow:review", "workflow": "review", "kind": "start",
                                         "steps": ["code", "review"], "t": T0}},
          {"event": "map_step", "data": {"map": "auto", "box": "workflow:review", "workflow": "review", "kind": "step", "n": 1,
                                         "name": "code", "state": "running", "t": T0}}]
    js = """const ov = M.ov.overlay({boxes: [], lines: []}, D.rows, D.ev, %s, {plain: true});
const gs = M.og.autoGroups(D.rows, ov.blocks), v = M.lit.autoView(M.view.view(D.auto, [], []), gs);
console.log(JSON.stringify({box: v.boxes.find((b) => b.group), steps: gs[0].steps, head: M.tb.blockHead("review", 1, gs[0].steps.length)}));""" % (T0 + 30)
    got = _run(["ov", "og", "view", "lit", "tb"], js, {"rows": rows, "ev": ev, "auto": AUTO})
    box = got.get("box") or {}
    ctx.check(f"a workflow run of n 3 takes colour 3, got {box.get('group')}", (box.get("group") or {}).get("colour") == 3)
    ctx.check(f"its steps as R14's rows, step 1 working, got {got.get('steps')}",
              [s.get("state") for s in got.get("steps") or []] == ["working", "next"])
    ctx.check(f"its head while it runs, got {got.get('head')!r}", got.get("head") == "workflow review · step 1 of 2")


@test
def test_five_groups_colour_five_is_colour_one(ctx: Ctx):
    rows = [MAIN] + [kid(f"k{i}", i, step=str(i), task=f"task {i}", key=f"task:task {i}", n=i) for i in range(1, 6)]
    js = """const gs = M.og.autoGroups(D.rows, {}), v = M.lit.autoView(M.view.view(D.auto, [], []), gs);
console.log(JSON.stringify(v.boxes.filter((b) => b.group).map((b) => [b.group.colour, b.name])));"""
    got = _run(["og", "view", "lit"], js, {"rows": rows, "auto": AUTO})
    ctx.check(f"colours 1, 2, 3, 4, 1, got {got}", [c for c, _ in got] == [1, 2, 3, 4, 1])
    ctx.check(f"the five names differ, got {[n for _, n in got]}", len({n for _, n in got}) == 5)


@test
def test_grandchild_has_three_lines(ctx: Ctx):
    rows = [MAIN, kid("c1", 1, step="1", task="look", key="task:look", n=1, desc="read report A", name="researcher"),
            kid("c2", 3, parent="c1", step="1", task="look", key="task:look", n=1, desc="check a figure", name="reviewer")]
    js = """const gs = M.og.autoGroups(D.rows, {}), g = gs[0];
console.log(JSON.stringify(g.members.map((m) => [M.gw.memberLine(m), M.gw.memberState(m), M.gw.thirdLine(g, m)])));"""
    got = _run(["og", "gw"], js, {"rows": rows})
    ctx.check(f"main's child two lines, its child three, got {got}",
              got == [["researcher · Goal: read report A", "working", ""], ["reviewer · Goal: check a figure", "working", "started by researcher: read report A"]])


@test
def test_line_live_from_rows_then_trace(ctx: Ctx):
    g1 = _grp(1, [_m("a", "working", t=1), _m("b", "done", t=4)], name="one")
    g2 = _grp(2, [_m("c", "done", t=9), _m("d", "done", t=10), _m("e", "done", t=11)], name="two")
    hop = {"event": "map_hop", "data": {"from": "main", "to": "group:1", "state": "start", "t": T0 + 99, "task": "x"}}
    js = """const t = M.hops.groupTotals(D.gs), l = [...M.hops.groupLive(D.gs)];
M.hops.foldHop(t, D.hop);
console.log(JSON.stringify({t, l, again: M.hops.groupTotals(D.gs), live2: [...M.hops.groupLive(D.gs)]}));"""
    got = _run(["hops"], js, {"gs": [g1, g2], "hop": hop})
    t = got.get("t") or {}
    ctx.check(f"main>group:n counted from its members, the newest group's key last, got {t}",
              t.get("lines") == {"main>group:1": {"n": 2, "last": T0 + 4, "task": "one", "off": False},
                                 "main>group:2": {"n": 3, "last": T0 + 11, "task": "two", "off": False}}
              and t.get("last") == "main>group:2" and t.get("flight") == {})
    ctx.check(f"live: only a group with a working member, got {got.get('l')}", got.get("l") == ["main>group:1"])
    ctx.check("a map_hop frame changes neither (they read rows, not frames)", got.get("again") == t and got.get("live2") == ["main>group:1"])


@test
def test_every_member_says_why_this_model(ctx: Ctx):
    mem = _m("k1", desc="read report A", cost=0.01, reason="code work; tools; mid budget", t=10)
    bare = _m("k2", "done", who="coder", desc="fix it", model="", t=10, ended=15)
    rows = [MAIN, kid("k1", 10, step="1", task="look", key="task:look", n=1, desc="read report A", name="researcher",
                      model="kimi-k3", model_reason="code work; tools; mid budget"),
            kid("k3", 12, step="1", task="look", key="task:look", n=1, desc="read report C", name="researcher", state="done")]
    js = """const gs = M.og.autoGroups(D.rows, {});
const t = M.sit.stepIn({kind: "member", aid: "k1", text: "x"}, D.rec, null, gs);
const e = M.sit.stepIn({kind: "member", aid: "k3", text: "x"}, D.rec, null, gs);
console.log(JSON.stringify({g4: M.gw.g4Lines(D.mem, %s), bare: M.gw.g4Lines(D.bare, %s), t, e}));""" % (T0 + 50, T0 + 99)
    got = _run(["og", "gw", "sit"], js, {"rows": rows, "rec": _rec(rows), "mem": mem, "bare": bare})
    ctx.check(f"G4 with a reason, got {got.get('g4')}",
              got.get("g4") == ["read report A", "researcher on kimi-k3", "Why this model: code work; tools; mid budget", f"working · $0.0100 · 40{NB}s"])
    ctx.check(f"G4 without one (and no model; an ended member's own time), got {got.get('bare')}",
              got.get("bare") == ["fix it", "coder", "Why this model: named by main or by your settings", f"done · $0.0000 · 5{NB}s"])
    t, e = got.get("t") or {}, got.get("e") or {}
    ctx.check(f"the member's card: the same why line, its who, the member live, got {t}",
              t.get("id") == "member:k1" and t.get("title") == "researcher" and t.get("why") == "Why this model: code work; tools; mid budget"
              and [w.get("aid") for w in t.get("who") or []] == ["k1"])
    ctx.check(f"an ended member: no row to press, got {e}", e.get("who") == [] and str(e.get("why")).startswith("Why this model: "))


@test
def test_group_head_hover_and_card(ctx: Ctx):
    rows = [MAIN, kid("k1", 1, step="1", task="compare", key="task:compare", n=2, desc="read A", name="researcher", model="kimi-k3", cost_usd=0.04),
            kid("k2", 2, step="1", task="compare", key="task:compare", n=2, desc="read B", name="researcher", model="kimi-k3", state="done",
                cost_usd=0.05),
            kid("k3", 3, step="1", task="compare", key="task:compare", n=2, desc="read C", name="coder", state="waiting")]
    js = """const gs = M.og.autoGroups(D.rows, {});
const c = M.sit.stepIn({kind: "group", n: 2, text: "3 agents"}, D.rec, null, gs);
const l = M.sit.stepIn({kind: "line", from: "main", to: "group:2", text: "x", off: false}, D.rec, null, gs);
console.log(JSON.stringify({g3: M.gw.g3Lines(gs[0]), at: M.tw.clock(gs[0].first), c, l}));"""
    got = _run(["og", "gw", "sit", "tw"], js, {"rows": rows, "rec": _rec(rows)})
    ctx.check(f"G3, got {got.get('g3')}", got.get("g3") == ["compare", f"Started by main at {got.get('at')}", "researcher · kimi-k3 · working",
                                                            "researcher · kimi-k3 · done", "coder · waiting on you", "$0.0900"])
    c = got.get("c") or {}
    ctx.check(f"the group's card: its name, a row per LIVE member in start order, got {c}",
              c.get("id") == "group:2" and c.get("title") == "compare" and [w.get("aid") for w in c.get("who") or []] == ["k1", "k3"])
    ln = got.get("l") or {}
    ctx.check(f"main's line into the group opens the same card (no inner id read), got {ln}",
              ln.get("title") == "compare" and [w.get("aid") for w in ln.get("who") or []] == ["k1", "k3"])


@test
def test_an_all_done_groups_card_lists_every_member(ctx: Ctx):
    """3.6.0.15 O2-9: a group whose members are ALL done folds to its head (L8: its members' boxes hidden), so its card is
    the one door to them: it has a row per member, in start order, so one can be chosen and given a model (the MODEL block
    is the chosen row's). A group with a member still live keeps a row per LIVE member; one with a failed or stopped
    member (it never folds: its boxes stay) keeps today's rows."""
    def grp(states: list) -> list:
        return [MAIN, *[kid(f"k{i}", i, step="1", task="tidy", key="task:tidy", n=len(states), desc=f"part {i}", name=f"w{i}", state=s)
                        for i, s in enumerate(states, 1)]]
    cases = {"done": grp(["done", "done"]), "live": grp(["done", "running"]), "stopped": grp(["done", "stopped"])}
    js = """const out = {};
for (const [k, rows] of Object.entries(D.cases)) {
  const gs = M.og.autoGroups(rows, {});
  out[k] = M.sit.stepIn({kind: "group", n: gs[0].n, text: "2 agents"}, D.rec[k], null, gs).who.map((w) => [w.aid, w.name]);
}
console.log(JSON.stringify(out));"""
    got = _run(["og", "sit"], js, {"cases": cases, "rec": {k: _rec(v) for k, v in cases.items()}})
    ctx.check(f"all done: a row per member, in start order, got {got.get('done')}", got.get("done") == [["k1", "w1"], ["k2", "w2"]])
    ctx.check(f"one still live: its row only, got {got.get('live')}", got.get("live") == [["k2", "w2"]])
    ctx.check(f"done and stopped (never folds): no row, as before, got {got.get('stopped')}", got.get("stopped") == [])


@test
def test_g5_lists_the_start_agents(ctx: Ctx):
    names = [f"a{i}" for i in range(1, 15)]
    js = "console.log(JSON.stringify({a: M.gw.g5Lines('glm-5', D), b: M.gw.g5Lines('glm-5', []), c: M.gw.g5Lines('glm-5', D.slice(0, 2))}));"
    got = _run(["gw"], js, names)
    ctx.check(f"14 names: twelve, then ' and 2 more' (no comma before and), got {got.get('a')}",
              got.get("a") == ["main · glm-5", "Can hand work to: " + ", ".join(names[:12]) + " and 2 more"])
    ctx.check(f"none: the first line only, got {got.get('b')}", got.get("b") == ["main · glm-5"])
    ctx.check(f"two, got {got.get('c')}", got.get("c") == ["main · glm-5", "Can hand work to: a1, a2"])
    # R8 (3.6.0.13 L3): before its first request main's hover is mainHover(..., null, null), the same G5 lines byte for byte
    js = ("const h = (n) => M.turn.mainHover('glm-5', n, null, null);"
          "console.log(JSON.stringify({a: h(D), b: h([]), c: h(D.slice(0, 2))}));")
    hv = _run(["turn"], js, names)
    ctx.check(f"main's hover before the first request is G5's, got {hv}",
              hv.get("a") == got.get("a") and hv.get("b") == got.get("b") and hv.get("c") == got.get("c"))


@test
def test_main_sheet_names_every_kind_it_was_told(ctx: Ctx):
    """3.6.0.14 O1-4: main's sheet says "Told it can start: {every name}" (+ " and {n} more", n what main itself read as
    more), never the hover's first twelve; nothing told (null, or no names): no line."""
    names = [f"k{i}" for i in range(1, 15)]
    js = """const t = M.turn;
console.log(JSON.stringify({all: t.toldEvery({names: D, more: 2}), none: t.toldEvery({names: D.slice(0, 2), more: 0}),
  nul: t.toldEvery(null), empty: t.toldEvery({names: [], more: 3})}));"""
    got = _run(["turn"], js, names)
    ctx.check(f"fourteen names and 2 more: every name, then ' and 2 more', got {got.get('all')!r}",
              got.get("all") == "Told it can start: " + ", ".join(names) + " and 2 more")
    ctx.check(f"no more: no tail, got {got.get('none')!r}", got.get("none") == "Told it can start: k1, k2")
    ctx.check(f"null told or no names: '', got {got.get('nul')!r} {got.get('empty')!r}", got.get("nul") == "" == got.get("empty"))


@test
def test_turn_line_and_mains_hover(ctx: Ctx):
    """L3 with R5, R8 and the coordinator's ruling: TURN's words (a zero part left out, "1 helper", "1 tool", both zero
    or no turn: blank), its held rows (two at 224 px, three at 160 px), and main's hover once main was told its kinds."""
    names = [f"k{i}" for i in range(1, 15)]
    js = """const t = M.turn, out = {};
out.lines = [t.turnLine({helpers: 5, tools: 4}), t.turnLine({helpers: 1, tools: 1}), t.turnLine({helpers: 3, tools: 0}),
             t.turnLine({helpers: 0, tools: 2}), t.turnLine(null), t.turnLine(undefined), t.turnLine({helpers: 0, tools: 0})];
out.sample = [t.TURN_SAMPLE, t.TURN_SAMPLE.length, t.turnRows(224), t.turnRows(160)];
out.before = [t.mainHover('glm-5', D, null, null), M.gw.g5Lines('glm-5', D)];
out.told = t.mainHover('glm-5', D, {names: D, more: 2}, {helpers: 12, tools: 30});
out.few = t.mainHover('', [], {names: ['coder', 'writer'], more: 0}, {helpers: 1, tools: 0});
out.zero = t.mainHover('glm-5', [], {names: ['coder'], more: 0}, {helpers: 0, tools: 0});
out.cut = t.mainHover('glm-5', [], {names: ['coder'], more: 3}, null);
console.log(JSON.stringify(out));"""
    got = _run(["turn", "gw"], js, names)
    ctx.check(f"TURN's words, letter for letter, got {got.get('lines')}", got.get("lines") == [
        "This turn: started 5 helpers · used 4 tools itself", "This turn: started 1 helper · used 1 tool itself",
        "This turn: started 3 helpers", "This turn: used 2 tools itself", "", "", ""])
    ctx.check(f"R5: the longest usual words (52 characters) hold 2 rows at 224 px and 3 at 160 px, got {got.get('sample')}",
              got.get("sample") == ["This turn: started 12 helpers · used 14 tools itself", 52, 2, 3])
    before = got.get("before") or [[], None]
    ctx.check(f"told null: g5Lines exactly, got {before}", before[0] == before[1])
    ctx.check(f"told 14 names and 2 more: twelve, then ' and 4 more', got {got.get('told')}", got.get("told") == [
        "main · glm-5", "This session: started 12 helpers · used 30 tools itself",
        "Told it can start: " + ", ".join(names[:12]) + " and 4 more"])
    ctx.check(f"no model: 'main'; a zero part left out, got {got.get('few')}", got.get("few") == [
        "main", "This session: started 1 helper", "Told it can start: coder, writer"])
    ctx.check(f"both session counts zero: no 'This session' line, got {got.get('zero')}",
              got.get("zero") == ["main · glm-5", "Told it can start: coder"])
    ctx.check(f"kinds_more alone counts in ' and {{n}} more', got {got.get('cut')}",
              got.get("cut") == ["main · glm-5", "Told it can start: coder and 3 more"])


# React, the feed, the stores, the pick and built.ts stood in for (as tests/test_map_overlay.py LIT_HOOK does)
_REACT = ("export const useCallback = (f) => f, useLayoutEffect = () => {}, useRef = (v) => ({current: v}), "
          "useState = (v) => [v, () => {}], useMemo = (f) => f();")
_HOOK = r"""const STUB = %s, LIT = %s;
export async function resolve(spec, ctx, next) {
  if (spec === 'react') return { url: STUB, shortCircuit: true };
  const r = await next(spec, ctx);
  if (/[\/-](events|store|pick|built)\.(ts|mjs)$/.test(r.url)) return { url: LIT, shortCircuit: true };
  return r; }"""


def _stubbed(module: str, body: str) -> dict:
    """`body` runs with `m` = the module, its neighbours stood in for."""
    import urllib.parse
    from tests.helpers import node_ts
    from tests.test_map_overlay import LIT_STUB
    url = lambda src: json.dumps("data:text/javascript," + urllib.parse.quote(src))  # noqa: E731
    hook = _HOOK % (url(_REACT), url(LIT_STUB))
    return node_ts.run(f"""import {{ register }} from 'node:module';
register('data:text/javascript,' + encodeURIComponent({json.dumps(hook)}));
globalThis.__on = {{}}; globalThis.__ups = 0;
const m = await import({json.dumps((SRC / module).resolve().as_uri())});
{body}""")


@test
def test_old_rows_on_starter_are_auto(ctx: Ctx):
    import re
    js = """const row = {sid: "S", title: "S", map: "starter", started: 1, live: 1};
const shop = {sid: "T", title: "T", map: "shop", started: 2, live: 1};
console.log(JSON.stringify({chosen: m.chosen([shop, row], "", "auto")?.sid || null, his: m.chosen([row, shop], "", "shop")?.sid || null,
  owns: [m.ownsMap("starter", {map: "auto"}), m.ownsMap("auto", {map: "auto"}), m.ownsMap("shop", {map: "auto"}), m.ownsMap("shop")],
  lit: m.toLit({session_id: "S", map: "auto", map_plain: true, map_agents: ["coder", 3]}),
  none: m.toLit({session_id: "N", map: null, map_plain: true}), hisRow: m.toLit({session_id: "H", map: "shop", map_plain: true})}));"""
    got = _stubbed("routes/crew/map/litStore.ts", js)
    ctx.check(f"a row on 'starter' is the session lit for Auto, got {got.get('chosen')}", got.get("chosen") == "S")
    ctx.check(f"his map shop still finds its own row, got {got.get('his')}", got.get("his") == "T")
    ctx.check(f"ownsMap: starter and auto own Auto, shop does not, no show owns, got {got.get('owns')}",
              got.get("owns") == [True, True, False, True])
    lit, none = got.get("lit") or {}, got.get("none") or {}
    ctx.check(f"toLit: auto from map_plain, map_agents kept as strings, got {lit}", lit.get("auto") is True and lit.get("map_agents") == ["coder", "3"])
    ctx.check(f"a session with no map: not auto (its drawing as today), got {none}", none.get("auto") is False and none.get("plain") is True)
    ctx.check(f"a row naming his map shop is never drawn as groups, even when it says map_plain, got {got.get('hisRow')}",
              (got.get("hisRow") or {}).get("auto") is False)
    src = (SRC / "routes/crew/map/litStore.ts").read_text(encoding="utf-8") + (SRC / "routes/crew/map/LitMini.tsx").read_text(encoding="utf-8")
    ctx.check("no === between map names left in litStore.ts and LitMini.tsx",
              not re.search(r"(?<!typeof )\b\w+\.map\s*===|===\s*\w+\.map\b|===\s*shown\b", src))  # `typeof s.map ===` is no compare


@test
def test_member_and_group_cards_mark_their_box(ctx: Ctx):
    js = """const c = (id) => ({id, title: "", text: "", who: [], sender: ""});
console.log(JSON.stringify([
  m.selected(c("group:2"), "group:2", undefined, ["k1"]), m.selected(c("member:k1"), "group:2", undefined, ["k1"]),
  m.selected(c("member:k9"), "group:2", undefined, ["k1"]), m.selected(c("group:2"), "group:3", undefined, ["k5"]),
  m.selected(c("group:2"), "group:2"), m.selected(c("box:code"), "code"), m.selected(c("head:W"), "workflow:W", "W"),
  m.selected(c("member:k1"), "code"), m.selected(null, "group:2", undefined, ["k1"])]));"""
    got = _stubbed("routes/crew/map/runFrame.ts", js)
    ctx.check(f"a group card and a member's card mark the group's box; every call without members as today, got {got}",
              got == [True, True, False, False, False, True, True, False, False])


@test
def test_no_fetch_or_timer_in_group_files(ctx: Ctx):
    """B25: nothing in (b) adds a fetch, a timer or a network call (green before and after: a guard). 3.6.0.13 L6: the
    files of NOW, TURN, the rings and the cover too, and no requestAnimationFrame( either; a listed file that is missing fails."""
    import re
    bad, missing = {}, []
    for f in ("GroupBlock.tsx", "GroupMember.tsx", "groupWords.ts", "overlayGroups.ts", "litView.ts", "nowLine.ts", "nowRoom.ts",
              "turnWords.ts", "rings.ts", "useRings.ts", "cover.ts", "foldRule.ts"):
        p = SRC / "routes/crew/map" / f
        if not p.is_file():
            missing.append(f)
            continue
        hits = re.findall(r"\b(?:fetch|setInterval|setTimeout|api|requestAnimationFrame)\(|\bapi\.", p.read_text(encoding="utf-8"))
        if hits:
            bad[f] = hits
    ctx.check(f"every listed file exists, missing {missing}", not missing)
    ctx.check(f"no fetch(, setInterval(, setTimeout(, api(, requestAnimationFrame( in the group files, got {bad}", not bad)


# ---------------------------------------------------------------------------------------------- 5. (batch 6) the slot, the doors

def _box(n: int, y: float, members: list) -> dict:
    return {"id": f"group:{n}", "x": 12, "y": y, "w": 384, "h": 150, "rank": 1, "row": n,
            "group": {"n": n, "key": f"task:t{n}", "colour": (n - 1) % 4 + 1, "members": members}}


@test
def test_slot_names_the_working_group(ctx: Ctx):
    """B26: the slot names the working group wholly below the visible part (the lowest n); its words, letter for letter."""
    boxes = [{"id": "main", "x": 12, "y": 12, "w": 384, "h": 80, "rank": 0, "row": 0},
             _box(1, 100, ["a"]), _box(2, 300, ["b"]), _box(3, 500, ["c"]), _box(4, 700, ["d"])]
    calm = [_grp(1, [_m("a")], "one"), _grp(2, [_m("b", "done")], "two"), _grp(3, [_m("c", "waiting"), _m("c2")], "three"),
            _grp(4, [_m("d")], "four")]
    two = [_grp(1, [_m("a")], "one"), _grp(2, [_m("b")], "two"), _grp(3, [_m("c", "done")], "three"), _grp(4, [_m("d", "done")], "four")]
    none = [_grp(n, [_m(x, "done")], x) for n, x in ((1, "a"), (2, "b"), (3, "c"), (4, "d"))]
    js = """const w = (gs, k, top, h, bx = D.boxes) => M.df.workingBelow(bx, gs, k, top, h)?.id ?? null;
console.log(JSON.stringify({
  lowest: w(D.calm, 1, 0, 290), two: w(D.two, 1, 0, 290), above: w(D.two, 1, 400, 290), none: w(D.none, 1, 0, 290),
  zoom: w(D.calm, 2, 0, 900), edge: w(D.calm, 1, 10, 290), his: w(D.calm, 1, 0, 290, D.boxes.map(({group, ...b}) => b)),
  words: [M.gw.belowGroup("fix the login bug", 0), M.gw.belowGroup("fix the login bug", 2)]}));"""
    got = _run(["df", "gw"], js, {"boxes": boxes, "calm": calm, "two": two, "none": none})
    ctx.check(f"group 3 (its member working, group 2's done) is named, not group 4, got {got.get('lowest')}", got.get("lowest") == "group:3")
    ctx.check(f"the lowest n with a working member wins, got {got.get('two')}", got.get("two") == "group:2")
    ctx.check(f"a working group in view or above is not below, got {got.get('above')}", got.get("above") is None)
    ctx.check(f"nothing working below: null, got {got.get('none')}", got.get("none") is None)
    ctx.check(f"the zoom counts: at 200 % group 3 starts at 1000 >= 900, got {got.get('zoom')}", got.get("zoom") == "group:3")
    ctx.check(f"a box whose top is at the view's foot (300 >= 10 + 290) is below, got {got.get('edge')}", got.get("edge") == "group:3")
    ctx.check(f"boxes with no group (a map of his): null, got {got.get('his')}", got.get("his") is None)
    ctx.check(f"the two section-3 forms letter for letter, got {got.get('words')}",
              got.get("words") == ["↓ fix the login bug · working", "↓ fix the login bug · working · and 2 more groups below"])


@test
def test_focus_is_stored_and_taken_once(ctx: Ctx):
    """B27: a group card's Open in Agents -> Live stores {sid, n}; the drawing of that session takes it once."""
    js = """const before = m.lit.get().focus;
m.focusGroup("s1", 3);
const stored = m.lit.get().focus;
const other = m.takeFocus("s2"), kept = m.lit.get().focus;
const once = m.takeFocus("s1"), twice = m.takeFocus("s1");
console.log(JSON.stringify({before, stored, other, kept, once, twice, after: m.lit.get().focus}));"""
    got = _stubbed("routes/crew/map/litStore.ts", js)
    ctx.check(f"no focus at first, got {got.get('before')!r}", got.get("before") is None)
    ctx.check(f"focusGroup stores {{sid, n}}, got {got.get('stored')}", got.get("stored") == {"sid": "s1", "n": 3})
    ctx.check(f"another session takes nothing and leaves it, got {got.get('other')!r} {got.get('kept')}",
              got.get("other") is None and got.get("kept") == {"sid": "s1", "n": 3})
    ctx.check(f"its session takes n once, then null, and the store is cleared, got {got.get('once')} {got.get('twice')} {got.get('after')}",
              got.get("once") == 3 and got.get("twice") is None and got.get("after") is None)
    src = (SRC / "routes/crew/map/StepIn.tsx").read_text(encoding="utf-8")
    ctx.check("StepIn: a group card's Open in Agents -> Live stores the group before the drawing's door",
              "focusGroup(" in src and src.index("focusGroup(") < src.index("onLive()"))


@test
def test_scroll_answer_changes_only_with_the_slot(ctx: Ctx):
    """b/batch07 entry 3: Agents -> Live on Auto re-renders on a scroll only when the slot's answer (the group it names and
    the count below) changes (routes/agents/liveSlot.ts slotAnswer, sameAnswer); a stored focus is taken when its group is
    placed and dropped at a full draw that has not placed it (focusStep)."""
    boxes = [{"id": "main", "x": 12, "y": 12, "w": 384, "h": 80, "rank": 0, "row": 0}] + [
        _box(i, 100 + 200 * (i - 1), [f"m{i}"]) for i in range(1, 13)]
    gs = [_grp(i, [_m(f"m{i}", "working" if i == 12 else "done")], f"g{i}") for i in range(1, 13)]
    js = """const ans = (top) => M.slot.slotAnswer(D.boxes, D.gs, 1, top, 290);
const walk = (from) => { let last = ans(from), sets = 0; for (let i = 1; i <= 40; i++) { const a = ans(from + 2 * i); if (!M.slot.sameAnswer(last, a)) { sets++; last = a; } } return sets; };
const f = {sid: "s1", n: 3};
console.log(JSON.stringify({inside: walk(300), across: walk(400), first: ans(300), none: M.slot.slotAnswer(D.boxes, undefined, 1, 300, 290),
  same: [M.slot.sameAnswer(null, null), M.slot.sameAnswer({n: 1, more: 2}, {n: 1, more: 3}), M.slot.sameAnswer(null, {n: 1, more: 0})],
  focus: [M.slot.focusStep(f, "s1", true, true), M.slot.focusStep(f, "s1", false, true), M.slot.focusStep(f, "s1", false, false),
          M.slot.focusStep(f, "s2", false, true), M.slot.focusStep(null, "s1", false, true)]}));"""
    got = _run(["slot"], js, {"boxes": boxes, "gs": gs})
    ctx.check(f"the slot names group 12 with 8 more below (groups 4-12 below the view), got {got.get('first')}",
              got.get("first") == {"n": 12, "more": 8})
    ctx.check(f"40 small scroll steps inside one group's span: no new answer, got {got.get('inside')}", got.get("inside") == 0)
    ctx.check(f"40 steps across one box's edge: one new answer (at most 2), got {got.get('across')}", got.get("across") == 1)
    ctx.check(f"no groups (a map of his): no answer, got {got.get('none')}", got.get("none") is None)
    ctx.check(f"sameAnswer compares the group and the count, got {got.get('same')}", got.get("same") == [True, False, False])
    ctx.check(f"a stored focus: taken when placed, dropped at a full draw without it, kept until then and for another session, got {got.get('focus')}",
              got.get("focus") == ["take", "drop", "wait", "wait", "none"])
    src = (SRC / "routes/agents/LiveDraw.tsx").read_text(encoding="utf-8")
    ctx.check("LiveDraw: one requestAnimationFrame per burst of scrolls, cancelled when the view leaves; the end listener once",
              "requestAnimationFrame(" in src and "cancelAnimationFrame(" in src and "{ once: true }" in src and "sameAnswer(" in src)


@test
def test_slot_twin_holds_a_long_name_of_ordinary_letters(ctx: Ctx):
    """b/batch08 entry 1: Session's slot on Auto is sized by a hidden twin whose text is the slot's own words function
    (groupWords.ts belowGroup) called with one exported 60-character sample of ordinary letters and a two-digit count."""
    sample = "compare the three reports and write the summary for the team"
    js = """console.log(JSON.stringify({sample: M.gw.BELOW_SAMPLE ?? null, room: M.gw.slotWords(M.gw.BELOW_SAMPLE ?? "", "under", 99)}));"""
    got = _run(["gw"], js, {})
    ctx.check(f"groupWords exports BELOW_SAMPLE, the 60-character sample, got {got.get('sample')!r}",
              got.get("sample") == sample and len(sample) == 60)
    ctx.check(f"the twin's words: the slot's longest form (3.6.0.13 L4) with the sample and 99, got {got.get('room')!r}",
              got.get("room") == f"{sample} · waits on you · under the open box · and 99 more groups below")
    src = (SRC / "routes/session/MapDown.tsx").read_text(encoding="utf-8")
    ctx.check("MapDown: the twin's text is slotWords(BELOW_SAMPLE, \"under\", 99), no row of capital W's",
              'slotWords(BELOW_SAMPLE, "under", 99)' in src and '"W".repeat(' not in src)


@test
def test_live_slot_hears_the_fits_observer(ctx: Ctx):
    """b/batch08 entry 2: Agents -> Live's slot answer is also worked out when the view's size changes, told by the ONE
    ResizeObserver the fit already has (lib/canvasNav.ts), through the same once-a-frame path as a scroll; no second
    observer and no timer in LiveDraw.tsx (the browser half: tests.test_studio_auto_groups)."""
    nav = (SRC / "lib/canvasNav.ts").read_text(encoding="utf-8")
    live = (SRC / "routes/agents/LiveDraw.tsx").read_text(encoding="utf-8")
    ro = nav[nav.index("new ResizeObserver("):]
    ctx.check("canvasNav: its observer tells the canvas's `resized` on every size change, before the width-only fit check",
              "resized?: () => void" in nav and ro.index("resized?.()") < ro.index("if (now === width"))
    ctx.check("LiveDraw: `resized` on Auto while shown goes through onScroll (one frame, set only when the answer differs) and "
              "the same one observer tells the drawing the view's width (L9a: seeView, Auto's group column)",
              "resized: s.auto && shown ? () => (onScroll(), seeView()) : undefined" in live)
    ctx.check("LiveDraw: no observer and no timer of its own",
              "ResizeObserver" not in live and "setTimeout(" not in live and "setInterval(" not in live)
    ctx.check(f"LiveDraw.tsx stays under 250 lines, got {live.count(chr(10))}", live.count("\n") < 250)


@test
def test_ask_door_lands_on_the_group_on_auto(ctx: Ctx):
    """M6-M8, the owner's point 24: on Auto an ask's Open lands on the asker's group (no box of the PlainMap is drawn)."""
    rows = [MAIN, kid("k1", 1, step="1", task="a", key="task:a", n=1), kid("k2", 2, step="2", task="b", key="task:b", n=2),
            kid("k3", 3, parent="k2", step="3", key="task:b", n=2)]
    js = """const ov = M.ov.overlay({boxes: [], lines: []}, D.rows, [], %s, {plain: true});
const gs = M.og.autoGroups(D.rows, ov.blocks);
const p = (aid, g) => M.sit.placeOf(aid, ov, D.rec, g);
console.log(JSON.stringify({k2: p("k2", gs), k3: p("k3", gs), main: p("main", gs), stranger: p("zz", gs),
  bare: [p("k2"), p("k3"), p("main"), p("zz")]}));""" % (T0 + 60)
    got = _run(["ov", "og", "sit"], js, {"rows": rows, "rec": _rec(rows)})
    ctx.check(f"a member of group 2 lands on its group, got {got.get('k2')}", got.get("k2") == {"box": "group:2", "member": "k2"})
    ctx.check(f"a child of a child lands on its parent's group, got {got.get('k3')}", got.get("k3") == {"box": "group:2", "member": "k3"})
    ctx.check(f"main lands on main, got {got.get('main')}", got.get("main") == {"box": "main"})
    ctx.check(f"an agent in no group: null (the door's own path), got {got.get('stranger')!r}", got.get("stranger") is None)
    ctx.check(f"without groups placeOf answers as before (main's kids on main), got {got.get('bare')}",
              got.get("bare") == [{"box": "main"}, {"box": "main"}, {"box": "main"}, None])
    src = (SRC / "routes/crew/map/askBox.ts").read_text(encoding="utf-8")
    ctx.check("askBox: the door passes the drawing's groups and a group's box opens the member's card",
              "L.groups" in src and 'kind: "member"' in src)


# ---------------------------------------------------------------------------------------------- 6. (k/batch02) main holds still
@test
def test_mains_box_holds_its_fullest_height_on_auto(ctx: Ctx):
    """k/batch02 entry 1: on Auto main's box has the height of its fullest state from the first draw -- a hidden twin of
    the row "main · working · {what it does}" and of the clock's "waiting for a model reply · {s}" holds their room when
    they are empty (groupWords.ts MAIN_HOLD) -- and a box marked `data-hold` never measures shorter than it was
    (runFrame.ts nextHeights: a longer text grows it once and it holds). On a map of his: no twin, no hold (as 3.6.0.4)."""
    js = """console.log(JSON.stringify({hold: M.gw.MAIN_HOLD || null, clock: M.tb.waitClock("a model reply", ""),
  work: M.gw.STATE_WORDS.working}));"""
    got = _run(["gw", "tb"], js, None)
    hold = got.get("hold") or {}
    ctx.check(f"MAIN_HOLD: the fullest row and the model wait's clock in the shipped words, got {hold}",
              hold.get("row") == f"main · {got.get('work')} · Agent read the report" and hold.get("clock") == got.get("clock")
              and hold.get("secs") == "59 s")
    js = """const n = m.nextHeights;
console.log(JSON.stringify([n({main: 107, g: 80}, {main: 56, g: 60}, ["main"]), n({main: 107}, {main: 107.5}, ["main"]),
  n({main: 107}, {main: 124}, ["main"]), n({main: 107}, {main: 56}, []), n({}, {main: 56}, ["main"]), n({g: 60}, {g: 60}, [])]));"""
    got = _stubbed("routes/crew/map/runFrame.ts", js)
    ctx.check(f"a held box never shrinks, grows when its words need it and holds; an unheld box follows its words, got {got}",
              got == [{"main": 107, "g": 60}, None, {"main": 124}, {"main": 56}, {"main": 56}, None])
    face = (SRC / "routes/crew/map/LitMini.tsx").read_text(encoding="utf-8")
    box = (SRC / "routes/session/DownBox.tsx").read_text(encoding="utf-8")
    frame = (SRC / "routes/crew/map/runFrame.ts").read_text(encoding="utf-8")
    ctx.check("LitFace draws the twin only for main on Auto (bare && b.main); DownBox marks only main on Auto data-hold",
              "const held = bare && b.main;" in face and "MAIN_HOLD" in face
              and 'data-hold={b.main && L.groups ? "" : undefined}' in box)
    ctx.check("useMeasure passes the held boxes to nextHeights (no timer, no observer added)",
              "nextHeights(heights, got, held)" in frame and "Observer" not in frame and "setTimeout(" not in frame)


# ---------------------------------------------------------------------------------------------- 7. (r/batch04) room, units, numbers

def _placed(i: str, y: float, h: float, n: int = 0) -> dict:
    b = {"id": i, "x": 12, "y": y, "w": 384, "h": h, "rank": 1 if n else 0, "row": n}
    if n:
        b["group"] = {"n": n, "key": f"task:t{n}", "colour": (n - 1) % 4 + 1, "members": [f"a{n}"]}
    return b


@test
def test_the_auto_drawing_uses_the_whole_room(ctx: Ctx):
    """r/batch04 entry 1, the pure rule: on Auto the drawing's visible box is the whole room, whatever fits whole and at
    any scroll; on a map of his it is the released rule (the bottom of the last whole row plus the pad). On Auto the slot
    names the working group not wholly in view below it (cut at the foot, or wholly below; never one whose head is above
    the view), with the count of the other boxes wholly below."""
    boxes = [_placed("main", 12, 107), _placed("group:1", 147, 231, 1), _placed("group:2", 394, 137, 2),
             _placed("group:3", 547, 173, 3), _placed("group:4", 736, 137, 4)]
    gs = [_grp(1, [_m("a1")], "one"), _grp(2, [_m("a2", "done")], "two"), _grp(3, [_m("a3", "waiting")], "three"),
          _grp(4, [_m("a4")], "four")]
    js = """const rows = M.df.rowsOf(D.boxes), h = (auto, n, top, room) => M.df.drawingHeight(auto, rows.slice(0, n), 1, top, room);
const s = (top, viewH, bx = D.boxes) => { const x = M.df.slotOf(bx, D.gs, 1, top, viewH); return x && [x.box.id, x.more]; };
console.log(JSON.stringify({
  auto: [h(true, 1, 0, 354), h(true, 2, 0, 354), h(true, 5, 0, 354), h(true, 5, 300, 354), h(true, 5, 0, 499)],
  his: [h(false, 1, 0, 354), h(false, 5, 0, 354), h(false, 5, 0, 499), M.df.viewHeight(rows, 1, 0, 499)],
  cut: s(0, 354), below: s(0, 131), inview: s(0, 390), foot: s(140, 600), head_above: s(200, 354),
  his_slot: s(0, 354, D.boxes.map(({group, ...b}) => b)),
  size: [M.df.scrollSize(true, D.boxes, 1, 885, 354), M.df.scrollSize(false, D.boxes, 1, 885, 354),
         M.df.scrollSize(true, D.boxes.slice(0, 1), 1, 131, 354), M.df.scrollSize(true, D.boxes, 2, 885, 354)]}));"""
    got = _run(["df"], js, {"boxes": boxes, "gs": gs})
    ctx.check(f"Auto: the whole room (354, 499) before any group, with one, with four, scrolled, got {got.get('auto')}",
              got.get("auto") == [354, 354, 354, 354, 499])
    ctx.check(f"his map: the released rule (main alone 131; group 1 whole at 499: 390), got {got.get('his')}",
              got.get("his") == [131, 131, 390, 390])
    ctx.check(f"group 1 working, cut at the foot: named, with the 3 boxes wholly below, got {got.get('cut')}",
              got.get("cut") == ["group:1", 3])
    ctx.check(f"group 1 wholly below: named as before (3 more), got {got.get('below')}", got.get("below") == ["group:1", 3])
    ctx.check(f"group 1 wholly in view: the next working group below is named, got {got.get('inview')}",
              got.get("inview") == ["group:4", 2])
    ctx.check(f"group 4 cut at the foot of a scrolled view: named, nothing more below, got {got.get('foot')}",
              got.get("foot") == ["group:4", 0])
    ctx.check(f"a working group whose head is above the view is not named, got {got.get('head_above')}",
              got.get("head_above") == ["group:4", 0])
    ctx.check(f"boxes with no group (a map of his): no group named, got {got.get('his_slot')}", got.get("his_slot") is None)
    ctx.check(f"Auto's scroll reaches the last group's head at the box's top (736 + 354; at 200 %: 1472 + 354); his map and "
              f"main alone: the drawing's own height, got {got.get('size')}", got.get("size") == [1090, 885, 131, 1826])


@test
def test_a_number_keeps_its_unit(ctx: Ctx):
    """r/batch04 entry 3: every span ("{n} s", "{n} min") and cost the group words return holds no ordinary space between
    the number and its unit (a no-break space, U+00A0; the cost has none); " · " between two facts stays a break point."""
    import re
    done = _grp(2, [_m("k1", "done", who="coder", desc="fix the login form", cost=0.02, t=10, ended=10)], "fix the login bug")
    slow = _grp(3, [_m("k2", "done", t=10, ended=200), _m("k3", "done", t=20, ended=4000)], "x")
    js = """const g = M.gw;
console.log(JSON.stringify({spans: [0, 1, 59, 60, 125, 3599, 7200].map((s) => g.span(s)), money: [M.fmt.cost(0), M.fmt.cost(0.02), M.fmt.cost(12.5)],
  lines: [g.doneLine(D.done), g.countsLine(D.done), g.countsLine(D.slow), ...g.g4Lines(D.m, %s), ...g.g3Lines(D.done)]}));""" % (T0 + 50)
    got = _run(["gw", "fmt"], js, {"done": done, "slow": slow, "m": _m("k4", cost=0.01, t=10)})
    spans, money, lines = got.get("spans") or [], got.get("money") or [], got.get("lines") or []
    ctx.check(f"every span is the number, a no-break space and its unit, got {spans!r}",
              len(spans) == 7 and all(re.fullmatch(r"\d+\u00a0(s|min|h)", x) for x in spans))
    src = (SRC / "routes" / "crew" / "map" / "groupWords.ts").read_text(encoding="utf-8")
    ctx.check("the source writes the no-break space as an escape that can be seen (\\u00a0), never the bare character",
              'const NB = "\\u00a0";' in src and "\u00a0" not in src)
    ctx.check(f"the cost has no inner space, got {money!r}", money == ["$0.0000", "$0.0200", "$12.50"])
    torn = [x for x in lines if re.search(r"\d (s|min|h)\b", x)]
    ctx.check(f"no line holds an ordinary space between a number and its unit, got {torn!r} of {lines!r}", lines and not torn)
    ctx.check(f"the done group's line, the facts still joined by ' · ', got {lines[:1]!r}",
              lines[:1] == [f"1 agent · all done · $0.0200 · 0{NB}s"])
    ctx.check(f"a slow group's time in minutes, got {lines[2:3]!r}", lines[2:3] == [f"2 agents · all done · $0.0000 · 66{NB}min"])


@test
def test_no_room_is_left_for_a_group_that_is_not_drawn(ctx: Ctx):
    """r/batch04 entry 4: rows where two groups carry the same engine number (the live rig of the attention tests wrote
    its own task with n 1 while the real session's first group is n 1): each KEY is one group; the later-started of two
    colliding numbers takes, in start order, the numbers after the largest (as a group with none does), so every block the
    view places is drawn once and the drawing equals the one of rows numbered without a collision: no hole, no overlap."""
    def rows(tester_n: int) -> list:
        return [MAIN, kid("i1", 1, step="1", task="apply the discount", key="task:apply the discount", n=1, desc="Implement"),
                kid("r1", 2, step="1", task="apply the discount", key="task:apply the discount", n=1, desc="Research"),
                kid("t1", 3, step="2", task="run the basket suite", key="task:run the basket suite", n=tester_n, desc="Test"),
                kid("d1", 4),  # the rig's docs row: no group (a row from before groups)
                kid("v1", 5, step="4", task="review the basket diff", key="task:review the basket diff", n=2, desc="Review")]
    js = """const place = (rows) => { const gs = M.og.autoGroups(rows, {}), v = M.lit.autoView(M.view.view(D.auto, [], []), gs);
  const d = M.ld.layoutDown(v, () => 90, 432);
  return {ns: gs.map((g) => [g.key, g.n]), ids: v.boxes.map((b) => b.id), placed: d.boxes.map((b) => [b.id, b.y, b.h]), h: d.h}; };
console.log(JSON.stringify({clash: place(D.clash), clean: place(D.clean)}));"""
    got = _run(["og", "view", "lit", "ld"], js, {"auto": AUTO, "clash": rows(1), "clean": rows(3)})
    clash, clean = got.get("clash") or {}, got.get("clean") or {}
    ids = clash.get("ids") or []
    ctx.check(f"each key is one group, each with its own number, in start order after the largest, got {clash.get('ns')}",
              clash.get("ns") == [["task:apply the discount", 1], ["task:review the basket diff", 2],
                                  ["task:run the basket suite", 3], ["agent:d1", 4]])
    ctx.check(f"main and four blocks, no id twice, got {ids}", len(ids) == 5 and len(set(ids)) == 5)
    ctx.check(f"every block the view places is drawn (one placed box per id), got {clash.get('placed')}",
              sorted(p[0] for p in clash.get("placed") or []) == sorted(ids))
    ctx.check(f"the drawing equals the one without a collision (the first group right under main, no hole), got "
              f"{clash.get('placed')} vs {clean.get('placed')}", clash.get("placed") == clean.get("placed") and clash.get("h") == clean.get("h"))


# ---------------------------------------------------------------------------------------------- 8. (3.6.0.13 LV) NOW in words

NOW_MS = (T0 + 100) * 1000  # the drawing's clock in these cases (ms)


@test
def test_now_words_each_branch(ctx: Ctx):
    """L1 (with R11 and the coordinator's rulings): nowOf says what a helper (or main) does now, the FIRST branch that
    applies; an end Studio never saw reads the blank kept line; a tool known only from the row reads its name alone."""
    ms = lambda s: NOW_MS - s * 1000  # noqa: E731
    you = {"kind": "you", "what": "x asks you", "since": ms(40), "who": "k"}
    model = {"kind": "model", "what": "a model reply", "since": ms(7), "who": "k"}
    cases = {
        "waiting": {"raw": "waiting", "started": T0, "ended": 0, "wait": you},
        "waiting_tool": {"raw": "waiting", "started": T0, "ended": 0, "wait": you, "tool": {"tool": "Grep", "t0": ms(3)}},
        "paused": {"raw": "paused", "started": T0, "ended": 0, "wait": {**you, "since": None}},
        "queued": {"raw": "queued", "started": T0 + 95, "ended": 0, "wait": {"kind": "nothing", "what": "queued, not started", "since": None, "who": "k"}},
        "queued_stale": {"raw": "queued", "started": T0 + 95, "ended": 0, "wait": model},
        "stopped": {"raw": "stopped", "started": T0, "ended": T0 + 41},
        "done": {"raw": "done", "started": T0, "ended": T0 + 41},
        "failed": {"raw": "failed", "started": T0, "ended": T0 + 125},
        "done_unseen": {"raw": "done", "started": T0, "ended": 0},
        "stopped_unseen": {"raw": "stopped", "started": T0, "ended": 0},
        "failed_unseen": {"raw": "failed", "started": T0, "ended": 0},
        "done_nostart": {"raw": "done", "started": 0, "ended": T0 + 41},
        "failed_nostart": {"raw": "failed", "started": 0, "ended": T0 + 41},
        "tool": {"raw": "running", "started": T0, "ended": 0, "tool": {"tool": "Read", "t0": ms(3)}, "wait": model},
        "row_tool": {"raw": "running", "started": T0, "ended": 0,
                     "wait": {"kind": "tool", "what": "Bash pytest -q", "since": None, "who": "k", "tool": "Bash"}},
        "thought": {"raw": "running", "started": T0, "ended": 0, "last": {"kind": "thinking", "t0": ms(12)}, "wait": model},
        "writing": {"raw": "running", "started": T0, "ended": 0, "last": {"kind": "text", "t0": ms(2)},
                    "wait": {"kind": "nothing", "what": "working: writing", "since": None, "who": "k"}},
        "model": {"raw": "running", "started": T0, "ended": 0, "wait": model},
        "blank": {"raw": "running", "started": T0, "ended": 0},
    }
    js = """const out = {};
for (const [k, x] of Object.entries(D.cases)) out[k] = M.now.nowOf(x, D.now);
console.log(JSON.stringify(out));"""
    got = _run(["now"], js, {"cases": cases, "now": NOW_MS})
    sep = " · "
    want = {
        "waiting": ["waiting for you" + sep, "40 s", "wait"], "waiting_tool": ["waiting for you" + sep, "40 s", "wait"],
        "paused": ["paused", "", ""], "queued": ["queued" + sep, "5 s", ""], "queued_stale": ["queued" + sep, "5 s", ""],
        "stopped": [f"stopped after 41{NB}s", "", ""], "done": [f"done in 41{NB}s", "", ""], "failed": [f"failed after 2{NB}min", "", ""],
        "done_unseen": ["", "", ""], "stopped_unseen": ["", "", ""], "failed_unseen": ["", "", ""],
        "done_nostart": ["", "", ""], "failed_nostart": ["", "", ""],
        "tool": ["Read" + sep, "3 s", "tool"], "row_tool": ["Bash", "", "tool"], "thought": ["thinking" + sep, "12 s", "think"],
        "writing": ["writing" + sep, "2 s", ""], "model": ["waiting for a model reply" + sep, "7 s", ""], "blank": ["", "", ""],
    }
    for k, w in want.items():
        g = got.get(k) or {}
        ctx.check(f"{k}: {w}, got {g}", [g.get("text"), g.get("secs"), g.get("kind")] == w)
    ends = [k for k, g in got.items() if not g.get("secs") and (g.get("text") or "").rstrip().endswith("·")]
    ctx.check(f"a line with no seconds never ends in a separator, got {ends}", not ends)


@test
def test_member_carries_its_raw_state(ctx: Ctx):
    """L1: every member carries its row's own state (`raw`) while `state` stays the BoxState every reader knows."""
    states = ["queued", "running", "paused", "waiting", "done", "stopped", "failed"]
    rows = [MAIN, *[kid(f"a{i}", i + 1, step=str(i + 1), state=s, key="task:x", n=1) for i, s in enumerate(states)]]
    js = """const gs = M.og.autoGroups(D.rows), out = {};
for (const g of gs) for (const m of g.members) out[m.aid] = [m.raw, m.state];
const want = {}; for (const r of D.rows.slice(1)) want[r.agent_id] = [r.state, M.ov.stateOf([r])];
console.log(JSON.stringify({out, want}));"""
    got = _run(["og", "ov"], js, {"rows": rows})
    ctx.check(f"raw is the row's state, state is stateOf's, got {got.get('out')} want {got.get('want')}",
              bool(got.get("want")) and got.get("out") == got.get("want"))


@test
def test_member_now_drawn_and_its_words(ctx: Ctx):
    """L2a: a queued member reads "queued", a stopped one "stopped"; the hover adds "Now: ..."; NOW is drawn on every
    member (map-member-now) and on main's face on Auto (map-main-now), coloured by live-now.css."""
    q, s = _m("q", raw="queued", t=1), _m("s", "done", raw="stopped", t=1, ended=5)
    w = _m("w", desc="read report A", reason="it reads fast", t=1)
    js = """const g = M.gw;
console.log(JSON.stringify({q: g.memberState(D.q), s: g.memberState(D.s), g3: g.g3Lines(D.grp),
  tool: g.g4Lines(D.w, D.now, "Grep · 4 s"), queued: g.g4Lines(D.q, D.now, "queued · 6 s"),
  plain: g.g4Lines(D.w, D.now), empty: g.g4Lines(D.w, D.now, "")}));"""
    got = _run(["gw"], js, {"q": q, "s": s, "w": w, "grp": _grp(1, [q, s]), "now": T0 + 10})
    ctx.check(f"the state words: {got.get('q')!r}, {got.get('s')!r}", got.get("q") == "kimi-k3 · queued" and got.get("s") == "kimi-k3 · stopped")
    ctx.check(f"G3 says queued and stopped, got {got.get('g3')}", "researcher · kimi-k3 · queued" in (got.get("g3") or [])
              and "researcher · kimi-k3 · stopped" in (got.get("g3") or []))
    ctx.check(f"the hover adds Now: ..., got {got.get('tool')}", (got.get("tool") or [""])[-1] == "Now: Grep · 4 s")
    ctx.check(f"a queued member's hover, got {got.get('queued')}",
              (got.get("queued") or [""])[-1] == "Now: queued · 6 s: it starts when a running helper ends.")
    ctx.check(f"no NOW words: today's list, got {got.get('plain')}", got.get("plain") == got.get("empty")
              and not any(x.startswith("Now:") for x in got.get("plain") or []))
    member = (SRC / "routes/crew/map/GroupMember.tsx").read_text(encoding="utf-8")
    face = (SRC / "routes/crew/map/LitMini.tsx").read_text(encoding="utf-8")
    box = (SRC / "routes/session/DownBox.tsx").read_text(encoding="utf-8")
    main = (SRC / "main.tsx").read_text(encoding="utf-8")
    css_p = SRC / "styles/live-now.css"
    css = css_p.read_text(encoding="utf-8") if css_p.exists() else ""
    by, now, save = member.find('data-testid="map-member-by"'), member.find('data-testid="map-member-now"'), member.find('data-testid="map-save-agent"')
    ctx.check(f"GroupMember draws map-member-now after map-member-by and before map-save-agent ({by}, {now}, {save})",
              0 < by < now < save and "data-raw={m.raw}" in member)
    ctx.check("LitFace draws map-main-now for main on Auto, from the `main` prop OneBox passes",
              'data-testid="map-main-now"' in face and "main?: RecordAgent" in face and "main={" in box)
    ctx.check("main.tsx imports live-now.css after map-down.css and before textbox.css (the text box's sheet stays last)",
              0 < main.find('"./styles/map-down.css"') < main.find('"./styles/live-now.css"') < main.find('"./styles/textbox.css"'))
    ctx.check("live-now.css colours --think, --warn, --muted and the --line-strong edge",
              all(x in css for x in ("var(--think)", "var(--warn)", "var(--muted)", "var(--line-strong)", "[data-raw=queued]", "[data-raw=stopped]")))


@test
def test_now_room_holds_two_rows_and_grows_once(ctx: Ctx):
    """L2b with R6: NOW holds two rows from the first draw (members at 204 / 156 px, main at 224 / 160); a longer tool name
    grows the box ONCE when the drawing is not held, else reads "a tool · {s}"; the state line's rows are held too."""
    js = """const r = M.room, deck = {text: "mcp__deckcraft__insert_chart_from_range · ", secs: "4 s"};
const k0 = {rows: r.heldRows(156), grown: false};
const a = r.nowFit(deck, 156, k0, true), b = r.nowFit(deck, 156, a.kept, false);
const c = r.nowFit({text: "x".repeat(60) + " · ", secs: "5 s"}, 156, b.kept, false);
const d = r.nowFit({text: "done in 41\\u00a0s", secs: ""}, 156, c.kept, false);
const e = r.nowFit(deck, 160, {rows: r.heldRows(160), grown: false}, false), f = r.nowFit({text: "waiting for you · ", secs: "3 s"}, 160, e.kept, false);
console.log(JSON.stringify({held: [r.heldRows(204), r.heldRows(156), r.heldRows(224), r.heldRows(160)], a, b, c, d, e, f,
  state: [r.stateRows("kimi-k3", 156), r.stateRows("kimi-k3", 204), r.stateRows("", 156)]}));"""
    got = _run(["room"], js, None)
    pick = lambda x: [(x or {}).get("text"), (x or {}).get("secs"), (x or {}).get("rows")]  # noqa: E731
    deck = "mcp__deckcraft__insert_chart_from_range · "
    ctx.check(f"two rows held at 204, 156, 224 and 160 px, got {got.get('held')}", got.get("held") == [2, 2, 2, 2])
    ctx.check(f"held: the held form in 2 rows, no growth used, got {got.get('a')}",
              pick(got.get("a")) == ["a tool · ", "4 s", 2] and (got.get("a") or {}).get("kept") == {"rows": 2, "grown": False})
    ctx.check(f"not held: grows once to 3 rows, whole, got {got.get('b')}",
              pick(got.get("b")) == [deck, "4 s", 3] and (got.get("b") or {}).get("kept") == {"rows": 3, "grown": True})
    ctx.check(f"later longer words: the held form, still 3 rows, got {got.get('c')}", pick(got.get("c")) == ["a tool · ", "5 s", 3])
    ctx.check(f"done in 41 s keeps 3 rows, got {got.get('d')}", pick(got.get("d")) == [f"done in 41{NB}s", "", 3])
    ctx.check(f"main at 160: the deckcraft name grows once to 3 and keeps 3, got {got.get('e')} {got.get('f')}",
              pick(got.get("e")) == [deck, "4 s", 3] and pick(got.get("f")) == ["waiting for you · ", "3 s", 3])
    ctx.check(f"the state line's held rows: kimi-k3 at 156 2, at 204 1, alone at 156 1, got {got.get('state')}",
              got.get("state") == [2, 1, 1])
    member = (SRC / "routes/crew/map/GroupMember.tsx").read_text(encoding="utf-8")
    ctx.check("GroupMember holds map-member-state's rows from stateRows and NOW's from its kept rows",
              "minHeight: stateRows(m.model" in member and "minHeight: fit.rows * 17" in member)


@test
def test_counts_line_holds_its_longest_rows_from_the_first_draw(ctx: Ctx):
    """3.6.0.15 F1: a group's counts line holds, from the group's first draw, the rows its LONGEST form takes at the width
    the group has (every part present, the cost eight characters, the all-done form at "59 min"); a part that joins later
    never adds a row. The narrow width is read from layoutDown at Session's drawer narrowest (clientWidth 360)."""
    steps = [[_m("a", "working"), _m("b", "working")],
             [_m("a", "working"), _m("b", "working", raw="queued")],
             [_m("a", "working"), _m("b", "waiting")],
             [_m("a", "done", t=1, ended=9), _m("b", "waiting")],
             [_m("a", "done", t=1, ended=9, cost=0.0004), _m("b", "waiting", cost=0.0002)],
             [_m("a", "done", t=1, ended=9, cost=0.0004), _m("b", "failed", cost=0.0002)],
             [_m("a", "done", t=1, ended=9, cost=0.0004), _m("b", "done", t=2, ended=3500, cost=0.0002)]]
    js = """const v = M.lit.autoView(M.view.view(D.auto, [], []), [{n: 1, key: "task:a", by: "task", name: "a", members: [], first: 1}]);
const at = (cw) => M.lit.groupBox(M.ld.layoutDown(v, () => 80, cw).boxes.find((b) => b.id === M.lit.groupId(1)).w).inner;
const narrow = at(360), wide = M.lit.groupBox(760).inner;
const lines = D.steps.map((ms) => M.gw.countsLine({n: 1, key: "task:a", by: "task", name: "a", members: ms, first: 1}));
console.log(JSON.stringify({narrow, wide, lines, rows: lines.map((l) => M.room.wrapRows(l, narrow)),
  held: [1, 2, 3, 8, 12].map((k) => M.room.countsRows(k, narrow)), heldWide: M.room.countsRows(2, wide),
  wrap: [M.room.wrapRows("aaa bbb", 7 * 7.2 + 1), M.room.wrapRows("aaa bbb", 6 * 7.2 + 1), M.room.wrapRows("x".repeat(30), 24 * 7.2 + 1),
         M.room.wrapRows("aaaa 1\\u00a0bbbbb", 6 * 7.2 + 1), M.room.wrapRows("a b c", 1 * 7.2 + 1)]}));"""
    got = _run(["view", "lit", "ld", "gw", "room"], js, {"auto": AUTO, "steps": steps})
    lines, rows, held = got.get("lines") or [], got.get("rows") or [], got.get("held") or []
    ctx.check(f"the narrow group's text width is read from the drawer's layout (176 at clientWidth 360), got {got.get('narrow')}",
              got.get("narrow") == 176)
    ctx.check(f"the rows a line takes when it breaks at its spaces: 1, 2, a long word broken inside (2), a no-break space "
              f"never breaks (3), one character a row (3), got {got.get('wrap')}", got.get("wrap") == [1, 2, 2, 3, 3])
    ctx.check(f"unheld, the counts line takes more rows as parts join (the fault), got {list(zip(lines, rows))}",
              len(rows) == len(steps) and rows[0] == 1 and max(rows) > rows[0])
    ctx.check(f"held from the first draw: countsRows(2, narrow) {held[1:2]} is at least every line's rows {rows}",
              len(held) == 5 and rows and held[1] >= max(rows))
    ctx.check(f"more members never hold fewer rows, got {held}", held == sorted(held))
    ctx.check(f"at a wide group (Agents -> Live) the line holds one row, got {got.get('heldWide')}", got.get("heldWide") == 1)
    block = (SRC / "routes/crew/map/GroupBlock.tsx").read_text(encoding="utf-8")
    ctx.check("GroupBlock holds map-group-counts' rows from countsRows, in a kept ref that never shrinks at the width the "
              "group has (a new width takes its rows anew)",
              "countsRows(g.members.length, box.inner)" in block and "minHeight: rows * 17" in block
              and "Math.max(kept.current.rows" in block and "kept.current.w !== b.w" in block)


@test
def test_a_cost_above_zero_never_reads_zero(ctx: Ctx):
    """3.6.0.15 F5: every amount a group's words write comes from the box heads' formatter (orchestra/format.ts `cost`),
    which writes "<$0.0001" for an amount above zero under $0.00005; nothing above zero reads as zero."""
    pair = _grp(1, [_m("a", "working", cost=0.0004, t=1), _m("b", "working", cost=0.0002, t=2)], "x")
    done = _grp(2, [_m("a", "done", cost=0.0004, t=1, ended=5), _m("b", "done", cost=0.0002, t=2, ended=6)], "y")
    tiny = _m("c", "working", cost=0.00003, t=1)
    none = _grp(3, [_m("a", "done", t=1, ended=5)], "z")
    js = """const g = M.gw, f = M.fmt;
console.log(JSON.stringify({line: g.countsLine(D.pair), done: g.countsLine(D.done), g3: g.g3Lines(D.pair).slice(-1)[0],
  g4: g.g4Lines(D.tiny, %s).find((l) => l.startsWith("working")), none: g.countsLine(D.none), zero: [g.countsLine(D.zero)],
  fmt: [f.cost(0), f.cost(null), f.cost(0.00003), f.cost(0.00005), f.cost(0.0004), f.cost(0.04), f.cost(12.5)]}));""" % (T0 + 9)
    got = _run(["gw", "fmt"], js, {"pair": pair, "done": done, "tiny": tiny, "none": none,
                                   "zero": _grp(4, [_m("a", "working")], "w")})
    ctx.check(f"a group that cost $0.0006: its counts line, got {got.get('line')!r}", got.get("line") == "2 agents · 2 working · $0.0006")
    ctx.check(f"its all-done line, got {got.get('done')!r}", got.get("done") == f"2 agents · all done · $0.0006 · 5{NB}s")
    ctx.check(f"G3's cost line, got {got.get('g3')!r}", got.get("g3") == "$0.0006")
    ctx.check(f"G4 for a member that cost $0.00003, got {got.get('g4')!r}", got.get("g4") == f"working · <$0.0001 · 8{NB}s")
    ctx.check(f"nothing spent: the all-done line writes the formatter's zero, got {got.get('none')!r}",
              got.get("none") == f"1 agent · all done · $0.0000 · 4{NB}s")
    ctx.check(f"nothing spent: no cost part on the counts line, got {got.get('zero')!r}", got.get("zero") == ["1 agent · 1 working"])
    ctx.check(f"cost: zero and nothing known stay $0.0000; above zero under $0.00005 '<$0.0001'; four decimals under $1, two "
              f"from $1, got {got.get('fmt')}",
              got.get("fmt") == ["$0.0000", "$0.0000", "<$0.0001", "$0.0001", "$0.0004", "$0.0400", "$12.50"])
    src = (SRC / "routes/crew/map/groupWords.ts").read_text(encoding="utf-8")
    ctx.check("groupWords writes amounts with orchestra/format's cost, no formatter of its own",
              'from "../../orchestra/format"' in src and "toFixed" not in src)


@test
def test_counts_read_the_raw_state(ctx: Ctx):
    """L4 with R1: a group's counts and its all-done form read each member's raw state: "{w} working" (running, paused),
    "{q} queued", "{v} waiting on you" (warn), "{d} done", "{k} stopped", "{f} failed" (bad); a stopped member never
    makes a group "all done"."""
    stop1 = _grp(1, [_m("a", "done", raw="stopped", t=1, ended=5)], "one")
    stop2 = _grp(2, [_m("a", "done", t=1, ended=5), _m("b", "done", raw="stopped", t=2, ended=6)], "two")
    mix = _grp(3, [_m("a", "working", raw="paused"), _m("b", "working", raw="queued"), _m("c", "waiting")], "three")
    done = _grp(4, [_m("a", "done", cost=0.03, t=1, ended=60), _m("b", "done", cost=0.03, t=5, ended=100)], "four")
    bad = _grp(5, [_m("a", "failed"), _m("b", "done", raw="stopped")], "five")
    js = """const g = M.gw, out = {};
for (const [k, x] of Object.entries(D)) out[k] = {line: g.countsLine(x), all: g.isAllDone(x), parts: g.countParts(x)};
console.log(JSON.stringify(out));"""
    got = _run(["gw"], js, {"stop1": stop1, "stop2": stop2, "mix": mix, "done": done, "bad": bad})
    one, two, mx, dn, bd = (got.get(k) or {} for k in ("stop1", "stop2", "mix", "done", "bad"))
    ctx.check(f"one stopped member: its counts, never all done, got {one}", one.get("line") == "1 agent · 1 stopped" and one.get("all") is False)
    ctx.check(f"one done and one stopped: the counts, got {two}", two.get("line") == "2 agents · 1 done · 1 stopped" and two.get("all") is False)
    ctx.check(f"paused counts working, queued its own part, waiting on you marked warn, got {mx}",
              mx.get("line") == "3 agents · 1 working · 1 queued · 1 waiting on you"
              and [p.get("warn", False) for p in mx.get("parts") or []] == [False, False, False, True])
    ctx.check(f"every member raw done: the all-done form, got {dn}", dn.get("all") is True and "all done" in str(dn.get("line")))
    ctx.check(f"failed (bad) and stopped, got {bd}", bd.get("line") == "2 agents · 1 stopped · 1 failed"
              and [p.get("bad", False) for p in bd.get("parts") or []] == [False, False, True])


# ---------------------------------------------------------------------------------------------- 3.6.0.15 L8: the fold

_FOLDS = """const f = M.fold, out = {};
for (const [k, [g, now]] of Object.entries(D)) out[k] = f.foldsAt(g, now);
console.log(JSON.stringify(out));"""


@test
def test_fold_ten_seconds_after_the_last_end(ctx: Ctx):
    """L8: a group whose members are all raw done folds to its head 10 s after its LAST end (FOLD_S, the ten seconds of
    fleet/store.ts DONE_MS and crew/live/now.ts LINGER_MS)."""
    g = _grp(1, [_m("a", "done", t=1, ended=5), _m("b", "done", t=2, ended=20)], "one")
    got = _run(["fold"], _FOLDS, {"before": [g, T0 + 29.9], "at": [g, T0 + 30], "after": [g, T0 + 31], "first": [g, T0 + 15]})
    ctx.check(f"not before 10 s after the last end, folded from it, got {got}",
              got == {"before": False, "at": True, "after": True, "first": False})
    fold = (SRC / MODS["fold"]).read_text(encoding="utf-8")
    ctx.check("FOLD_S is the same ten seconds", "FOLD_S = 10" in fold)


@test
def test_failed_or_stopped_keeps_it_open(ctx: Ctx):
    """L8 with R1: only a group whose members are ALL raw done folds; a failed or a stopped member keeps it open, so does
    anything live (running, queued, waiting, paused), and a group with no member never folds."""
    d = lambda aid: _m(aid, "done", t=1, ended=5)  # noqa: E731
    late = T0 + 1000
    data = {
        "done+failed": [_grp(1, [d("a"), _m("b", "failed", t=1, ended=6)]), late],
        "failed": [_grp(2, [_m("a", "failed", t=1, ended=6)]), late],
        "done+stopped": [_grp(3, [d("a"), _m("b", "done", raw="stopped", t=1, ended=6)]), late],
        "stopped": [_grp(4, [_m("a", "done", raw="stopped", t=1, ended=6)]), late],
        "done+running": [_grp(5, [d("a"), _m("b", "working", t=2)]), late],
        "done+queued": [_grp(6, [d("a"), _m("b", "working", raw="queued")]), late],
        "done+waiting": [_grp(7, [d("a"), _m("b", "waiting", t=2)]), late],
        "done+paused": [_grp(8, [d("a"), _m("b", "working", raw="paused", t=2)]), late],
        "empty": [_grp(9, []), late],
        "all done": [_grp(10, [d("a"), d("b")]), late],
    }
    got = _run(["fold"], _FOLDS, data)
    ctx.check(f"every group but the all-done one stays open, got {got}",
              got == {k: k == "all done" for k in data})
    fold = (SRC / MODS["fold"]).read_text(encoding="utf-8")
    ctx.check("foldRule.ts reads the raw state through groupWords' isAllDone, never a second copy of the rule",
              re.search(r"import\s*\{[^}]*\bisAllDone\b[^}]*\}\s*from\s*\"\./groupWords\"", fold) is not None
              and "rawOf(" not in fold and '=== "done"' not in fold)


@test
def test_an_end_the_page_did_not_see_is_past(ctx: Ctx):
    """L8 (the coordinator's ruling 1): an end this page did not see (`ended` 0: it ended before the page loaded, or was
    first seen ended) counts as long past, so such a group is folded from its first draw; no clock yet (now 0) never folds."""
    unseen = _grp(1, [_m("a", "done", t=1), _m("b", "done", t=2)])
    mixed = _grp(2, [_m("a", "done", t=1, ended=20), _m("b", "done", t=2)])
    got = _run(["fold"], _FOLDS, {"unseen": [unseen, 1], "unseen late": [unseen, T0 + 3], "mixed before": [mixed, T0 + 29.9],
                                  "mixed at": [mixed, T0 + 30], "no clock": [unseen, 0]})
    ctx.check(f"unseen ends are past, a seen one counts, no clock never folds, got {got}",
              got == {"unseen": True, "unseen late": True, "mixed before": False, "mixed at": True, "no clock": False})


@test
def test_fold_waits_for_the_hold(ctx: Ctx):
    """L8: the first draw takes the rule at once (nothing moves after it); after that nothing folds or unfolds while the
    drawing is held (the pointer on it or a sheet open): the re-flow waits for the hold."""
    due = _grp(1, [_m("a", "done", t=1, ended=5)])
    js = """const f = M.fold, [g, now] = [D.g, D.now], late = D.late;
console.log(JSON.stringify([f.foldNext(undefined, g, late, true), f.foldNext(false, g, late, true), f.foldNext(false, g, late, false),
  f.foldNext(true, g, now, true), f.foldNext(true, g, now, false), f.foldNext(undefined, g, now, false)]));"""
    got = _run(["fold"], js, {"g": due, "now": T0 + 6, "late": T0 + 100})
    ctx.check(f"first draw at once; held keeps the last answer both ways; free takes the rule, got {got}",
              got == [True, False, True, True, False, False])


@test
def test_group_block_folds_to_its_head(ctx: Ctx):
    """L8: GroupBlock reads the drawing's hold from RunCtx, asks foldNext before its first `return null` (hooks first),
    marks `data-folded`, hides its steps and members rows (`hidden`) and keeps every member mounted; no timer anywhere."""
    src = (SRC / "routes/crew/map/GroupBlock.tsx").read_text(encoding="utf-8")
    fold = (SRC / MODS["fold"]).read_text(encoding="utf-8")
    early = src.find("return null")
    ctx.check("the hold from useContext(RunCtx), foldNext( before the first return null",
              "useContext(RunCtx)" in src and 0 <= src.find("foldNext(") < early and src.find("useContext(RunCtx)") < early)
    ctx.check("data-folded on the group, hidden={folded} on the steps row and on the members row",
              "data-folded=" in src and re.search(r'className="mp-group-steps"[^>]*hidden=\{folded\}', src) is not None
              and re.search(r'className="mp-group-members"[^>]*hidden=\{folded\}', src) is not None)
    ctx.check("every member is still mapped (kept mounted)", "g.members.map((m, i) => (" in src and "<GroupMember " in src)
    ctx.check("no setTimeout( or setInterval( in GroupBlock.tsx or foldRule.ts",
              not re.search(r"\bset(?:Timeout|Interval)\(", src + fold))


@test
def test_slot_names_a_waiting_group_first(ctx: Ctx):
    """L4: the slot names first a group whose waiting member is out of sight -- wholly below "↓", above "↑", partly in view
    (cut at the foot) "↓", wholly in view under the open card "... under the open box"; of several the lowest n; else the
    working form. The working form never names a group whose members are all raw queued (a raw paused one counts)."""
    view = {"top": 100, "bottom": 400, "left": 0, "right": 500}
    card = {"top": 150, "bottom": 350, "left": 280, "right": 500}
    at = lambda n, top, bottom, left=10, right=200, aid="w": {"n": n, "aid": aid, "top": top, "bottom": bottom, "left": left, "right": right}  # noqa: E731
    cases = {"below": [at(2, 450, 500)], "above": [at(2, 20, 80)], "under": [at(2, 200, 260, 300, 450)],
             "inview": [at(2, 200, 260)], "cut": [at(2, 380, 430)], "lowest": [at(3, 450, 500, aid="x"), at(2, 20, 80)], "none": []}
    boxes = [{"id": "main", "x": 12, "y": 12, "w": 384, "h": 80, "rank": 0, "row": 0},
             _box(1, 100, ["a"]), _box(2, 300, ["b"]), _box(3, 500, ["c"]), _box(4, 700, ["d"])]
    queued = [_grp(1, [_m("a")], "one"), _grp(3, [_m("c", raw="queued"), _m("c2", raw="queued")], "three"), _grp(4, [_m("d")], "four")]
    paused = [_grp(1, [_m("a")], "one"), _grp(3, [_m("c", raw="paused"), _m("c2", raw="queued")], "three"), _grp(4, [_m("d")], "four")]
    js = """const out = {};
for (const [k, s] of Object.entries(D.cases)) out[k] = M.df.waitSlot(s, D.view, k === 'under' || k === 'inview' ? D.card : null);
out.nocover = M.df.waitSlot(D.cases.under, D.view, null);
out.words = [M.gw.slotWords("ask", "down", 0), M.gw.slotWords("ask", "up", 1), M.gw.slotWords("ask", "under", 3),
             M.gw.slotWords("ask", "working", 0), M.gw.belowGroup("ask", 1), M.gw.slotWords("ask", undefined, 3)];
out.queued = M.df.workingBelow(D.boxes, D.queued, 1, 0, 290)?.id ?? null;
out.paused = M.df.workingBelow(D.boxes, D.paused, 1, 0, 290)?.id ?? null;
out.groups = [M.df.groupsBelow(D.boxes, 1, 0, 290, 3), M.df.groupsBelow(D.boxes, 1, 0, 290, 9), M.df.groupsBelow(D.boxes, 1, 400, 290, 4)];
console.log(JSON.stringify(out));"""
    got = _run(["df", "gw"], js, {"cases": cases, "view": view, "card": card, "boxes": boxes, "queued": queued, "paused": paused})
    ctx.check(f"wholly below: down, got {got.get('below')}", got.get("below") == {"n": 2, "aid": "w", "arrow": "down"})
    ctx.check(f"above: up, got {got.get('above')}", got.get("above") == {"n": 2, "aid": "w", "arrow": "up"})
    ctx.check(f"in view under the card: under, got {got.get('under')}", got.get("under") == {"n": 2, "aid": "w", "arrow": "under"})
    ctx.check(f"in view, not under the card: none, got {got.get('inview')}", got.get("inview") is None)
    ctx.check(f"no card: in view is none, got {got.get('nocover')}", got.get("nocover") is None)
    ctx.check(f"partly in view, cut at the foot: down, got {got.get('cut')}", got.get("cut") == {"n": 2, "aid": "w", "arrow": "down"})
    ctx.check(f"of several, the lowest n, got {got.get('lowest')}", got.get("lowest") == {"n": 2, "aid": "w", "arrow": "up"})
    ctx.check(f"no waiting member: none, got {got.get('none')}", got.get("none") is None)
    ctx.check(f"every form and its tail, letter for letter, got {got.get('words')}", got.get("words") == [
        "↓ ask · waits on you", "↑ ask · waits on you · and 1 more group below",
        "ask · waits on you · under the open box · and 3 more groups below", "↓ ask · working",
        "↓ ask · working · and 1 more group below", "↓ ask · working · and 3 more groups below"])
    ctx.check(f"a group of raw queued members is not working: group 4 is named, got {got.get('queued')}", got.get("queued") == "group:4")
    ctx.check(f"a raw paused member works: group 3 is named, got {got.get('paused')}", got.get("paused") == "group:3")
    ctx.check(f"groups wholly below (groups 2-4 at 300 px and lower), the named one not counted, got {got.get('groups')}", got.get("groups") == [2, 3, 0])


@test
def test_slot_press_folds_before_it_scrolls(ctx: Ctx):
    """L4 with R4: a press on the slot while the step-in card is open first folds it (and clears `cover`), then scrolls;
    the "under the open box" form only folds. Both drawings scroll from a layout effect that runs once the card is closed
    (cover.ts useSlotGo), never while it is open, and LiveDraw's answer effect follows the card."""
    js = """const p = M.df.slotPress;
console.log(JSON.stringify([p("down", true), p("up", true), p("under", true), p("down", false), p("working", true), p("working", false), p("under", false)]));"""
    got = _run(["df"], js, {})
    ctx.check(f"fold then scroll, the under form only folds, got {got}", got == [
        ["fold", "scroll"], ["fold", "scroll"], ["fold"], ["scroll"], ["fold", "scroll"], ["scroll"], []])
    cover = (SRC / "routes/crew/map/cover.ts").read_text(encoding="utf-8") if (SRC / "routes/crew/map/cover.ts").exists() else ""
    live = (SRC / "routes/agents/LiveDraw.tsx").read_text(encoding="utf-8")
    down = (SRC / "routes/session/MapDown.tsx").read_text(encoding="utf-8")
    ctx.check("cover.ts: the asked scroll waits in a layout effect on the card until it is closed; a fold clears cover",
              "if (card || after.current == null) return;" in cover and "setCover(where, null)" in cover and "slotPress(" in cover)
    ctx.check("both drawings press through useSlotGo; LiveDraw's slot sets no scrollTop in its click",
              "useSlotGo(" in live and "useSlotGo(" in down and "scroll.current.scrollTop = wb.y * k" not in live)
    deps = re.search(r"useLayoutEffect\(answer, \[([^\]]*)\]", live)
    ctx.check(f"LiveDraw's answer effect lists `card`, got {deps and deps.group(1)}", bool(deps) and "card" in deps.group(1).split(", "))
    ctx.check("useSlotGo is called before each drawing's answer (its cover is set first)",
              live.find("useSlotGo(") >= 0 and live.find("useSlotGo(") < live.find("useLayoutEffect(answer")
              and down.find("useSlotGo(") >= 0 and down.find("useSlotGo(") < down.find("waitAnswer("))
    for name, src in (("LiveDraw.tsx", live), ("MapDown.tsx", down)):
        ctx.check(f"{name} stays at or under 215 lines, got {src.count(chr(10))}", src.count("\n") <= 215)


@test
def test_slot_reads_the_card_and_a_hidden_member_where_they_are_now(ctx: Ctx):
    """L4 repair: the open card's rect is read when the slot's answer is worked out, never kept from when it opened (a
    resize moves the card); a waiting member past the eight drawn (hidden) stands at its group's "+n more" row, so the
    slot still names its group when that row is out of sight."""
    view = {"top": 100, "bottom": 400, "left": 0, "right": 500}
    js = """const el = (r, x = {}) => ({isConnected: true, getBoundingClientRect: () => r, ...x});
let at = {top: 150, bottom: 350, left: 280, right: 500};
const card = {isConnected: true, getBoundingClientRect: () => at};
const out = {opened: M.df.rectNow(card)};
at = {top: 150, bottom: 350, left: 0, right: 220}; // the drawer was narrowed: the card moved over the member
out.moved = M.df.rectNow(card);
out.gone = M.df.rectNow({...card, isConnected: false});
const more = el({top: 600, bottom: 620, left: 10, right: 200});
const grp = {querySelector: (s) => (s === "[data-testid=map-group-more]" ? more : null)};
const hidden = el({top: 0, bottom: 0, left: 0, right: 0}, {hidden: true, closest: (s) => (s === ".mp-group-members" ? grp : null)});
const shown = el({top: 200, bottom: 230, left: 10, right: 200});
out.hidden = M.df.placeOf(hidden); out.shown = M.df.placeOf(shown); out.none = M.df.placeOf(null);
out.flat = M.df.placeOf(el({top: 5, bottom: 5, left: 0, right: 0}));
out.ninth = M.df.waitSlot([{...out.hidden, n: 2, aid: "w9"}], D.view, null);
out.under = M.df.waitSlot([{...out.shown, n: 2, aid: "w"}], D.view, out.moved);
console.log(JSON.stringify(out));"""
    got = _run(["df"], js, {"view": view})
    ctx.check(f"the card's rect is the one on screen now, got {got.get('opened')} -> {got.get('moved')}",
              got.get("opened", {}).get("left") == 280 and got.get("moved", {}).get("left") == 0)
    ctx.check(f"a card gone from the page covers nothing, got {got.get('gone')}", got.get("gone") is None)
    ctx.check(f"a hidden member stands at its group's '+n more' row, got {got.get('hidden')}",
              got.get("hidden") == {"top": 600, "bottom": 620, "left": 10, "right": 200})
    ctx.check(f"a drawn member is its own row; none and a flat one are nothing, got {got.get('shown')} {got.get('none')} {got.get('flat')}",
              got.get("shown") == {"top": 200, "bottom": 230, "left": 10, "right": 200} and got.get("none") is None and got.get("flat") is None)
    ctx.check(f"a ninth waiting member below the view: its group is named, down, got {got.get('ninth')}",
              got.get("ninth") == {"n": 2, "aid": "w9", "arrow": "down"})
    ctx.check(f"a card moved over a waiting member in view: under, got {got.get('under')}",
              got.get("under") == {"n": 2, "aid": "w", "arrow": "under"})
    cover = (SRC / "routes/crew/map/cover.ts").read_text(encoding="utf-8")
    ctx.check("cover.ts keeps the card itself (its rect read by rectNow when asked) and reads members by placeOf",
              "rectNow(cover.get()[where])" in cover and "rectOf(el)" not in cover and cover.count("placeOf(") >= 2)


# ---------------------------------------------------------------------------------------------- 3.6.0.13 L5 L6: the rings

def _mb(aid: str, raw: str, top: float, h: float = 83, left: float = 24, right: float = 376) -> dict:
    return {"id": aid, "kind": "member", "raw": raw, "top": top, "bottom": top + h, "left": left, "right": right}


def _gb(n: int, members: list, top: float, bottom: float, left: float = 12, right: float = 388) -> dict:
    return {"id": f"group:{n}", "kind": "group", "members": members, "top": top, "bottom": bottom, "left": left, "right": right}


def _s3(raws: dict, relaid: bool) -> list:
    """S3's drawing on screen: seven groups; `relaid`: group 1 drawn with the fourth researcher (91 px taller, 2-7 moved)."""
    d = 91 if relaid else 0
    out = [_gb(1, ["r1", "r2", "r3"] + (["r4"] if relaid else []), 24, 378 + d),
           _mb("r1", raws["r1"], 66), _mb("r2", raws["r2"], 157), _mb("r3", raws["r3"], 248)]
    if relaid:
        out.append(_mb("r4", "queued", 339))
    for n, top, bottom, ms in ((2, 406, 578, ["coder"]), (3, 606, 869, ["rev1", "rev2"]), (4, 897, 1069, ["writer"]),
                               (5, 1097, 1360, ["t1", "t2"]), (6, 1388, 1588, ["media"]), (7, 1616, 1879, ["p1", "p2"])):
        out.append(_gb(n, ms, top + d, bottom + d))
        out += [_mb(m, raws[m], top + d + 42 + 91 * i) for i, m in enumerate(ms)]
    return out


@test
def test_ring_events_s3_second_and_limits(ctx: Ctx):
    """L5: S3's second -- the coder ends (DONE), researcher-2 fails (FAILED), main adds a fourth researcher to group 1 (HAND,
    once it is drawn), Tester-1 asks out of view (no ring): three rings, top-most first. The limits: nothing on the first
    draw, for a stopped member, out of view, under the pointer, meeting the open card, a box that rang under 4 s ago, a
    re-draw with no change; at most four at once, the top-most. Once main was drawn alone, the first group rings HAND."""
    before = {"r1": "running", "r2": "running", "r3": "queued", "coder": "running", "rev1": "queued", "rev2": "queued",
              "writer": "done", "t1": "running", "t2": "queued", "media": "queued", "p1": "queued", "p2": "queued"}
    after = {**before, "r2": "failed", "r3": "running", "coder": "done", "rev1": "running", "t1": "waiting"}
    view = {"top": 0, "bottom": 700, "left": 0, "right": 400, "pointer": None, "now": 100_000}
    V = {"top": 0, "bottom": 1000, "left": 0, "right": 1000, "pointer": None, "now": 100_000}
    D = {"prev": _s3(before, False), "held": _s3(after, False), "second": _s3(after, True), "view": view, "V": V,
         "six0": [_mb(c, "running", 100 * (6 - i)) for i, c in enumerate("abcdef")],
         "six1": [_mb(c, "done", 100 * (6 - i)) for i, c in enumerate("abcdef")],
         "a": [_mb("a", "running", 100)], "aStop": [_mb("a", "stopped", 100)], "aDone": [_mb("a", "done", 100)],
         "aAsk": [_mb("a", "waiting", 100)], "aFail": [_mb("a", "failed", 100)], "aCut": [_mb("a", "done", -10)],
         "g0": [_gb(1, ["a"], 50, 300), _mb("a", "running", 100)], "g1": [_gb(1, ["a", "b"], 50, 400), _mb("a", "running", 100)],
         "gOther": [_gb(1, ["x", "y"], 50, 400)], "gNew": [_gb(1, ["a"], 50, 300), _mb("a", "running", 100), _gb(2, ["b"], 420, 600)],
         "meets": {"top": 150, "bottom": 400, "left": 300, "right": 600}, "apart": {"top": 400, "bottom": 600, "left": 0, "right": 600}}
    js = """const R = M.rings.ringEvents, out = {};
out.second = R(D.prev, D.second, D.view, null, {});
out.held = R(D.prev, D.held, D.view, null, {});
out.relaid = R(D.held, D.second, D.view, null, {});
out.first = R([], D.second, D.view, null, {});
out.firstGroup = R([], D.g0, D.V, null, {}, false);
out.redraw = R(D.second, D.second, D.view, null, {});
out.stopped = R(D.a, D.aStop, D.V, null, {});
out.ask = R(D.a, D.aAsk, D.V, null, {}); out.fail = R(D.a, D.aFail, D.V, null, {});
out.cut = R(D.a, D.aCut, D.V, null, {});
out.pointer = R(D.a, D.aDone, {...D.V, pointer: "a"}, null, {});
out.pointerGroup = R(D.g0, D.g1, {...D.V, pointer: "a"}, null, {});
out.hand = R(D.g0, D.g1, D.V, null, {});
out.newGroup = R(D.g0, D.gNew, D.V, null, {});
out.otherMembers = R(D.g0, D.gOther, D.V, null, {});
out.meets = R(D.a, D.aDone, D.V, D.meets, {}); out.apart = R(D.a, D.aDone, D.V, D.apart, {});
out.ago3 = R(D.a, D.aDone, D.V, null, {a: D.V.now - 3000}); out.ago5 = R(D.a, D.aDone, D.V, null, {a: D.V.now - 5000});
out.six = R(D.six0, D.six1, D.V, null, {});
console.log(JSON.stringify(out));"""
    got = _run(["rings"], js, D)
    ring = lambda *p: [{"id": i, "kind": k} for i, k in p]  # noqa: E731
    ctx.check(f"S3's second: three rings, top-most first (group 1 HAND, researcher-2 FAILED, the coder DONE), none for "
              f"Tester-1 out of view, got {got.get('second')}",
              got.get("second") == ring(("group:1", "hand"), ("r2", "failed"), ("coder", "done")))
    ctx.check(f"held (the fourth researcher not drawn yet): no HAND, got {got.get('held')}",
              got.get("held") == ring(("r2", "failed"), ("coder", "done")))
    ctx.check(f"re-laid with the fourth researcher drawn: group 1 HAND alone, got {got.get('relaid')}",
              got.get("relaid") == ring(("group:1", "hand")))
    ctx.check(f"first draw and a re-draw with no change: none, got {got.get('first')} {got.get('redraw')}",
              got.get("first") == [] and got.get("redraw") == [])
    ctx.check(f"main was drawn alone before (not the first draw): the session's first group rings HAND, got "
              f"{got.get('firstGroup')}", got.get("firstGroup") == ring(("group:1", "hand")))
    ctx.check(f"a stopped member: no DONE, got {got.get('stopped')}", got.get("stopped") == [])
    ctx.check(f"ASK and FAILED, got {got.get('ask')} {got.get('fail')}",
              got.get("ask") == ring(("a", "ask")) and got.get("fail") == ring(("a", "failed")))
    ctx.check(f"not wholly in view: none, got {got.get('cut')}", got.get("cut") == [])
    ctx.check(f"under the pointer (the box, and the group of the member under it): none, got {got.get('pointer')} "
              f"{got.get('pointerGroup')}", got.get("pointer") == [] and got.get("pointerGroup") == [])
    ctx.check(f"a member joins a group: HAND; a new group drawn: HAND; a group whose members were replaced (another "
              f"session's): none, got {got.get('hand')} {got.get('newGroup')} {got.get('otherMembers')}",
              got.get("hand") == ring(("group:1", "hand")) and got.get("newGroup") == ring(("group:2", "hand"))
              and got.get("otherMembers") == [])
    ctx.check(f"meeting the open card: none; apart from it: rings, got {got.get('meets')} {got.get('apart')}",
              got.get("meets") == [] and got.get("apart") == ring(("a", "done")))
    ctx.check(f"once per 4 s: 3 s ago none, 5 s ago rings, got {got.get('ago3')} {got.get('ago5')}",
              got.get("ago3") == [] and got.get("ago5") == ring(("a", "done")))
    ctx.check(f"six at once: the four top-most, got {got.get('six')}",
              got.get("six") == ring(("f", "done"), ("e", "done"), ("d", "done"), ("c", "done")))


@test
def test_rings_are_css_with_one_end_listener(ctx: Ctx):
    """L6: useRings sets data-ring (and a kept data-rang counter), one animationend listener { once: true } per ringing box,
    no timer, no animation frame; live-now.css draws the ring as ::after (2 px, 3 px out, radius 9, no pointer events), ASK
    --warn and FAILED --bad shake, DONE --ok and HAND --g fade, never infinite, nothing under reduced motion; a member is
    always positioned, a group keeps its inline position; both drawings call useRings."""
    p = SRC / "routes/crew/map/useRings.ts"
    src = p.read_text(encoding="utf-8") if p.is_file() else ""
    ctx.check("useRings.ts exists", bool(src))
    ctx.check("one animationend listener { once: true }, data-ring and data-rang",
              src.count('addEventListener("animationend"') >= 1 and "{ once: true }" in src and "data-ring" in src and "data-rang" in src)
    ctx.check("a ring cut off (animationcancel) is taken off too, and every ring when the drawing is not shown",
              'addEventListener("animationcancel"' in src and 'querySelectorAll<HTMLElement>("[data-ring]")' in src)
    ctx.check("the first draw is said by useRings (main drawn alone counts as drawn; boxes gone for a draw: a first draw again)",
              "!seen.current)" in src and "[data-box=main]" in src and "else if (had.current) seen.current = false;" in src)
    ctx.check("no requestAnimationFrame(, setTimeout(, setInterval( in useRings.ts",
              not re.search(r"\b(?:requestAnimationFrame|setTimeout|setInterval)\(", src))
    ctx.check("useRings reads reduced motion and runs ringEvents with the cover", "prefers-reduced-motion: reduce" in src
              and "ringEvents(" in src and "coverOf(" in src)
    css = (SRC / "styles/live-now.css").read_text(encoding="utf-8")
    ctx.check("a member is always positioned; no position rule for a group",
              re.search(r"\.mp-member\s*\{\s*position:\s*relative;\s*\}", css) is not None
              and not re.search(r"\.mp-group[^{]*\{[^}]*position", css))
    after = re.search(r"\[data-ring\]::after\s*\{([^}]*)\}", css)
    body = after.group(1) if after else ""
    ctx.check(f"[data-ring]::after: 2 px, 3 px out, radius 9, no pointer events, got {body!r}",
              all(x in body for x in ("content: \"\"", "position: absolute", "inset: -3px", "border: 2px solid",
                                      "border-radius: 9px", "pointer-events: none")))
    for kind, colour in (("ask", "--warn"), ("failed", "--bad"), ("done", "--ok"), ("hand", "--g")):
        rule = re.search(r"\[data-ring=" + kind + r"\]::after\s*\{([^}]*)\}", css)
        ctx.check(f"{kind}: {colour}", bool(rule) and f"var({colour})" in rule.group(1))
    ctx.check("ASK and FAILED shake 0,-2,2,-2,2,0 px in 360 ms; DONE and HAND fade in 600 ms; never infinite",
              "360ms" in css and "600ms" in css and "infinite" not in css
              and re.search(r"translateX\(0\).*translateX\(-2px\).*translateX\(2px\)", css, re.S) is not None)
    rm = re.search(r"@media \(prefers-reduced-motion: reduce\)\s*\{\s*\[data-ring\]::after\s*\{([^}]*)\}", css)
    ctx.check("reduced motion: no ring drawn", bool(rm) and "animation: none" in rm.group(1) and "display: none" in rm.group(1))
    ctx.check("no clip in live-now.css", "clip" not in css)
    for name in ("routes/agents/LiveDraw.tsx", "routes/session/MapDown.tsx"):
        s = (SRC / name).read_text(encoding="utf-8")
        ctx.check(f"{name} calls useRings and stays at or under 215 lines", "useRings(" in s and s.count("\n") <= 215)


@test
def test_pause_reads_resume_while_a_pause_is_set(ctx: Ctx):
    """3.6.0.15 F3: one fact, one rule (routes/fleet/pauseFact.ts): a door reads "Resume" while the agent holds or a
    pause is set on it (`pause_set`, from the press until a resume, also before it holds), else "Pause"; every
    Pause / Resume door reads it, none decides from the state alone."""
    cases = [({"state": "waiting", "pause_set": True}, "Resume"), ({"state": "paused"}, "Resume"),
             ({"state": "running"}, "Pause"), ({"state": "waiting", "pause_set": False}, "Pause"),
             ({"state": "running", "pause_set": True}, "Resume"), (None, "Pause")]
    js = """console.log(JSON.stringify({w: D.map(([a]) => M.pf.pauseWord(a)), s: D.map(([a]) => M.pf.pauseSet(a))}));"""
    got = _run(["pf"], js, cases)
    for (a, want), w, s in zip(cases, got.get("w") or [], got.get("s") or []):
        ctx.check(f"{a}: {want}, got {w} {s}", w == want and s == (want == "Resume"))
    ctx.check(f"every case answered, got {got}", len(got.get("w") or []) == len(cases))
    doors = {"routes/fleet/actions.ts": "pauseSet(", "routes/crew/map/StepIn.tsx": "pauseWord(",
             "routes/crew/map/BoxHead.tsx": "pauseSet(", "routes/fleet/Agent.tsx": "pauseWord(",
             "routes/fleet/commands.ts": "pauseSet(", "routes/session/LiveSteer.tsx": "pauseSet("}
    for name, call in doors.items():
        s = (SRC / name).read_text(encoding="utf-8")
        ctx.check(f"{name} reads the one fact ({call}) and no door decides from `=== \"paused\"` alone",
                  call in s and "pauseFact" in s and not re.search(r"""=== "paused" \? (?:`?(?:Resume|Pause)|"(?:play|resume)")""", s))


def _todo(content: str, status: str = "pending", active: str = "") -> dict:
    return {"content": content, "status": status, "activeForm": active or f"Doing {content}"}


@test
def test_the_plan_is_main_rows_plan_in_words(ctx: Ctx):
    """3.6.0.23 PV rulings 1, 3, 4: the one path is main's row `plan` (planWords.ts planOf; todoStore.ts reads it, the
    dead `todos` frame is gone); the chip says "Plan k of N" (steps done of all) or "no plan yet"; its hover the step in
    progress; each step a mark AND a word, the step in progress in its activeForm words over a twin of the other form."""
    three = [_todo("Read the code", "completed"), _todo("Write the parser", "in_progress", "Writing the parser"), _todo("Test it")]
    sess = {"agents": [{**MAIN, "plan": three, "objective": "Fix the parser so it reads YAML"},
                       {**kid("h1", 2), "plan": [_todo("a helper's own step", "in_progress")]}]}
    js = """const P = M.pw, L = (l) => [P.chipWords(l), P.chipHover(l), P.planWords(l)];
const all = D.three.map((t) => ({...t, status: "completed"})), none = D.three.map((t) => ({...t, status: "pending"}));
console.log(JSON.stringify({plan: P.planOf(D.sess), same: P.planOf(D.sess) === P.planOf(D.sess), obj: P.objectiveOf(D.sess),
  bare: [P.planOf({agents: [D.helper]}), P.planOf(null), P.objectiveOf({agents: []})],
  k: L(P.planOf(D.sess)), zero: L(none), n: L(all), empty: L([]),
  steps: P.planOf(D.sess).map((t) => [P.STEP[t.status].mark, P.STEP[t.status].word, P.stepText(t).text, P.stepText(t).twin]), rows: P.PLAN_ROWS}));"""
    got = _run(["pw"], js, {"sess": sess, "three": three, "helper": sess["agents"][1]})
    ctx.check(f"main's row's plan, never a helper's, got {got['plan']}", [t["content"] for t in got["plan"]] == ["Read the code", "Write the parser", "Test it"])
    ctx.check("one array per row's list (a view's selector keeps its reference)", got["same"] is True)
    ctx.check(f"main's objective, got {got['obj']!r}", got["obj"] == "Fix the parser so it reads YAML")
    ctx.check(f"no main, no session: no plan, no objective, got {got['bare']}", got["bare"] == [[], [], ""])
    ctx.check(f"k of N, got {got['k']}", got["k"] == ["Plan 1 of 3", "Now: Writing the parser", "plan: 1 of 3 done"])
    ctx.check(f"0 of N, got {got['zero']}", got["zero"] == ["Plan 0 of 3", "No step in progress", "plan: 0 of 3 done"])
    ctx.check(f"N of N, got {got['n']}", got["n"] == ["Plan 3 of 3", "Every step is done", "plan: 3 of 3 done"])
    ctx.check(f"no plan, got {got['empty']}", got["empty"] == ["no plan yet", "No plan yet: when main writes a to-do list, its steps show here", ""])
    ctx.check(f"each step: mark, word, its words and their twin, got {got['steps']}", got["steps"] == [
        ["✓", "done", "Read the code", "Doing Read the code"], ["▸", "doing", "Writing the parser", "Write the parser"],
        ["○", "to do", "Test it", "Doing Test it"]])
    ctx.check(f"eight steps before the list scrolls, got {got['rows']}", got["rows"] == 8)
    store = (SRC / "routes/crew/map/todoStore.ts").read_text(encoding="utf-8")
    ctx.check("todoStore reads main's row (planOf over the fleet store), never a `todos` frame",
              "planOf(" in store and "onEvent" not in store and '"todos"' not in store)
    kinds = (SRC / "lib/events.ts").read_text(encoding="utf-8") + (SRC.parent.parent / "feed_kinds.py").read_text(encoding="utf-8")
    ctx.check("Studio no longer asks for the dead `todos` kind", '"todos"' not in kinds)
    fold = (SRC / "routes/session/planFold.ts").read_text(encoding="utf-8")
    ctx.check("the fold is kept the page's way (writeLocal, read back at load); closed unless the person opened it",
              "writeLocal(KEY" in fold and 'localStorage.getItem(KEY) !== "0"' in fold and 'folded ? "1" : "0"' in fold)


@test
def test_a_list_over_the_cap_says_its_true_counts_and_what_is_not_shown(ctx: Ctx):
    """3.6.0.23 PV after the review, fault 4: the chip says "Plan <done> of <all>" from the row's true counts
    (`plan_count`), its hover the kept step in progress past the cap; the list shows the kept steps and, where numbers
    are left out (between two kept steps, or after the last), ONE muted line "+N more steps not shown" in that place."""
    kept = [{**_todo(f"step {i}", "completed" if i <= 10 else "pending"), "n": i} for i in range(1, 30)]
    kept.append({**_todo("step 35", "in_progress", "Doing step 35"), "n": 35})
    sess = {"agents": [{**MAIN, "plan": kept, "plan_count": {"all": 40, "done": 10}}]}
    old = {"agents": [{**MAIN, "plan": [_todo("a"), _todo("b", "completed")]}]}
    js = """const P = M.pw, l = P.planOf(D.sess), c = P.countOf(D.sess, l);
const shape = (ls) => ls.map((x) => ("more" in x ? P.moreWords(x.more) : x.step.n));
console.log(JSON.stringify({chip: P.chipWords(l, c), hover: P.chipHover(l, c), lines: shape(P.planLines(l, c.all)),
  whole: shape(P.planLines(l.slice(0, 29), 29)), old: [P.chipWords(P.planOf(D.old), P.countOf(D.old)), P.countOf(D.old)],
  tail: shape(P.planLines(l.slice(0, 29), 31)), one: P.moreWords(1), map: P.planWords(l, c)}));"""
    got = _run(["pw"], js, {"sess": sess, "old": old})
    ctx.check(f"the chip counts the whole list, got {got['chip']!r}", got["chip"] == "Plan 10 of 40")
    ctx.check(f"its hover is the kept step in progress, got {got['hover']!r}", got["hover"] == "Now: Doing step 35")
    ctx.check(f"the kept steps, one line between, one after, got {got['lines'][27:]}",
              got["lines"] == list(range(1, 30)) + ["+5 more steps not shown", 35, "+5 more steps not shown"])
    ctx.check(f"a whole list: no line added, got {len(got['whole'])}", got["whole"] == list(range(1, 30)))
    ctx.check(f"numbers left out after the last only, got {got['tail'][-2:]}", got["tail"][-1] == "+2 more steps not shown" and len(got["tail"]) == 30)
    ctx.check(f"a row without counts counts its own list, got {got['old']}", got["old"] == ["Plan 1 of 2", {"all": 2, "done": 1}])
    # PV after the first CI run (the coordinator's two faults of words): one step is "step"; the map's line counts the whole list
    ctx.check(f"exactly one left out says 'step', got {got['one']!r}", got["one"] == "+1 more step not shown")
    ctx.check(f"the map's line counts the WHOLE list (plan_count), got {got['map']!r}", got["map"] == "plan: 10 of 40 done")
    lit = (SRC / "routes/crew/map/LitLine.tsx").read_text(encoding="utf-8") + (SRC / "routes/crew/map/todoStore.ts").read_text(encoding="utf-8")
    ctx.check("the map's line is drawn from the row's true counts (todoStore usePlanLine: planWords over countOf)",
              "usePlanLine(sid)" in lit and "planWords(planOf(ss), countOf(ss))" in lit)
    src = (SRC / "routes/crew/map/PlanList.tsx").read_text(encoding="utf-8") + (SRC / "routes/session/FeedPlan.tsx").read_text(encoding="utf-8")
    ctx.check("the list draws planLines (the more line muted, in its place); the head passes the true counts",
              "planLines(list, all)" in src and "muted" in src and "all={count.all}" in src and "chipWords(list, count)" in src)


@test
def test_a_card_says_goal_and_its_hover_the_step_it_was_started_for(ctx: Ctx):
    """3.6.0.23 PV ruling 5: a member's first line says "Goal" before its description (no new row); its hover adds
    "started for: <main's step in progress at its start>" (spawn.plan_step, words frozen at the start, never "n of M"),
    nothing without one."""
    rows = [MAIN, kid("a1", 1, step="main#1", desc="read report A", plan_step="Compare the numbers"),
            kid("a2", 2, step="main#1", desc="read report B")]
    for r in rows[1:]:
        r["spawn"].update({k: r.pop(k) for k in ("plan_step",) if k in r})
    js = """const gs = M.og.autoGroups(D.rows), ms = gs.flatMap((g) => g.members);
console.log(JSON.stringify(ms.map((m) => ({aid: m.aid, line: M.gw.memberLine(m), hover: M.gw.g4Lines(m, 0).slice(0, 2), forStep: m.forStep || null}))));"""
    got = {m["aid"]: m for m in _run(["og", "gw"], js, {"rows": rows})}
    ctx.check(f"the first line says Goal before the description, got {got['a1']['line']!r}", got["a1"]["line"] == "agent · Goal: read report A")
    ctx.check(f"its hover: the description, then the step it was started for, got {got['a1']['hover']}",
              got["a1"]["hover"] == ["read report A", "started for: Compare the numbers"])
    ctx.check(f"no step in progress at its start: nothing added, got {got['a2']}", got["a2"]["forStep"] is None
              and not any(x.startswith("started for") for x in got["a2"]["hover"]))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
