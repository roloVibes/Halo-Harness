"""halo_harness.work.adapters.lane -- an Orchestra lane as a unit (Halo 3.1.2.0 R1).

The one owner of `<run>/lanes/<n>.json`'s shape (docs/ORCHESTRA.md): the
record a new lane starts with (`new_record`), every read and write of it
(`read`, `write_record`, `update`, `store_written`, `set_state`,
`send_back`), the lane as a `Unit` and back, and the run's
`events.jsonl` as ledger lines. orchestra/lanes.py's `Lane` is the handle
the engine holds; it calls these. Every change is a read-modify-write
under the file's lock, so the runner and a worker's own OrchestraRelease
never lose each other's fields.

Unit mapping: id = the lane number; owner = the bio (else the holder);
claims = the job's keys (mode `unit`); needs = `handoff.needs`; gives =
`gave`; after, base; attempts = `pieces_returned`; gate = the merge and
quality gate (`required`, round = the pieces sent back); refs = sessions,
branch, worktree, head, holder; extra = job, order, written, reply,
history, handoff, bio, model, denied, and (3.1.2.0 R2, orchestra/stale.py)
stale and rebased.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

from halo_harness.orchestra import jsonl
from halo_harness.work import states as ST
from halo_harness.work import unit as U
from halo_harness.work.adapters import overlay
from halo_harness.work.ledger import line

KIND = "lane"
LANE_STATES = tuple(w for w in ST.words(KIND) if w)
_EXTRA = ("job", "order", "written", "reply", "history", "handoff", "bio", "model", "denied", "stale", "rebased")


def lane_path(run_dir, n) -> Path:
    return Path(run_dir) / "lanes" / f"{int(n)}.json"


def new_record(job, *, n: int, branch: str, worktree, started: float) -> dict:
    """The record a new lane's file starts with."""
    return {"lane": int(n), "job": job.id, "title": job.title, "claims": list(job.claims), "order": job.order,
            "state": "", "holder": "", "branch": branch, "worktree": str(worktree), "head": "",
            "cost_usd": 0.0, "started": started, "ended": None, "pieces_returned": 0, "session_ids": [],
            "written": {}, "error": "", "reply": "", "history": [],
            "handoff": dict(getattr(job, "handoff", None) or {}), "after": list(getattr(job, "upstreams", []) or []),
            "base": "", "gave": [], "bio": str(getattr(job, "bio", "") or ""), "model": str(getattr(job, "model", "") or ""),
            "denied": []}


def read(path) -> dict:
    data = jsonl.read_json(path, {})
    return data if isinstance(data, dict) else {}


def write_record(path, data: dict) -> None:
    jsonl.write_json(path, data)


def update(path, **fields) -> dict:
    with jsonl.locked(path):
        data = read(path)
        data.update(fields)
        write_record(path, data)
    return data


def store_written(path, key: str, text: str) -> None:
    with jsonl.locked(path):
        data = read(path)
        written = dict(data.get("written") or {})
        written[key] = text
        data["written"] = written
        write_record(path, data)


def set_state(run_dir, n: int, state: str, text: str = "", *, clock: Callable = time.time) -> None:
    """Move lane `n` to the engine word `state`: one history row and one `state` line in the run log.
    The move goes through `Unit.move` (3.1.2.0 R2): an edge the machine does not have raises IllegalMove."""
    from halo_harness.orchestra import events as run_events
    if state not in LANE_STATES:
        raise ValueError(f"lane state must be one of {', '.join(LANE_STATES)}, got {state!r}")
    path = lane_path(run_dir, n)
    ts = clock()
    with jsonl.locked(path):
        data = read(path)
        U.move_word(KIND, n, str(data.get("state") or ""), state, Path(run_dir).name)
        history = list(data.get("history") or [])
        history.append({"state": state, "ts": round(ts, 3), "elapsed_s": jsonl.elapsed(run_dir, ts), "text": text})
        data.update(state=state, history=history)
        write_record(path, data)
    run_events.log(run_dir, "state", f"lane {n} {state}" + (f": {text}" if text else ""),
                   lane=n, step=f"worker-{n}", lane_state=state)


def send_back(run_dir, n: int, text_of: Callable[[int], str], *, clock: Callable = time.time) -> int:
    """The gate sent lane `n`'s piece back: one more attempt, the lane `waiting` (text_of(attempts) its line)."""
    path = lane_path(run_dir, n)
    returned = int(read(path).get("pieces_returned") or 0) + 1
    update(path, pieces_returned=returned)
    set_state(run_dir, n, "waiting", text_of(returned), clock=clock)
    return returned


# ---- the unit ------------------------------------------------------------------------------

def to_unit(rec: dict, run_id: str = "") -> U.Unit:
    n = rec.get("lane")
    base = rec.get("base")
    return U.Unit.from_native(
        KIND, n, str(rec.get("state") or ""), title=str(rec.get("title") or ""), run_id=run_id,
        owner=str(rec.get("bio") or rec.get("holder") or ""), claims=U.claims(rec.get("claims"), "unit"),
        needs=list((rec.get("handoff") or {}).get("needs") or []) if isinstance(rec.get("handoff"), dict) else [],
        gives=list(rec.get("gave") or []), after=list(rec.get("after") or []), base=base if base else None,
        gate=U.gate("required", None, int(rec.get("pieces_returned") or 0)),
        cost_usd=float(rec.get("cost_usd") or 0.0), started=rec.get("started"), ended=rec.get("ended"),
        attempts=int(rec.get("pieces_returned") or 0), error=str(rec.get("error") or ""),
        refs={"sessions": list(rec.get("session_ids") or []), "branch": rec.get("branch") or "",
              "worktree": rec.get("worktree") or "", "head": rec.get("head") or "", "holder": rec.get("holder") or ""},
        extra={k: rec[k] for k in _EXTRA if k in rec}, source=dict(rec))


def to_record(unit: U.Unit) -> dict:
    src = unit.source or {}
    refs = unit.refs or {}
    fields = {"lane": int(unit.id), "title": unit.title, "claims": list(unit.claims.get("keys") or []),
              "state": unit.native, "holder": refs.get("holder", ""), "branch": refs.get("branch", ""),
              "worktree": refs.get("worktree", ""), "head": refs.get("head", ""), "cost_usd": unit.cost_usd,
              "started": unit.started, "ended": unit.ended, "pieces_returned": int(unit.attempts),
              "session_ids": list(refs.get("sessions") or []), "error": unit.error, "after": list(unit.after),
              "base": unit.base if unit.base else src.get("base", ""), "gave": list(unit.gives)}
    fields.update({k: v for k, v in (unit.extra or {}).items() if k in _EXTRA})
    return overlay(src, fields)


def units(run_dir) -> list:
    folder = Path(run_dir) / "lanes"
    try:
        names = sorted(int(p.stem) for p in folder.glob("*.json") if p.stem.isdigit())
    except OSError:
        return []
    out = []
    for n in names:
        rec = jsonl.read_json(lane_path(run_dir, n), None)
        if isinstance(rec, dict):
            out.append(to_unit(rec, Path(run_dir).name))
    return out


def unit(run_dir, uid):
    rec = jsonl.read_json(lane_path(run_dir, uid), None)
    return to_unit(rec, Path(run_dir).name) if isinstance(rec, dict) else None


def write(run_dir, u: U.Unit) -> None:
    path = lane_path(run_dir, u.id)
    with jsonl.locked(path):
        write_record(path, to_record(u))
    u.source = to_record(u)


# ---- the ledger ----------------------------------------------------------------------------

_KIND = {"state": "state", "claim": "claim", "merge": "change", "gate": "gate", "report": "note", "note": "note"}


def ledger_lines(run_dir) -> list:
    run = Path(run_dir).name
    out = []
    for e in jsonl.read_lines(Path(run_dir) / "events.jsonl"):
        data = e.get("data") or {}
        kind = _KIND.get(str(e.get("kind")), "note")
        uid = e.get("lane") if e.get("lane") is not None else data.get("lane_n")
        out.append(line(e, kind, run, unit=uid, by=data.get("holder") or "",
                        key=data.get("key") if kind == "claim" else None))
    return out


def set_native(run_dir, uid, word: str, text: str = "") -> None:
    set_state(run_dir, int(uid), word, text)


def read_gate(run_dir, uid) -> dict:
    u = unit(run_dir, uid)
    return u.gate if u is not None else U.gate("none")
