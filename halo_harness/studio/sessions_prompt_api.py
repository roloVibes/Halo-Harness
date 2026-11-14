"""halo_harness.studio.sessions_prompt_api -- Studio's Prompt panel on a live session (Halo 3.3.11.0 R1): the
receipts of what it sends, its slash list and the ladder's rows.

    POST sessions/<sid>/command {cmd: submit, text, when_busy?: steer|refuse|queue, client_id?, image?...}
         200 {ok, result, receipt}                     taken (a turn, a steer, or the turn held for later)
         200 {ok, busy: true, line, result, receipt}   `refuse` while a turn runs: nothing was taken
         409 {error: line, busy, held, receipt}        `queue` while one turn is already held
         200 {ok, duplicate: true, receipt}            a retry with a `client_id` already stored: nothing is sent
    POST ... {cmd: steer | answer, ..., client_id?}    the same receipt (`steer` and `answer` rows)
    POST ... {cmd: slash, line | name + args}          200 {ok, result: {output, lines}}: what the TUI would print
    POST ... {cmd: tail, n?}                           200 {ok, result: {markdown}}
    GET  sessions/<sid>/slash                          [{name, group, help, args, source}]: the builtins table and
                                                       the session's project and user commands and skills
    GET  sessions/<sid>/receipts                       {receipts: [{id, client_id, kind, sha256, at, sent_at,
                                                        state, reason?, turn?, seq?}]}, the TTL applied

A `submit` or `steer` from Studio carries `origin: {via: "studio", by: <fleet name>}`, so the terminal's transcript
says "(from Studio)". The `sent` row is stored before the socket call (remote/receipts.py); the session moves it on
(delivered, read, replied), and this side marks `delivered` too once the socket answered (a no-op when the session
already did), `failed` with the reason when the socket refused, or the session was busy (`busy`), or held a turn
already (`held`).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Optional

from halo_harness.remote.prompt_queue import WHEN_BUSY

SEND_KINDS = {"submit": "prompt", "steer": "steer", "answer": "answer"}
TAIL_DEFAULT = 40


@dataclass
class Pending:
    """One send on its way: its receipts file and `sent` row (None for a command that has none)."""
    rec: object = None
    row: Optional[dict] = None


def _receipts(sid: str, entry: dict):
    from halo_harness.remote.receipts import Receipts, session_folder
    folder = session_folder(sid, (entry or {}).get("cwd"))
    return Receipts(folder) if folder is not None else None


def _client_id(body: dict) -> str:
    cid = str(body.get("client_id") or "").strip()
    return cid if re.fullmatch(r"[A-Za-z0-9_.:-]{1,64}", cid) else ""


def fields_for(cmd: str, body: dict) -> "tuple[Optional[tuple], dict]":
    """The socket fields of a `slash` / `tail` (or the extra ones of a `submit` / `steer`); (422 answer, {}) when bad."""
    if cmd == "slash":
        line, name = str(body.get("line") or "").strip(), str(body.get("name") or "").strip()
        if not (line.startswith("/") or name):
            return (422, {"error": "a slash needs `line` (\"/cost\") or `name`", "problems": []}), {}
        return None, ({"line": line} if line.startswith("/") else {"name": name.lstrip("/"), "args": str(body.get("args") or "")})
    if cmd == "tail":
        n = body.get("n", TAIL_DEFAULT)
        return None, {"n": n if isinstance(n, int) and not isinstance(n, bool) else TAIL_DEFAULT}
    from halo_harness.studio.live_agents_api import caller
    extra: dict = {"origin": {"via": "studio", "by": caller()["by"]}}
    wb = str(body.get("when_busy") or "")
    if cmd == "submit" and wb:
        if wb not in WHEN_BUSY:
            return (422, {"error": f"when_busy is one of {', '.join(WHEN_BUSY)}, got {wb!r}", "problems": []}), {}
        extra["when_busy"] = wb
    return None, extra


def before(sid: str, entry: dict, cmd: str, body: dict, fields: dict) -> "tuple[Optional[tuple], Pending]":
    """Store `sent` (and put its id on the socket fields as `receipt`); a stored `client_id` answers here."""
    kind = SEND_KINDS.get(cmd)
    if kind is None:
        return None, Pending()
    rec = _receipts(sid, entry)
    if rec is None:
        return None, Pending()
    text = str(fields.get("text") or "") if kind != "answer" else json.dumps(fields, sort_keys=True, default=str)
    row, duplicate = rec.record(kind, text, client_id=_client_id(body))
    if duplicate:
        return (200, {"ok": True, "duplicate": True, "receipt": row, "result": {}}), Pending(rec, row)
    fields["receipt"] = row["id"]
    return None, Pending(rec, row)


def after(p: Pending, resp: dict) -> "tuple[int, dict]":
    """The socket's answer as Studio's, the receipt moved with it."""
    rid = (p.row or {}).get("id") or ""
    rec = p.rec

    def move(state: str, reason: str = "") -> Optional[dict]:
        if rec is None or not rid:
            return None
        rec.advance(rid, state, reason=reason)
        return rec.get(rid)
    if not resp.get("ok"):
        err = str(resp.get("error") or "the session refused the command")
        got = move("failed", err[:200])
        return 502, {"error": err, **({"receipt": got} if got else {})}
    result = resp.get("result") if isinstance(resp.get("result"), dict) else {}
    if result.get("busy") and result.get("held"):
        return 409, {"error": result.get("line") or "one turn is already queued", "busy": True, "held": True,
                     "receipt": move("failed", "held")}
    if result.get("busy") and not result.get("queued"):
        return 200, {"ok": True, "busy": True, "line": result.get("line") or "", "result": result,
                     "receipt": move("failed", "busy")}
    if isinstance(result.get("output"), str):
        result = {**result, "lines": result["output"].splitlines()}
    got = move("delivered") if rid else None
    return 200, {"ok": True, "result": result, **({"receipt": got} if got else {})}


def get_receipts(req):
    sid = req.params["sid"]
    from halo_harness.studio.sessions_api import _list_live
    entry = next((e for e in _list_live() if e.get("session_id") == sid), {})
    from halo_harness.safe_id import is_safe_session_id
    if not is_safe_session_id(sid):
        return 422, {"error": f"not a session id: {sid!r}", "problems": []}
    rec = _receipts(sid, entry)
    return 200, {"receipts": rec.read_all() if rec is not None else []}  # None: no folder yet, so nothing sent


def catalog(cwd) -> list:
    """The slash list the TUI completes from: [{name, group, help, args, source}], sorted by name."""
    from halo_harness.commands.registry import Registry
    from halo_harness.config.paths import home
    reg = Registry.discover(cwd, home())
    return [{"name": c.name, "group": c.kind, "help": c.description or "", "args": c.argument_hint or "",
             "source": c.source} for c in reg.all()]


def get_slash(req):
    sid = req.params["sid"]
    from halo_harness.studio.sessions_api import _list_live
    entry = next((e for e in _list_live() if e.get("session_id") == sid), None)
    if entry is None:
        return 404, {"error": f"no live session {sid!r}"}
    return 200, catalog(entry.get("cwd") or req.cwd)


ROUTES = [("GET", r"^sessions/(?P<sid>[A-Za-z0-9_.:-]+)/slash$", get_slash),
          ("GET", r"^sessions/(?P<sid>[A-Za-z0-9_.:-]+)/receipts$", get_receipts)]
