"""halo_harness.studio.postmortem_api -- Halo 3.3.6.0 R4: "Why this answer?" in Studio (agent/postmortem.py;
added to studio/sessions_api.py's routes; docs/STUDIO-session.md).

    GET sessions/<sid>/postmortem?turn=N&agent=ID&at=<unix s>
        {ok, line, details, causes, model, host, turn, session, dialect, ladder, cli}: one assistant turn of the
        main agent (or of a sub-agent: `agent` is its own session id) reconstructed from the traffic ledger and
        the session log (a sub-agent's ledger lines are its own `agent-<id>`; `main` is the main agent); `at` picks the turn whose call ended at or before that time (a Live row's time);
        no `turn` and no `at`: the newest. A turn with no local call answers ok false with the line saying so.

Read-only: the ledger and the log are read, nothing is sent.
"""

from __future__ import annotations


def _int(v):
    try:
        return int(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _float(v):
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def get_postmortem(req):
    from halo_harness.agent.postmortem import postmortem
    from halo_harness.safe_id import is_safe_session_id
    q = req.query or {}
    sid = str(req.params.get("sid") or "")
    agent = str(q.get("agent") or "").strip()
    if agent and not is_safe_session_id(agent):
        return 422, {"error": f"not an agent id: {agent!r}", "problems": ["agent"]}
    if agent in ("", "main"):
        agent = ""
    target = (agent if agent.startswith("agent-") else f"agent-{agent}") if agent else sid  # a child's log id
    got = postmortem(req.state_dir, target, turn=_int(q.get("turn")), at=_float(q.get("at")))
    cli = "halo session postmortem" + (f" --session {sid}" if sid else "") + (
        f" --turn {got['turn']}" if got.get("turn") is not None else "") + (f" --agent {agent}" if agent else "")
    return 200, {**got, "cli": cli}


ROUTES = [("GET", r"^sessions/(?P<sid>[A-Za-z0-9_.-]+)/postmortem$", get_postmortem)]
