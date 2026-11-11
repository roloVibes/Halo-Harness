"""halo_harness.host.routes_guard -- the host's R4 reads (Halo 3.3.7.0 R4; docs/HOST.md "The residency clock", "The
off-hours refresh"; dispatched by host/routes_act.get).

    GET residency   {residency: [{host, model, at, by, op, keep_alive}], min_resident_s, claims}: the shared clock and
                    (3.3.7.0 R5) the bundles' claims on the cards this host serves (local_sched/claims_file.py)
    GET idle        {hosts: [{host, idle_s, last, last_what, busy, foreign: [...], line, foreign_line}]}
    GET refresh     {settings, plan, line, last, last_line, review, running}
Read-only: one /api/ps per served host for `idle`; nothing loads.
"""

from __future__ import annotations

from halo_harness.peers import protocol

ROUTES = ("residency", "idle", "refresh")


def get(svc, head: str, q: dict):
    if head == "residency":
        from halo_harness.host.residency import claims, rows  # 3.3.7.0 R5 claims; 3.3.8.0 R3: the live ones (a lease)
        from halo_harness.local_sched.pivot import min_resident_s
        return 200, protocol.doc(residency=rows(svc.home), min_resident_s=min_resident_s(), claims=claims(svc.home))
    if head == "idle":
        from halo_harness.ollama_steward.idle import idle_since
        out = []
        for h in svc.view.hosts():
            if q.get("host") and h.name != q["host"]:
                continue
            got = idle_since(svc.home, h)
            out.append({"host": h.name, **{k: got[k] for k in ("idle_s", "last", "last_what", "busy", "line",
                                                                "foreign_line")},
                        "foreign": got["foreign"]})
        return 200, protocol.doc(hosts=out)
    from halo_harness.host.refresh import status
    got = status(svc.home, svc.view.hosts())
    return 200, protocol.doc(**{k: got[k] for k in ("settings", "plan", "line", "last", "last_line", "review",
                                                     "running")})
