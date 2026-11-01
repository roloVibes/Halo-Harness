"""halo_harness.ollama_steward.chat_log -- the steward's chat is the steward's own session log (Halo 3.3.7.0 R5;
`<state>/ollama/steward-chat.jsonl`; ollama_steward/chat.py writes it, Studio's Steward page and `halo ollama steward
chat` read it).

    Row = {id, at, role (user | steward | tool | button | bigger), text, model?, cost?, seconds?, tool?, args?,
           ok?, action?, usage?}
        user     a question;  steward  an answer (its model, its cost: "local, 4 s" or "$0.0012");
        tool     one tool the model asked for and what it answered;  button  an action waiting for its one button
                 (retire, add, bench, battery: {verb, label, route, body, cli});  bigger  an answer from the session's
                 main model ("ask a bigger model")
    append(state_dir, row) -> row      read(state_dir, limit=100) -> [row], oldest first
    turns(state_dir, n=4) -> the last n question / answer pairs, for the next question's context
Nothing here calls a model.
"""

from __future__ import annotations

import itertools
import json
import os
import time
from pathlib import Path

FILE = "steward-chat.jsonl"
_SEQ = itertools.count(1)


def path(state_dir) -> Path:
    from halo_harness.ollama_steward.ledger import ledger_dir
    return ledger_dir(state_dir) / FILE


def append(state_dir, row: dict) -> dict:
    from halo_harness.filelock import file_lock
    out = {"id": row.get("id") or f"sc-{int(time.time() * 1000)}-{os.getpid()}-{next(_SEQ)}",
           "at": round(time.time(), 3), **{k: v for k, v in row.items() if k != "id"}}
    p = path(state_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    with file_lock(p, timeout=2.0):
        with open(p, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(out, ensure_ascii=False, default=str) + "\n")
    return out


def read(state_dir, limit: int = 100) -> list:
    try:
        with open(path(state_dir), "r", encoding="utf-8", errors="replace") as f:
            raw = f.readlines()
    except OSError:
        return []
    out = []
    for line in raw[-max(1, int(limit)):]:
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if isinstance(r, dict) and r.get("role"):
            out.append(r)
    return out


def turns(state_dir, n: int = 4) -> list:
    """[(question, answer)] of the last n turns that were answered."""
    rows = read(state_dir, limit=200)
    pairs, q = [], None
    for r in rows:
        if r["role"] == "user":
            q = r.get("text") or ""
        elif r["role"] in ("steward", "bigger") and q is not None:
            pairs.append((q, r.get("text") or ""))
            q = None
    return pairs[-n:]
