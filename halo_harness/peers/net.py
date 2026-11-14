"""halo_harness.peers.net -- three small helpers every machine-to-machine door uses (Halo 3.0.5.0 R2 in fleet/hub.py
and fleet/cli.py; here since 3.4.0.0 C, when the fleet left the core: `halo host serve`, the pool, the probes and the
steward use them with the fleet pack off).

    lan_address()     this machine's LAN address (the interface its default route uses), else 127.0.0.1
    NetworkOffline      raised when offline mode (`network.offline`, `--offline`) keeps a listener from starting
    parse_ttl(text)   "10m" / "90s" / "1h" -> seconds (a pairing code's life)
"""

from __future__ import annotations

import re
import socket


class NetworkOffline(RuntimeError):
    pass


def lan_address() -> str:
    """This machine's LAN address (the interface its default route uses; a
    UDP socket's `connect` sends nothing, and the probe is a documentation
    address, RFC 5737), else 127.0.0.1."""
    for probe in ("192.0.2.1", "198.51.100.1"):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect((probe, 9))
                addr = s.getsockname()[0]
            if addr and not addr.startswith("0."):
                return addr
        except OSError:
            continue
    return "127.0.0.1"


def parse_ttl(text: str) -> float:
    m = re.fullmatch(r"\s*(\d+)\s*([smh]?)\s*", str(text or ""))
    if not m:
        raise ValueError(f"a ttl is a number with s, m or h (10m, 90s, 1h), got {text!r}")
    return float(m.group(1)) * {"": 1, "s": 1, "m": 60, "h": 3600}[m.group(2)]
