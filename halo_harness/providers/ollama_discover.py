"""halo_harness.providers.ollama_discover -- Halo 3.2.3.0 R2: the Ollama
servers are found, not typed. `discover("local")` asks this machine's own
doors (`OLLAMA_HOST`, 127.0.0.1 and [::1] on `ollama.discover.ports`, this
machine's LAN address, `host.docker.internal`, the WSL door), each
confirmed by `/api/version` (1.5 s) then `/api/tags` (3 s), sixteen in
parallel, about 4 s in all. `discover("lan")` sweeps the /24 of
`fleet.hub.lan_address()` plus `ollama.discover.subnets` (a 10 s cap) and
confirms the responders the same way; `"all"` is both. Nothing in Halo
runs the network scan on its own: a command or a wizard button asks.

A server reached by two of this machine's doors is one row (the loopback
address kept): the same port, version and model list with the same
digests. Network rows are merged only by address. A row whose url
matches an `ollama.hosts` entry is `configured` and carries that entry's
name. `add_hosts` writes the chosen new rows as `ollama.hosts` entries;
their models are `ol:<model>@<name>` at once.

Under `BRIDGE_TEST_NO_BACKGROUND_NET=1` the network scope returns no rows
and one note, and the local scope asks only the loopback addresses on the
ports `ollama.discover.ports` names (the default port is not asked then).
"""

from __future__ import annotations

import os
import threading
import time
import urllib.parse
from dataclasses import dataclass, field
from typing import Callable, Optional

from halo_harness.providers import ollama_discover_net as net

DEFAULT_DISCOVER_PORTS = (11434,)
LOCAL_BUDGET_S = 4.0
LAN_BUDGET_S = 10.0
VERSION_TIMEOUT_S = 1.5
TAGS_TIMEOUT_S = 3.0
LOCAL_THREADS = 16
CACHE_TTL_S = 60.0
TEST_LAN_NOTE = "the network scan is off in tests"
OFFLINE_LAN_NOTE = "offline mode is on, so the network scan is off"
NOT_ADDED_HINT = "found, not added (halo ollama discover --add)"
_WHERE_RANK = {"loopback": 0, "env": 1, "self": 2, "docker": 3, "wsl": 4, "lan": 5}
_LOOPBACK = {"127.0.0.1", "localhost", "::1", "0.0.0.0"}


@dataclass
class Found:
    url: str
    name: str
    version: Optional[str]
    models: "list[str]"
    configured: bool = False
    where: str = "loopback"  # "env" | "loopback" | "self" | "docker" | "wsl" | "lan"
    digests: tuple = field(default=(), repr=False)
    # the other `(host, port)` keys this same server answered on (merged by `dedupe`)
    aliases: list = field(default_factory=list, repr=False)

    def as_dict(self) -> dict:
        return {"url": self.url, "name": self.name, "version": self.version, "models": list(self.models),
                "configured": self.configured, "where": self.where}


class DiscoverResult(list):
    """The `Found` rows, plus `notes`: one line per thing worth saying
    about the scan itself (a skipped subnet, the scan off in tests)."""

    def __init__(self, rows=(), notes=()):
        super().__init__(rows)
        self.notes = list(notes)


def _test_mode() -> bool:
    from halo_harness.config.paths import background_net_disabled
    return background_net_disabled()


def discover_ports(*, test_mode: Optional[bool] = None) -> tuple:
    """`ollama.discover.ports` (a config list of ints), else `(11434,)`;
    in tests only the configured ports."""
    from halo_harness.theme import get_config_value
    raw = get_config_value("ollama.discover.ports", default=None)
    ports: list = []
    for p in raw if isinstance(raw, list) else []:
        if isinstance(p, bool):
            continue
        try:
            n = int(p)
        except (TypeError, ValueError):
            continue
        if 0 < n < 65536 and n not in ports:
            ports.append(n)
    if ports:
        return tuple(ports)
    return () if (_test_mode() if test_mode is None else test_mode) else DEFAULT_DISCOVER_PORTS


def discover_subnets() -> "list[str]":
    from halo_harness.theme import get_config_value
    raw = get_config_value("ollama.discover.subnets", default=None)
    if isinstance(raw, str):
        raw = raw.split(",")
    return [str(s).strip() for s in raw if str(s).strip()] if isinstance(raw, list) else []


def _url(host: str, port: int) -> str:
    return f"http://[{host}]:{port}" if ":" in host else f"http://{host}:{port}"


def url_key(url: str) -> tuple:
    """`(host, port)` for comparing two urls; every loopback spelling is one."""
    try:
        parsed = urllib.parse.urlparse(url if "://" in url else f"http://{url}")
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError:
        return (url, 0)
    host = (parsed.hostname or "").lower()
    return ("loopback" if host in _LOOPBACK or host.startswith("127.") else host, port)


def _ported(name: str, port: int) -> str:
    return name if port == 11434 else f"{name}-{port}"


def dedupe(rows: "list[Found]") -> "list[Found]":
    """One row per server: the same address always; the same port +
    version + model list + digests too when neither row came from the
    network scan (two machines may well serve the same models)."""
    kept: "list[Found]" = []
    for row in sorted(rows, key=lambda r: _WHERE_RANK.get(r.where, 9)):
        keys = {url_key(row.url), *row.aliases}
        match = next((k for k in kept if keys & {url_key(k.url), *k.aliases}), None)
        if match is None:
            match = next((k for k in kept if "lan" not in (k.where, row.where) and row.models
                          and url_key(k.url)[1] == url_key(row.url)[1]
                          and (k.version, sorted(k.models), k.digests)
                          == (row.version, sorted(row.models), row.digests)), None)
        if match is None:
            kept.append(row)
        else:
            match.aliases = sorted({*match.aliases, *keys} - {url_key(match.url)})
    return kept


def _unique(name: str, taken: set) -> str:
    base, n, candidate = name or "ollama", 2, name or "ollama"
    while candidate.lower() in taken:
        candidate, n = f"{base}-{n}", n + 1
    return candidate


def _mark_configured(rows: "list[Found]", env, test_mode: bool) -> None:
    from halo_harness.providers.ollama import resolve_ollama_hosts
    index: dict = {}
    hosts = resolve_ollama_hosts(env)
    for h in hosts:
        key = url_key(h.url)
        index.setdefault(key, h.name)
        if not test_mode and key[0] != "loopback" and not key[0].replace(".", "").isdigit():
            for ip in net.resolve_ipv4(key[0]):
                index.setdefault((ip, key[1]), h.name)
    taken = {h.name.lower() for h in hosts}
    for row in rows:
        name = next((index[k] for k in (url_key(row.url), *row.aliases) if k in index), None)
        if name:
            row.configured, row.name = True, name
    for row in rows:
        if not row.configured:
            row.name = _unique(row.name, taken)
            taken.add(row.name.lower())


def discover(scope: str = "local", budget_s: Optional[float] = None, env=None, state_dir=None, *,
             ports=None, subnets=None, own_subnet: bool = True,
             on_progress: "Optional[Callable[[str], None]]" = None) -> DiscoverResult:
    """The servers in `scope` ("local", "lan" or "all"), never raising."""
    from halo_harness.providers.ollama_discover_probe import _lan_rows, _local_jobs, _pool
    env = env if env is not None else os.environ
    test_mode = _test_mode()
    notes: "list[str]" = []
    ports = tuple(int(p) for p in ports) if ports else discover_ports(test_mode=test_mode)
    if not ports:
        notes.append("no port to probe: in tests only ollama.discover.ports is asked")
    rows: "list[Found]" = []
    if scope in ("local", "all") and ports:
        rows.extend(_pool(_local_jobs(ports, env, test_mode), budget_s or LOCAL_BUDGET_S))
    if scope in ("lan", "all"):
        from halo_harness.providers.http import offline_mode_enabled
        if test_mode:
            notes = [TEST_LAN_NOTE] if scope == "lan" else notes + [TEST_LAN_NOTE]
        elif offline_mode_enabled():
            notes.append(OFFLINE_LAN_NOTE)
        elif ports:
            subnets = discover_subnets() if subnets is None else list(subnets)
            rows.extend(_lan_rows(ports, budget_s or LAN_BUDGET_S, subnets, own_subnet, notes, on_progress))
    rows = dedupe(rows)
    _mark_configured(rows, env, test_mode)
    return DiscoverResult(rows, notes)


_cache_lock = threading.Lock()
_cache: "Optional[tuple]" = None  # (monotonic ts, key, DiscoverResult)


def discover_local_cached(*, env=None, force: bool = False) -> DiscoverResult:
    """`discover("local")` behind a 60 s in-process cache (like the HF
    probe's), keyed by the ports and the configured host urls."""
    global _cache
    from halo_harness.providers.ollama import resolve_ollama_hosts
    key = (discover_ports(), _test_mode(), tuple(h.url for h in resolve_ollama_hosts(env)))
    now = time.monotonic()
    with _cache_lock:
        if not force and _cache is not None and _cache[1] == key and now - _cache[0] < CACHE_TTL_S:
            return DiscoverResult(_cache[2], _cache[2].notes)
    result = discover("local", env=env)
    with _cache_lock:
        _cache = (now, key, result)
    return result


def reset_discover_cache() -> None:
    global _cache
    with _cache_lock:
        _cache = None


def add_hosts(found, names=None, state_dir=None) -> "list[str]":
    """`ollama_discover_hosts.add_hosts` (kept there with the renderings)."""
    from halo_harness.providers.ollama_discover_hosts import add_hosts as _add_hosts
    return _add_hosts(found, names, state_dir)
