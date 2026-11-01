"""halo_harness.local_sched.bundle_parts -- a bundle's verdict across its reservations (Halo 3.3.8.0 R4; docs/
MODELS-bundles.md "Several reservations, a schedule, a priority"): each reservation is judged where it is held.

    split(bundle) -> (main block, [{host, reservation, role, need}])   the default host's block keeps the needs no
        other reservation holds and the default host's reservation; one part per reservation with a `host`
    verdict(bundle, host=None, *, state_dir=None) -> local_sched/bundle_fit's verdict of the main block, plus
        parts [{host, role, model, state, says, gb, preempts, via}] for the others, `schedule` {hours, now, line},
        `priority`; `state` is the worst of them (wont > unknown > downloads > ready) and `says` carries each part
        (`main_says`: the default host's line alone)
    pool_part(res, need, *, bundle, state_dir=None) -> a part the pool holds (local_pool/route): its fit, the GGUF
        here, and who holds the pool now -- the pool is one resource: a lower claim on it is pre-empted, an equal or
        higher one holds it
A bundle with one reservation on the default host and no schedule is judged exactly as before (bundle_fit alone).
Arithmetic and reads only: nothing loads, nothing is claimed here.
"""

from __future__ import annotations

from typing import Optional

GIB = 2 ** 30
WORST = {"wont": 3, "unknown": 2, "downloads": 1, "ready": 0}
POOL = "pool"


def split(bundle: dict) -> "tuple[dict, list]":
    away = [r for r in bundle.get("reservations") or [] if r.get("host")]
    roles = {r.get("role") for r in away if r.get("role")}
    main = {**bundle, "needs": {k: v for k, v in (bundle.get("needs") or {}).items() if k not in roles}}
    parts = [{"host": r["host"], "reservation": r, "role": r.get("role"),
              "need": (bundle.get("needs") or {}).get(r.get("role") or "") or {}} for r in away]
    return main, parts


def schedule_of(bundle: dict, now: Optional[float] = None) -> Optional[dict]:
    from halo_harness.packs.manifest_bundle_claims import in_hours
    s = bundle.get("schedule") or {}
    if not s.get("hours"):
        return None
    on = in_hours(s["hours"], now)
    start = s["hours"].split("-", 1)[0].strip()
    return {"hours": s["hours"], "now": on, "line": f"holds its claims {s['hours']} (the host's local clock): " +
            ("held now" if on else f"not held now (from {start})")}


def _held_pool(bundle_id: str, state_dir) -> list:
    from halo_harness.local_sched.reserve import claims
    return [c for c in claims(None, state_dir=state_dir) if str(c.get("host") or "").lower() == POOL
            and c.get("bundle") != bundle_id]


def pool_part(res: dict, need: dict, *, bundle: dict, state_dir=None) -> dict:
    from halo_harness.local_pool.route import model_for, route
    from halo_harness.local_sched import preempt as PE
    names = (need.get("any_of") or []) if res.get("model") == res.get("role") else [res["model"]]
    pick = next((n for n in names if model_for(n) is not None), None)
    out = {"host": POOL, "role": res.get("role"), "model": pick, "gb": None, "preempts": [], "via": "pool",
           "priority": res.get("priority") or "normal", "window": res.get("window") or need.get("window")}
    if pick is None:
        from halo_harness.local_pool.catalog import names as cat
        return {**out, "state": "wont", "says": f"the pool for {res.get('role') or res['model']}: it serves its catalog "
                                                f"models ({', '.join(cat())}), not {', '.join(names) or res['model']}"}
    a = route({"model": pick, "window": out["window"]}, state_dir=state_dir)
    out["model"] = model_for(pick)["name"]
    out["gb"] = round(a["need_bytes"] / GIB, 1) if a.get("need_bytes") else None
    head = f"the pool for {res.get('role') or out['model']}"
    if not a.get("fits"):
        return {**out, "state": "wont", "says": f"{head}: {a.get('verdict')}"}
    held = _held_pool(bundle["id"], state_dir)
    pe = PE.plan(held, need_gb=1.0, free_gb=0.0, priority=out["priority"], bundle=bundle["id"]) if held else None
    if pe is not None:
        lower = [c for c in held if PE.rank(c.get("priority")) < PE.rank(out["priority"])]
        if len(lower) < len(held):  # the pool is one resource: an equal or higher claim holds all of it
            return {**out, "state": "wont", "says": f"{head}: " + PE.held_line(bundle["id"], out["priority"], [
                c for c in held if c not in lower])}
        out["preempts"] = [{"bundle": c.get("bundle"), "host": POOL, "gb": float(c.get("gb") or 0),
                            "priority": c.get("priority") or "normal", "via": c.get("via")} for c in lower]
    state = "ready" if a.get("installed") else "downloads"
    says = f"{head}: {a.get('verdict')}" + ("" if a.get("installed") else " -- the GGUF is not here yet")
    says += "".join(f"; pre-empts {c['bundle']} ({c['priority']}) on the pool" for c in out["preempts"])
    return {**out, "state": state, "says": says, "speed": a.get("speed")}


def _away(part: dict, bundle: dict, state_dir) -> dict:
    from halo_harness.local_sched.bundle_fit import verdict_one as fit
    res = part["reservation"]
    if str(part["host"]).lower() == POOL:
        return pool_part(res, part["need"], bundle=bundle, state_dir=state_dir)
    sub = {**bundle, "needs": {part["role"]: part["need"]} if part["role"] else {},
           "reservation": {**res, "host": None}, "routing": {**bundle["routing"], "task_work": "local"}}
    v = fit(sub, part["host"], state_dir=state_dir)
    return {"host": v.get("host") or part["host"], "role": part["role"], "model": (v.get("reserved") or {}).get("model"),
            "gb": (v.get("reserved") or {}).get("gb"), "state": v["state"], "via": v.get("via"),
            "says": f"{part['host']} for {part['role'] or res['model']}: {v['says']}", "preempts": v.get("preempts") or [],
            "priority": res.get("priority") or "normal", "window": (v.get("reserved") or {}).get("window")}


def verdict(bundle: dict, host=None, *, state_dir=None, now: Optional[float] = None, reads_=None) -> dict:
    from halo_harness.local_sched.bundle_fit import verdict_one as fit
    main, parts = split(bundle)
    v = fit(main, host, state_dir=state_dir, reads_=reads_)
    sched = schedule_of(bundle, now)
    v.update(parts=[], schedule=sched, priority=bundle.get("priority") or "normal", main_says=v["says"])
    for p in parts:
        got = _away(p, bundle, state_dir)
        v["parts"].append(got)
        if WORST[got["state"]] > WORST.get(v["state"], 0):
            v["state"] = got["state"]
        v["says"] += f"; {got['says']}"
    if sched:
        v["says"] += f"; {sched['line']}"
    return v
