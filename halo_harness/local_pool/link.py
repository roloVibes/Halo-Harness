"""halo_harness.local_pool.link -- the network link of the machine that runs `halo host` (Halo 3.3.8.0 R1; docs/POOL.md
"Wired or Wi-Fi"). A pooled decode is a round trip per layer boundary, so a Wi-Fi member's latency poisons it; the
adapter's own type says so before any RTT does.

    read(addr=None) -> {type: wired | wireless | unknown, speed_mbps: int | None, iface, source}
        the adapter that carries `addr` (the host's own address; else this machine's LAN address), read from the OS:
        Windows  Get-NetIPAddress -> Get-NetAdapter (NdisPhysicalMedium / PhysicalMediaType, ReceiveLinkSpeed)
        Linux    `ip -o -4 addr show` -> /sys/class/net/<if>/speed and /sys/class/net/<if>/wireless
        macOS    `ifconfig` -> `networksetup -listallhardwareports` (the port's name) and `ifconfig <dev>`'s media
    word(link) -> "Wi-Fi (adapter)" | "1 GbE" | "2.5 GbE" | "10 GbE" | "100 Mb/s" | "wired" | "unknown"

RUNNER is the seam (the tests' fixture output per OS): {"system": fn() -> "windows" | "linux" | "darwin",
"run": fn(argv) -> stdout | None, "read": fn(path) -> text | None, "exists": fn(path) -> bool}. Under the test flag
(BRIDGE_TEST_NO_BACKGROUND_NET) with no RUNNER nothing starts and the link is unknown. Never raises.
"""

from __future__ import annotations

import json
import os
import platform
import re
import subprocess
from typing import Optional

RUNNER: dict = {}
TIMEOUT_S = 4.0
UNKNOWN = {"type": "unknown", "speed_mbps": None, "iface": None, "source": "not read"}
_WIN = ("$ip = '{addr}'; $c = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object "
        "{{ $_.IPAddress -eq $ip }} | Select-Object -First 1; if ($c) {{ Get-NetAdapter -InterfaceIndex $c.InterfaceIndex "
        "| Select-Object Name,InterfaceDescription,PhysicalMediaType,NdisPhysicalMedium,LinkSpeed,ReceiveLinkSpeed "
        "| ConvertTo-Json -Compress }}")
_SAFE_ADDR = re.compile(r"^[0-9A-Fa-f:.]{2,45}$")


def _system() -> str:
    if "system" in RUNNER:
        return RUNNER["system"]()
    return {"Windows": "windows", "Darwin": "darwin"}.get(platform.system(), "linux")


def _run(argv: list) -> Optional[str]:
    if "run" in RUNNER:
        return RUNNER["run"](argv)
    try:
        done = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=TIMEOUT_S,
                              stdin=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout if done.returncode == 0 else None


def _read(p: str) -> Optional[str]:
    if "read" in RUNNER:
        return RUNNER["read"](p)
    try:
        with open(p, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def _exists(p: str) -> bool:
    return RUNNER["exists"](p) if "exists" in RUNNER else os.path.exists(p)


def _speed_words(text: str) -> Optional[int]:
    m = re.search(r"(\d+(?:\.\d+)?)\s*([GM])\s*bps", str(text or ""), re.I)
    if not m:
        return None
    n = float(m.group(1))
    return int(n * 1000) if m.group(2).upper() == "G" else int(n)


def _windows(addr: str) -> dict:
    out = _run(["powershell", "-NoProfile", "-NonInteractive", "-Command", _WIN.format(addr=addr)])
    try:
        got = json.loads(out or "")
    except ValueError:
        return {**UNKNOWN, "source": "Get-NetAdapter: no adapter carries " + addr}
    got = got[0] if isinstance(got, list) and got else got
    if not isinstance(got, dict):
        return {**UNKNOWN, "source": "Get-NetAdapter: no adapter carries " + addr}
    medium = str(got.get("PhysicalMediaType") or "") + " " + str(got.get("InterfaceDescription") or "")
    ndis = got.get("NdisPhysicalMedium")
    wireless = ndis == 9 or bool(re.search(r"802\.11|wireless|wi-?fi|wlan", medium, re.I))
    wired = ndis == 14 or "802.3" in medium or bool(re.search(r"ethernet|gbe", medium, re.I))
    bps = got.get("ReceiveLinkSpeed")
    speed = int(bps / 1e6) if isinstance(bps, (int, float)) and bps > 0 else _speed_words(got.get("LinkSpeed"))
    kind = "wireless" if wireless else "wired" if wired else "unknown"
    return {"type": kind, "speed_mbps": speed, "iface": got.get("Name"), "source": "Get-NetAdapter"}


def _linux(addr: str) -> dict:
    out = _run(["ip", "-o", "-4", "addr", "show"]) or ""
    iface = next((ln.split()[1] for ln in out.splitlines() if re.search(rf"\binet {re.escape(addr)}/", ln)
                  and len(ln.split()) > 1), None)
    if not iface:
        return {**UNKNOWN, "source": "ip addr: no interface carries " + addr}
    base = f"/sys/class/net/{iface}"
    wireless = _exists(f"{base}/wireless") or _exists(f"{base}/phy80211")
    raw = (_read(f"{base}/speed") or "").strip()
    speed = int(raw) if raw.lstrip("-").isdigit() and int(raw) > 0 else None
    return {"type": "wireless" if wireless else "wired", "speed_mbps": speed, "iface": iface,
            "source": f"/sys/class/net/{iface}"}


def _darwin(addr: str) -> dict:
    conf = _run(["ifconfig"]) or ""
    dev, cur = None, None
    for ln in conf.splitlines():
        m = re.match(r"^([A-Za-z0-9]+):", ln)
        if m:
            cur = m.group(1)
        elif cur and re.search(rf"\binet {re.escape(addr)}\b", ln):
            dev = cur
            break
    if not dev:
        return {**UNKNOWN, "source": "ifconfig: no interface carries " + addr}
    ports = _run(["networksetup", "-listallhardwareports"]) or ""
    port = next((b for b in ports.split("\n\n") if re.search(rf"Device:\s*{re.escape(dev)}\b", b)), "")
    name = (re.search(r"Hardware Port:\s*(.+)", port) or [None, ""])[1].strip()
    wireless = bool(re.search(r"wi-?fi|airport", name, re.I))
    media = (re.search(r"media:.*?\((\d+(?:\.\d+)?)(G|)base", _run(["ifconfig", dev]) or "", re.I))
    speed = None if wireless or not media else int(float(media.group(1)) * (1000 if media.group(2) else 1))
    kind = "wireless" if wireless else "wired" if name else "unknown"
    return {"type": kind, "speed_mbps": speed, "iface": dev, "source": f"networksetup ({name or 'no port name'})"}


def read(addr: Optional[str] = None) -> dict:
    if not RUNNER:
        from halo_harness.config.paths import background_net_disabled
        if background_net_disabled():
            return {**UNKNOWN, "source": "not read in tests"}
    try:
        if not addr:
            from halo_harness.fleet.hub import lan_address
            addr = lan_address()
        if not addr or not _SAFE_ADDR.match(addr) or addr.startswith("127."):
            return {**UNKNOWN, "source": "no LAN address on this machine"}
        return {"windows": _windows, "darwin": _darwin}.get(_system(), _linux)(addr)
    except Exception as e:  # one bad reader never takes the card down
        return {**UNKNOWN, "source": f"not read ({type(e).__name__})"}


def word(link: Optional[dict]) -> str:
    link = link or {}
    if link.get("type") == "wireless":
        return "Wi-Fi (adapter)"
    s = link.get("speed_mbps")
    if link.get("type") == "wired":
        if isinstance(s, int) and s >= 1000:
            g = s / 1000
            return f"{g:g} GbE"
        return f"{s} Mb/s" if isinstance(s, int) else "wired"
    return "unknown"
