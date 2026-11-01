"""halo_harness.host.refresh -- the off-hours refresh: the battery and the quick bench when the card is free (Halo
3.3.7.0 R4; plans/local-model-fit-brief.md G13; the plan is host/refresh_plan.py).

    tick(home, hosts, *, now=None, runners=None, start=None, clock=time.time) -> "" | what it started
        host/service.py's loop calls it (every CHECK_S): the refresh is on, inside `host.refresh.window`, nothing
        running; the plan's first model's card has been idle `host.refresh.idle_min` (ollama_steward/idle.idle_since:
        no call in the ledger, no scheduler load, nothing foreign in /api/ps, no session on it); then that one model
        runs on a thread (`start`), never two at a time
    run_one(home, host, row, *, runners=None, clock=time.time, why="the window") -> the log line
        the battery (when the plan says), then the quick bench, one model; it stops the moment a call arrives (a
        ledger call on that host since it began, a session on it, a foreign model: `interrupted`), and stamps the
        profile and the speed card "verified <date> by the host" (`verified_by`, `refreshed_at`)
    review(home, now=None) -> "" | "roster review: ..."   with nothing left to measure: the roster adviser
        (models_library/advise.py) when the roster, an Ollama version or the hosts changed; a `roster-review` line
    status(home, hosts=None, *, now=None) -> {settings, plan, line, last, running, log, pool_line (3.3.8.0 R4)}
    log(home, n=20) -> the newest lines of <state>/host/refresh.jsonl     request_now(home) / take_now(home)
`runners` {"battery": fn(host, model, *, state_dir, on_status), "bench": fn(host, model, *, state_dir, on_line)} are
the tests' seams; the defaults are providers/capability_battery.run and providers/local_bench.bench (their calls go to
Ollama's API: the model loads in Ollama, never in this process). Nothing runs during a session.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Callable, Optional

CHECK_S = 30.0
FILE, NOW_FILE = "refresh.jsonl", "refresh-now"
_STATE: dict = {"running": None, "checked": 0.0}
_LOCK = threading.Lock()


class Stopped(Exception):
    pass


def _path(home, name=FILE) -> Path:
    from halo_harness.host.state import host_dir
    return host_dir(home) / name


def write(home, row: dict) -> None:
    p = _path(home)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(row, default=str) + "\n")
    except OSError:
        pass


def log(home, n: int = 20) -> list:
    try:
        raw = _path(home).read_text(encoding="utf-8").splitlines()[-n:]
    except OSError:
        return []
    out = []
    for line in raw:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def request_now(home) -> None:
    _path(home, NOW_FILE).parent.mkdir(parents=True, exist_ok=True)
    _path(home, NOW_FILE).write_text(str(time.time()), encoding="utf-8")


def take_now(home) -> bool:
    try:
        _path(home, NOW_FILE).unlink()
        return True
    except OSError:
        return False


def interrupted(home, host, since: float, *, now: Optional[float] = None) -> str:
    """Why the refresh stops now ("" goes on): a call since it began, a session on the card, a foreign model."""
    from halo_harness.ollama_steward.idle import idle_since
    from halo_harness.ollama_steward.ledger import read_calls
    name = str(getattr(host, "name", host))
    now = time.time() if now is None else now
    calls = read_calls(home, since=max(1.0, now - since + 1.0), host=name)
    if calls:
        c = calls[-1]
        return f"a call arrived ({c.get('model') or 'a model'} from {c.get('from') or 'this machine'}): stopped"
    got = idle_since(home, host, now=now)
    return f"stopped: {got['busy']}" if got["busy"] else ""


def _runners(runners: Optional[dict]) -> dict:
    def battery(host, model, *, state_dir, on_status):
        from halo_harness.providers.capability_battery import run
        from halo_harness.studio.ollama_hosts_view import card_of
        return run(host, model, card=card_of(host), on_status=on_status, state_dir=state_dir, force=True)

    def bench(host, model, *, state_dir, on_line):
        from halo_harness.providers.local_bench import bench as run_bench
        from halo_harness.studio.ollama_hosts_view import card_of
        return run_bench(host, model, quick=True, card=card_of(host), state_dir=state_dir, on_line=on_line,
                         check_busy=False)
    return {"battery": battery, "bench": bench, **(runners or {})}


def _stamp(home, host_name: str, model: str, at: float) -> list:
    from halo_harness.providers.local_bench_runs import load, save
    from halo_harness.providers.ollama_capability import profile_for, save_profile
    done = []
    p = profile_for(home, model, host_name)
    if p and p.get("host") == host_name and float(p.get("probed_at") or 0) >= at - 1:
        save_profile(home, {**p, "verified_by": "the host", "refreshed_at": time.time()})
        done.append("profile")
    sc = load(home, host_name, model)
    if sc and float(sc.get("at") or 0) >= at - 1:
        save(home, {**sc, "verified_by": "the host", "refreshed_at": time.time()})
        done.append("speed card")
    return done


def run_one(home, host, row: dict, *, runners: Optional[dict] = None, clock: Callable[[], float] = time.time,
            why: str = "the window") -> dict:
    from halo_harness.local_sched.loads import record
    name, model, t0 = str(getattr(host, "name", host)), row["model"], clock()
    r = _runners(runners)
    record(home, session=None, host=name, model=model, seconds=0.0, why="refresh")  # idle explains its load
    write(home, {"at": t0, "kind": "start", "host": name, "model": model, "why": row.get("why"), "by": why})
    did, stopped, ok = [], "", True

    def check(_x=None):
        nonlocal stopped
        stopped = interrupted(home, host, t0, now=clock())
        if stopped:
            raise Stopped(stopped)
    try:
        if row.get("battery", True):
            got = r["battery"](host, model, state_dir=home, on_status=check)
            ok = ok and bool((got or {}).get("ok", True))
            did.append("battery")
        check()
        if row.get("bench", True):
            got = r["bench"](host, model, state_dir=home, on_line=check)
            ok = ok and bool((got or {}).get("ok", True))
            did.append("bench")
    except Stopped:
        ok = False
    stamped = _stamp(home, name, model, t0) if did else []
    end = {"at": clock(), "kind": "end", "host": name, "model": model, "why": row.get("why"), "did": did, "ok": ok,
           "stopped": stopped, "stamped": stamped, "took_s": round(clock() - t0, 1),
           "line": (f"{model} on {name}: {stopped}" if stopped else
                    f"{model} on {name}: {' + '.join(did) or 'nothing'} in {int(clock() - t0)} s"
                    + (f", {' and '.join(stamped)} verified by the host" if stamped else ""))}
    write(home, end)
    return end


def _start(fn) -> None:
    threading.Thread(target=fn, daemon=True, name="halo-host-refresh").start()


def tick(home, hosts: list, *, now: Optional[float] = None, runners: Optional[dict] = None,
         start: Optional[Callable] = None, clock: Callable[[], float] = time.time, force: bool = False) -> str:
    from halo_harness.host.refresh_plan import in_window, plan, settings
    from halo_harness.ollama_steward.idle import idle_since
    now = clock() if now is None else now
    asked = take_now(home) or force
    with _LOCK:
        if _STATE["running"] or (not asked and now - _STATE["checked"] < CHECK_S):
            return ""
        _STATE["checked"] = now
    s = settings(home)
    if not asked and (not s["enabled"] or not in_window(s["window"], now)):
        return ""
    p = plan(home, hosts, now=now, settings_=s)
    if not p["rows"]:
        return review(home, now=now)
    for row in p["rows"]:
        one, host = run_one, next((h for h in hosts if h.name == row["host"]), None)
        if row.get("pool"):  # 3.3.8.0 R4: the pool's re-bench once every member is idle (host/refresh_pool.py)
            from halo_harness.host import refresh_pool as RP
            if not RP.members_idle(home, now=now, idle_min=s["idle_min"])["ok"]:
                continue
            one, host = RP.run, "pool"
        elif host is None:
            continue
        idle = idle_since(home, host, now=now) if one is run_one else {"busy": "", "idle_s": None}
        if idle["busy"] or (idle["idle_s"] is not None and idle["idle_s"] < s["idle_min"] * 60):
            continue
        with _LOCK:
            _STATE["running"] = row

        def go(row=row, host=host, one=one):
            try:
                one(home, host, row, runners=runners, clock=clock, why="now" if asked else "the window")
            finally:
                with _LOCK:
                    _STATE["running"] = None
        (start or _start)(go)
        return f"refresh: {row['model']} on {row['host']} ({row['why']})"
    return ""


def review(home, *, now: Optional[float] = None, force: bool = False) -> str:
    """The off-hours "roster review" (Part J): the adviser, when the roster, an Ollama version or the hosts changed."""
    from halo_harness.models_library.advise import advise, due, inputs, remember
    try:
        inp = inputs(home)
        go, why = due(home, inp)
        if not (go or force):
            return ""
        got = advise(home, inp=inp)
    except Exception:
        return ""
    remember(home, got)
    write(home, {"at": time.time() if now is None else now, "kind": "roster-review", "why": why, "lines": got["lines"][:12],
                 "kinds": got["kinds"]})
    return f"roster review: {got['head']}"


def service_tick(svc) -> str:
    """The host loop's call: never with background requests off (the test flag), always on `halo host refresh now`."""
    from halo_harness.config.paths import background_net_disabled
    if background_net_disabled() and not _path(svc.home, NOW_FILE).exists():
        return ""
    return tick(svc.home, svc.view.hosts())


def status(home, hosts: Optional[list] = None, *, now: Optional[float] = None) -> dict:
    from halo_harness.host.refresh_plan import plan, settings
    if hosts is None:
        from halo_harness.host.state import served_hosts
        hosts = served_hosts()
    s = settings(home)
    p = plan(home, hosts, now=now, settings_=s)
    rows = log(home, 40)
    last = next((r for r in reversed(rows) if r.get("kind") == "end"), None)
    review = next((r for r in reversed(rows) if r.get("kind") == "roster-review"), None)
    from halo_harness.host.refresh_pool import status_line  # 3.3.8.0 R4: when the pool is re-benched
    return {"settings": s, "plan": p, "line": p["line"], "last": last, "review": review,
            "pool_line": status_line(home, p, s, now), "running": _STATE["running"], "log": rows[-10:],
            "last_line": f"last refresh: {last['line']}" if last else "last refresh: none yet"}
