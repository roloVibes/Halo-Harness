"""halo_harness.orchestra.coach_record -- what the coach applied, and the runs
it read (Halo 3.1.3.0 R1). Both live in the state dir's `coach/` folder:

    ~/.halo/coach/applied.jsonl   one line per Apply and per Undo:
        {"op": "apply", "apply_id": "a-<10 hex>", "id": "<suggestion id>", "run": "<run id>",
         "run_dir": "<folder>", "kind": "orchestra|flow|mission|team", "target": "bio|lineup|plan",
         "name", "field", "value", "file": "<path written>", "existed": true, "before": "<text>",
         "after": "<text>", "ts": 1760800000.0}
        {"op": "undo", "apply_id": "a-...", "file": "<path>", "ts": ...}
    ~/.halo/coach/runs.json       {"<run folder>": {run, kind, n, top, ts}}: the runs the coach read
                                  (the Fleet digest's coach lines)

The Undo rule: the file must still hold the apply's `after` text exactly;
then the `before` text is written back (or the file removed when the apply
created it). Anything else is refused with the reason, and nothing is written.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Optional

from halo_harness.orchestra import jsonl

APPLIED, RUNS = "applied.jsonl", "runs.json"


def folder(state_dir=None) -> Path:
    if state_dir is None:
        from halo_harness.config.paths import bridge_home
        state_dir = bridge_home()
    return Path(state_dir) / "coach"


def new_id() -> str:
    return "a-" + uuid.uuid4().hex[:10]


def append(row: dict, state_dir=None) -> dict:
    path = folder(state_dir) / APPLIED
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    return row


def applies(state_dir=None) -> list:
    """Every apply, oldest first, each with `undone` (the undo's ts, or None)."""
    rows = jsonl.read_lines(folder(state_dir) / APPLIED)
    undone = {r.get("apply_id"): r.get("ts") for r in rows if r.get("op") == "undo"}
    return [dict(r, undone=undone.get(r.get("apply_id"))) for r in rows if r.get("op") == "apply"]


def states(run_dir, state_dir=None) -> dict:
    """{suggestion id: {state: applied|undone, apply_id, file, ts}} for one run folder (its newest apply wins)."""
    key, out = str(Path(run_dir).resolve()), {}
    for r in applies(state_dir):
        if r.get("run_dir") == key:
            out[str(r.get("id"))] = {"state": "undone" if r["undone"] else "applied", "apply_id": r["apply_id"],
                                     "file": r.get("file"), "ts": r["undone"] or r.get("ts")}
    return out


def find(apply_id: Optional[str], state_dir=None) -> Optional[dict]:
    rows = applies(state_dir)
    if apply_id:
        return next((r for r in rows if r.get("apply_id") == apply_id), None)
    return next((r for r in reversed(rows) if not r["undone"]), None)


def text_of(path) -> Optional[str]:
    """The file's exact text (its line endings kept), None when it cannot be read."""
    try:
        return Path(path).read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def write_exact(path, text: str) -> None:
    """`text` byte for byte (no newline translation), atomically: temp file beside it, then os.replace."""
    import tempfile
    path = Path(path)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(text.encode("utf-8"))
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def undo(apply_id: Optional[str] = None, state_dir=None) -> tuple:
    """(ok, message, the apply row). The last apply not undone when `apply_id` is None."""
    rec = find(apply_id, state_dir)
    if rec is None:
        return False, (f"no apply {apply_id!r} in the coach's record" if apply_id else
                       "nothing to undo: every apply in the coach's record is undone"), None
    if rec["undone"]:
        return False, f"{rec['apply_id']} is already undone", rec
    path = Path(rec["file"])
    now = text_of(path)
    if now is None:
        return False, f"{path} is gone: the coach leaves it as it is", rec
    if now != rec.get("after"):
        return False, f"{path} changed after the apply: the coach leaves it as it is (edit it by hand)", rec
    if rec.get("existed"):
        write_exact(path, rec.get("before") or "")
    else:
        os.remove(path)
    append({"op": "undo", "apply_id": rec["apply_id"], "file": str(path), "ts": round(time.time(), 3)}, state_dir)
    return True, (f"undid {rec['apply_id']}: {path} " + ("holds its text from before the apply" if rec.get("existed")
                                                        else "is removed (the apply created it)")), rec


def note_run(result: dict, run_dir, state_dir=None) -> None:
    """Keep the run's count and top card in runs.json (the Fleet digest reads it); never raises."""
    try:
        path = folder(state_dir) / RUNS
        data = jsonl.read_json(path, {}) or {}
        rows = result.get("suggestions") or []
        data[str(Path(run_dir).resolve())] = {"run": result.get("run"), "kind": result.get("kind"), "n": len(rows),
                                              "top": rows[0]["text"] if rows else "", "ts": round(time.time(), 3)}
        jsonl.write_json(path, data)
    except Exception:
        pass


def runs_since(since: float, state_dir=None) -> list:
    """[{run_dir, run, kind, n, top, ts, applied}] read since `since`, newest last."""
    data = jsonl.read_json(folder(state_dir) / RUNS, {}) or {}
    rows = applies(state_dir)
    out = []
    for key, r in data.items():
        if isinstance(r, dict) and float(r.get("ts") or 0) >= since:
            live = {x.get("id") for x in rows if x.get("run_dir") == key and not x["undone"]}
            out.append(dict(r, run_dir=key, applied=len(live)))
    return sorted(out, key=lambda r: float(r.get("ts") or 0))


def summary_line(n: int, applied: int, top: str) -> str:
    """The run reports' and the Fleet digest's one coach line."""
    head = f"coach: {n} suggestion{'s' if n != 1 else ''}, {applied} applied"
    return head + (f", top: {top[:90]}" if n and top else "")


def summary(run_dir, state_dir=None) -> str:
    """The coach line of one run folder ('' when it is not a run the coach reads)."""
    from halo_harness.orchestra.coach import cached
    try:
        result = cached(run_dir, state_dir=state_dir)
    except Exception:
        return ""
    rows = result.get("suggestions") or []
    done = sum(1 for v in states(run_dir, state_dir).values() if v["state"] == "applied")
    return summary_line(len(rows), done, rows[0]["text"] if rows else "")
