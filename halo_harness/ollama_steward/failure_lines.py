"""halo_harness.ollama_steward.failure_lines -- Halo 3.3.6.0 R1: a server
event said with its fix, read off the model's battery profile
(plans/local-model-fit-brief.md E5; the loop's own lines are
agent/local_failure.py). `server_events.record_events` passes every event
through `explain` before it is written, so the steward's findings, the
Local tab's traffic and `halo ollama events` say the same line.

    explain(event, state_dir, fingerprint=None) -> the event, its `say` ending in the fix and `fix` set when a rule
        applies (3.3.6.0 R3: a crash with its fingerprint ends in the fingerprint's line, profile or not)
    swap_line(models, host, state_dir) -> "two models can't co-reside on this card: ..." | ""

    cpu-spill   "it didn't fit (59/66 layers on GPU): lower the window to <usable> or use <smaller model>"
    slow-load / a load past COLD_S   "cold load of 17 GB, ~25 s: pin it (keep_alive -1) or pre-warm"
An event about a model with no profile stays as the rule said it.
"""

from __future__ import annotations

from typing import Optional

COLD_S = 10.0


def _profile(state_dir, model: Optional[str], host: Optional[str]) -> Optional[dict]:
    if not model or state_dir is None:
        return None
    from halo_harness.providers.ollama_capability import profile_for
    return profile_for(state_dir, model, host) or profile_for(state_dir, model)


def _smaller(state_dir, model: str, size_gb) -> str:
    from halo_harness.providers.ollama_capability import all_profiles
    from halo_harness.providers.ollama import ollama_names_match
    if not isinstance(size_gb, (int, float)):
        return "a smaller model"
    rows = [p for p in all_profiles(state_dir) if isinstance(p.get("size_gb"), (int, float)) and p["size_gb"] < size_gb
            and not ollama_names_match(p.get("model"), model) and p.get("tools") == "yes"]
    rows.sort(key=lambda p: -p["size_gb"])
    return f"ol:{rows[0]['model']}" if rows else "a smaller model"


def explain(ev: dict, state_dir, fingerprint: Optional[dict] = None) -> dict:
    try:
        kind, model, d = ev.get("kind"), ev.get("model"), ev.get("data") or {}
        if fingerprint:  # 3.3.6.0 R3: a crash the loop read off the log names its fingerprint (fingerprints.py)
            fix = f"{fingerprint.get('line') or 'crashed here'} (halo ollama crashes --why)"
            return {**ev, "say": f"{ev.get('say')} -- {fix}" if ev.get("say") else fix, "fix": fix}
        p = _profile(state_dir, model, ev.get("host"))
        if not p:  # the fix is read off the battery's profile: an unprobed model's event stays as the rule said it
            return ev
        fix = ""
        if kind == "cpu-spill":
            a, b = d.get("offloaded"), d.get("layers")
            lay = f"{a}/{b} layers on GPU" if isinstance(a, int) and isinstance(b, int) else "part of it on the CPU"
            usable = ((p or {}).get("window") or {}).get("usable")
            window = f"lower the window to {usable:,}" if isinstance(usable, int) and usable > 0 else "lower the window"
            fix = f"it didn't fit ({lay}): {window} or use {_smaller(state_dir, model or '', (p or {}).get('size_gb'))}"
        elif kind == "slow-load" or (kind == "loaded" and isinstance(d.get("load_s"), (int, float)) and d["load_s"] >= COLD_S):
            secs = d.get("seconds") or d.get("load_s")
            size = f"{p['size_gb']:g} GB" if p and p.get("size_gb") else (model or "the model")
            fix = f"cold load of {size}, ~{float(secs or 0):.0f} s: pin it (keep_alive -1) or pre-warm"
        if fix:
            return {**ev, "say": f"{ev.get('say')} -- {fix}" if ev.get("say") else fix, "fix": fix}
    except Exception:
        pass
    return ev


def swap_line(models: list, host: str, state_dir) -> str:
    """The thrash finding's fix when two of `models` cannot co-reside on `host` (their profiles say so)."""
    from halo_harness.providers.ollama import ollama_names_match
    for i, a in enumerate(models or []):
        pa = _profile(state_dir, a, host)
        res = (pa or {}).get("resident") or {}
        if res.get("pivot_only") is None:
            continue
        for b in models[i + 1:]:
            if not any(ollama_names_match(n, b) for n in res.get("co_resides_with") or []):
                return (f"{a} and {b} can't co-reside on this card (probed): make one resident (keep_alive -1) and "
                        "pivot explicitly")
    return ""
