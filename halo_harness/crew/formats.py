"""halo_harness.crew.formats -- the three crew file formats (Halo 3.6.0.0 R1, docs/CREW-FORMATS.md).

One YAML file per thing, each with a `format:` line:

    agent/1     crew/agents/<name>.yaml      name, does, instructions, model, needs, uses, careful, more
    workflow/1  crew/workflows/<name>.yaml   name, for, steps [{name, agents, gets, hands, when, repeat}], own_copy
    map/1       crew/maps/<name>.yaml        name, boxes [{id, agent | workflow}], lines [{from, to, when}], main, caps

`agent_problems(raw)`, `workflow_problems(raw)` and `map_problems(raw)` answer one plain line per problem (an empty
list: the file is good). A map whose lines make a circle has a problem line here, so no saved map can loop.
"""

from __future__ import annotations

import re

AGENT, WORKFLOW, MAP = "agent/1", "workflow/1", "map/1"
NAME = re.compile(r"^[a-z][a-z0-9-]{0,47}$")
USES = ("read", "edit", "bash", "web")  # plus skill:<name> and mcp:<server>
USE_PREFIX = ("skill:", "mcp:")
CAREFUL = ("ask-changes", "ask-commands", "own")
NEEDS = ("images", "audio", "video", "pdf", "reasoning", "long-text")
MORE_KEYS = {"fallback": str, "effort": str, "thinking": bool, "max_turns": int, "max_minutes": int,
             "max_usd": (int, float), "reads": list, "worktree": bool, "offline": bool, "check": dict}
EFFORTS = ("low", "medium", "high", "xhigh", "max")
AGENT_KEYS = ("format", "name", "does", "instructions", "model", "needs", "uses", "careful", "more")
STEP_KEYS = ("name", "agents", "gets", "hands", "when", "repeat")
WHEN_WORDS = ("always", "ask")
LINE_WHEN = ("always", "ask", "main-decides")


def name_problem(name, what: str = "name") -> str:
    if not isinstance(name, str) or not NAME.match(name):
        return f"{what} {name!r}: lowercase letters, digits and dashes, starting with a letter, at most 48"
    return ""


def use_ok(u) -> bool:
    if not isinstance(u, str):
        return False
    if u in USES:
        return True
    return any(u.startswith(p) and NAME.match(u[len(p):]) for p in USE_PREFIX)


def _text(raw: dict, key: str, out: list, need: bool = True, most: int = 20000) -> None:
    v = raw.get(key)
    if v is None and not need:
        return
    if not isinstance(v, str) or (need and not v.strip()):
        out.append(f"{key}: a line of text is needed")
    elif len(v) > most:
        out.append(f"{key}: at most {most} characters, got {len(v)}")


def _more_problems(more, out: list) -> None:
    if more is None:
        return
    if not isinstance(more, dict):
        out.append("more: a mapping (fallback, effort, thinking, max_turns, max_minutes, max_usd, reads, worktree, offline, check)")
        return
    for k, v in more.items():
        want = MORE_KEYS.get(k)
        if want is None:
            out.append(f"more.{k}: not a field of agent/1 (fallback, effort, thinking, max_turns, max_minutes, max_usd, reads, "
                       "worktree, offline, check)")
        elif v is None:
            continue
        elif isinstance(v, bool) and want is not bool:
            out.append(f"more.{k}: a number or text, not true/false")
        elif not isinstance(v, want):
            out.append(f"more.{k}: wrong kind of value ({type(v).__name__})")
        elif k in ("max_turns", "max_minutes", "max_usd") and v <= 0:
            out.append(f"more.{k}: more than 0")
        elif k == "effort" and v not in EFFORTS:
            out.append(f"more.effort: one of {', '.join(EFFORTS)}")
        elif k == "reads" and not all(isinstance(x, str) and x.strip() for x in v):
            out.append("more.reads: a list of file names")
        elif k == "check" and not (isinstance(v.get("ask"), str) and v.get("ask").strip()):
            out.append("more.check: {ask: <a request>, expect: <a word the reply holds>}")


def agent_problems(raw, *, name: str = "") -> "list[str]":
    if not isinstance(raw, dict):
        return ["an agent file is a mapping"]
    out: list = []
    if raw.get("format") != AGENT:
        out.append(f"format: {AGENT!r} (the first line of an agent file)")
    p = name_problem(raw.get("name"))
    if p:
        out.append(p)
    elif name and raw.get("name") != name:
        out.append(f"name: the file is {name}.yaml, so its name is {name!r}")
    _text(raw, "does", out, most=600)
    _text(raw, "instructions", out, need=False)
    model = raw.get("model")
    if not isinstance(model, str) or not model.strip() or len(model) > 200:
        out.append("model: a model from your catalog, or auto")
    needs = raw.get("needs") or []
    if not isinstance(needs, list) or any(n not in NEEDS for n in needs):
        out.append(f"needs: a list of {', '.join(NEEDS)}")
    elif needs and model != "auto":
        out.append("needs: only with model: auto (it says what Auto must pick a model for)")
    uses = raw.get("uses")
    if uses is None:
        uses = []
    if not isinstance(uses, list) or not all(use_ok(u) for u in uses):
        out.append("uses: a list of read, edit, bash, web, skill:<name>, mcp:<server>")
    elif len(set(uses)) != len(uses):
        out.append("uses: each one once")
    if raw.get("careful") not in CAREFUL:
        out.append(f"careful: one of {', '.join(CAREFUL)}")
    _more_problems(raw.get("more"), out)
    for k in raw:
        if k not in AGENT_KEYS:
            out.append(f"{k}: not a field of {AGENT} ({', '.join(AGENT_KEYS)})")
    return out


def when_problem(when, words=WHEN_WORDS, where: str = "when") -> str:
    if when is None or when in words:
        return ""
    if isinstance(when, dict) and len(when) == 1:
        (k, v), = when.items()
        if k == "needs" and isinstance(v, list) and v and all(n in NEEDS or n in ("code", "review") for n in v):
            return ""
        if k == "says" and isinstance(v, list) and v and all(isinstance(w, str) and w.strip() for w in v):
            return ""
    return f"{where}: {' | '.join(words)} | {{needs: [...]}} | {{says: [words]}}"


def workflow_problems(raw, *, name: str = "") -> "list[str]":
    if not isinstance(raw, dict):
        return ["a workflow file is a mapping"]
    out: list = []
    if raw.get("format") != WORKFLOW:
        out.append(f"format: {WORKFLOW!r} (the first line of a workflow file)")
    p = name_problem(raw.get("name"))
    if p:
        out.append(p)
    elif name and raw.get("name") != name:
        out.append(f"name: the file is {name}.yaml, so its name is {name!r}")
    _text(raw, "for", out, most=600)
    steps = raw.get("steps")
    if not isinstance(steps, list) or not steps:
        out.append("steps: at least one step")
        steps = []
    for i, s in enumerate(steps, 1):
        if not isinstance(s, dict):
            out.append(f"step {i}: a mapping")
            continue
        if not isinstance(s.get("name"), str) or not s["name"].strip():
            out.append(f"step {i}: a name")
        agents = s.get("agents")
        if not isinstance(agents, list) or not agents or any(name_problem(a) for a in agents):
            out.append(f"step {i}: agents, a list of agent names")
        w = when_problem(s.get("when"), where=f"step {i} when")
        if w:
            out.append(w)
        rep = s.get("repeat")
        if rep is not None and not (isinstance(rep, dict) and isinstance(rep.get("until"), str) and rep["until"].strip()
                                    and isinstance(rep.get("max"), int) and not isinstance(rep.get("max"), bool) and 1 <= rep["max"] <= 10):
            out.append(f"step {i} repeat: {{until: <words>, max: 1-10}}")
        for k in s:
            if k not in STEP_KEYS:
                out.append(f"step {i}: {k} is not a field of a step ({', '.join(STEP_KEYS)})")
    if "own_copy" in raw and not isinstance(raw["own_copy"], bool):
        out.append("own_copy: true or false")
    return out


def circle(lines: list) -> "list[str]":
    """The first circle the lines make (ids in order, the first again at the end), or []."""
    nxt: dict = {}
    for ln in lines:
        nxt.setdefault(ln["from"], []).append(ln["to"])
    state: dict = {}

    def walk(node: str, path: list) -> list:
        state[node] = 1
        for to in nxt.get(node, []):
            if state.get(to) == 1:
                return path[path.index(to):] + [to] if to in path else [node, to]
            if not state.get(to):
                got = walk(to, path + [to])
                if got:
                    return got
        state[node] = 2
        return []

    for start in list(nxt):
        if not state.get(start):
            got = walk(start, [start])
            if got:
                return got
    return []


def map_problems(raw, *, name: str = "") -> "list[str]":
    if not isinstance(raw, dict):
        return ["a map file is a mapping"]
    out: list = []
    if raw.get("format") != MAP:
        out.append(f"format: {MAP!r} (the first line of a map file)")
    p = name_problem(raw.get("name"))
    if p:
        out.append(p)
    elif name and raw.get("name") != name:
        out.append(f"name: the file is {name}.yaml, so its name is {name!r}")
    ids = {"main"}
    for i, b in enumerate(raw.get("boxes") or [], 1):
        ok = isinstance(b, dict) and isinstance(b.get("id"), str) and b["id"] not in ids
        ref = (b or {}).get("agent") if isinstance(b, dict) else None
        refs = ref if isinstance(ref, list) else [ref] if ref else []
        wf = (b or {}).get("workflow") if isinstance(b, dict) else None
        if not ok:
            out.append(f"box {i}: an id of its own (main is taken)")
        elif bool(refs) == bool(wf) or any(name_problem(r) for r in refs) or (wf and name_problem(wf)):
            out.append(f"box {b['id']}: agent: <name> (or a list: main decides) or workflow: <name>")
        if ok:
            ids.add(b["id"])
    lines = [ln for ln in (raw.get("lines") or []) if isinstance(ln, dict)]
    for ln in lines:
        if ln.get("from") not in ids or ln.get("to") not in ids or ln.get("to") == "main":
            out.append(f"line {ln.get('from')} -> {ln.get('to')}: both ends are boxes on the map, and nothing hands work to main")
        w = when_problem(ln.get("when"), LINE_WHEN, f"line {ln.get('from')} -> {ln.get('to')} when")
        if w:
            out.append(w)
    loop = circle([ln for ln in lines if isinstance(ln.get("from"), str) and isinstance(ln.get("to"), str)])
    if loop:
        out.append(f"the lines make a circle ({' -> '.join(loop)}): a loop lives inside a workflow as repeat until")
    caps = raw.get("caps")
    if caps is not None and not (isinstance(caps, dict) and all(isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0
                                                                for v in caps.values())):
        out.append("caps: {session_usd: <dollars>}")
    return out


PROBLEMS = {"agent": agent_problems, "workflow": workflow_problems, "map": map_problems}
