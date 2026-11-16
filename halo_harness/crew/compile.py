"""halo_harness.crew.compile -- a map becomes what a session already runs (Halo 3.6.0.0 R3, the design's "What runs
underneath"; docs/CREW-sessions.md).

    in_use(flag, cwd) -> (name, source)     `--map <name>` (this run), else config `crew.map`, else (roles off) no
                                            map, else the shipped `starter` map ("default", 3.6.0.0 R5)
    is_default(c) -> bool                   the default map: a drawing of a plain session, no rules of its own
    compile_map(name, cwd, state_dir) -> Compiled
    for_session(flag, cwd, state_dir) -> (Compiled | None, lines)
                                            a map with a problem: its problem lines, and the session runs on
                                            `starter` instead (None only when `starter` itself cannot be read)

A map file and the agent and workflow files it names compile to three things:

1. **main's session config** (`main`): its model (`auto`: the session's own model, as today), its instructions (added
   to the system prompt), the tool kinds it may use (read / edit / bash / web: the kinds it does not list are taken
   out; every other tool stays) and its permission mode from `careful` (crew/spec.py MODES).
2. **the hand-off table** (`handoffs`): one entry per line from main, `{line, box, kind: agent | workflow, name, when}`
   (a box naming a list of agents is one entry per agent, each with the line's when), and `chains`: the same per box,
   for the lines that leave it (the runtime follows them when that box finishes; crew/map_run.py).
3. **the agent specs** (`specs`): each agent file as the AgentSpec agent/subagent.py spawns (crew/spec.py), its
   `role` its own name, so an `auto` model is picked by models_auto with the agent's `needs` (`auto_needs`).

`caps.session_usd` is the session's money cap; `caps.max_depth` / `caps.max_parallel` (3.6.0.0 R5c) how deep
hand-offs nest and how many run at once (a knob you set yourself, `agents.max_depth` / `agents.max_concurrent`, wins). Every problem is a plain line: a missing agent or workflow, a file with
problems, the map's own problems (the circle is named).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

from halo_harness.crew import store
from halo_harness.crew.formats import PROBLEMS

AUTO_NEEDS = {"images": "vision", "long-text": "long-context"}  # agent/1 words -> models_auto's


@dataclass
class Compiled:
    name: str
    path: str = ""
    scope: str = ""
    mtime: float = 0.0
    hash: str = ""                                 # 3.6.0.2 R50: sha256 hex of the file's bytes, taken at compile
    main: dict = field(default_factory=dict)
    boxes: dict = field(default_factory=dict)      # box id -> {kind, names[]}
    handoffs: list = field(default_factory=list)   # the lines from main
    chains: dict = field(default_factory=dict)     # box id -> [entry]: the lines that leave it
    specs: dict = field(default_factory=dict)      # agent name -> AgentSpec
    agents: dict = field(default_factory=dict)     # agent name -> its file (clean)
    workflows: dict = field(default_factory=dict)  # workflow name -> its file (clean)
    cap_usd: Optional[float] = None
    delegation: dict = field(default_factory=dict)  # 3.6.0.0 R5c: caps.max_depth / caps.max_parallel (a 1.x lineup's)
    problems: list = field(default_factory=list)
    source: str = ""                               # 3.6.0.0 R5: how it came to be in use: flag, config or default

    def agent_targets(self) -> list:
        return [h["name"] for h in self.handoffs if h["kind"] == "agent"]

    def workflow_targets(self) -> list:
        return [h["name"] for h in self.handoffs if h["kind"] == "workflow"]

    def needs_of(self, name: str) -> list:
        raw = self.agents.get(name) or {}
        return [AUTO_NEEDS.get(str(n), str(n)) for n in raw.get("needs") or []]


DEFAULT_MAP = "starter"


def _roles_on() -> bool:
    try:
        from halo_harness.roles import roles_mode_enabled
        return bool(roles_mode_enabled())
    except Exception:
        return True


def in_use(flag: Optional[str] = None, cwd=None) -> "tuple[Optional[str], str]":
    """`--map` (this run), else config `crew.map`, else -- roles off ("One model for everything") -- no map at all
    (None, "none"), else the starter map as the default ("default")."""
    if isinstance(flag, str) and flag.strip():
        return flag.strip(), "flag"
    try:
        from halo_harness.theme import get_config_value
        name = get_config_value("crew.map", default=None)
    except Exception:
        name = None
    if isinstance(name, str) and name.strip():
        return name.strip(), "config"
    if not _roles_on():  # 3.6.0.0 R5 fix (M6): one model, no hand-offs, nothing added -- as 3.5's roles off
        return None, "none"
    return DEFAULT_MAP, "default"  # 3.6.0.0 R5: with none set, the starter map, drawn (is_default below)


def is_default(c) -> bool:
    """The one place that says a session runs on the DEFAULT map: it named no map and config sets none (or the map it
    named has a problem and the starter stands in). The default map is a drawing of what a plain session already did
    (crew/map_control.py PlainMap): nothing a 3.5 plain session could do is refused, capped, moved or reworded --
    no cap, no gate on agent names, no instructions added, no tool taken out. A map you picked or wrote keeps its rules."""
    return c is not None and getattr(c, "source", "") == "default"


def _entry(line: dict, box: dict, name: str) -> dict:
    return {"line": f"{line['from']} -> {line['to']}", "from": line["from"], "box": line["to"], "kind": box["kind"],
            "name": name, "when": line.get("when")}


def _load(kind: str, name: str, cwd, state_dir, extra):
    """A file as the store reads it, or as a Builder card would leave it (`extra` {(kind, name): body}: 3.6.0.2 R54)."""
    got = (extra or {}).get((kind, name))
    return got if got is not None else store.load(kind, name, cwd=cwd, state_dir=state_dir)


def _main(raw: dict, problems: list, cwd, state_dir, extra=None) -> dict:
    who = str(((raw.get("main") or {}) if isinstance(raw.get("main"), dict) else {}).get("agent") or "main")
    body = _load("agent", who, cwd, state_dir, extra)
    if body is None:
        problems.append(f"main: no agent named {who} (yours, this project's or a starter)")
        return {"agent": who}
    clean = store.clean(body)
    bad = PROBLEMS["agent"](clean, name=who)
    problems += [f"main ({who}): {p}" for p in bad]
    from halo_harness.crew.spec import MODES
    model = str(clean.get("model") or "auto")
    return {"agent": who, "model": None if model == "auto" else model, "instructions": str(clean.get("instructions") or ""),
            "uses": list(clean.get("uses") or []), "careful": clean.get("careful"), "mode": MODES.get(clean.get("careful"), "default"),
            "effort": (clean.get("more") or {}).get("effort"), "scope": body.get("_scope")}


def compile_raw(raw: dict, *, name: str = "", cwd=None, state_dir=None, extra=None) -> Compiled:
    """The map body `raw` compiled (nothing read but the agent and workflow files it names; `extra` holds the bodies a
    Builder card makes, read before the store's: 3.6.0.2 R54)."""
    out = Compiled(name=name or str(raw.get("name") or ""))
    out.problems = list(PROBLEMS["map"](raw, name=out.name))
    out.main = _main(raw, out.problems, cwd, state_dir, extra)
    for b in raw.get("boxes") or []:
        if not isinstance(b, dict) or not isinstance(b.get("id"), str):
            continue
        if b.get("workflow"):
            out.boxes[b["id"]] = {"kind": "workflow", "names": [str(b["workflow"])]}
        else:
            ref = b.get("agent")
            out.boxes[b["id"]] = {"kind": "agent", "names": [str(r) for r in (ref if isinstance(ref, list) else [ref]) if r]}
    from halo_harness.crew.spec import agent_spec
    for bid, box in out.boxes.items():
        for n in box["names"]:
            kind = box["kind"]
            got = _load(kind, n, cwd, state_dir, extra)
            if got is None:
                out.problems.append(f"box {bid}: no {kind} named {n} (yours, this project's or a starter)")
                continue
            clean = store.clean(got)
            bad = PROBLEMS[kind](clean, name=n)
            if bad:
                out.problems += [f"{kind} {n}: {p}" for p in bad]
                continue
            if kind == "agent":
                out.agents[n] = clean
                spec = agent_spec(clean, source=f"crew:{got.get('_scope')}")
                spec.role = n  # the role an `auto` model is picked for (crew/map_control.py bio_for)
                out.specs[n] = spec
            else:
                out.workflows[n] = clean
    for ln in raw.get("lines") or []:
        if not isinstance(ln, dict) or ln.get("to") not in out.boxes:
            continue
        box = out.boxes[ln["to"]]
        for n in box["names"]:
            e = _entry(ln, box, n)
            if ln.get("from") == "main":
                out.handoffs.append(e)
            else:
                out.chains.setdefault(str(ln.get("from")), []).append(e)
    cap = (raw.get("caps") or {}).get("session_usd") if isinstance(raw.get("caps"), dict) else None
    out.cap_usd = float(cap) if isinstance(cap, (int, float)) and not isinstance(cap, bool) else None
    caps = raw.get("caps") if isinstance(raw.get("caps"), dict) else {}
    out.delegation = {k: caps[k] for k in ("max_depth", "max_parallel")
                      if isinstance(caps.get(k), int) and not isinstance(caps.get(k), bool) and caps[k] > 0}
    return out


def compile_map(name: str, *, cwd=None, state_dir=None) -> Compiled:
    name = store.resolve("map", name, cwd=cwd, state_dir=state_dir)[0]  # 3.6.0.0 R5c: a pack's map named bare
    got = store.find("map", name, cwd=cwd, state_dir=state_dir)
    if got is None:
        return Compiled(name=name, problems=[f"no map named {name} (yours, this project's or a starter)"])
    path, scope = got
    raw = store.read(path) if scope != "pack" else store.clean(store.load("map", name, cwd=cwd, state_dir=state_dir) or {})
    if raw is None:
        return Compiled(name=name, path=str(path), scope=scope, problems=[f"the map {name} is not YAML Halo can read"])
    out = compile_raw(raw, name=name, cwd=cwd, state_dir=state_dir)
    out.path, out.scope = str(path), scope
    try:
        out.mtime = os.path.getmtime(path)
    except OSError:
        out.mtime = 0.0
    try:  # 3.6.0.2 R50: the very file this session follows (map_start and the status row carry it)
        import hashlib
        with open(path, "rb") as fh:
            out.hash = hashlib.sha256(fh.read()).hexdigest()
    except OSError:
        out.hash = ""
    return out


def problem_lines(c: Compiled) -> list:
    head = f"halo: the map {c.name} has a problem, so this session runs on the map {DEFAULT_MAP}:"
    return [head] + [f"  {p}" for p in c.problems]


def for_session(flag: Optional[str], *, cwd=None, state_dir=None) -> "tuple[Optional[Compiled], list]":
    name, _source = in_use(flag, cwd)
    if not name:
        return None, []
    name, said = store.resolve("map", name, cwd=cwd, state_dir=state_dir)  # 3.6.0.0 R5c: a 3.5 name typed bare
    told = [said] if said else []
    c = compile_map(name, cwd=cwd, state_dir=state_dir)
    c.source = _source  # 3.6.0.0 R5: "default" -- no map was chosen, the starter runs (main's mode stays the session's)
    if not c.problems:
        return c, told
    lines = problem_lines(c)
    if name == DEFAULT_MAP:
        return None, told + [lines[0].replace(f"runs on the map {DEFAULT_MAP}", "runs as with no map")] + lines[1:]
    lines = told + lines
    back = compile_map(DEFAULT_MAP, cwd=cwd, state_dir=state_dir)  # 3.6.0.0 R5: never a session on no map
    back.source = "default"
    return (None, lines) if back.problems else (back, lines)
