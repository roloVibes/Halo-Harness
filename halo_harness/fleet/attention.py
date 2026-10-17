"""halo_harness.fleet.attention -- ONE queue of every decision a person has to
make across the fleet (Halo 3.0.5.0 "Fleet" round R4, D3). Pure: rows are
computed from the hub's view and the other sources; studio/fleet_panels_api.py
serves them (`GET /api/fleet/attention`) and routes the answers.

    permission | question | plan | approval   a session's open card (its `pending` ids)
    fleet_ask      a hub asks this harness's owner to allow a command (a `fleet-ask:` question here)
    waiting        an agent waits with no card of its own session listed
    paused         an agent (or a whole session) paused, waiting on resume
    flow_gate      a flow run waits at a gate (the render OK)
    orchestra_gate an Orchestra run the gate stopped (the return cap, or failing tests)
    control_ask    a command this hub sent waits on a member's owner
    cap            a spend cap reached: its sessions are paused
    conflict       two agents of different sessions edit the same file
    mission_plan | mission_claim | mission_ask   a fleet mission waits for approval, a part was refused an edit
                   outside its claims, a hub asks to run a part here (3.0.6.0 R7, fleet/mission_attention.py)
    team_gate      a stage of this repo's team run waits at its gate (3.0.8.0 R2, fleet/team_attention.py)

Each row: {id, kind, harness, harness_name, local, session_id, session, agent_id, agent, what, detail,
since, keys: {a|r|s|o: label}, text_for: "r" | None, target: {...}}. `keys` holds only the answers
that kind takes; `r` with `text_for` sends the typed text (deny reason, instruction, feedback, answer).
"""

from __future__ import annotations

import time
from typing import Optional

from halo_harness.remote.bridge_cards import describe_input, normalize_questions, one_line

ASK_PREFIX = "fleet-ask:"
OPEN = {"o": "open"}
KEYS = {
    "permission": {"a": "allow once", "r": "deny", "s": "stop", **OPEN},
    "question": {"r": "answer", "s": "stop", **OPEN},
    "plan": {"a": "approve", "r": "send back", "s": "stop", **OPEN},
    "approval": {"a": "accept", "r": "edit", "s": "stop", **OPEN},
    "fleet_ask": {"a": "allow", "r": "deny", **OPEN},
    "waiting": {"s": "stop", **OPEN},
    "paused": {"a": "resume", "s": "stop", **OPEN},
    "flow_gate": {"a": "accept", "r": "redo", "s": "stop", "o": "open Flow"},
    "orchestra_gate": {"a": "set aside", "o": "open Orchestra"},
    "control_ask": {"a": "set aside", **OPEN},
    "cap": {"a": "lift for today", "o": "open Costs"},
    "conflict": {"a": "set aside", "o": "open the map"},
    "mission_plan": {"a": "approve and run", "r": "edit", "s": "drop", "o": "open the mission"},  # 3.0.6.0 R7
    "mission_claim": {"a": "set aside", "o": "open the mission"},
    "mission_ask": {"a": "allow", "r": "deny", **OPEN},
    "team_gate": {"a": "accept", "r": "redo", "s": "stop", "o": "open Team"},  # 3.0.8.0 R2
}
TEXT_FOR = {"permission": "r", "question": "r", "plan": "r", "approval": "r", "flow_gate": "r", "mission_plan": "r",
            "team_gate": "r"}
CARD_KINDS = ("permission", "question", "plan", "approval")


def title_of(s: dict) -> str:
    main = next((a for a in s.get("agents") or [] if not a.get("parent")), {})
    folder = str(s.get("cwd") or "").replace("\\", "/").rstrip("/").split("/")[-1]
    return str(s.get("title") or main.get("task") or folder or str(s.get("session_id") or "")[:8])[:120]


def _what(kind: str, ask: dict) -> "tuple[str, str]":
    data = ask.get("data") if isinstance(ask.get("data"), dict) else {}
    if kind == "permission":
        name = str(data.get("name") or "a tool")
        return f"Permission: {name}", one_line(describe_input(name, data.get("input")) or data.get("reason"), 240)
    if kind == "question":
        qs = normalize_questions(data)
        return "Question", one_line(qs[0]["question"] if qs else "", 240)
    if kind == "plan":
        return "Plan review", one_line(data.get("plan"), 240)
    return f"Approval ({data.get('position') or 'next step'})", one_line(data.get("text"), 240)


def _row(kind: str, rid: str, h: dict, s: Optional[dict], aid: str, what: str, detail: str, seen: dict, now: float,
         **target) -> dict:
    agent = next((a for a in (s or {}).get("agents") or [] if a.get("agent_id") == aid), {})
    rid_full = f"{kind}:{h.get('id') or '-'}:{(s or {}).get('session_id') or '-'}:{rid}"
    return {"id": rid_full, "kind": kind, "harness": h.get("id"), "harness_name": h.get("name") or str(h.get("id") or "")[:8],
            "local": bool(h.get("local")), "session_id": (s or {}).get("session_id"), "session": title_of(s) if s else "",
            "agent_id": aid or None, "agent": agent.get("name") or agent.get("role") or aid or "", "what": what,
            "detail": detail, "since": seen.setdefault(rid_full, now), "keys": dict(KEYS[kind]),
            "remote_attached": int((s or {}).get("remote_attached") or 0),
            "text_for": TEXT_FOR.get(kind), "target": {k: v for k, v in target.items() if v is not None}}


def session_rows(view: dict, asks: dict, seen: dict, now: float) -> list:
    out = []
    for h in view.get("harnesses") or []:
        for s in h.get("sessions") or []:
            pend = s.get("pending") if isinstance(s.get("pending"), dict) else {}
            listed = False
            for kind in CARD_KINDS:
                for rid in pend.get(kind) or []:
                    rid = str(rid)
                    if kind == "question" and rid.startswith(ASK_PREFIX):
                        if h.get("local"):
                            task = rid.startswith(ASK_PREFIX + "mission-")  # R7: a run_task card
                            detail, extra = "", {}
                            if task:  # R8: the card's text, and the mission / part it names (O opens it)
                                from halo_harness.fleet.mission_attention import ask_target
                                detail, extra = ask_target(asks.get((str(h.get("id")), str(s.get("session_id")), rid)))
                            out.append(_row("mission_ask" if task else "fleet_ask", rid, h, s, "main",
                                            "A hub asks to run a mission part here" if task else
                                            "A hub asks to run a command here", detail, seen, now, request_id=rid, **extra))
                        continue  # a member's own fleet card is its owner's to answer
                    ask = asks.get((str(h.get("id")), str(s.get("session_id")), rid)) or {}
                    what, detail = _what(kind, ask)
                    out.append(_row(kind, rid, h, s, str(ask.get("agent_id") or "main"), what, detail, seen, now,
                                    request_id=rid))
                    listed = True
            for a in s.get("agents") or []:
                aid = str(a.get("agent_id") or "")
                if a.get("state") == "waiting" and not listed:
                    out.append(_row("waiting", aid, h, s, aid, f"{a.get('name') or aid} waits on you",
                                    one_line(a.get("current") or a.get("task"), 200), seen, now))
                elif a.get("state") == "paused":
                    out.append(_row("paused", aid, h, s, aid, f"{a.get('name') or aid} is paused",
                                    "it holds at its next step until you resume it", seen, now))
    return out


def flow_rows(flows: list, local: dict, seen: dict, now: float) -> list:
    return [_row("flow_gate", str(r.get("run")), local, None, "", f"Flow {r.get('name') or r.get('run')} waits at "
                 f"{r.get('waiting_step')}", "confirm the render, redo it with an instruction, or stop the run",
                 seen, now, run=r.get("run"), step=r.get("waiting_step"))
            for r in flows if r.get("waiting_step")]


def orchestra_rows(runs: list, local: dict, seen: dict, now: float, within_s: float = 86400.0) -> list:
    return [_row("orchestra_gate", str(r.get("run_id")), local, None, "", f"Orchestra run {r.get('run_id')} stopped at the gate",
                 one_line(r.get("stop_reason") or r.get("goal_what"), 240), seen, now, run=r.get("run_id"))
            for r in runs if r.get("state") == "stopped" and now - float(r.get("created") or 0) < within_s]


def command_rows(commands: list, view: dict, seen: dict, now: float) -> list:
    out = []
    names = {str(h.get("id")): h for h in view.get("harnesses") or []}
    for c in commands:
        if c.get("state") != "asked":
            continue
        h = names.get(str(c.get("harness"))) or {"id": c.get("harness"), "name": str(c.get("harness"))[:8]}
        s = next((x for x in h.get("sessions") or [] if x.get("session_id") == c.get("session_id")), None)
        out.append(_row("control_ask", str(c.get("command_id")), h, s, "", f"Your {c.get('cmd')} waits on {h.get('name')}'s owner",
                        "they allow or deny it on that machine", seen, now, command_id=c.get("command_id")))
    return out


def cap_rows(reached: list, local: dict, seen: dict, now: float) -> list:
    return [_row("cap", f"{r['scope']}:{r['key']}", local, None, "", f"Cap reached: {r['label']}",
                 f"${r['spent']:.2f} of ${r['cap']:.2f} today; its {len(r['sessions'])} session"
                 f"{'' if len(r['sessions']) == 1 else 's'} paused", seen, now, scope=r["scope"], key=r["key"],
                 sessions=r["sessions"]) for r in reached]


def conflict_rows(conflicts: list, view: dict, seen: dict, now: float) -> list:
    out = []
    names = {str(h.get("id")): h for h in view.get("harnesses") or []}
    for c in conflicts:
        a, b = c["a"], c["b"]
        h = names.get(str(a.get("harness"))) or {"id": a.get("harness"), "name": a.get("harness_name")}
        s = next((x for x in h.get("sessions") or [] if x.get("session_id") == a.get("session_id")), None)
        row = _row("conflict", f"{c['repo']}:{c['file']}:{a['key']}:{b['key']}", h, s, str(a.get("agent_id") or ""),
                   f"{a['name']} and {b['name']} are both editing {c['file']}",
                   f"{a.get('harness_name')} and {b.get('harness_name')} on {c['repo']}", seen, now,
                   a=a["key"], b=b["key"], file=c["file"])
        out.append(row)
    return out


def build(view: dict, *, asks: Optional[dict] = None, flows=(), orchestra=(), commands=(), reached=(), conflicts=(),
          seen: Optional[dict] = None, acks=(), now: Optional[float] = None, home=None, teams=()) -> list:
    """Every row, newest decision last within each harness, set-aside rows left out."""
    now = now or time.time()
    seen = seen if seen is not None else {}
    local = next((h for h in view.get("harnesses") or [] if h.get("local")), {"id": None, "name": "this harness", "local": True})
    rows = (session_rows(view, asks or {}, seen, now) + flow_rows(list(flows), local, seen, now)
            + orchestra_rows(list(orchestra), local, seen, now) + command_rows(list(commands), view, seen, now)
            + cap_rows(list(reached), local, seen, now) + conflict_rows(list(conflicts), view, seen, now))
    if home is not None:  # 3.0.6.0 R7: the missions' rows
        from halo_harness.fleet.mission_attention import rows as mission_rows
        rows += mission_rows(home, local, seen, now)
    if teams:  # 3.0.8.0 R2: the team gates of Studio's repo (fleet/team_attention.py gated)
        from halo_harness.fleet.team_attention import rows as team_rows
        rows += team_rows(list(teams), local, seen, now)
    gone = set(acks)
    return sorted([r for r in rows if r["id"] not in gone], key=lambda r: r["since"])
