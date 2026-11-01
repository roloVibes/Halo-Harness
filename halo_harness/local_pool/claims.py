"""halo_harness.local_pool.claims -- the pool's claim on every member, with a lease (Halo 3.3.8.0 R3; docs/POOL.md
"Claims"; the claim shape is 3.3.7.0 R5's, local_sched/claims_file.py).

    scope(model) -> "pool:<model>"    the bundle id every pool claim carries
    shares(model, v, ctx, q8) -> {member: GB}   each node's layers (its split x (weights + KV at the window)) + its own
                                     routing-table copy + 1 GB of buffers: what the pool holds on that card
    place(model, v, rows, *, ctx, q8, state_dir=None, home=None) -> (ok, lines, placed)
        per member, the Ollama models resident there that leave less free than its share are unloaded first, each
        with its pivot line ("pivot: qwen3.8:27b -> pool (Qwen3-Next) on pc, unloaded first: the pool's share is
        never spilled to the CPU"), then the claim: through the paired halo host (`control/claim`, the lease
        `lease_s`), in this machine's claims file for `local`, none for a bare address (said). A member still short
        after that is the overcommit line ("refused: worker2 needs 23.1 GB for its share, 20.0 GB free -- 3.1 GB
        missing") and nothing stays claimed.
    release(placed, *, state_dir=None, home=None, model="") -> lines   the claims released, then each model the pool
        pivoted out comes back as a stated pivot ("qwen3.8:27b reloads on pc, ~25 s"), never Ollama's silent load
    hold(scope, placed, state_dir) / renew_lines(placed, until, state_dir) -> the heartbeat renews them
        (local_sched/lease.py): a killed controller's claims expire within pool.claim_lease_s
"""

from __future__ import annotations

import time

from halo_harness.local_sched import claims_file as CF


def scope(model: str) -> str:
    return f"pool:{model}"


def shares(model: dict, v: dict, ctx: int, q8: bool) -> dict:
    from halo_harness.local_pool.fit import OVERHEAD_GB, kv_gb
    W, R = float(model["weights_gb"]), float(model["routing_table_gb"])
    kv = kv_gb(model, int(ctx), q8=q8)
    return {name: round(w * (W + kv) + R + OVERHEAD_GB, 2) for name, w in zip(v["members"], v["split"])}


def _here():
    from halo_harness.local_sched.facts import host_named
    return host_named(None)


def _local_row(model: dict, gb: float, until: float) -> dict:
    import os
    return {"bundle": scope(model["name"]), "host": getattr(_here(), "name", None) or "local", "model": scope(model["name"]),
            "gb": gb, "priority": "high",
            "at": round(time.time(), 3), "by": "pool", "holder": "process", "holder_pid": os.getpid(), "scope": "keep",
            "via": "local", "until": until}


def _unload(m: dict, name: str, home, local: bool) -> "tuple[bool, str]":
    if local:
        from halo_harness.providers.ollama_load import unload
        got = unload(_here(), name)
        return bool(got.get("ok")), str(got.get("say") or "")
    from halo_harness.local_pool.hosts import act
    ok, say, _got = act(m, "unload", {"model": name}, home=home, why="the pool needs the card")
    return ok, say


def _unload_first(m: dict, r: dict, need: float, model: dict, home, local: bool = False) -> "tuple[float, list, list, str]":
    """When the card's free VRAM is short of the share, every Ollama model resident there is unloaded first (its GB
    come back as the card read them): a pool's share is never spilled to the CPU."""
    free, lines, gone = float(r.get("free_gb") or 0), [], []
    if free >= need or not r.get("resident"):
        return free, lines, gone, ""
    for name in list(r.get("resident") or []):
        ok, say = _unload(m, name, home, local)
        if not ok:
            return free, lines, gone, f"{m['name']}: {name} stays resident ({say}), so the pool's share would not fit"
        gone.append(name)
        lines.append(f"pivot: {name} -> pool ({model['display']}) on {m['name']}, unloaded first: the pool's share is "
                     "never spilled to the CPU")
    return free + float(r.get("resident_gb") or 0), lines, gone, ""


def place(model: dict, v: dict, rows: list, *, ctx: int, q8: bool, state_dir=None, home=None) -> "tuple[bool, list, list]":
    from halo_harness.local_pool.hosts import act
    from halo_harness.local_pool.members import resolve
    want = shares(model, v, ctx, q8)
    until = round(time.time() + CF.lease_s(), 3)
    lines, placed = [], []
    for r in [x for x in rows if x["name"] in want]:
        m, need = {"name": r["name"], "host": r["host"], "rpc_port": r["rpc_port"]}, want[r["name"]]
        kind = resolve(m, home)["kind"]
        row = {"member": r["name"], "host": r["host"], "rpc_port": r["rpc_port"], "kind": kind, "gb": need, "pivoted": []}
        if kind == "address":
            lines.append(f"{r['name']}: no halo host there, so nothing on it is claimed ({need:.1f} GB is its share)")
            placed.append(row)
            continue
        free, said, gone, why = _unload_first(m, r, need, model, home, local=kind == "local")
        lines += said
        row["pivoted"] = gone
        if why or free + 0.05 < need:
            lines.append(why or f"refused: {r['name']} needs {need:.1f} GB for its share, {free:.1f} GB free -- "
                                f"{need - free:.1f} GB missing (a pool never spills a share to the CPU)")
            lines += release(placed + [row], state_dir=state_dir, home=home, bundle=scope(model["name"]))
            return False, lines, []
        if kind == "local":
            CF.put(CF.local_file(_state(state_dir)), _local_row(model, need, until))
            lines.append(f"claimed {need:.1f} GB on {r['name']} (this machine) for the pool, lease {CF.lease_s():g} s")
        else:
            ok, say, _got = act(m, "claim", {"model": scope(model["name"]), "gb": need, "bundle": scope(model["name"]),
                                             "priority": "high", "lease_s": CF.lease_s()}, home=home, why="the pool")
            if not ok:
                lines.append(f"refused: {r['name']} did not take the pool's claim ({say})")
                lines += release(placed + [row], state_dir=state_dir, home=home, bundle=scope(model["name"]))
                return False, lines, []
            lines.append(f"claimed {need:.1f} GB on {r['name']} for the pool, lease {CF.lease_s():g} s")
        placed.append(row)
    hold(scope(model["name"]), placed, state_dir, home)
    return True, lines, placed


def _state(state_dir=None):
    if state_dir is not None:
        return state_dir
    from halo_harness.config.paths import bridge_home
    return bridge_home()


def renew_lines(placed: list, bundle: str, until: float, state_dir=None, home=None) -> list:
    from pathlib import Path
    from halo_harness.local_pool.hosts import act
    if not Path(_state(state_dir)).is_dir():  # that home is gone (a test's scratch home): nothing to renew
        return []
    out = []
    for p in placed:
        if p["kind"] == "local":
            n = len(CF.renew(CF.local_file(_state(state_dir)), bundle, until))
            out.append(f"{p['member']}: {n} renewed here")
        elif p["kind"] == "paired":
            ok, say, _g = act({"name": p["member"], "host": p["host"], "rpc_port": p["rpc_port"]}, "renew",
                              {"bundle": bundle, "lease_s": CF.lease_s()}, home=home)
            out.append(say if ok else f"{p['member']}: the renewal did not land ({say})")
    return out


def hold(bundle: str, placed: list, state_dir=None, home=None) -> None:
    from halo_harness.local_sched import lease
    state = _state(state_dir)
    lease.hold(bundle, lambda until: renew_lines(placed, bundle, until, state, home))


def release(placed: list, *, state_dir=None, home=None, model: str = "", bundle: str = "") -> list:
    from halo_harness.local_pool.hosts import act
    from halo_harness.local_sched import lease
    bundle = bundle or scope(model)
    out = []
    for p in placed:
        m = {"name": p["member"], "host": p["host"], "rpc_port": p["rpc_port"]}
        b = bundle or p.get("bundle") or ""
        if p["kind"] == "local":
            gone = CF.drop(CF.local_file(_state(state_dir)), b)
            out += [f"released {float(g.get('gb') or 0):.1f} GB on {p['member']}" for g in gone]
        elif p["kind"] == "paired":
            ok, say, _g = act(m, "release", {"bundle": b}, home=home)
            out.append(say if ok else f"{p['member']}: the release did not land ({say}); the claim ends with its lease")
        for name in p.get("pivoted") or []:
            out.append(_return_line(m, name, home, local=p["kind"] == "local"))
    lease.release(bundle)
    return out


def _return_line(m: dict, name: str, home, local: bool = False) -> str:
    """The model the pool pivoted out comes back as a stated pivot (its load seconds from the host's `route`, or this
    machine's ledger), never Ollama's silent load on the next call."""
    from halo_harness.local_pool.hosts import act, client
    from halo_harness.local_sched.swap_cost import load_s_for, secs
    took = None
    try:
        if local:
            took = load_s_for(_here(), name, fetch=False)["s"]
        else:
            c, _k, _l = client(m, home)
            took = (c.route({"model": name}) or {}).get("load_s") if c is not None else None
    except Exception:
        took = None
    if local:
        from halo_harness.providers.ollama_load import load
        got = load(_here(), name)
        ok, say = bool(got.get("ok")), str(got.get("say") or "")
    else:
        ok, say, _g = act(m, "warm", {"model": name}, home=home, why="the pool stopped: back to what ran there")
    eta = f"~{secs(took)}" if isinstance(took, (int, float)) else "load time unknown"
    return (f"pivot: pool -> {name} on {m['name']}: {name} reloads on {m['name']}, {eta}" if ok else
            f"pivot: pool -> {name} on {m['name']}: {name} reloads on {m['name']} on its next call, {eta} ({say})")
