"""halo_harness.fleet.table -- the fleet as a table for a terminal: `halo
fleet` (live, table_live.py) and `/fleet` in the TUI (tui/dialogs/
fleet_table.py) (Halo 3.0.5.0 "Fleet" round R2, plan item D9).

`snapshot()` reads `GET /api/fleet` from the Studio this machine runs (every
member of its hub included), else the merged view of a `halo fleet serve`
running here, else this harness alone (the local registry and sockets).
`rows(view)` is one row per agent: harness, session, agent (indented under
its parent), state, what it is doing now, cost. `send(row, cmd, source)`
steers, stops, pauses or resumes that agent the same way: through Studio,
through the local hub, or straight over the session's control socket.
"""

from __future__ import annotations

import json
from typing import Optional

from halo_harness.fleet import identity

COLUMNS = (("HARNESS", 24), ("SESSION", 9), ("AGENT", 22), ("STATE", 9), ("CURRENT", 34), ("COST", 8))
WIRE = {"steer": "agent_steer", "stop": "agent_stop", "pause": "pause", "resume": "resume"}


def snapshot() -> "tuple[dict, str]":
    """`(view, source)`: source is studio | hub | local."""
    from halo_harness.studio.launch import api_call
    home = identity.home()
    got = api_call(home, "GET", "fleet", timeout=3.0)
    if got and got[0] == 200 and isinstance(got[1], dict) and "harnesses" in got[1]:
        return got[1], "studio"
    from halo_harness.fleet.hub import running_view
    view = running_view(home)
    if view:
        return view, "hub"
    from halo_harness.fleet.local_view import snapshot as local
    return {"harnesses": [local()], "hub": {"serving": False}}, "local"


def _depths(agents: list) -> dict:
    parent = {a.get("agent_id"): a.get("parent") for a in agents}
    out = {}
    for aid in parent:
        d, cur, seen = 0, parent.get(aid), set()
        while cur in parent and cur not in seen and d < 8:
            seen.add(cur)
            d, cur = d + 1, parent.get(cur)
        out[aid] = d
    return out


def rows(view: dict) -> list:
    out = []
    for h in view.get("harnesses") or []:
        name = str(h.get("name") or str(h.get("id") or "")[:8])
        name += " (you)" if h.get("local") else ("" if h.get("online", True) else " (away)")
        if h.get("version_mismatch"):
            name += " !v"
        sessions = h.get("sessions") or []
        if not sessions:
            out.append({"harness": h.get("id"), "harness_name": name, "session_id": None, "agent_id": None,
                        "agent": "-", "depth": 0, "state": "online" if h.get("online", True) else "away",
                        "current": "no live session", "cost": None, "local": bool(h.get("local"))})
        for s in sessions:
            agents = s.get("agents") or [{"agent_id": "main", "name": "main", "state": s.get("status"),
                                          "cost_usd": s.get("cost_usd")}]
            depth = _depths(agents)
            for a in agents:
                current = a.get("current") or (s.get("title") if a.get("agent_id") == "main" else a.get("task"))
                out.append({"harness": h.get("id"), "harness_name": name, "session_id": s.get("session_id"),
                            "agent_id": a.get("agent_id"), "agent": str(a.get("name") or a.get("agent_id")),
                            "depth": depth.get(a.get("agent_id"), 0), "state": a.get("state") or s.get("status"),
                            "current": current or "", "cost": a.get("cost_usd"), "local": bool(h.get("local"))})
    return out


def _cell(text, width: int) -> str:
    t = " ".join(str(text if text is not None else "").split())
    return (t[:width - 1] + "~") if len(t) > width else t.ljust(width)


def render(table: list, selected: Optional[int] = None) -> str:
    head = "  " + " ".join(_cell(n, w) for n, w in COLUMNS)
    lines = [head.rstrip()]
    last = (None, None)
    for i, r in enumerate(table):
        same_h, same_s = last[0] == r["harness"], last == (r["harness"], r["session_id"])
        cost = f"${r['cost']:.2f}" if isinstance(r.get("cost"), (int, float)) else ""
        cells = ("" if same_h else r["harness_name"], "" if same_s else str(r["session_id"] or "-")[:8],
                 "  " * r["depth"] + r["agent"], r["state"] or "", r["current"], cost)
        mark = "> " if i == selected else "  "
        lines.append((mark + " ".join(_cell(c, w) for c, (_n, w) in zip(cells, COLUMNS))).rstrip())
        last = (r["harness"], r["session_id"])
    if not table:
        lines.append("  (nothing yet: start a halo session; joined harnesses appear here too)")
    return "\n".join(lines)


def send(row: dict, cmd: str, source: str, **fields) -> "tuple[bool, str]":
    """Run `cmd` (steer | stop | pause | resume) on the row's agent: `(ok, message)`."""
    if not row.get("session_id") or not row.get("agent_id"):
        return False, "that row has no agent to act on"
    body = {"cmd": cmd, **fields}
    if source == "studio":
        from halo_harness.studio.launch import api_call
        got = api_call(identity.home(), "POST",
                       f"fleet/{row['harness']}/{row['session_id']}/agents/{row['agent_id']}/command", body, timeout=10.0)
        status, out = got if got else (0, {"error": "Studio did not answer"})
    elif source == "hub" and not row.get("local"):
        from halo_harness.fleet.hub import running_call
        wire = {"agent_id": row["agent_id"], **fields, **({"mode": "nudge"} if cmd == "steer" else {})}
        got = running_call(identity.home(), "POST", "local/command",
                           {"harness": row["harness"], "session_id": row["session_id"], "cmd": WIRE[cmd], "fields": wire})
        status, out = got if got else (0, {"error": "the hub did not answer"})
    else:
        from halo_harness.studio.fleet_api import forward
        status, out = forward(row["session_id"], WIRE[cmd], {"agent_id": row["agent_id"], "by": identity.fleet_name(),
                                                             "via": "halo fleet", **fields})
    if status == 200:
        return True, f"{cmd}: done"
    if status == 202:
        return True, f"{cmd}: asked; {out.get('text') or 'waiting for the owner'}"
    return False, f"{cmd}: {out.get('error') or status}"


def cmd_table(argv: list) -> int:
    import argparse
    p = argparse.ArgumentParser(prog="halo fleet", description="The live table of every harness, session and agent.")
    p.add_argument("--once", action="store_true", help="print the table once and exit")
    p.add_argument("--json", action="store_true", help="print the fleet view (GET /api/fleet) as JSON and exit")
    try:
        a = p.parse_args(argv)
    except SystemExit as e:
        return 0 if e.code in (0, None) else 2
    if a.json or a.once:
        view, source = snapshot()
        print(json.dumps({"source": source, **view}, indent=2, default=str) if a.json else render(rows(view)))
        return 0
    from halo_harness.fleet.table_live import live
    return live()
