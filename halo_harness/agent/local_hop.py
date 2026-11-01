"""halo_harness.agent.local_hop -- local -> local escalation: the bigger capable local model before any cloud rung
(Halo 3.3.7.0 R3; plans/local-model-fit-brief.md D1 4), so "switch when needed" stays offline.

    pick(session) -> {ref, model, host, size, words, fits, load_s, load_from, warm, pivot, line} | (None, why)
    rung(session, turn_no, trigger, n, p) -> a generator: the ladder's `bigger-local` rung (agent/degrade.py);
        returns {"rung", "do": "rebuild"} when it switched, None when it was not taken (said, or silent for a trigger
        it does not answer)
    escalate(session, turn_no, trigger) -> a generator: the same hop at the escalation points
        (Session._maybe_escalate); True when it switched

The candidates are the probed local models that call tools (the capability profile, providers/placement.with_tools)
whose placement verdict for the session's role is not a no, heavier than the model in use (its weights, the
catalog row), that fit their card alone at the lane's window (local_sched/facts: weights + KV, the reserve, the
helper's footprint; a card not read is said, never guessed). The next size up wins (the smallest step that is
bigger), agentic-ready first on a tie. On the same card as the model in use and not beside it, the hop is a pivot
(local_sched/pivot.py: one at a time per card, the minimum residency); the line names its cost either way. The
triggers: escalation's low_confidence / tool_failures / context_overflow (agent/escalation.local_hop_triggers);
`routing.local_hop` (default: true on a local-first session) turns it off.
"""

from __future__ import annotations

import logging
from typing import Optional

from halo_harness import events

log = logging.getLogger("bridge")

ANSWERS = ("low_confidence", "tool_failures", "context_overflow")


def _size_words(row: Optional[dict]) -> str:
    d = (row or {}).get("details") or {}
    if d.get("parameter_size"):
        return str(d["parameter_size"])
    size = (row or {}).get("size")
    return f"{size / 1e9:.1f} GB" if isinstance(size, int) else "?"


def pick(session):
    from halo_harness.local_sched import facts as F
    from halo_harness.local_sched.swap_cost import secs
    from halo_harness.providers.ollama import ollama_names_match
    from halo_harness.providers.placement import profile_for_ref, verdict, with_tools
    ref = getattr(session, "model_ref", None)
    if getattr(ref, "provider", "") != "ollama":
        return None, "the session is not on a local Ollama model"
    state = getattr(session, "state_dir", None)
    me_host = F.host_named(getattr(ref, "host", None))
    mine, _src = F.row(me_host, ref.model)
    if not isinstance((mine or {}).get("size"), int):
        return None, f"the weights of {ref.model} were not read"
    role = getattr(session, "role_name", None) or "main"
    found, said = [], []
    for raw in with_tools(state):
        model, hname = F.split_ref(raw)
        host = F.host_named(hname)
        if host is None or ollama_names_match(model, ref.model):
            continue
        row, _r = F.row(host, model)
        if not isinstance((row or {}).get("size"), int) or row["size"] <= mine["size"]:
            continue
        from halo_harness.local_sched.reserve import claimed_bytes, held  # 3.3.7.0 R5: a bundle's reservation
        c = held(host, model, state_dir=state)
        if c:
            said.append(f"{raw} is reserved for {c['bundle']}")
            continue
        v = verdict(profile_for_ref(raw, state), role, state_dir=state)
        if v.get("ok") is False:
            said.append(f"{raw}: {v['why']}")
            continue
        card = F.card(host)
        rows = F.loaded(host)
        b = F.budget(card, host.name)
        held_b = claimed_bytes(host, state_dir=state)
        room = F.usable(b, F.helper(host, rows)) - held_b
        w, _wf = F.window(host, model, role=role, row_=row, card_=card)
        fits = None if not b.get("budget") else F.together(b, [{"row": row, "window": w}]) <= room
        if fits is False:
            from halo_harness.local_sched.reserve import holds_words
            said.append(f"{raw} does not fit {host.name} at {w:,}" + (f" ({holds_words(host, state_dir=state)} there)"
                                                                      if held_b else ""))
            continue
        warm = F.is_loaded(rows, model, w)
        same = me_host is not None and str(host.url).rstrip("/") == str(me_host.url).rstrip("/")
        beside = bool(fits) and same and F.together(b, [{"row": row, "window": w}, {"row": mine, "window": w}]) <= room
        load_s, load_from = _cost(host, model, state, row, warm)
        found.append({"ref": raw, "model": model, "host": host.name, "size": row["size"], "words": _size_words(row),
                      "fits": fits, "warm": warm, "window": w, "pivot": bool(fits) and same and not beside and not warm,
                      "ready": bool((profile_for_ref(raw, state) or {}).get("agentic_ready")),
                      "load_s": load_s, "load_from": load_from})
    if not found:
        return None, ("; ".join(said[:2]) or "no bigger probed local model with tools here")
    best = sorted(found, key=lambda c: (c["size"], not c["ready"], c["ref"]))[0]
    if best["warm"]:
        cost = "already warm"
    elif best["load_s"] is not None:
        cost = f"{'a pivot' if best['pivot'] else 'a load'} ~{secs(best['load_s'])} ({best['load_from']})"
    else:
        cost = "load time unknown"
    fit = "" if best["fits"] else ", fit not read"
    best["line"] = f"{best['ref']} ({best['words']} over {_size_words(mine)}; {cost}{fit})"
    return best, ""


def _cost(host, model, state, row, warm) -> tuple:
    if warm:
        return None, None
    from halo_harness.local_sched.swap_cost import load_s_for
    c = load_s_for(host, model, state_dir=state, row=row, fetch=False)
    return c["s"], c["source"]


def _hop(session, turn_no: int, best: dict):
    if best.get("pivot"):
        from halo_harness.local_sched import facts as F
        from halo_harness.local_sched.pivot import plan, run
        ref = session.model_ref
        host = F.host_named(best["host"])
        p = plan(host, ref.model, best["model"], window=best["window"], labels=("this model", "the bigger one"),
                 state_dir=getattr(session, "state_dir", None))
        yield from run(p, host=host, session=session, turn=turn_no)
    from halo_harness.agent.preflight import _switch
    yield from _switch(session, best["ref"], turn_no)


def rung(session, turn_no: int, trigger: str, n: int, p: dict):
    from halo_harness.agent.escalation import local_hop_enabled
    if trigger not in ANSWERS:
        return None
    if not local_hop_enabled(session):
        yield events.turn_marker("ladder", f"↳ rung {n}: a bigger local model -- not taken: routing.local_hop is off",
                                 turn=turn_no)
        p["taken"].append({"rung": "bigger-local", "trigger": trigger, "line": "routing.local_hop is off", "skipped": True})
        return None
    best, why = pick(session)
    if best is None:
        yield events.turn_marker("ladder", f"↳ rung {n}: a bigger local model -- none: {why}; next rung", turn=turn_no)
        p["taken"].append({"rung": "bigger-local", "trigger": trigger, "line": why, "skipped": True})
        return None
    line = f"rung {n}: a bigger local model -- {best['line']}"
    yield events.turn_marker("ladder", f"↳ {line}", turn=turn_no, hop=best)
    try:
        yield from _hop(session, turn_no, best)
    except Exception:
        log.debug("local_hop: the hop to %s failed", best["ref"], exc_info=True)
        return None
    p["taken"].append({"rung": "bigger-local", "trigger": trigger, "line": line})
    return {"rung": "bigger-local", "do": "rebuild"}


def escalate(session, turn_no: int, trigger: str):
    """The hop at Session._maybe_escalate's two points, once a turn (the ladder's pass shares it): "hopped" (it
    switched, or the ladder's rung did this turn), "deferred" (`tool_failures` is the ladder's own trigger between
    tool rounds: while its rungs still hold `bigger-local`, no cloud escalation goes ahead of it), or False."""
    from halo_harness.agent.degrade import _pass, rungs
    p = _pass(session, turn_no)
    done = [t for t in p["taken"] if t.get("rung") == "bigger-local"]
    if any(not t.get("skipped") for t in done):
        return "hopped"
    if done:
        return False
    best, why = pick(session)
    if best is None:
        p["taken"].append({"rung": "bigger-local", "trigger": trigger, "line": why, "skipped": True})
        return False
    if trigger == "tool_failures" and "bigger-local" in rungs():
        return "deferred"
    line = f"{trigger}: a bigger local model first -- {best['line']}"
    yield events.turn_marker("ladder", f"↳ {line}", turn=turn_no, hop=best)
    try:
        yield from _hop(session, turn_no, best)
    except Exception:
        log.debug("local_hop: the hop to %s failed", best["ref"], exc_info=True)
        return False
    p["taken"].append({"rung": "bigger-local", "trigger": trigger, "line": line})
    yield events.system_note(f"escalated locally to {best['ref']}: {trigger}")
    return "hopped"
