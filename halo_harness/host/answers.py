"""halo_harness.host.answers -- the fit simulation and the routing answer (Halo 3.3.7.0 R1; host/http.py routes them).

    simulate(view, body) -> {host, model, fits, says, need_bytes, budget, window, kv, row_source, installed, max_window}
        body {model | size_gb, window, kv?, host?}: would it fit here (pulled or not)? `fit.plan` over the
        installed row, else a synthetic one: the library snapshot's size and the published shape when the model is
        known there, else `size_gb` with a typical shape for its size (an estimate, said so)
    route(view, body) -> {host, fits, now, warm, evicts, load_s, verdict, need_bytes, budget, free_now, capable}
        body {need: {size_gb | model, window, tools?, vision?}}: can it run here, and right now? `now` is the free
        VRAM now (or the model is loaded at that window: `warm`); `evicts` the loaded models that would have to go;
        `load_s` the speed card's cold load (or the measured one)

Arithmetic only, from this host's own card: no model is called, no model is loaded, nothing on the server changes.
The library snapshot is the packaged one (no request leaves the LAN).
"""

from __future__ import annotations

from typing import Optional

GIB = 2 ** 30
DEFAULT_WINDOW = 32768
GB_PER_B = 0.6  # a Q4 model weighs about 0.6 GB per billion parameters (a typical shape for a size-only ask)


def _gib(n) -> str:
    return f"{(n or 0) / GIB:.1f} GB"


def _window(raw) -> int:
    try:
        w = int(raw or DEFAULT_WINDOW)
    except (TypeError, ValueError):
        return DEFAULT_WINDOW
    return max(512, min(w, 1 << 20))


def library_row(model: str) -> "tuple[Optional[dict], str]":
    """A not-pulled model's row from the packaged library snapshot: its weights and the published shape."""
    from halo_harness.models_library import shapes, snapshot
    name, _, tag = str(model or "").partition(":")
    tag = tag or "latest"
    man = snapshot.manifest_of(name, tag) or {}
    t = next((x for x in snapshot.tags_of(name) if x.get("tag") == tag), None) or {}
    weights = man.get("weights") or t.get("size_bytes")
    if not isinstance(weights, int) or weights <= 0:
        return None, ""
    info, src = shapes.shape_for(name, tag, man.get("params"))
    return {"model": model, "size": weights, "model_info": info or {}}, f"the library snapshot ({src})"


def row_for(view, h, body: dict) -> "tuple[Optional[dict], str, bool]":
    """(row, where it came from, installed here)."""
    from halo_harness.providers.ollama import ollama_names_match
    model = str(body.get("model") or "").strip()
    if model:
        hit = next((r for r in view.host_catalog(h) if ollama_names_match(r.get("model") or r.get("name"), model)), None)
        if hit is not None:
            return {**hit, "model": model}, "installed here (/api/show)", True
        row, src = library_row(model)
        if row is not None:
            return row, src, False
    try:
        gb = float(body.get("size_gb"))
    except (TypeError, ValueError):
        gb = 0.0
    if gb <= 0:
        return None, "neither installed here, in the library snapshot, nor given a size_gb", False
    from halo_harness.models_library import shapes
    params = gb / GB_PER_B
    return ({"model": model or f"a {gb:g} GB model", "size": int(gb * GIB), "model_info": shapes.generic(params) or {}},
            f"the size given ({gb:g} GB; a typical shape for about {params:.0f}B: an estimate)", False)


def _host(view, body: dict):
    hs = view._pick(str(body.get("host") or ""))
    return hs[0] if hs else None


def _card(view, h, kv: str) -> dict:
    card = view.host_card(h)
    if kv:
        card = {**card, "server": {**(card.get("server") or {}), "kv_cache_type": kv}}
    return card


def _plan(card: dict, row: dict, window: int, name: str) -> dict:
    from halo_harness.ollama_steward.fit import plan
    p = plan(card, [{"model": row["model"], "window": window, "max_prompt": 0, "calls": 1}], {row["model"]: row},
             host_name=name)
    need = (p.get("models") or [{}])[0].get("need") if p.get("models") else None
    return {"fits": p.get("fits_now"), "says": p.get("says"), "need_bytes": int(need) if need else None,
            "budget": int((p.get("budget") or {}).get("budget") or 0)}


def simulate(view, body: dict) -> "tuple[int, dict]":
    from halo_harness.ollama_steward.fit import model_window_on_card
    h = _host(view, body)
    if h is None:
        return 404, {"error": "this machine serves no Ollama host" + (f" named {body.get('host')!r}" if body.get("host") else "")}
    window, kv = _window(body.get("window")), str(body.get("kv") or "").strip().lower()
    row, src, installed = row_for(view, h, body)
    if row is None:
        return 422, {"error": f"simulate takes {{model | size_gb, window, kv?}}: {src}"}
    card = _card(view, h, kv)
    out = _plan(card, row, window, h.name)
    return 200, {"host": h.name, "model": row["model"], **out, "window": window,
                 "kv": kv or (card.get("server") or {}).get("kv_cache_type") or "f16", "row_source": src,
                 "installed": installed, "max_window": model_window_on_card(card, row, forced=False, step=4096)}


def _free_now(card: dict, budget: int) -> int:
    gpus = [g for g in card.get("gpus") or [] if isinstance(g, dict)]
    live = [g.get("available_bytes") for g in gpus if isinstance(g.get("available_bytes"), int)]
    if gpus and len(live) == len(gpus):
        return int(sum(live))
    held = sum(int(m.get("size_vram") or 0) for m in card.get("loaded") or [] if isinstance(m, dict))
    return max(0, budget - held)


def _capable(view, h, model: str, need: dict) -> Optional[bool]:
    if not model or not (need.get("tools") or need.get("vision")):
        return None
    from halo_harness.providers.ollama_capability import profile_for
    p = profile_for(view.home, model, h.name)
    if not p:
        return None
    ok = True
    if need.get("tools"):
        ok = ok and p.get("tools") == "yes"
    if need.get("vision"):
        ok = ok and p.get("vision") in ("yes", True)
    return ok


def _load_s(view, h, model: str) -> Optional[float]:
    if not model:
        return None
    facts = view.model_facts(h, model)
    sp = facts.get("speed") or {}
    v = sp.get("cold_load_s") if isinstance(sp, dict) else None
    return v if isinstance(v, (int, float)) else facts["measured"].get("load_s")


def route(view, body: dict) -> "tuple[int, dict]":
    from halo_harness.providers.ollama import ollama_names_match
    need = body.get("need") if isinstance(body.get("need"), dict) else {}
    h = _host(view, {**need, "host": body.get("host")})
    if h is None:
        return 404, {"error": "this machine serves no Ollama host"}
    window = _window(need.get("window"))
    row, src, installed = row_for(view, h, need)
    if row is None:
        return 422, {"error": f"route takes {{need: {{size_gb | model, window, tools?, vision?}}}}: {src}"}
    card = view.host_card(h)
    p = _plan(card, row, window, h.name)
    model = str(need.get("model") or "")
    loaded = [m for m in card.get("loaded") or [] if isinstance(m, dict)]
    warm = bool(model) and any(ollama_names_match(m.get("model"), model) and int(m.get("context_length") or 0) >= window
                               for m in loaded)
    free = _free_now(card, p["budget"])
    want = p["need_bytes"] or 0
    now = bool(p["fits"]) and (warm or (bool(want) and want <= free))
    evicts: list = []
    if p["fits"] and not now:
        room = free
        for m in sorted((m for m in loaded if not (model and ollama_names_match(m.get("model"), model))),
                        key=lambda m: -int(m.get("size_vram") or 0)):
            if room >= want:
                break
            evicts.append(m.get("model"))
            room += int(m.get("size_vram") or 0)
    capable = _capable(view, h, model, need)
    load_s = None if warm else _load_s(view, h, model)
    fits = bool(p["fits"]) and capable is not False
    what = model or row["model"]
    if capable is False:
        verdict = f"{what} is here but its profile says it cannot do what was asked (tools/vision)"
    elif not p["fits"]:
        verdict = f"{what} does not fit {h.name} at {window:,}: {p['says']}"
    elif warm:
        verdict = f"{what} is loaded on {h.name} at {window:,} or more: it runs now"
    elif now:
        verdict = (f"{what} fits {h.name} at {window:,} now ({_gib(want)} of {_gib(free)} free)"
                   + (f"; about {load_s:.0f} s to load" if load_s else ""))
    else:
        verdict = (f"{what} fits {h.name} at {window:,} once {', '.join(evicts) or 'the card frees'} unload"
                   + ("s" if len(evicts) == 1 else "") + (f"; about {load_s:.0f} s to load" if load_s else ""))
    if not installed:
        verdict += f" (not pulled here: {src})"
    from halo_harness.host.invariants import footprint  # 3.3.7.0 R2: the helper's footprint, said
    fp = footprint(view, h, rows=loaded)
    return 200, {"host": h.name, "model": what, "usable_gb": fp["usable_gb"], "footprint": fp["line"],
                 "usable_with_helper_gb": fp["usable_with_helper_gb"], "fits": fits, "now": now and capable is not False, "warm": warm,
                 "evicts": evicts, "load_s": load_s, "verdict": verdict, "need_bytes": p["need_bytes"],
                 "budget": p["budget"], "free_now": free, "capable": capable, "window": window, "installed": installed}
