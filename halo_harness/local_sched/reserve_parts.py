"""halo_harness.local_sched.reserve_parts -- claiming a bundle's other reservations (Halo 3.3.8.0 R4; docs/
MODELS-bundles.md "Several reservations, a schedule, a priority"; local_sched/reserve_act.claim calls it after the
default host's claim).

    claim_parts(bundle_id, b, v, *, holder, state) -> [line]   each part of the verdict (local_sched/bundle_parts):
        the lower claims it pre-empts first (local_sched/preempt.take: one line each, a notice for their owner), then
        the pool: a row on host `pool` in this machine's claims file (the pool is reserved for that lane; Warm starts
        it -- a reservation never launches a process); a paired host: its `claim` op (with the lease when a halo
        process holds it, and the bundle's hours), else a local row, and the reserved model's keep_alive -1 there
    lease_keys(bundle_id) -> the heartbeat keys a bundle's parts hold      every row carries `hours` (the schedule)
Nothing downloads and nothing loads here.
"""

from __future__ import annotations

import os
import time

from halo_harness.local_sched import claims_file as CF

POOL = "pool"


def _row(bundle_id: str, b: dict, p: dict, *, holder: str, host: str, via: str) -> dict:
    return {"bundle": bundle_id, "name": b.get("name"), "host": host, "model": p.get("model"),
            "gb": round(float(p.get("gb") or 0), 2), "window": p.get("window"), "priority": p.get("priority"),
            "keep_alive": -1, "at": round(time.time(), 3), "by": "halo", "holder": holder,
            "holder_pid": os.getpid() if holder == "process" else None,
            "scope": "until-restart" if holder == "process" else "keep", "change_id": None,
            "escalation": b["routing"]["escalation"], "task_work": b["routing"]["task_work"], "via": via,
            "until": round(time.time() + CF.lease_s(), 3) if holder == "process" else None,
            "hours": (b.get("schedule") or {}).get("hours")}


def _pool(bundle_id: str, b: dict, p: dict, holder: str, state) -> list:
    CF.put(CF.local_file(state), _row(bundle_id, b, p, holder=holder, host=POOL, via="local"))
    from halo_harness.local_pool import catalog as C, launch
    m = C.get(p.get("model") or "") or {"display": p.get("model"), "name": p.get("model")}
    r = launch.run(state)
    now = bool(r and launch.alive(r) and r.get("model") == m["name"])
    return [f"reserved the pool for {bundle_id}'s {p.get('role') or 'lane'} ({m['display']}, {p.get('gb') or 0:g} GB "
            f"across its members, priority {p.get('priority')}): " +
            ("it runs it now" if now else f"Warm starts it (halo local serve --pool {m['name']}); nothing launches "
                                          "until then")]


def _paired(bundle_id: str, b: dict, p: dict, holder: str, state) -> list:
    from halo_harness.local_sched.facts import host_named
    from halo_harness.local_sched.reserve_act import _host_act, _keep_alive
    h = host_named(p["host"])
    hours = (b.get("schedule") or {}).get("hours")
    landed, say = _host_act(h, "claim", {"model": p["model"], "gb": round(float(p.get("gb") or 0), 2),
                                         "bundle": bundle_id, "window": int(p.get("window") or 8192),
                                         "priority": p.get("priority"),
                                         **({"lease_s": CF.lease_s()} if holder == "process" else {}),
                                         **({"hours": hours} if hours else {})})
    if say and not landed:
        return [f"{bundle_id}: the halo host for {p['host']} did not take the claim: {say}"]
    row = _row(bundle_id, b, p, holder=holder, host=p["host"], via="host" if landed else "local")
    row["change_id"], ka = _keep_alive(state, p["host"], p["model"], bundle_id, holder)
    CF.put(CF.local_file(state), row)
    if holder == "process" and landed:
        _lease(bundle_id, state, h)
    return [f"reserved {p['model']} on {p['host']} for {bundle_id}: {float(p.get('gb') or 0):.1f} GB held"
            + (" by the halo host" if landed else "") + f"; {ka}"]


def _lease(bundle_id: str, state, host) -> None:
    from halo_harness.local_sched import lease
    from halo_harness.local_sched.reserve_act import _host_act

    def renew(_until: float) -> list:
        ok, say = _host_act(host, "renew", {"bundle": bundle_id, "lease_s": CF.lease_s()})
        return [say if ok else f"the host did not renew it ({say or 'no answer'})"]
    lease.hold(f"bundle:{bundle_id}@{getattr(host, 'name', host)}", renew)


def lease_keys(bundle_id: str) -> list:
    from halo_harness.local_sched import lease
    return [k for k in lease.held() if k.startswith(f"bundle:{bundle_id}@")]


def claim_parts(bundle_id: str, b: dict, v: dict, *, holder: str, state) -> list:
    from halo_harness.local_sched import preempt as PE
    lines = []
    for p in v.get("parts") or []:
        for c in p.get("preempts") or []:
            lines += PE.take(c, winner=bundle_id, priority=p.get("priority") or "normal", state_dir=state)
        if str(p.get("host")).lower() == POOL:
            lines += _pool(bundle_id, b, p, holder, state)
        elif p.get("model"):
            lines += _paired(bundle_id, b, p, holder, state)
    return lines
