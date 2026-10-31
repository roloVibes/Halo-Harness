"""halo_harness.agent.model_switch -- Halo 3.3.5.0 R0: a session fits the
model it moves to, in one explicit step.

    plan(session, ref, ...) -> SwitchReport (a dict)
    run_switch(session, ref, profile, creds, *, why)   `/model`: a generator of events
    fit_session_to(session, ref, *, why)               the session is already on `ref`

SwitchReport = {from, to, why, window, source, ceiling, prompt_tokens,
compacted, converted: {images, thinking, tools}, tools_max, reserve, effort,
target_tokens, needs_compaction, line}.

The step: (a) the target's window (`agent/model_window.window_of`, the source
named); (b) one line before anything moves ("switching to ol:qwen3.5:9b@lan:
window 32,768 (learned cap); this conversation is 48,210 tokens ->
compacting to fit · effort: think off"), in the transcript (a `turn_marker`
of state "switch", which Studio's Live shows too) and the session log (a
`model_switch` node with the report); (c) the history fitted: compacted to
`compact_at` (the profile's, 0.8 when unset) of the target's window before
the first call (the compaction path with `trigger: "switch"`), the tool
catalog re-capped for the window's class, what the target cannot take
converted on the wire (`model_switch_history`); (d) the reply reserve: the
profile's `num_predict`, else the window class's default.

`/model` compacts BEFORE moving, on the model the session is leaving (its
window holds the history; a configured compaction model writes the summary
instead, its own window checked first). The other paths (a resumed session
on another model, an Auto lineup child, a profile that lowered the window)
find the session already on the target: the compaction runs before its first
call, on that model, from a transcript bounded to its window.
"""

from __future__ import annotations

import dataclasses
import logging
from typing import Optional

from halo_harness import events

log = logging.getLogger("bridge")

COMPACT_AT = 0.8
# the reply's room per window class (a tool call's arguments -- a file Write -- ride in the reply)
CLASS_RESERVE = ((16384, 2048), (32768, 4096), (65536, 8192))
CLASS_RESERVE_TOP = 16384


def class_reserve(window: Optional[int]) -> int:
    if not isinstance(window, int) or window <= 0:
        return 2048
    for below, reserve in CLASS_RESERVE:
        if window < below:
            return reserve
    return CLASS_RESERVE_TOP


def _env(session):
    return getattr(getattr(session, "settings", None), "effective_env", None)


def _ollama_facts(session, ref) -> "tuple[Optional[dict], Optional[dict], Optional[bool]]":
    """(catalog row, steward profile, tools probe) for an `ol:` ref; Nones elsewhere."""
    if getattr(ref, "provider", "") != "ollama":
        return None, None, None
    try:
        from halo_harness.providers.ollama import get_catalog, resolve_ollama_host
        from halo_harness.providers.ollama_hw import catalog_row
        host = resolve_ollama_host(ref.host, _env(session))
        if host is None:
            return None, None, None
        row = catalog_row(get_catalog(host), ref.model)
        from halo_harness.ollama_steward.profiles import lookup
        profile = lookup(host, ref.model)
        probe = None
        digest = (row or {}).get("digest")
        if digest and getattr(session, "state_dir", None) is not None:
            from halo_harness.providers.ollama_capability import load_capability_cache
            entry = load_capability_cache(session.state_dir).get(digest)
            probe = entry.get("tool_calls") if isinstance(entry, dict) else None
        return row, profile, probe
    except Exception:
        log.debug("model_switch: the Ollama facts for %s could not be read", getattr(ref, "raw", ref), exc_info=True)
        return None, None, None


def history(session) -> "tuple[str, list, list]":
    from halo_harness.agent.derive import derive_request
    return derive_request(session.log, tools=None)


def estimate(system_text: str, messages, tools) -> int:
    """The prompt part of a request (chars / 3.5), without the reply's room."""
    from halo_harness.providers.ollama_prompt import estimate_request_tokens, reply_reserve
    return estimate_request_tokens(messages, tools, system_text) - reply_reserve(None)


def plan(session, ref, *, model_profile=None, why: str = "/model", readers=None,
         catalog_row=None, profile=None, tools_probe=None, prev_ref=None) -> dict:
    from halo_harness.agent.model_switch_history import caps_for, convert
    from halo_harness.agent.model_window import window_of
    from halo_harness.providers.effort_on import effort_on, think_choice_for
    if catalog_row is None and profile is None and tools_probe is None:
        catalog_row, profile, tools_probe = _ollama_facts(session, ref)
    from halo_harness.agent.model_window import kind_of
    if kind_of(ref) == "cloud" and getattr(model_profile, "context_tokens", None):
        readers = {"cloud": lambda _r: model_profile.context_tokens, **(readers or {})}
    w = window_of(ref, state_dir=getattr(session, "state_dir", None), catalog=catalog_row, readers=readers)
    vision = getattr(model_profile, "vision", None)
    caps = caps_for(ref, catalog_row=catalog_row, vision=vision, tools_probe=tools_probe)
    system_text, messages, tools = history(session)
    converted, counts = convert(messages, caps)
    tools_for_estimate = [] if not caps["tools"] else tools
    prompt = estimate(system_text, converted, tools_for_estimate)
    window = w["tokens"]
    from halo_harness.ollama_steward.profiles import compact_at
    share = compact_at(profile) if profile else COMPACT_AT
    reserve = (profile or {}).get("num_predict") or class_reserve(window)
    target = max(0, min(int(share * window), window - reserve)) if window else None
    if getattr(ref, "provider", "") == "ollama":
        from halo_harness.providers.ollama_fit import resolve_ollama_tools_max
        tools_max = (profile or {}).get("tools_max") or resolve_ollama_tools_max(window)
    else:
        from halo_harness.agent.catalog import host_cap
        tools_max = host_cap(getattr(ref, "provider", ""))
    if not caps["tools"]:
        tools_max = 0
    eff = effort_on(ref, catalog_row, effort=getattr(session, "effort", None),
                    explicit=getattr(session, "effort_source", None) in ("flag", "session"),
                    think_choice=think_choice_for(getattr(ref, "raw", "") or ""))
    old = prev_ref if prev_ref is not None else getattr(session, "model_ref", None)
    report = {"from": getattr(old, "raw", None), "to": getattr(ref, "raw", None), "why": why, "window": window,
              "source": w["source"], "ceiling": w["ceiling"], "prompt_tokens": prompt, "compacted": False,
              "converted": {k: counts.get(k, 0) for k in ("images", "thinking", "tools")}, "tools_max": tools_max,
              "reserve": reserve, "effort": eff["word"], "effort_kind": eff["kind"], "target_tokens": target,
              "compact_at": share, "needs_compaction": bool(target and prompt > target), "caps": caps}
    report["line"] = line_for(report)
    return report


LEADS = {"profile": "the steward profile lowered {to}'s window", "resume": "resumed on {to}",
         "auto": "the task runs on {to}", "start": "this session runs on {to}",  # start: 3.3.5.0 R1
         "eyes": "this turn sees through {to} (the visual lane)"}  # eyes: 3.3.6.0 R6, back after the turn


def line_for(r: dict) -> str:
    to = r.get("to") or "?"
    lead = LEADS.get(r.get("why") or "", "switching to {to}").format(to=to)
    what = "this conversation" if r.get("why") != "auto" else "the task"
    if not r.get("window"):
        head = f"{lead}: window unknown; {what} is {r['prompt_tokens']:,} tokens"
    elif r.get("needs_compaction"):
        head = (f"{lead}: window {r['window']:,} ({r['source']}); {what} is "
                f"{r['prompt_tokens']:,} tokens -> {'cut' if r.get('why') == 'auto' else 'compacting'} to fit")
    else:
        head = f"{lead}: window {r['window']:,} ({r['source']}); fits ({r['prompt_tokens']:,} of {r['window']:,})"
    return head + (f" · effort: {r['effort']}" if r.get("effort") else "")


def after_line(r: dict) -> str:
    bits = []
    if r.get("compacted"):
        bits.append(f"compacted to {r.get('prompt_after', 0):,} tokens")
    elif r.get("needs_compaction"):
        bits.append("compacts before the first call")
    conv = r.get("converted") or {}
    done = [f"{n} {word}" for word, n in (("images to captions", conv.get("images")),
                                          ("thinking blocks dropped", conv.get("thinking")),
                                          ("tool turns as text", conv.get("tools"))) if n]
    bits.extend(done)
    bits.append(f"tools {r['tools_max']}" if r.get("tools_max") else "no tools (answers only)")
    bits.append(f"reply reserve {r['reserve']:,}")
    return f"on {r.get('to')}: " + "; ".join(bits)


def _record(session, report: dict) -> None:
    keep = {k: v for k, v in report.items() if k != "caps"}
    try:
        session.log._append({"type": "model_switch", "report": keep})
    except Exception:
        log.debug("model_switch: the log node could not be written", exc_info=True)


def finish(session, report: dict) -> None:
    """Apply the fitted state to a session that is now on `report["to"]`."""
    window = report.get("window")
    from halo_harness.agent.model_window import kind_of
    local = kind_of(getattr(session, "model_ref", None)) != "cloud"
    if local and isinstance(window, int) and window > 0 and getattr(session, "model_profile", None) is not None:
        try:
            session.model_profile = dataclasses.replace(session.model_profile, context_tokens=window)
        except (TypeError, ValueError):
            pass
    dialect = getattr(getattr(session, "route", None), "dialect", None)
    session._switch_caps = dict(report.get("caps") or {}, model=report.get("to"), **({"dialect": dialect} if dialect else {}))
    session._switch_reserve = report.get("reserve")
    session._switch_fitted_for = getattr(getattr(session, "model_ref", None), "model", None)
    session._ledger_switched_from = report.get("from")
    catalog =getattr(session, "session_catalog", None)
    if getattr(getattr(session, "route", None), "dialect", None) == "ollama" and hasattr(session, "_sync_ollama_tools_cap"):
        try:
            session._sync_ollama_tools_cap()
        except Exception:
            log.debug("model_switch: re-capping the tool catalog failed", exc_info=True)
    elif catalog is not None and report.get("tools_max"):
        catalog.cap = min(catalog.cap, report["tools_max"]) if catalog.cap else report["tools_max"]
    _record(session, report)


def _compact(session, report: dict, turn_no: int):
    """The compaction to the target's window, as events; returns True when it wrote one."""
    session._compaction_tail_window = report.get("window")
    try:
        done = yield from session._run_compaction(turn_no, trigger="switch")
    finally:
        session._compaction_tail_window = None
    if done:
        system_text, messages, tools = history(session)
        report["compacted"] = True
        report["prompt_after"] = estimate(system_text, messages, tools)
    return bool(done)


def run_switch(session, ref, model_profile, creds, *, why: str = "/model"):
    """`/model`: say it, compact on the model being left when the target's window needs it, move, fit."""
    report = plan(session, ref, model_profile=model_profile, why=why)
    turn_no = getattr(session, "turn_count", 0) or 0
    yield events.turn_marker("switch", report["line"], turn=turn_no, report={k: v for k, v in report.items() if k != "caps"})
    if report["needs_compaction"]:
        compacted = yield from _compact(session, report, turn_no)
        if not compacted:
            session._switch_compact_pending = True
    session.set_model(ref, model_profile, creds)
    finish(session, report)
    yield events.turn_marker("switch", after_line(report), turn=turn_no)
    return report


def fit_session_to(session, ref=None, *, why: str, prev_ref=None) -> dict:
    """The session is already on `ref`: say it (queued for the next step), fit, and leave the compaction
    (when the window needs one) to run before the first call."""
    ref = ref or session.model_ref
    report = plan(session, ref, model_profile=getattr(session, "model_profile", None), why=why, prev_ref=prev_ref)
    finish(session, report)
    lines = getattr(session, "_switch_lines", None)
    if not isinstance(lines, list):
        lines = session._switch_lines = []
    lines.append(report["line"])
    if report["needs_compaction"]:
        session._switch_compact_pending = True
    return report
