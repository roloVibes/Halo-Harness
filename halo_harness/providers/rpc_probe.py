"""halo_harness.providers.rpc_probe -- Halo 3.3.8.0 R1: the RPC-port probe, a sibling of `providers.
ollama_discover_probe` (that one confirms Ollama's API; this one asks whether a llama.cpp `rpc-server` port takes a TCP
connect, and how long the connect took). docs/POOL.md "Scan".

    probe(host, port, *, tries=3, timeout=1.0) -> {host, port, alive, rtt_ms, error, wifi_suspect, line}
        a TCP connect (resolved first, so the time is the connect's own round trip, not DNS), the fastest of `tries`
        after one connect that is not counted (it pays for ARP and the OS's first use);
        "Wi-Fi?" past WIFI_MS (10 ms): a wired LAN connects in well under a millisecond or two
    sweep(port, *, subnets=None, own_subnet=True, budget_s=10.0) -> {candidates [probe row + name], networks, notes}
        `ollama_discover_net.sweep` over the /24 of this machine's LAN address plus `subnets`, on the RPC port, then a
        probe of each responder; explicit action only (a command, a button), never on a page load

What a connect's time can tell: the round trip to that machine's network stack right now (a Wi-Fi hop shows as
milliseconds and jitter). What it cannot: the link's bandwidth, whether the far end is rpc-server or something else on
that port, or the adapter type -- the host card's `link` (local_pool/link.py) says that, and it wins.

Every connect passes `_gate` first: under `network.offline` only loopback, a private address, a local name (`.local`,
a bare single label) or an allow-listed host is asked (providers/http.allowlisted_local_hosts includes the pool's
members). Under the test flag (BRIDGE_TEST_NO_BACKGROUND_NET) the network scan is off unless SEAMS["sweep"] stands in
for it; SEAMS["own"] stands in for this machine's address. Never raises.
"""

from __future__ import annotations

import os
import socket
import threading
import time
from typing import Optional

SEAMS: dict = {}  # "sweep": fn(networks, ports, deadline) -> [(ip, port)], "own": fn() -> address | None
WIFI_MS = 10.0
CONNECT_TIMEOUT_S = 1.0
TEST_NOTE = "the network scan is off in tests"
OFFLINE_NOTE = "offline mode is on, so the network scan is off"


def _gate(host: str) -> Optional[str]:
    """None when `host` may be asked; else the one line saying why not (offline mode)."""
    from halo_harness.providers import http as H
    if not H.offline_mode_enabled():
        return None
    if H._is_loopback_host(host) or H._is_private_ip_literal(host) or H._is_local_hostname(host):
        return None
    if host.strip().lower() in H.allowlisted_local_hosts():
        return None
    return H.format_offline_refusal(host)


def _connect_ms(addr: tuple, family: int, timeout: float, exact: bool = False) -> "tuple[bool, float, str]":
    """One connect and its time. `exact` (Windows): a blocking connect, bounded by a timer that closes the socket --
    a connect with a timeout waits in select(), which Windows rounds to its 15.6 ms timer tick, so a 0.2 ms loopback
    connect would read 15 ms ("Wi-Fi?"); a blocking one is timed to the microsecond."""
    s = socket.socket(family, socket.SOCK_STREAM)
    timer = None
    if exact:
        timer = threading.Timer(timeout, s.close)
        timer.daemon = True
        timer.start()
    else:
        s.settimeout(timeout)
    start = time.perf_counter()
    try:
        code = s.connect_ex(addr)
    except OSError as e:
        return False, (time.perf_counter() - start) * 1000.0, str(e) or type(e).__name__
    finally:
        ms = (time.perf_counter() - start) * 1000.0
        if timer is not None:
            timer.cancel()
        s.close()
    return code == 0, ms, "" if code == 0 else (_refused(code) if code else "no answer")


def _refused(code: int) -> str:
    import errno
    words = {errno.ECONNREFUSED: "connection refused", 10061: "connection refused", errno.ETIMEDOUT: "timed out",
             10060: "timed out", errno.EAGAIN: "timed out", errno.EWOULDBLOCK: "timed out", 10035: "timed out",
             errno.EHOSTUNREACH: "no route to the host", 10065: "no route to the host", 10038: "timed out", 10004: "timed out"}
    return words.get(code, f"error {code}")


def ms_word(ms: Optional[float]) -> str:
    if not isinstance(ms, (int, float)):
        return "?"
    return f"{ms:.1f} ms" if ms < 10 else f"{ms:.0f} ms"


def probe(host: str, port: int, *, tries: int = 3, timeout: float = CONNECT_TIMEOUT_S) -> dict:
    out = {"host": host, "port": int(port), "alive": False, "rtt_ms": None, "error": "", "wifi_suspect": False}
    from halo_harness.config.paths import background_net_disabled
    why = _gate(host)
    if not why and background_net_disabled() and host.strip("[]").lower() not in ("127.0.0.1", "localhost", "::1"):
        why = "not asked in tests (only 127.0.0.1 is)"  # the test flag: no name lookup, no connect beyond loopback
    if why:
        out["error"] = why
    else:
        try:
            infos = socket.getaddrinfo(host.strip("[]"), int(port), type=socket.SOCK_STREAM)
        except (OSError, UnicodeError) as e:
            infos, out["error"] = [], f"the name does not resolve ({e})"
        if infos:
            family, _t, _p, _c, addr = infos[0]
            best = None
            for i in range(max(1, tries) + 1):  # the first connect pays for ARP and first use: it is not counted
                ok, ms, err = _connect_ms(addr, family, timeout, exact=bool(i) and os.name == "nt")
                if not ok:
                    out["error"] = err
                    break
                if i:
                    best = ms if best is None else min(best, ms)
            if best is not None and not out["error"]:
                out.update(alive=True, rtt_ms=round(best, 2), wifi_suspect=best >= WIFI_MS)
    door = f"{host}:{port}"
    if out["alive"]:
        out["line"] = f"{door} answers in {ms_word(out['rtt_ms'])}" + (" -- Wi-Fi?" if out["wifi_suspect"] else "")
    else:
        out["line"] = f"{door}: no answer ({out['error'] or 'nothing listens'})"
    return out


def _own() -> Optional[str]:
    if "own" in SEAMS:
        return SEAMS["own"]()
    from halo_harness.peers.net import lan_address
    return lan_address()


def sweep(port: int, *, subnets=None, own_subnet: bool = True, budget_s: float = 10.0) -> dict:
    from halo_harness.config.paths import background_net_disabled
    from halo_harness.providers import http as H
    from halo_harness.providers import ollama_discover_net as net
    notes: "list[str]" = []
    if background_net_disabled() and "sweep" not in SEAMS:
        return {"candidates": [], "networks": [], "notes": [TEST_NOTE]}
    if H.offline_mode_enabled():
        return {"candidates": [], "networks": [], "notes": [OFFLINE_NOTE]}
    networks, more = net.sweep_networks(_own() if own_subnet else None, subnets or [], own_subnet=own_subnet)
    notes.extend(m.replace("ollama.discover.subnets", "pool.scan_subnets") for m in more)
    if not networks:
        notes.append("no network to scan: no LAN address here and pool.scan_subnets is empty")
        return {"candidates": [], "networks": [], "notes": notes}
    deadline = time.monotonic() + max(1.0, budget_s * 0.7)
    found = (SEAMS["sweep"] if "sweep" in SEAMS else net.sweep)(networks, (int(port),), deadline=deadline)
    rows = []
    for ip, p in found:
        row = probe(ip, p)
        row["name"] = None if background_net_disabled() else net.reverse_name(ip)
        rows.append(row)
    return {"candidates": rows, "networks": [str(n) for n in networks], "notes": notes}
