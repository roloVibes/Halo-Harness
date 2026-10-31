"""halo_harness.local_sched.facts -- what the scheduler reads about one Ollama host (Halo 3.3.7.0 R3).

    host_named(name) -> OllamaHost | None          an `ollama.hosts` entry (None: the default one)
    split_ref("ol:qwen3:30b@pc") -> ("qwen3:30b", "pc" | None)
    card(host) -> the hardware card ({} when none was read)
    row(host, model) -> (catalog row | None, where it came from)   installed (/api/show), else the library snapshot
    loaded(host) -> [{model, size, size_vram, context_length}]      /api/ps now, else the card's `loaded`
    helper(host, rows) -> {model, bytes} | None    the duty steward's model while it is resident
    window(host, model, role=None, row=None, card=None) -> (window, where it came from)
    budget(card, host_name) -> fit.card_budget's answer
    together(b, items) -> bytes                    weights + KV at each item's window + the per-card reserve
    usable(b, helper) -> bytes                     the budget minus the helper's footprint (host/invariants' rule)

Reads only. The card is studio/ollama_hosts_view's (cached 60 s); under the test flag
(BRIDGE_TEST_NO_BACKGROUND_NET) a card is read only through that module's READERS and a catalog only from a
loopback fake (providers/ollama_guard), never this machine's own GPU, server log or Ollama.
"""

from __future__ import annotations

from typing import Optional

GIB = 2 ** 30
DEFAULT_WINDOW = 32768
SEAMS: dict = {}  # tests: "loaded": fn(host) -> rows


def gb(n) -> str:
    return f"{(n or 0) / GIB:.1f}"


def host_named(name: Optional[str]):
    try:
        from halo_harness.providers.ollama import resolve_ollama_host
        return resolve_ollama_host(name or None)
    except Exception:
        return None


def split_ref(raw: str) -> "tuple[str, Optional[str]]":
    s = str(raw or "").strip()
    if s.startswith("ol:"):
        s = s[3:]
    model, _, host = s.partition("@")
    return model, (host or None)


def _guarded(kind: str, host) -> bool:
    """True when the test flag keeps this read away (no fixture reader, or not a loopback fake)."""
    from halo_harness.providers.ollama_guard import control_blocked, flag_on
    from halo_harness.studio import ollama_hosts_view as V
    if not flag_on() or kind in V.READERS:
        return False
    return kind == "card" or control_blocked(host) is not None


def card(host) -> dict:
    if host is None or _guarded("card", host):
        return {}
    from halo_harness.studio import ollama_hosts_view as V
    got = V.card_of(host)
    return got if isinstance(got, dict) else {}


def row(host, model: str) -> "tuple[Optional[dict], str]":
    from halo_harness.providers.ollama_hw import catalog_row
    if host is not None and not _guarded("catalog", host):
        from halo_harness.studio import ollama_hosts_view as V
        cat = V.catalog_of(host)
        hit = catalog_row(cat, model)
        if hit is not None and isinstance(hit.get("size"), int):
            return {**hit, "model": model}, "installed (/api/show)"
        if hit is None and (cat or {}).get("models"):  # 3.3.7.0 R4: a tag Halo knew there and that is gone
            from halo_harness.ollama_steward.dead_tag import check
            dead = check(f"ol:{model}@{host.name}", catalog=cat)
            if dead["dead"] and dead["known"]:
                return None, dead["line"]
    try:
        from halo_harness.host.answers import library_row
        got, src = library_row(model)
    except Exception:
        got, src = None, ""
    return (got, src) if got is not None else (None, f"no catalog row for {model}")


def loaded(host) -> list:
    if host is None:
        return []
    if "loaded" in SEAMS:
        return list(SEAMS["loaded"](host) or [])
    try:
        from halo_harness.providers.ollama_control import loaded as ps
        got = ps(host)
    except Exception:
        got = {"ok": False}
    if got.get("ok"):
        return [r for r in got.get("models") or [] if isinstance(r, dict)]
    return [m for m in card(host).get("loaded") or [] if isinstance(m, dict)]


def is_loaded(rows: list, model: str, window: Optional[int] = None) -> bool:
    from halo_harness.providers.ollama import ollama_names_match
    return any(ollama_names_match(r.get("model") or r.get("name"), model)
               and (not window or not r.get("context_length") or int(r["context_length"]) >= int(window)) for r in rows)


def helper(host, rows: list) -> Optional[dict]:
    try:
        from halo_harness.config.paths import bridge_home
        from halo_harness.host.invariants import helper_row
        h = helper_row(bridge_home(), rows)
    except Exception:
        h = None
    if not h:
        return None
    return {"model": h.get("model"), "bytes": int(h.get("size_vram") or h.get("size") or 0)}


def window(host, model: str, role: Optional[str] = None, row_: Optional[dict] = None,
           card_: Optional[dict] = None) -> "tuple[int, str]":
    from halo_harness.ollama_steward.profiles import all_profiles, key_for, lookup
    name = getattr(host, "name", host)
    prof = lookup(name, model, role=role or "") or {}
    if isinstance(prof.get("num_ctx"), int) and prof["num_ctx"] > 0:
        own = role and key_for(name, model, role) in all_profiles()
        w, src = prof["num_ctx"], f"the {role} lane's profile" if own else "the profile"
    elif isinstance(getattr(host, "max_ctx", None), int) and host.max_ctx > 0:
        w, src = host.max_ctx, "the host's max_ctx"
    else:
        w, src = DEFAULT_WINDOW, f"the default {DEFAULT_WINDOW:,}"
    if card_ and row_:
        from halo_harness.ollama_steward.fit import model_window_on_card
        cap = model_window_on_card(card_, row_, forced=False, step=4096)
        if isinstance(cap, int) and 0 < cap < w:
            w, src = cap, f"{src}, held to {cap:,} (the most it fits alone)"
    return int(w), src


def budget(card_: dict, host_name: str = "") -> dict:
    from halo_harness.ollama_steward.fit import card_budget
    return card_budget(card_ or {}, host_name)


def need(b: dict, row_: Optional[dict], window_: int) -> Optional[float]:
    if not row_ or not isinstance(row_.get("size"), int) or not b.get("budget"):
        return None
    from halo_harness.ollama_steward.fit import _need
    return _need(b, row_, int(window_))


def together(b: dict, items: list) -> float:
    """`items`: [{row, window}]: their bytes on one card with its reserve (fit._together)."""
    from halo_harness.ollama_steward.fit import _together
    return _together(b, [{"row": it["row"], "window": it["window"]} for it in items]) if items else 0.0


def usable(b: dict, helper_: Optional[dict]) -> int:
    return max(0, int(b.get("budget") or 0) - int((helper_ or {}).get("bytes") or 0))
