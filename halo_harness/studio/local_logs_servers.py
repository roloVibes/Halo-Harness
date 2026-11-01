"""halo_harness.studio.local_logs_servers -- Halo 3.3.8.0 R2: Local -> Logs for a local server (llama-server, LM Studio,
mlx_lm.server) beside the Ollama hosts, the same answers studio/local_logs_api.py gives for a host (it routes here
when `<name>` is a server, ollama_steward/servers_hf.py), read-only:

    GET local/logs/servers                  {servers: [{name, runtime, source, url}]}   the page's picker
    GET local/host/<server>/log?n=&kind=    the bounded tail (server_log_hf.tail_lines), each line's group
    GET local/host/<server>/log/status      log_status_hf.status (the same keys as a host's, `runtime` beside them)
    GET local/host/<server>/log/models      per model: the last load (window per slot, layers on the GPU), the cut
                                            prompts, the error lines, "crashed here" with the fingerprint's line, and
                                            the kinds the runtime's log never prints (`not_asked`)
"""

from __future__ import annotations


def servers_list(state_dir) -> dict:
    from halo_harness.ollama_steward.servers_hf import roster
    return {"servers": [{"name": s.name, "runtime": s.runtime, "source": s.source, "url": s.url} for s in roster(state_dir)]}


def server_log(req, server, n: int, kind: str) -> "tuple[int, dict]":
    from halo_harness.ollama_steward.log_status import group_of
    from halo_harness.ollama_steward.log_status_hf import status
    from halo_harness.ollama_steward.server_log_hf import tail_lines
    from halo_harness.ollama_steward.server_rules_hf import line_time
    lines, source, why = tail_lines(server, n)
    rows = [{"text": x[:2000], "group": group_of(x), "at": line_time(x)} for x in lines]
    if kind != "all":
        rows = [r for r in rows if r["group"] == kind]
    st = status(req.state_dir, server)
    return 200, {"host": server.name, "server": True, "runtime": server.runtime, "lines": rows, "source": source,
                 "why": why, "n": n, "kind": kind, "cli": f"halo local log {server.name} -n {n}",
                 "tail_cli": st.get("tail_cli") or "", "path": st.get("path") or source}


def server_status(req, server) -> "tuple[int, dict]":
    from halo_harness.ollama_steward.log_status_hf import status
    return 200, status(req.state_dir, server)


def server_models(req, server) -> "tuple[int, dict]":
    from halo_harness.ollama_steward.fingerprints import read
    from halo_harness.ollama_steward.server_events import read_events
    from halo_harness.ollama_steward.server_rules_hf import not_asked
    evs = read_events(req.state_dir, since=86400.0, host=server.name)
    names: list = []
    for m in [server.model] + [e.get("model") for e in evs]:
        if m and m not in names:
            names.append(m)
    fps = read(req.state_dir, host=server.name)
    rows = []
    for m in names:
        mine = [e for e in evs if e.get("model") == m]
        load = next((e for e in reversed(mine) if e.get("kind") == "load-result"), None)
        d = (load or {}).get("data") or {}
        off, lay = d.get("offloaded"), d.get("layers")
        spilled = isinstance(off, int) and isinstance(lay, int) and off < lay
        fp = next((f for f in fps if f.get("model") == m), None)
        rows.append({"model": m, "load": {
            "state": "unverified" if load is None else ("spilled" if spilled else "fits"), "line": (load or {}).get("say")
            or "no load seen in its log yet", "layers": [off, lay] if isinstance(lay, int) else None, "splits": None,
            "kv_gpu_mib": None, "kv_cpu_mib": None, "on_gpu_pct": round(100.0 * off / lay) if isinstance(off, int) and lay
            else None, "tok_s": None, "window": d.get("window"), "at": (load or {}).get("at"), "source": "its log"},
            "truncations": [{"at": e.get("at"), "say": e.get("say"), "limit": (e.get("data") or {}).get("limit"),
                             "prompt": (e.get("data") or {}).get("prompt"), "window_sent": (e.get("data") or {}).get("window")}
                            for e in mine if e.get("kind") == "prompt-trimmed"][-10:],
            "errors": [{"at": e.get("at"), "kind": e.get("kind"), "say": e.get("say")} for e in mine
                       if e.get("severity") == "error"][-10:],
            "crashed": {"line": fp.get("line"), "signature": fp.get("signature"), "at": fp.get("at"),
                        "count": fp.get("count")} if fp else None})
    return 200, {"host": server.name, "runtime": server.runtime, "not_asked": not_asked(server.runtime), "models": rows,
                 "session": {"id": None, "since": None}}
