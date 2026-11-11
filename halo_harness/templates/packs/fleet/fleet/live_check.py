"""halo_harness.fleet.live_check -- the scripted two-machine check's steps
(Halo 3.1.2.0 R3; tools/live_fleet_check.py is the CLI, docs/FLEET.md "The
two-machine check"). The hub box, after a member joins, drives:

    who       `fleet who nmap` names the member, `who gridcraft` this host
    mission   a one-part files mission pinned to the member writes one file and hands back here
    recall    `recall --fleet` with a query only the member's index answers

Each step is a `Step` with a PASS / FAIL and one evidence line; `run_all`
returns the report `tools/live_fleet_check.py --json` writes. Every wait is
bounded; cleanup stops the mission. (3.4.0.0 B: the team step left with the team file.) No model is called with
`--fake` (fleet/live_check_fakes.py); the real configured model otherwise.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Optional


def _wait(fn: Callable, timeout: float, *, step: float = 0.3, drive: Optional[Callable] = None):
    end = time.monotonic() + max(1.0, timeout)
    while time.monotonic() < end:
        if drive is not None:
            try:
                drive()
            except Exception:
                pass
        try:
            got = fn()
        except Exception:
            got = None
        if got:
            return got
        time.sleep(step)
    return fn() if drive is None else None


def member_of(hub) -> Optional[dict]:
    """The first online member of the hub this box runs (not this harness)."""
    for h in hub.state.view().get("harnesses") or []:
        if not h.get("local") and h.get("online"):
            return h
    return None


def _caps_rows(hub) -> list:
    return [{"harness": r.get("harness"), "name": r.get("name"), "local": r.get("local"), "catalog": r.get("catalog")}
            for r in hub.state.caps.entries()]


def step_who(hub, member: dict, timeout: float) -> "tuple[bool, str]":
    from . import capabilities_who as who
    rows = _wait(lambda: (_caps_rows(hub) if any(r.get("catalog") and not r.get("local") for r in _caps_rows(hub))
                          else None), timeout) or _caps_rows(hub)
    nmap = who.rank(rows, "nmap")
    grid = who.rank(rows, "gridcraft")
    ok = bool(nmap) and nmap[0]["harness"] == member.get("id") and bool(grid) and grid[0].get("local")
    top_n = nmap[0]["name"] if nmap else "nobody"
    top_g = grid[0]["name"] if grid else "nobody"
    return ok, f"who nmap -> {top_n} (the member); who gridcraft -> {top_g} (this host)"


def step_mission(home, member: dict, timeout: float, cleanups: list) -> "tuple[bool, str]":
    from .live_check_fakes import NMAP_LINE
    from .delegate import FleetDelegate
    d = FleetDelegate(home=home)
    task = {"team": "live-check", "stage": "scan", "title": "nmap version to scan.txt",
            "brief": f"Run `nmap --version` and write its first line to scan.txt (expected: {NMAP_LINE})."}
    status, body = d.send({"name": member.get("name"), "harness": member.get("id")}, task)
    if status not in (200, 202):
        return False, f"the member would not take the part: {status} {body.get('error')}"
    handle = body["handle"]
    cleanups.append(lambda: d.stop(handle, "live-check done"))
    res = _wait(lambda: d.poll(handle) or None, timeout)
    if not res:
        return False, f"no hand-back from {member.get('name')} within {timeout:g} s"
    body = [ln for ln in (res.get("text") or "").splitlines() if ln.strip() and not ln.startswith("#")]
    return bool(res.get("ok")), (f"mission {handle['mission']} part 1 ran on {member.get('name')}, hand-back landed here: "
                                 f"{(body or ['(empty)'])[0][:90]}" if res.get("ok") else f"the part failed: {res.get('error')}")


def step_recall(hub, home, timeout: float) -> "tuple[bool, str]":
    from .hub_recall import merged
    query = "the live-check planted this on the member only"
    out = _wait(lambda: (lambda o: o if any(not r.get("local") and r.get("state") == "answered" and r.get("hits")
                                            for r in o.get("harnesses") or []) else None)(
                merged(hub, query, k=5, by="live-check")), timeout)
    if not out:
        return False, f"no member answered the fleet recall within {timeout:g} s"
    member_hits = [h for h in out.get("hits") or [] if h.get("harness")]
    labels = sorted({h.get("harness") for h in member_hits})
    local_hits = next((r.get("hits") for r in out.get("harnesses") or [] if r.get("local")), 0)
    ok = bool(member_hits) and all(h.get("harness") for h in member_hits)
    return ok, (f"recall --fleet: {len(member_hits)} hit(s) from {', '.join(labels)}, this host's own index "
                f"answered {local_hits}")


def run_all(hub, home, *, member: Optional[dict] = None, fake: bool = False, timeout: float = 30.0,
            repo: Optional[Path] = None) -> dict:
    """Drive every step on the hub box; `member` defaults to the first online member (`repo` is unused since 3.4.0.0)."""
    started = time.time()
    member = member or member_of(hub)
    report = {"ok": False, "fake": bool(fake), "hub": hub.state.name, "member": (member or {}).get("name"),
              "member_id": (member or {}).get("id"), "started": started, "steps": []}
    cleanups: list = []
    if member is None:
        report["steps"].append({"name": "member", "ok": False, "seconds": 0.0,
                                "evidence": "no member joined this hub (the other box has not run its half yet)"})
        report["ended"] = time.time()
        return report
    plan = [("who", lambda: step_who(hub, member, timeout)),
            ("mission", lambda: step_mission(home, member, timeout, cleanups)),
            ("recall", lambda: step_recall(hub, home, timeout))]
    for name, fn in plan:
        t0 = time.monotonic()
        try:
            ok, evidence = fn()
        except Exception as e:
            ok, evidence = False, f"{type(e).__name__}: {e}"
        report["steps"].append({"name": name, "ok": bool(ok), "evidence": evidence,
                                "seconds": round(time.monotonic() - t0, 2)})
    for fn in reversed(cleanups):
        try:
            fn()
        except Exception:
            pass
    report["ok"] = all(s["ok"] for s in report["steps"])
    report["ended"] = time.time()
    return report


def render(report: dict) -> str:
    lines = [f"Halo fleet two-machine check -- hub {report.get('hub')}, member {report.get('member') or '(none)'}"
             + ("  [--fake: no model calls]" if report.get("fake") else "")]
    for s in report.get("steps") or []:
        mark = "PASS" if s["ok"] else "FAIL"
        lines.append(f"  [{mark}] {s['name']:<8} {s['evidence']}  ({s.get('seconds', 0)}s)")
    passed = sum(1 for s in report.get("steps") or [] if s["ok"])
    total = len(report.get("steps") or [])
    lines.append(f"{'OK' if report.get('ok') else 'FAILED'}: {passed}/{total} step(s) passed.")
    return "\n".join(lines)
