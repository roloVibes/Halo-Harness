"""halo_harness.local_sched.pivot -- one pivot as a visible step: unload the resident model, load the one a lane needs
(Halo 3.3.7.0 R3; plans/local-model-fit-brief.md D1 1).

    plan(host, frm, to, *, window=None, window_from="", labels=(None, None), state_dir=None) -> Pivot
    Pivot = {host, url, from, to, window, window_from, load_s, load_from, via ("host" | "local"), line}
    run(p, *, session=None, turn=0, sleep=time.sleep) -> a generator of events; returns {ok, took_s, waited_s, say, via}
    run_now(p, say=print, **kw) -> the same result, each line handed to `say` (the CLI's form)
    held_for(host, model) -> the seconds `model` still stays resident (config local.min_resident_s, default 60)
    mark_loaded(host, model)    the scheduler loaded it now (the residency clock starts)

The scheduler's own rules: one pivot at a time per card (a lock per host address: a second one waits and says so)
and a stated minimum residency -- a model the scheduler loaded is not unloaded before `local.min_resident_s`, so
two lanes cannot thrash one card: the pivot waits the rest and says how long. A model a halo host serves pivots
through the host's `pivot` operation (host/ops_control.py: its invariants first, one event each); a local one
through the Ollama API (providers/ollama_load: unload, then load at the window). One line before ("pivot: main
(qwen3.8:27b) -> coder (qwen3-coder:30b) on pc, ~25 s (the ledger), fits history to 32 k") and one after ("pivoted in
24 s"); the load goes on the session's loading tax (local_sched/loads.py).
"""

from __future__ import annotations

import threading
import time
from typing import Optional

from halo_harness import events

MIN_RESIDENT_S = 60.0
LOCK_WAIT_S = 600.0
_GUARD = threading.Lock()
_LOCKS: dict = {}
_SINCE: dict = {}


def min_resident_s() -> float:
    try:
        from halo_harness.theme import get_config_value
        v = get_config_value("local.min_resident_s", default=MIN_RESIDENT_S)
        return max(0.0, float(v))
    except Exception:
        return MIN_RESIDENT_S


def _url(host) -> str:
    return str(getattr(host, "url", host) or "").rstrip("/")


def _key(host, model: str) -> tuple:
    from halo_harness.ollama_steward.profiles import short_model
    return _url(host), short_model(model)


def mark_loaded(host, model: str, now: Optional[float] = None) -> None:
    _SINCE[_key(host, model)] = time.monotonic() if now is None else now


def held_for(host, model: Optional[str], now: Optional[float] = None) -> float:
    if not model:
        return 0.0
    since = _SINCE.get(_key(host, model))
    if since is None:
        return 0.0
    now = time.monotonic() if now is None else now
    return max(0.0, min_resident_s() - (now - since))


def _lock(host) -> threading.Lock:
    with _GUARD:
        return _LOCKS.setdefault(_url(host), threading.Lock())


def _client(host):
    from halo_harness.ollama_steward.host_client import _usable, for_host
    try:
        c = for_host(host)
    except Exception:
        return None
    return c if _usable(c) else None


def plan(host, frm: Optional[str], to: str, *, window: Optional[int] = None, window_from: str = "",
         labels=(None, None), state_dir=None) -> dict:
    from halo_harness.local_sched.swap_cost import load_s_for, secs
    name = str(getattr(host, "name", host) or "")
    cost = load_s_for(host, to, state_dir=state_dir, fetch=False)
    via = "host" if _client(host) is not None else "local"
    a = f"{labels[0]} ({frm})" if labels[0] and frm else (frm or "nothing")
    b = f"{labels[1]} ({to})" if labels[1] else to
    fits = f", fits history to {window // 1024} k" if isinstance(window, int) and window >= 1024 else ""
    took = f"~{secs(cost['s'])} ({cost['source']})" if cost["s"] is not None else "load time unknown"
    return {"host": name, "url": _url(host), "from": frm, "to": to, "window": window, "window_from": window_from,
            "load_s": cost["s"], "load_from": cost["source"], "via": via,
            "line": f"pivot: {a} -> {b} on {name}, {took}{fits}" + (" (through the halo host)" if via == "host" else "")}


def _through_host(host, p: dict) -> dict:
    from halo_harness.ollama_steward.host_client import HostError, _addr_port
    c = _client(host)
    if c is None:
        return {"ok": False, "say": "the halo host did not answer"}
    params = {"from": p["from"], "to": p["to"]} if p["from"] else {"model": p["to"]}
    if p.get("window"):
        params["num_ctx"] = int(p["window"])
    served = c.served_name(_addr_port(p["url"])[1])
    if served:
        params["host"] = served
    try:
        got = c.act("control", "pivot" if p["from"] else "warm", params, why="the scheduler's pivot")
    except HostError as e:
        return {"ok": False, "say": str(e)}
    if got.get("queued"):
        return {"ok": False, "say": got.get("line") or "queued for the host's owner"}
    return {"ok": bool(got.get("ok", True)), "say": got.get("say") or got.get("line") or "pivoted"}


def _local(host, p: dict) -> dict:
    from halo_harness.providers.ollama_load import load, unload
    if p["from"]:
        gone = unload(host, p["from"])
        if not gone["ok"]:
            return {"ok": False, "say": f"pivot stopped: {gone['say']}; {p['to']} was not loaded"}
    got = load(host, p["to"], num_ctx=p.get("window"))
    return {"ok": got["ok"], "say": got["say"] + ("" if got["ok"] or not p["from"] else f"; {p['from']} stays unloaded")}


def run(p: dict, *, host=None, session=None, turn: int = 0, sleep=time.sleep):
    from halo_harness.local_sched.facts import host_named
    from halo_harness.local_sched.swap_cost import secs
    host = host if host is not None else host_named(p["host"])
    if host is None:
        return {"ok": False, "took_s": 0.0, "waited_s": 0.0, "say": f"no Ollama host named {p['host']!r}", "via": None}
    yield events.turn_marker("pivot", p["line"], turn=turn, pivot={k: v for k, v in p.items() if k != "line"})
    lock, waited = _lock(host), 0.0
    start = time.monotonic()
    if not lock.acquire(blocking=False):
        yield events.turn_marker("pivot", f"pivot: {p['to']} waits -- a pivot is already running on {p['host']} "
                                          "(one at a time per card)", turn=turn)
        if not lock.acquire(timeout=LOCK_WAIT_S):
            return {"ok": False, "took_s": 0.0, "waited_s": LOCK_WAIT_S, "say": "the other pivot did not finish",
                    "via": p["via"]}
    try:
        hold = held_for(host, p["from"])
        if hold > 0:
            yield events.turn_marker("pivot", f"pivot held {secs(hold)}: {p['from']} was loaded "
                                              f"{secs(min_resident_s() - hold)} ago (local.min_resident_s "
                                              f"{min_resident_s():g})", turn=turn)
            sleep(hold)
        waited = time.monotonic() - start
        t0 = time.monotonic()
        got = _through_host(host, p) if p["via"] == "host" else _local(host, p)
        took = round(time.monotonic() - t0, 1)
        if got["ok"]:
            mark_loaded(host, p["to"])
            if p["from"]:
                _SINCE.pop(_key(host, p["from"]), None)
    finally:
        lock.release()
    if got["ok"]:
        from halo_harness.local_sched.loads import record
        record(getattr(session, "state_dir", None), session=getattr(getattr(session, "log", None), "session_id", None),
               host=p["host"], model=p["to"], seconds=took, why="pivot")
    after = f"pivoted in {secs(took)}: {got['say']}" if got["ok"] else f"pivot did not land: {got['say']}"
    yield events.turn_marker("pivot", after, turn=turn, took_s=took, ok=got["ok"])
    return {"ok": got["ok"], "took_s": took, "waited_s": round(waited, 1), "say": got["say"], "via": p["via"]}


def run_now(p: dict, say=print, **kw) -> dict:
    gen = run(p, **kw)
    while True:
        try:
            ev = next(gen)
        except StopIteration as stop:
            return stop.value
        say(ev.data.get("text", ""))
