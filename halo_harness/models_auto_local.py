"""halo_harness.models_auto_local -- Auto's pick weighs fit and warm state (Halo 3.3.7.0 R3; plans/local-model-fit-
brief.md D1 7), so Auto cannot pick a model that thrashes main's card.

    state_for(cands, main_ref, state_dir) -> {ref: {fits, warm, swap_s, swap_from}}   the local candidates only
        fits: True / False beside main on its card (roles_fit.verdict: the warm-set arithmetic), None when main is
        not on that card or the card was not read; warm: loaded now (/api/ps); swap_s: its load time when not warm
    weigh(cands, local_state) -> (cands, skipped [line])
        a local model that does not fit beside main is left out while another candidate remains; one that needs a
        load keeps SWAP_WEIGHT(swap_s) of its score (25 s -> 0.875, 50 s or more -> 0.75); warm ones keep it whole
    note_for(ref, local_state) -> "already warm" | "fits beside main" | "needs a swap, 25 s" | ... | ""

`models_auto.pick` reads it before the band's rule; the Pick's `local_note` says which it was and the pick line
carries it ("auto: ol:qwen3-coder:30b@pc -- ...; already warm"). Nothing is loaded.
"""

from __future__ import annotations

from typing import Optional

SWAP_FLOOR = 0.75
SWAP_PER_S = 0.005


def swap_weight(swap_s) -> float:
    if not isinstance(swap_s, (int, float)) or swap_s <= 0:
        return 1.0
    return round(max(SWAP_FLOOR, 1.0 - float(swap_s) * SWAP_PER_S), 3)


def _one(ref: str, main_ref: str, state_dir) -> Optional[dict]:
    from halo_harness.roles_fit import verdict
    v = verdict("auto", ref, main_ref, state_dir=state_dir) if str(main_ref or "").startswith("ol:") else None
    if v is not None:
        return {"fits": v["fits_beside_main"], "warm": v["warm_now"], "swap_s": v["swap_s"], "swap_from": v["swap_from"]}
    from halo_harness.local_sched import facts as F
    from halo_harness.local_sched.swap_cost import load_s_for
    model, hname = F.split_ref(ref)
    host = F.host_named(hname)
    if host is None:
        return None
    warm = F.is_loaded(F.loaded(host), model)
    cost = {"s": None, "source": None} if warm else load_s_for(host, model, state_dir=state_dir, fetch=False)
    return {"fits": None, "warm": warm, "swap_s": cost["s"], "swap_from": cost["source"]}


def state_for(cands: list, main_ref: str, state_dir) -> dict:
    if state_dir is None:
        return {}
    out: dict = {}
    for c in cands:
        ref = str(getattr(c, "ref", c) or "")
        if not ref.startswith("ol:") or ref == main_ref:
            continue
        try:
            got = _one(ref, main_ref, state_dir)
        except Exception:
            got = None
        if got is not None:
            out[ref] = got
    return out


def note_for(ref: str, local_state: Optional[dict]) -> str:
    from halo_harness.local_sched.swap_cost import secs
    s = (local_state or {}).get(ref)
    if not s:
        return ""
    if s.get("warm"):
        return "already warm"
    load = f", {secs(s['swap_s'])}" if isinstance(s.get("swap_s"), (int, float)) else ""
    if s.get("fits") is True:
        return "fits beside main" + (f", ~{secs(s['swap_s'])} to load" if load else "")
    if s.get("fits") is False:
        return f"does not fit beside main: needs a swap{load}"
    return f"needs a load{load}" if load else ""


def weigh(cands: list, local_state: Optional[dict]) -> "tuple[list, list]":
    if not local_state:
        return cands, []
    keep, skipped = [], []
    for c in cands:
        s = local_state.get(c.ref) or {}
        if s.get("fits") is False and not s.get("warm"):
            skipped.append(c)
            continue
        keep.append(c if s.get("warm") else c._replace(score=round(c.score * swap_weight(s.get("swap_s")), 4)))
    if not keep:  # nothing else: the swap is the price, weighed
        keep = [c._replace(score=round(c.score * swap_weight((local_state.get(c.ref) or {}).get("swap_s")), 4))
                for c in skipped]
        return keep, []
    return keep, [f"skipped {c.ref}: it does not fit beside main, so every hand-off would swap" for c in skipped]
