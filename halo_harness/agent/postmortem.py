"""halo_harness.agent.postmortem -- Halo 3.3.6.0 R4: the answer post-mortem
(plans/local-model-fit-brief.md Part G9): what the model actually saw for one
assistant turn, reconstructed in one plain line with the details beneath.

    postmortem(state_dir, session_id, *, turn=None, at=None, nodes=None) -> {ok, line, details [str], causes {...},
        model, host, turn, session, dialect, ladder, calls}
        turn None: the newest turn; `at` (unix seconds): the turn whose call ended at or before it (Studio's
        Live row); `nodes`: the session log's nodes (the TUI has them; else the log is read by the session id)

Sources: the ledger's lines of that turn (`session`, `turn`; ollama_steward/ledger.py) -- `trimmed`,
`prompt_eval_count` against `estimate_tokens` and `num_ctx_sent`, `composition` (agent/prompt_composition.py:
system / memory / topics / tools / history / you), `tools_count`, `done_reason`, `cache_reused_pct`,
`log_events` (the server log's kinds, agent/ollama_log_recovery.py), `dialect_record` and `ladder` -- and the
transcript (a thinking block and no text in the turn's last assistant message). The causes, in the order the
line names them: cut (where, how much), an empty reply from a small budget (`num_predict` hit), thinking only,
memory-dominated (memory and topics over half the prompt), no tools offered; then the cache. A turn with no
ledger line (a cloud model, the ledger off) says so.
"""

from __future__ import annotations

from typing import Optional

MEMORY_SHARE = 0.5


def _lines_of(state_dir, session_id: str, turn, at) -> "tuple[list, Optional[int]]":
    from halo_harness.ollama_steward.ledger import parse_at, read_calls
    rows = [x for x in read_calls(state_dir) if x.get("session") == session_id and x.get("kind") == "turn"]
    if not rows:
        return [], None
    if turn is None and at is not None:
        before = [x for x in rows if (parse_at(x.get("at")) or 0) <= float(at) + 5]
        turn = (before or rows)[-1].get("turn")
    if turn is None:
        turn = rows[-1].get("turn")
    return [x for x in rows if x.get("turn") == turn], turn


def _turn_nodes(nodes: list, turn) -> list:
    """The assistant messages of the `turn`-th user prompt (1-based)."""
    from halo_harness.session_trace import NOT_A_PROMPT
    n, out = 0, []
    for node in nodes or []:
        if node.get("type") == "user" and node.get("kind") not in NOT_A_PROMPT and any(
                isinstance(b, dict) and b.get("type") == "text" for b in node.get("content") or []):
            n += 1
            continue
        if node.get("type") == "assistant" and isinstance(turn, int) and n == turn:
            out.append(node)
    return out


def _read_nodes(session_id: str) -> list:
    try:
        from halo_harness.session_trace import _read
        from halo_harness.session_trace_cli import find_session_log
        path, _why = find_session_log(session_id)
        return _read(path) if path is not None else []
    except Exception:
        return []


def _thinking_only(msgs: list) -> bool:
    if not msgs:
        return False
    last = msgs[-1].get("content") or []
    thought = any(isinstance(b, dict) and b.get("type") == "thinking" and str(b.get("text") or "").strip() for b in last)
    said = any(isinstance(b, dict) and b.get("type") in ("text", "tool_use") and (b.get("type") == "tool_use" or str(
        b.get("text") or "").strip()) for b in last)
    return thought and not said


def postmortem(state_dir, session_id: str, *, turn=None, at=None, nodes=None) -> dict:
    lines, turn = _lines_of(state_dir, session_id, turn, at) if state_dir is not None and session_id else ([], None)
    if not lines:
        return {"ok": False, "line": "no local call is recorded for that turn (a cloud model, or the traffic ledger "
                "is off): nothing to reconstruct", "details": [], "causes": {}, "turn": turn, "session": session_id}
    last = lines[-1]
    seen, est, ctx = last.get("prompt_eval_count"), last.get("estimate_tokens"), last.get("num_ctx_sent")
    comp = last.get("composition") or {}
    kinds = sorted({k for x in lines for k in (x.get("log_events") or [])})
    causes: dict = {}
    cut = next((x for x in lines if x.get("trimmed") or "prompt-trimmed" in (x.get("log_events") or [])), None)
    if cut:
        s, e, c = cut.get("prompt_eval_count"), cut.get("estimate_tokens"), cut.get("num_ctx_sent")
        causes["cut"] = {"read": s, "sent": e, "window": c}
        lost = (f"; about {e - s:,} tokens were dropped" if isinstance(e, int) and isinstance(s, int) and e > s else "")
        causes["cut"]["say"] = (f"the prompt was cut at {s:,} of {c:,}" if isinstance(s, int) and isinstance(c, int)
                                else "the prompt was cut") + lost + ": Ollama keeps 4 tokens of the front and the tail, " \
                                "so the task summary at the front was dropped"
    if last.get("done_reason") == "length" or "reply-cut" in kinds:
        causes["budget"] = {"say": f"the reply hit its budget ({last.get('eval_count') or 0:,} tokens, num_predict)"}
    msgs = _turn_nodes(nodes if nodes is not None else _read_nodes(session_id), turn)
    if _thinking_only(msgs):
        causes["thinking_only"] = {"say": "it answered in thinking only: no text reached the reply"}
    total = comp.get("total") or 0
    mem = (comp.get("memory") or 0) + (comp.get("topic_index") or 0)
    if total and mem / total > MEMORY_SHARE:
        causes["memory"] = {"share": round(mem / total, 2), "say": f"memory was {mem / total:.0%} of the prompt "
                            f"({mem:,} of {total:,} tokens): the task had little room"}
    if not last.get("tools_count") and not (last.get("body_flags") or {}).get("tools"):
        causes["no_tools"] = {"say": "no tools were offered (the tool budget, or a model that takes none)"}
    cache = last.get("cache_reused_pct")
    order = ("cut", "budget", "thinking_only", "memory", "no_tools")
    named = [causes[k]["say"] for k in order if k in causes]
    tail = f"{cache} % of the prompt reused from cache" if isinstance(cache, int) else "cache reuse not measured"
    line = "; ".join(named[:2]) if named else f"nothing cut; {tail}"
    host = (last.get("host") or {}).get("name")
    details = [f"{last.get('model')} on {host}, turn {turn}, {len(lines)} call{'s' if len(lines) != 1 else ''}",
               f"prompt: Ollama read {seen if seen is not None else '?'} of about {est if est is not None else '?'} "
               f"tokens sent, window {ctx if ctx is not None else '?'}"]
    if comp:
        parts = [("system", "system"), ("memory", "memory"), ("topic_index", "topics"), ("tools_schema", "tools"),
                 ("history", "history"), ("user", "you")]
        details.append(f"prompt {comp.get('total') or 0:,}: " + " · ".join(f"{w} {comp.get(k) or 0:,}" for k, w in parts))
    details += [c for c in named[2:]]
    details.append(f"tools offered: {last.get('tools_count') or 0}; reply {last.get('eval_count') or 0:,} tokens "
                   f"({last.get('done_reason') or '?'}); {tail}")
    if kinds:
        details.append("the server log showed: " + ", ".join(kinds))
    if last.get("dialect_record"):
        d = last["dialect_record"]
        details.append(f"dialect in force: instructions in {d.get('placement')}, reserve {d.get('reserve')}, repair "
                       f"{d.get('repair')}, loop guard {'on' if d.get('guard') else 'off'}, thinking {d.get('thinking')}")
    ladder = [r for x in lines for r in (x.get("ladder") or [])]
    seen_lines, rungs = set(), []
    for r in ladder:
        if r.get("line") not in seen_lines:
            seen_lines.add(r.get("line"))
            rungs.append(r)
    details += [f"ladder: {r.get('line')}" for r in rungs]
    if any(x.get("loop") for x in lines):
        details.append("the loop guard saw it repeat itself")
    return {"ok": True, "line": line, "details": details, "causes": causes, "model": last.get("model"), "host": host,
            "turn": turn, "session": session_id, "dialect": last.get("dialect_record"), "ladder": rungs,
            "cache_reused_pct": cache, "calls": len(lines)}
