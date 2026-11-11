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


def items(rows) -> list:
    """model_rank items for the catalog rows that state the `work-data` strength (and no tool calls)."""
    from halo_harness.capabilities_strengths import blended_price
    return [{"ref": r["ref"], "score": 1.0, "price": blended_price(r), "context": r.get("context_tokens"),
             "provider": r.get("provider") or "", "measured": None, "local": False}
            for r in rows or [] if isinstance(r, dict) and r.get("ref") and NEED in (r.get("strengths") or [])
            and r.get("tools") is not True]


def work_pick(needs, main_ref: str = "", rows: Optional[list] = None) -> Optional[object]:
    """The Pick when `needs` asks for work-data (and not tools) and a catalog row states that strength -- `cp:work`
    once Copilot is signed in (`rows`: the catalog's; default `copilot_rows()`, [] until signed in); else None. The
    rows go through model_rank's one comparator (strongest), as every other pick does."""
    wanted = _needs(needs)
    if NEED not in wanted or "tools" in wanted:
        return None
    from halo_harness.providers.copilot_catalog import copilot_rows
    cands = items(copilot_rows() if rows is None else rows)
    if not cands:
        return None
    from halo_harness import model_rank as R
    from halo_harness.models_auto import Pick
    from halo_harness.providers.copilot_catalog import PRICE_WORDS, STRENGTH_WORDS
    key = R.strongest_key(cands)
    ordered = R.ranked(cands, key)
    tie = R.why(ordered[0], ordered[1] if len(ordered) > 1 else None, key, R.STRONGEST)
    return Pick(ordered[0]["ref"], f"{STRENGTH_WORDS} needs your work's Copilot ({PRICE_WORDS}; a consult role: no "
                f"tools)" + (f"; {tie}" if tie else ""), [NEED], [it["ref"] for it in ordered[1:4]])
