"""halo_harness.host.refresh_pool -- the off-hours refresh re-benches the pool (Halo 3.3.8.0 R4; docs/HOST.md "The
off-hours refresh"; host/refresh.py runs the plan, host/refresh_plan.py lists this row with the models).

    row(home, *, now=None, settings_=None) -> the plan's pool row | None
        when this machine runs the pool and its speed card is missing (unverified), was measured with other members or
        another split (drifted), or is older than host.refresh.max_age_days (older): {host: "pool", model, why, says,
        battery: False, bench: True, minutes, seconds, age, pool: True}
    members_idle(home, *, now=None, idle_min=20) -> {ok, line, members [{name, line}]}
        every member idle `idle_min`: no call through the pool in that time, and each member's card quiet -- a paired
        member through its halo host's `GET idle`, this machine through ollama_steward/idle.idle_since
    run(home, host, row, *, runners=None, clock=time.time, why="the window") -> the end row (refresh.jsonl)
        the pool's quick bench (local_pool/bench.py: the -c alone); a call through the pool while it runs stops it
        (`stopped`); the card is stamped "verified <date> by the host"
SEAMS["idle"]: fn(member placed row) -> {busy, idle_s} (the tests'). Nothing loads here: the pool already runs.
"""

from __future__ import annotations

import math
import time
from typing import Callable, Optional

SEAMS: dict = {}


class Stopped(Exception):
    pass


def row(home, *, now: Optional[float] = None, settings_: Optional[dict] = None) -> Optional[dict]:
    from halo_harness.host.refresh_plan import settings
    from halo_harness.local_pool import bench, catalog as C, launch, speed
    r = launch.run(home)
    if not r or not launch.alive(r):
        return None
    s, now = settings_ or settings(home), (time.time() if now is None else now)
    model = C.get(r.get("model") or "") or {"name": r.get("model")}
    card = speed.card_for(model, home)
    stale = speed.stale(card, r)
    age = (now - float(card["at"])) / 86400 if card and isinstance(card.get("at"), (int, float)) else None
    if card is None:
        why, says = "unverified", "no pool speed card yet"
    elif stale:
        why, says = "drifted", stale
    elif age is not None and age > s["max_age_days"]:
        why, says = "older", f"benched {int(age)} days ago (host.refresh.max_age_days {s['max_age_days']})"
    else:
        return None
    est = bench.estimate(r, quick=True, state_dir=home)
    return {"host": "pool", "model": r["model"], "why": why, "says": says, "battery": False, "bench": True,
            "minutes": max(1, math.ceil(est["seconds"] / 60)), "seconds": est["seconds"],
            "age": float((card or {}).get("at") or 0), "pool": True}


def _member_idle(home, p: dict, now: float) -> dict:
    if "idle" in SEAMS:
        return SEAMS["idle"](p)
    if p.get("kind") == "paired":
        from halo_harness.local_pool.hosts import client
        c, _k, line = client({"name": p["member"], "host": p["host"], "rpc_port": p.get("rpc_port")}, home)
        if c is None:
            return {"busy": f"its halo host does not answer ({line or 'not paired'})", "idle_s": None}
        try:
            rows = c.get("idle").get("hosts") or []
        except Exception as e:
            return {"busy": f"its halo host did not answer GET idle ({type(e).__name__})", "idle_s": None}
        busy = next((x.get("busy") for x in rows if x.get("busy")), "")
        idle = [x.get("idle_s") for x in rows if isinstance(x.get("idle_s"), (int, float))]
        return {"busy": busy, "idle_s": min(idle) if idle else None}
    from halo_harness.local_sched.facts import host_named
    from halo_harness.ollama_steward.idle import idle_since
    h = host_named(None)
    return idle_since(home, h, now=now) if h is not None else {"busy": "", "idle_s": None}


def members_idle(home, *, now: Optional[float] = None, idle_min: int = 20) -> dict:
    from halo_harness.local_pool import launch
    from halo_harness.ollama_steward.ledger import read_calls
    now = time.time() if now is None else now
    r = launch.run(home)
    if not r or not launch.alive(r):
        return {"ok": False, "line": "the pool is not running here: nothing to re-bench", "members": []}
    calls = read_calls(home, since=idle_min * 60.0, host="pool")
    if calls:
        return {"ok": False, "members": [], "line": f"the pool answered a call within {idle_min} min: it waits"}
    rows, ok = [], True
    for p in r.get("placed") or []:
        got = _member_idle(home, p, now)
        quiet = not got.get("busy") and (got.get("idle_s") is None or got["idle_s"] >= idle_min * 60)
        ok = ok and quiet
        rows.append({"name": p["member"], "line": f"{p['member']}: " + (
            "idle" if quiet else f"busy -- {got['busy']}" if got.get("busy") else
            f"idle {int((got.get('idle_s') or 0) // 60)} of {idle_min} min")})
    return {"ok": ok, "members": rows, "line": ("every member idle " if ok else "a member is busy: ") +
            "; ".join(x["line"] for x in rows)}


def run(home, host, row: dict, *, runners: Optional[dict] = None, clock: Callable[[], float] = time.time,
        why: str = "the window") -> dict:
    from halo_harness.host.refresh import write
    from halo_harness.local_pool import bench, catalog as C, speed
    from halo_harness.ollama_steward.ledger import read_calls
    from halo_harness.providers.local_bench_runs import save
    t0, model = clock(), row["model"]
    write(home, {"at": t0, "kind": "start", "host": "pool", "model": model, "why": row.get("why"), "by": why,
                 "pool": True})
    stopped = ""

    def check(_line=None):
        nonlocal stopped
        hit = read_calls(home, since=max(1.0, clock() - t0 + 1.0), host="pool")
        if hit:
            stopped = f"a call arrived through the pool ({hit[-1].get('model') or 'a model'}): stopped"
            raise Stopped(stopped)
    run_bench = (runners or {}).get("pool_bench") or (lambda **kw: bench.bench(**kw))
    try:
        got = run_bench(quick=True, state_dir=home, on_line=check)
    except Stopped:
        got = {"ok": False}
    ok, stamped = bool(got.get("ok")), []
    if ok:
        card = speed.card_for(C.get(model) or {"name": model}, home)
        if card is not None:
            save(home, {**card, "verified_by": "the host", "refreshed_at": time.time()})
            stamped = ["speed card"]
    word = speed.figures(C.get(model), home)["word"] if ok and C.get(model) else ""
    end = {"at": clock(), "kind": "end", "host": "pool", "model": model, "why": row.get("why"), "did": ["bench"] if ok
           else [], "ok": ok, "stopped": stopped, "stamped": stamped, "took_s": round(clock() - t0, 1), "pool": True,
           "line": (f"the pool ({model}): {stopped}" if stopped else
                    f"the pool ({model}): bench in {int(clock() - t0)} s, its speed card verified by the host -- {word}"
                    if ok else f"the pool ({model}): the bench did not run ({got.get('say') or 'no answer'})")}
    write(home, end)
    return end


def status_line(home, plan_: dict, s: dict, now: Optional[float] = None) -> str:
    """`halo host refresh status`'s pool line: when the pool is re-benched, or why not."""
    from halo_harness.host.refresh_plan import start_words
    from halo_harness.local_pool import catalog as C, launch, speed
    r = next((x for x in (plan_ or {}).get("rows") or [] if x.get("pool")), None)
    if r is not None:
        return (f"the pool: re-bench {r['model']} (~{r['seconds']} s, {r['why']}: {r['says']}) "
                f"{start_words(s['window'], now)} once every member has been idle {s['idle_min']} min")
    run_ = launch.run(home)
    if not run_ or not launch.alive(run_):
        return "the pool: not running here (nothing to re-bench)"
    model = C.get(run_.get("model") or "")
    return "the pool: its speed card is fresh" + (f" ({speed.figures(model, home, run_)['word']})" if model else "")
