"""halo_harness.doctor_local_servers -- Halo 3.3.8.0 R2: `halo doctor --local`'s line per local server (llama-server,
LM Studio, mlx_lm.server; ollama_steward/servers_hf.py): whether the steward can read its log, from the status line
the Logs page shows (ollama_steward/log_status_hf.py). A server whose log cannot be read from here is a WARN naming
how to make it readable ("start it with `halo local serve` or set `log`"); a readable one is an OK line with its
state. No request: files only.

    server_steps(state_dir, *, servers=None) -> [{step, ok, reason, elapsed_s, tag?}]
"""

from __future__ import annotations

from typing import Optional


def server_steps(state_dir, *, servers: Optional[list] = None) -> list:
    from halo_harness.doctor_local_ids import _step
    try:
        from halo_harness.ollama_steward.log_status_hf import status
        from halo_harness.ollama_steward.servers_hf import roster
        rows = roster(state_dir) if servers is None else servers
    except Exception:
        return []
    out = []
    for s in rows:
        try:
            st = status(state_dir, s)
        except Exception as e:
            out.append(_step(f"server log {s.name}", True, f"{s.name}: its log status was not read ({e})", "WARN"))
            continue
        head = f"{s.name} ({s.runtime or 'a local server'})"
        if st["state"] in ("unreadable", "missing", "remote-no-ssh"):
            out.append(_step(f"server log {s.name}", True, f"{head}: the steward cannot read its log -- {st['line']}", "WARN"))
        else:
            out.append(_step(f"server log {s.name}", True, f"{head}: server log {st['line']}"))
    return out
