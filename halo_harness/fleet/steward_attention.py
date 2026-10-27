"""halo_harness.fleet.steward_attention -- the Ollama steward's newest note
as a row of the Fleet attention queue (Halo 3.3.4.0 R4; fleet/attention.py
builds the queue, studio/fleet_answer.py routes the keys).

    ollama_steward   a note of the last WITHIN_S whose findings carry severity
                     `error`, or any change (`attention: true` in steward.jsonl,
                     ollama_steward/notes.py)      a set aside | o open Ollama

One row, the newest such note: `what` is its first line, `detail` the rest
(and the cost of the model's call); setting it aside hides that note's row,
a newer one raises a new row. On a member the hub's note is its own
(`hub-note.json`): it shows only when it says `attention`.
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
    from halo_harness.fleet.attention import _row
    from halo_harness.ollama_steward import notes
    from halo_harness.remote.bridge_cards import one_line
    out = []
    marked = [r for r in notes.read(home, since_s=WITHIN_S, now=now) if r.get("attention")
              and r.get("stage") in ("note", "change", "finding")]
    if marked:
        n = marked[-1]
        rest = list((n.get("lines") or [])[1:])
        out.append(_row(KIND, str(n.get("id")), local, None, "", one_line(notes.first_line(n), 240),
                        one_line(" ".join(rest), 240), seen, now, note=n.get("id"), stage=n.get("stage")))
    hub = notes.hub_note(home)
    if hub and hub.get("attention"):
        from halo_harness.ollama_steward.ledger import parse_at
        if now - (parse_at(hub.get("at")) or 0) < WITHIN_S:
            out.append(_row(KIND, f"hub:{hub.get('id')}", local, None, "", one_line(notes.member_line(hub), 240),
                            "", seen, now, note=hub.get("id"), hub=hub.get("hub")))
    return out


def open_target(row: dict) -> dict:
    t = row.get("target") or {}
    return {"section": "fleet", "panel": "ollama", "note": t.get("note"), "hub": t.get("hub")}


def latest_attention(home, now: float = None) -> "dict | None":
    """The newest note that raises the signal (a test and R5's panel read it)."""
    got = rows(home, {"id": None, "name": "this harness", "local": True}, {}, now or time.time())
    return got[0] if got else None
