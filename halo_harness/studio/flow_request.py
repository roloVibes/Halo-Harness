"""halo_harness.studio.flow_request -- the body parsing of Studio's Flow
routes (Halo 3.0.4.0 round R5; 3.1.0.0 R2 renamed it from flow_api_io.py
and moved the assets upload to flow_assets_api.py): the 422 answer, a run's
intake (`budget_usd` as a number) and its per-step overrides. Used by
flow_api.py.
"""

from __future__ import annotations


def bad(lines, status: int = 422):
    lines = [lines] if isinstance(lines, str) else list(lines)
    return status, {"error": lines[0] if lines else "invalid", "problems": lines}


def intake_of(body):
    """(intake, None) or (None, error): the intake mapping, `budget_usd` as a number."""
    intake = body.get("intake") if isinstance(body.get("intake"), dict) else {}
    intake = {str(k): v for k, v in intake.items() if v is not None}
    budget = intake.get("budget_usd")
    if isinstance(budget, str) and budget.strip():
        try:
            intake["budget_usd"] = float(budget)
        except ValueError:
            return None, bad(f"intake.budget_usd is a number, got {budget!r}")
    elif budget in ("", None):
        intake.pop("budget_usd", None)
    return intake, None


def overrides_of(raw):
    """`{step: {key: value}}` or `{"step.key": value}` -> ({step: {key: value}}, None) or (None, error)."""
    if raw in (None, ""):
        return {}, None
    if not isinstance(raw, dict):
        return None, bad("set is {\"<step>.<key>\": value} or {\"<step>\": {\"<key>\": value}}")
    out: dict = {}
    for key, val in raw.items():
        if isinstance(val, dict):
            out.setdefault(str(key), {}).update(val)
            continue
        step, dot, field = str(key).partition(".")
        if not dot or not step or not field:
            return None, bad(f"set takes <step>.<key>, got {key!r}")
        out.setdefault(step, {})[field] = val
    return out, None
