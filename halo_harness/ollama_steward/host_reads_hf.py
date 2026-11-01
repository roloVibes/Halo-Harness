"""halo_harness.ollama_steward.host_reads_hf -- Halo 3.3.8.0 R2: a local server on another machine read through the
paired `halo host` there (the host's card lists its machine's servers, host/routes_view.py), under this machine's
name for the server. Sizes and lines only: the host never sends a request body.

    client_for(server) -> the HostClient of the halo host on the server's machine | None
    server_row(server) -> the host card's row for the server on that port | None
    tail_via_host(server, n) -> (lines, "via host <addr>: <source>", why) | None   None: no paired host there
    events_via_host(server, since) -> [event] under this machine's name for the server
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Optional


def client_for(server):
    from halo_harness.ollama_steward.host_client import _addr_port, _usable, any_paired, for_host
    from halo_harness.ollama_steward.servers_hf import is_local
    if server is None or is_local(server) or not any_paired():
        return None
    addr, _port = _addr_port(getattr(server, "url", ""), 80)
    c = for_host(SimpleNamespace(url=f"http://{addr}:11434", name=getattr(server, "name", "")))
    return c if _usable(c) else None


def server_row(server, c=None) -> Optional[dict]:
    from halo_harness.ollama_steward.host_client import HostError, _addr_port
    c = c or client_for(server)
    if c is None:
        return None
    port = _addr_port(getattr(server, "url", ""), 80)[1]
    try:
        rows = [r for r in c.card().get("servers") or [] if isinstance(r, dict)]
    except HostError:
        return None
    return next((r for r in rows if int(r.get("port") or 0) == port), None)


def tail_via_host(server, n: int = 200) -> "Optional[tuple[list, str, Optional[str]]]":
    from halo_harness.ollama_steward.host_client import HostError
    c = client_for(server)
    if c is None:
        return None
    row = server_row(server, c)
    if row is None:
        return [], f"via host {c.addr}", f"the halo host at {c.addr} lists no local server on that port"
    try:
        got = c.tail(n, host=str(row.get("name") or ""))
    except HostError as e:
        return [], f"via host {c.addr}", str(e)
    return list(got.get("lines") or []), f"via host {c.addr}: {got.get('source') or 'its server log'}", got.get("why")


def events_via_host(server, since=86400.0) -> list:
    from halo_harness.ollama_steward.host_client import HostError
    c = client_for(server)
    row = server_row(server, c) if c is not None else None
    if row is None:
        return []
    try:
        rows = c.events(since=since).get("events") or []
    except HostError:
        return []
    want = str(row.get("name") or "").lower()
    return [{**e, "host": server.name, "from_host": e.get("host"), "via": "host"} for e in rows
            if isinstance(e, dict) and str(e.get("host") or "").lower() == want]
