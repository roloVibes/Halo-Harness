"""halo_harness.host.invariants -- the host's deterministic invariants (Halo 3.3.7.0 R2; plans/local-model-fit-brief.md
H10.6). Mechanics with no model and no judgement in them:

- never load what does not fit: `warm` / `pin` / `pivot` run `fit.plan` for the model at the asked window on the
  host's card first and are refused with the plan's verdict line when it does not fit;
- one resident per card: a load beside another loaded model is refused unless the request sends `beside: true` and
  the plan says both fit (the duty steward's helper model does not count: it is evicted when the card is needed);
- `keep_alive`: the asked one goes on the load and comes back in the answer;
- the helper's footprint: when the duty steward's model is resident (`/api/ps`), the card and `route` answers carry
  `usable_gb` and `usable_with_helper_gb` and the line "20.6 GB usable; 18.6 GB with the helper";
- a request whose dry run says the card would be breached is refused in the same words the preview shows.

    loaded(view, host) -> [{model, size, size_vram, context_length}]   /api/ps, else the card's `loaded`
    helper(home) -> the duty steward's model name (when it is on) | None
    footprint(view, host, rows=None) -> {usable_bytes, usable_gb, helper, usable_with_helper_gb, line}
    check_load(view, host, model, window, *, beside=False) -> {ok, verdict, need_bytes, others, evict_helper, window}
"""

from __future__ import annotations

from typing import Optional

GIB = 2 ** 30


def _gb(n) -> str:
    return f"{(n or 0) / GIB:.1f} GB"


def loaded(view, host) -> list:
    from halo_harness.providers.ollama_control import loaded as ps
    if "loaded" in view.readers:
        return list(view.readers["loaded"](host) or [])
    try:
        got = ps(host)
    except Exception:
        got = {"ok": False}
    if got.get("ok"):
        return [r for r in got.get("models") or [] if isinstance(r, dict)]
    return [m for m in (view.host_card(host).get("loaded") or []) if isinstance(m, dict)]


def _bare(ref: str) -> str:
    m = str(ref or "").strip()
    if m.startswith("ol:"):
        m = m[3:]
    return m.split("@", 1)[0]


def helper(home) -> Optional[str]:
    """The duty steward's model (host.steward.model) while host.steward.enabled is true."""
    from halo_harness.host.state import _cfg
    if _cfg("host.steward.enabled", False, home) is not True:
        return None
    m = _bare(_cfg("host.steward.model", "", home) or "")
    return m or None


def helper_row(home, rows: list) -> Optional[dict]:
    from halo_harness.providers.ollama import ollama_names_match
    m = helper(home)
    return next((r for r in rows if m and ollama_names_match(r.get("model"), m)), None) if m else None


def _budget(view, host) -> int:
    from halo_harness.ollama_steward.fit import card_budget
    card = view.host_card(host)
    return int(card_budget(card, host.name)["budget"]) if card.get("gpus") else 0


def footprint(view, host, rows: Optional[list] = None) -> dict:
    usable = _budget(view, host)
    rows = loaded(view, host) if rows is None else rows
    h = helper_row(view.home, rows)
    held = int((h or {}).get("size_vram") or (h or {}).get("size") or 0)
    out = {"usable_bytes": usable, "usable_gb": round(usable / GIB, 1),
           "helper": {"model": h.get("model"), "gb": round(held / GIB, 1)} if h else None,
           "usable_with_helper_gb": round(max(0, usable - held) / GIB, 1)}
    if not usable:
        out["line"] = "usable memory not read yet"
    elif h:
        out["line"] = f"{_gb(usable)} usable; {_gb(usable - held)} with the helper ({h.get('model')}, {_gb(held)})"
    else:
        out["line"] = f"{_gb(usable)} usable"
    return out


def _row(view, host, model: str) -> Optional[dict]:
    from halo_harness.providers.ollama import ollama_names_match
    return next((r for r in view.host_catalog(host) if ollama_names_match(r.get("model") or r.get("name"), model)), None)


def _plan_many(card: dict, items: list, host_name: str) -> dict:
    from halo_harness.ollama_steward.fit import plan
    asked = [{"model": r["model"], "window": w, "max_prompt": 0, "calls": len(items) - i} for i, (r, w) in enumerate(items)]
    return plan(card, asked, {r["model"]: r for r, _w in items}, host_name=host_name)


def check_load(view, host, model: str, window: Optional[int], *, beside: bool = False,
               rows: Optional[list] = None) -> dict:
    """Would loading `model` at `window` here keep the invariants? The verdict line either way."""
    from halo_harness.host.answers import _plan
    from halo_harness.providers.ollama import ollama_names_match
    from halo_harness.providers.ollama_load import window_for
    out = {"ok": False, "verdict": "", "need_bytes": None, "others": [], "evict_helper": None, "window": window}
    row = _row(view, host, model)
    if row is None:
        out["verdict"] = f"{model} is not on {host.name} (manage/pull brings it)"
        return out
    if not window:
        window = window_for(host, model)[0] or 32768
    out["window"] = int(window)
    row = {**row, "model": model}
    card = view.host_card(host)
    p = _plan(card, row, int(window), host.name)
    out["need_bytes"] = p["need_bytes"]
    if not p["fits"]:
        out["verdict"] = f"{model} does not fit {host.name} at {int(window):,}: {p['says']}"
        return out
    rows = loaded(view, host) if rows is None else rows
    hrow = helper_row(view.home, rows)
    others = [r for r in rows if not ollama_names_match(r.get("model"), model) and r is not hrow]
    out["others"] = [r.get("model") for r in others]
    if others and not beside:
        names = ", ".join(str(r.get("model")) for r in others)
        out["verdict"] = (f"one resident per card: {names} {'is' if len(others) == 1 else 'are'} loaded on {host.name}; "
                          f"pivot to {model} (it unloads first), or send beside: true when both fit")
        return out
    held = sum(int(r.get("size_vram") or 0) for r in others)
    if others:
        items = [(row, int(window))] + [((_row(view, host, str(r.get("model"))) or {}), int(r.get("context_length")
                                         or 4096)) for r in others]
        if any(not it[0].get("size") for it in items):
            out["verdict"] = f"beside: the fit of {', '.join(out['others'])} is not known here (no catalog row)"
            return out
        both = _plan_many(card, [(dict(r, model=str(r.get("model") or "")), w) for r, w in items], host.name)
        if not both.get("fits_now"):
            out["verdict"] = f"{model} beside {', '.join(out['others'])} on {host.name}: {both.get('says')}"
            return out
    free = max(0, p["budget"] - held)
    if hrow is not None and (p["need_bytes"] or 0) > free - int(hrow.get("size_vram") or 0):
        out["evict_helper"] = hrow.get("model")
    out.update(ok=True, verdict=(f"{model} fits {host.name} at {int(window):,} ({_gb(p['need_bytes'])} of "
                                 f"{_gb(p['budget'])})" + (f"; the helper {hrow.get('model')} unloads first"
                                                            if out["evict_helper"] else "")))
    return out
