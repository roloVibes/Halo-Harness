"""halo_harness.packs.crew_v1 -- what a pack gives a session's agents, workflows and maps (extension API 2.0, Halo
3.6.0.0 R5b; docs/EXTENSION-API.md "2.0: a pack's crew").

A 2.0 pack ships `crew/agents/*.yaml` (agent/1), `crew/workflows/*.yaml` (workflow/1) and `crew/maps/*.yaml` (map/1),
read in place. A 1.x pack's bios, lineups and workflows are READ as those where the meaning is clear, so a pack that
worked on 3.5 never goes silent:

- a bio (`agents/<n>.yaml`) is an agent: `does` its description, `instructions` its `context.system_prompt`, `model` its
  `models.preference` when that is a model (else auto, with its needs), `uses` from `tools.allow`, `careful` from
  `tools.permission_mode`, `more` its effort, `limits.max_iterations` and `limits.max_budget_usd`;
- a lineup (`teams/<n>.yaml`) is a map: main its `role: main` card's agent, a box and a line from main per other card
  (`when: {says: [...]}` from its `routing` words, else main decides), `caps.session_usd` its `budget.max_budget_usd`;
- a pack workflow (`workflows/<n>.yaml`) whose stages are plain (no `for_each`, no required input, no human gate) is a
  workflow: a step per stage, its `role`'s agent. Any other runs on the run engine as before, not as a workflow.

Every name is `<pack>--<name>`, so a pack never shadows yours or a starter. What is not carried (a lineup's tiers,
permissions, delegation, stages; a bio's hooks, memory, schedules; a workflow that is not plain) is one line per pack:

    items(pack, kind) -> {name: body}      the pack's agents / workflows / maps, 2.0 files and 1.x ones read as them
    left_line(pack) -> str                 "" or the one line `halo pack list` and `halo pack doctor` say
"""

from __future__ import annotations

from pathlib import Path

from halo_harness.packs.names import qualify

FOLDERS = {"agent": "agents", "workflow": "workflows", "map": "maps"}
USE_OF = {"Read": "read", "Glob": "read", "Grep": "read", "Edit": "edit", "Write": "edit", "NotebookEdit": "edit",
          "Bash": "bash", "PowerShell": "bash", "WebFetch": "web", "WebSearch": "web"}
NEED_OF = {"long-context": "long-text", "vision": "images", "image": "images", "images": "images", "audio": "audio",
           "video": "video", "pdf": "pdf", "reasoning": "reasoning", "tools": "tools", "long-text": "long-text"}
CAREFUL_OF = {"auto": "own", "bypassPermissions": "own", "acceptEdits": "ask-commands"}
LINEUP_LEFT = ("tiers", "permissions", "pipeline", "escalation", "context", "workflows", "acceptance")


def _yaml(path: Path):
    from halo_harness.yamlfile import _read_yaml_file
    got = _read_yaml_file(path)
    return got if isinstance(got, dict) else None


def _files(root: Path, sub: str) -> "list[Path]":
    try:
        return sorted(p for p in (root / sub).glob("*.yaml") if p.is_file())
    except OSError:
        return []


def _model(models: dict) -> str:
    pref = str(models.get("preference") or "")
    return pref if ":" in pref else "auto"


def agent_of(pid: str, stem: str, bio: dict) -> dict:
    models = bio.get("models") if isinstance(bio.get("models"), dict) else {}
    tools = bio.get("tools") if isinstance(bio.get("tools"), dict) else {}
    context = bio.get("context") if isinstance(bio.get("context"), dict) else {}
    limits = bio.get("limits") if isinstance(bio.get("limits"), dict) else {}
    allow = [t for t in tools.get("allow") or [] if isinstance(t, str)]
    uses = list(dict.fromkeys(USE_OF[t] for t in allow if t in USE_OF)) if allow else ["read", "edit", "bash", "web"]
    deny = {USE_OF.get(t) for t in tools.get("deny") or [] if isinstance(t, str)}
    if not allow:
        uses = [u for u in uses if u not in deny]
    model = _model(models)
    raw_needs = list(models.get("needs") or []) + list(models.get("capabilities") or [])
    needs = list(dict.fromkeys(NEED_OF[n] for n in raw_needs if isinstance(n, str) and n in NEED_OF)) if model == "auto" else []
    out = {"format": "agent/1", "name": qualify(pid, stem),
           "does": " ".join(str(bio.get("description") or f"The {stem} agent of the {pid} pack.").split())[:600],
           "model": model, "uses": uses, "careful": CAREFUL_OF.get(str(tools.get("permission_mode") or ""), "ask-changes")}
    if isinstance(context.get("system_prompt"), str) and context["system_prompt"].strip():
        out["instructions"] = context["system_prompt"].strip()
    if needs:
        out["needs"] = needs
    more = {}
    if models.get("effort") in ("low", "medium", "high", "xhigh", "max"):
        more["effort"] = models["effort"]
    if isinstance(limits.get("max_iterations"), int) and not isinstance(limits.get("max_iterations"), bool)             and limits["max_iterations"] > 0:
        more["max_turns"] = limits["max_iterations"]
    if isinstance(limits.get("max_budget_usd"), (int, float)) and not isinstance(limits.get("max_budget_usd"), bool)             and limits["max_budget_usd"] > 0:
        more["max_usd"] = limits["max_budget_usd"]
    if more:
        out["more"] = more
    return out


def map_of(pid: str, stem: str, lineup: dict, own: set) -> dict:
    def who(agent) -> str:
        return qualify(pid, agent) if agent in own else str(agent)
    cards = [e for e in lineup.get("agents") or [] if isinstance(e, dict) and e.get("agent")]
    main = next((e for e in cards if e.get("role") == "main"), None)
    routing = lineup.get("routing") if isinstance(lineup.get("routing"), dict) else {}
    boxes, lines = [], []
    for e in cards:
        if e is main:
            continue
        box = str(e.get("as") or e.get("role") or e["agent"]).lower().replace("_", "-")
        if box in [b["id"] for b in boxes] or box == "main":
            box = f"{box}-{len(boxes) + 1}"
        boxes.append({"id": box, "agent": who(e["agent"])})
        words = [k for k, v in routing.items() if k != "default" and v in (e.get("as"), e.get("role"))]
        lines.append({"from": "main", "to": box, "when": {"says": words} if words else "main-decides"})
    out = {"format": "map/1", "name": qualify(pid, stem), "boxes": boxes, "lines": lines,
           "main": {"agent": who(main["agent"]) if main else "main"}}
    cap = (lineup.get("budget") or {}).get("max_budget_usd") if isinstance(lineup.get("budget"), dict) else None
    if isinstance(cap, (int, float)) and not isinstance(cap, bool) and cap > 0:
        out["caps"] = {"session_usd": cap}
    return out


def plain(wf: dict) -> bool:
    stages = wf.get("stages") if isinstance(wf.get("stages"), list) else []
    required = [k for k, v in (wf.get("inputs") or {}).items() if isinstance(v, dict) and v.get("required")] \
        if isinstance(wf.get("inputs"), dict) else []
    return bool(stages) and not required and all(isinstance(s, dict) and s.get("role") and not s.get("for_each")
                                                   and s.get("gate") != "human" for s in stages)


def workflow_of(pid: str, stem: str, wf: dict, role_agent) -> dict:
    steps = []
    for s in wf["stages"]:
        gives = ", ".join(str(g.get("name")) for g in s.get("gives") or [] if isinstance(g, dict)) or "what it did"
        steps.append({"name": str(s.get("title") or s.get("id"))[:80], "agents": [role_agent(s["role"])],
                      "gets": "the task" if not steps else f"what {steps[-1]['name']} handed on", "hands": gives})
    return {"format": "workflow/1", "name": qualify(pid, stem),
            "for": " ".join(str(wf.get("description") or f"The {stem} workflow of the {pid} pack.").split())[:600],
            "steps": steps}


def _role_agent(pid: str, own: set, lineups: list):
    """A stage's `role` -> the pack's agent playing it (a card of the pack's lineups, else a bio of that name)."""
    by_role = {}
    for raw in lineups:
        for e in raw.get("agents") or []:
            if isinstance(e, dict) and e.get("agent"):
                for key in (e.get("as"), e.get("role")):
                    if key:
                        by_role.setdefault(str(key), str(e["agent"]))
    return lambda role: qualify(pid, by_role.get(role, role)) if by_role.get(role, role) in own else by_role.get(role, role)


def items(pack, kind: str) -> dict:
    """{name: body} -- the pack's own 2.0 files first (crew/<kind>s/), then its 1.x files read as them."""
    from halo_harness.crew.formats import PROBLEMS
    root, pid = Path(pack.root), pack.id
    out: dict = {}
    for p in _files(root / "crew", FOLDERS[kind]):
        data = _yaml(p)
        if data is not None:
            out[qualify(pid, p.stem)] = {**data, "name": qualify(pid, p.stem), "_path": str(p)}
    bios = {p.stem: _yaml(p) for p in _files(root, "agents")}
    bios = {k: v for k, v in bios.items() if v is not None}
    lineups = {p.stem: _yaml(p) for p in _files(root, "teams") if not p.name.endswith(".team.yaml")}
    lineups = {k: v for k, v in lineups.items() if v is not None}
    if kind == "agent":
        made = {qualify(pid, n): (agent_of(pid, n, b), root / "agents" / f"{n}.yaml") for n, b in bios.items()}
    elif kind == "map":
        made = {qualify(pid, n): (map_of(pid, n, t, set(bios)), root / "teams" / f"{n}.yaml") for n, t in lineups.items()}
    else:
        from halo_harness.packs.workflow_rules import read_workflow, workflow_files
        made = {}
        for n, path in workflow_files(pack.manifest, root).items():
            wf, _t = read_workflow(path)
            if isinstance(wf, dict) and plain(wf):
                made[qualify(pid, n)] = (workflow_of(pid, n, wf, _role_agent(pid, set(bios), list(lineups.values()))), path)
    for name, (body, path) in made.items():
        if name not in out and not PROBLEMS[kind](body, name=name):
            out[name] = {**body, "_path": str(path), "_v1": True}
    return out


def left_line(pack) -> str:
    """One line: what of a 1.x pack's bios / lineups / workflows a session does not get, and what its author changes.
    "" for a pack that ships `crew/` (its author moved to 2.0; its run-engine workflows stay what they are)."""
    root = Path(pack.root)
    if (root / "crew").is_dir():
        return ""
    left = []
    for kind, sub in (("agent", "agents"), ("map", "teams"), ("workflow", "workflows")):
        stems = [p.stem for p in _files(root, sub) if not p.name.endswith(".team.yaml")]
        got = {n.split("--", 1)[-1] for n, b in items(pack, kind).items() if b.get("_v1")}
        missed = [s for s in stems if s not in got]
        word = {"agent": "bio", "map": "lineup", "workflow": "workflow"}[kind]
        if missed:
            left.append(f"{len(missed)} {word}{'s' if len(missed) != 1 else ''} ({', '.join(missed[:3])}"
                        f"{', ...' if len(missed) > 3 else ''})")
    parts = [n for n in LINEUP_LEFT if any(isinstance(t, dict) and t.get(n) for t in
                                           (_yaml(p) for p in _files(root, "teams")))]
    if not left and not parts:
        return ""
    what = "; ".join(x for x in ["not read: " + ", ".join(left) if left else "",
                                 "its lineups' " + ", ".join(parts) + " are not carried" if parts else ""] if x)
    return (f"pack {pack.id}: {what} (Halo 3.6 reads a 1.x pack's bios as agents, lineups as maps, plain workflows as "
            "workflows; its author moves the rest to crew/ (docs/EXTENSION-API.md, 2.0)")
