"""halo_harness.host.verify -- apply, measure, keep or revert (Halo 3.3.7.0 R2; plans/local-model-fit-brief.md H10.3).

After a profile fix lands (host/ops_control.py's `set_*`), the host records `before` -- the card's loaded row for the
model (`size`, `size_vram`, `context_length` from `/api/ps`), the newest `load-result` event's layers and splits, and
the ledger's median tok/s, trims, cut replies and errors over the last JUDGE_CALLS calls of that host and model --
and watches the next `host.verify_calls` (5) calls or `host.verify_s` (600 s), whichever comes first. Then it writes
`after` and the verdict into the fix's row (`<state>/host/fixes.jsonl`) and a `verdict` event into the change's own
file (`<state>/ollama/changes.jsonl`), publishes one `event` frame, and when the calls went worse -- more trims, cut
replies and errors than before (ollama_steward/steward_rollback.py's comparison), or a tok/s at least 10 % lower --
puts the change back (`changes.revert`) and says so:

    "set_num_ctx 32768 on pc|qwen3-coder:30b: 16 -> 188 tok/s, no trims -- kept"

A window with no calls in it measures nothing: the change is kept and the line says so. No model is called.

    before(view, host, model) / open_fix(home, **row) / open_on(home, host) / last_on(home, key) / tick(svc, now)
    listing(home) -> GET changes: the host's change rows newest first, each with its fix row (verdict, before, after)
"""

from __future__ import annotations

import json
import statistics
import time
from typing import Optional

FIXES_FILE = "fixes.jsonl"
VERIFY_CALLS = 5
VERIFY_S = 600.0
SLOWER = 0.9
KEEP_ROWS = 300


def _n(home, key: str, default, kind=float):
    from halo_harness.host.state import _cfg
    try:
        v = kind(_cfg(key, default, home))
    except (TypeError, ValueError):
        return default
    return v if v > 0 else default


def verify_calls(home) -> int:
    return _n(home, "host.verify_calls", VERIFY_CALLS, int)


def verify_s(home) -> float:
    return _n(home, "host.verify_s", VERIFY_S)


def _path(home):
    from halo_harness.host.state import host_dir
    return host_dir(home) / FIXES_FILE


def _rows(home) -> list:
    out = []
    try:
        for raw in _path(home).read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                r = json.loads(raw)
            except ValueError:
                continue
            if isinstance(r, dict) and r.get("id"):
                out.append(r)
    except OSError:
        return []
    return out


def _save(home, rows: list) -> None:
    from halo_harness.privateio import write_private_atomic
    _path(home).parent.mkdir(parents=True, exist_ok=True)
    write_private_atomic(_path(home), "".join(json.dumps(r, default=str) + "\n" for r in rows[-KEEP_ROWS:]))


def _lines(home, host_name: str, model: str, hosts: Optional[list] = None) -> list:
    """That host's calls of `model` (a peer's pushed lines too: their host is mapped to this host's own name)."""
    from halo_harness.ollama_steward.ledger import read_calls
    from halo_harness.ollama_steward.profiles import short_model
    from halo_harness.ollama_steward.traffic import canonical_host
    want, hosts = short_model(model), list(hosts or [])
    return [x for x in read_calls(home, since=7 * 86400.0) if x.get("kind") != "calibrate"
            and short_model(x.get("model")) == want
            and str(canonical_host(x.get("host") or {}, hosts)[0]).lower() == host_name.lower()]


def stats(lines: list) -> dict:
    from halo_harness.ollama_steward.steward_rollback import _bad
    rates = [x.get("eval_tok_s") for x in lines if isinstance(x.get("eval_tok_s"), (int, float)) and not x.get("warming")]
    return {"calls": len(lines), "tok_s": round(statistics.median(rates), 1) if rates else None,
            "trims": sum(1 for x in lines if x.get("trimmed")), "cuts": sum(1 for x in lines if x.get("done_reason") == "length"),
            "errors": sum(1 for x in lines if x.get("status") not in (None, 200)), "bad": sum(map(_bad, lines))}


def _loaded_row(view, host, model: str) -> Optional[dict]:
    from halo_harness.host.invariants import loaded
    from halo_harness.providers.ollama import ollama_names_match
    try:
        hit = next((r for r in loaded(view, host) if ollama_names_match(r.get("model"), model)), None)
    except Exception:
        hit = None
    return {k: hit.get(k) for k in ("size", "size_vram", "context_length")} if hit else None


def _load_result(home, host_name: str, model: str) -> dict:
    from halo_harness.ollama_steward.server_events import read_events
    from halo_harness.providers.ollama import ollama_names_match
    rows = [e for e in read_events(home, since=7 * 86400.0, kind="load-result")
            if str(e.get("host") or "").lower() == host_name.lower() and ollama_names_match(e.get("model"), model)]
    d = (rows[-1].get("data") or {}) if rows else {}
    return {"layers": d.get("layers"), "splits": d.get("splits")}


def before(view, host, model: str) -> dict:
    from halo_harness.ollama_steward.steward import JUDGE_CALLS
    lines = _lines(view.home, host.name, model, view.hosts())[-JUDGE_CALLS:]
    return {"loaded": _loaded_row(view, host, model), **_load_result(view.home, host.name, model), **stats(lines)}


def open_fix(home, *, change_id: str, peer: str, op: str, host: str, model: str, key: str, field: str, to,
             evidence: Optional[dict], before_: dict, now: Optional[float] = None) -> dict:
    from halo_harness.filelock import file_lock
    now = time.time() if now is None else now
    row = {"id": change_id, "at": now, "peer": peer, "op": op, "host": host, "model": model, "key": key, "field": field,
           "to": to, "evidence": evidence, "before": before_, "after": None, "verdict": "verifying",
           "need_calls": verify_calls(home), "ends_at": now + verify_s(home), "line": ""}
    with file_lock(_path(home), timeout=2.0):
        _save(home, _rows(home) + [row])
    return row


def open_on(home, host_name: str) -> Optional[dict]:
    return next((r for r in reversed(_rows(home)) if r.get("verdict") == "verifying"
                 and str(r.get("host") or "").lower() == host_name.lower()), None)


def last_on(home, key: str) -> Optional[dict]:
    return next((r for r in reversed(_rows(home)) if r.get("key") == key), None)


def _fmt(v) -> str:
    return f"{v:.0f}" if isinstance(v, (int, float)) else "?"


def judge(row: dict, after_lines: list, *, window_s: float) -> "tuple[str, str, dict]":
    b, a = row.get("before") or {}, stats(after_lines)
    label = f"{row['op']} {row.get('to')} on {row['key']}"
    if not after_lines:
        return "kept", f"{label}: no calls in {int(window_s)} s to judge by -- kept (nothing measured)", a
    slower = isinstance(a["tok_s"], (int, float)) and isinstance(b.get("tok_s"), (int, float)) and a["tok_s"] < b["tok_s"] * SLOWER
    worse = a["bad"] > int(b.get("bad") or 0) or slower
    speed = (f"{_fmt(b.get('tok_s'))} -> {_fmt(a['tok_s'])} tok/s" if a["tok_s"] is not None or b.get("tok_s") is not None
             else "tok/s not measured")
    bad = ("no trims" if not (a["trims"] or a["cuts"] or a["errors"]) else
           f"{a['trims']} trims, {a['cuts']} cut replies, {a['errors']} errors in {a['calls']} calls (before: "
           f"{b.get('trims', 0)}, {b.get('cuts', 0)}, {b.get('errors', 0)})")
    verdict = "reverted" if worse else "kept"
    return verdict, f"{label}: {speed}, {bad} -- {verdict}", a


def tick(svc, now: Optional[float] = None) -> list:
    """Close every fix whose window ended (by calls or by time); returns the closed rows."""
    from halo_harness.filelock import file_lock
    from halo_harness.ollama_steward import changes
    from halo_harness.ollama_steward.ledger import parse_at
    home, now = svc.home, (time.time() if now is None else now)
    if not _path(home).exists():
        return []
    closed = []
    live = {r["id"] for r in changes.in_force(home)}
    with file_lock(_path(home), timeout=2.0):
        rows = _rows(home)
        for row in rows:
            if row.get("verdict") != "verifying":
                continue
            if row["id"] not in live:  # put back by hand (manage/revert) before the window closed
                row.update(verdict="reverted", line=f"{row['op']} {row.get('to')} on {row['key']}: put back by hand "
                           "before its window closed", closed_at=now)
                closed.append(dict(row))
                continue
            after = [x for x in _lines(home, row["host"], row["model"], svc.view.hosts())
                     if (parse_at(x.get("at")) or 0) >= row["at"]]
            after = after[:int(row.get("need_calls") or VERIFY_CALLS)]
            if len(after) < int(row.get("need_calls") or VERIFY_CALLS) and now < float(row.get("ends_at") or 0):
                continue
            verdict, line, a = judge(row, after, window_s=float(row["ends_at"]) - float(row["at"]))
            host = next((h for h in svc.view.hosts() if h.name == row["host"]), None)
            a["loaded"] = _loaded_row(svc.view, host, row["model"]) if host is not None else None
            if verdict == "reverted":
                back = changes.revert(home, row["id"], f"the host's verify: {line}")
                line += f"; {back[0]}" if back else ""
            row.update(verdict=verdict, after=a, line=line, closed_at=now)
            changes._append(home, {"event": "verdict", "id": row["id"], "verdict": verdict, "line": line, "after": a})
            closed.append(dict(row))
        if closed:
            _save(home, rows)
    if closed:
        from halo_harness.host.jobs import of
        for r in closed:
            of(svc).bus.publish("event", {"kind": "fix-verdict", "say": r["line"], "change": r["id"], "key": r["key"],
                                          "verdict": r["verdict"], "peer": r.get("peer"), "at": now})
    return closed


def listing(home, *, limit: int = 100) -> list:
    from halo_harness.ollama_steward.changes import line_of, read
    fixes = {r["id"]: r for r in _rows(home)}
    out = []
    for r in sorted(read(home), key=lambda r: str(r.get("at")), reverse=True)[:limit]:
        f = fixes.get(r["id"]) or {}
        out.append({**r, "line": line_of(r), "verdict": f.get("verdict"), "verify_line": f.get("line") or None,
                    "before_m": f.get("before"), "after_m": f.get("after"), "peer": f.get("peer"), "op": f.get("op"),
                    "evidence": f.get("evidence")})
    return out
