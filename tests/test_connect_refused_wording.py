"""tests.test_connect_refused_wording -- 3.6.0.0 fix pass: a server that is
simply not running (the connection is REFUSED: the host answered, nothing
listens on that port) must not be reported as a network, DNS or VPN problem.
The line names host:port and, for a local or LAN address, says to start the
model server (Ollama: `ollama serve`). A name that does not resolve keeps the
DNS/VPN wording. Every connect failure keeps CONNECT_FAILURE_MARKER, which the
agent loop's no-retry rule matches. Loopback only; no real server is reached.
"""
from __future__ import annotations

import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()


def _dead_loopback_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@test
def test_a_refused_local_connection_says_nothing_listens_and_to_start_the_server(ctx: Ctx):
    from halo_harness.providers.http import format_connect_error, is_connect_failure_message
    err = ConnectionRefusedError(10061, "No connection could be made because the target machine actively refused it")
    for host in ("127.0.0.1", "localhost", "::1", "gpu-box", "gpu-box.local"):
        msg = format_connect_error(host, err, port=11434)
        ctx.check(f"{host}: no DNS/VPN wording for a refusal, got {msg!r}", "DNS or VPN" not in msg)
        ctx.check(f"{host}: names host and port, got {msg!r}", f"{host}:11434" in msg)
        ctx.check(f"{host}: says nothing is listening, got {msg!r}", "nothing is listening" in msg)
        ctx.check(f"{host}: says how to start Ollama, got {msg!r}", "ollama serve" in msg)
        ctx.check(f"{host}: keeps the connect-failure marker, got {msg!r}", is_connect_failure_message(msg))


@test
def test_a_refused_public_host_says_nothing_listens_without_the_ollama_hint(ctx: Ctx):
    from halo_harness.providers.http import format_connect_error, is_connect_failure_message
    msg = format_connect_error("api.example.com", ConnectionRefusedError(111, "Connection refused"), port=443)
    ctx.check(f"no DNS/VPN wording, got {msg!r}", "DNS or VPN" not in msg)
    ctx.check(f"says nothing is listening at host:port, got {msg!r}",
              "nothing is listening" in msg and "api.example.com:443" in msg)
    ctx.check(f"no Ollama hint for a public host, got {msg!r}", "ollama" not in msg.lower())
    ctx.check(f"keeps the marker, got {msg!r}", is_connect_failure_message(msg))


@test
def test_a_name_that_does_not_resolve_keeps_the_dns_wording(ctx: Ctx):
    from halo_harness.providers.http import format_connect_error
    msg = format_connect_error("gpu-box", socket.gaierror(11001, "getaddrinfo failed"), port=11434)
    ctx.check(f"DNS/VPN wording kept for a lookup failure, got {msg!r}", "DNS or VPN" in msg)
    ctx.check(f"no 'nothing is listening' for a lookup failure, got {msg!r}", "nothing is listening" not in msg)


@test
def test_open_upstream_to_a_dead_loopback_port_reports_nothing_listening(ctx: Ctx):
    from halo_harness.providers.http import UpstreamConnectError, open_upstream
    port = _dead_loopback_port()
    try:
        conn = open_upstream("127.0.0.1", port, False, connect_timeout=8)
        conn.close()
        ctx.check("expected UpstreamConnectError for a dead port", False)
    except UpstreamConnectError as e:
        msg = str(e)
        ctx.check(f"no DNS/VPN wording, got {msg!r}", "DNS or VPN" not in msg)
        ctx.check(f"names 127.0.0.1:{port}, got {msg!r}", f"127.0.0.1:{port}" in msg)
        ctx.check(f"says to start Ollama, got {msg!r}", "nothing is listening" in msg and "ollama serve" in msg)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
