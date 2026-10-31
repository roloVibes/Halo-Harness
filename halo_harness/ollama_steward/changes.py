"""halo_harness.ollama_steward.changes -- Halo 3.3.6.0 R5: every Halo-side change to a local model's profile carries
a scope, and every one can be put back (plans/local-model-fit-brief.md D6 item 22: "revert-on-session-end for any
tuning Halo applies").

One line per change in `<state>/ollama/changes.jsonl`: {id, at, by (steward | ledger | user | bench | settings), host,
model, key, field (a profile field or `dialect.<name>`), before, after, scope, session_id, pid, reverted_at, why,
journal_id}. `scope`: `session` (undone when that session ends: agent/loop.py `_fire_session_end`), `until-restart`
(undone when the halo process that made it exits: atexit and the TUI's quit, `at_exit`), `keep`. A revert or a new
scope is one more line (`event: revert | scope`); `read` folds them.

    revert(state_dir, id | "all", why, *, scope=None, host=None) -> lines   "put num_ctx back to 32,768 on pc|m (why)"
    revert_scope(state_dir, "session", session_id) | (state_dir, "until-restart") -> lines ([] and nothing written when
        nothing is due); until-restart also takes the rows of a halo that is gone (a killed process)

A field changed again after this change is left as it is (the line says so); several revert newest first.
"""

from __future__ import annotations

import itertools
import json
import os
from pathlib import Path
from typing import Optional

SCOPES = ("session", "until-restart", "keep")
FILE = "changes.jsonl"
WORDS = {"session": "undone when the session ends", "until-restart": "undone when this halo exits", "keep": "kept"}
_DIRS: set = set()
_HOOKED = [False]
_SEQ = itertools.count(1)


def path(state_dir) -> Path:
    from halo_harness.ollama_steward.ledger import ledger_dir
    return ledger_dir(state_dir) / FILE


def _append(state_dir, row: dict) -> dict:
    from halo_harness.filelock import file_lock
    p = path(state_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    with file_lock(p, timeout=2.0):
        with open(p, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    return row


def _remember(state_dir) -> None:
    _DIRS.add(str(state_dir))
    if not _HOOKED[0]:
        import atexit
        atexit.register(at_exit)
        _HOOKED[0] = True


def record(state_dir, *, by: str, key: str, field: str, before, after, scope: str, why: str = "",
           session_id: Optional[str] = None, session_pid: Optional[int] = None, id: Optional[str] = None,
           journal_id: Optional[str] = None, before_by: Optional[str] = None, now: Optional[float] = None) -> dict:
    import time
    from halo_harness.ollama_steward.ledger import now_iso
    from halo_harness.ollama_steward.profiles import split_key
    scope = scope if scope in SCOPES else "keep"
    host, model = split_key(key)
    now = time.time() if now is None else now
    row = {"id": id or f"ch-{int(now)}-{os.getpid()}-{next(_SEQ)}", "at": now_iso(now), "by": by, "host": host,
           "model": model, "key": key, "field": field, "before": before, "after": after, "scope": scope,
           "session_id": session_id, "session_pid": session_pid, "pid": os.getpid(), "reverted_at": None,
           "why": str(why or "")[:300], "journal_id": journal_id, "before_by": before_by}
    _append(state_dir, row)
    if scope != "keep":
        _remember(state_dir)
    return row


def read(state_dir) -> list:
    rows: dict = {}
    try:
        with open(path(state_dir), "r", encoding="utf-8", errors="replace") as f:
            for raw in f:
                try:
                    r = json.loads(raw)
                except ValueError:
                    continue
                if not isinstance(r, dict) or not r.get("id"):
                    continue
                ev = r.get("event")
                if ev is None:
                    rows[r["id"]] = r
                elif r["id"] in rows and ev == "revert":
                    rows[r["id"]].update(reverted_at=r.get("reverted_at"), revert_why=r.get("revert_why"),
                                         revert_line=r.get("revert_line"))
                elif r["id"] in rows and ev == "scope" and r.get("scope") in SCOPES:
                    rows[r["id"]].update(scope=r["scope"], session_id=r.get("session_id", rows[r["id"]].get("session_id")))
    except OSError:
        return []
    return list(rows.values())


def in_force(state_dir, host: Optional[str] = None) -> list:
    return [r for r in read(state_dir) if not r.get("reverted_at") and (not host or str(r.get("host")).lower() == host.lower())]


def fmt(v) -> str:
    if v is None or isinstance(v, bool):
        return "unset" if v is None else "on" if v else "off"
    if isinstance(v, int):
        return f"{v:,}"
    if isinstance(v, dict):
        return ", ".join(f"{k} {fmt(x)}" for k, x in v.items())
    return str(v)


def _current(row: dict):
    from halo_harness.ollama_steward.profiles import all_profiles
    entry = all_profiles().get(row["key"]) or {}
    if str(row["field"]).startswith("dialect."):
        return (entry.get("dialect") or {}).get(row["field"].split(".", 1)[1])
    return entry.get(row["field"])


def _set(row: dict, value, note: str) -> None:
    from halo_harness.ollama_steward.profiles import set_field, split_key
    if str(row["field"]).startswith("dialect."):
        from halo_harness.providers import dialect as D
        host, model = split_key(row["key"])
        name = row["field"].split(".", 1)[1]
        if value is None:
            D.reset(host, model, name)
        else:
            D.set_fields(host, model, {name: value}, by=row.get("before_by") or "ledger")
        return
    by = row.get("before_by") if row.get("before_by") in ("steward", "user", "hub") else "steward"
    set_field(row["key"], row["field"], value, by=by, note=note[:300])


def _put_back(state_dir, row: dict, why: str, now: Optional[float]) -> str:
    from halo_harness.ollama_steward.ledger import now_iso
    cur = _current(row)
    where = f"{row['field']} on {row['key']}"
    if cur != row.get("after"):
        line = f"left {where} as it is ({fmt(cur)}): it was changed again after this change ({why})"
    else:
        before = row.get("before")
        line = (f"put {row['field']} back to {fmt(before)} on {row['key']} ({why})" if before is not None
                else f"took {where} away: it had none before ({why})")
        _set(row, before, line)
        if row.get("journal_id"):
            from halo_harness.ollama_steward.steward import _append as journal
            journal(state_dir, {"_now": now, "id": f"u-{row['journal_id']}", "kind": "undo", "reverts": row["journal_id"],
                                "key": row["key"], "field": row["field"], "from": row.get("after"),
                                "to": row.get("before"), "why": why, "say": f"steward undo: {line}"})
    _append(state_dir, {"event": "revert", "id": row["id"], "reverted_at": now_iso(now), "revert_why": why,
                        "revert_line": line})
    return line


def _do(state_dir, due: list, why: str, now: Optional[float]) -> list:
    if not due:
        return []
    from halo_harness.ollama_steward.steward import profile_lock
    with profile_lock(state_dir):
        return [_put_back(state_dir, r, why, now) for r in sorted(due, key=lambda r: str(r.get("at")), reverse=True)]


def revert(state_dir, which: str, why: str = "reverted by hand", *, scope: Optional[str] = None,
           host: Optional[str] = None, now: Optional[float] = None) -> list:
    rows = in_force(state_dir, host)
    if scope:
        rows = [r for r in rows if r.get("scope") == scope]
    if which != "all":
        rows = [r for r in rows if r.get("id") == which]
        if not rows:
            return [f"no change in force with the id {which} (halo local changes lists them)"]
    return _do(state_dir, rows, why, now) or ["nothing to revert: no change in force" + (f" on {host}" if host else "")]


def mark_reverted(state_dir, journal_id: str, line: str, why: str, now: Optional[float] = None) -> None:
    """The steward's own undo / rollback (steward._revert) put the field back: its change row says so."""
    from halo_harness.ollama_steward.ledger import now_iso
    for r in in_force(state_dir):
        if r.get("journal_id") == journal_id:
            _append(state_dir, {"event": "revert", "id": r["id"], "reverted_at": now_iso(now), "revert_why": why,
                                "revert_line": line})


def _alive(pid, cache: dict) -> bool:
    if pid == os.getpid():
        return True
    if pid not in cache:
        from halo_harness.bg_run import pid_alive
        cache[pid] = pid_alive(pid) if isinstance(pid, int) else False
    return cache[pid]


def revert_scope(state_dir, scope: str, session_id: Optional[str] = None, *, why: Optional[str] = None,
                 now: Optional[float] = None) -> list:
    """The changes due under `scope` put back; [] (and nothing written) when none is due."""
    if state_dir is None or not path(state_dir).exists():
        return []
    rows, seen = in_force(state_dir), {}
    if scope == "session":
        due = [r for r in rows if r.get("scope") == "session" and session_id and r.get("session_id") == session_id]
        return _do(state_dir, due, why or "the session ended", now)
    if scope != "until-restart":
        return []
    mine = [r for r in rows if r.get("scope") == "until-restart" and r.get("pid") == os.getpid()]
    gone = [r for r in rows if r not in mine and ((r.get("scope") == "until-restart" and not _alive(r.get("pid"), seen))
            or (r.get("scope") == "session" and r.get("session_pid") and not _alive(r.get("session_pid"), seen)))]
    return _do(state_dir, mine, why or "this halo exited", now) + _do(state_dir, gone, "the halo that made it is gone", now)


def rescope(state_dir, which: str, scope: str, session_id: Optional[str] = None) -> str:
    if scope not in SCOPES:
        return f"{scope!r} is not a scope ({', '.join(SCOPES)})"
    row = next((r for r in in_force(state_dir) if r.get("id") == which), None)
    if row is None:
        return f"no change in force with the id {which}"
    if scope == "session" and not (session_id or row.get("session_id")):
        return "session needs a session to end with: name one (--session) or pick until-restart or keep"
    _append(state_dir, {"event": "scope", "id": which, "scope": scope, "session_id": session_id or row.get("session_id")})
    if scope != "keep":
        _remember(state_dir)
    return f"{row['field']} on {row['key']}: {WORDS[scope]}"


def line_of(r: dict) -> str:
    """'[ch-1] num_ctx 32,768 -> 16,384 on pc|m (by steward, until-restart: undone when this halo exits)'."""
    state = f"reverted: {r.get('revert_line')}" if r.get("reverted_at") else f"{r.get('scope')}: {WORDS.get(r.get('scope'), '')}"
    return (f"[{r['id']}] {r['field']} {fmt(r.get('before'))} -> {fmt(r.get('after'))} on {r['key']} "
            f"(by {r.get('by')}, {state})" + (f" -- {r['why']}" if r.get("why") else ""))


def at_exit() -> list:
    """The exit path: this process's until-restart changes put back in every home it recorded one in (only while that
    home is still this process's home and its file is there: a test's scratch home that moved on is left alone)."""
    out: list = []
    try:
        from halo_harness.config.paths import bridge_home
        here = Path(bridge_home()).resolve()
    except Exception:
        return out
    for d in sorted(_DIRS):
        try:
            if Path(d).resolve() == here and path(d).exists():
                out += revert_scope(d, "until-restart")
        except Exception:
            continue
    return out
