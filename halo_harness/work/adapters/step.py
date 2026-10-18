"""halo_harness.work.adapters.step -- a flow step as a unit (Halo 3.1.2.0
R1). The run folder is `~/.halo/flows/runs/<run-id>/` (flows/state.py):
`flow.json` holds the step list and each step's state, `steps/<n>.json`
the record (its output, cost, rounds), `steps/<n>.gate.json` /
`<n>.answer.json` a human gate (flows/gates.py). This adapter reads a step
across those files as a `Unit`, writes a unit back onto its flow.json row
and `steps/<n>.json`, and reads the step's gate.

Unit mapping: id = the step id; owner = its `uses` (the lineup, org or
tool it runs through); claims none; needs = the `$.<step>` refs of its
inputs/set (`take: output`); gives = its output (`kind: output`); after =
the steps it reads; gate = `required` for a `confirm` step; attempts =
`rounds`; refs = run ids from refs if any; extra = kind, uses, output,
rounds, instructions.
"""

from __future__ import annotations

from pathlib import Path

from halo_harness.flows import gates
from halo_harness.flows import state as FS
from halo_harness.work import handoff as H
from halo_harness.work import unit as U
from halo_harness.work.ledger import line

KIND = "step"
_EXTRA = ("kind", "uses", "output", "rounds", "instructions")


def new_record(sid, kind, started: float, old: dict) -> dict:
    """The record a step (re)starts with in steps/<n>.json (flows/run.py); a killed attempt's cost, rounds and
    redo instructions carry over."""
    record = {"id": sid, "kind": kind, "started": started, "finished": None,
              "cost_usd": float(old.get("cost_usd") or 0.0) if old else 0.0, "output": None,
              "error": None, "rounds": int(old.get("rounds") or 0) if old else 0}
    for keep in ("instructions",):
        if old.get(keep):
            record[keep] = old[keep]
    return record


def _spec_steps(run_dir) -> list:
    """The flow's steps: the spec's (the full step dicts) when present, else flow.json's own step list."""
    flow = FS.read_flow(run_dir)
    return list((flow.get("spec") or {}).get("steps") or flow.get("steps") or [])


def _refs(step: dict) -> list:
    """The step ids this step's inputs/set read (`$.<step>.<path>`), once each."""
    import re
    out = []
    for value in list((step.get("inputs") or {}).values()) + list((step.get("set") or {}).values()):
        m = re.match(r"\$\.([A-Za-z0-9_-]+)", str(value))
        if m and m.group(1) not in out:
            out.append(m.group(1))
    return out


def to_unit(step: dict, idx: int, rec: dict, run_dir, run_id: str = "") -> U.Unit:
    sid = str(step.get("id"))
    kind = str(step.get("kind") or "")
    state = next((s.get("state") for s in FS.read_flow(run_dir).get("steps") or [] if s.get("id") == sid), "pending")
    gate = gates.open_gate(run_dir) or {}
    g_here = gate if gate.get("step") == sid else {}
    c = rec.get("cost_usd")
    return U.Unit.from_native(
        KIND, sid, str(state or "pending"), title=sid, run_id=run_id, owner=str(step.get("uses") or ""),
        needs=[H.need(r, "output") for r in _refs(step)], gives=[H.give(sid, "output", f"steps/{idx}.json")],
        after=_refs(step), base=None,
        gate=U.gate("required" if kind == "confirm" else "none", g_here.get("id"), int(g_here.get("round") or 0),
                    _answer(g_here)),
        cost_usd=float(c or 0.0), started=rec.get("started"), ended=rec.get("finished"),
        attempts=int(rec.get("rounds") or 0), error=str(rec.get("error") or ""),
        refs={k: v for k, v in (rec.get("output") or {}).items() if k.endswith("run") or k == "prompt_id"}
        if isinstance(rec.get("output"), dict) else {},
        extra={"kind": kind, "uses": step.get("uses"), "output": rec.get("output"), "rounds": int(rec.get("rounds") or 0),
               "instructions": list(rec.get("instructions") or [])},
        source={"step": dict(step), "idx": idx, "rec": dict(rec), "state": state})


def _answer(gate: dict):
    a = gate.get("answer") if isinstance(gate.get("answer"), dict) else None
    return a


def units(run_dir) -> list:
    run = Path(run_dir).name
    return [to_unit(s, i + 1, FS.read_step(run_dir, i + 1), run_dir, run) for i, s in enumerate(_spec_steps(run_dir))]


def unit(run_dir, uid):
    for i, s in enumerate(_spec_steps(run_dir)):
        if str(s.get("id")) == str(uid):
            return to_unit(s, i + 1, FS.read_step(run_dir, i + 1), run_dir, Path(run_dir).name)
    return None


def write(run_dir, u: U.Unit) -> None:
    idx = int((u.source or {}).get("idx") or 0)
    rec = dict((u.source or {}).get("rec") or {})
    extra = u.extra or {}
    rec.update(id=u.id, kind=extra.get("kind"), started=u.started, finished=u.ended, cost_usd=round(float(u.cost_usd or 0.0), 6),
               error=u.error or None, output=extra.get("output"), rounds=int(u.attempts))
    if extra.get("instructions"):
        rec["instructions"] = list(extra["instructions"])
    if idx:
        FS.write_step(run_dir, idx, rec)
    data = FS.read_flow(run_dir)
    for row in data.get("steps") or []:
        if row.get("id") == u.id:
            row["state"] = u.native
    from halo_harness.orchestra import jsonl
    jsonl.write_json(Path(run_dir) / "flow.json", data)


def set_native(run_dir, uid, word: str, text: str = "") -> None:
    FS.Flow(run_dir).set(str(uid), word, text)


def read_gate(run_dir, uid) -> dict:
    u = unit(run_dir, uid)
    return u.gate if u is not None else U.gate("none")


def answer_gate(run_dir, uid, action: str, text: str = "") -> "tuple[bool, str]":
    return gates.write_answer(run_dir, str(uid), action, text)


_KIND = {"state": "state", "step": "note", "gate": "gate", "post": "note", "metric": "note", "report": "note",
         "note": "note"}


def ledger_lines(run_dir) -> list:
    run = Path(run_dir).name
    out = []
    for e in FS.read_events(run_dir):
        kind = _KIND.get(str(e.get("kind")), "note")
        out.append(line(e, kind, run, unit=e.get("step"), by=""))
    return out
