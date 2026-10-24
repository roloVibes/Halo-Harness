"""halo_harness.outcomes.routing -- `models.preference: measured` (Halo 3.1.8.0
R3, docs/OUTCOMES.md "Route by it"; docs/ROLES.md).

A bio whose preference is `measured` is picked at spawn like an `auto` one
(models_auto_spawn.resolver), with one rule first: among the candidates that
carry the task's needs (the same candidates `models_auto.pick` weighs), the
ones measured for the bio's kind here from `MIN_N` (3) checked tasks are
ranked by their rate (outcomes/measured.py, first-time success); a tie goes
by the auto pick's own rules for the band (models_auto._choose). With nothing
measured for that kind yet, the pick is the `auto` pick, its reason starting
"nothing measured for <kind> yet". The reason ends with the numbers it used,
"(measured 4/5 code)", which Studio shows on the card's pill and in the Live
tab line.
"""

from __future__ import annotations

from typing import Optional

from halo_harness.models_auto import DEFAULT_BAND, MEASURED, Pick, _candidates, _choose, load_rows, pick, price_words
from halo_harness.outcomes.measured import MIN_N, success_by_model_kind, words


def pick_measured(state_dir, *, kind: str, needs=(), task_text: str = "", attachments=(), band: str = DEFAULT_BAND,
                  main_ref: str = "", role: str = "", rows: Optional[dict] = None,
                  stats: Optional[dict] = None) -> Pick:
    """The model a `measured` agent runs on, and why. `stats`: success_by_model_kind's answer (default: read
    from `state_dir`); `rows`: the best-at index's rows (default: read from `state_dir`)."""
    entries = load_rows(state_dir) if rows is None else rows
    auto = pick(state_dir, needs=needs, task_text=task_text, attachments=attachments, band=band, main_ref=main_ref,
                role=role, rows=entries, kind=kind)
    auto.how = MEASURED  # 3.1.9.0 R3: the outcome row's `picked`
    try:
        stats = success_by_model_kind(state_dir) if stats is None else stats
    except Exception:
        stats = {}
    cands = _candidates(entries, auto.kinds, main_ref) if entries else []
    measured = [c for c in cands if int((stats.get((c.ref, kind)) or {}).get("n") or 0) >= MIN_N]
    if not measured:
        auto.reason = f"nothing measured for {kind} yet, so the auto pick: {auto.reason}"
        return auto
    best = max(stats[(c.ref, kind)]["rate"] for c in measured)
    top = [c for c in measured if stats[(c.ref, kind)]["rate"] == best]
    chosen, _ordered, _rule, tie = _choose(top, auto.kinds, band, main_ref)
    if len(top) > 1 and not tie:
        tie = "; a tie on the rate, so by the band's rule"
    s = stats[(chosen.ref, kind)]
    what = ("+".join(auto.kinds) + " ") if auto.kinds else ""
    reason = (f"the best measured {kind} rate here among the {what}models ({price_words(chosen.facts)}){tie} "
              f"(measured {words(kind, s)})")
    rest = sorted((c for c in measured if c.ref != chosen.ref), key=lambda c: (-stats[(c.ref, kind)]["rate"], c.ref))
    return Pick(chosen.ref, reason, auto.kinds, [c.ref for c in rest[:3]], how=MEASURED)
