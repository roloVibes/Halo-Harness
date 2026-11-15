"""halo_harness.workflows.doctor_rows -- which squares a session enables, and from where (Halo 3.3.16.2; 3.6.0.0 R5d:
config's set only, lineups are gone): `halo doctor`'s line under the map in use.

    squares_line(lineup=None, cwd=None) -> "Squares a session enables: media (config workflows.enabled)"
    rows(cwd)                           -> doctor's ("lineup", ...) (the Map row) and ("lineup_squares", ...) entries
"""

from __future__ import annotations

from typing import Optional


def where_words(where: str = "config", lineup: str = "") -> str:
    from halo_harness.workflows.registry import CONFIG_KEY
    return f"config {CONFIG_KEY}"


def rules_of(lineup: str, cwd=None) -> dict:
    try:
        from halo_harness.workflows.when_store import rules_for
        return rules_for(lineup, cwd=cwd)
    except Exception:
        return {}


def _named(wf, rules: dict) -> str:
    """ "media" for a plain ref; "media (when needs pdf)" / "plan (by name only)" when it carries a when (3.3.16.3)."""
    rule = rules.get(wf.ref)
    if rule is None or rule.plain:
        return wf.ref
    from halo_harness.workflows.when import label
    got = label(rule, wf.contract.covers)
    return f"{wf.ref} ({got if rule.mode in ('off', 'named', 'always') else 'when ' + got})"


def squares_line(lineup: Optional[str] = None, *, cwd=None) -> str:
    from halo_harness.workflows import registry
    name = lineup if lineup is not None else (registry.active_lineup() or "auto")
    refs, where = registry.enabled_from(name, cwd=cwd)
    rules = rules_of(name, cwd)
    on = [_named(w, rules) for w in registry.enabled_squares(name, cwd=cwd)]
    src = where_words(where, name)
    head = "Squares a session enables"  # 3.6.0.0 R5c/R5d: a session reads no lineup, so the set is config's
    if not on:
        missing = f" ({', '.join(refs)} not found)" if refs else ""
        return (f"{head}: none{missing} ({src}), so the Workflow tool is not offered; "
                f"`halo config set workflows.enabled media` turns one on")
    return f"{head}: {', '.join(on)} ({src})"


def rows(cwd=None) -> list:
    from halo_harness.doctor import OK, _check_lineup
    try:
        line = f"{OK} {squares_line(cwd=cwd)}"
    except Exception as e:
        line = f"{OK} Squares: could not be read ({type(e).__name__})"
    return [("lineup", _check_lineup()), ("lineup_squares", line)]
