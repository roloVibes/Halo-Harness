"""halo_harness.providers.ollama_guard -- Halo 3.3.5.0 R3: what the test flag
keeps away from a real Ollama.

Under `BRIDGE_TEST_NO_BACKGROUND_NET=1` (every test run sets it):

- `skip_default(host)`: True for the host `resolve_ollama_hosts` made up from
  `OLLAMA_HOST` / 127.0.0.1:11434 (`OllamaHost.synthesized`, `ollama.hosts`
  empty). Every catalog reader asks it first -- the model list behind Roles,
  Setup's state read, `halo local`'s view, the catalog refresh, Local's Hosts
  and Models pages -- so a test that leaves `OLLAMA_HOST` unset (or pointing
  at this machine's own server) never reads that server's `/api/tags`. A
  test reads a fake through a configured `ollama.hosts` entry instead.
- `control_blocked(host)`: the reason a pull, delete, copy, show, twin or
  `/api/ps` read is not sent, or None: the made-up default host, and any
  address that is not a loopback fake (a test's fakes listen on 127.0.0.1:0,
  never Ollama's own 11434).

Without the flag both answer "go ahead": nothing here gates a real run.
"""

from __future__ import annotations

import urllib.parse
from typing import Optional

OLLAMA_PORT = 11434


def flag_on() -> bool:
    from halo_harness.config.paths import background_net_disabled
    return background_net_disabled()


def skip_default(host) -> bool:
    return bool(getattr(host, "synthesized", False)) and flag_on()


def control_blocked(host) -> Optional[str]:
    if not flag_on() or host is None:
        return None
    if getattr(host, "synthesized", False):
        return "the test flag (BRIDGE_TEST_NO_BACKGROUND_NET) keeps the default host out of reach"
    try:
        parsed = urllib.parse.urlparse(str(getattr(host, "url", "") or ""))
        name, port = (parsed.hostname or "").lower(), parsed.port
    except ValueError:
        return "the test flag: the host's address does not parse"
    if not (name.startswith("127.") or name in ("localhost", "::1")) or port in (None, OLLAMA_PORT):
        return f"the test flag (BRIDGE_TEST_NO_BACKGROUND_NET) reaches loopback fakes only, not {name}:{port}"
    return None


__all__ = ["OLLAMA_PORT", "control_blocked", "flag_on", "skip_default"]
