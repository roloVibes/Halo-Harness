"""halo_harness.live.steward_attention -- the Ollama steward's newest note
as a row of the attention queue (Halo 3.3.4.0 R4; live/attention.py
builds the queue, studio/live_answer.py routes the keys).

    ollama_steward   a note of the last WITHIN_S whose findings carry severity
                     `error`, or any change (`attention: true` in steward.jsonl,
                     ollama_steward/notes.py)      a set aside | o open Local -> Hosts

One row, the newest such note: `what` is its first line, `detail` the rest
(and the cost of the model's call); setting it aside hides that note's row,
a newer one raises a new row.
"""

from __future__ import annotations

import time

WITHIN_S = 24 * 3600.0
KIND = "ollama_steward"


def rows(home, local: dict, seen: dict, now: float) -> list:
    try:
        return _rows(home, local, seen, now)
    except Exception:  # the queue never fails over the steward's file
        return []


def _rows(home, local: dict, seen: dict, now: float) -> list:
    from halo_harness.live.attention import _row
    from halo_harness.ollama_steward import notes
    from halo_harness.remote.cards import one_line
    out = []
    marked = [r for r in notes.read(home, since_s=WITHIN_S, now=now) if r.get("attention")
              and r.get("stage") in ("note", "change", "finding")]
    if marked:
        n = marked[-1]
        rest = list((n.get("lines") or [])[1:])
        out.append(_row(KIND, str(n.get("id")), local, None, "", one_line(notes.first_line(n), 240),
                        one_line(" ".join(rest), 240), seen, now, note=n.get("id"), stage=n.get("stage"),
                        host=n.get("where") or (n.get("data") or {}).get("host") or ""))
    return out


def open_target(row: dict) -> dict:
    t = row.get("target") or {}
    # 3.3.16.0 R2: the shell opens Local -> Hosts on `host`
    return {"section": "live", "panel": "ollama", "note": t.get("note"), "host": t.get("host") or ""}


def latest_attention(home, now: float = None) -> "dict | None":
    """The newest note that raises the signal (a test and R5's panel read it)."""
    got = rows(home, {"id": None, "name": "this harness", "local": True}, {}, now or time.time())
    return got[0] if got else None
