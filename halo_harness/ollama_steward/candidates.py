"""halo_harness.ollama_steward.candidates -- the models that could run the steward here (Halo 3.3.7.0 R5; ROADMAP
"during init, or whenever, halo should find good model candidates to control the local models").

    candidates(state_dir=None, host=None, *, local=None, cached=False) -> [Candidate]   best first (cached: no request)
    Candidate = {model (ref: ol:<model>@<host>), ref (as the local view names it), host, installed, gb, fits_beside_main (True | False | None), tool_calls (yes | no |
                 not probed), tok_s, download_gb, minutes, why}
    line(cands) -> "candidates to run the steward on this machine: qwen3.5:9b (fits beside the coder, 6.1 GB, tool
                   calls verified), ..."
    best(cands) -> the first installed candidate that can call tools (or is not probed yet) and does not crowd main out

From what Halo already holds -- the roster (`roster()`: each configured host's catalog, the cached view; else
agent.local_models), the battery profiles (tools, the
measured tok/s), the card and the main model's need (local_sched/facts: weights + KV at the steward's window, the
reservations counted) -- ranked: tool calls verified first, then fits beside the main model, then measured speed, then
the smaller. With nothing installed that fits, the known-good small models of the library snapshot that would (each
with its download size and minutes): a row to download, never a download. Arithmetic only: no request, no model.
"""

from __future__ import annotations

from typing import Optional

WINDOW = 8192
KNOWN_GOOD = ("qwen3.5:9b", "qwen3:8b", "qwen3.5:4b", "llama3.2:3b")
GIB = 2 ** 30


def _main(host_name: str):
    from halo_harness.local_sched.facts import split_ref
    from halo_harness.start.provider import default_model
    ref = default_model()
    if not ref.startswith("ol:"):
        return None
    model, h = split_ref(ref)
    from halo_harness.local_sched.facts import host_named
    default = getattr(host_named(None), "name", None)
    return model if str(h or default or "").lower() == str(host_name).lower() else None


def _peek(kind: str, host):
    """cached=True's read: a fixture reader, else what the views (or the catalog cache) already hold; never a request."""
    from halo_harness.studio import ollama_hosts_view as V
    if kind in V.READERS:
        return V._cached(kind, host)
    with V._LOCK:
        hit = V._CACHE.get((kind, str(getattr(host, "url", ""))))
    if hit is not None:
        return hit[1]
    if kind == "catalog":
        from halo_harness.providers.local_models_cached import cached_catalog
        return cached_catalog(host)
    return None


def _row_of(host, model: str, cached: bool) -> Optional[dict]:
    from halo_harness.local_sched import facts as F
    if not cached:
        return F.row(host, model)[0]
    from halo_harness.providers.ollama_hw import catalog_row
    hit = catalog_row(_peek("catalog", host) or {}, model)
    if hit is not None and isinstance(hit.get("size"), int):
        return {**hit, "model": model}
    from halo_harness.host.answers import library_row
    return library_row(model)[0]


def _fit(host, model: str, row: Optional[dict], main: Optional[str], state_dir,
         cached: bool = False) -> "tuple[Optional[float], Optional[bool], str]":
    from halo_harness.local_sched import facts as F
    from halo_harness.local_sched.reserve import claimed_bytes
    card = (_peek("card", host) or {}) if cached else F.card(host)
    b = F.budget(card, host.name)
    need = F.need(b, row, WINDOW) if row else None
    gb = round(need / GIB, 1) if need else (round(row["size"] / GIB, 1) if row and isinstance(row.get("size"), int) else None)
    if not need or not b.get("budget"):
        return gb, None, "the card not read"
    rows = (card.get("loaded") or []) if cached else F.loaded(host)
    room = F.usable(b, F.helper(host, rows)) - (0 if cached else claimed_bytes(host, state_dir=state_dir))
    if not main:
        ok = F.together(b, [{"row": row, "window": WINDOW}]) <= room
        return gb, ok, "fits the card" if ok else "does not fit the card"
    from halo_harness.providers.ollama import ollama_names_match
    if ollama_names_match(model, main):
        return gb, True, "is the main model (it shares main's weights: no more memory)"
    mrow = _row_of(host, main, cached)
    if not mrow:
        return gb, None, f"the main model {main} not read"
    mw = F.window(host, main, row_=mrow, card_=card)[0]
    both = F.together(b, [{"row": row, "window": WINDOW}, {"row": mrow, "window": mw}])
    ok = both <= room
    return gb, ok, (f"fits beside {main}" if ok else f"does not fit beside {main} ({both / GIB:.1f} of {room / GIB:.1f} GB)")


def _profile(state_dir, model: str, host_name: str) -> dict:
    from halo_harness.providers.placement import profile_for_ref
    return profile_for_ref(f"ol:{model}@{host_name}", state_dir) or {}


def _row(host, model: str, state_dir, installed: bool, size: Optional[int] = None, cached: bool = False) -> dict:
    row = _row_of(host, model, cached)
    gb, fits, fit_words = _fit(host, model, row, _main(host.name), state_dir, cached)
    if gb is None and isinstance(size, int) and size > 0:
        gb = round(size / GIB, 1)  # the size on disk the local view lists
    p = _profile(state_dir, model, host.name)
    tools = {"yes": "yes", "no": "no"}.get(str(p.get("tools") or ""), "not probed")
    tok_s = (p.get("speed") or {}).get("tok_s")
    bits = [fit_words, f"{gb:g} GB" if gb else "size not read",
            {"yes": "tool calls verified", "no": "its battery says it cannot call tools"}.get(tools, "tool calls not probed")]
    if isinstance(tok_s, (int, float)):
        from halo_harness.providers.local_bench_link import tail  # 3.3.8.1: "(over the LAN from mac)"
        bits.append(f"{tok_s:g} tok/s" + (f" ({tail(p.get('speed'))})" if tail(p.get("speed")) else ""))
    out = {"model": f"ol:{model}@{host.name}", "host": host.name, "installed": installed, "gb": gb, "fits_beside_main": fits,
           "tool_calls": tools, "tok_s": tok_s, "download_gb": None, "minutes": 0}
    if not installed:
        from halo_harness.models_library.advise_lines import cost
        dl = round(row["size"] / 1e9, 1) if row and isinstance(row.get("size"), int) else None
        out.update(download_gb=dl, minutes=cost(dl or 0, None, None, None)["minutes"])
        bits.append(f"a {dl:g} GB download, ~{out['minutes']} min" if dl else "a download")
    out["why"] = ", ".join(bits)
    return out


def _rank(c: dict) -> tuple:
    known = next((i for i, m in enumerate(KNOWN_GOOD) if c["model"].startswith(f"ol:{m}@")), len(KNOWN_GOOD))
    return (not c["installed"], c["tool_calls"] == "no", c["fits_beside_main"] is False, c["tool_calls"] != "yes",
            -(c["tok_s"] or 0), 0 if c["installed"] else known, c["gb"] or 99, c["model"])


def roster(cached: bool = False) -> list:
    """[(ref, size)] of the chat models each configured Ollama host lists (the cached catalog view, 60 s; cached=True:
    only what is held already -- Setup's state read opens no connection)."""
    from halo_harness.models_library.advise_lines import purpose
    from halo_harness.providers.ollama import resolve_ollama_hosts
    from halo_harness.studio import ollama_hosts_view as V
    out = []
    for h in resolve_ollama_hosts():
        for r in ((_peek("catalog", h) if cached else V.catalog_of(h)) or {}).get("models") or []:
            name = str((r or {}).get("model") or (r or {}).get("name") or "")
            if name and purpose(name, r.get("capabilities")) != "embed":
                out.append((f"ol:{name}@{h.name}", r.get("size")))
    return out


def candidates(state_dir=None, host=None, *, local=None, cached: bool = False) -> list:
    from halo_harness.local_sched.facts import host_named, split_ref
    from halo_harness.ollama_steward.agent import local_models
    rows = (roster(cached) or local_models(state_dir)) if local is None else list(local)
    out, seen = [], set()
    for ref, size in rows:
        if not str(ref).startswith("ol:"):
            continue
        model, hname = split_ref(ref)
        h = host_named(hname)
        if h is None or (host and h.name.lower() != str(host).lower()):
            continue
        seen.add((h.name, model))
        out.append({**_row(h, model, state_dir, True, size, cached), "ref": ref})
    if not any(c["fits_beside_main"] is not False and c["tool_calls"] != "no" for c in out):
        h = host_named(host)
        for model in KNOWN_GOOD if h is not None else ():
            if (h.name, model) not in seen:
                c = _row(h, model, state_dir, False, cached=cached)
                if c["fits_beside_main"] is not False:
                    out.append({**c, "ref": c["model"]})
    return sorted(out, key=_rank)


def best(cands: list) -> Optional[dict]:
    return next((c for c in cands if c["installed"] and c["tool_calls"] != "no" and c["fits_beside_main"] is not False),
                None)


def line(cands: list) -> str:
    if not cands:
        return "candidates to run the steward on this machine: none (no local model is installed or known to fit)"
    return "candidates to run the steward on this machine: " + ", ".join(
        f"{c['model'].split(':', 1)[1].rsplit('@', 1)[0]} ({c['why']})" for c in cands[:4])
