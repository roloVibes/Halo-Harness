"""halo_harness.remote.receipts -- the receipts ladder of what Studio sends a live session (Halo 3.3.11.0 R1;
the local half of the ladder adopted from Concord MCP, plans/ROADMAP.md).

Every prompt, steer and answer Studio sends gets an id and a ladder, kept in `<session folder>/receipts.jsonl`
(`~/.halo/sessions/<project>/<session id>/receipts.jsonl`, beside the session's tool-results and sub-agents):

    sent       the Studio server stored it, before the socket call; a retry with the same `client_id` returns
               this row and sends nothing (one turn, never two)
    delivered  the session's handle took the text (remote/handle.py)
    read       the message is in the model's input: the loop wrote the user node the request is derived from and
               that node carries the receipt id (agent/loop.py through remote/receipt_seams.py); the transcript is
               the evidence, never a timer
    replied    the turn that read it ended (`turn_done`)
    failed     with a reason: `expired` (a sent or delivered row older than TTL_S, applied lazily when a send or a
               read touches the file), `busy` (the session was busy and the send said `when_busy: refuse`),
               `held` (a second `queue` while one turn is already held)

`delivered -> sent` when the session ends with the row unread (`requeue_unread`, at the handle's detach). The file
is append-only: every change is a new full row and the last row per id wins. This class is its one writer; a
lock per file keeps a process's writes whole, and each row is one short appended line.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import threading
import time
from pathlib import Path
from typing import Callable, Optional

TTL_S = 24 * 3600
KINDS = ("prompt", "steer", "answer")
LADDER = ("sent", "delivered", "read", "replied")
STATES = LADDER + ("failed",)
FILE = "receipts.jsonl"
_locks: dict = {}
_guard = threading.Lock()


def _lock_for(path: Path) -> threading.Lock:
    with _guard:
        return _locks.setdefault(str(path), threading.Lock())


def text_sha(text: str) -> str:
    return hashlib.sha256(str(text or "").encode("utf-8", "replace")).hexdigest()


def session_folder(sid: str, cwd=None) -> Optional[Path]:
    """The session's folder from Studio's side: the log's own (`sessions/*/<sid>.jsonl`), else the registry
    entry's project (`cwd`); None for an id that is not a session id."""
    from halo_harness.config.paths import bridge_home, project_slug
    from halo_harness.safe_id import is_safe_session_id
    if not is_safe_session_id(sid):
        return None
    root = bridge_home() / "sessions"
    hits = sorted(root.glob(f"*/{sid}.jsonl")) if root.is_dir() else []
    if hits:
        return hits[0].parent / sid
    return root / project_slug(cwd) / sid if cwd else None


def allowed(cur: str, new: str) -> bool:
    """A move up the ladder; `failed` from anything not finished; `sent` again only from `delivered` (requeue)."""
    if cur == new or cur in ("replied", "failed") or new not in STATES:
        return False
    if new == "failed":
        return True
    if new == "sent":
        return cur == "delivered"
    return LADDER.index(new) > LADDER.index(cur)


class Receipts:
    def __init__(self, folder, *, clock: Callable[[], float] = time.time, ttl_s: float = TTL_S) -> None:
        self.folder = Path(folder)
        self.path = self.folder / FILE
        self.clock = clock
        self.ttl_s = ttl_s
        self._lock = _lock_for(self.path)

    # ---- the file -------------------------------------------------------------------------------------------------
    def rows(self) -> list:
        """Every row in file order (a line that does not parse is skipped)."""
        out = []
        try:
            with open(self.path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    try:
                        row = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(row, dict) and row.get("id"):
                        out.append(row)
        except OSError:
            pass
        return out

    def _fold(self) -> dict:
        """{id: last row} in first-seen order; each row carries `sent_at`, the time of its id's first row."""
        out: dict = {}
        for row in self.rows():
            first = out.get(row["id"])
            out[row["id"]] = {**row, "sent_at": (first or row).get("sent_at") or (first or row).get("at")}
        return out

    def _append(self, row: dict) -> dict:
        from halo_harness.privateio import private_mkdir, private_opener
        private_mkdir(self.folder)
        with open(self.path, "a", encoding="utf-8", opener=private_opener) as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return row

    def _expire(self, folded: dict) -> list:
        now, out = self.clock(), []
        for rid, row in folded.items():
            if row.get("state") in ("sent", "delivered") and now - float(row.get("sent_at") or now) > self.ttl_s:
                folded[rid] = self._append({**row, "state": "failed", "reason": "expired", "at": now})
                out.append(folded[rid])
        return out

    # ---- the ladder -----------------------------------------------------------------------------------------------
    def touch(self) -> list:
        """The lazy TTL: every sent or delivered row older than `ttl_s` becomes failed(expired); returns those."""
        with self._lock:
            return self._expire(self._fold())

    def read_all(self) -> list:
        """The last row of every id (the TTL applied first), in the order they were first sent."""
        with self._lock:
            folded = self._fold()
            self._expire(folded)
            return list(folded.values())

    def get(self, rid: str) -> Optional[dict]:
        return next((r for r in self.read_all() if r.get("id") == rid), None)

    def record(self, kind: str, text: str, *, client_id: str = "", via: str = "studio") -> "tuple[dict, bool]":
        """`sent`: a new row, or (with a `client_id` already stored) that stored row and True."""
        with self._lock:
            folded = self._fold()
            self._expire(folded)
            if client_id:
                for row in folded.values():
                    if row.get("client_id") == client_id:
                        return row, True
            now = self.clock()
            row = {"id": "r_" + secrets.token_hex(8), "client_id": client_id or "", "kind": kind if kind in KINDS else "prompt",
                   "sha256": text_sha(text), "at": now, "sent_at": now, "state": "sent", "via": via}
            return self._append(row), False

    def advance(self, rid: str, state: str, *, reason: str = "", turn: Optional[int] = None, **extra) -> Optional[dict]:
        """Move `rid` to `state` when the ladder allows it; the new row, or None (unknown id, or not a move)."""
        if not rid:
            return None
        with self._lock:
            folded = self._fold()
            cur = folded.get(rid)
            if cur is None or not allowed(str(cur.get("state")), state):
                return None
            row = {**cur, "state": state, "at": self.clock(), **extra}
            row.pop("reason", None)
            if reason:
                row["reason"] = reason
            if turn is not None:
                row["turn"] = int(turn)
            return self._append(row)

    def requeue_unread(self, reason: str = "the session ended before the model read it") -> list:
        """At session end: every delivered row back to sent (the sender sees it was never read)."""
        with self._lock:
            folded = self._fold()
            out = []
            for row in folded.values():
                if row.get("state") == "delivered":
                    out.append(self._append({**row, "state": "sent", "reason": reason, "at": self.clock()}))
            return out

    def replied_up_to(self, turn: int) -> list:
        """`turn_done`: every row read in a turn up to `turn`, and every delivered answer, is replied."""
        with self._lock:
            folded = self._fold()
            out = []
            for row in folded.values():
                read = row.get("state") == "read" and int(row.get("turn") or 0) <= int(turn)
                answered = row.get("state") == "delivered" and row.get("kind") == "answer"
                if read or answered:
                    out.append(self._append({**row, "state": "replied", "at": self.clock(), "turn": int(turn)}))
            return out
