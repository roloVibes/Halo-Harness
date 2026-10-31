"""halo_harness.studio.local_logs_api -- Halo 3.3.6.0 R3: Local -> Logs's routes (dispatched by
studio/local_api.dispatch_local; docs/STUDIO-local.md). Read-only: a server log is read, never written, and no
host-side setting changes.

    GET local/host/<name>/log?n=200&kind=all     the bounded tail (ollama_steward/log_tail.tail_lines): {lines [{text,
                                                 group, at}], source, why, n, kind, cli, tail_cli}; kind = fit |
                                                 headroom | truncation | failure | all
    GET local/host/<name>/log/status             ollama_steward/log_status.status (read=True: a host with an ssh entry
                                                 never read is read once)
    GET local/host/<name>/log/models             per model: the last load result (providers/fit_evidence.py), the
                                                 truncations of this session (since the first ledger line of the
                                                 newest session that called the host), the error lines with times
                                                 (24 h), "crashed here" with the fingerprint's line
"""

from __future__ import annotations

import re
import urllib.parse

_LOG = re.compile(r"^local/host/(?P<name>[^/]+)/log(?:/(?P<part>status|models))?$")
KINDS = ("fit", "headroom", "truncation", "failure", "all")
MAX_N = 2000


def _host(name: str):
    from halo_harness.providers.ollama import resolve_ollama_hosts
    return next((h for h in resolve_ollama_hosts() if h.name.lower() == name.lower()), None)


def get_log(req, host):
    from halo_harness.ollama_steward.log_status import group_of, status
    from halo_harness.ollama_steward.log_tail import tail_lines
    from halo_harness.ollama_steward.server_rules import line_time, strip_prefix
    try:
        n = max(1, min(MAX_N, int(req.query.get("n") or 200)))
    except ValueError:
        return 422, {"error": "n is a number of lines", "problems": ["n: 1 to 2000"]}
    kind = str(req.query.get("kind") or "all").strip().lower()
    if kind not in KINDS:
        return 422, {"error": f"kind is one of {', '.join(KINDS)}", "problems": [f"kind: {kind!r}"]}
    lines, source, why = tail_lines(host, n)
    rows = [{"text": x[:2000], "group": group_of(x), "at": line_time(strip_prefix(x))} for x in lines]
    if kind != "all":
        rows = [r for r in rows if r["group"] == kind]
    st = status(req.state_dir, host)
    return 200, {"host": host.name, "lines": rows, "source": source, "why": why, "n": n, "kind": kind,
                 "cli": f"halo ollama log --host {host.name} -n {n}" + (f" --kind {kind}" if kind != "all" else ""),
                 "tail_cli": st.get("tail_cli") or "", "path": st.get("path") or source}


def session_since(state_dir, host) -> "tuple[float | None, str | None]":
    """(when the newest session that called `host` made its first call, its id) from the ledger's last day."""
    from halo_harness.ollama_steward.ledger import parse_at, read_calls
    lines = read_calls(state_dir, since=86400.0, host=host.name)
    sid = next((x.get("session") for x in reversed(lines) if x.get("session")), None)
    if sid is None:
        return None, None
    first = next((parse_at(x.get("at")) for x in lines if x.get("session") == sid), None)
    return first, sid


def log_models(state_dir, host) -> dict:
    from halo_harness.ollama_steward.fingerprints import read
    from halo_harness.ollama_steward.ledger import parse_at
    from halo_harness.ollama_steward.server_events import read_events
    from halo_harness.providers.fit_evidence import evidence
    from halo_harness.providers.ollama import ollama_names_match
    from halo_harness.studio.ollama_hosts_view import catalog_of
    from halo_harness.ollama_steward.host_reads import events_of  # 3.3.7.0 R1: a paired halo host's events
    evs = read_events(state_dir, since=86400.0, host=host.name) + events_of(state_dir, host, 86400.0)
    since, sid = session_since(state_dir, host)
    names: list = []
    for m in [str(r.get("model") or r.get("name") or "") for r in catalog_of(host).get("models") or [] if isinstance(r, dict)] + \
            [str(e.get("model") or "") for e in evs]:
        if m and not any(ollama_names_match(m, x) for x in names):
            names.append(m)
    fps = read(state_dir, host=host.name)
    rows = []
    for m in names:
        mine = [e for e in evs if e.get("model") and ollama_names_match(e["model"], m)]
        ev = evidence(state_dir, host.name, m)
        trims = [{"at": e.get("at"), "say": e.get("say"), **{k: (e.get("data") or {}).get(k) for k in ("limit", "prompt", "window_sent")}}
                 for e in mine if e.get("kind") == "prompt-trimmed" and (since is None or (parse_at(e.get("at")) or 0) >= since)]
        errors = [{"at": e.get("at"), "kind": e.get("kind"), "say": e.get("say")} for e in mine if e.get("severity") == "error"]
        fp = next((f for f in fps if f.get("model") and ollama_names_match(f["model"], m)), None)
        rows.append({"model": m, "load": {k: ev.get(k) for k in ("state", "line", "layers", "splits", "kv_gpu_mib", "kv_cpu_mib",
                                                                  "on_gpu_pct", "tok_s", "window", "at", "source")},
                     "truncations": trims[-10:], "errors": errors[-10:],
                     "crashed": {"line": fp.get("line"), "signature": fp.get("signature"), "at": fp.get("at"),
                                 "count": fp.get("count")} if fp else None})
    rank = lambda r: (r["crashed"] is None, not r["errors"], not r["truncations"], r["load"]["state"] == "unverified", r["model"])  # noqa: E731
    return {"host": host.name, "models": sorted(rows, key=rank), "session": {"id": sid, "since": since}}


def dispatch_logs(req):
    """The answer for a route of this file, else None."""
    m = _LOG.match(req.path)
    if not m:
        return None
    if req.method != "GET":
        return 405, {"error": "method not allowed"}
    name = urllib.parse.unquote(m.group("name"))
    host = _host(name)
    if host is None:
        return 404, {"error": f"no configured Ollama host named {name!r}"}
    part = m.group("part")
    if part == "status":
        from halo_harness.ollama_steward.log_status import status
        return 200, status(req.state_dir, host, read=True)
    if part == "models":
        return 200, log_models(req.state_dir, host)
    return get_log(req, host)
