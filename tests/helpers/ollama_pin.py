"""tests.helpers.ollama_pin -- Halo 3.3.5.0 R3: the `OLLAMA_HOST` a test run
uses (tests/helpers/chrome_driver.driver_env for every Chrome rig,
tests/run_all.py for the whole run, tests/test_no_local_reads.py pins it).
The value is kept when it names a loopback fake (127.x on a port that is not
Ollama's own 11434); anything else -- unset, 0.0.0.0, this machine's own
server, a LAN address -- becomes a refused port, so a rig's catalog read
never reaches a real Ollama."""
from __future__ import annotations

import urllib.parse

REFUSED_OLLAMA = "http://127.0.0.1:9"


def pinned_ollama_host(value: "str | None") -> str:
    raw = str(value or "").strip()
    if not raw:
        return REFUSED_OLLAMA
    try:
        p = urllib.parse.urlparse(raw if "://" in raw else f"http://{raw}")
        name, port = (p.hostname or "").lower(), p.port
    except ValueError:
        return REFUSED_OLLAMA
    return raw if name.startswith("127.") and port not in (None, 11434) else REFUSED_OLLAMA
