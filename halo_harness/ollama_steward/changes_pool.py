"""halo_harness.ollama_steward.changes_pool -- the pool's warm and stop as changes under the steward contract (Halo
3.3.8.0 R3; docs/POOL.md "Warm and stop"; ollama_steward/changes.py holds the rows).

    warm(name, *, allow_wifi=None, window=None, keep=False, state_dir=None, home=None, by="user", scope="keep")
        -> {ok, lines, preflight, change}     one pool change per COOLDOWN_S (10 min): a second one inside it is one
        line with the minutes left; the preflight first (local_pool/preflight.py), then local_pool/launch.start; the
        change row: key `pool|<model>`, field `pool.state`, before `stopped`, after `running`, with the baseline (the
        pool's own speed card, 3.3.8.0 R4; else the single-node bench card that could hold the model; else none) in
        its `why`
    stop(*, state_dir=None, home=None, by="user", why="") -> {ok, lines, change}   launch.stop + its row
    judge(state_dir=None, *, home=None, calls=JUDGE_CALLS) -> {verdict, line, stopped, ...}
        the auto-revert: the first JUDGE_CALLS calls through the pool (ledger lines named `pool`) are worse than the
        baseline -- their median tok/s under the single-node card's, or half of them failed -- and the pool stops (a
        revert of the warm, said with both numbers); no baseline: the failures alone judge, said
    baseline(model) -> {tok_s, host, at} | None      cooldown(state_dir, now=None) -> "" | the line
    current(row) / put(row, value, note)   changes.revert's hooks for a `pool.state` row: the live state, and a revert
        of a warm stops the pool (a revert of a stop says how to warm it again: nothing relaunches on its own)
Nothing here runs a model; a warm starts processes Halo launches and stops them again.
"""

from __future__ import annotations

import statistics
import time
from typing import Optional

COOLDOWN_S = 600.0
JUDGE_CALLS = 3
FIELD = "pool.state"
OWN_SLACK = 0.8  # against the pool's own bench card: a fifth slower than it measured is worse


def _state(state_dir=None):
    from halo_harness.local_pool.claims import _state as s
    return s(state_dir)


def _rows(state_dir) -> list:
    from halo_harness.ollama_steward.changes import read
    return sorted((r for r in read(state_dir) if r.get("field") == FIELD), key=lambda r: str(r.get("at")))


def cooldown(state_dir=None, now: Optional[float] = None) -> str:
    from halo_harness.ollama_steward.ledger import parse_at
    rows = _rows(_state(state_dir))
    if not rows:
        return ""
    at = parse_at(rows[-1].get("at")) or 0.0
    left = COOLDOWN_S - ((time.time() if now is None else now) - at)
    if left <= 0:
        return ""
    return (f"one pool change per {COOLDOWN_S / 60:.0f} min: the last ({rows[-1].get('after')} {rows[-1].get('model')}) "
            f"was {(COOLDOWN_S - left) / 60:.0f} min ago -- the next in {left / 60:.0f} min")


def baseline(model: dict, state_dir=None) -> Optional[dict]:
    """3.3.8.0 R4: the pool's own speed card first (its slowest window, OWN_SLACK below it is worse), else a single
    node's card of the same model."""
    from halo_harness.local_pool.speed import card_for, floor
    own = card_for(model, _state(state_dir))
    if floor(own):
        return {"tok_s": floor(own), "host": "pool", "model": own.get("model"), "at": own.get("at"), "own": True}
    from halo_harness.providers.local_bench_runs import all_cards, mirror
    words = [w.lower() for w in model.get("match") or ()]
    for c in all_cards(_state(state_dir)):
        name = str(c.get("model") or "").lower()
        if str(c.get("host") or "").lower() != "pool" and any(w in name for w in words):
            m = mirror(c)
            if isinstance(m.get("tok_s"), (int, float)):
                return {"tok_s": float(m["tok_s"]), "host": c.get("host"), "model": c.get("model"), "at": c.get("at")}
    return None


def held_for(name: str, state_dir=None) -> str:
    """3.3.8.0 R4: '' unless a bundle holds the pool for another model (local_sched/reserve_parts: a row on host
    `pool`) -- then the one line naming it and its priority; a Warm of the model it holds goes ahead."""
    from halo_harness.local_pool.catalog import get
    from halo_harness.local_sched.reserve import claims
    want = (get(name) or {}).get("name") or name
    for c in claims(None, state_dir=_state(state_dir)):
        if str(c.get("host") or "").lower() == "pool" and c.get("model") and c["model"] != want:
            return (f"{c['bundle']} holds the pool for {c['model']} (priority {c.get('priority') or 'normal'}): a Warm "
                    f"of {want} waits until halo pack off {c['bundle']}")
    return ""


def _record(state, model: str, before: str, after: str, by: str, scope: str, why: str) -> dict:
    from halo_harness.ollama_steward.changes import record
    return record(state, by=by, key=f"pool|{model}", field=FIELD, before=before, after=after, scope=scope, why=why)


def warm(name: str, *, allow_wifi=None, window=None, keep: bool = False, state_dir=None, home=None, by: str = "user",
         scope: str = "keep") -> dict:
    from halo_harness.local_pool import catalog as C, launch
    from halo_harness.local_pool.preflight import preflight
    state = _state(state_dir)
    wait = cooldown(state) or held_for(name, state)
    if wait:
        return {"ok": False, "lines": [wait], "cooldown": not held_for(name, state)}
    pf = preflight(name, allow_wifi=allow_wifi, window=window, state_dir=state_dir, home=home)
    if pf is None:
        return {"ok": False, "lines": [f"{name!r} is not in the pool catalog ({', '.join(C.names())})"]}
    if not pf["ok"]:
        return {"ok": False, "lines": [pf["line"]], "preflight": pf}
    got = launch.start(pf, state_dir=state_dir, home=home, by=by)
    if not got["ok"]:
        return {**got, "preflight": pf}
    b = baseline(C.get(pf["model"]), state)
    why = (f"the pool warmed {pf['display']} ({pf['cache']} KV, -c {pf['ctx']:,}); baseline: " +
           (f"{b['tok_s']:.1f} tok/s on {b['host']} ({b['model']}, its bench card)" if b else
            "none (no single-node bench card holds this model here: the first calls' failures judge it)"))
    ch = _record(state, pf["model"], "stopped", "running", by, scope, why)
    r = launch.run(state)
    launch._save({**r, "change_id": ch["id"], "baseline": b, "keep": bool(keep)}, state)
    if not keep:
        _stop_at_exit(state, home)
    return {**got, "lines": got["lines"] + [f"[{ch['id']}] pool.state stopped -> running ({why})"], "preflight": pf,
            "change": ch}


def stop(*, state_dir=None, home=None, by: str = "user", why: str = "") -> dict:
    from halo_harness.local_pool import launch
    state = _state(state_dir)
    r = launch.run(state)
    got = launch.stop(state_dir=state_dir, home=home, why=why)
    if not r:
        return got
    ch = _record(state, r.get("model") or "?", "running", "stopped", by, "keep", why or "stopped by hand")
    return {**got, "lines": got["lines"] + [f"[{ch['id']}] pool.state running -> stopped"], "change": ch}


def _tok_s(line: dict) -> Optional[float]:
    v = line.get("eval_tok_s")
    if isinstance(v, (int, float)) and v > 0:
        return float(v)
    n, ms = line.get("eval_count"), line.get("total_ms")
    return float(n) / (float(ms) / 1000.0) if isinstance(n, int) and isinstance(ms, (int, float)) and ms > 0 else None


def judge(state_dir=None, *, home=None, calls: int = JUDGE_CALLS) -> dict:
    from halo_harness.local_pool import launch
    from halo_harness.ollama_steward.ledger import parse_at, read_calls
    state = _state(state_dir)
    r = launch.run(state)
    if not r or r.get("judged"):
        return {"verdict": "none", "line": "" if not r else r.get("judged_line", "")}
    since = float(r.get("started") or 0)
    lines = [x for x in read_calls(state, host="pool") if (parse_at(x.get("at")) or 0) >= since][:calls]
    if len(lines) < calls:
        return {"verdict": "waiting", "line": f"the pool's first {calls} calls decide the warm ({len(lines)} so far)"}
    bad = sum(1 for x in lines if x.get("status") != 200)
    from halo_harness.ollama_steward.verify_timing import rates  # 3.3.8.0 R4: the reply rate the pool's log printed
    speeds = rates(state, "pool", r.get("model"), since=since, first=calls) or [
        s for s in (_tok_s(x) for x in lines if x.get("status") == 200) if s]
    med = statistics.median(speeds) if speeds else None
    b = r.get("baseline")
    limit = float(b["tok_s"]) * (OWN_SLACK if b.get("own") else 1.0) if b else None
    worse = bad * 2 >= calls or (limit is not None and med is not None and med < limit)
    said = (f"the pool's first {calls} calls: {bad} failed, median {med:.1f} tok/s" if med is not None else
            f"the pool's first {calls} calls: {bad} failed") + (
        (f" against its own bench card's {float(b['tok_s']):.1f} tok/s" if b.get("own") else
         f" against {float(b['tok_s']):.1f} tok/s on {b['host']}") if b else " (no single-node baseline)")
    if not worse:
        launch._save({**r, "judged": True, "judged_line": f"{said}: kept"}, state)
        return {"verdict": "kept", "line": f"{said}: kept"}
    got = stop(state_dir=state_dir, home=home, by="steward", why=f"{said}: worse, so the warm is reverted")
    return {"verdict": "reverted", "line": f"{said}: worse -- the pool stopped", "stopped": got}


def _stop_at_exit(state, home) -> None:
    import atexit
    from pathlib import Path

    def bye():
        try:
            from halo_harness.config.paths import bridge_home
            if Path(bridge_home()).resolve() == Path(state).resolve():
                from halo_harness.local_pool import launch
                r = launch.run(state)
                if r and not r.get("keep"):
                    stop(state_dir=state, home=home, by="halo", why="the halo that warmed it exited")
        except Exception:
            pass
    atexit.register(bye)


def current(row: dict):
    from halo_harness.local_pool import launch
    r = launch.run(_state())
    return "running" if r and launch.alive(r) and r.get("model") == row.get("model") else "stopped"


def put(row: dict, value, note: str) -> None:
    if value == "stopped" and current(row) == "running":
        stop(by="ledger", why=note)
