"""halo_harness.ollama_steward.rules_ft -- the steward watches a FreeToken server (Halo 3.3.9.1; docs/MODELS-steward-
servers.md "FreeToken"; knowledge/local-servers.md "## FreeToken"). The events are FreeToken's own log lines
(server_log_ft.py, from the source, unverified against a live run); one finding per rule and group, keyed
`<server>|<model>`, each with `server`, `runtime` (freetoken) and a stated fix line -- never applied by itself.

    ft-expert-thrash  the newest decode steps' expert cache hits under THRASH_HIT (median of the `--moe-collect-stats`
                      lines): the misses stream over the host link, so the link is the limit -- a smaller model, a
                      bigger cache share (`ft ctl cache --moe N`, live), or NVLink-class hardware
    ft-pinned-cap     under WSL the expert banks did not all pin: FreeToken locked layers for CPU decode (slower), or
                      the load stopped -- run it on Linux, or a smaller checkpoint
    ft-kernel-jit     the first request after an install compiled FreeToken's CUDA kernels (a startup warmup over
                      server_log_ft.JIT_S, or the first call after a load over JIT_S): said, nothing to change, the
                      session's wait allows it; an error when the toolchain cannot compile them (nvcc against CUDA 13)

    ft_rules(ctx) -> [finding]
"""

from __future__ import annotations

from statistics import median

from halo_harness.ollama_steward.rules import finding, hint

THRASH_HIT = 0.5
RECENT = 8
JIT_S = 60.0


def _tag(f: dict, g: dict) -> dict:
    from halo_harness.ollama_steward.server_rules_hf import not_asked
    f.update(server=g.get("server") or g["host"], runtime="freetoken", not_asked=not_asked("freetoken"), applied=False)
    return f


def _of(g: dict, kind: str) -> list:
    return [e for e in g["events"] if e.get("kind") == kind]


def _last_load(g: dict) -> dict:
    rows = _of(g, "load-result")
    return dict(rows[-1].get("data") or {}) if rows else {}


def thrash(g: dict, ctx: dict) -> list:
    stats = [e.get("data") or {} for e in _of(g, "expert-cache")][-RECENT:]
    hits = [float(d["hit"]) for d in stats if isinstance(d.get("hit"), (int, float))]
    if len(hits) < 2 or median(hits) >= THRASH_HIT:
        return []
    from halo_harness.freetoken.link import link_words
    gbs, link = link_words(ctx.get("state_dir"))
    decode = [float((e.get("data") or {}).get("tok_s")) for e in _of(g, "timing")
              if (e.get("data") or {}).get("phase") == "decode" and isinstance((e.get("data") or {}).get("tok_s"), (int, float))]
    slots = _last_load(g).get("cache_slots")
    who = g.get("server") or g["host"]
    text = (f"{g['model']} on {who}: the expert cache hits {median(hits):.0%} of the experts a step asks (the newest "
            f"{len(hits)} decode stats); the misses stream over the host link ({link}), so the link is the limit"
            + (f" (decoding at {median(decode[-RECENT:]):g} tok/s)" if decode else "")
            + " -- a smaller model, a bigger cache share, or NVLink-class hardware")
    line = (f"ft ctl cache --moe {int(slots) * 2} on {who}" if slots else
            f"ft serve ... --moe-cache-rate 0.5 on {who} (a restart of the FreeToken server)")
    nums = {"hit": round(median(hits), 3), "stats": len(hits), "cache_slots": slots, "link_gbs": gbs,
            "decode_tok_s": round(median(decode[-RECENT:]), 1) if decode else None}
    return [_tag(finding("ft-expert-thrash", g, "warn", text, numbers=nums, server_hint=hint(
        None, line, "VRAM from the KV cache (a shorter window holds), or a smaller model's quality")), g)]


def pinned(g: dict, ctx: dict) -> list:
    caps = _of(g, "pin-cap") + [e for e in _of(g, "load-failed") if (e.get("data") or {}).get("pinned")]
    if not caps:
        return []
    d = caps[-1].get("data") or {}
    stopped = caps[-1].get("kind") == "load-failed"
    who = g.get("server") or g["host"]
    text = (f"{g['model']} on {who}: under WSL the pinned bank did not fit ({d.get('banks_gib'):g} GiB of expert banks"
            + (f" over a {d['budget_gib']:g} GiB pin budget" if d.get("budget_gib") else "") + "): "
            + ("the load stopped" if stopped else f"{d.get('locked') or 'some'} layers decode on the CPU, slower")
            + " -- run it on Linux, or a smaller checkpoint")
    return [_tag(finding("ft-pinned-cap", g, "error" if stopped else "warn", text, events=caps,
                         numbers={"banks_gib": d.get("banks_gib"), "budget_gib": d.get("budget_gib"),
                                  "locked": d.get("locked"), "stopped": stopped},
                         server_hint=hint(None, "serve it from native Linux (WSL caps CUDA pinning near half of RAM), "
                                          "or a smaller checkpoint (an NVFP4 one, or fewer experts)",
                                          "a reboot into Linux, or a smaller model's quality")), g)]


def _first_call_s(g: dict) -> "tuple[float, str] | None":
    from halo_harness.ollama_steward.ledger import parse_at
    loads = [e for e in _of(g, "load-result")]
    since = parse_at(loads[-1].get("at")) if loads else None
    calls = [x for x in g.get("lines") or [] if isinstance(x.get("total_ms"), (int, float))
             and (since is None or (parse_at(x.get("at")) or 0) >= since)]
    if calls and calls[0]["total_ms"] >= JIT_S * 1000:
        return calls[0]["total_ms"] / 1000.0, "the first call after the load"
    return None


def jit(g: dict, ctx: dict) -> list:
    who = g.get("server") or g["host"]
    broke = [e for e in _of(g, "load-failed") if (e.get("data") or {}).get("toolchain")]
    if broke:
        from halo_harness.freetoken import CUDA_LINE
        text = f"{g['model']} on {who}: FreeToken cannot compile its CUDA kernels -- {broke[-1].get('say', '')[:160]}"
        return [_tag(finding("ft-kernel-jit", g, "error", text, events=broke, numbers={"toolchain": True},
                             server_hint=hint(None, f"install {CUDA_LINE}", "the toolkit's download (a few GB), once")), g)]
    warm = _of(g, "kernel-jit")
    seen = (float((warm[-1].get("data") or {}).get("seconds") or 0), "the startup warmup") if warm else _first_call_s(g)
    if not seen:
        return []
    secs, where = seen
    text = (f"{g['model']} on {who}: {where} took {secs:.0f} s -- FreeToken compiled its CUDA kernels on first use; "
            "later requests do not pay it, nothing to change (the session's wait allows it)")
    return [_tag(finding("ft-kernel-jit", g, "info", text, events=warm, numbers={"seconds": round(secs), "where": where}), g)]


def ft_rules(ctx: dict) -> list:
    out: list = []
    for g in ctx.get("groups") or []:
        if g.get("runtime") == "freetoken":
            out += thrash(g, ctx) + pinned(g, ctx) + jit(g, ctx)
    return out
