"""halo_harness.studio.fleet_answer -- one key on one attention row, routed
through the route that already answers that kind (Halo 3.0.5.0 "Fleet"
round R4, D3). studio/fleet_panels_api.py `POST fleet/attention/answer`
calls `act`; the decision is journaled there with `by`.

    permission      a allow once | r deny (text: the reason) | s deny, then stop the agent
    question        r answer (text) | s answer "(stopped from Fleet)", then stop the agent
    plan            a approve | r send back (text: feedback) | s send back, then stop the agent
    approval        a accept | r edit (text: the instruction) | s stop (the card's own stop)
    fleet_ask       a allow | r deny                   the `fleet-ask:` question on this harness
    waiting         s stop the agent
    paused          a resume the agent (or the session) | s stop it
    flow_gate       a accept | r redo (text: the instruction) | s stop   (flow/runs/<id>/answer)
    orchestra_gate, control_ask, conflict   a set aside (journal kind `ack`, hidden from then on)
    cap             a lift for today: resume what the cap paused
    mission_plan    a approve and run | r edit (text: "part 2 to kali" / "drop 3") | s drop the mission  (R7)
    mission_ask     a allow | r deny                   the `fleet-ask:mission-` card of a hub's run_task here
    mission_claim   a set aside
    every kind      o open: answered with where to open it, nothing is sent

Cards go through `fleet/<harness>/<sid>/command {cmd: answer, ...}` (this
harness: its control socket; a member: the hub, which a member answers only
under fleet.allow_control all + fleet.allow_answers); stops through
`fleet/<harness>/<sid>/agents/<aid>/command`.
"""

from __future__ import annotations

STOP_NOTE = "stopped from the Fleet attention queue"
ANSWER = {
    ("permission", "a"): {"action": "allow", "scope": "once"},
    ("permission", "r"): {"action": "deny"},
    ("permission", "s"): {"action": "deny"},
    ("question", "s"): {"answer": "(stopped from Fleet)"},
    ("plan", "a"): {"approved": True},
    ("plan", "r"): {"approved": False},
    ("plan", "s"): {"approved": False, "feedback": "stop"},
    ("approval", "a"): {"action": "accept"},
    ("approval", "r"): {"action": "edit"},
    ("approval", "s"): {"action": "stop"},
    ("fleet_ask", "a"): {"answer": "allow"},
    ("fleet_ask", "r"): {"answer": "deny"},
    ("mission_ask", "a"): {"answer": "allow"},
    ("mission_ask", "r"): {"answer": "deny"},
}
NEEDS_TEXT = {("question", "r"), ("plan", "r"), ("approval", "r"), ("flow_gate", "r"), ("mission_plan", "r")}
SET_ASIDE = ("orchestra_gate", "control_ask", "conflict", "mission_claim")
FLOW = {"a": "accept", "r": "redo", "s": "stop"}


def _sub(req, path: str, body: dict, params: dict):
    from halo_harness.studio.api import Request
    return Request(method="POST", path=path, query={}, body=body, cwd=req.cwd, state_dir=req.state_dir,
                   server=req.server, params=params)


def session_command(req, hid: str, sid: str, body: dict):
    from halo_harness.studio.fleet_hub_api import post_session_command
    return post_session_command(_sub(req, f"fleet/{hid}/{sid}/command", body, {"hid": hid, "sid": sid}))


def agent_command(req, hid: str, sid: str, aid: str, body: dict):
    from halo_harness.studio.fleet_hub_api import post_agent_command
    return post_agent_command(_sub(req, f"fleet/{hid}/{sid}/agents/{aid}/command", body,
                                   {"hid": hid, "sid": sid, "aid": aid}))


def open_target(row: dict) -> dict:
    kind, t = row["kind"], row.get("target") or {}
    if kind == "flow_gate":
        return {"section": "flow", "run": t.get("run"), "step": t.get("step")}
    if kind == "orchestra_gate":
        return {"section": "orchestra", "run": t.get("run")}
    if kind == "cap":
        return {"section": "fleet", "panel": "fleet-costs", "scope": t.get("scope"), "key": t.get("key")}
    if kind.startswith("mission_") and (kind != "mission_ask" or t.get("mission")):  # R8: a run_task card names its mission
        from halo_harness.fleet.mission_attention import open_target as mission_target
        return mission_target(row)
    if kind == "conflict":
        return {"section": "fleet", "panel": "fleet-map", "file": t.get("file"), "a": t.get("a"), "b": t.get("b")}
    return {"section": "fleet", "panel": "fleet-agent", "harness": row.get("harness"), "session_id": row.get("session_id"),
            "agent_id": row.get("agent_id") or "main"}


def _card(req, row: dict, key: str, text: str):
    kind = row["kind"]
    fields = dict(ANSWER[(kind, key)])
    fields.update(kind="question" if kind in ("fleet_ask", "mission_ask") else kind, request_id=(row.get("target") or {}).get("request_id"))
    if (kind, key) == ("permission", "r") and text:
        fields["message"] = text
    elif (kind, key) == ("question", "r"):
        fields["answer"] = text
    elif (kind, key) == ("plan", "r"):
        fields["feedback"] = text
    elif (kind, key) == ("approval", "r"):
        fields["instruction"] = text
    return session_command(req, row["harness"], row["session_id"], {"cmd": "answer", **fields})


def act(req, watcher, row: dict, key: str, text: str):
    """`(status, body, answer)` for `key` on `row` (already checked against `row["keys"]`)."""
    kind, t = row["kind"], row.get("target") or {}
    label = row["keys"][key]
    if key == "o":
        return 200, {"open": open_target(row)}, label
    if kind == "mission_plan":  # 3.0.6.0 R7
        from halo_harness.fleet.mission_attention import answer
        return answer(req, row, key, text)
    if kind in SET_ASIDE:
        watcher.acks.add(row["id"])
        from halo_harness.fleet import journal
        journal.append(watcher.home, "ack", harness=row.get("harness"), harness_name=row.get("harness_name"),
                       session_id=row.get("session_id"), row=row["id"])
        return 200, {"set_aside": True}, label
    if kind == "cap":
        from halo_harness.studio.fleet_watch_io import by
        return 200, {"lifted": True, "resumed": watcher.lift(t.get("scope"), t.get("key"), by(req.state_dir))}, label
    if kind == "flow_gate":
        from halo_harness.studio.flow_api import post_answer
        body = {"step": t.get("step"), "action": FLOW[key], "instruction": text}
        status, got = post_answer(_sub(req, f"flow/runs/{t.get('run')}/answer", body, {"run": str(t.get("run"))}))
        return status, got, label
    hid, sid, aid = row["harness"], row["session_id"], row.get("agent_id") or "main"
    if (kind, key) in ANSWER:
        status, got = _card(req, row, key, text)
        if key != "s" or kind == "approval" or status >= 300:
            return status, got, label
    elif kind == "paused" and key == "a":
        body = {"cmd": "resume"} if aid == "main" else {"cmd": "resume", "agent_id": aid}
        status, got = session_command(req, hid, sid, body)
        return status, got, label
    status, got = agent_command(req, hid, sid, aid, {"cmd": "stop", "reason": STOP_NOTE})
    return status, got, label
