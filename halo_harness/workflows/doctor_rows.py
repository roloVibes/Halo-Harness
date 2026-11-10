"""halo_harness.workflows.doctor_rows -- which squares are on for the lineup, and from where (Halo 3.3.16.2):
`halo doctor`'s line under the lineup and the header `halo workflows list` adds.

    squares_line(lineup=None, cwd=None) -> "Squares for lineup mine: media (config workflows.enabled: the
                                            lineup sets no `workflows:`)"
    rows(cwd)                           -> doctor's ("lineup", ...) and ("lineup_squares", ...) entries
"""

from __future__ import annotations

from typing import Optional


def where_words(where: str, lineup: str) -> str:
    from halo_harness.workflows.registry import CONFIG_KEY, uses_config
    if where == "lineup":
        return "the lineup's own `workflows:`"
    if uses_config(lineup):
        return f"config {CONFIG_KEY}"
    return f"config {CONFIG_KEY}: the lineup sets no `workflows:`"


def squares_line(lineup: Optional[str] = None, *, cwd=None) -> str:
    from halo_harness.workflows import registry
    name = lineup if lineup is not None else (registry.active_lineup() or "auto")
    refs, where = registry.enabled_from(name, cwd=cwd)
    on = [w.ref for w in registry.enabled_squares(name, cwd=cwd)]
    src = where_words(where, name)
    if not on:
        missing = f" ({', '.join(refs)} not found)" if refs else ""
        return (f"Squares for lineup {name}: none{missing} ({src}), so the Workflow tool is not offered; "
                f"`halo workflows enable media` turns one on")
    return f"Squares for lineup {name}: {', '.join(on)} ({src})"


def rows(cwd=None) -> list:
    from halo_harness.doctor import OK, _check_lineup
    try:
        line = f"{OK} {squares_line(cwd=cwd)}"
    except Exception as e:
        line = f"{OK} Squares: could not be read ({type(e).__name__})"
    return [("lineup", _check_lineup()), ("lineup_squares", line)]
