"""halo_harness.studio.live_answer -- one key on one attention row, routed through the route that already answers
that kind (Halo 3.0.5.0 R4, D3). studio/live_panels_api.py `POST live/attention/answer` calls `act`; the decision is
journaled there with `by`.

    permission      a allow once | r deny (text: the reason) | s deny, then stop the agent
    question        r answer (text) | s answer "(stopped from Live)", then stop the agent
    plan            a approve | r send back (text: feedback) | s send back, then stop the agent
    approval        a accept | r edit (text: the instruction) | s stop (the card's own stop)
    waiting         s stop the agent
    paused          a resume the agent (or the session) | s stop it
    orchestra_gate, conflict   a set aside (journal kind `ack`, hidden from then on)
    ollama_steward  a set aside | o open the Ollama panel (3.3.4.0 R4, live/steward_attention.py)
    cap             a lift for today: resume what the cap paused
    goal_plan | goal_gate | goal_budget | goal_ask | goal_replan   a supervisor decision (3.1.8.0 R1/R2,
                    live/supervise_attention.py): the answer is written to its decision file; the supervisor applies it
    pack:<id>:<kind>  a | r | s the pack's labels: answers/<row>.json in its data folder; o its section (3.2.0.0 R3)
    every kind      o open: answered with where to open it, nothing is sent

Cards go through `live/<harness>/<sid>/command {cmd: answer, ...}` (this harness's control socket); stops through
`live/<harness>/<sid>/agents/<aid>/command`.
"""

from __future__ import annotations

STOP_NOTE = "stopped from the attention queue"
ANSWER = {
    ("permission", "a"): {"action": "allow", "scope": "once"},
    ("permission", "r"): {"action": "deny"},
    ("permission", "s"): {"action": "deny"},
    ("question", "s"): {"answer": "(stopped from Live)"},
    ("plan", "a"): {"approved": True},
    ("plan", "r"): {"approved": False},
    ("plan", "s"): {"approved": False, "feedback": "stop"},
    ("approval", "a"): {"action": "accept"},
    ("approval", "r"): {"action": "edit"},
    ("approval", "s"): {"action": "stop"},
}
NEEDS_TEXT = {("question", "r"), ("plan", "r"), ("approval", "r"),
              ("goal_gate", "r"), ("goal_budget", "r")}
SET_ASIDE = ("orchestra_gate", "conflict", "ollama_steward")  # 3.3.4.0 R4: the steward's note
SUPERVISE = ("goal_plan", "goal_gate", "goal_budget", "goal_ask", "goal_replan")  # R2: goal_replan


def _sub(req, path: str, body: dict, params: dict):
    from halo_harness.studio.api import Request
    return Request(method="POST", path=path, query={}, body=body, cwd=req.cwd, state_dir=req.state_dir,
                   server=req.server, params=params)


def session_command(req, hid: str, sid: str, body: dict):
    from halo_harness.studio.live_api import post_session_command
    return post_session_command(_sub(req, f"live/{hid}/{sid}/command", body, {"hid": hid, "sid": sid}))


def agent_command(req, hid: str, sid: str, aid: str, body: dict):
    from halo_harness.studio.live_api import post_agent_command
    return post_agent_command(_sub(req, f"live/{hid}/{sid}/agents/{aid}/command", body,
                                   {"hid": hid, "sid": sid, "aid": aid}))


def open_target(row: dict) -> dict:
    kind, t = row["kind"], row.get("target") or {}
    if kind.startswith("pack:"):  # 3.2.0.0 R3: a pack's own row opens its section
        from halo_harness.live.pack_attention import open_target as pack_target
        return pack_target(row)
    if kind == "orchestra_gate":
        return {"section": "agents", "view": "live", "run": t.get("run")}  # 3.4.0.0 D: the run on Live, else its report in History
    if kind in SUPERVISE:  # 3.1.8.0 R1
        from halo_harness.live.supervise_attention import open_target as supervise_target
        return supervise_target(row)
    if kind == "ollama_steward":  # 3.3.4.0 R4
        from halo_harness.live.steward_attention import open_target as steward_target
        return steward_target(row)
    if kind == "cap":
        return {"section": "live", "panel": "fleet-costs", "scope": t.get("scope"), "key": t.get("key")}
    if kind == "conflict":
        return {"section": "live", "panel": "fleet-map", "file": t.get("file"), "a": t.get("a"), "b": t.get("b")}
    return {"section": "live", "panel": "fleet-agent", "harness": row.get("harness"), "session_id": row.get("session_id"),
            "agent_id": row.get("agent_id") or "main"}


def _card(req, row: dict, key: str, text: str):
    kind = row["kind"]
    fields = dict(ANSWER[(kind, key)])
    fields.update(kind=kind, request_id=(row.get("target") or {}).get("request_id"))
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
    if kind.startswith("pack:"):  # 3.2.0.0 R3: the pack's code reads the answer file
        from halo_harness.live.pack_attention import answer as pack_answer
        return pack_answer(req, row, key, text)
    if kind in SUPERVISE:  # 3.1.8.0 R1: the answer goes into the decision file; the supervisor applies it
        from halo_harness.live.supervise_attention import answer as supervise_answer
        return supervise_answer(req, row, key, text)
    if kind in SET_ASIDE:
        watcher.acks.add(row["id"])
        from halo_harness.live import journal
        journal.append(watcher.home, "ack", harness=row.get("harness"), harness_name=row.get("harness_name"),
                       session_id=row.get("session_id"), row=row["id"])
        return 200, {"set_aside": True}, label
    if kind == "cap":
        from halo_harness.studio.live_watch_sources import by
        return 200, {"lifted": True, "resumed": watcher.lift(t.get("scope"), t.get("key"), by(req.state_dir))}, label
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
