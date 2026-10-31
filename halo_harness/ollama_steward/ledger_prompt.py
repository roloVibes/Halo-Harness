"""halo_harness.ollama_steward.ledger_prompt -- Halo 3.3.5.0 R4: the fields
the prompt budget adds to a call's ledger line (`ledger_call.py` writes it).

    prompt_fields(session, kind)   before the call: composition {system, memory, topic_index,
                                   tools_schema, history, user, total}, prefix_tokens,
                                   prefix_changed, preflight ("compact" | "switch" | "sent" | None)
    finish(line, reserve, session) after it: warming, cache_reused_pct; 3.3.6.0 R4 (a turn): dialect_record (the
                                   record in force), loop (the loop guard saw one), ladder (the rungs taken)
    is_warming(load_ns)            the call loaded the model first (over 2 s of load)

`preflight` is the decision the preflight took before this call
(agent/preflight.py), consumed by the session's next turn call. `warming` is
the first call after a load (`load_ms` over 2,000): the steward's speed
figures and the status bar never count its tok/s. `cache_reused_pct` is the
share of the prompt Ollama did not read again, from `prompt_eval_count`
against Halo's estimate of the prompt (a count over the estimate, a trimmed
call or a figure under 5 % reads 0; None when the server gave no count).
`prefix_changed` is True when the system prompt, the tools JSON and the
memory placed in it differ from the previous call of the session: the KV
cache cannot be reused past the change.
"""

from __future__ import annotations

from typing import Optional

WARM_LOAD_MS = 2000.0
NOISE_PCT = 5


def is_warming(load_ns) -> bool:
    return isinstance(load_ns, (int, float)) and not isinstance(load_ns, bool) and load_ns / 1e6 > WARM_LOAD_MS


def prompt_fields(session, kind: str) -> dict:
    if session is None or kind not in ("turn", "compaction"):
        return {}
    from halo_harness.agent.prompt_composition import ledger_fields
    out: dict = {}
    comp = getattr(session, "_prompt_composition", None)
    prefix = getattr(session, "_prompt_prefix", None) or {}
    if kind == "turn":
        out["composition"] = ledger_fields(comp)
        out["prefix_tokens"] = prefix.get("tokens")
        prev = getattr(session, "_ledger_prev_prefix", None)
        out["prefix_changed"] = bool(prev) and bool(prefix.get("hash")) and prev != prefix.get("hash")
        session._ledger_prev_prefix = prefix.get("hash") or prev
        out["preflight"] = getattr(session, "_preflight_decision", None)
        session._preflight_decision = None
    return out


def finish(line: dict, reserve: int = 1024, session=None) -> None:
    if session is not None and line.get("kind") == "turn":  # 3.3.6.0 R4: what the dialect and the ladder did
        try:
            from halo_harness.providers.dialect_apply import ledger_view
            line["dialect_record"] = ledger_view(session)
            line["loop"] = bool(getattr(session, "_dialect_loop", None))
            from halo_harness.agent.degrade import ledger_rungs
            line["ladder"] = ledger_rungs(session)
        except Exception:
            pass
    load = line.get("load_ms")
    line["warming"] = isinstance(load, (int, float)) and not isinstance(load, bool) and load > WARM_LOAD_MS
    seen, est = line.get("prompt_eval_count"), line.get("estimate_tokens")
    if line.get("status") != 200 or not isinstance(seen, int) or isinstance(seen, bool) or not isinstance(est, int):
        line.setdefault("cache_reused_pct", None)
        return
    line["cache_reused_pct"] = 0 if line.get("trimmed") else cache_pct(seen, est, reserve)


def cache_pct(seen, estimate, reserve: int = 1024) -> Optional[int]:
    """The share of the prompt (the estimate less the reply's room) Ollama did not read again."""
    if not isinstance(seen, int) or isinstance(seen, bool) or not isinstance(estimate, int):
        return None
    prompt = max(1, estimate - int(reserve or 0))
    pct = int(round(100 * (1 - seen / prompt))) if seen < prompt else 0
    return pct if pct >= NOISE_PCT else 0


def cache_word(pct: Optional[int]) -> str:
    return f"cache reused {pct} %" if isinstance(pct, int) else ""


def speed_lines(lines: list) -> list:
    """The lines whose eval rate counts: answered, not warming."""
    return [x for x in lines if not x.get("warming")]
