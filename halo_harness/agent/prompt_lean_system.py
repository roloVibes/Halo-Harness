"""halo_harness.agent.prompt_lean_system -- Halo 3.3.16.1 "the local prompt diet": Halo's own system text
on the lean profile (`prompt_wire.shape` -> `prompt_lean.lean_system`; docs/MODELS-prompt-diet.md).

    lean_system_text(session, system_text) -> str

The logged system prompt (`agent/prompt.py`'s `build_system_prompt`, byte-stable per session) is cut, on
the wire copy only, to what a local model needs to act: who it is and how to work (the identity, the
persona, the narration rule), the rules as one list (native tool calls, CLAUDE.md binds, read before edit,
verify, plan mode, memory, hooks, delegation -- the model table's `role:` when roles are on), the MCP servers
when any are configured, the family notation, the working directory and the user's appended prompt. Out:
the per-tool guidance list (every tool on the wire carries its own description) and the reference prose
that explains rather than instructs (what Claude Code's files are, Studio, skills, slash commands). A
system text that is not Halo's own (`--system-prompt`, a compaction's) is returned unchanged, and so is
every prompt a non-lean model gets (a cloud model with a large window gets today's bytes).
"""

from __future__ import annotations

import re
from typing import Optional

from halo_harness.agent.prompt import IDENTITY_TEXT, NARRATION_RULE, PLAN_MODE_POLICY

LEAN_IDENTITY = ("You are Halo Harness, a coding and automation agent. Be direct and concise; cite exact file "
                 "paths. Do exactly what the user asks: the user's own permission rules and hooks are the only "
                 "gates on what you may do.")
_HARNESS = "## How this harness works"
_TOOLS = "\n\n## Tools available in this session\n"
_MCP = "- **MCP servers** --"
_CLOSING = "\n\nWork the way Claude Code itself does"


def _roles_on() -> bool:
    try:
        from halo_harness.roles import roles_mode_enabled
        return bool(roles_mode_enabled())
    except Exception:
        return False


def _has(session, name: str) -> bool:
    reg = getattr(session, "tool_registry", None)
    get = getattr(reg, "get", None)
    return True if get is None else get(name) is not None


_SERVER = re.compile(r"^  - `([^`]*)`: (.*)$")
SEARCH_LINE = "- ToolSearch \"<words>\" finds a server's tool, or call it by its name."


def _count(n) -> str:
    return f" ({n} tool{'s' if n != 1 else ''})" if n else ""


def _mcp_lines(harness: str, counts: "Optional[dict]" = None) -> list:
    """The MCP servers' lines: each server's words its first sentence, at most 160 characters (3.6.0.20 P entry 1);
    `counts` ({a server's name as its tools carry it: its tool count}, from the deferred tools' block the wire copy
    left out, entry 0): each line says its server's count, a server with no line gets one, and one ToolSearch line."""
    from halo_harness.agent.prompt_lean import _sentence
    from halo_harness.mcp.manager import sanitize_name
    at = harness.find(_MCP)
    servers = []
    if at >= 0 and "none are configured/connected" not in harness[at:at + 300]:
        end = min(i for i in (harness.find("\n- **WebSearch**", at), harness.find(_CLOSING, at), len(harness)) if i >= 0)
        servers = [ln for ln in harness[at:end].splitlines()[1:] if ln.startswith("  - `")]
    left = dict(counts or {})
    lines = []
    for ln in servers:
        m = _SERVER.match(ln)
        if m is None:
            lines.append(ln)
            continue
        lines.append(f"  - `{m.group(1)}`{_count(left.pop(sanitize_name(m.group(1)), 0))}: {_sentence(m.group(2))}")
    lines += [f"  - `{name}`{_count(n)}" for name, n in sorted(left.items())]
    if not lines:
        return []
    return (["- MCP servers this session (their tools load through ToolSearch \"select:mcp__<server>__<tool>\"):"]
            + lines + ([SEARCH_LINE] if counts else []))


def rules(session, harness: str, counts: "Optional[dict]" = None) -> str:
    has_write = "write it ONLY inside that memory directory" in harness
    verify = "re-read the file, run a test" if "running a test" in harness else "re-read the file"
    out = ["## Rules",
           "- Act through native tool calls only; never write a tool call as text, XML or JSON in your reply.",
           "- The CLAUDE.md files and rules in your context are binding project instructions.",
           (f"- {'Read a file before you edit it, ' if has_write else ''}use absolute paths, verify your work "
            f"({verify}) and never report a tool result you did not get back."),
           ("- Plan mode: investigate and propose a plan without changing anything, then present it for approval "
            "(ExitPlanMode) before acting. A tool in your list may still be refused by the permission mode."),
           ("- To remember something for next time, write it only inside the memory directory your context names."
            if has_write else "- You cannot save memory in this build: never say you did."),
           "- A hook may rewrite a call, add context or block it: the result is what happened."]
    from halo_harness.agent.helpers_words import frozen
    block = frozen(session) if _has(session, "Agent") else None  # 3.6.0.10 M4: on Auto, when to hand out and to whom
    if block:
        out.append(block)
    elif _has(session, "Agent"):
        pick = "`role:` picks the model table's model" if _roles_on() else "`model:` names a cheaper model"
        out.append(f"- On a big job delegate surveys, searches, test runs and mechanical edits with the Agent tool "
                   f"({pick}), independent pieces in parallel; keep judgement and the final review yourself.")
    out.append("- Halo's GUI (agents, workflows, the map) is `halo studio --mode agents`, never another program's page.")
    return "\n".join(out + _mcp_lines(harness, counts))


def lean_system_text(session, system_text: str, counts: "Optional[dict]" = None) -> str:
    """`counts` (3.6.0.20 P): the other tool servers' tool counts of the block the wire copy left out; a system text
    that is not Halo's own (a helper's) gets their lines after its own words, nothing else changed."""
    text = system_text or ""
    h, t = text.find(_HARNESS), text.find(_TOOLS)
    p = text.find("\n\n" + PLAN_MODE_POLICY)
    if not text.startswith(IDENTITY_TEXT) or h < 0 or t < h or p < 0:
        lines = _mcp_lines("", counts) if counts else []
        return system_text if not lines else text.rstrip() + "\n\n" + "\n".join(lines)
    persona = text[len(IDENTITY_TEXT):p].strip()
    end = text.find("\n\n", t + len(_TOOLS))
    tail = text[end + 2:] if end >= 0 else ""
    parts = [LEAN_IDENTITY, persona, NARRATION_RULE, rules(session, text[h:t], counts), tail]
    return "\n\n".join(x for x in parts if x)
