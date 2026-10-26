"""halo_harness.providers.ollama_discover_probe -- Halo 3.2.3.0 R2: the
probing half of `providers.ollama_discover`: one candidate confirmed by
`/api/version` then `/api/tags`, the thread pool that asks them all
inside the caller's budget, this machine's door list, and the network
pass (the sweep from `ollama_discover_net`, then the same confirmation).
"""

from __future__ import annotations

import concurrent.futures as cf
import socket
import time
import urllib.parse
from typing import Optional

from halo_harness.providers import ollama_discover_net as net
from halo_harness.providers.ollama_discover import (LOCAL_THREADS, TAGS_TIMEOUT_S, VERSION_TIMEOUT_S, Found,
                                                    _ported, _url)

def _confirm(url: str, where: str, name: str) -> Optional[Found]:
    from halo_harness.providers.ollama import OllamaHost, fetch_tags, probe_version
    host = OllamaHost(name=name or "found", url=url)
    info = probe_version(host, timeout=VERSION_TIMEOUT_S)
    if not isinstance(info, dict) or not info.get("version"):
        return None
    tags = fetch_tags(host, timeout=TAGS_TIMEOUT_S) or {}
    models, digests = [], []
    for row in tags.get("models") or [] if isinstance(tags, dict) else []:
        model = (row.get("model") or row.get("name")) if isinstance(row, dict) else None
        if isinstance(model, str) and model:
            models.append(model)
            digests.append(str(row.get("digest") or ""))
    return Found(url=url, name=name, version=str(info["version"]), models=models, where=where,
                 digests=tuple(sorted(digests)))


def _confirm_lan(ip: str, port: int) -> Optional[Found]:
    row = _confirm(_url(ip, port), "lan", "")
    if row is not None:
        row.name = _ported(net.reverse_name(ip) or f"ollama-{ip.rsplit('.', 1)[-1]}", port)
    return row


def _wsl_rows(ports: tuple) -> "list[Found]":
    addr, name = net.wsl_door()
    return [r for r in (_confirm(_url(addr, p), "wsl", _ported(name, p)) for p in ports) if r] if addr else []


def _pool(jobs: list, budget_s: float, threads: int = LOCAL_THREADS) -> "list[Found]":
    if not jobs:
        return []
    ex = cf.ThreadPoolExecutor(max_workers=min(threads, len(jobs)), thread_name_prefix="ollama-discover")
    try:
        futures = [ex.submit(fn, *args) for fn, args in jobs]
        done, _ = cf.wait(futures, timeout=max(0.0, budget_s))
        rows: "list[Found]" = []
        for f in futures:
            if f in done and f.exception() is None and f.result():
                result = f.result()
                rows.extend(result if isinstance(result, list) else [result])
        return rows
    finally:
        ex.shutdown(wait=False, cancel_futures=True)


def _local_jobs(ports: tuple, env, test_mode: bool) -> list:
    jobs: list = []
    raw = (env.get("OLLAMA_HOST") or "").strip() if not test_mode else ""
    if raw:
        from halo_harness.providers.ollama import _normalize_host_url
        parsed = urllib.parse.urlparse(_normalize_host_url(raw))
        host = parsed.hostname or "127.0.0.1"
        host = "127.0.0.1" if host == "0.0.0.0" else host
        try:
            port = parsed.port or 11434
        except ValueError:
            port = 11434
        jobs.append((_confirm, (_url(host, port), "env", _ported(net.safe_name(host) or "env", port))))
    for p in ports:
        for addr in ("127.0.0.1", "::1"):
            jobs.append((_confirm, (_url(addr, p), "loopback", _ported("local", p))))
    if not test_mode:
        from halo_harness.fleet.hub import lan_address
        own = lan_address()
        if own and not own.startswith("127."):
            me = net.safe_name(socket.gethostname()) or "this-machine"
            jobs.extend((_confirm, (_url(own, p), "self", _ported(me, p))) for p in ports)
        jobs.extend((_confirm, (_url("host.docker.internal", p), "docker", _ported("docker", p))) for p in ports)
        jobs.append((_wsl_rows, (ports,)))
    return jobs


def _lan_rows(ports: tuple, budget_s: float, subnets, own_subnet: bool, notes: list, on_progress) -> "list[Found]":
    start = time.monotonic()
    from halo_harness.fleet.hub import lan_address
    networks, more = net.sweep_networks(lan_address() if own_subnet else None, subnets, own_subnet=own_subnet)
    notes.extend(more)
    if not networks:
        notes.append("no network to scan: no LAN address here and ollama.discover.subnets is empty")
        return []
    if on_progress is not None:
        on_progress(f"scanning {', '.join(str(n) for n in networks)} ...")
    sweep_deadline = start + max(budget_s * 0.5, budget_s - VERSION_TIMEOUT_S - TAGS_TIMEOUT_S)
    responders = net.sweep(networks, ports, deadline=sweep_deadline)
    return _pool([(_confirm_lan, r) for r in responders], start + budget_s - time.monotonic())
