"""halo_harness.local_pool.preflight -- every check before a pool launches, one function, one answer (Halo 3.3.8.0 R3;
docs/POOL.md "The preflight"; `halo pool preflight <model>`, the Pool page's lines before Warm is enabled).

    preflight(name, *, allow_wifi=None, window=None, state_dir=None, home=None) -> {
        ok, model, display, checks [{check, ok, lines}], lines, blocks, fit, rows, used, excluded, gguf, versions,
        ctx, q8, cache, rpc [{member, addr}], local, split, line}
    the checks, in order (each a row; a block makes ok False and is said with its number):
      fit       local_pool/fit over the members' free VRAM read NOW (each host's card fresh; a resident Ollama model
                counts as room, Warm pivots it out first; a claim never does): pool / one node holds it
                (run it there: pooling is unnecessary) / does not fit (the node and the GB, the matched-memory block)
      link      the adapter type first, the RTT second: a Wi-Fi member is left out unless allowed (pool.allow_wifi,
                `--allow-wifi`, the page's switch), said either way
      rpc       each worker's rpc-server (its host's `GET rpc`, then the port probed): running and answering, or
                not running (Warm starts it through that host); a bare address must already answer
      versions  llama-server --version here against each rpc-server's build (both printed when they differ)
      build     the model's min_build on every node (Qwen3-Next: b7186+)
      gguf      the GGUF in a model folder or the hub cache, else the one Download line (nothing downloads unpressed)
      resident  what is resident and claimed on every member now: what Warm pivots out first
      window    the window asked (default the fit's F16 window; past it Q8_0 KV up to the Q8_0 window; never past it)
Reads only: no process starts, nothing loads, nothing is claimed.
"""

from __future__ import annotations

from typing import Optional


def _wifi(r: dict) -> bool:
    return "Wi-Fi" in str(r.get("link_word") or "") or "Wi-Fi" in str(r.get("rtt_word") or "")


def _allow_wifi(asked: Optional[bool]) -> bool:
    if asked is not None:
        return bool(asked)
    from halo_harness.theme import get_config_value
    return get_config_value("pool.allow_wifi", default=False) is True


def _room(r: dict) -> dict:
    """The fit counts a resident Ollama model as room: Warm pivots it out first (a claim is never room)."""
    if r.get("kind") == "address" or not r.get("resident") or not isinstance(r.get("free_gb"), (int, float)):
        return r
    return {**r, "free_gb": round(float(r["free_gb"]) + float(r.get("resident_gb") or 0), 1)}


def _row(check: str, ok: bool, lines: list) -> dict:
    return {"check": check, "ok": ok, "lines": [x for x in lines if x]}


def _rpc(rows: list, home) -> "tuple[dict, list]":
    from halo_harness.local_pool.hosts import rpc, rpc_addr
    from halo_harness.providers.rpc_probe import probe
    lines, blocks, workers, rpcs = [], [], [], []
    for r in rows:
        m = {"name": r["name"], "host": r["host"], "rpc_port": r["rpc_port"]}
        if r["kind"] == "local":
            lines.append(f"{r['name']}: this machine -- llama-server serves its share on its own GPU (no rpc-server)")
            continue
        addr = rpc_addr(m, home)
        lk = r.get("link") or {}  # 3.3.8.0 R4: the link the OS read wins over the RTT; both kept, the speaker named
        rpcs.append({"member": r["name"], "addr": addr, "kind": r["kind"], "rtt_ms": r.get("rtt_ms"),
                     "link": r.get("link_word") if lk.get("type") not in (None, "unknown") else None})
        st = rpc(m, "status", home=home)
        status = st.get("status") or {}
        up = status.get("running")
        if r["kind"] == "paired" and not up:
            lines.append(f"{r['name']}: rpc-server is not running -- Warm starts it through its halo host (control grant)"
                         if st.get("ok") else st["say"])
            workers.append({"name": r["name"], "version": {}, "running": False})
            continue
        door, _sep, port = addr.rpartition(":")
        got = status.get("probe") or probe(door.strip("[]"), int(port))
        if got.get("rtt_ms") is not None:
            rpcs[-1].update(rtt_ms=got["rtt_ms"], rtt_from="the preflight's probe")
        if not got["alive"]:
            (blocks if r["kind"] == "address" else lines).append(f"{r['name']}: no rpc-server answers on {addr} ({got['line']})")
        else:
            lines.append(f"{r['name']}: rpc-server answers on {addr} in {got['rtt_ms']} ms" if r["kind"] == "address" else
                         f"{r['name']}: {status.get('line')}; the port answers in {got['rtt_ms']} ms")
        workers.append({"name": r["name"], "version": status.get("version") or {}, "running": bool(up or got["alive"])})
    return {"lines": lines, "blocks": blocks, "workers": workers, "rpc": rpcs}, blocks


def _window(v: dict, window: Optional[int]) -> "tuple[int, bool, str]":
    from halo_harness.local_pool.fit import k
    f16, q8 = int(v.get("max_ctx_f16") or 0), int(v.get("max_ctx_q8") or 0)
    if not window or window <= f16:
        w = int(window or f16)
        return w, False, f"-c {w:,} at F16 KV (the fit's F16 window is {k(f16)})"
    if window <= q8:
        return int(window), True, (f"-c {int(window):,} with the KV cache at Q8_0 (past the F16 window {k(f16)}, inside "
                                   f"the Q8_0 window {k(q8)})")
    return 0, False, (f"refused: {int(window):,} is past the pool's Q8_0 window {k(q8)} (the fit: the room left after the "
                      "weights, every node's routing table and buffers) -- a larger promise never reaches a request")


def preflight(name: str, *, allow_wifi: Optional[bool] = None, window: Optional[int] = None, state_dir=None,
              home=None) -> Optional[dict]:
    from halo_harness.local_pool import catalog as C, gguf, versions as V
    from halo_harness.local_pool.budget import budgets
    from halo_harness.local_pool.fit import fit
    model = C.get(name)
    if model is None:
        return None
    rows = budgets(state_dir=state_dir, home=home, fresh=True)
    wifi_ok = _allow_wifi(allow_wifi)
    out_wifi = [r for r in rows if _wifi(r) and not wifi_ok]
    used = [r for r in rows if r not in out_wifi]
    checks, blocks = [], []
    link = [f"{r['name']} is on {r['link_word'] if 'Wi-Fi' in str(r['link_word']) else r['rtt_word']}: left out (a pooled "
            "decode waits one round trip per layer boundary; --allow-wifi or the page's switch keeps it)" for r in out_wifi]
    link += [f"{r['name']} is on {r['link_word'] if 'Wi-Fi' in str(r['link_word']) else r['rtt_word']}: kept, as you "
             "allowed (expect a slower decode)" for r in used if _wifi(r)]
    v = fit(model, [_room(r) for r in used])
    fit_block = [] if v["state"] == "pool" else [v["verdict"] if v["state"] != "single" else
                                                f"{v['verdict']} (halo local serve on {v['node']})"]
    checks.append(_row("fit", not fit_block, v["lines"]))
    checks.append(_row("link", True, link or ["every member is wired (or its link is not known: its RTT is the check)"]))
    counted = [r for r in used if r["name"] in v["members"]]  # the rows as read (claims.place unloads from these)
    rp, rp_block = _rpc(counted, home)
    checks.append(_row("rpc", not rp_block, rp["lines"] + rp["blocks"]))
    ctl = V.controller(state_dir)
    vb, vn = V.compare(ctl, rp["workers"])
    checks.append(_row("versions", not vb, [f"llama-server here: {V.word(ctl)} ({ctl.get('binary')})"] + vb + vn))
    bb, bn = V.min_build(model, ctl, rp["workers"])
    checks.append(_row("build", not bb, bb + bn or [f"{model['display']} names no minimum llama.cpp build"]))
    g = gguf.find(model)
    checks.append(_row("gguf", bool(g["path"]), [g["line"]]))
    res = [f"{r['name']}: " + (", ".join(r["resident"]) + f" resident ({r['resident_gb']:.1f} GB): pivoted out first if "
                               "its share needs the room" if r.get("resident") else "nothing resident")
           + (f"; {r['claims_gb']:.1f} GB claimed" if r.get("claims_gb") else "") for r in counted]
    checks.append(_row("resident", True, res or ["no member counted"]))
    ctx, q8, wline = _window(v, window) if v["state"] == "pool" else (0, False, "no window: the pool does not run it")
    checks.append(_row("window", bool(ctx), [wline]))
    for c in checks:
        if not c["ok"]:
            blocks += (fit_block if c["check"] == "fit" else rp_block if c["check"] == "rpc" else vb if c["check"] ==
                       "versions" else bb if c["check"] == "build" else c["lines"][:1])
    local = [r["name"] for r in counted if r["kind"] == "local"]
    order = [r["name"] for r in counted if r["kind"] != "local"] + local  # the --rpc devices first, then this GPU
    split = dict(zip(v["members"], v["split"] or []))
    ok = not blocks
    return {"ok": ok, "model": model["name"], "display": model["display"], "checks": checks, "blocks": blocks,
            "lines": [f"{c['check']}: {'ok' if c['ok'] else 'BLOCKS'} -- " + "; ".join(c["lines"]) for c in checks],
            "fit": v, "rows": rows, "used": [r["name"] for r in counted], "excluded": [r["name"] for r in out_wifi],
            "gguf": g, "versions": {"controller": ctl, "workers": rp["workers"]}, "ctx": ctx, "q8": q8,
            "cache": "q8_0" if q8 else "f16", "rpc": rp["rpc"], "local": local, "order": order,
            "split": [split.get(n, 0.0) for n in order], "allow_wifi": wifi_ok,
            "line": (f"preflight green: {model['display']} on {len(counted)} nodes, {wline}" if ok else
                     f"preflight blocks {model['display']}: {blocks[0]}")}
