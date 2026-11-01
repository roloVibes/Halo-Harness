"""halo_harness.ollama_steward.log_status_hf -- Halo 3.3.8.0 R2: is a local server's log live, the sibling of
log_status.status for llama-server, LM Studio and mlx_lm.server (the same keys, so the Logs page, the Hosts card and
`halo local log` show one status line for every server):

    status(state_dir, server, *, now=None, root=None) -> {host, runtime, state, path, paths, last_line_at, why, debug,
        readable, rung, tail_cli, halo_cli, debug_action, line}
    debug_action(server) -> how to get more detail from that runtime, said as a stated action (Halo never sets it)

The states: live / stale / quiet as for Ollama (the ledger's calls to the server's url against the log's newest line;
llama-server prints no timestamps, so the file's modification time stands in for its newest line), `unreadable` (a
server Halo did not start and no `log` path: "the server log of <name> is not readable from here: start it with `halo
local serve` or set `log`"), `missing` (LM Studio with no server-logs folder yet), `remote-no-ssh` (on that machine,
no halo host there to read it).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Optional

LIVE_SLACK_S = 60.0
RECENT_S = 900.0


def debug_action(server) -> str:
    rt, name = getattr(server, "runtime", None) or "llama-server", getattr(server, "name", "the server")
    if rt == "lmstudio":
        return (f"turn on verbose logging in LM Studio on {name} (Developer -> the server's settings -> Verbose "
                "Logging); Halo reads the newer lines, it never changes the setting")
    if rt == "mlx":
        return f"start mlx_lm.server on {name} with --log-level DEBUG (Halo never restarts it); turn it off after"
    return (f"start llama-server on {name} with --verbose and --log-file <path>, then set that path as `log` on its "
            "huggingface.local_servers entry (Halo never restarts it); turn --verbose off after")


def _newest_call(state_dir, server) -> Optional[float]:
    from halo_harness.ollama_steward.ledger import parse_at, read_calls
    from halo_harness.ollama_steward.servers_hf import _same
    rows = [x for x in read_calls(state_dir, since=RECENT_S * 4) if _same((x.get("host") or {}).get("url"), server.url)]
    times = [t for t in (parse_at(x.get("at")) for x in rows) if t is not None]
    return max(times) if times else None


def _tail_cli(path: Path) -> str:
    return f'Get-Content -Wait -Tail 50 "{path}"' if sys.platform.startswith("win") else f"tail -f {path}"


def status(state_dir, server, *, now: Optional[float] = None, root=None) -> dict:
    from halo_harness.ollama_steward.log_status import ago
    from halo_harness.ollama_steward.log_tail import local_tail
    from halo_harness.ollama_steward.server_log_hf import source_for_server
    from halo_harness.ollama_steward.server_rules_hf import line_time
    from halo_harness.ollama_steward.servers_hf import is_local
    now = time.time() if now is None else now
    st: dict = {"host": server.name, "runtime": server.runtime, "source": server.source, "state": None, "path": "",
                "paths": [], "last_line_at": None, "why": "", "debug": False, "readable": False,
                "rung": "local" if is_local(server) or server.log else "remote", "tail_cli": "",
                "halo_cli": f"halo local log {server.name} --follow", "debug_action": debug_action(server)}
    target, why = source_for_server(server, root=root)
    if target is None and st["rung"] == "remote":
        from halo_harness.ollama_steward.host_reads_hf import client_for, server_row
        c = client_for(server)
        row = server_row(server, c) if c is not None else None
        if row is not None:
            log = row.get("log") or {}
            st.update(rung="host", via="host", path=f"via host {c.addr}" + (f": {log['path']}" if log.get("path") else ""),
                      state=log.get("state") or "unreadable", why=str(log.get("why") or ""),
                      readable=bool(log.get("readable")), last_line_at=log.get("last_line_at"))
        else:
            st.update(state="remote-no-ssh", why=why or "")
    elif target is None:
        st.update(state="missing" if server.runtime == "lmstudio" else "unreadable", why=why or "")
    else:
        rows = local_tail(target, 400)
        st.update(path=str(target), paths=[str(target)], readable=True, tail_cli=_tail_cli(target),
                  debug=any("[DEBUG]" in x or " DEBUG " in x for x in rows))
        times = [t for t in (line_time(x) for x in rows) if t is not None]
        try:
            st["last_line_at"] = max(times) if times else (target.stat().st_mtime if rows else None)
        except OSError:
            st.update(readable=False, state="unreadable", why=f"{target} could not be read")
    if st["state"] is None:
        call, last = _newest_call(state_dir, server), st.get("last_line_at")
        recent = call is not None and now - call <= RECENT_S
        if recent and last is not None and last >= call - LIVE_SLACK_S:
            st["state"] = "live"
        elif recent:
            st.update(state="stale", why=f"the ledger has calls the log never saw (the newest call {ago(now - call)} ago"
                      + (f", the newest log line {ago(now - last)} ago)" if last else ", nothing in the log)"))
        elif last is not None and now - last <= RECENT_S:
            st["state"] = "live"
        else:
            st.update(state="quiet", why="no calls and no log lines in the last 15 minutes")
    last = st.get("last_line_at")
    head = {"remote-no-ssh": "on that machine"}.get(st["state"], st["state"])
    st["line"] = (head + (f", last line {ago(now - last)} ago" if isinstance(last, (int, float)) else "") +
                  (" · debug: on" if st["debug"] else "") + (f" · {st['path']}" if st["path"] else "") +
                  (f" ({st['why']})" if st["why"] and st["state"] != "live" else ""))
    return st
