"""halo_harness.local_pool.fit -- can this model run on the pool, or on one of its nodes (Halo 3.3.8.0 R1; docs/POOL.md
"The fit"). One deterministic function, every number said; no model, no network.

    fit(model, rows) -> {model, display, state (single | pool | no), node, split, max_ctx_f16, max_ctx_q8, need_gb,
                         free_gb, nodes, members, excluded, lines, verdict, badge, batch_only, min_build, speed,
                         weights_gb, routing_table_gb, active_b}
        model: a local_pool/catalog row; rows: local_pool/budget rows (free_gb per member; one with no VRAM read is
        left out with its line)

The arithmetic (GB = 2^30 bytes, as the host cards count):
    kv(ctx)      = ctx x kv_bytes_per_token at F16; Q8_0 halves it
    single node  = weights + routing tables + kv(16k) + 1 GB of buffers <= that node's FREE VRAM
                   -> "a single node holds it -- run it there, pooling is unnecessary" (the single-node-first rule)
    the pool     = weights + n x routing tables (every RPC device holds its own copy) + n x 1 GB + kv(16k) <= the
                   members' free VRAM together, and each node's share (split x (weights + kv(16k))) + its routing
                   table + 1 GB <= its own free VRAM
    the window   = the room left / kv per token: F16 rounded down to 1k, Q8_0 the same room doubled, both clamped at
                   32k -- never 64k on a pool this size
One KV floor (16k at F16) for both checks. The split is proportional to each node's free VRAM after its own copy of the
routing tables and its buffers (model_split; the weights you set win).
The matched-memory block is said only for a model with routing tables: a dense model's share shrinks with its node.
"""

from __future__ import annotations

from halo_harness.local_pool.budget import normalize, split_from, tensor_split

OVERHEAD_GB = 1.0
FLOOR = 16384
CLAMP = 32768
STEP = 1024
GIB = 2 ** 30


def kv_gb(model: dict, ctx: int, q8: bool = False) -> float:
    return ctx * float(model["kv_bytes_per_token"]) / GIB / (2.0 if q8 else 1.0)


def windows(room_gb: float, model: dict) -> "tuple[int, int]":
    raw = max(0.0, room_gb) * GIB / float(model["kv_bytes_per_token"])
    return min(CLAMP, int(raw // STEP) * STEP), min(CLAMP, int(2 * raw // STEP) * STEP)


def k(n: int) -> str:
    return f"{n // 1024}k" if n >= 1024 else str(n)


def _counted(rows: list) -> "tuple[list, list]":
    ok = [r for r in rows if isinstance(r.get("free_gb"), (int, float)) and r["free_gb"] > 0]
    return ok, [r for r in rows if r not in ok]


def _tail(model: dict, rows: list, state: str) -> "list[str]":
    out = []
    for r in rows:
        if r.get("vram_source") == "stated":
            out.append(f"{r['name']}: VRAM as you stated it ({r['free_gb']:g} GB); no card read there")
        link, rtt = str(r.get("link_word") or ""), str(r.get("rtt_word") or "")
        word = link if "Wi-Fi" in link else rtt  # the adapter type first, the RTT second
        if "Wi-Fi" in word:
            out.append(f"{r['name']} is on {word}: a pooled decode waits on a round trip per layer boundary, so R2's "
                       "launch leaves a Wi-Fi member out unless you allow it")
    if model.get("batch_only"):
        s = model["speed"]
        out.append(f"batch-only: ~{s['tok_s_low']:g}-{s['tok_s_high']:g} tok/s pooled, a background lane, not interactive")
    if model.get("min_build"):
        out.append(f"needs llama.cpp b{model['min_build']}+ on the controller and every rpc-server")
    s = model["speed"]
    rng = f"{s['tok_s_low']:g}" if s["tok_s_low"] == s["tok_s_high"] else f"{s['tok_s_low']:g}-{s['tok_s_high']:g}"
    word = "measured elsewhere" if s["measured"] else "extrapolated"
    out.append(f"speed: {rng} tok/s pooled, {word} -- {s['source']}" + (
        "; on one node it decodes faster (pooling costs 21-55 % of decode)" if state == "single" else ""))
    return out


def fit(model: dict, rows: list) -> dict:
    counted, left = _counted(rows)
    W, R = float(model["weights_gb"]), float(model["routing_table_gb"])
    out = {"model": model["name"], "display": model["display"], "state": "no", "node": None, "split": [],
           "split_from": "", "max_ctx_f16": 0, "max_ctx_q8": 0, "need_gb": None, "free_gb": None, "nodes": 0,
           "members": [r["name"] for r in counted], "excluded": [r["name"] for r in left],
           "batch_only": bool(model.get("batch_only")), "min_build": model.get("min_build"), "speed": dict(model["speed"]),
           "weights_gb": W, "routing_table_gb": R, "active_b": model.get("active_b")}
    lines: "list[str]" = []
    need_one = W + R + kv_gb(model, FLOOR) + OVERHEAD_GB
    holders = sorted((r for r in counted if r["free_gb"] >= need_one), key=lambda r: (-r["free_gb"], r["name"]))
    if holders:
        best = holders[0]
        f16, q8 = windows(best["free_gb"] - W - R - OVERHEAD_GB, model)
        out.update(state="single", node=best["name"], split=[1.0], max_ctx_f16=f16, max_ctx_q8=q8, need_gb=round(need_one, 1),
                   free_gb=best["free_gb"], nodes=1, badge="pool: 1 node holds it")
        lines.append(f"a single node holds it: {best['name']} has {best['free_gb']:.1f} GB free, it needs {need_one:.1f} GB "
                     f"at 16k F16 -- run it there, pooling is unnecessary ({k(f16)} F16 / {k(q8)} Q8_0 there)")
    elif len(counted) < 2:
        out.update(need_gb=round(need_one, 1), free_gb=counted[0]["free_gb"] if counted else 0.0,
                   nodes=len(counted), badge="pool: no")
        lines.append(f"does not fit: needs {need_one:.1f} GB on one node, " + (
            f"{counted[0]['name']} has {counted[0]['free_gb']:.1f} GB free; a pool needs a second member with its VRAM read"
            if counted else "no member's VRAM is read yet (add members, or state a worker's VRAM with --vram)"))
    else:
        _pool(out, lines, model, counted)
    for r in left:
        lines.append(f"{r['name']}: not counted -- {r.get('line') or 'its VRAM is not read'}")
    out["lines"] = lines + _tail(model, counted, out["state"])
    out["verdict"] = out["lines"][0]
    return out



def model_split(model: dict, counted: list) -> "tuple[list, str]":
    """The model's tensor split: the weights you set, else each node's room for layers -- its free VRAM after its own
    copy of the routing tables and its buffers (for a dense model, free VRAM minus the buffers)."""
    if split_from(counted) == "the weights you set":
        return tensor_split(counted), "the weights you set"
    R = float(model["routing_table_gb"])
    return normalize([r["free_gb"] - R - OVERHEAD_GB for r in counted]), (
        "free VRAM after each node's routing table and buffers" if R else "free VRAM after each node's buffers")


def _pool(out: dict, lines: list, model: dict, counted: list) -> None:
    W, R, n = float(model["weights_gb"]), float(model["routing_table_gb"]), len(counted)
    split, how = model_split(model, counted)
    total = sum(r["free_gb"] for r in counted)
    kv16 = kv_gb(model, FLOOR)
    need = W + n * R + n * OVERHEAD_GB + kv16
    f16, q8 = windows(total - W - n * R - n * OVERHEAD_GB, model)
    shares = list(zip(counted, split or [0.0] * n))
    short = [(r, w * (W + kv16)) for r, w in shares if w * (W + kv16) + R + OVERHEAD_GB > r["free_gb"]]
    words = " / ".join(f"{w:.2f}" for w in split)
    out.update(split=split, split_from=how, need_gb=round(need, 1), free_gb=round(total, 1), nodes=n)
    if need <= total and not short:
        out.update(state="pool", max_ctx_f16=f16, max_ctx_q8=q8, badge=f"pool: fits ({n} nodes, {k(q8)} Q8_0)")
        lines.append(f"fits the pool: {n} nodes, split {words}, {k(f16)} F16 / {k(q8)} Q8_0")
        lines.append(f"needs {need:.1f} GB -- {total:.1f} GB free across {n} nodes (the split from {how})"
                     + (f"; one {R:g} GB routing table per node" if R else ""))
        return
    out["badge"] = "pool: no"
    if need > total:
        lines.append(f"does not fit: needs {need:.1f} GB" + (f" with {R:g} GB of routing tables per node" if R else "")
                     + f", {total:.1f} GB free across {n} nodes")
    else:
        r, layers = short[0]
        lines.append(f"does not fit: {r['name']}'s share needs {layers + R + OVERHEAD_GB:.1f} GB, it has "
                     f"{r['free_gb']:.1f} GB free")
    if R and need <= total:
        for r, layers in short:
            lines.append(f"matched memory: the {R:g} GB routing table replicates to every node; {r['name']} has "
                         f"{r['free_gb']:.1f} GB free and its share needs {layers + R + OVERHEAD_GB:.1f} GB ({layers:.1f} "
                         f"GB of layers + {R:g} GB of routing tables + {OVERHEAD_GB:g} GB of buffers)")
    elif R:
        small = min(counted, key=lambda r: r["free_gb"])
        lines.append(f"matched memory: the {R:g} GB routing table replicates to every node ({n * R:g} GB of the "
                     f"{need:.1f} GB); the smallest node, {small['name']}, has {small['free_gb']:.1f} GB free")
    kv8 = kv_gb(model, FLOOR, q8=True)
    q8_short = [r for r, w in shares if w * (W + kv8) + R + OVERHEAD_GB > r["free_gb"]]
    if need > total >= W + n * R + n * OVERHEAD_GB + kv8 and not q8_short:
        lines.append(f"with the KV cache at Q8_0 it would hold {k(q8)} -- under the 16k F16 floor Halo promises, so it "
                     "is not counted as a fit")
