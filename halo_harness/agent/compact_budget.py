"""halo_harness.agent.compact_budget -- Halo 3.3.5.0 R4: compaction sized to
the window, and the tail that carried the memory a second time.

    strip_reinjected(log, tail)   the verbatim tail without the snapshot blocks the compaction re-injects
    budget(session, system_text, tools) -> {window, target, fixed, summary_max, tail_max} | None
    over_budget(session) -> Optional[int]    the derived request's prompt part when it is still past the target

The double block (found 2026-10-30): `_run_compaction` keeps a verbatim tail
of the conversation and re-injects every session-start snapshot (CLAUDE.md,
the memory and topic index, the environment, the roster, the deferred tool
names) after its marker. In a short session the tail's one unit is the first
user message, which already holds those snapshots, so the compacted request
carried the memory block twice (the re-injected copy, with the topic index
read again from disk, then the tail's old copy) and CLAUDE.md twice. The
tail is now selected without them.

The budget: `compact_at x window - reserve - (system + tools)` for the model
the compaction runs on; the summary gets at most half of it (never over the
4,096 the summariser always asked for, never under 512) and the tail what is
left. A summary that still does not fit is compacted once more
(`agent/loop.py`'s overflow path), then the preflight line says so.
"""

from __future__ import annotations

from typing import Optional

REINJECTED = ("claude_md", "memory_index", "environment", "roster", "deferred_tools", "plan_mode", "files_read")
SUMMARY_MAX = 4096
SUMMARY_MIN = 512


def _reinjected_texts(log) -> set:
    out = set()
    try:
        nodes = log.nodes()
    except Exception:
        return out
    for n in nodes:
        if n.get("type") == "snapshot" and n.get("kind") in REINJECTED:
            for b in n.get("content") or []:
                if isinstance(b, dict) and b.get("type") == "text" and b.get("text"):
                    out.add(b["text"])
    return out


def strip_reinjected(log, tail: list) -> list:
    """`tail` (derived messages) without any text block that is a snapshot the
    compaction appends again, and without a prior compaction summary (the new
    summary merges it); a user message left empty is dropped when that keeps
    the turns alternating, else it keeps one line."""
    from halo_harness.agent.prompt_composition import SUMMARY_MARK, is_memory_block
    texts = _reinjected_texts(log)
    out: list = []
    tail = list(tail or [])
    for i, msg in enumerate(tail):
        content = msg.get("content") if isinstance(msg, dict) else None
        if msg.get("role") != "user" or not isinstance(content, list):
            out.append(msg)
            continue
        keep = [b for b in content if not (isinstance(b, dict) and b.get("type") == "text" and (
            b.get("text") in texts or is_memory_block(b.get("text")) or SUMMARY_MARK in (b.get("text") or "")))]
        if keep:
            out.append({**msg, "content": keep} if len(keep) != len(content) else msg)
        elif out and out[-1].get("role") == "assistant" and i + 1 < len(tail):
            out.append({**msg, "content": [{"type": "text", "text": "(continued)"}]})
    return out


def _window(session) -> Optional[int]:
    w = getattr(getattr(session, "model_profile", None), "context_tokens", None)
    return w if isinstance(w, int) and w > 0 else None


def budget(session, system_text: str, tools) -> Optional[dict]:
    """The compaction's budget on a local model (None on a cloud model or an unknown window)."""
    from halo_harness.agent.prompt_lean import is_local
    from halo_harness.agent.prompt_composition import tokens_of
    if not is_local(getattr(session, "model_ref", None)):
        return None
    window = getattr(session, "_compaction_tail_window", None) or _window(session)
    if not isinstance(window, int) or window <= 0:
        return None
    from halo_harness.agent.model_switch import COMPACT_AT, class_reserve
    share = COMPACT_AT
    try:
        from halo_harness.ollama_steward.profiles import compact_at, lookup
        ref = session.model_ref
        prof = lookup(ref.host or "default", ref.model) if getattr(ref, "provider", "") == "ollama" else None
        share = compact_at(prof) if prof else COMPACT_AT
        reserve = (prof or {}).get("num_predict") or class_reserve(window)
    except Exception:
        reserve = class_reserve(window)
    reserve = max(int(reserve), int(getattr(session, "_switch_reserve", 0) or 0))
    fixed = tokens_of(system_text) + (tokens_of(tools) if tools else 0)
    target = max(0, int(share * window) - reserve - fixed)
    summary_max = max(SUMMARY_MIN, min(SUMMARY_MAX, target // 2))
    return {"window": window, "target": target, "fixed": fixed, "reserve": reserve,
            "summary_max": summary_max, "tail_max": max(0, target - summary_max)}


def again_lines(session, turn_no: int):
    """After an overflow compaction: the conversation still past its budget -> one more
    compaction; then, still over, the line (and when the fixed part alone is over, that line)."""
    from halo_harness import events
    got = over_budget(session)
    if got is None:
        return
    prompt, b = got
    if b["target"] <= 0:
        yield events.turn_marker("preflight", f"↳ the system prompt, the memory and the tools alone are "
                                 f"{b['fixed']:,} tokens, more than this {b['window']:,} window holds with the reply's "
                                 f"{b['reserve']:,}: a bigger-window model holds them", turn=turn_no)
        return
    yield events.turn_marker("resend", f"↳ the compacted request ({prompt:,} tokens) is still past the window's "
                             "budget: compacting once more", turn=turn_no)
    yield from session._run_compaction(turn_no, trigger="overflow")
    got = over_budget(session)
    if got is not None:
        yield events.turn_marker("preflight", f"↳ after two compactions the request is {got[0]:,} tokens, past the "
                                 "window's budget: the turn's own tool output is cut on the wire to fit", turn=turn_no)


def over_budget(session) -> "Optional[tuple[int, dict]]":
    """(the shaped request's prompt tokens, the budget) when they are past the budget's target plus
    the fixed part, else None."""
    from halo_harness.agent.derive import derive_request
    from halo_harness.agent.model_switch import estimate
    try:
        from halo_harness.agent.prompt_wire import shape
        system_text, messages, tools = shape(session, *derive_request(session.log, tools=None), purpose="compaction")
        b = budget(session, system_text, tools)
        if b is None:
            return None
        prompt = estimate(system_text, messages, tools)
        return (prompt, b) if prompt > b["target"] + b["fixed"] else None
    except Exception:
        return None
