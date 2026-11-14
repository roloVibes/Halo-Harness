"""halo_harness.host.ops_claim -- a bundle's reservation, held by the host (Halo 3.3.7.0 R5; plans/local-model-fit-brief.md
L2: "a deterministic claim the host enforces"; host/ops.py has the registry).

    claim {model, gb, bundle, window?, priority?, keep_alive?}   a row in `<state>/host/claims.json`: the model is
                                                    reserved for that bundle on the server this host serves; nothing
                                                    loads (the model loads on its first call, or with warm / pin)
    release {bundle}                                that bundle's rows taken out
    3.3.8.0 R4: claim's `hours` (the bundle's schedule) is kept on the row: outside them, on this host's clock, the
    claim is dormant (local_sched/claims_file.live)
    3.3.8.0 R3: claim's `lease_s` sets the row's `until` (now + lease_s; local_sched/claims_file.py): past it the claim
    is not a claim; `renew {bundle, lease_s?}` moves the lease of the rows that peer placed (its heartbeat:
    local_sched/lease.py) -- a renewal of a peer's own claim is never queued under host.allow_control: ask

While a claim holds a model the host's invariants count its GB in every load's budget (host/invariants.check_load:
a load that would breach what is left is refused with the claim and the numbers), never unload or pivot it out for a
request that does not name its bundle, and `GET residency` answers the claims so every peer's scheduler reads one
list. Grant: control. Nothing here changes a server setting or calls Ollama.
"""

from __future__ import annotations

import time

from halo_harness.host.ops import HOST, MODEL, PORT, Op
from halo_harness.host.ops_control import LOCAL_TIME


def _file(ctx):
    from halo_harness.local_sched.claims_file import host_file
    return host_file(ctx.home)


def _until(p: dict):
    v = p.get("lease_s")
    return round(time.time() + float(v), 3) if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0 else None


def _row(ctx, p: dict) -> dict:
    return {"bundle": p["bundle"], "host": ctx.host.name, "model": p["model"], "gb": float(p["gb"]),
            "window": p.get("window"), "priority": p.get("priority") or "normal", "keep_alive": p.get("keep_alive", -1),
            "at": round(time.time(), 3), "by": ctx.peer, "holder": "peer", "holder_pid": None, "scope": "keep",
            "change_id": None, "escalation": None, "task_work": None, "until": _until(p),
            "hours": p.get("hours") or None}  # 3.3.8.0 R4: the bundle's schedule, this host's clock


def p_claim(ctx, p):
    if not isinstance(p.get("gb"), (int, float)) or isinstance(p.get("gb"), bool) or float(p["gb"]) <= 0:
        raise ValueError("gb: the reservation's size in GB")
    return {"would": [f"hold {p['model']} on {ctx.host.name} for {p['bundle']} ({float(p['gb']):g} GB) until it is "
                      "released: nothing else evicts it, every load counts it"],
            "writes": ["<state>/host/claims.json: one row"], "takes": "~0 s", "cost": LOCAL_TIME}


def a_claim(ctx, p):
    from halo_harness.local_sched.claims_file import put
    p_claim(ctx, p)
    rows = put(_file(ctx), _row(ctx, p))
    ctx.publish("event", {"kind": "claimed", "model": p["model"], "bundle": p["bundle"],
                          "say": f"{p['bundle']} holds {p['model']} ({float(p['gb']):g} GB) on {ctx.host.name}"})
    return {"ok": True, "say": f"reserved {p['model']} on {ctx.host.name} for {p['bundle']} ({float(p['gb']):g} GB)",
            "claims": [r for r in rows if r.get("host") == ctx.host.name]}


def p_release(ctx, p):
    return {"would": [f"release what {p['bundle']} holds on {ctx.host.name}"], "writes": ["<state>/host/claims.json"],
            "takes": "~0 s", "cost": LOCAL_TIME}


def a_release(ctx, p):
    from halo_harness.local_sched.claims_file import drop
    gone = drop(_file(ctx), p["bundle"], ctx.host.name)
    if gone:
        ctx.publish("event", {"kind": "released", "bundle": p["bundle"], "say": f"{p['bundle']} released on {ctx.host.name}"})
    return {"ok": True, "released": len(gone), "say": (f"released {', '.join(str(r.get('model')) for r in gone)} on "
                                                       f"{ctx.host.name} ({p['bundle']})" if gone else
                                                       f"{p['bundle']} held nothing on {ctx.host.name}")}


def p_renew(ctx, p):
    return {"would": [f"move the lease of what {p['bundle']} holds on {ctx.host.name} to now + "
                      f"{float(p.get('lease_s') or 0) or 'pool.claim_lease_s'} s"], "writes": ["<state>/host/claims.json"],
            "takes": "~0 s", "cost": LOCAL_TIME}


def a_renew(ctx, p):
    from halo_harness.local_sched.claims_file import lease_s, renew
    until = _until(p) or round(time.time() + lease_s(), 3)
    got = renew(_file(ctx), p["bundle"], until, host=ctx.host.name, by=ctx.peer)
    return {"ok": True, "renewed": len(got), "until": until,
            "say": f"{p['bundle']}: {len(got)} claim{'' if len(got) == 1 else 's'} renewed on {ctx.host.name}" if got else
            f"{p['bundle']} holds no live leased claim of {ctx.peer} on {ctx.host.name} (an expired one is not renewed)"}


def held(home, host_name: str, model: str):
    """The claim on `model` on that server (the host's invariants read it), or None."""
    from halo_harness.local_sched.claims_file import host_file, read
    from halo_harness.providers.ollama import ollama_names_match
    return next((r for r in read(host_file(home)) if str(r.get("host") or "").lower() == str(host_name).lower()
                 and r.get("model") and ollama_names_match(r["model"], model)), None)


def claimed(home, host_name: str, *, but=None) -> list:
    from halo_harness.local_sched.claims_file import host_file, read
    from halo_harness.providers.ollama import ollama_names_match
    return [r for r in read(host_file(home)) if str(r.get("host") or "").lower() == str(host_name).lower()
            and float(r.get("gb") or 0) > 0 and not (but and r.get("model") and ollama_names_match(r["model"], but))]


BUNDLE = ("str", True, "the bundle's id")
TABLE = [
    Op("claim", "control", {"host": HOST, "port": PORT, "model": MODEL, "gb": ("any", True, "its size in GB"),
                            "bundle": BUNDLE, "window": ("int", False, "the window it is held at"),
                            "priority": ("str", False, "high, normal or low"),
                            "keep_alive": ("any", False, "how long Ollama keeps it (-1)"),
                            "lease_s": ("any", False, "the claim's lease in s (renewed by its holder)"),
                            "hours": ("str", False, "the hours it is held, HH:MM-HH:MM on this host's clock")},
       p_claim, a_claim,
       help="reserve a model for a bundle: nothing else evicts it, every load counts it"),
    Op("renew", "control", {"host": HOST, "port": PORT, "bundle": BUNDLE, "lease_s": ("any", False, "the lease (s)")},
       p_renew, a_renew, help="renew the lease of a bundle's claims (the holder's heartbeat)"),
    Op("release", "control", {"host": HOST, "port": PORT, "bundle": BUNDLE}, p_release, a_release,
       help="release what a bundle holds"),
]
