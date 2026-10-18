"""halo_harness.work.adapters.stage -- a team stage as a unit (Halo 3.1.2.0
R1). The run folder is `<repo>/.halo/team/<run-id>/` (team/board.py):
`board.json` holds the stage rows, `stages/<id>/` the gate, answer and
result. This adapter reads a stage row as a `Unit`, writes a unit back
onto its board row, and reads the stage's gate (team/stages.py).

Unit mapping: id = the stage id; owner = the lead; claims = the blocks it
writes (mode `block`); needs = the blocks it reads (`take: block`); gives
= the blocks it writes (`kind: block`); after = a `stage_done:<stage>`
trigger; gate = the stage's `gate:` and its open gate's round; attempts =
the round; refs = the stage's refs.json; extra = kind, trigger, members,
lead, harness, summary, gate_answer and (3.1.2.0 R2) members_state, remote,
budget. A stage run on a fleet member whose part is `asked` is `waiting`.
"""

from __future__ import annotations

from pathlib import Path

from halo_harness.team import board as BD
from halo_harness.team import stages as ST
from halo_harness.work import handoff as H
from halo_harness.work import unit as U
from halo_harness.work.ledger import line

KIND = "stage"
_EXTRA = ("kind", "trigger", "members", "lead", "harness", "summary", "gate_answer", "members_state", "remote", "budget")


def new_row(stage: dict, members: list, lead: str, harness) -> dict:
    """The row a stage starts with in board.json `stages` (team/board.py stage_row)."""
    return {"id": stage["id"], "kind": stage["kind"], "state": "pending", "trigger": stage["trigger"],
            "members": list(members), "lead": lead, "gate": stage["gate"], "harness": harness,
            "started": None, "ended": None, "cost_usd": 0.0, "summary": "", "error": "", "round": 0,
            "waiting": "", "gate_answer": None}


def _spec(run_dir) -> dict:
    """The team file this run belongs to (its blocks name what a stage reads and writes), or {}."""
    from halo_harness.orchestra import jsonl
    from halo_harness.team import spec as S
    root = (jsonl.read_json(Path(run_dir) / "run.json", {}) or {}).get("root")
    try:
        return (S.load_team(Path(root)) or {}) if root else {}
    except Exception:
        return {}


def _reads_writes(team: dict, sid: str) -> "tuple[list, list]":
    stage = next((s for s in (team.get("workflow") or {}).get("stages") or [] if s.get("id") == sid), {})
    return list(stage.get("reads") or []), list(stage.get("writes") or [])


def _after(trigger) -> list:
    from halo_harness.team.spec import parse_trigger
    kind, target = parse_trigger(str(trigger or "manual"))
    return [target] if kind == "stage_done" and target else []


def to_unit(row: dict, run_dir, run_id: str = "", team: dict = None) -> U.Unit:
    team = team if team is not None else _spec(run_dir)
    sid = str(row.get("id"))
    reads, writes = _reads_writes(team, sid)
    gate = ST.read_gate(run_dir, sid) or {}
    u = U.Unit.from_native(
        KIND, sid, str(row.get("state") or "pending"), title=sid, run_id=run_id, owner=str(row.get("lead") or ""),
        claims=U.claims(writes, "block"), needs=[H.need(b, "block") for b in reads],
        gives=[H.give(b, "block", b) for b in writes], after=_after(row.get("trigger")), base=None,
        gate=U.gate(row.get("gate") or "none", gate.get("id"), int(gate.get("round") or row.get("round") or 0),
                    row.get("gate_answer")),
        acceptance=(gate.get("acceptance") if isinstance(gate.get("acceptance"), dict) else None),
        cost_usd=float(row.get("cost_usd") or 0.0), started=row.get("started"), ended=row.get("ended"),
        attempts=int(row.get("round") or 0), error=str(row.get("error") or ""),
        refs=BD.read_stage_file(run_dir, sid, "refs.json", {}) or {},
        extra={k: row.get(k) for k in _EXTRA if k in row}, source=dict(row))
    remote = row.get("remote") if isinstance(row.get("remote"), dict) else {}
    if u.state == "running" and remote.get("part_state") == "asked":  # 3.1.2.0 R2: a member's owner has the card
        u.state = "waiting"
    return u


def units(run_dir) -> list:
    team, run = _spec(run_dir), Path(run_dir).name
    return [to_unit(r, run_dir, run, team) for r in BD.read_board(run_dir).get("stages") or []]


def unit(run_dir, uid):
    row = BD.row(BD.read_board(run_dir), str(uid))
    return to_unit(row, run_dir, Path(run_dir).name) if row else None


def write(run_dir, u: U.Unit) -> None:
    refs = u.refs or {}
    if refs:
        BD.write_stage_file(run_dir, u.id, "refs.json", refs)
    fields = {"cost_usd": u.cost_usd, "started": u.started, "ended": u.ended, "round": int(u.attempts),
              "error": u.error, "gate_answer": (u.extra or {}).get("gate_answer")}
    fields.update({k: v for k, v in (u.extra or {}).items() if k in ("members", "lead", "harness", "summary")})

    def apply(board: dict) -> None:
        row = BD.row(board, u.id)
        if row is not None:
            row["state"] = u.native
            row.update({k: v for k, v in fields.items() if k in row or v not in (None, "", [], 0, 0.0)})
    BD.update_board(run_dir, apply)


def set_native(run_dir, uid, word: str, text: str = "") -> None:
    BD.set_stage(run_dir, str(uid), word, text)


def read_gate(run_dir, uid) -> dict:
    row = BD.row(BD.read_board(run_dir), str(uid)) or {}
    gate = ST.read_gate(run_dir, str(uid)) or {}
    return U.gate(row.get("gate") or "none", gate.get("id"), int(gate.get("round") or row.get("round") or 0),
                  row.get("gate_answer"))


def answer_gate(run_dir, uid, action: str, text: str = "") -> "tuple[bool, str]":
    return ST.write_answer(run_dir, str(uid), action, text)


_KIND = {"state": "state", "claim": "claim", "change": "change", "gate": "gate", "trigger": "note", "report": "note",
         "note": "note"}


def ledger_lines(run_dir) -> list:
    run = Path(run_dir).name
    out = []
    for e in BD.read_events(run_dir):
        data = e.get("data") or {}
        kind = _KIND.get(str(e.get("kind")), "note")
        out.append(line(e, kind, run, unit=e.get("stage"), by=data.get("holder") or data.get("member") or "",
                        key=data.get("key")))
    return out
