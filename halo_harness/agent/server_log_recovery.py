"""halo_harness.agent.server_log_recovery -- Halo 3.3.8.0 R2: after an `hf:local/*` or `hf:mlx/*` call, the local
server's own log read the way agent/ollama_log_recovery.py reads Ollama's (the sibling for llama-server, LM Studio,
mlx_lm.server; ollama_steward/server_log_hf.py finds the log):

- the lines this session has not read yet (the offset its last read left; the first read: the newest 400, and of
  those the lines of this call -- since the call began for a log with timestamps, else after the request line
  before this call's own), waiting at most DEADLINE_S, a read every POLL_S, until this call's request line is there;
- the events (server_context_hf.Rules) go on the call's ledger line (`log_events`); a crash writes its fingerprint at
  once, its line naming it; a cut, a spill and the server's own n_predict say one line each under the turn.

    ledger_kinds(session, target, line) -> [kinds] | None   ollama_log_recovery.ledger_kinds hands an OpenAI-dialect
                                                           call here (None: no readable log for that server)
    after_call(session) -> [lines]                          agent/loop.py's hf path, after the reply
"""

from __future__ import annotations

import logging
import time
from typing import Optional

log = logging.getLogger("bridge")

DEADLINE_S = 2.0
POLL_S = 0.2
CACHE_S = 15.0
CRASH = ("gpu-memory", "other-error", "load-failed")
MARKS = ("log_server_r: request:", "Generated prediction", '"POST /v1/', "Running chat completion")
SEAMS: dict = {}  # "before_read": fn(session), the tests' hook before the first read


def _server(session, target: dict):
    from halo_harness.ollama_steward.servers_hf import for_url
    url = str(((target or {}).get("host") or {}).get("url") or "")
    return for_url(url, getattr(session, "state_dir", None)) if url else None


def _this_call(lines: list, started_at: float) -> list:
    from halo_harness.ollama_steward.server_rules_hf import line_time
    times = [(i, line_time(x)) for i, x in enumerate(lines)]
    if any(t is not None for _i, t in times):
        first = next((i for i, t in times if t is not None and t >= started_at), None)
        return lines[first:] if first is not None else []
    marks = [i for i, x in enumerate(lines) if any(m in x for m in MARKS)]
    return lines[marks[-2] + 1:] if len(marks) >= 2 else lines[-60:]


def _read(session, server, target, started_at: float) -> list:
    from halo_harness.ollama_steward.log_tail import local_tail
    from halo_harness.ollama_steward.server_log import tail
    if "before_read" in SEAMS:
        SEAMS["before_read"](session)
    box = session.__dict__.setdefault("_server_log_pos", {})
    st = box.get(server.name)
    if st:
        got, deadline = [], time.monotonic() + DEADLINE_S
        while True:
            more, st = tail(target, st)
            got += more
            if any(m in x for x in got for m in MARKS) or time.monotonic() + POLL_S > deadline:
                box[server.name] = st
                return got
            time.sleep(POLL_S)
    lines = local_tail(target, 400)
    box[server.name] = tail(target, {})[1]
    return _this_call(lines, started_at)


def read_for_call(session, server, model: Optional[str], started_at: float) -> Optional[dict]:
    from halo_harness.ollama_steward.server_context_hf import Rules
    from halo_harness.ollama_steward.server_log_hf import source_for_server
    target, _why = source_for_server(server)
    if target is None:
        return None
    rules = Rules(server.runtime)
    lines = _read(session, server, target, started_at)
    evs = [e for x in lines for e in rules.feed(x, at=time.time())]
    evs = [e for e in evs if not e.get("model") or not model or e["model"] == model or str(model).endswith(e["model"])]
    return {"events": evs, "kinds": sorted({e["kind"] for e in evs}), "lines": len(lines),
            "trim": next((e for e in evs if e["kind"] == "prompt-trimmed"), None),
            "spill": next((e for e in evs if e["kind"] == "cpu-spill"), None),
            "cut": next((e for e in evs if e["kind"] in ("reply-cut", "window-full")), None),
            "crashes": _fingerprints(session, server, [e for e in evs if e["kind"] in CRASH], model)}


def _fingerprints(session, server, crashes: list, model: Optional[str]) -> list:
    from halo_harness.ollama_steward.fingerprints import record, signature_of
    from halo_harness.ollama_steward.ledger import now_iso
    rows = [{**e, "host": server.name, "at": now_iso(time.time()), "model": e.get("model") or model,
             "data": {**(e.get("data") or {}), **({"launch": server.launch} if server.launch else {})}}
            for e in crashes if signature_of(e)]
    if not rows or getattr(session, "state_dir", None) is None:
        return []
    return [{"fingerprint": fp, "line": f"the log of {server.name} shows {fp['line']} (halo ollama crashes --why)"}
            for fp in record(session.state_dir, rows, server.name)[:1]]


def ledger_kinds(session, target: dict, line: dict) -> Optional[list]:
    if session is None:
        return None
    try:
        server = _server(session, target)
        if server is None:
            return None
        total = line.get("total_ms") if isinstance(line.get("total_ms"), (int, float)) else 0
        r = read_for_call(session, server, line.get("model"), time.time() - float(total) / 1000.0 - 1.0)
    except Exception:
        log.debug("server_log_recovery: the log read after the call failed", exc_info=True)
        return None
    session._server_log_read = {"mono": time.monotonic(), "server": server.name, "result": r}
    return r["kinds"] if r is not None else None


def after_call(session) -> list:
    """The lines said under the turn from the read the ledger made for this call (none: nothing to say)."""
    hit, session._server_log_read = getattr(session, "_server_log_read", None), None
    if not hit or not hit.get("result") or time.monotonic() - hit["mono"] > CACHE_S:
        return []
    r, name, out = hit["result"], hit["server"], []
    if r["trim"]:
        out.append(f"the log of {name} shows {r['trim']['say']}")
    if r["spill"]:
        out.append(f"the log of {name} shows {r['spill']['say']}")
    out += [c["line"] for c in r["crashes"] if c.get("line")]
    if r["cut"] and not r["trim"]:
        out.append(f"the log of {name} shows {r['cut']['say']}")
    return out
