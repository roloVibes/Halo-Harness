"""halo_harness.tools.skill_gate -- Halo 3.3.13.1 (plans/REVIEW-2026-11.md #1, PERMS-1): a skill that came with the
project (a `.claude/skills/` folder of the cwd or an ancestor) or with a plugin root, in a folder Halo does not trust
(config/claude_json.is_trusted), is repo text. Before this, its frontmatter `allowed-tools: Bash` became a session
allow rule for the rest of the turn and its pre-run `` !`cmd` `` spans ran on that grant, with no card.

- `untrusted(cmd, cwd)`: "" for a skill of the person's own (`~/.claude/skills`, synced) or any skill in a trusted
  folder; else the one line said when its grant is dropped.
- `span_decide(engine, ...)`: a span is decided as the Bash call it is -- the armed pack policies
  (agent/policy_gate.before: deny over ask over allow), then the permission engine. Every skill's spans go through
  it (commands/registry.run_preexec_commands `decide=`).
- `gate(session, tool_input, decision)`: agent/policy_gate.decide's step for a `Skill` call. For an untrusted skill
  with spans, the call's decision is its spans' decisions joined: a deny denies the call naming the command, an ask
  is the ordinary ask card naming the commands; the person's yes lets those spans run once (`take_yes`). 3.4.1.2
  (ENGINE-3): the card is held for the person: a mode cycle leaves it up, and only their answer is a yes (`confirm`).
- `for_slash(...)`: the same for `/<skill>` typed in the prompt: no grant, the spans decided; an ask there has no
  card before the prompt is sent, so the command is not run and the line says how to allow it.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

YES = "_skill_span_yes"  # on the engine: the (skill, args) keys whose spans the person said yes to
ASKED = "_skill_span_asked"  # 3.4.1.2 (ENGINE-3): keys whose card is up; only the person's answer moves one to YES


def _user_roots() -> list:
    from halo_harness.config.paths import claude_config_dir, home
    roots = [claude_config_dir() / "skills"] if "CLAUDE_CONFIG_DIR" in os.environ else []
    return roots + [home() / ".claude" / "skills"]


def _inside(path: Path, root: Path) -> bool:
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except (OSError, ValueError):
        return False


def untrusted(skill_path, cwd) -> str:
    """The one line for a project or plugin skill in a folder that is not trusted, else ""."""
    if skill_path is None or any(_inside(skill_path, r) for r in _user_roots()):
        return ""
    try:
        from halo_harness.config.claude_json import is_trusted, load_claude_json
        if is_trusted(Path(cwd), load_claude_json()):
            return ""
    except Exception:
        pass
    name = Path(skill_path).parent.name
    return (f"skill {name} comes from this folder's files (not trusted): its allowed-tools are not granted and "
            "its pre-run commands are asked like any Bash call")


def span_decide(engine, *, cwd, session_id: str = "", agent: str = "", yes: bool = False):
    """A `decide(name, tool_input)` for run_preexec_commands: the armed packs, then the engine; `yes`: the person
    already said yes to this call's commands on its card (a deny still denies)."""
    from halo_harness.agent import policy_gate as G
    from halo_harness.permissions import Decision

    def decide(name, tool_input):
        w = G.before(name, tool_input, cwd=cwd, session=session_id, agent=agent,
                     permission_mode=str(getattr(engine, "mode", "default")))
        if w is not None and w.action == "deny":
            return Decision("deny", G.said(w), source=w.source)
        d = engine.decide(name, tool_input)
        if w is not None and w.action == "ask" and d.action != "deny":
            d = Decision("ask", G.said(w), source=w.source)
        if yes and d.action == "ask":
            return Decision("allow", "you said yes on the skill's card", source="ask")
        return d
    return decide


def spans(skill_path, args_text: str) -> list:
    """The skill body's pre-run commands, with the arguments in (the prose and the variables as they are)."""
    from halo_harness.commands.registry import _BACKTICK_CMD_RE, substitute_arguments
    from halo_harness.config.frontmatter import parse
    try:
        _fm, body = parse(Path(skill_path).read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return []
    return [m.group(1) for m in _BACKTICK_CMD_RE.finditer(substitute_arguments(body, args_text))]


def _key(tool_input) -> tuple:
    t = tool_input if isinstance(tool_input, dict) else {}
    return str(t.get("skill") or ""), str(t.get("args") or "")


def _held(engine, attr: str) -> set:
    got = getattr(engine, attr, None)
    if got is None:
        got = set()
        setattr(engine, attr, got)
    return got


def confirm(engine, tool_input) -> None:
    """3.4.1.2 (ENGINE-3): the person answered allow on this Skill call's card (Session.resolve_permission): its
    commands may run once. A mode cycle, a hook or anything else that lifts the ask never calls this."""
    if engine is not None and _key(tool_input) in _held(engine, ASKED):
        _held(engine, ASKED).discard(_key(tool_input))
        _held(engine, YES).add(_key(tool_input))


def take_yes(engine, tool_input) -> bool:
    """True once when the person said yes to this Skill call's commands (the card `gate` raised)."""
    held = getattr(engine, YES, None)
    if not held or _key(tool_input) not in held:
        return False
    held.discard(_key(tool_input))
    return True


def gate(session, tool_input, decision):
    """policy_gate.decide's Skill step: an untrusted skill's spans decide the call."""
    from halo_harness.permissions import Decision
    if getattr(decision, "action", "") == "deny" or not isinstance(tool_input, dict):
        return decision
    try:
        from halo_harness.commands.skills import find_skill
        cmd = find_skill(str(tool_input.get("skill") or ""), Path(session.cwd),
                         plugin_roots=getattr(session, "plugin_roots", None))
    except Exception:
        return decision
    engine = session.permission_engine
    held, asked_set = _held(engine, YES), _held(engine, ASKED)
    held.discard(_key(tool_input))
    asked_set.discard(_key(tool_input))
    why = untrusted(getattr(cmd, "path", None), session.cwd) if cmd is not None else ""
    if not why:
        return decision
    from halo_harness.agent.policy_gate import _sid, agent_of
    decide = span_decide(engine, cwd=session.cwd, session_id=_sid(session), agent=agent_of(session))
    asked = []
    for c in spans(cmd.path, str(tool_input.get("args") or "")):
        d = decide("Bash", {"command": c})
        if d.action == "deny":
            return Decision("deny", f"skill {cmd.name}: its pre-run command {c!r} is denied ({d.reason})",
                            source=getattr(d, "source", None) or "skill")
        if d.action == "ask":
            asked.append(c)
    if not asked:
        return decision
    asked_set.add(_key(tool_input))  # 3.4.1.2 (ENGINE-3): a yes only once the person answers (confirm)
    shown = "; ".join(f"`{c}`" for c in asked[:4]) + (f" (+{len(asked) - 4} more)" if len(asked) > 4 else "")
    return Decision("ask", f"{why}; it runs {shown} before the model reads it", source="skill")


def for_slash(skill_path, cwd, allowed_tools: list, session) -> "tuple[list, Optional[object], str]":
    """(the allowed-tools to grant, the span decide or None, the line to add) for `/<skill>` typed by the person."""
    engine = getattr(session, "permission_engine", None)
    why = untrusted(skill_path, cwd)
    if engine is None:
        return ([] if why else list(allowed_tools)), None, (f"\n\n({why}.)" if why and allowed_tools else "")
    from halo_harness.agent.policy_gate import _sid, agent_of
    decide = span_decide(engine, cwd=cwd, session_id=_sid(session), agent=agent_of(session))
    return ([] if why else list(allowed_tools)), decide, (f"\n\n({why}.)" if why and allowed_tools else "")
