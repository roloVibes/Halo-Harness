"""halo_harness.work.adapters.part -- a fleet mission's part as a unit (Halo
3.1.2.0 R1). The run folder is the mission folder
`<missions root>/<id>/` (fleet/mission_store.py), which holds
`mission.json` (the part states), `plan.json` (the parts), `claims.json`
and `parts/<n>/result.json`. This adapter reads a part across those files
as a `Unit` and writes its state back onto `mission.json`.

Unit mapping: id = the part id; owner = the harness it ran on; claims =
the part's `claims` (mode `path`); needs = `depends_on` (each `take` the
part's own); gives = `outputs` + its handback; after = `depends_on`; base;
attempts = `refused`; gate none; refs = session, command, branch, head,
harness; extra = kind, harness_name, outputs, take, reason, pinned,
depends_on, files. A mission's gate is its plan's approval, not a part's.
"""

from __future__ import annotations

import time
from pathlib import Path

from halo_harness.fleet import mission_store as S
from halo_harness.orchestra import jsonl
from halo_harness.work import handoff as H
from halo_harness.work import unit as U
from halo_harness.work.ledger import line

KIND = "part"
_EXTRA = ("kind", "harness_name", "outputs", "take", "reason", "pinned", "depends_on", "files")


def new_state(part: dict) -> dict:
    """The state a part starts with in mission.json `parts.<id>` (fleet/mission.py new_part_state)."""
    return {"state": "pending", "harness": part.get("harness"), "harness_name": part.get("harness_name"),
            "session_id": None, "command_id": None, "started": None, "ended": None, "cost_usd": 0.0, "error": None,
            "branch": None, "files": [], "refused": 0, "base": None}


def update_state(run_dir, pid: str, fields: dict) -> dict:
    """The engine's part move (fleet/mission_run.py): `fields` merged into the part's state, the doc stamped;
    a new `state` goes through `Unit.move` (3.1.2.0 R2: IllegalMove for an edge the machine does not have)."""
    def apply(doc: dict) -> None:
        st = doc["parts"].setdefault(pid, {})
        if "state" in fields:
            U.move_word(KIND, pid, st.get("state") or "pending", fields["state"], str(doc.get("id") or ""))
        st.update(fields)
    return S.update_at(run_dir, apply)


def _plan(run_dir) -> dict:
    return jsonl.read_json(Path(run_dir) / "plan.json", {}) or {}


def _parts(run_dir) -> list:
    return list(_plan(run_dir).get("parts") or [])


def _doc(run_dir) -> dict:
    return S.load_at(run_dir) or {}


def to_unit(part: dict, state: dict, run_id: str = "") -> U.Unit:
    take = part.get("take") or "outputs"
    gives = [H.give(o, "output", o) for o in part.get("outputs") or []]
    gives.append(H.give("hand-back", "handback", f"parts/{part['id']}/handback.md"))
    base = state.get("base") or part.get("base")
    return U.Unit.from_native(
        KIND, part["id"], str(state.get("state") or "pending"), title=str(part.get("title") or ""), run_id=run_id,
        owner=str(state.get("harness_name") or part.get("harness_name") or state.get("harness") or ""),
        claims=U.claims(part.get("claims"), "path"),
        needs=[H.need(d, take) for d in part.get("depends_on") or []], gives=gives,
        after=list(part.get("depends_on") or []), base=base if base else None, gate=U.gate("none"),
        cost_usd=float(state.get("cost_usd") or 0.0), started=state.get("started"), ended=state.get("ended"),
        attempts=int(state.get("refused") or 0), error=str(state.get("error") or ""),
        refs={"session": state.get("session_id"), "command": state.get("command_id"), "branch": state.get("branch"),
              "head": state.get("head"), "harness": state.get("harness") or part.get("harness")},
        extra={"kind": part.get("kind"), "harness_name": state.get("harness_name") or part.get("harness_name"),
               "outputs": list(part.get("outputs") or []), "take": take, "reason": part.get("reason"),
               "pinned": bool(part.get("pinned")), "depends_on": list(part.get("depends_on") or []),
               "files": list(state.get("files") or [])},
        source={"part": dict(part), "state": dict(state)})


def units(run_dir) -> list:
    doc, run = _doc(run_dir), Path(run_dir).name
    states = doc.get("parts") or {}
    return [to_unit(p, states.get(p["id"]) or {}, run) for p in _parts(run_dir)]


def unit(run_dir, uid):
    doc = _doc(run_dir)
    part = next((p for p in _parts(run_dir) if str(p["id"]) == str(uid)), None)
    if part is None:
        return None
    return to_unit(part, (doc.get("parts") or {}).get(str(uid)) or {}, Path(run_dir).name)


def _state_fields(unit: U.Unit) -> dict:
    refs = unit.refs or {}
    extra = unit.extra or {}
    return {"state": unit.native, "harness": refs.get("harness"), "harness_name": extra.get("harness_name"),
            "session_id": refs.get("session"), "command_id": refs.get("command"), "cost_usd": unit.cost_usd,
            "started": unit.started, "ended": unit.ended, "error": unit.error or None, "branch": refs.get("branch"),
            "head": refs.get("head"), "files": list(extra.get("files") or []), "refused": int(unit.attempts),
            "base": unit.base}


def write(run_dir, u: U.Unit) -> None:
    src_state = (u.source or {}).get("state") or {}
    fields = _state_fields(u)
    if all(src_state.get(k) == v for k, v in fields.items() if k in src_state or v not in (None, "", [], 0, 0.0)):
        return  # nothing about the part changed: leave mission.json as it is

    def apply(doc: dict) -> None:
        st = doc.setdefault("parts", {}).setdefault(str(u.id), {})
        for k, v in fields.items():
            if k in st or v not in (None, "", [], 0, 0.0):
                st[k] = v
    S.update_at(run_dir, apply)


def set_native(run_dir, uid, word: str, text: str = "") -> None:
    def apply(doc: dict) -> None:
        st = doc.setdefault("parts", {}).setdefault(str(uid), {})
        U.move_word(KIND, uid, st.get("state") or "pending", word, str(doc.get("id") or ""))
        st["state"] = word
    S.update_at(run_dir, apply)
    log_path = Path(run_dir) / "log.jsonl"
    with jsonl.locked(log_path):
        jsonl.append_line(log_path, {"ts": round(time.time(), 3), "kind": "part", "part": str(uid), "state": word})


def read_gate(run_dir, uid) -> dict:
    return U.gate("none")


_KIND = {"part": "state", "claim_refused": "claim", "planned": "note", "running": "note", "merged": "change",
         "dispatch": "note", "file_put": "note"}


def ledger_lines(run_dir) -> list:
    run = Path(run_dir).name
    out = []
    for e in jsonl.read_lines(Path(run_dir) / "log.jsonl"):
        native = str(e.get("kind") or "")
        kind = _KIND.get(native, "note")
        text = e.get("text") or (f"part {e.get('part')} {e.get('state')}" if native == "part" else
                                 f"part {e.get('part')} could not write {e.get('file')}" if native == "claim_refused"
                                 else native)
        out.append(line({"ts": e.get("ts"), "text": text}, kind, run, unit=e.get("part"),
                        by=e.get("harness") or e.get("by") or "", key=e.get("file"), native=native,
                        data={k: v for k, v in e.items() if k not in ("ts", "kind")}))
    return out
