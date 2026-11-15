"""halo_harness.packs.crew_v1 -- what a pack gives a session's agents, workflows and maps (extension API 2.0, Halo
3.6.0.0 R5b; docs/EXTENSION_API.md "A pack's crew: agents, workflows and maps").

A 2.0 pack ships `crew/agents/*.yaml` (agent/1), `crew/workflows/*.yaml` (workflow/1) and `crew/maps/*.yaml` (map/1),
read in place. A 1.x pack's bios, lineups and workflows are READ as those where the meaning is clear, so a pack that
worked on 3.5 never goes silent:

- a bio (`agents/<n>.yaml`) is an agent: `does` its description, `instructions` its `context.system_prompt`, `model` its
  `models.preference` when that is a model (else auto, with its needs), `uses` from `tools.allow`, `careful` from
  `tools.permission_mode`, `more` its effort, `limits.max_iterations` and `limits.max_budget_usd`;
- a lineup (`teams/<n>.yaml`) is a map: main its `role: main` card's agent, a box and a line from main per other card
  (`when: {says: [...]}` from its `routing` words, else main decides), `caps.session_usd` its `budget.max_budget_usd`,
  `caps.max_depth` / `caps.max_parallel` its `delegation`'s (3.6.0.0 R5c);
- a pack workflow (`workflows/<n>.yaml`) whose stages are plain (no `for_each`, no required input, no human gate) is a
  workflow: a step per stage, its `role`'s agent. Any other runs on the run engine as before, not as a workflow.

Every name is `<pack>--<name>`, so a pack never shadows yours or a starter. What is not carried (a lineup's tiers,
permissions, stages; a bio's hooks, memory, schedules; a workflow that is not plain) is one line per pack:

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
    if allow and "web" in uses and "WebSearch" not in allow:  # 3.6.0.0 R5c: WebFetch alone is WebFetch only
        uses = [("fetch" if u == "web" else u) for u in uses]
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


#: 3.6.0.0 R5c (the judge's S2): Halo's own 3.5 bios a 1.x lineup may name, read as the starter agent that does that
#: job now (the plain session's cards were made from the auto-* bios; crew/plain.py). `default-model` as main is main.
SHIPPED_BIO = {"auto-coder": "coder", "auto-media": "media-reader", "auto-ops": "ops", "auto-planner": "planner",
               "auto-researcher": "researcher", "auto-reviewer": "reviewer", "auto-writer": "writer",
               "coder": "coder", "implementer": "implementer", "researcher": "researcher", "reviewer": "reviewer",
               "tester": "tester", "media": "media-reader", "planner": "planner", "writer": "writer", "ops": "ops"}


def _starters() -> set:
    from halo_harness.crew.store import SHIPPED
    try:
        return {q.stem for q in (SHIPPED / "agents").glob("*.yaml")}
    except OSError:
        return set()


def _cards(lineup: dict) -> list:
    """The lineup's cards: `agents:`, else the `roles:` shorthand ({role: bio} or {role: {agent, ...}})."""
    if isinstance(lineup.get("agents"), list):
        return [e for e in lineup["agents"] if isinstance(e, dict) and e.get("agent")]
    out = []
    for role, v in (lineup.get("roles") or {}).items() if isinstance(lineup.get("roles"), dict) else []:
        if isinstance(v, str) and v.strip():
            out.append({"agent": v.strip(), "role": role})
        elif isinstance(v, dict) and v.get("agent"):
            out.append({**v, "role": role})
    return out


def resolved(stem: str, lineups: dict, root: Path, chain=()) -> "tuple[dict | None, str]":
    """(the lineup with `extends:` followed, "") or (None, why): the parent is another lineup of the pack, else one Halo
    3.5 shipped; sections merge key by key (the child's key wins), the cards are the child's when it has any (as 3.5)."""
    raw = lineups.get(stem)
    if raw is None:
        shipped = Path(__file__).resolve().parent.parent / "templates" / "teams" / f"{stem}.yaml"
        raw = _yaml(shipped) if shipped.is_file() else None
    if raw is None:
        return None, f"extends {stem}, which is no lineup of the pack's or Halo's"
    parent = raw.get("extends")
    if not (isinstance(parent, str) and parent.strip()):
        return raw, ""
    if parent.strip() in chain or parent.strip() == stem:
        return None, f"extends {parent.strip()} in a circle"
    up, why = resolved(parent.strip(), lineups, root, (*chain, stem))
    if up is None:
        return None, why
    out = dict(up)
    for k, v in raw.items():
        if isinstance(v, dict) and isinstance(up.get(k), dict) and k not in ("roles",):
            out[k] = {**up[k], **v}
        else:
            out[k] = v
    if not _cards(raw):
        out["agents"], out["roles"] = up.get("agents"), up.get("roles")
    return out, ""


def map_of(pid: str, stem: str, lineup: dict, own: set) -> dict:
    """The lineup as a map/1 body; `_left` names why it is not carried (a card naming no agent here) -- such a map is
    never counted as carried (items() leaves it out, left_line names it)."""
    starters = _starters()
    left: list = []

    def who(agent, role=None) -> str:
        agent = str(agent)
        if agent in own:
            return qualify(pid, agent)
        if agent == "default-model" and role == "main":
            return "main"  # "main on your model" (docs/ROLES.md): the starter main runs on the session model
        got = SHIPPED_BIO.get(agent) or (agent if agent in starters else None)
        if got is None:
            left.append(agent)
            return agent
        return got
    cards = _cards(lineup)
    main = next((e for e in cards if e.get("role") == "main"), None)
    routing = lineup.get("routing") if isinstance(lineup.get("routing"), dict) else {}
    boxes, lines = [], []
    for e in cards:
        if e is main:
            continue
        box = str(e.get("as") or e.get("role") or e["agent"]).lower().replace("_", "-")
        if box in [b["id"] for b in boxes] or box == "main":
            box = f"{box}-{len(boxes) + 1}"
        boxes.append({"id": box, "agent": who(e["agent"], e.get("role"))})
        words = [k for k, v in routing.items() if k != "default" and v in (e.get("as"), e.get("role"))]
        lines.append({"from": "main", "to": box, "when": {"says": words} if words else "main-decides"})
    out = {"format": "map/1", "name": qualify(pid, stem), "boxes": boxes, "lines": lines,
           "main": {"agent": who(main["agent"], "main") if main else "main"}}
    caps = {}
    cap = (lineup.get("budget") or {}).get("max_budget_usd") if isinstance(lineup.get("budget"), dict) else None
    if isinstance(cap, (int, float)) and not isinstance(cap, bool) and cap > 0:
        caps["session_usd"] = cap
    dele = lineup.get("delegation") if isinstance(lineup.get("delegation"), dict) else {}  # 3.6.0.0 R5c (the judge's S3)
    for k in ("max_depth", "max_parallel"):
        if isinstance(dele.get(k), int) and not isinstance(dele.get(k), bool) and dele[k] > 0:
            caps[k] = dele[k]
    if caps:
        out["caps"] = caps
    if left:
        out["_left"] = f"names {', '.join(dict.fromkeys(left))}, which is no agent here"
    return out


def _maps(pack) -> "dict[str, tuple]":
    """{`<pack>--<lineup>`: (body | None, path, why)} -- every 1.x lineup of the pack, read as a map or not, and why."""
    root, pid = Path(pack.root), pack.id
    bios = {q.stem for q in _files(root, "agents") if _yaml(q) is not None}
    lineups = {q.stem: _yaml(q) for q in _files(root, "teams") if not q.name.endswith(".team.yaml")}
    lineups = {k: v for k, v in lineups.items() if v is not None}
    out = {}
    for n in lineups:
        t, why = resolved(n, lineups, root)
        body = map_of(pid, n, t, bios) if t is not None else None
        if body is not None and body.get("_left"):
            why, body = body["_left"], None
        out[qualify(pid, n)] = (body, root / "teams" / f"{n}.yaml", why)
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
    def agent(role):
        name = by_role.get(role, role)
        return qualify(pid, name) if name in own else SHIPPED_BIO.get(name, name)  # 3.6.0.0 R5c: Halo's bio names too
    return agent


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
    elif kind == "map":  # 3.6.0.0 R5c: extends followed, Halo's bio names read, one that cannot be carried left out
        made = {n: (body, path) for n, (body, path, _why) in _maps(pack).items() if body is not None}
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
    "" for a pack that ships `crew/` (its author moved to 2.0; its run-engine workflows stay what they are).
    3.6.0.0 R5c: a lineup that cannot be read as a map is named with its reason; a workflow that is not plain is named
    with where it runs (the run engine: halo orchestra new --workflow <pack>/<name>)."""
    root = Path(pack.root)
    if (root / "crew").is_dir():
        return ""
    left = []
    stems = [q.stem for q in _files(root, "agents")]
    got = {n.split("--", 1)[-1] for n, b in items(pack, "agent").items() if b.get("_v1")}
    missed = [x for x in stems if x not in got]
    if missed:
        left.append(f"{len(missed)} bio{'s' if len(missed) != 1 else ''} ({', '.join(missed[:3])}"
                    f"{', ...' if len(missed) > 3 else ''}) not read")
    maps = _maps(pack)
    for name, (body, _path, why) in sorted(maps.items()):
        if body is None:
            left.append(f"lineup {name.split('--', 1)[-1]} not carried ({why})")
    unread = [q.stem for q in _files(root, "teams") if not q.name.endswith(".team.yaml") and qualify(pack.id, q.stem) not in maps]
    if unread:
        left.append(f"lineup{'s' if len(unread) != 1 else ''} {', '.join(unread[:3])} not read (not YAML Halo can read)")
    from halo_harness.packs.workflow_rules import workflow_files
    flows = [n for n in workflow_files(pack.manifest, root) if qualify(pack.id, n) not in items(pack, "workflow")]
    if flows:
        left.append(f"{len(flows)} workflow{'s' if len(flows) != 1 else ''} ({', '.join(flows[:3])}"
                    f"{', ...' if len(flows) > 3 else ''}) run on the run engine only (halo orchestra new --workflow "
                    f"{pack.id}/<name>), not as a session's workflow")
    parts = [n for n in LINEUP_LEFT if any(isinstance(t, dict) and t.get(n) for t in
                                           (_yaml(q) for q in _files(root, "teams")))]
    if not left and not parts:
        return ""
    what = "; ".join(x for x in left + (["its lineups' " + ", ".join(parts) + " are not carried"] if parts else []))
    return (f"pack {pack.id}: {what} (Halo 3.6 reads a 1.x pack's bios as agents, lineups as maps, plain workflows as "
            "workflows; its author moves the rest to crew/: docs/EXTENSION_API.md, 2.0)")
