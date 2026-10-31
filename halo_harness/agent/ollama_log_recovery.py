"""halo_harness.agent.ollama_log_recovery -- Halo 3.3.6.0 R3: the log drives recovery
(plans/local-model-fit-brief.md D3 item 14).

After each call to an Ollama host whose server log is readable from here (this machine's file, or a host whose ssh
read answered before), the log lines since the call began are read (DEADLINE_S in all: a read every POLL_S until the
call's `[GIN]` line is there; one read over ssh), the events for this model and the unattributed ones kept, and:

    prompt-trimmed   trim_recovery takes the log's exact limit / prompt / keep (`exact`, `trim_said`) instead of a
                     reply-count guess: "the log shows the prompt was cut at N of M tokens: re-sent with ..."
    cpu-spill        one line with the layers and the fit plan's option (or the profile's fix)
    a crash          its fingerprint at once (fingerprints.record) and failure_lines.explain's line naming it
    reply-cut        the reply reserve line

    read_for_call(session, host, model, started_at) -> {events, kinds, trim, spill, crashes, cut} | None (cached)
    ledger_kinds(session, target, line) -> [kinds] | None   ollama_steward/ledger_call._write's `log_events`
    after_call(session, body, meta) -> {lines, trim, clean}  agent/loop.py's Ollama path, after local_failure; clean:
                     the log has the call's [GIN] line and no cut, so the reply-count guess is not made
    preflight_evidence(session, last) -> {line, factor} | None   agent/preflight.check's evidence line
No readable log, or nothing new: no change.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

log = logging.getLogger("bridge")

DEADLINE_S = 2.0
POLL_S = 0.2
CACHE_S = 15.0
REMOTE_TAIL_BYTES = 64 * 1024  # one ssh read after a call: the newest 64 KB of the two newest files, as base64
CRASH = ("gpu-memory", "other-error", "load-failed")
SEAMS: dict = {}  # "before_read": fn(session) once before the first read (the tests append their fixture there)
_GIN_SEEN: dict = {}  # host url -> did the last read see its call's [GIN] line (no: later reads do not wait)


def _source(session, host) -> "tuple[Optional[str], object]":
    from halo_harness.fleet.ollama_share import served_here
    from halo_harness.ollama_steward.hardware_readers import server_log_path
    if served_here(host.url):
        target = server_log_path()
        return ("file", target) if target.exists() else (None, None)
    if getattr(host, "ssh", None) and getattr(session, "state_dir", None) is not None:
        from halo_harness.ollama_steward.server_log_remote import host_state
        rs = host_state(session.state_dir, host.name)
        return ("ssh", None) if rs.get("ok_at") and not rs.get("why") else (None, None)
    return None, None


def _since(lines: list, started_at: float) -> list:
    from halo_harness.ollama_steward.server_rules import line_time, strip_prefix
    for i, line in enumerate(lines):
        t = line_time(strip_prefix(line))
        if t is not None and t >= started_at:
            return lines[i:]
    return []


def _new_lines(session, host, kind, target) -> list:
    """The lines this session has not read yet: this machine's file from the offset its last read left (the first
    read: the newest 3,000), that machine's newest 400 after the last line read before."""
    from halo_harness.ollama_steward.log_tail import local_tail, remote_tail
    from halo_harness.ollama_steward.server_log import tail
    box = session.__dict__.setdefault("_ollama_log_pos", {})
    if kind == "file":
        st = box.get(host.name)
        if st:
            lines, box[host.name] = tail(target, st)
            return lines
        lines, (_none, box[host.name]) = local_tail(target, 3000), tail(target, {})
        return lines
    lines = remote_tail(host, 400, timeout=DEADLINE_S, tail_bytes=REMOTE_TAIL_BYTES)[0]
    mark = box.get(host.name)
    if mark and mark in lines:
        lines = lines[len(lines) - lines[::-1].index(mark):]
    if lines:
        box[host.name] = lines[-1]
    return lines


def _read(session, host, kind, target, started_at: float) -> list:
    if "before_read" in SEAMS:
        SEAMS["before_read"](session)
    deadline, got = time.monotonic() + DEADLINE_S, []
    while True:
        got += _new_lines(session, host, kind, target)
        lines = _since(got, started_at)
        seen = any("[GIN]" in x for x in lines)
        if seen or kind != "file" or not _GIN_SEEN.get(host.url, True) or time.monotonic() + POLL_S > deadline:
            _GIN_SEEN[host.url] = seen or (kind != "file" and _GIN_SEEN.get(host.url, True))
            return lines
        time.sleep(POLL_S)


def read_for_call(session, host, model: Optional[str], started_at: float) -> Optional[dict]:
    """The log's events of the call to `model` on `host` that began at `started_at` (epoch s), or None."""
    if host is None or session is None:
        return None
    hit = getattr(session, "_ollama_log_read", None)
    if hit and hit["key"] == (host.name, model) and time.monotonic() - hit["mono"] < CACHE_S and abs(hit["started"] - started_at) <= 2:
        return hit["result"]
    try:
        kind, target = _source(session, host)
        if kind is None:
            return None
        from halo_harness.ollama_steward.server_context import Rules
        from halo_harness.providers.ollama import ollama_names_match
        rules = Rules()
        lines = _read(session, host, kind, target, started_at)
        evs = [e for x in lines for e in rules.feed(x)] + rules.flush()
        evs = [e for e in evs if not e.get("model") or not model or ollama_names_match(e["model"], model)]
        r = {"events": evs, "kinds": sorted({e["kind"] for e in evs}), "lines": len(lines),
             "gin": any("[GIN]" in x for x in lines),
             "trim": next((dict(e["data"]) for e in evs if e["kind"] == "prompt-trimmed"), None),
             "spill": next((e for e in evs if e["kind"] == "cpu-spill"), None),
             "cut": next((e for e in evs if e["kind"] in ("reply-cut", "window-full")), None),
             "crashes": _fingerprints(session, host, [e for e in evs if e["kind"] in CRASH], model)}
    except Exception:
        log.debug("ollama_log_recovery: the log read after the call failed", exc_info=True)
        return None
    session._ollama_log_read = {"key": (host.name, model), "mono": time.monotonic(), "started": started_at, "result": r}
    return r


def _fingerprints(session, host, crashes: list, model: Optional[str]) -> list:
    """Each crash's fingerprint written now (the steward's own read later joins it) and its line; a crash line that
    names no model is the call's (it fell in the call's window)."""
    from halo_harness.ollama_steward.fingerprints import record, signature_of
    from halo_harness.ollama_steward.ledger import now_iso
    rows = [{**e, "host": host.name, "at": now_iso(e["at"] if isinstance(e.get("at"), (int, float)) else time.time()),
             "model": e.get("model") or model, "data": {**(e.get("data") or {}),
                                                         **({} if e.get("model") else {"model_from": "the call"})}}
            for e in crashes if signature_of(e)]
    if not rows or getattr(session, "state_dir", None) is None:
        return []
    from halo_harness.ollama_steward.failure_lines import explain
    out, seen = [], set()
    for row, fp in zip(rows, record(session.state_dir, rows, host.name)):  # the lines of one crash: one fingerprint
        if (fp.get("at"), fp.get("model")) not in seen:
            seen.add((fp.get("at"), fp.get("model")))
            out.append({"fingerprint": fp, "line": explain(row, session.state_dir, fingerprint=fp).get("say")})
    return out


def _host_of(session, name: Optional[str]):
    from halo_harness.providers.ollama import resolve_ollama_host
    env = getattr(getattr(session, "settings", None), "effective_env", None)
    return resolve_ollama_host(name, env)


def ledger_kinds(session, target: dict, line: dict) -> Optional[list]:
    """The kinds the log showed for the call this ledger line records (None: no readable log)."""
    if session is None or target.get("dialect") != "ollama":
        return None
    total = line.get("total_ms") if isinstance(line.get("total_ms"), (int, float)) else 0
    started = time.time() - float(total) / 1000.0 - 1.0
    r = read_for_call(session, _host_of(session, (target.get("host") or {}).get("name")), line.get("model"), started)
    return r["kinds"] if r is not None else None


def _spill_line(session, host, model: str, ev: dict, num_ctx) -> str:
    from halo_harness.ollama_steward.failure_lines import explain
    d = ev.get("data") or {}
    a, b = d.get("offloaded"), d.get("layers")
    lay = f"{a}/{b} layers on the GPU" if isinstance(a, int) and isinstance(b, int) else "part of it on the CPU"
    fix = explain({**ev, "host": host.name}, session.state_dir).get("fix")
    if not fix:
        fix = _plan_option(host, model, num_ctx) or (f"a smaller window or a fitted twin (halo ollama tune {model} "
                                                       f"--host {host.name})")
    return f"the log shows {model} spilled to the CPU ({lay}): {fix}"


def _plan_option(host, model: str, num_ctx) -> Optional[str]:
    try:
        from halo_harness.ollama_steward.fit import plan
        from halo_harness.providers.fit_meter import host_card_of
        from halo_harness.providers.local_models_cached import cached_catalog
        rows = {str(r.get("model") or r.get("name")): r for r in (cached_catalog(host) or {}).get("models") or []
                if isinstance(r, dict)}
        p = plan(host_card_of(host) or {}, [{"model": model, "window": num_ctx, "calls": 1}], rows, host_name=host.name)
        ch = p.get("chosen")
        return p["options"][ch]["says"] if isinstance(ch, int) and ch < len(p.get("options") or []) else None
    except Exception:
        return None


def after_call(session, body: dict, meta: Optional[dict] = None) -> dict:
    """{lines (said under the turn), trim (the log's limit / prompt / keep, or None)} after one Ollama call: the
    ledger's read of this call when it made one (ledger_kinds), else a read of its own."""
    from halo_harness.agent.ollama_window import _state
    last = _state(session).get("last") or {}
    model, num_ctx = body.get("model"), (body.get("options") or {}).get("num_ctx")
    hit, session._ollama_log_read = getattr(session, "_ollama_log_read", None), None
    host = _host_of(session, last.get("host_name"))
    if hit and host is not None and hit["key"] == (host.name, model) and time.monotonic() - hit["mono"] < CACHE_S:
        r = hit["result"]
    else:
        took = ((meta or {}).get("timing_ns") or {}).get("total_duration")
        started = time.time() - (float(took) / 1e9 if isinstance(took, (int, float)) else DEADLINE_S * 15) - 1.0
        r = read_for_call(session, host, model, started) if host is not None else None
        session._ollama_log_read = None
    if not r:
        return {"lines": [], "trim": None, "clean": False}
    out: list = []
    if r["trim"]:
        session._ollama_log_trims = {**(getattr(session, "_ollama_log_trims", None) or {}), model: {
            **r["trim"], "estimate": last.get("estimate"), "reserve": last.get("reserve"), "at": time.time()}}
    if r["spill"] and host is not None:
        out.append(_spill_line(session, host, model, r["spill"], num_ctx))
    out += [c["line"] for c in r["crashes"] if c.get("line")]
    if r["cut"] and not r["trim"]:
        out.append(f"the log shows {r['cut']['say']}")
    return {"lines": out, "trim": r["trim"], "clean": bool(r.get("gin")) and not r["trim"]}


def exact(session, trim: dict) -> None:
    """The window state's estimate becomes the log's exact prompt (plus the reply's room) before trim_recovery."""
    from halo_harness.agent.ollama_window import _state
    last = _state(session).get("last")
    if last and isinstance(trim.get("prompt"), int):
        last["estimate"] = int(trim["prompt"]) + int(last.get("reserve") or 1024)


def trim_said(trim: dict, kind: str, num_ctx: Optional[int], host_name: str) -> str:
    from halo_harness.providers.ollama_prompt import fmt_window
    done = f"re-sent with a {fmt_window(num_ctx)} window" if kind == "resend" else "compacted and re-sent"
    return (f"the log shows the prompt was cut at {trim.get('limit'):,} of {trim.get('prompt'):,} tokens on {host_name} "
            f"(the request's window {trim.get('window_sent'):,}): {done}")


def preflight_evidence(session, last: dict) -> Optional[dict]:
    """The log's last truncation of this model in this session: how far Halo's estimate fell short of the real prompt."""
    t = (getattr(session, "_ollama_log_trims", None) or {}).get((last or {}).get("model"))
    if not t or not isinstance(t.get("prompt"), int):
        return None
    est = max(1, int(t.get("estimate") or 0) - int(t.get("reserve") or 1024))
    when = time.strftime("%H:%M", time.localtime(t.get("at") or time.time()))
    return {"factor": max(1.0, t["prompt"] / est), "line": f"the log cut this model's prompt at {t['limit']:,} of "
            f"{t['prompt']:,} tokens at {when}"}
