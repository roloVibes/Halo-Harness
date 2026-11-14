"""halo_harness.live.attention -- ONE queue of every decision a person has to
make on this machine (Halo 3.0.5.0 R4, D3). Pure: rows are computed from
Studio's view of this machine and the other sources; studio/live_panels_api.py
serves them (`GET /api/live/attention`) and routes the answers.

    permission | question | plan | approval   a session's open card (its `pending` ids)
    waiting        an agent waits with no card of its own session listed
    paused         an agent (or a whole session) paused, waiting on resume
    orchestra_gate an Orchestra run the gate stopped (the return cap, or failing tests)
    cap            a spend cap reached: its sessions are paused
    conflict       two agents of different sessions edit the same file
    goal_plan | goal_gate | goal_budget | goal_ask   a supervisor decision (3.1.8.0 R1,
                   live/supervise_attention.py): a goal's plan review, a gate past the cap, a budget cap, a job's ask
    goal_replan    a replan's new plan failed its check twice (3.1.8.0 R2): apply / keep the old plan / stop
    ollama_steward the Ollama steward's newest note with an `error` finding or a change (3.3.4.0 R4,
                   live/steward_attention.py): set aside / open Local
    background_done  a session's background work finished while it was idle (3.4.1.3, its status's `bg_done`,
                   agent/bg_pickup.py): set aside / open; it goes with the person's next message there
    crew_try       a Try it run ended while the Agents tab did not show it (3.6.0.0 R1, live/crew_attention.py)

Each row: {id, kind, harness, harness_name, local, session_id, session, agent_id, agent, what, detail,
since, keys: {a|r|s|o: label}, text_for: "r" | None, target: {...}}. `keys` holds only the answers
that kind takes; `r` with `text_for` sends the typed text (deny reason, instruction, feedback, answer).
3.3.11.0 R2: a card of a `headless` session (no terminal) is `parked: true`; with no Studio page open
(`pages`, how many pages Studio's feed serves) its `what` ends "-- waiting on you in Studio".
"""

from __future__ import annotations

import time
from typing import Optional

from halo_harness.remote.cards import describe_input, normalize_questions, one_line

OPEN = {"o": "open"}
KEYS = {
    "permission": {"a": "allow once", "r": "deny", "s": "stop", **OPEN},
    "question": {"r": "answer", "s": "stop", **OPEN},
    "plan": {"a": "approve", "r": "send back", "s": "stop", **OPEN},
    "approval": {"a": "accept", "r": "edit", "s": "stop", **OPEN},
    "waiting": {"s": "stop", **OPEN},
    "paused": {"a": "resume", "s": "stop", **OPEN},
    "orchestra_gate": {"a": "set aside", "o": "open its report"},  # 3.4.0.0 D: a stopped run's report is in History
    "cap": {"a": "lift for today", "o": "open the spend"},  # 3.3.16.0 R2: Agents -> Live, the machine's spend
    "conflict": {"a": "set aside", "o": "open Live"},  # 3.3.16.0 R2: Agents -> Live
    # 3.1.8.0 R1 (the supervisor): the keys ride on the row itself (supervise_attention.rows), one per decision kind
    "goal_plan": {"a": "approve", "r": "reject", "o": "open the plan"},
    "goal_gate": {"a": "raise the cap by 1 and resume", "r": "raise the cap by N", "s": "stop", "o": "open the run"},
    "goal_budget": {"a": "raise by its cap and resume", "r": "raise by $N", "s": "stop", "o": "open the goal"},
    "goal_ask": {"a": "allow once", "r": "deny", "s": "stop the goal", "o": "open the session"},
    "goal_replan": {"a": "apply the new plan", "r": "keep the old plan", "s": "stop the goal", "o": "open the plan"},  # R2
    "ollama_steward": {"a": "set aside", "o": "open Local"},  # 3.3.4.0 R4: the steward's note; 3.3.16.0 R2: Local -> Hosts
    "background_done": {"a": "set aside", **OPEN},  # 3.4.1.3: background work finished while the session was idle
    "crew_try": {"a": "set aside", **OPEN},  # 3.6.0.0 R1: a Try it run ended while the Agents tab did not show it
}
BG_THEN = {"continue": "the agent picks it up by itself", "tell": "it is read with your next message"}
# 3.3.5.0 R4: a preflight card (agent/preflight.py) answers accept = compact, edit = the bigger-window model, stop
PREFLIGHT_KEYS = {"a": "compact", "r": "bigger-window model", "s": "stop", **OPEN}
TEXT_FOR = {"permission": "r", "question": "r", "plan": "r", "approval": "r",
            "goal_plan": "r", "goal_gate": "r", "goal_budget": "r", "goal_ask": "r",
            "goal_replan": "r"}
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


NO_PAGE = "waiting on you in Studio"  # 3.3.11.0 R2: a headless session's ask with no Studio page open


def _parked(row: dict, pages: Optional[int]) -> None:
    """A session with no terminal (headless_session.py) parks its asks: only Studio's Prompt panel answers them."""
    row["parked"] = True
    if not pages:
        row["what"] = f"{row['what']} -- {NO_PAGE}"
        row["detail"] = f"{row['detail']} (no terminal: open Session's Prompt panel to answer)".strip()


def session_rows(view: dict, asks: dict, seen: dict, now: float, pages: Optional[int] = None) -> list:
    out = []
    for h in view.get("harnesses") or []:
        for s in h.get("sessions") or []:
            pend = s.get("pending") if isinstance(s.get("pending"), dict) else {}
            listed = False
            for kind in CARD_KINDS:
                for rid in pend.get(kind) or []:
                    rid = str(rid)
                    ask = asks.get((str(h.get("id")), str(s.get("session_id")), rid)) or {}
                    what, detail = _what(kind, ask)
                    out.append(_row(kind, rid, h, s, str(ask.get("agent_id") or "main"), what, detail, seen, now,
                                    request_id=rid))
                    if kind == "approval" and rid.startswith("preflight-"):  # 3.3.5.0 R4: agent/preflight.py's card
                        out[-1].update(keys={**PREFLIGHT_KEYS}, text_for=None)
                    if s.get("kind") == "headless":
                        _parked(out[-1], pages)
                    listed = True
            for a in s.get("agents") or []:
                aid = str(a.get("agent_id") or "")
                if a.get("state") == "waiting" and not listed:
                    out.append(_row("waiting", aid, h, s, aid, f"{a.get('name') or aid} waits on you",
                                    one_line(a.get("current") or a.get("task"), 200), seen, now))
                elif a.get("state") == "paused":
                    out.append(_row("paused", aid, h, s, aid, f"{a.get('name') or aid} is paused",
                                    "it holds at its next step until you resume it", seen, now))
            bg = s.get("bg_done") if isinstance(s.get("bg_done"), dict) else None
            if bg:  # 3.4.1.3 (agent/bg_pickup.py): no prompt needed to learn it; a new batch is a new row (one alert)
                n = int(bg.get("count") or 1)
                out.append(_row("background_done", f"bg-{bg.get('since')}", h, s, "main",
                                "Background work finished" + (f" ({n} tasks)" if n > 1 else ""),
                                one_line(f"{bg.get('line') or ''} -- {BG_THEN.get(str(bg.get('mode')), '')}", 240),
                                seen, now))
    return out


def orchestra_rows(runs: list, local: dict, seen: dict, now: float, within_s: float = 86400.0) -> list:
    return [_row("orchestra_gate", str(r.get("run_id")), local, None, "", f"Orchestra run {r.get('run_id')} stopped at the gate",
                 one_line(r.get("stop_reason") or r.get("goal_what"), 240), seen, now, run=r.get("run_id"))
            for r in runs if r.get("state") == "stopped" and now - float(r.get("created") or 0) < within_s]


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


def build(view: dict, *, asks: Optional[dict] = None, orchestra=(), reached=(), conflicts=(),
          seen: Optional[dict] = None, acks=(), now: Optional[float] = None, home=None, packs=(),
          pages: Optional[int] = None) -> list:
    """Every row, newest decision last, set-aside rows left out."""
    now = now or time.time()
    seen = seen if seen is not None else {}
    local = next((h for h in view.get("harnesses") or [] if h.get("local")), {"id": None, "name": "this harness", "local": True})
    rows = (session_rows(view, asks or {}, seen, now, pages)
            + orchestra_rows(list(orchestra), local, seen, now)
            + cap_rows(list(reached), local, seen, now) + conflict_rows(list(conflicts), view, seen, now))
    if home is not None:  # 3.1.8.0 R1: the supervisor's parked decisions (live/supervise_attention.py)
        from halo_harness.live.supervise_attention import rows as supervise_rows
        rows += supervise_rows(home, local, seen, now)
    if home is not None:  # 3.3.4.0 R4: the Ollama steward's newest note that raises the signal
        from halo_harness.live.steward_attention import rows as steward_rows
        rows += steward_rows(home, local, seen, now)
    if home is not None:  # 3.6.0.0 R1: a Try it run that ended unseen (live/crew_attention.py)
        from halo_harness.live.crew_attention import rows as crew_rows
        rows += crew_rows(home, local, seen, now)
    if packs:  # 3.2.0.0 R3: a pack's own rows (`pack:<id>:<kind>`, live/pack_attention.py)
        from halo_harness.live.pack_attention import rows as pack_rows
        rows += pack_rows(list(packs), local, seen, now)
    gone = set(acks)
    return sorted([r for r in rows if r["id"] not in gone], key=lambda r: r["since"])
