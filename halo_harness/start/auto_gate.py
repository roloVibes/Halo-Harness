"""halo_harness.start.auto_gate -- the guided first run belongs to custom lineups (Halo 3.3.15.0 R5).

On the Auto lineup (`team` unset with roles on, or `auto` named) every part of the guided first run is one model
picked per task, so the run would rehearse one model five times and say little. With no lineup at all (roles off:
one model for everything) it is the same. So, while the active lineup is Auto or none:

    halo start                    prints AUTO_LINE and GYM_LINE and exits 0 without running (`--lineup <name>` runs)
    halo init / the wizard        the Summary's checks and the console offer leave the guided first run out and print
                                  AUTO_LINE in its place
    halo check                    `--all` and `--explain` leave it out; `--start` prints AUTO_LINE
    Setup -> Check (Studio)       no guided-first-run row; AUTO_LINE in its place (setup_check_state `start_auto`)
    Start here (Studio)           no Run button; AUTO_LINE in its place; POST start answers 422 `auto_lineup`

A custom lineup (any other `team`) keeps all of these as before. The test of a lineup or a workflow moves to Agents ->
Runs in 3.3.16.0, on top of the same engine (halo_harness/start/engine.py). 3.3.15.0 R7: the guided first run
rehearses that lineup (start/lineup.py `pick`), so AUTO_LINE says the real condition: pick or build one first.
"""

from __future__ import annotations

from typing import Optional

AUTO_LINE = "Your lineup is Auto: pick or build a lineup in Roles first, then `halo start` rehearses it."  # 3.3.15.0 R7
GYM_LINE = "To measure your models instead: halo gym --quick (tool calls, edits, recall and instructions, scored)."
REASON = "auto_lineup"


def lineup_now() -> "tuple[Optional[str], str]":
    """`(name, source)` of the lineup sessions run now (lineup_default.lineup_in_use); `(None, "none")` on an error."""
    try:
        from halo_harness.lineup_default import lineup_in_use
        return lineup_in_use()
    except Exception:
        return None, "none"


def on_auto() -> bool:
    """True when the active lineup is Auto (`auto`, named or the default) or there is none (roles off)."""
    from halo_harness.lineup_default import DEFAULT_LINEUP
    name, _source = lineup_now()
    return not name or name == DEFAULT_LINEUP


def offers_start(explicit_lineup: Optional[str] = None) -> bool:
    """Whether the guided first run is offered: a lineup named for this run, or an active custom lineup."""
    return bool(explicit_lineup and explicit_lineup.strip()) or not on_auto()


def lines() -> "list[str]":
    """What a surface prints in the guided first run's place."""
    return [AUTO_LINE, GYM_LINE]
