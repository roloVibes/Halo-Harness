"""halo_harness.local_pool.route -- the pool answers `route` like a host (Halo 3.3.8.0 R3; docs/POOL.md "The pool in
placement"; local_sched/place.py asks it beside every Ollama host).

    PoolHost(name="pool", url, max_ctx, pool=True)       the pseudo-host local_sched/place.solve scores
    pool_host(state_dir=None) -> PoolHost | None   when the pool has members (pool.json) or runs
    model_for(name) -> the catalog row a lane's model is (its name, display, repo, or one of its `match` words)
    route(need, *, state_dir=None) -> {host: "pool", via: "pool", fits, now, warm, evicts, load_s, load_from,
        installed, capable, need_bytes, usable_bytes, window, verdict, penalty_pct, penalty_from, degraded}
        fits: the fit from local_pool/fit (state "pool") at the window asked -- never past the pool's window (said);
        now / warm: the pool runs this model now (launched); load_s when it does not: the GGUF's download (its size
        over the measured pull rate) when it is not on disk, plus the load (the size over the disk rate assumed);
        degraded: a running pool with a worker down does not take a lane ("degraded (worker2 down)")
        penalty_pct: the research's measured 21-55 % decode penalty (its midpoint, PENALTY_PCT) until R4's bench
        measures the pool's own
Reads only (the members' cached cards); nothing launches.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

PENALTY_PCT = 38.0
PENALTY_FROM = "the research's measured 21-55 % decode penalty against one node (its midpoint; not measured here)"
DISK_BPS = 1.5e9
GIB = 2 ** 30


@dataclass(frozen=True)
class PoolHost:
    name: str = "pool"
    url: str = ""
    max_ctx: Optional[int] = None
    pool: bool = True


def pool_host(state_dir=None) -> Optional[PoolHost]:
    from halo_harness.local_pool import launch
    from halo_harness.local_pool.members import load
    r = launch.run(state_dir)
    if not r and not load(state_dir):
        return None
    return PoolHost(url=str(r.get("url") or ""), max_ctx=r.get("ctx"))


def model_for(name: str) -> Optional[dict]:
    from halo_harness.local_pool import catalog as C
    hit = C.get(str(name or "").split("@", 1)[0].removeprefix("hf:local/"))
    if hit is not None:
        return hit
    n = str(name or "").lower()
    return next((row for row in C.CATALOG.values() if any(w in n for w in row.get("match") or ())), None)


def _no(out: dict, verdict: str) -> dict:
    return {**out, "fits": False, "now": False, "verdict": verdict}


def route(need: dict, *, state_dir=None) -> dict:
    from halo_harness.local_pool import gguf, launch
    from halo_harness.local_pool.budget import budgets
    from halo_harness.local_pool.fit import fit, k
    from halo_harness.local_pool.recommend import rate
    window = int(need.get("window") or 0) or None
    out = {"host": "pool", "via": "pool", "fits": None, "now": False, "warm": False, "evicts": [], "load_s": None,
           "load_from": "", "installed": None, "capable": True, "need_bytes": None, "usable_bytes": None,
           "window": window, "penalty_pct": PENALTY_PCT, "penalty_from": PENALTY_FROM, "degraded": []}
    model = model_for(need.get("model") or "")
    if model is None:
        from halo_harness.local_pool.catalog import names
        return _no(out, f"the pool serves its catalog models ({', '.join(names())}), not {need.get('model')}")
    r = launch.run(state_dir)
    if r and r.get("model") == model["name"] and launch.alive(r):
        from halo_harness.local_pool.degrade import status
        st = status(state_dir)
        if st["state"] == "degraded":
            return {**_no(out, f"the pool is {st['line'].split(': ', 1)[-1]}: it takes no lane until it is warmed again"),
                    "degraded": st["degraded"]}
        cap = int(r.get("ctx") or 0)
        if window and cap and window > cap:
            return _no(out, f"{model['display']} runs on the pool at {cap:,} (the fit's window); {window:,} is past it")
        return {**out, "fits": True, "now": True, "warm": True, "installed": True, "window": window or cap,
                "verdict": f"{model['display']} runs on the pool now ({r.get('cache')} KV, -c {cap:,}); pooled decode "
                           f"is ~{PENALTY_PCT:.0f} % slower than one node that holds it"}
    from halo_harness.local_pool.preflight import _room  # a resident Ollama model is room Warm pivots out
    v = fit(model, [_room(x) for x in budgets(state_dir=state_dir)])
    if v["state"] != "pool":
        return _no(out, f"the pool: {v['verdict']}")
    best = v["max_ctx_q8"]
    if window and window > best:
        return _no(out, f"{model['display']} fits the pool up to {k(best)} (Q8_0 KV); {window:,} is past it")
    g = gguf.find(model)
    bps, src = rate(state_dir)
    size = float(model["weights_gb"]) * GIB
    load = size / DISK_BPS + (0.0 if g["path"] else size / bps)
    out.update(fits=True, installed=bool(g["path"]), load_s=round(load), need_bytes=int(v["need_gb"] * GIB),
               usable_bytes=int(v["free_gb"] * GIB), window=window or v["max_ctx_f16"],
               load_from=("the GGUF from disk at an assumed 1.5 GB/s" if g["path"] else
                          f"the {model['weights_gb']:g} GB download at {src}, then the load"))
    out["verdict"] = (f"{model['display']} fits the pool ({v['nodes']} nodes, {k(v['max_ctx_f16'])} F16 / "
                      f"{k(v['max_ctx_q8'])} Q8_0); Warm starts it, ~{round(load)} s ({out['load_from']})")
    return out
