"""halo_harness.agent.degrade_crash -- the degradation ladder's step on a crash fingerprint (Halo 3.3.7.0 R4; the
3.3.6.0 R4 leftover: "the ladder's rung on a crash fingerprint").

    crash_match(session, now=None) -> fingerprint | None   the model in use crashed on its host at this window in the
        last CRASH_S (ollama_steward/fingerprints.py: this machine's rows; each one is stepped on once)
    crash_turn(session, turn_no) -> a generator; True when a rung was taken: agent/degrade.step with trigger `crash`
        and the fingerprint (past the smaller ask; the line names it). agent/loop.py `_maybe_escalate` runs it first,
        before low_confidence's judge is asked anything.
"""

from __future__ import annotations

from typing import Optional

from halo_harness.agent.degrade import rungs, step

CRASH_S = 600.0


def crash_match(session, now: Optional[float] = None) -> Optional[dict]:
    """3.3.7.0 R4: the fingerprint of the model in use that just crashed on its host at this window (CRASH_S), once."""
    import time
    from halo_harness.model import is_local_model_ref
    from halo_harness.ollama_steward.fingerprints import _t, line, read
    from halo_harness.providers.ollama import ollama_names_match
    ref, state = getattr(session, "model_ref", None), getattr(session, "state_dir", None)
    if state is None or not is_local_model_ref(ref) or not rungs():
        return None
    last = (getattr(session, "_ollama_window_state", None) or {}).get("last") or {}
    host = last.get("host_name") or getattr(ref, "host", None)
    window = getattr(last.get("choice"), "num_ctx", None)
    now = time.time() if now is None else now
    seen = getattr(session, "_ladder_crash_seen", None) or set()
    for fp in read(state, host=host) if host else []:
        key = (fp.get("host"), fp.get("model"), fp.get("signature"), fp.get("at"))
        if fp.get("from") or key in seen or now - _t(fp.get("at")) > CRASH_S or not ollama_names_match(fp.get("model"), ref.model):
            continue
        if window and isinstance(fp.get("window_used"), int) and fp["window_used"] != window:
            continue
        session._ladder_crash_seen = seen | {key}
        return {**fp, "line": line(fp)}
    return None


def crash_turn(session, turn_no: int):
    """A generator: the ladder's step on a crash fingerprint match, before low_confidence's judge (agent/loop.py
    `_maybe_escalate`); returns True when a rung was taken."""
    fp = crash_match(session)
    if fp is None:
        return False
    act = yield from step(session, turn_no, "crash", None, fingerprint=fp)
    return act is not None
