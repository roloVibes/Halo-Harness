"""halo_harness.crew.spec -- an agent/1 file as what the loop already runs (Halo 3.6.0.0 R1, the design's "What runs
underneath", R1's part: the Agent tool can spawn a crew agent by name).

    agent_spec(raw)     -> config.agents_md.AgentSpec (the dict agent/subagent.py spawns from)
    agents_json(raw)    -> the `--agents` JSON entry of the same agent (Try it runs `halo -p --agents ... --agent <name>`)
    crew_specs(cwd, state_dir) -> {name: AgentSpec}: yours and this project's (a trusted folder), for discover_agents

What the fields become: `uses` -> the tool list (read: Read, Glob, Grep; edit: Edit, Write, NotebookEdit; bash: Bash,
PowerShell, BashOutput, TaskStop; web: WebFetch, WebSearch; skill:<n>: Skill with that skill; mcp:<server>: that
server's tools), `careful` -> the permission mode (ask-changes: default, ask-commands: acceptEdits, own: auto -- your
deny and ask rules still hold), `model` (auto stays auto: models_auto picks per task), `more` -> max_turns, effort,
its own worktree, offline (no web tools), the files it always reads (named in its instructions).
"""

from __future__ import annotations

TOOLS = {"read": ["Read", "Glob", "Grep"], "edit": ["Edit", "Write", "NotebookEdit"],
         "bash": ["Bash", "PowerShell", "BashOutput", "TaskStop"], "web": ["WebFetch", "WebSearch"]}
MODES = {"ask-changes": "default", "ask-commands": "acceptEdits", "own": "auto"}
WEB = ("WebFetch", "WebSearch")


def tools_of(raw: dict) -> "tuple[list, list, list]":
    """(tools, disallowed, skills) for the agent's `uses` and `more.offline`."""
    tools: list = ["TodoWrite"]
    skills: list = []
    for u in raw.get("uses") or []:
        if u in TOOLS:
            tools += [t for t in TOOLS[u] if t not in tools]
        elif u.startswith("skill:"):
            skills.append(u[len("skill:"):])
            if "Skill" not in tools:
                tools.append("Skill")
        elif u.startswith("mcp:"):
            tools.append(f"mcp__{u[len('mcp:'):]}__*")
            if "ToolSearch" not in tools:
                tools.append("ToolSearch")
    offline = bool((raw.get("more") or {}).get("offline"))
    return tools, (list(WEB) if offline else []), skills


def prompt_of(raw: dict) -> str:
    body = str(raw.get("instructions") or "").strip() or f"You are {raw.get('name')}. {str(raw.get('does') or '').strip()}"
    reads = [r for r in (raw.get("more") or {}).get("reads") or [] if isinstance(r, str)]
    if reads:
        body += "\n\nBefore you start, read: " + ", ".join(reads) + "."
    return body


def agent_spec(raw: dict, *, source: str = "crew"):
    from halo_harness.config.agents_md import AgentSpec
    more = raw.get("more") or {}
    tools, disallowed, skills = tools_of(raw)
    model = str(raw.get("model") or "") or None
    return AgentSpec(name=str(raw.get("name")), description=str(raw.get("does") or ""), tools=tools,
                     disallowed_tools=disallowed or None, model=model, permission_mode=MODES.get(raw.get("careful"), "default"),
                     max_turns=more.get("max_turns") if isinstance(more.get("max_turns"), int) else None,
                     skills=skills or None, effort=more.get("effort") if isinstance(more.get("effort"), str) else None,
                     isolation="worktree" if more.get("worktree") else None, body=prompt_of(raw), source=source)


def agents_json(raw: dict) -> dict:
    more = raw.get("more") or {}
    tools, disallowed, skills = tools_of(raw)
    entry = {"description": str(raw.get("does") or ""), "prompt": prompt_of(raw), "tools": tools,
             "permissionMode": MODES.get(raw.get("careful"), "default")}
    if disallowed:
        entry["disallowedTools"] = disallowed
    if skills:
        entry["skills"] = skills
    if raw.get("model") and raw.get("model") != "auto":
        entry["model"] = raw["model"]
    if isinstance(more.get("max_turns"), int):
        entry["maxTurns"] = more["max_turns"]
    return {str(raw.get("name")): entry}


def crew_specs(cwd, state_dir=None) -> dict:
    """Yours, then this project's on top (a trusted folder only); a file with problems is left out."""
    from halo_harness.crew import store
    from halo_harness.crew.formats import agent_problems
    out: dict = {}
    try:
        rows = store.rows("agent", cwd=cwd, state_dir=state_dir)
    except Exception:
        return out
    for scope in ("yours", "project"):
        for r in rows:
            if r["_scope"] == scope and not r["_problems"] and not agent_problems(store.clean(r), name=r["name"]):
                out[r["name"]] = agent_spec(store.clean(r), source=f"crew:{scope}")
    return out
