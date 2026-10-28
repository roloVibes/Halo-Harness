"""halo_harness.agent.model_switch_paths -- Halo 3.3.5.0 R0: the switch
step's other callers (`agent/model_switch.py` holds the step):

- `profile_change_check` -- a steward profile that lowered an Ollama model's
  window below the live prompt: the step, before the next call (`_step`);
- `resumed_on_another_model` -- a resumed log whose last model is not the
  session's (`halo -p --model X --resume`): the step at session start;
- `drain_lines` -- the switch lines the step queued, said by the next step;
- `summary_window` -- the summariser's own window, checked before the
  summary call (`_run_compaction`).
"""

from __future__ import annotations

import logging
from typing import Optional

from halo_harness.agent.model_switch import estimate, fit_session_to

log = logging.getLogger("bridge")

SUMMARY_REPLY = 4096  # `_run_compaction` asks for at most this many tokens of summary


def profile_change_check(session) -> Optional[dict]:
    """A steward profile that lowered this Ollama model's window below the live prompt: the step, before the call."""
    if getattr(getattr(session, "route", None), "dialect", None) != "ollama":
        return None
    last = (getattr(session, "_ollama_window_state", None) or {}).get("last") or {}
    profile = last.get("profile") or {}
    now = (profile.get("at"), profile.get("num_ctx"), last.get("model"))
    seen = getattr(session, "_switch_profile_seen", None)
    session._switch_profile_seen = now
    if seen is None or seen == now or seen[2] != now[2] or not now[1]:
        return None
    if seen[1] and now[1] >= seen[1]:
        return None
    from halo_harness.ollama_steward.profiles import compact_at
    if int(last.get("estimate") or 0) <= compact_at(profile) * now[1]:
        return None
    return fit_session_to(session, why="profile", prev_ref=session.model_ref)


def resumed_on_another_model(session, nodes) -> Optional[dict]:
    """A resumed log whose last model differs from the session's (`halo -p --model X --resume`): the step."""
    try:
        last = next((n.get("model") for n in reversed(nodes or []) if n.get("type") == "meta" and n.get("model")), None)
        now = getattr(getattr(session, "model_ref", None), "raw", None)
        if not last or not now or last == now:
            return None
        from types import SimpleNamespace
        report = fit_session_to(session, why="resume", prev_ref=SimpleNamespace(raw=last))
        session.log.append_meta(model=now)
        return report
    except Exception:
        log.debug("model_switch: the resume check failed", exc_info=True)
        return None


def drain_lines(session) -> list:
    lines = getattr(session, "_switch_lines", None) or []
    session._switch_lines = []
    return lines


def summary_window(session, system_text: str, messages, tools, *, always: bool = False) -> "tuple[Optional[int], int]":
    """(the summariser's window, the summary call's estimate): `_run_compaction` checks the
    compaction model's own window the same way before the summary call -- for a compaction
    model, a switch's compaction and a local summariser (a local server cuts an oversized prompt
    without a word); (None, estimate) otherwise."""
    from halo_harness.agent.model_window import kind_of, window_of
    ref = getattr(session, "model_ref", None)
    est = estimate(system_text, messages, tools) + SUMMARY_REPLY  # the summary's own room
    if not always and kind_of(ref) == "cloud":
        return None, est
    try:
        w = window_of(ref, state_dir=getattr(session, "state_dir", None))
    except Exception:
        w = {"tokens": None}
    session._switch_fitted_for = getattr(ref, "model", None)
    return w.get("tokens"), est
