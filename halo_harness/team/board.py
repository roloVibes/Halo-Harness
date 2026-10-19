"""halo_harness.team.board -- the run ledger, `<repo>/.halo/team/<run-id>/`.

    board.json      {run, team, created, state: open | done | stopped, stop_reason,
                     runner: {pid, beat} | null, stages: [<stage row>]}
    events.jsonl    {ts, elapsed_s, kind, stage, text, data}; kinds state, claim,
                    change, gate, trigger, report, note
    stop.json       {reason, ts} (halo team stop; the runner honours it)
    stages/<id>/    refs.json (agent session ids, the orchestra run id, a
                    mission id), handback.md, result.json, gate.json,
                    answer.json, scope.json (the write guard's scope)

A stage row is `{id, kind, state, trigger, members, lead, gate, harness,
started, ended, cost_usd, summary, error, round, waiting, gate_answer}` with
state pending | ready | running | gated | done | failed | skipped. Every
board write takes the run's lock, so the runner and a second process (an
answer, a stop, the guard in an agent's session) never interleave.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Callable, Optional

from halo_harness.orchestra import jsonl
from halo_harness.team import RUNS_DIR
from halo_harness.work.states import words
from halo_harness.work.unit import move_word

STATES = words("stage")  # pending ready running gated done failed skipped (work/states.py, 3.1.2.0 R1)
EVENT_KINDS = ("state", "claim", "change", "gate", "trigger", "report", "note")
RUN_STATES = ("open", "done", "stopped")
BEAT_S = 15.0


def runs_root(root) -> Path:
    return Path(root).joinpath(*RUNS_DIR)


def new_run_id(now: Optional[float] = None) -> str:
    import secrets
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(time.time() if now is None else now))
    return f"{stamp}-{secrets.token_hex(2)}"


def stage_row(stage: dict, members: list, lead: str, harness: Optional[str]) -> dict:
    """A new board row; its shape is the stage adapter's (work/adapters/stage.py, 3.1.2.0 R1)."""
    from halo_harness.work.adapters.stage import new_row
    return new_row(stage, members, lead, harness)


def new_run(root, team: dict, rows: list) -> Path:
    base = runs_root(root)
    base.mkdir(parents=True, exist_ok=True)
    ignore = base / ".gitignore"
    if not ignore.exists():
        ignore.write_text("# Halo team run ledgers: never committed\n*\n", encoding="utf-8")
    while True:
        run_dir = base / new_run_id()
        try:
            run_dir.mkdir()
            break
        except FileExistsError:
            continue
    (run_dir / "stages").mkdir()
    (run_dir / "events.jsonl").write_text("", encoding="utf-8")
    jsonl.write_json(run_dir / "run.json", {"run_id": run_dir.name, "created": time.time(), "root": str(root)})
    jsonl.write_json(run_dir / "board.json", {"run": run_dir.name, "team": team.get("name"), "created": time.time(),
                                              "state": "open", "stop_reason": "", "runner": None, "stages": rows})
    return run_dir


def list_runs(root) -> list:
    base = runs_root(root)
    return sorted(p for p in base.iterdir() if p.is_dir() and (p / "board.json").is_file()) if base.is_dir() else []


def latest_run(root, open_only: bool = False) -> Optional[Path]:
    for run_dir in reversed(list_runs(root)):
        if not open_only or read_board(run_dir).get("state") == "open":
            return run_dir
    return None


def find_run(root, ref: Optional[str]) -> Optional[Path]:
    if not ref:
        return latest_run(root)
    hits = [p for p in list_runs(root) if p.name == ref or p.name.startswith(ref)]
    return hits[-1] if len(hits) == 1 or (hits and hits[-1].name == ref) else None


def board_path(run_dir) -> Path:
    return Path(run_dir) / "board.json"


def read_board(run_dir) -> dict:
    """board.json; a read that lands while a write replaces it (Windows: the replace holds the file for a
    moment) tries again a few times instead of answering an empty board (3.0.8.0 R2)."""
    path = board_path(run_dir)
    for attempt in range(6):
        data = jsonl.read_json(path, None)
        if isinstance(data, dict) and data:
            return data
        if not path.exists():
            break
        time.sleep(0.02 * (attempt + 1))
    return data if isinstance(data, dict) else {}


def update_board(run_dir, fn: Callable[[dict], object]) -> dict:
    with jsonl.locked(board_path(run_dir)):
        board = read_board(run_dir)
        fn(board)
        jsonl.write_json(board_path(run_dir), board)
    return board


def row(board: dict, sid: str) -> Optional[dict]:
    return next((r for r in board.get("stages") or [] if r.get("id") == sid), None)


def log(run_dir, kind: str, text: str, stage: Optional[str] = None, **data) -> dict:
    if kind not in EVENT_KINDS:
        raise ValueError(f"event kind is one of {', '.join(EVENT_KINDS)}, got {kind!r}")
    path = Path(run_dir) / "events.jsonl"
    with jsonl.locked(path):
        ts = time.time()
        entry = {"ts": round(ts, 3), "elapsed_s": jsonl.elapsed(run_dir, ts), "kind": kind, "stage": stage,
                 "text": str(text), "data": dict(data)}
        jsonl.append_line(path, entry)
    return entry


def read_events(run_dir, since: int = 0) -> list:
    return jsonl.read_lines(Path(run_dir) / "events.jsonl")[max(0, int(since)):]


def set_stage(run_dir, sid: str, state: Optional[str] = None, text: str = "", **fields) -> dict:
    """Move one stage row (and any other fields); a state move logs a `state` line."""
    if state is not None and state not in STATES:
        raise ValueError(f"stage state is one of {', '.join(STATES)}, got {state!r}")
    moved: dict = {}

    def apply(board: dict) -> None:
        r = row(board, sid)
        if r is None:
            return
        if state is not None and r.get("state") != state:
            move_word("stage", sid, r.get("state"), state, board.get("run") or "")  # 3.1.2.0 R2: through Unit.move
            moved["from"] = r.get("state")
            r["state"] = state
        r.update(fields)
    board = update_board(run_dir, apply)
    if moved:
        log(run_dir, "state", f"{sid} {state}" + (f": {text}" if text else ""), stage=sid, state=state,
            was=moved["from"], **{k: v for k, v in fields.items() if k in ("cost_usd", "summary", "error", "round")})
    return row(board, sid) or {}


def stage_dir(run_dir, sid: str) -> Path:
    d = Path(run_dir) / "stages" / sid
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_stage_file(run_dir, sid: str, name: str, data) -> Path:
    path = stage_dir(run_dir, sid) / name
    if isinstance(data, str):
        path.write_text(data, encoding="utf-8")
    else:
        jsonl.write_json(path, data)
    return path


def read_stage_file(run_dir, sid: str, name: str, default=None):
    path = Path(run_dir) / "stages" / sid / name
    if name.endswith(".json"):
        return jsonl.read_json(path, default)
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return default


def beat(run_dir, clear: bool = False) -> None:
    def apply(board: dict) -> None:
        board["runner"] = None if clear else {"pid": os.getpid(), "beat": round(time.time(), 3)}
    update_board(run_dir, apply)


def runner_live(board: dict, now: Optional[float] = None) -> bool:
    r = board.get("runner") or {}
    return bool(r) and (now or time.time()) - float(r.get("beat") or 0) < BEAT_S * 2


def stop_path(run_dir) -> Path:
    return Path(run_dir) / "stop.json"


def request_stop(run_dir, reason: str = "stopped by the user") -> None:
    jsonl.write_json(stop_path(run_dir), {"reason": reason, "ts": round(time.time(), 3)})
    log(run_dir, "note", f"stop requested: {reason}", reason=reason)


def stop_requested(run_dir) -> Optional[str]:
    data = jsonl.read_json(stop_path(run_dir), None)
    return str(data.get("reason") or "stopped by the user") if isinstance(data, dict) else None


def cost(board: dict) -> float:
    return round(sum(float(r.get("cost_usd") or 0.0) for r in board.get("stages") or []), 6)


def unit_rows(run_dir) -> list:
    """Each stage as the shared report row (work/report.py; 3.1.2.0 R1, docs/WORK.md)."""
    from halo_harness.work.report import rows
    return rows(run_dir, "stage")
