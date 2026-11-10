"""halo_harness.models_auto_work -- Auto and the need `work-data` (Halo 3.3.17.0 R2, docs/PROVIDERS-copilot.md).

`cp:work` (your work's Copilot) carries the strength `work-data` -- "research over your work data" -- and no
`tools`. So:

* a bio or a lineup card that asks for `work-data` (`models.needs: [work-data]`) runs on `cp:work` when Copilot is set
  up and signed in: a consult role, which the agent loop offers no tools;
* a need that also asks for `tools` never gets it (a role that needs tool calls is never handed to Copilot);
* not signed in, the pick goes on as before: no catalog model states `work-data`, so main's model runs it and the
  reason says so;
* no other pick ever lands on it: its catalog row says `tools: False`, which `models_auto._candidates` skips.
"""

from __future__ import annotations

from typing import Optional

NEED = "work-data"


def _needs(needs) -> set:
    return {str(n).strip().lower() for n in needs or () if str(n).strip()}


def work_pick(needs, main_ref: str = "") -> Optional[object]:
    """The Pick for `cp:work` when `needs` asks for work-data (and not tools) and Copilot is signed in; else None."""
    wanted = _needs(needs)
    if NEED not in wanted or "tools" in wanted:
        return None
    from halo_harness.providers.copilot_route import signed_in
    if not signed_in():
        return None
    from halo_harness.models_auto import Pick
    from halo_harness.providers.copilot_catalog import PRICE_WORDS, STRENGTH_WORDS
    from halo_harness.providers.copilot_config import REF
    return Pick(REF, f"{STRENGTH_WORDS} needs your work's Copilot ({PRICE_WORDS}; a consult role: no tools)", [NEED], [])
