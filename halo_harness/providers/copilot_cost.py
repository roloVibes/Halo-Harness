"""halo_harness.providers.copilot_cost -- Copilot in the cost meter (Halo 3.3.17.0 R2).

A `cp:work` turn and a `copilot_ask` call add no dollars: Copilot is billed by the tenant (Copilot Credits on the
Work IQ door, the user's licence on the Graph door), never per token here. Both mark the session's cost incomplete
the 3.3.3.1 way (`CostMeter.has_cost_data = False`, `cp:work` in `cost_unknown`), so the TUI status bar shows the
priced part with its `+` (or the token counts when nothing else is priced) and never `$0.00`; `/cost`, `/status` and
Studio's Cost panel say the reason line below instead of "reports no price".
"""

from __future__ import annotations

from halo_harness.providers.copilot_config import REF

REASON = "Copilot: billed by your tenant (credits or licence)"


def is_copilot(model) -> bool:
    m = str(model or "")
    return m == REF or m.startswith("cp:")


def mark_unpriced(meter) -> None:
    """One Copilot call on `meter`: incomplete, `cp:work` named once; no-op without a meter."""
    if meter is None:
        return
    try:
        meter._note_unknown([REF], 1)
    except Exception:
        pass


def split_unknown(unknown) -> "tuple[list, str]":
    """(the unknown refs that are not Copilot, the Copilot reason or '')."""
    refs = [str(m) for m in unknown or [] if m]
    rest = [m for m in refs if not is_copilot(m)]
    return rest, (REASON if len(rest) != len(refs) else "")
