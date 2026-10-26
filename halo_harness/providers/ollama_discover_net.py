"""halo_harness.providers.ollama_discover_net -- Halo 3.2.3.0 R2: the
address helpers `providers.ollama_discover` builds its candidates from --
the WSL and Windows-host doors, the subnets of the network scan, the
TCP-connect sweep over them, and the reverse-DNS name of a responder.

Nothing here runs on its own: `ollama_discover.discover` calls these only
when the user asks (a command, a wizard button). The sweep is a plain TCP
connect (0.3 s) on each address and port, 64 threads, inside the caller's
budget; a responder is then confirmed through `providers.ollama`'s own
`/api/version` + `/api/tags` reads, which go through `providers.http.
open_upstream` like every other Ollama request.
"""

from __future__ import annotations

import concurrent.futures as cf
import ipaddress
import logging
import os
import platform
import re
import shutil
import socket
import subprocess
import time
from typing import Optional

log = logging.getLogger("bridge")

SWEEP_CONNECT_TIMEOUT_S = 0.3
SWEEP_THREADS = 64
REVERSE_DNS_TIMEOUT_S = 1.0
WSL_TIMEOUT_S = 3.0
# A /24 is 254 addresses; anything wider is skipped with one line.
MAX_SWEEP_HOSTS = 256


def is_wsl() -> bool:
    if os.environ.get("WSL_DISTRO_NAME"):
        return True
    try:
        return "microsoft" in platform.release().lower()
    except Exception:
        return False


def _first_ipv4(text: str) -> Optional[str]:
    for token in (text or "").split():
        try:
            if isinstance(ipaddress.ip_address(token), ipaddress.IPv4Address):
                return token
        except ValueError:
            continue
    return None


def _run(argv: list, timeout: float) -> Optional[bytes]:
    try:
        done = subprocess.run(argv, capture_output=True, timeout=max(0.1, timeout), check=False,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout if done.returncode == 0 else None


def wsl_distro_address(timeout: float = WSL_TIMEOUT_S) -> Optional[str]:
    """On Windows: the address of a RUNNING WSL distro (`wsl.exe -l
    --running -q`, then `wsl.exe -d <distro> hostname -I`), `None` when
    `wsl.exe` is missing or no distro is running -- asking only a running
    one means the scan never boots the WSL virtual machine. Both calls
    share the `timeout` cap."""
    exe = shutil.which("wsl.exe") or shutil.which("wsl")
    if not exe:
        return None
    deadline = time.monotonic() + timeout
    raw = _run([exe, "-l", "--running", "-q"], timeout)
    if not raw:
        return None
    text = raw.decode("utf-16-le", errors="ignore") if b"\x00" in raw else raw.decode("utf-8", errors="ignore")
    distros = [line.strip().strip("\x00") for line in text.splitlines() if line.strip().strip("\x00")]
    if not distros:
        return None
    out = _run([exe, "-d", distros[0], "hostname", "-I"], deadline - time.monotonic())
    return _first_ipv4(out.decode("utf-8", errors="ignore")) if out else None


def windows_host_from_resolv(path: str = "/etc/resolv.conf") -> Optional[str]:
    """Inside WSL (NAT networking): the Windows host is the nameserver
    `/etc/resolv.conf` names. `None` outside WSL or when the file has no
    usable IPv4 nameserver (a loopback one is skipped: the loopback
    candidates already cover it)."""
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2 and parts[0] == "nameserver":
                    addr = _first_ipv4(parts[1])
                    if addr and not addr.startswith("127."):
                        return addr
    except OSError:
        return None
    return None


def wsl_door() -> "tuple[Optional[str], str]":
    """`(address, name)` of the other side of WSL: the running distro on
    Windows, the Windows host inside WSL, `(None, "")` elsewhere."""
    if os.name == "nt":
        return wsl_distro_address(), "wsl"
    if is_wsl():
        return windows_host_from_resolv(), "windows"
    return None, ""


def sweep_networks(own_address: Optional[str], subnets, *, own_subnet: bool = True) -> "tuple[list, list[str]]":
    """The IPv4 networks the network scan covers: the /24 of
    `own_address` (unless `own_subnet` is False or the address is
    loopback) plus every CIDR in `subnets`; a network wider than a /24 is
    skipped with one line. Returns `(networks, notes)`."""
    networks: list = []
    notes: "list[str]" = []
    if own_subnet and own_address and not own_address.startswith("127."):
        try:
            networks.append(ipaddress.ip_network(f"{own_address}/24", strict=False))
        except ValueError:
            pass
    for raw in subnets or []:
        try:
            net = ipaddress.ip_network(str(raw).strip(), strict=False)
        except ValueError:
            notes.append(f"ollama.discover.subnets: {raw!r} is not a CIDR -- skipped")
            continue
        if not isinstance(net, ipaddress.IPv4Network):
            notes.append(f"ollama.discover.subnets: {raw} is IPv6 -- skipped (the scan covers IPv4 /24s)")
            continue
        if net.num_addresses > MAX_SWEEP_HOSTS:
            notes.append(f"ollama.discover.subnets: {raw} has {net.num_addresses:,} addresses, wider than a /24 "
                         f"-- skipped (list its /24s instead)")
            continue
        if net not in networks:
            networks.append(net)
    return networks, notes


def _tcp_open(ip: str, port: int, timeout: float) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            return s.connect_ex((ip, port)) == 0
    except OSError:
        return False


def sweep(networks, ports, *, deadline: float, threads: int = SWEEP_THREADS,
          connect_timeout: float = SWEEP_CONNECT_TIMEOUT_S) -> "list[tuple[str, int]]":
    """Every `(address, port)` in `networks` x `ports` that accepts a TCP
    connect before `deadline` (a `time.monotonic()` value). Addresses not
    reached by the deadline are left out."""
    targets = []
    for net in networks:
        hosts = list(net.hosts()) or [net.network_address]
        targets.extend((str(ip), int(p)) for ip in hosts for p in ports)
    if not targets:
        return []
    ex = cf.ThreadPoolExecutor(max_workers=max(1, min(threads, len(targets))), thread_name_prefix="ollama-sweep")
    try:
        futures = {ex.submit(_tcp_open, ip, port, connect_timeout): (ip, port) for ip, port in targets}
        done, _pending = cf.wait(futures, timeout=max(0.0, deadline - time.monotonic()))
        open_ = [futures[f] for f in done if not f.cancelled() and f.exception() is None and f.result()]
    finally:
        ex.shutdown(wait=False, cancel_futures=True)
    order = {t: i for i, t in enumerate(targets)}
    return sorted(open_, key=lambda t: order.get(t, 0))


_NAME_SAFE = re.compile(r"[^a-z0-9-]+")


def safe_name(raw: Optional[str]) -> str:
    """A host name usable in `ol:<model>@<name>`: the first DNS label,
    lowercased, anything but letters, digits and `-` turned into `-`."""
    label = (raw or "").strip().split(".", 1)[0].lower()
    return _NAME_SAFE.sub("-", label).strip("-")


def reverse_name(ip: str, timeout: float = REVERSE_DNS_TIMEOUT_S) -> Optional[str]:
    """The reverse-DNS name of `ip` as a `safe_name`, `None` after
    `timeout` or when there is none (the lookup runs on a helper thread
    so a slow resolver cannot hold the scan)."""
    ex = cf.ThreadPoolExecutor(max_workers=1, thread_name_prefix="ollama-rdns")
    try:
        fut = ex.submit(socket.gethostbyaddr, ip)
        try:
            name = fut.result(timeout=timeout)[0]
        except Exception:
            return None
    finally:
        ex.shutdown(wait=False, cancel_futures=True)
    name = safe_name(name)
    return name if name and name != "localhost" else None


def resolve_ipv4(hostname: str, timeout: float = REVERSE_DNS_TIMEOUT_S) -> "set[str]":
    """The IPv4 addresses `hostname` resolves to, within `timeout`
    (empty on a slow or failed lookup)."""
    ex = cf.ThreadPoolExecutor(max_workers=1, thread_name_prefix="ollama-dns")
    try:
        fut = ex.submit(socket.getaddrinfo, hostname, None, socket.AF_INET)
        try:
            return {info[4][0] for info in fut.result(timeout=timeout)}
        except Exception:
            return set()
    finally:
        ex.shutdown(wait=False, cancel_futures=True)
