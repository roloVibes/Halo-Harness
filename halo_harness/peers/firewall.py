"""halo_harness.peers.firewall -- whether Windows Firewall lets other machines reach a port Halo listens on (Halo
3.4.0.1 "Found live", defect 12). Read-only: it reads the rules (`netsh advfirewall`, no elevation) and never changes
one; when something is in the way it says the one command an administrator runs, and what it does.

The live check: a hub on Windows bound 0.0.0.0:7430 and printed its URL; a member's join timed out. Windows had added
two inbound Block rules named `python.exe` for Halo's python the moment it listened (its "allow access?" prompt,
declined or never seen). A rule is per program, so the same block hits every port that python listens on (the fleet
hub, `halo host serve`); and in Windows Firewall a block beats an allow.

    check(port, programs=None, run=None)  {state, rules, profiles, line}
        state: allowed | blocked | no-rule | off (the firewall is off) | unknown (could not read) | not-windows
    line(port, what="the fleet hub")      the one line to print, "" when nothing is in the way (or not Windows)
    JOIN_TIMEOUT                          what a member says when the hub does not answer
"""

from __future__ import annotations

import os
import re
from halo_harness import subprocess_safe as subprocess
import sys
from typing import Callable, Optional

JOIN_TIMEOUT = ("the hub did not answer on {host}:{port}: on Windows the firewall is the usual cause; "
                "on the hub run `halo doctor`")
RUN: Optional[Callable] = None  # test seam: (argv) -> stdout text


def _run(argv: list) -> str:
    if RUN is not None:
        return RUN(argv)
    done = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return done.stdout or ""


def _norm(p: str) -> str:
    return os.path.normcase(os.path.normpath(str(p or "").strip().strip('"'))) if p else ""


def _real(p: str) -> str:
    try:
        return os.path.realpath(os.path.expandvars(str(p).strip().strip('"')))
    except (OSError, ValueError):
        return str(p)


def programs() -> set:
    """This Halo's python, as a rule names it: the venv's launcher and the interpreter it starts, each also resolved
    (3.4.1.0 R5, defect 31: uv's `cpython-3.12-...` is a junction to `cpython-3.12.13-...`; the listening process runs
    the junction's path while Windows Firewall recorded the resolved one)."""
    out = {p for p in (sys.executable, getattr(sys, "_base_executable", "")) if p}
    return {_norm(p) for p in out | {_real(p) for p in out}}


def _is_mine(prog: str, mine: set) -> bool:
    """A rule's program is this Halo's python, as written or once resolved (a rule may name the junction's path too)."""
    return _norm(os.path.expandvars(prog)) in mine or _norm(_real(prog)) in mine


def _rules(text: str) -> list:
    rows, cur = [], None
    for raw in text.splitlines():
        m = re.match(r"^\s*([A-Za-z][A-Za-z ]*?):\s*(.*?)\s*$", raw)
        if not m:
            continue
        key, val = m.group(1).strip().lower(), m.group(2)
        if key == "rule name":
            cur = {"name": val}
            rows.append(cur)
        elif cur is not None:
            cur[key] = val
    return rows


def _port_in(spec: str, port: int) -> bool:
    spec = str(spec or "").strip().lower()
    if spec in ("", "any"):
        return True
    for part in spec.split(","):
        a, _, b = part.strip().partition("-")
        if a.isdigit() and (int(a) == port if not b else b.isdigit() and int(a) <= port <= int(b)):
            return True
    return False


def check(port: int, progs: Optional[set] = None, run: Optional[Callable] = None) -> dict:
    out = {"state": "not-windows", "rules": [], "profiles": "", "line": ""}
    if run is None and RUN is None and (os.name != "nt" or "BRIDGE_TEST_HOME" in os.environ):
        return out if os.name != "nt" else {**out, "state": "unknown"}  # a test reads the rules only through RUN
    run = run or _run
    try:
        state = run(["netsh", "advfirewall", "show", "currentprofile", "state"])
        text = run(["netsh", "advfirewall", "firewall", "show", "rule", "name=all", "dir=in", "verbose"])
    except (OSError, subprocess.SubprocessError):
        return {**out, "state": "unknown"}
    if re.search(r"^\s*State\s+OFF\s*$", state, re.M | re.I):
        return {**out, "state": "off"}
    rows = _rules(text)
    if not rows:
        return {**out, "state": "unknown"}
    mine = progs if progs is not None else programs()
    live = [r for r in rows if str(r.get("enabled", "")).lower() == "yes" and str(r.get("direction", "in")).lower() == "in"
            and str(r.get("protocol", "any")).lower() in ("tcp", "any")]
    def ours(r: dict) -> bool:  # this python's rule on any port, or any program's rule naming the port itself
        prog, ports = str(r.get("program", "any")).strip(), str(r.get("localport", "any")).strip().lower()
        if prog.lower() == "any":  # Any/Any is an app package's or a service's scope (netsh does not show which)
            return ports not in ("", "any") and _port_in(ports, port)
        return _is_mine(prog, mine) and _port_in(ports, port)
    blocks = [r for r in live if str(r.get("action", "")).lower() == "block" and ours(r)]
    if blocks:
        progs = {str(r.get("program", "")).strip() for r in blocks}  # 3.4.1.1 (39): the same program's UDP twins, counted
        udp = [r for r in rows if str(r.get("enabled", "")).lower() == "yes" and str(r.get("direction", "in")).lower() == "in"
               and str(r.get("protocol", "")).lower() == "udp" and str(r.get("action", "")).lower() == "block"
               and str(r.get("program", "")).strip() in progs and str(r.get("program", "any")).lower() != "any"]
        return {**out, "state": "blocked", "rules": [r["name"] for r in blocks], "udp": len(udp),
                "programs": sorted({str(r["program"]) for r in blocks if str(r.get("program", "any")).lower() != "any"}),
                "profiles": ", ".join(sorted({str(r.get("profiles", "")) for r in blocks}))}
    allows = [r for r in live if str(r.get("action", "")).lower() == "allow" and ours(r)]
    return {**out, "state": "allowed" if allows else "no-rule", "rules": [r["name"] for r in allows]}


_seen: dict = {}  # port -> (monotonic, check) for `cached`
CACHE_S = 60.0


def cached(port: int) -> dict:
    """`check(port)`, read at most once a minute (Studio's GET fleet asks on every refresh)."""
    import time
    hit = _seen.get(port)
    if hit is not None and time.monotonic() - hit[0] < CACHE_S:
        return hit[1]
    got = check(port)
    _seen[port] = (time.monotonic(), got)
    return got


def line(port: int, what: str = "the fleet hub", got: Optional[dict] = None) -> str:
    """The one plain line when Windows Firewall is in the way of `port`, else ""."""
    got = got if got is not None else cached(port)
    allow = (f"New-NetFirewallRule -DisplayName 'Halo {what.replace('the ', '')}' -Direction Inbound -Protocol TCP "
             f"-LocalPort {port} -Action Allow -Profile Private")
    if got["state"] == "blocked":
        n, progs = len(got["rules"]), got.get("programs") or []
        quoted = ",".join(f"'{x}'" for x in progs)  # every blocked program (TCP and UDP rules share one)
        find = (f"Get-NetFirewallApplicationFilter -Program {quoted} | Get-NetFirewallRule" if progs else
                "Get-NetFirewallRule -DisplayName " + ",".join(f"'{x}'" for x in sorted(set(got["rules"]))))
        udp = int(got.get("udp") or 0)  # 3.4.1.1 (39): netsh shows a UDP twin of each; the command below removes both
        return (f"Windows Firewall blocks other machines from {what} on port {port}: {n} inbound Block rule"
                f"{'s' if n != 1 else ''} for TCP{f' and {udp} for UDP' if udp else ''} "
                f"({', '.join(sorted(set(got['rules'])))}, {got['profiles'] or 'any profile'}) "
                "for this Halo's python, made when Windows asked to allow it and the prompt was declined or not seen; "
                "a block beats an allow. In an administrator PowerShell: "
                f"{find} | Where-Object "
                "{ $_.Direction -eq 'Inbound' -and $_.Action -eq 'Block' } | Remove-NetFirewallRule; "
                f"{allow} (removes those Block rules, then lets machines on your private network reach port {port}).")
    if got["state"] == "no-rule":
        return (f"No Windows Firewall rule lets other machines reach {what} on port {port} (Windows asks once when a "
                "program first listens; a prompt declined or not seen becomes a Block rule). In an administrator "
                f"PowerShell: {allow} (lets machines on your private network reach port {port}).")
    return ""
