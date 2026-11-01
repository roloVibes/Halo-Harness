"""halo_harness.local_pool.speed -- the pool's speed: measured (its own bench card) or extrapolated, and the penalty
against the single node that could hold the model (Halo 3.3.8.0 R4; docs/POOL.md "Measured or extrapolated").

    card_for(model, state_dir=None) -> the pool's speed card of this catalog model | None   (providers/
        local_bench_runs' store, host `pool`, cache key `pool|<model>`; local_pool/bench.py writes it)
    single_for(model, state_dir=None) -> {tok_s, host, model, at, on_gpu} | None   the fastest single-node bench card
        of the same model (the catalog's `match` words against the card's model name), never the pool's own
    stale(card, run) -> "" | "measured with pc, me; the pool runs pc, me, worker2 now"   the members or the split
        changed since the bench
    floor(card) -> the slowest measured reply rate on the card (the auto-revert's baseline: changes_pool.judge)
    figures(model, state_dir=None, run=None) -> {measured, tok_s, ttft_ms, cold_load_s, at, stale, penalty_pct,
        penalty_from, vs, word, extrapolated}
        a pool card: its reply rate at its largest window; with a single node's card the penalty measured against it
        ("11.2 tok/s measured, -38 % vs pc alone"; a node that spills the model to its CPU can be the slower one:
        "+120 % vs pc alone (it spills to the CPU there)"); without one the research's penalty, said. No pool card:
        the catalog's speed, "extrapolated" (or "measured elsewhere") said, and the research's penalty.
Reads only.
"""

from __future__ import annotations

from typing import Optional


def _store(state_dir=None):
    from halo_harness.local_pool.claims import _state
    return _state(state_dir)


def _name(model) -> str:
    return str(model.get("name") if isinstance(model, dict) else model or "")


def card_for(model, state_dir=None) -> Optional[dict]:
    from halo_harness.providers.local_bench_runs import all_cards
    name = _name(model)
    return next((c for c in all_cards(_store(state_dir), "pool") if c.get("model") == name), None)


def floor(card: Optional[dict]) -> Optional[float]:
    rates = [float(r["tok_s"]) for r in (card or {}).get("windows") or []
             if isinstance(r.get("tok_s"), (int, float)) and not r.get("error")]
    return min(rates) if rates else None


def single_for(model: dict, state_dir=None) -> Optional[dict]:
    from halo_harness.providers.local_bench_runs import all_cards, mirror
    words = [w.lower() for w in (model or {}).get("match") or ()]
    best = None
    for c in all_cards(_store(state_dir)):
        if str(c.get("host") or "").lower() == "pool" or c.get("pool"):
            continue
        if not any(w in str(c.get("model") or "").lower() for w in words):
            continue
        m = mirror(c)
        if isinstance(m.get("tok_s"), (int, float)) and (best is None or m["tok_s"] > best["tok_s"]):
            best = {"tok_s": float(m["tok_s"]), "host": c.get("host"), "model": c.get("model"), "at": c.get("at"),
                    "on_gpu": m.get("on_gpu")}
    return best


def _split(v) -> list:
    return [round(float(x), 2) for x in v or [] if isinstance(x, (int, float))]


def stale(card: Optional[dict], run: Optional[dict]) -> str:
    if not card or not run:
        return ""
    a, b = list(card.get("members") or []), list(run.get("members") or [])
    if a != b:
        return f"measured with {', '.join(a) or 'no members'}; the pool runs {', '.join(b) or 'no members'} now"
    if _split(card.get("split")) != _split(run.get("split")):
        word = lambda v: "/".join(f"{x:g}" for x in _split(v))  # noqa: E731
        return f"measured on the split {word(card.get('split'))}; the pool runs {word(run.get('split'))} now"
    return ""


def head_line(card: dict, day: str, stale_word: str = "") -> str:
    """The pool card's first line: "pool speed card (the bench, 2026-11-01, pc + me, split 0.34/0.66, f16 KV, -c
    32,768, llama-server): cold load 33 s"."""
    split = "/".join(f"{x:g}" for x in _split(card.get("split")))
    ctx = card.get("ctx")
    return (f"pool speed card (the bench, {day}, {' + '.join(card.get('members') or []) or 'no members'}"
            + (f", split {split}" if split else "") + f", {card.get('cache') or '?'} KV"
            + (f", -c {int(ctx):,}" if isinstance(ctx, int) else "") + ", llama-server"
            + (f", verified by {card['verified_by']}" if card.get("verified_by") else "")  # the off-hours re-bench
            + (f"; {stale_word}: re-bench" if stale_word else "") + ")"
            + (f": cold load {card['cold_load_s']:g} s" if isinstance(card.get("cold_load_s"), (int, float)) else ""))


def _extrapolated(model: dict) -> str:
    s = model["speed"]
    rng = f"{s['tok_s_low']:g}" if s["tok_s_low"] == s["tok_s_high"] else f"{s['tok_s_low']:g}-{s['tok_s_high']:g}"
    return f"{rng} tok/s " + ("measured elsewhere" if s["measured"] else "extrapolated")


def figures(model: dict, state_dir=None, run: Optional[dict] = None) -> dict:
    from halo_harness.local_pool.route import PENALTY_FROM, PENALTY_PCT
    from halo_harness.providers.local_bench_runs import mirror
    out = {"measured": False, "tok_s": None, "ttft_ms": None, "cold_load_s": None, "at": None, "stale": "",
           "penalty_pct": PENALTY_PCT, "penalty_from": PENALTY_FROM, "vs": None, "extrapolated": _extrapolated(model)}
    c = card_for(model, state_dir)
    m = mirror(c) if c else {}
    if not isinstance(m.get("tok_s"), (int, float)):
        out["word"] = out["extrapolated"] + " (no pool speed card yet: halo local bench --host pool)"
        return out
    tok = float(m["tok_s"])
    out.update(measured=True, tok_s=tok, ttft_ms=m.get("ttft_ms"), cold_load_s=c.get("cold_load_s"), at=c.get("at"),
               stale=stale(c, run))
    one = single_for(model, state_dir)
    if one:
        pct = round((1.0 - tok / one["tok_s"]) * 100)
        rel = f"-{pct} %" if pct >= 0 else f"+{-pct} %"
        out.update(penalty_pct=float(pct), vs=one["host"],
                   penalty_from=f"measured: the pool's bench card against {one['host']}'s ({one['model']}, "
                                f"{one['tok_s']:.1f} tok/s)")
        word = f"{tok:.1f} tok/s measured, {rel} vs {one['host']} alone" + (
            " (it spills to the CPU there)" if one.get("on_gpu") is False else "")
    else:
        out["penalty_from"] = ("the research's 21-55 % midpoint against one node (the pool's own speed is measured; no "
                               "single node here has a bench card of this model to hold it against)")
        word = f"{tok:.1f} tok/s measured (against one node: the research's -{PENALTY_PCT:.0f} %, no node here measured it)"
    out["word"] = word + (f" -- {out['stale']}: re-bench" if out["stale"] else "")
    return out
