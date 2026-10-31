"""halo_harness.ollama_steward.rules_host -- Halo 3.3.4.0 R3: the rules of a
host as a whole (knowledge/symptoms.md `stall`, `slow-load`, `cpu-spill`,
`gpu-memory`; knowledge/scheduler.md, eviction):

(f) slow box: the eval rate's p50 for a model under the threshold for its
    size (`ollama.steward.slow_tok_s` overrides it for every size) -> the
    host is marked slow in the finding (`slow: true`, read by R4's note and
    R5's panel) and, while its calls reload the model, a longer keep_alive.
(g) thrash: two or more models on one host that do not fit together and
    load in turns (`loaded` / `reloaded` events alternating, or most calls
    of several models paying a load) -> the fit plan (fit.py); its first
    Halo-side option becomes the proposal.
"""

from __future__ import annotations

import re
from typing import Optional

from halo_harness.ollama_steward.rules import finding, proposal

SWITCHES = 3
SLOW_BY_SIZE = ((8, 15.0), (16, 10.0), (40, 6.0), (10 ** 6, 3.0))  # (up to N billion parameters, tok/s)


def _billions(model: str, row: Optional[dict]) -> Optional[float]:
    size = str(((row or {}).get("details") or {}).get("parameter_size") or "")
    m = re.search(r"(\d+(?:\.\d+)?)\s*[bB]", size) or re.search(r"[:\-](\d+(?:\.\d+)?)b\b", str(model).lower())
    return float(m.group(1)) if m else None


def slow_threshold(model: str, row: Optional[dict]) -> float:
    try:
        from halo_harness.theme import get_config_value
        fixed = get_config_value("ollama.steward.slow_tok_s", default=None)
    except Exception:
        fixed = None
    if isinstance(fixed, (int, float)) and not isinstance(fixed, bool) and fixed > 0:
        return float(fixed)
    b = _billions(model, row) or 8.0
    return next(t for up_to, t in SLOW_BY_SIZE if b <= up_to)


def slow_box(g: dict, ctx: dict) -> list:
    s = g["stats"]
    rate = s["eval_p50"]
    rated = [x for x in g["lines"] if isinstance(x.get("eval_tok_s"), (int, float)) and not x.get("warming")]  # R4
    if rate is None or len(rated) < 3:
        return []
    row = (ctx["catalogs"].get(g["host"]) or {}).get(g["model"])
    limit = slow_threshold(g["model"], row)
    if rate >= limit:
        return []
    prop = None
    if len(s["reloads"]) * 3 >= len(rated) and not g["profile"].get("keep_alive"):
        prop = proposal("keep_alive", None, "30m", "the model is loaded again for most calls on a slow box")
    return [finding("slow-box", g, "warn", f"{g['host']} is a slow box for {g['model']}: {rate:.1f} tok/s (p50), "
                    f"under {limit:g}", calls=rated[:5], numbers={"eval_tok_s_p50": round(rate, 1),
                                                                  "threshold": limit, "reloads": len(s["reloads"])},
                    proposal=prop, slow=True)]


def _switches(events: list) -> int:
    seq = [e.get("model") for e in sorted(events, key=lambda e: str(e.get("at")))
           if e.get("kind") in ("loaded", "reloaded")]
    return sum(1 for a, b in zip(seq, seq[1:]) if a != b)


def thrash(ctx: dict) -> list:
    from halo_harness.ollama_steward.fit import plan
    out = []
    by_host: dict = {}
    for g in ctx["groups"]:
        by_host.setdefault(g["host"], []).append(g)
    for host, groups in by_host.items():
        asked = [g for g in groups if g["lines"] or g["events"]]
        if len(asked) < 2:
            continue
        events = [e for g in groups for e in g["events"]]
        switches = _switches(events)
        paying = [g for g in asked if g["lines"] and len(g["stats"]["reloads"]) * 2 > len(g["lines"])]
        if switches < SWITCHES and len(paying) < 2:
            continue
        card = ctx["cards"].get(host)
        p = plan(card or {}, [_asked(g) for g in asked], ctx["catalogs"].get(host) or {}, host_name=host,
                 other_hosts=lambda m, host=host: _serving(ctx, m, host))
        if p.get("fits_now"):
            continue
        chosen = p["options"][p["chosen"]] if p.get("chosen") is not None else None
        change = (chosen or {}).get("changes", [None])[0] if chosen else None
        lead = next((g for g in asked if change and g["key"] == change["key"]), asked[0])
        prop = None
        if change:
            prop = proposal(change["field"], (lead["profile"] or {}).get(change["field"]), change["to"],
                            f"{chosen['says']} (you lose: {chosen['lose']})")
        from halo_harness.ollama_steward.failure_lines import swap_line  # 3.3.6.0 R1: the battery's co-reside
        swap = swap_line([g["model"] for g in asked], host, ctx.get("state_dir"))
        out.append(finding("thrash", lead, "error",
                           f"{len(asked)} models on {host} load in turns ({switches} switches, "
                           f"{len(paying)} models paying a load on most calls): {p.get('says', '')}"
                           + (f"; {swap}" if swap else ""),
                           events=events, numbers={"switches": switches, "models": [g["model"] for g in asked]},
                           proposal=prop, plan=p,
                           server_hint=next((o["server_hint"] for o in p["options"] if o.get("server_hint")), None)))
    return out


def _asked(g: dict) -> dict:
    s = g["stats"]
    loads = sorted(x["load_ms"] for x in s["reloads"])
    return {"model": g["model"], "window": g["profile"].get("num_ctx") or s["window"], "max_prompt": s["max_prompt"],
            "calls": len(g["lines"]), "load_ms": loads[len(loads) // 2] if loads else None}


def _serving(ctx: dict, model: str, here: str) -> list:
    out = []
    for h in ctx["hosts"]:
        if h.name == here:
            continue
        rows = ctx["catalogs"].get(h.name)
        if rows and model in rows:
            out.append(h.name)
    return out


def host_rules(ctx: dict) -> list:
    out = []
    for g in ctx["groups"]:
        out.extend(slow_box(g, ctx))
    out.extend(thrash(ctx))
    return out
