"""halo_harness.team.validate_stages -- the stage half of `validate_team`
(team/validate.py; 3.1.0.0 R2 renamed it from spec_stages.py): kinds,
members, lead, reads/writes, gates, triggers, the trigger graph's cycles, an
orchestra stage's goal and a flow stage's flow.

The trigger graph has an edge S -> T when T starts on `stage_done:S`, or on
`block_change:B` while S writes B. A cycle there would start its stages
again and again, so it is a problem; so is a stage that starts on a change
of a block it writes itself.
"""

from __future__ import annotations

import re
from pathlib import Path

from halo_harness.team import spec as S

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


def _known_entry(team, entry, cwd, state_dir, cache) -> bool:
    from halo_harness.team.resolve import tier_members
    return bool(S.member_by_name(team, entry) or any(m["role"] == entry for m in team["members"])
                or tier_members(team, entry, cwd=cwd, state_dir=state_dir, cache=cache))


def _trigger(stage, earlier: list, blocks: set, ids: list) -> list:
    sid, raw = stage["id"], stage["trigger"]
    kind, target = S.parse_trigger(raw)
    if kind not in S.TRIGGER_KINDS:
        return [f"stage `{sid}`: trigger is manual, block_change:<block> or stage_done:<stage>, got {raw!r}"]
    if kind == "manual":
        return [] if not target else [f"stage `{sid}`: trigger `manual` takes nothing after it, got {raw!r}"]
    if kind == "block_change" and target not in blocks:
        return [f"stage `{sid}`: trigger `{raw}` names no declared block (blocks: {', '.join(sorted(blocks)) or 'none'})"]
    if kind == "stage_done":
        if target == sid:
            return [f"stage `{sid}`: trigger `{raw}` names the stage itself"]
        if target not in earlier:
            where = "a later stage" if target in ids else "no stage"
            return [f"stage `{sid}`: trigger `{raw}` names {where}; stage_done names an earlier stage "
                    f"(before it: {', '.join(earlier) or 'none'})"]
    if kind == "block_change":
        settle = stage.get("settle_s")
        if isinstance(settle, bool) or not isinstance(settle, (int, float)) or settle < 0:
            return [f"stage `{sid}`: settle_s is a number of seconds, 0 or more, got {settle!r}"]
    return []


def _goal(team, stage, root) -> list:
    from halo_harness.orchestra.goal import validate_goal
    from halo_harness.team.resolve import goal_for_stage
    sid = stage["id"]
    if not isinstance(stage.get("goal"), dict) or not stage["goal"]:
        return [f"stage `{sid}`: an orchestra stage needs a goal {{what, done_when, workers}}"]
    goal = goal_for_stage(team, stage, root)
    return [f"stage `{sid}`: goal: {p}" for p in validate_goal(goal)]


def _flow(stage, cwd, state_dir) -> list:
    from halo_harness.flows import spec as fspec
    sid, name = stage["id"], stage.get("flow") or ""
    if not name:
        return [f"stage `{sid}`: a flow stage names its flow (`halo flow templates` lists them)"]
    path = fspec.find_flow(name, cwd=cwd, state_dir=state_dir)
    if path is None:
        return [f"stage `{sid}`: no flow `{name}` (`halo flow new {name}` makes one from a template)"]
    try:
        fspec.load_flow(path)
    except ValueError as e:
        return [f"stage `{sid}`: flow `{name}` does not load: {e}"]
    return []


def _r2(stage: dict, raw_team: dict) -> list:
    """3.1.2.0 R2: a stage's budget_usd (team/budget.py) and an orchestra / flow stage's `harness`
    (team/remote_stage.py; an agent stage delegates through its members' `harness`)."""
    from halo_harness.team.validate import _budget
    sid, out = stage["id"], _budget(f"stage `{stage['id']}`: budget_usd", stage.get("budget_usd"))
    h = stage.get("harness")
    if h is not None and not _ID.match(str(h).replace("@", "-").replace(".", "-")):
        out.append(f"stage `{sid}`: harness {h!r} names a fleet member (`halo fleet who` lists them)")
    return out


def edges(team: dict) -> "dict[str, set]":
    """`{stage: {stages it starts}}` -- the trigger graph."""
    writers: "dict[str, set]" = {}
    for s in team["workflow"]["stages"]:
        for b in s["writes"]:
            writers.setdefault(b, set()).add(s["id"])
    out: "dict[str, set]" = {s["id"]: set() for s in team["workflow"]["stages"]}
    for s in team["workflow"]["stages"]:
        kind, target = S.parse_trigger(s["trigger"])
        if kind == "stage_done" and target in out:
            out[target].add(s["id"])
        elif kind == "block_change":
            for w in writers.get(target, ()):
                out.setdefault(w, set()).add(s["id"])
    return out


def find_cycle(graph: "dict[str, set]") -> list:
    """One cycle as `[a, b, ..., a]`, or []."""
    state: dict = {}
    path: list = []

    def visit(n) -> list:
        state[n] = 1
        path.append(n)
        for m in sorted(graph.get(n, ())):
            if state.get(m) == 1:
                return path[path.index(m):] + [m]
            if state.get(m) is None:
                found = visit(m)
                if found:
                    return found
        state[n] = 2
        path.pop()
        return []

    for n in sorted(graph):
        if state.get(n) is None:
            found = visit(n)
            if found:
                return found
    return []


def check_stages(team: dict, root: Path, *, cwd=None, state_dir=None, cache=None) -> list:
    cache = {} if cache is None else cache
    stages = team["workflow"]["stages"]
    blocks = {b["id"] for b in team["blocks"]}
    ids = [s["id"] for s in stages]
    out, earlier = [], []
    if not stages:
        out.append("workflow.stages: list at least one stage (id, kind, trigger)")
    for i, s in enumerate(stages):
        sid = s["id"]
        if not _ID.match(sid):
            out.append(f"workflow.stages[{i}]: id {sid!r} is letters, digits, - and _")
        elif sid in earlier:
            out.append(f"stage `{sid}` is declared twice")
        if s["kind"] not in S.STAGE_KINDS:
            out.append(f"stage `{sid}`: kind is agent, orchestra or flow, got {s['kind']!r}")
        for entry in s["members"]:
            if not _known_entry(team, entry, cwd, state_dir, cache):
                out.append(f"stage `{sid}`: `{entry}` is no member, alias or tier of this team")
        members = S.stage_members(team, s, cwd=cwd, state_dir=state_dir)
        if s["kind"] == "agent" and not members:
            out.append(f"stage `{sid}`: an agent stage runs at least one member")
        if s["lead"] and s["lead"] not in members and s["kind"] == "agent":
            out.append(f"stage `{sid}`: lead `{s['lead']}` is not one of its members ({', '.join(members) or 'none'})")
        for b in s["reads"]:
            if b != S.BRIEF_ID and b not in blocks:
                out.append(f"stage `{sid}`: reads `{b}`, which is no declared block")
        for b in s["writes"]:
            if b not in blocks:
                out.append(f"stage `{sid}`: writes `{b}`, which is no declared block")
        if s["gate"] not in S.GATES:
            out.append(f"stage `{sid}`: gate is required, optional or none, got {s['gate']!r}")
        acc = s.get("acceptance")
        if acc is not None and not (isinstance(acc.get("expect", ""), str) and isinstance(acc.get("prompt", ""), str)):
            out.append(f"stage `{sid}`: acceptance is {{prompt, expect}} with text values")
        out += _trigger(s, earlier, blocks, ids)
        out += _r2(s, team)
        if s["kind"] == "orchestra":
            out += _goal(team, s, root)
        if s["kind"] == "flow" and not s.get("harness"):
            out += _flow(s, cwd, state_dir)
        elif s["kind"] == "flow" and not s.get("flow"):  # a flow run on a member: the flow is the member's
            out.append(f"stage `{sid}`: a flow stage names its flow (`halo flow templates` lists them)")
        earlier.append(sid)
    cycle = find_cycle(edges(team))
    if cycle:
        out.append("triggers loop: " + " -> ".join(f"`{c}`" for c in cycle)
                   + " (each start would start the next again); break the loop with a manual trigger")
    return out
