"""halo_harness.concierge -- Halo 2.0.7 round 0e: the concierge, one
secretary that is also the eyes (rolo, 2026-10-08: "one secretary that is
also the eyes, one media agent, not three").

The concierge is a ROLE (`roles.concierge`, e.g.
`or:z-ai/glm-5.3-flash` -- vision=True at a fraction of the main model's
price), resolved through the same role table every agent resolves
through. Every concierge feature degrades to today's behavior when the
role is not configured: nothing here ever hard-requires it.

Three surfaces:
  * `/ask <question>` -- quick Q&A and "what's been done" updates answered
    WITHOUT waking the orchestrator: a one-shot call (never through the
    session log, never touching the main conversation) over a
    deterministic digest of the recent session history + the pending
    status notices.
  * the eyes -- when the ACTIVE model is blind and images arrive, a
    concierge that sees is the describer of the eyes offer (3.3.6.0 R6:
    agent/eyes_offer.describer, agent/eyes_turn.py): its description
    enters the turn as a snapshot and the main turn goes on with it.
  * the notice digest -- a pending-notice block (round 0b) that would
    reach the main model verbatim is digested to a couple of lines by the
    concierge; the model sees frame + digest, the full text is preserved
    in the log as a meta node (never model-visible) for /tasks and
    resume.
"""
from __future__ import annotations

from typing import Optional

CONCIERGE_ROLE = "concierge"


def resolve_concierge(session):
    """`(ModelRef, ModelProfile)` for `roles.concierge` RIGHT NOW, or None
    when the role is not actually configured (the "fall back to the
    session model" resolution `resolve_role_ref` applies to every unknown
    role means "no entry" here, not "use the main model" -- a concierge
    that IS the orchestrator wakes the orchestrator)."""
    try:
        from halo_harness.roles import resolve_role_ref, resolve_role_table
        role_table = resolve_role_table(provider=session.model_ref.provider)
        ref, profile, _effort, source = resolve_role_ref(
            CONCIERGE_ROLE, role_table=role_table,
            parent_ref=session.model_ref, parent_profile=session.model_profile,
            state_dir=session.state_dir, routes={},
        )
    except Exception:
        return None
    if source == "session model" or ref.raw == session.model_ref.raw:
        return None
    return ref, profile


# ---- /ask: the secretary --------------------------------------------------------

def _history_digest(session, *, max_nodes: int = 120, max_chars: int = 6000) -> str:
    """A deterministic compact rendering of the session's RECENT log: user
    prompts, assistant text heads, tool calls with one-line results, and
    every status notice -- enough for "what's been done" without
    replaying (or paying for) the whole transcript."""
    lines: list = []
    nodes = session.log.nodes()
    for node in nodes[-max_nodes:]:
        ntype = node.get("type")
        if ntype == "user":
            kind = node.get("kind")
            if kind == "steer":
                text = _first_text(node)
                if text:
                    lines.append(f"user (steer): {_clip(text, 120)}")
            elif kind is None:
                text = _first_text(node)
                if text:
                    lines.append(f"user: {_clip(text, 200)}")
        elif ntype == "assistant":
            text = _first_text(node)
            tools = [b.get("name") for b in (node.get("content") or [])
                     if isinstance(b, dict) and b.get("type") == "tool_use"]
            if tools:
                lines.append(f"assistant used tools: {', '.join(tools)}")
            elif text:
                lines.append(f"assistant: {_clip(text, 200)}")
        elif ntype == "tool_result":
            content = node.get("content")
            body = content if isinstance(content, str) else _first_text(node)
            if body:
                lines.append(f"  result: {_clip(body, 140)}")
        elif ntype == "snapshot" and node.get("kind") == "status_notice":
            text = _first_text(node)
            if text:
                lines.append(f"status notice: {_clip(text, 200)}")
    out = "\n".join(lines)
    return out[-max_chars:] if len(out) > max_chars else out


def _first_text(node) -> str:
    for block in node.get("content") or []:
        if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str):
            return block["text"]
    return ""


def _clip(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


def ask_concierge(session, question: str, *, timeout_s: float = 60.0) -> str:
    """One `/ask` answer. Raises only when no concierge is configured
    (callers surface that as setup guidance)."""
    resolved = resolve_concierge(session)
    if resolved is None:
        raise RuntimeError(
            "no concierge configured -- set one with `/roles` or config "
            "(roles.concierge, e.g. or:z-ai/glm-5.3-flash)")
    ref, _profile = resolved
    digest = _history_digest(session)
    system_text = (
        "You are the concierge for a coding session: a fast secretary answering "
        "the human's quick questions WITHOUT involving the main agent. You see a "
        "compact digest of the session's recent history (prompts, actions, tool "
        "results, status notices). Answer briefly and concretely from that "
        "digest; if the digest does not contain the answer, say so in one line. "
        "This exchange is not part of any other conversation.")
    user_text = (f"Session digest so far:\n{digest or '(session just started)'}\n\n"
                 f"Question: {question}")
    return session.call_small_model(system_text=system_text, user_text=user_text,
                                    model_ref=ref, timeout_s=timeout_s)


# ---- the notice digest -----------------------------------------------------------

def digest_notice_block(session, notice_text: str, *, timeout_s: float = 20.0) -> Optional[str]:
    """A 1-3 line digest of a pending-notice block for the MAIN model's
    context; the full text stays in the log (meta node, never
    model-visible). None = no concierge / the call failed: the caller
    keeps the round-0b verbatim delivery."""
    if not notice_text:
        return None
    resolved = resolve_concierge(session)
    if resolved is None:
        return None
    ref, _profile = resolved
    try:
        digest = session.call_small_model(
            system_text="You digest background-work completion notices for a busy coding agent. "
                        "Compress the notice block below to at most three lines: what finished, "
                        "pass/fail, and the one thing (if any) that needs the agent's attention. "
                        "Never invent details.",
            user_text=notice_text,
            model_ref=ref, timeout_s=timeout_s, max_tokens=400,
        )
    except Exception:
        return None
    digest = (digest or "").strip()
    return digest or None
