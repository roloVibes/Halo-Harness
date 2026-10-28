"""halo_harness.ollama_steward.fit -- Halo 3.3.4.0 R3: the fit planner.

Given a host's hardware card (its GPUs, what else holds memory:
`other_users`), the catalog rows of the models the halos ask for on it (the
models with calls in the ledger's window, every member's lines included)
and the windows they ask with, `plan()` finds a set that fits, in this
order, each option saying what you lose:

    windows      a window per model so they fit together (never under a
                 model's largest prompt plus its reply)
    one-at-a-time  `keep_alive` 0 on the less-called model, the busier one first
    other-host   the less-called model asked on another host configured here
                 that serves it (`host_for`)
    twin         a tuned twin (every layer on the GPU) where `--fit` spills
    smaller-quant  a smaller quantization (the pull line)
    kv-q8_0      `OLLAMA_KV_CACHE_TYPE=q8_0` on the server (the env line)

The first three are profile changes (ollama_steward/profiles.py); the last
three are recommendations only. The arithmetic is
providers/ollama_fit_parts.py's (knowledge/memory.md).
"""

from __future__ import annotations

from typing import Callable, Optional

from halo_harness.providers.ollama_fit import kv_bytes_per_elem_for
from halo_harness.providers.ollama_fit_parts import fit_window, need_bytes, projector_for

STEP = 4096
FLOOR = 8192
REPLY = 4096
GIB = 2 ** 30


def card_budget(card: dict, host_name: str = "") -> dict:
    """What models may hold on the card: the cards' total (on unified memory
    the GPU's share, `available_bytes`), minus what other programs hold --
    3.3.5.0 R1: the Local tab's newest sample of the host when it is newer
    than the card (resources_share.others_for: a ComfyUI that just started)."""
    gpus = [g for g in (card or {}).get("gpus") or [] if isinstance(g, dict)]
    unified = bool((card or {}).get("unified"))
    key = "available_bytes" if unified else "total_bytes"
    total = sum(int(g.get(key) or g.get("total_bytes") or 0) for g in gpus)
    others = sum(int(u.get("bytes") or 0) for u in (card or {}).get("other_users") or [] if isinstance(u, dict))
    from halo_harness.ollama_steward.resources_share import others_for
    live = others_for(host_name, card) if host_name else None
    others, others_from = (live, "sample") if live is not None else (others, "card")
    server = (card or {}).get("server") or {}
    return {"total": total, "others": others, "budget": max(0, total - others), "unified": unified,
            "metal": unified or any((g.get("library") or "") == "Metal" for g in gpus), "cards": max(1, len(gpus)),
            "bpe": kv_bytes_per_elem_for(server.get("kv_cache_type")), "kv": server.get("kv_cache_type") or "f16",
            "parallel": server.get("parallel") or 1, "others_from": others_from}


def _kw(b: dict, row: dict) -> dict:
    return {"bytes_per_elem": b["bpe"], "parallel": b["parallel"], "projector_bytes": projector_for(row)}


def model_window_on_card(card: dict, row: dict, *, alone: bool = True, forced: bool = True,
                         step: Optional[int] = None) -> Optional[int]:
    """The largest window `row`'s model fits on the card by itself."""
    b = card_budget(card)
    if not b["budget"] or not isinstance((row or {}).get("size"), int):
        return None
    got = fit_window(row.get("model_info") or {}, weight_bytes=row["size"], free_bytes=b["budget"], forced=forced,
                     metal=b["metal"], cards=b["cards"], step=step, **_kw(b, row))
    return got if isinstance(got, int) else None


def _need(b: dict, row: dict, window: int) -> Optional[float]:
    """One model's bytes at `window`, its share of the reserve not included."""
    full = need_bytes(row.get("model_info") or {}, weight_bytes=row["size"], window=window, metal=b["metal"],
                      **_kw(b, row))
    if full is None:
        return None
    return full - (512 if b["metal"] else 457) * 2 ** 20


def _together(b: dict, items: list) -> float:
    reserve = (512 if b["metal"] else 457) * 2 ** 20 * b["cards"]
    return sum(_need(b, it["row"], it["window"]) or 0 for it in items) + reserve


def _gib(n) -> str:
    return f"{n / GIB:.1f} GiB"


def plan(card: dict, asked: list, catalog: dict, *, host_name: str, other_hosts: Optional[Callable] = None) -> dict:
    """`asked`: [{model, window, max_prompt, calls, load_ms}] for one host."""
    b = card_budget(card, host_name)
    items, missing = [], []
    for a in sorted(asked, key=lambda a: -(a.get("calls") or 0)):
        row = (catalog or {}).get(a["model"])
        if not row or not isinstance(row.get("size"), int) or not a.get("window"):
            missing.append(a["model"])
            continue
        items.append({**a, "row": row})
    out = {"host": host_name, "budget": b, "models": [], "fits_now": None, "options": [], "chosen": None,
           "missing": missing}
    if not items or not b["budget"]:
        out["says"] = "nothing to plan: " + ("no card read" if not b["budget"] else "no model with calls and a catalog row")
        return out
    for it in items:
        out["models"].append({"model": it["model"], "window": it["window"], "need": _need(b, it["row"], it["window"])})
    used = _together(b, items)
    out["fits_now"] = used <= b["budget"]
    if out["fits_now"]:
        out["says"] = f"they fit together: {_gib(used)} of {_gib(b['budget'])}"
        return out
    out["says"] = (f"{len(items)} model{'s' if len(items) > 1 else ''} at their windows need {_gib(used)}; the card has "
                   f"{_gib(b['budget'])}" + (f" ({_gib(b['others'])} held by other programs)" if b["others"] else ""))
    key = lambda m: f"{host_name}|{m}"  # noqa: E731
    if len(items) > 1:
        trial = [dict(it) for it in items]
        floors = {it["model"]: max(FLOOR, -(-int((it.get("max_prompt") or 0) * 1.25 + REPLY) // STEP) * STEP)
                  for it in trial}
        while _together(b, trial) > b["budget"]:
            room = [t for t in trial if t["window"] - STEP >= floors[t["model"]]]
            if not room:
                break
            t = max(room, key=lambda t: t["window"] - floors[t["model"]])
            t["window"] -= STEP
        if _together(b, trial) <= b["budget"]:
            lose = "; ".join(f"{t['model']} {o['window']} -> {t['window']}" for t, o in zip(trial, items)
                             if t["window"] != o["window"])
            out["options"].append({"kind": "windows", "says": "a window per model so they fit together",
                                   "changes": [{"key": key(t["model"]), "field": "num_ctx", "to": t["window"]}
                                               for t, o in zip(trial, items) if t["window"] != o["window"]],
                                   "server_hint": None, "lose": f"smaller windows ({lose}); the largest prompts "
                                   "seen still fit", "fits": True})
        second = items[-1]
        alone = [it for it in items if (_need(b, it["row"], it["window"]) or 0) + 457 * 2 ** 20 <= b["budget"]]
        if len(alone) == len(items):
            secs = (second.get("load_ms") or 0) / 1000.0
            out["options"].append({"kind": "one-at-a-time", "says": f"one model at a time: {items[0]['model']} first, "
                                   f"{second['model']} unloaded after each call",
                                   "changes": [{"key": key(second["model"]), "field": "keep_alive", "to": "0"}],
                                   "server_hint": None, "fits": True,
                                   "lose": "every switch reloads a model" + (f" (about {secs:.0f} s)" if secs else "")})
        elsewhere = other_hosts(second["model"]) if other_hosts else []
        if elsewhere:
            rest = _together(b, items[:-1]) <= b["budget"]
            out["options"].append({"kind": "other-host", "says": f"{second['model']} asked on {elsewhere[0]}",
                                   "changes": [{"key": key(second["model"]), "field": "host_for", "to": elsewhere[0]}],
                                   "server_hint": None, "fits": rest,
                                   "lose": f"its calls go over the network to {elsewhere[0]}"
                                   + ("" if rest else f"; {items[0]['model']} still needs a smaller window")})
    first = items[0]
    if _together(b, [first]) > b["budget"]:
        w = (first["window"] // STEP) * STEP
        floor = max(FLOOR, -(-int((first.get("max_prompt") or 0) * 1.25 + REPLY) // STEP) * STEP)
        while w - STEP >= floor and _together(b, [{**first, "window": w}]) > b["budget"]:
            w -= STEP
        ok = _together(b, [{**first, "window": w}]) <= b["budget"]
        out["options"].append({"kind": "window-alone", "says": f"{first['model']} alone at {w}" if ok else
                               f"{first['model']} does not fit beside what else holds the card even at {w}",
                               "changes": [{"key": key(first["model"]), "field": "num_ctx", "to": w}] if ok else [],
                               "server_hint": None, "fits": ok,
                               "lose": f"its window {first['window']} -> {w}" if ok else "nothing Halo-side helps"})
    for it in items:
        forced = model_window_on_card(card, it["row"], forced=True, step=STEP) or 0
        default = model_window_on_card(card, it["row"], forced=False, step=STEP) or 0
        if default < it["window"] <= forced:
            out["options"].append({"kind": "twin", "says": f"a tuned twin of {it['model']} (every layer on the GPU)",
                                   "changes": [], "fits": True, "lose": "one fixed window; a second model name",
                                   "server_hint": {"env": None, "line": f"halo ollama tune {it['model']} --host {host_name}",
                                                   "cost": "no disk; a fixed window per twin"}})
    big = items[0]
    quant = str(((big["row"].get("details") or {}).get("quantization_level")) or "")
    if quant.upper().startswith(("Q4", "Q5", "Q6", "Q8", "F16")):
        saved = int(big["row"]["size"] * 0.2)
        out["options"].append({"kind": "smaller-quant", "says": f"a smaller quantization of {big['model']} (about "
                               f"{_gib(saved)} less)", "changes": [], "fits": used - saved <= b["budget"],
                               "lose": "some quality (3-bit weights)",
                               "server_hint": {"env": None, "line": f"ollama pull {big['model']}-q3_K_M",
                                               "cost": "a download; some quality"}})
    if b["kv"] in ("f16", "bf16", "f32"):
        kv = sum((_need(b, it["row"], it["window"]) or 0) - (_need({**b, "bpe": 1.0625}, it["row"], it["window"]) or 0)
                 for it in items)
        out["options"].append({"kind": "kv-q8_0", "says": f"the server's KV cache at q8_0 (about {_gib(kv)} less)",
                               "changes": [], "fits": used - kv <= b["budget"], "lose": "a very small precision loss",
                               "server_hint": {"env": "OLLAMA_KV_CACHE_TYPE", "line": "OLLAMA_KV_CACHE_TYPE=q8_0",
                                               "cost": "a very small precision loss; every model's cache halves"}})
    for i, o in enumerate(out["options"]):
        if o["changes"] and o["fits"]:
            out["chosen"] = i
            break
    return out


def format_plan(p: dict) -> "list[str]":
    out = [f"'{p['host']}': {p.get('says', '')}"]
    for m in p["models"]:
        need = f"{_gib(m['need'])}" if m.get("need") else "?"
        out.append(f"  {m['model']} at {m['window']}: {need}")
    for i, o in enumerate(p["options"]):
        mark = "*" if i == p.get("chosen") else "-"
        hint = f"; on the server: {o['server_hint']['line']}" if o.get("server_hint") else ""
        out.append(f"  {mark} {o['kind']}: {o['says']} (you lose: {o['lose']}){hint}")
    if p.get("missing"):
        out.append(f"  not planned (no catalog row or window): {', '.join(p['missing'])}")
    return out
