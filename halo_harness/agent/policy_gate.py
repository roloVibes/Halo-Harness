"""halo_harness.agent.policy_gate -- a pack's verdict decides a tool call (Halo 3.3.10.0 R2; docs/EXTENSION_API.md
"Policy hooks", docs/ARCHITECTURE-permissions.md "Pack policy hooks").

`agent/loop.py _resolve_tool_call` calls `decide` where it called `permission_engine.decide` (the first decide, the
re-decides after a PreToolUse or PermissionRequest hook rewrote the input, the plan specials), and
`_finalize_tool_result` calls `after` on a call that ran. Every armed policy is asked (`agent` = the sub-agent or
the Orchestra worker making the call); the winner is deny over ask over allow: deny refuses the call with the pack's
line, ask goes to the approval flow with it, allow leaves the call to the engine as before. With no pack armed,
`policy.armed()` is [] (a home with no packs folder: two stats), no process starts, and `decide` is exactly the one
`permission_engine.decide` call it replaced.

    before(name, tool_input, *, cwd, session, agent, permission_mode) -> the winning Verdict | None
    decide(session, item, name, tool_input, tool) -> Decision
    after(session, item, tr) -> ToolResult (pass: tr; redact: the pack's result; drop: the pack's line)
    fields(item) -> {"policy": {"line", "verdicts"}} | {}    the transcript tool row's and the events' field
    warm(cwd) -> how many armed policies' processes run now (session start, and arming in a session process)
"""

from __future__ import annotations

import logging
import os

log = logging.getLogger(__name__)
_seen = {"session": False}  # warm() ran here: this process asks verdicts, so arming starts the process too


def _P():
    from halo_harness.packs import policy as P
    return P


def _armed(cwd) -> list:
    """3.3.10.0 R3: when the pack catalog cannot be read, the last list `armed()` read in this process answers (an
    armed `on_error: deny` fence still denies); with nothing ever armed here that list is empty: no change."""
    try:
        return _P().armed(cwd=cwd)
    except Exception as e:  # said once per call
        try:
            last = list(_P()._last)
        except Exception:
            last = []
        log.warning("policy: the armed policies could not be read: %s%s", e, "; the last ones read here answer: " +
                    ", ".join(f"{p.pack}/{p.id}" for p in last) if last else "")
        return last


def agent_of(session) -> str:
    """The sub-agent's id, `worker:<lane>` in an Orchestra worker, else "" (the main agent)."""
    if getattr(session, "agent_id", None):
        return str(session.agent_id)
    lane = os.environ.get("HALO_ORCHESTRA_LANE")
    return f"worker:{lane}" if lane else ""


def _sid(session) -> str:
    return str(getattr(getattr(session, "log", None), "session_id", "") or "")


def _mode(pack_id: str):
    from halo_harness.packs import mode_state as M
    return M.read(pack_id)["mode"]


def is_pack(decision) -> bool:
    return str(getattr(decision, "source", "") or "").startswith("pack:")


def line(v, at: str = "before") -> str:
    """`policy: deny -- fence: outside the project` (after the call: `policy after: redact -- ...`)."""
    return f"policy{'' if at == 'before' else ' after'}: {v.action} -- {v.policy}: {v.reason}"


def said(v, at: str = "before") -> str:
    """The line the model and the person read: the pack's reason, the pack and the rule named."""
    return f"{line(v, at)} (pack {v.pack}, rule {v.rule or '-'})"


def text(decision) -> str:
    """The refused call's text for a pack's decision (its line, as it is); '' for every other decision."""
    return str(decision.reason) if is_pack(decision) else ""


def hook_may(decision, hook_decision) -> bool:
    """A PreToolUse hook's allow never lifts a pack's ask (a hook's deny still wins: deny over ask)."""
    return not (is_pack(decision) and getattr(decision, "action", "") == "ask" and hook_decision == "allow")


def _row(v, at: str, winner: bool, **extra) -> dict:
    row = {"at": at, "pack": v.pack, "policy": v.policy, "verdict": v.action, "reason": v.reason, "rule": v.rule,
           "ms": v.ms, "winner": winner}
    return {**row, **({"error": v.error} if v.error else {}), **extra}


def _asked(pols, name, tool_input, *, cwd, session, agent, permission_mode) -> list:
    P = _P()
    out = []
    for p in pols:
        req = P.request(p, name, tool_input, cwd=cwd, session=session, agent=agent, mode=_mode(p.pack),
                        permission_mode=permission_mode)
        v = P.ask(p, req, log=False)
        if v.asked:
            out.append((p, req, v))
    return out


def _record(asked: list, at: str, **extra) -> "tuple":
    P = _P()
    w = P.winner([v for _, _, v in asked])
    rows = []
    for p, req, v in asked:
        more = extra if v.action not in ("allow", "pass") else {}
        P.log_row(p, v, req, at=at, winner=v is w, **({"of": len(asked)} if len(asked) > 1 else {}), **more)
        rows.append(_row(v, at, v is w, **more))
    return w, rows


def before(name, tool_input, *, cwd, session: str = "", agent: str = "", permission_mode: str = "default"):
    """Every armed policy's verdict on one call, each logged, the winner named and returned (None: none asked)."""
    asked = _asked(_armed(cwd), name, tool_input, cwd=cwd, session=session, agent=agent, permission_mode=permission_mode)
    return _record(asked, "before")[0] if asked else None


def _keep(item: dict, at: str, rows: list) -> None:
    item["policy"] = [r for r in item.get("policy") or [] if r.get("at") != at] + rows


def decide(session, item: dict, name, tool_input, tool):
    from halo_harness.permissions import Decision
    engine = session.permission_engine
    pols = _armed(session.cwd)
    item["_policies"] = pols
    asked = _asked(pols, name, tool_input, cwd=session.cwd, session=_sid(session), agent=agent_of(session),
                   permission_mode=str(getattr(engine, "mode", "default"))) if pols else []
    if not asked:
        item.pop("policy", None)
        return engine.decide(name, tool_input, tool=tool)
    w, rows = _record(asked, "before")
    _keep(item, "before", rows)
    words = said(w)
    if w.action == "deny":
        return Decision("deny", words, source=w.source, permission_denial={
            "tool_name": name, "tool_input": tool_input, "reason": words, "suggested_rule": None,
            "pack": w.pack, "policy": w.policy, "rule": w.rule})
    d = engine.decide(name, tool_input, tool=tool)
    if w.action == "ask" and d.action != "deny":
        return Decision("ask", words, source=w.source)
    return d


def after(session, item: dict, tr):
    """The post-call verdicts of the armed `after: true` policies, in run order: each sees the result as the one
    before it left it; a drop ends the round."""
    pols = item.get("_policies")
    if pols is None:
        pols = _armed(session.cwd)
    P = _P()
    name = item.get("name") or ""
    pols = [p for p in pols or [] if p.after and P.matches(p, name)]
    if not pols:
        return tr
    from halo_harness.packs.policy_after import as_text, digest
    from halo_harness.tools.base import ToolResult
    engine = getattr(session, "permission_engine", None)
    original, current, asked, kept_last = as_text(tr.content), tr.content, [], None
    for p in pols:
        req = P.request(p, name, item.get("input"), cwd=session.cwd, session=_sid(session), agent=agent_of(session),
                        mode=_mode(p.pack), permission_mode=str(getattr(engine, "mode", "default")))
        v, kept = P.ask_after(p, req, current, tr.duration_ms, log=False)
        if not v.asked:
            continue
        asked.append((p, req, v))
        if v.action == "redact":
            current = kept_last = kept
        if v.action == "drop":
            break
    if not asked:
        return tr
    w, rows = _record(asked, "after", sha256=digest(original))
    _keep(item, "after", rows)
    if w.action == "drop":
        return ToolResult(content=said(w, "after"), is_error=tr.is_error, duration_ms=tr.duration_ms)
    if kept_last is not None:
        return ToolResult(content=current, is_error=tr.is_error, duration_ms=tr.duration_ms)
    return tr


def fields(item: dict) -> dict:
    """`{events.TOOL_POLICY_FIELD: {"line", "verdicts"}}` for a call a policy answered, else {} (no key at all)."""
    from halo_harness.events import TOOL_POLICY_FIELD
    rows = item.get("policy") if isinstance(item, dict) else None
    if not rows:
        return {}
    wins = [r for r in rows if r.get("winner")]
    text_ = "; ".join(f"policy{'' if r['at'] == 'before' else ' after'}: {r['verdict']} -- {r['policy']}: {r['reason']}"
                      for r in wins)
    return {TOOL_POLICY_FIELD: {"line": text_, "verdicts": list(rows)}}


def warm(cwd) -> int:
    """Start every armed policy's process now, so the first tool call pays no interpreter start."""
    _seen["session"] = True
    n = 0
    for p in _armed(cwd):
        try:
            n += _P().start(p) == ""
        except Exception as e:  # a process that cannot start is the first verdict's on_error, said then
            log.warning("policy %s/%s: %s", p.pack, p.id, e)
    return n


def on_armed(cwd=None) -> None:
    """mode_state after a write: in a process that runs sessions, the newly armed policies start at once."""
    if _seen["session"]:
        warm(cwd)
