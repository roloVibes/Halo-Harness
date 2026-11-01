"""halo_harness.ollama_steward.rules_pool -- the steward watches the pool like a host (Halo 3.3.8.0 R4; docs/
MODELS-steward-servers.md "The pool's three kinds"): llama.cpp's RPC lines in the controller's log (the pool's
llama-server, read by server_log_hf under the server name `pool`), one line per finding, keyed `pool|<model>`, each
with `server: "pool"`, `runtime: "llama-server"` and `pool: true`.

    pool-degraded  an RPC backend lost mid-generation (`rpc-lost` events: "Remote RPC server crashed or returned
                   malformed response", "Failed to connect to <addr>"): the request failed once and is not retried;
                   the member named from run.json's rpc rows, the same word as local_pool/degrade.status
                   ("degraded (worker2 down)")
    pool-rtt       the reply rate the log printed (`timing` events) against the pool's own bench card (no card: no
                   finding -- an extrapolated figure says nothing about this pool): slower than the round trips the
                   preflight measured explain. The link the OS read speaks first, the RTT second; it names which spoke
    pool-spill     the newest load's per-device model buffers against the split (a node holds less than its share),
                   or layers left on the controller's CPU (`offloaded a/b`)
    pool_rules(ctx) -> [finding]            supersede(findings) -> the generic cpu-spill of the pool's group dropped
    member_of(addr, run) -> the member that address is, else the address
Reads only: nothing here changes the pool; a finding says what to do (Warm again, a member to look at).
"""

from __future__ import annotations

from statistics import median
from typing import Optional

from halo_harness.ollama_steward.rules import finding

SLOW = 0.75          # a reply rate under three quarters of the reference is a slow pool
LINK_X = 2.0         # ...and the slowdown per token is more than twice what the round trips explain
SPILL_SHARE = 0.85   # a node holding under 85 % of its split's share of the weights
RECENT = 8           # the newest timing events read


def _pool(g: dict) -> bool:
    from halo_harness.local_pool import POOL_SERVER_NAME
    return str(g.get("host") or "").lower() == POOL_SERVER_NAME


def _run(ctx: dict) -> dict:
    from halo_harness.local_pool import launch
    return launch.run(ctx.get("state_dir"))


def member_of(addr: Optional[str], run: dict) -> str:
    a = str(addr or "").strip("[]")
    for x in run.get("rpc") or []:
        door = str(x.get("addr") or "")
        if a and (a == door or a in door or door in a):
            return str(x.get("member"))
    return a or "a worker"


def _tag(f: dict) -> dict:
    f.update(server="pool", runtime="llama-server", pool=True, not_asked=[])
    return f


def degraded(g: dict, ctx: dict, run: dict) -> list:
    from halo_harness.local_pool.degrade import word
    lost = [e for e in g["events"] if e.get("kind") == "rpc-lost"]
    if not lost:
        return []
    named = sorted({member_of(e["data"]["addr"], run) for e in lost if (e.get("data") or {}).get("addr")})
    who = named or ["a worker"]  # the abort line names no address: the connect line before it does
    last = lost[-1]
    text = (f"{g['model']} on the pool: {word(who)} -- an RPC backend was lost mid-generation ({len(lost)} line"
            f"{'s' if len(lost) != 1 else ''}, the newest at {last.get('at')}): the request failed once and is not "
            f"retried; Warm the pool again once {', '.join(who)} answers (halo pool rpc {who[0]} status)")
    return [_tag(finding("pool-degraded", g, "error", text, events=lost,
                         numbers={"lost": len(lost), "members": who}))]


def _reference(g: dict, ctx: dict) -> "tuple[Optional[float], str]":
    """The pool's own bench card (its slowest window): an extrapolated figure says nothing about this pool, so with
    no card there is no pool-rtt (halo local bench --host pool measures it)."""
    from halo_harness.local_pool.catalog import get
    from halo_harness.local_pool.route import model_for
    from halo_harness.local_pool.speed import card_for, floor
    model = model_for(g["model"]) or get(g["model"]) or {}
    own = floor(card_for(model, ctx.get("state_dir"))) if model else None
    return (own, "its own bench card") if own else (None, "")


def _link(run: dict) -> "tuple[float, str]":
    rows = [x for x in run.get("rpc") or [] if isinstance(x, dict)]
    ms = sum(float(x["rtt_ms"]) for x in rows if isinstance(x.get("rtt_ms"), (int, float)))
    said = []
    for x in rows:
        if x.get("link"):  # the OS read the adapter: it speaks first
            said.append(f"{x['member']} {x['link']} (the OS)")
        elif isinstance(x.get("rtt_ms"), (int, float)):
            said.append(f"{x['member']} {x['rtt_ms']:g} ms RTT (the probe)")
    return ms, ", ".join(said) or "no link read"


def rtt(g: dict, ctx: dict, run: dict) -> list:
    rates = [float((e.get("data") or {}).get("eval_tok_s")) for e in g["events"] if e.get("kind") == "timing"
             and isinstance((e.get("data") or {}).get("eval_tok_s"), (int, float))][-RECENT:]
    ref, ref_from = _reference(g, ctx)
    if len(rates) < 3 or not ref:
        return []
    got = median(rates)
    seen_ms, want_ms = 1000.0 / got, 1000.0 / ref
    link_ms, link_said = _link(run)
    if got >= SLOW * ref or (seen_ms - want_ms) <= LINK_X * max(link_ms, 0.0):
        return []
    wifi = "Wi-Fi" in link_said
    text = (f"{g['model']} on the pool replies at {got:.1f} tok/s ({seen_ms:.0f} ms a token) against {ref:.1f} "
            f"({want_ms:.0f} ms, {ref_from}); the round trips explain ~{link_ms:.1f} ms a token ({link_said}): "
            + ("a member is on Wi-Fi -- wire it or leave it out" if wifi else
               "slower than its link explains -- a member's GPU is shared, or a worker throttles"))
    return [_tag(finding("pool-rtt", g, "warn", text, numbers={"tok_s": round(got, 1), "reference": round(ref, 1),
                                                             "ms_per_token": round(seen_ms, 1),
                                                             "link_ms": round(link_ms, 2), "link": link_said}))]


def _shares(load: dict, run: dict) -> list:
    """[(member, expected share, actual share, GB)] of the GPU devices in the newest load."""
    from halo_harness.ollama_steward.server_context_hf import HOST_BUFS
    devs = [d for d in load.get("devices") or [] if d.get("device") not in HOST_BUFS and d.get("model_mib")]
    total = sum(float(d["model_mib"]) for d in devs)
    order, split = list(run.get("order") or []), list(run.get("split") or [])
    if total <= 0 or not order or len(split) != len(order):
        return []
    local = [m for m in order if m not in {x.get("member") for x in run.get("rpc") or []}]
    out = []
    for d in devs:
        name = d["device"]
        who = member_of(name[4:-1], run) if name.startswith("RPC[") else (local[0] if local else name)
        if who in order:
            out.append((who, float(split[order.index(who)]), float(d["model_mib"]) / total, float(d["model_mib"]) / 1024))
    return out


def spill(g: dict, ctx: dict, run: dict) -> list:
    loads = [e.get("data") or {} for e in g["events"] if e.get("kind") == "load-result"]
    if not loads:
        return []
    ld = loads[-1]
    a, b = ld.get("offloaded"), ld.get("layers")
    low = [(m, want, have, gb) for m, want, have, gb in _shares(ld, run) if have < SPILL_SHARE * want]
    cpu = isinstance(a, int) and isinstance(b, int) and a < b
    if not low and not cpu:
        return []
    parts = [f"{m} holds {gb:.1f} GB of the weights, {have:.0%} against its {want:g} split" for m, want, have, gb in low]
    if cpu:
        parts.append(f"{b - a} of {b} layers stayed on the controller's CPU (offloaded {a}/{b})")
    text = (f"{g['model']} on the pool: " + "; ".join(parts) + " -- a node holds less than its split: its free VRAM "
            "fell after the preflight (another program, a resident model); Stop and Warm again re-reads it")
    per = ld.get("device_layers") or []
    return [_tag(finding("pool-spill", g, "warn", text, numbers={"low": [m for m, *_r in low], "offloaded": a,
                                                               "layers": b, "device_layers": per,
                                                               "layers_from": ld.get("layers_from")}))]


def pool_rules(ctx: dict) -> list:
    run = _run(ctx)
    out: list = []
    for g in ctx.get("groups") or []:
        if _pool(g):
            out += degraded(g, ctx, run) + rtt(g, ctx, run) + spill(g, ctx, run)
    return out


def supersede(findings: list) -> list:
    """The pool's group: pool-spill says the spill with its devices, so the generic cpu-spill is dropped."""
    from halo_harness.local_pool import POOL_SERVER_NAME
    return [f for f in findings if not (f.get("rule") == "cpu-spill" and str(f.get("host") or "").lower() ==
                                        POOL_SERVER_NAME)]
