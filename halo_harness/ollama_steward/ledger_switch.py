"""halo_harness.ollama_steward.ledger_switch -- Halo 3.3.5.0 R0: the two
ledger fields a model switch adds to a call's line (`ledger_call.py` writes
the line): `switched_from` and `fitted`. `agent/model_switch.finish` and the
compaction's window check (`model_switch.summary_window`) leave
`_switch_fitted_for` on the session; the first call of that model consumes it.
"""

from __future__ import annotations


def switch_fields(session, model, kind: str) -> dict:
    """3.3.5.0 R0: `switched_from` (the previous turn or compaction call's model in this session, or
    the model a switch step moved from) and `fitted` (a switch step ran before this call)."""
    if session is None or kind not in ("turn", "compaction"):
        return {}
    from halo_harness.ollama_steward.profiles import short_model
    prev = getattr(session, "_ledger_prev_model", None)
    fitted_for = getattr(session, "_switch_fitted_for", None)
    fitted = bool(fitted_for) and short_model(fitted_for) == short_model(model)
    switched = prev if prev and short_model(prev) != short_model(model) else None
    if fitted and not switched:
        frm = getattr(session, "_ledger_switched_from", None)
        switched = frm if frm and frm != getattr(getattr(session, "model_ref", None), "raw", None) else None
    session._ledger_prev_model = model
    if fitted:
        session._switch_fitted_for = None
        session._ledger_switched_from = None
    return {"switched_from": switched, "fitted": fitted}
