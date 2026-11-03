"""halo_harness.remote.receipt_seams -- where a live session moves its receipts (Halo 3.3.11.0 R1;
remote/receipts.py holds the file and the ladder).

The session's side of the ladder, each a call of a few lines at its seam:

* `delivered` -- the handle took the text (remote/handle.py `ControllerHandle.submit`, the socket's `answer`:
  `answered`, which marks it before the card resolves so the turn that goes on can never end first);
* `read` -- the loop writes the user node a request is derived from (agent/loop.py: the turn's first user
  node from the `user_input` Command whose meta carries `receipt`, and a steer's node at the safe point that
  applies it): `take_turn` / `take_steer` hand the loop the receipt, `tag` puts its id on the node (the
  transcript is the evidence), `mark_read` moves the row with the turn and the node's `seq`;
* `replied` -- `turn_done` of the main session (the handle's event tap: `replied`);
* `delivered -> sent` -- the handle's detach (`requeue`).

A steer's receipt cannot ride on `Session.steer(text)`, so `Controller.submit`'s steer path notes it by text
(`note_steer`); a steer that reaches no safe point and is resubmitted as a fresh turn (agent/loop.py
`_resubmit_leftover_steers`) finds the same note through `take_turn`. Every call here is best-effort: a receipt
never stands in a turn's way.
"""

from __future__ import annotations

import threading
from typing import Optional

_lock = threading.Lock()


def receipts_for(session, cwd=None):
    """The session's Receipts: its log's folder (`<log dir>/<session id>`), else the project's (`cwd`)."""
    from halo_harness.remote.receipts import Receipts, session_folder
    log = getattr(session, "log", None)
    sid = str(getattr(log, "session_id", "") or "")
    folder = getattr(log, "dir", None)
    if folder is not None and sid:
        from pathlib import Path
        return Receipts(Path(folder) / sid)
    path = session_folder(sid, cwd or getattr(session, "cwd", None))
    return Receipts(path) if path is not None else None


def _advance(session, rid: str, state: str, cwd=None, **kw) -> Optional[dict]:
    if not rid:
        return None
    try:
        r = receipts_for(session, cwd)
        return r.advance(rid, state, **kw) if r is not None else None
    except Exception:
        return None


def delivered(session, rid: str, cwd=None) -> Optional[dict]:
    return _advance(session, rid, "delivered", cwd)


def failed(session, rid: str, reason: str, cwd=None) -> Optional[dict]:
    return _advance(session, rid, "failed", cwd, reason=reason)


def note_steer(session, text: str, meta: Optional[dict]) -> None:
    """Controller.submit's steer path: the steer's meta, found again by its text where it is applied."""
    if not (isinstance(meta, dict) and meta.get("receipt")):
        return
    with _lock:
        notes = getattr(session, "_receipt_steers", None)
        if notes is None:
            notes = session._receipt_steers = []
        notes.append((str(text), dict(meta)))


def _pop_note(session, *, text: str = "", rid: str = "") -> dict:
    with _lock:
        notes = getattr(session, "_receipt_steers", None) or []
        for i, (t, meta) in enumerate(notes):
            if (rid and meta.get("receipt") == rid) or (not rid and t == text):
                notes.pop(i)
                return meta
    return {}


def take_turn(session, text: str) -> dict:
    """The meta of the turn the loop starts (the `user_input` Command's, set by `Session.run`), or a resubmitted
    steer's note; {} for a turn nobody sent with a receipt."""
    meta = getattr(session, "_turn_meta", None)
    session._turn_meta = None
    meta = dict(meta) if isinstance(meta, dict) else {}
    if meta.get("receipt"):
        _pop_note(session, rid=str(meta["receipt"]))  # a steer that became this turn after all
        return meta
    return _pop_note(session, text=str(text or "")) or meta


def take_steer(session, text: str) -> dict:
    return _pop_note(session, text=str(text or ""))


def tag(meta: Optional[dict]) -> dict:
    """The keyword for `SessionLog.append_user`: `{"receipt": id}`, {} without one."""
    rid = (meta or {}).get("receipt") if isinstance(meta, dict) else None
    return {"receipt": str(rid)} if rid else {}


def mark_read(session, meta: Optional[dict], turn: int, node: Optional[dict] = None) -> Optional[dict]:
    rid = str((meta or {}).get("receipt") or "") if isinstance(meta, dict) else ""
    if not rid:
        return None
    seq = node.get("seq") if isinstance(node, dict) else None
    return _advance(session, rid, "read", turn=turn, **({"seq": seq} if seq is not None else {}))


def stamp(ev, meta: Optional[dict]):
    """The turn's `user_message` event with where it came from (`via`, `by`) and its `receipt`: the Studio feed
    draws "from Studio" and the ladder from them."""
    if isinstance(meta, dict) and meta:
        try:
            ev.data.update({k: str(meta[k]) for k in ("via", "by", "receipt") if meta.get(k)})
        except Exception:
            pass
    return ev


def replied(session, turn: int, cwd=None) -> list:
    try:
        r = receipts_for(session, cwd)
        return r.replied_up_to(turn) if r is not None else []
    except Exception:
        return []


def requeue(session, cwd=None) -> list:
    try:
        r = receipts_for(session, cwd)
        return r.requeue_unread() if r is not None else []
    except Exception:
        return []


def rows(session, cwd=None) -> list:
    """The socket's `receipts`: the ladder of every receipt of this session."""
    r = receipts_for(session, cwd)
    return r.read_all() if r is not None else []


def answered(handle, req: dict, fn):
    """The socket's `answer` with a `receipt`: delivered before the card resolves, failed when nothing waited."""
    from halo_harness.remote.base import HandleError
    rid = str(req.get("receipt") or "")
    delivered(handle.session, rid, handle.cwd)
    try:
        return fn()
    except HandleError as e:
        _advance(handle.session, rid, "failed", handle.cwd, reason=str(e)[:200])
        raise
