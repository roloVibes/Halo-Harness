"""halo_harness.ollama_steward.notes -- Halo 3.3.4.0 R4: where the steward's
words go.

Every `say` of the steward's job (job.py) is a `note` line in
`<state>/ollama/steward.jsonl`, beside R3's apply / proposal / undo /
rollback lines:

    {id, at, kind: "note", stage: "finding" | "change" | "note" | "idle",
     say (one line: the TUI status line's text), lines (the whole note),
     cost ("local, free" | "<in> in / <out> out tokens, $x" | None),
     attention (true: an `error` finding or a change; raises the fleet
     attention signal), model, data {finding | change | findings, ...}, where}

A `note` stage line is the agent's plain-language note (agent.py); the other
stages are the rules' and the profiles' own lines. `latest()` is what the TUI,
the attention row and a member's "steward on <hub>" read. A member keeps the
hub's latest note in `<state>/ollama/hub-note.json` (fleet/ollama_share.py
carries it in the answer to the member's POST /fleet/v1/ollama).
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

STAGES = ("finding", "change", "note", "idle")
HUB_NOTE = "hub-note.json"
SHARE_S = 24 * 3600.0  # a hub hands on a note at most this old


def append(state_dir, stage: str, say: str, *, lines: Optional[list] = None, cost: Optional[str] = None,
           attention: bool = False, model: Optional[str] = None, data: Optional[dict] = None,
           where: Optional[str] = None, now: Optional[float] = None) -> dict:
    """One `note` line in steward.jsonl; returns it as written."""
    from halo_harness.ollama_steward.steward import _append
    now = time.time() if now is None else now
    return _append(state_dir, {"_now": now, "id": f"n-{int(now * 1000)}-{stage}", "kind": "note", "stage": stage,
                               "say": str(say)[:400], "lines": [str(x)[:400] for x in (lines or [say])][:8],
                               "cost": cost, "attention": bool(attention), "model": model, "data": data or {},
                               "where": where})


def read(state_dir, *, since_s: Optional[float] = None, stage: Optional[str] = None,
         now: Optional[float] = None) -> list:
    """The note lines, oldest first."""
    from halo_harness.ollama_steward.ledger import parse_at
    from halo_harness.ollama_steward.steward import read_journal
    now = time.time() if now is None else now
    out = []
    for row in read_journal(state_dir):
        if row.get("kind") != "note" or (stage and row.get("stage") != stage):
            continue
        if since_s is not None and now - (parse_at(row.get("at")) or 0) > since_s:
            continue
        out.append(row)
    return out


def latest(state_dir, *, stages=("note", "change"), since_s: Optional[float] = None,
           now: Optional[float] = None) -> Optional[dict]:
    """The newest note line of one of `stages` (the agent's note or a change), or None."""
    rows = [r for r in read(state_dir, since_s=since_s, now=now) if r.get("stage") in stages]
    return rows[-1] if rows else None


def first_line(note: Optional[dict]) -> str:
    if not note:
        return ""
    lines = note.get("lines") or [note.get("say") or ""]
    return str(lines[0] if lines else note.get("say") or "")


# ---- the hub's note on a member ------------------------------------------------------------

def share_payload(home, hub_name: str, *, now: Optional[float] = None) -> Optional[dict]:
    """What the hub hands a member: its newest note or change of the last day."""
    try:
        note = latest(home, since_s=SHARE_S, now=now)
    except Exception:  # the profiles' answer never fails over a note
        note = None
    if not note:
        return None
    return {"hub": hub_name, "id": note.get("id"), "at": note.get("at"), "line": first_line(note),
            "attention": bool(note.get("attention"))}


def hub_note_path(state_dir) -> Path:
    from halo_harness.ollama_steward.ledger import ledger_dir
    return ledger_dir(state_dir) / HUB_NOTE


def hub_note(state_dir) -> Optional[dict]:
    try:
        data = json.loads(hub_note_path(state_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and data.get("line") else None


def take_hub_note(state_dir, payload) -> bool:
    """A member keeps the hub's note (True when it is a new one)."""
    if not isinstance(payload, dict) or not payload.get("line") or not payload.get("id"):
        return False
    mine = hub_note(state_dir) or {}
    if mine.get("id") == payload.get("id"):
        return False
    keep = {k: payload.get(k) for k in ("hub", "id", "at", "line", "attention")}
    keep["line"] = str(keep["line"])[:400]
    try:
        p = hub_note_path(state_dir)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(keep), encoding="utf-8")
    except OSError:
        return False
    return True


def member_line(note: Optional[dict]) -> str:
    """The line a member's TUI shows for the hub's note."""
    return f"steward on {note.get('hub') or 'the hub'}: {note.get('line')}" if note and note.get("line") else ""
