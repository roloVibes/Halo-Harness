"""halo_harness.agents_md_bridge -- Halo 2.0.4 round 4 (deliverable 6):
import/export between an agent BIO (`agents_yaml.py`) and Claude Code's
own `.claude/agents/*.md` frontmatter (`config/agents_md.py::AgentSpec`).

This is a LOSSY bridge both ways, by design -- the two schemas overlap
but neither is a subset of the other (see `docs/AGENTS.md`'s own field
table for exactly which fields survive a round trip). Import reuses
`discover_agents` (the SAME precedence-aware loader the live agent
runtime itself calls) rather than re-parsing a file by hand, so an
imported bio is guaranteed to describe what a REAL `Agent(subagent_type=
name)` call would actually see.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

# Every AgentSpec field this bridge actually maps, one direction or both
# -- see docs/AGENTS.md for the authoritative table (this tuple is the
# single source that table is written FROM, so it never drifts).
MAPPED_FIELDS = ("name", "description", "tools", "disallowed_tools", "model", "permission_mode",
                 "max_turns", "skills", "mcp_servers", "memory", "effort", "color", "body")


def bio_from_agent_spec(spec) -> dict:
    """`AgentSpec` -> a bio dict (`agents_yaml.py`'s own shape) -- never
    writes a file itself; the caller (`import_agent_bio`) decides where
    `save_agent_bio` puts it."""
    bio: dict = {"name": spec.name, "description": spec.description or ""}
    if spec.color:
        bio["color"] = spec.color
    models: dict = {}
    if spec.model:
        models["preference"] = spec.model
    if spec.effort:
        models["effort"] = spec.effort
    if models:
        bio["models"] = models
    tools: dict = {}
    if spec.tools is not None:
        tools["allow"] = list(spec.tools)
    if spec.disallowed_tools is not None:
        tools["deny"] = list(spec.disallowed_tools)
    if spec.permission_mode:
        tools["permission_mode"] = spec.permission_mode
    if spec.mcp_servers is not None:
        tools["mcp_servers"] = spec.mcp_servers if isinstance(spec.mcp_servers, list) else [spec.mcp_servers]
    if tools:
        bio["tools"] = tools
    context: dict = {}
    if spec.skills is not None:
        context["skills"] = list(spec.skills)
    if spec.memory:
        context["memory"] = spec.memory
    if spec.body and spec.body.strip():
        context["system_prompt"] = spec.body.strip()
    if context:
        bio["context"] = context
    limits: dict = {}
    if spec.max_turns is not None:
        limits["max_iterations"] = spec.max_turns
    if limits:
        bio["limits"] = limits
    return bio


def import_agent_bio(name: str, *, cwd=None, settings=None) -> "tuple[Optional[dict], list[str]]":
    """`([bio|None], problems)` -- `discover_agents` is the SAME
    precedence-aware `.claude/agents` loader the live agent runtime
    itself calls (built-ins, `.claude/agents` walking up from cwd,
    `~/.claude/agents`, plugin, managed, `--agents`), so this never
    imports a DIFFERENT definition than what an `Agent(subagent_type=
    name)` call in a real session would resolve to. `problems` is non-
    empty only when `name` isn't found at all."""
    from halo_harness.config.agents_md import discover_agents
    cwd = Path(cwd) if cwd is not None else Path.cwd()
    specs = discover_agents(cwd, settings=settings)
    spec = specs.get(name)
    if spec is None:
        return None, [f"no .claude/agents definition named {name!r} was found"]
    return bio_from_agent_spec(spec), []


def frontmatter_text_from_bio(bio: dict) -> str:
    """The `.md` file TEXT (frontmatter + body) a bio exports to --
    deliberately simple/flat YAML (scalars and flat lists only, matching
    what `config/frontmatter.py`'s own hand-rolled subset parser already
    understands) so a round trip through `frontmatter.parse` reads back
    the same fields. Any bio section/field this bridge doesn't map at
    all (limits.max_budget_usd, output.*, environment.*, acceptance, ...)
    is simply absent here -- lost on export, same as it would be absent
    on import (see this module's own docstring)."""
    import yaml
    front: dict = {"name": bio.get("name") or "", "description": bio.get("description") or ""}
    models = bio.get("models") or {}
    if models.get("preference"):
        front["model"] = models["preference"]
    if models.get("effort"):
        front["effort"] = models["effort"]
    tools = bio.get("tools") or {}
    if tools.get("allow") is not None:
        front["tools"] = ", ".join(tools["allow"]) if tools["allow"] else ""
    if tools.get("deny") is not None:
        front["disallowedTools"] = ", ".join(tools["deny"]) if tools["deny"] else ""
    if tools.get("permission_mode"):
        front["permission_mode"] = tools["permission_mode"]
    if tools.get("mcp_servers"):
        front["mcp_servers"] = tools["mcp_servers"]
    context = bio.get("context") or {}
    if context.get("skills"):
        front["skills"] = ", ".join(context["skills"])
    if context.get("memory"):
        front["memory"] = context["memory"]
    limits = bio.get("limits") or {}
    if limits.get("max_iterations") is not None:
        front["max_turns"] = limits["max_iterations"]
    if bio.get("color"):
        front["color"] = bio["color"]
    body = (bio.get("context") or {}).get("system_prompt") or ""
    frontmatter_yaml = yaml.safe_dump(front, sort_keys=False, default_flow_style=False, allow_unicode=True)
    return f"---\n{frontmatter_yaml}---\n\n{body}\n" if body else f"---\n{frontmatter_yaml}---\n"


def claude_agents_path(name: str, *, cwd=None, project: bool = True) -> Path:
    if project:
        return (Path(cwd) if cwd is not None else Path.cwd()) / ".claude" / "agents" / f"{name}.md"
    from halo_harness.config.paths import home
    return home() / ".claude" / "agents" / f"{name}.md"


def export_agent_bio(name: str, bio: dict, *, cwd=None, project: bool = True) -> "tuple[bool, str]":
    """Writes `.claude/agents/<name>.md` (project, default) or
    `~/.claude/agents/<name>.md`. Refuses to overwrite a file this
    module didn't just read back identically -- actually, simplest and
    safest: it always OVERWRITES (an explicit `halo agents export` is
    the user's own deliberate action, same as `halo roles template
    export` already behaves) -- the path written to is returned so the
    caller can report it."""
    path = claude_agents_path(name, cwd=cwd, project=project)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(frontmatter_text_from_bio(bio), encoding="utf-8")
    return True, str(path)
