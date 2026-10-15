"""halo_harness.studio.fleet_extras_api -- hand-offs, flight recordings and the
canvas replay (Halo 3.0.5.0 "Fleet" round R4, D4 / D5 / D12), appended to
studio/fleet_hub_api.py's ROUTES; the same loopback + token guard.

    POST fleet/<h>/<sid>/agents/<aid>/handoff {mode: take_over | hand_to, brief?, to?, assignee?}
        take_over  a redirect steer with `brief`, recorded as a hand-off in the agent's transcript and its
                   parent's -> {ok, mode, result}
        hand_to    the agent's task, last hand-back and files as one brief: a Paperclip issue assigned to `to`'s
                   company agent when Org mode is on, else <repo>/.halo/handoffs/<id>.md (the state directory's
                   handoffs/ when the repo is not on this machine); then the agent is stopped
                   -> {ok, mode, to, title, issue? | path?, note, stopped: {status, result}}
    POST fleet/<h>/<sid>/recording[?agent=<aid>]
        -> {ok, path, name, url: "fleet/recordings/<name>", bytes, agents, states}   ~/.halo/recordings/<sid>[-<aid>].html
    GET  fleet/recordings/<name>      the recording's HTML (text/html, attachment; its own CSP)
    GET  fleet/replay?session=<sid>[&harness=<h>]
        -> {session_id, harness, title, started, ended, cost_usd, agents: [...], states: [{t, agent_id, state,
            activity, tool?}], costs: [{t, usd}]}   the `agent_state` history the Roles canvas replays

A member's session comes through the hub (`agent_tail` per agent, which needs
its share `full`); this harness's from its transcripts on disk. Every hand-off
is journaled (the digest). `PAPERCLIP` is the client factory (tests stub it).
"""

from __future__ import annotations

from pathlib import Path

from halo_harness.fleet import journal
from halo_harness.studio import fleet_watch_io as io

PAPERCLIP = None
TAIL_N = 300


def _find(req, hid: str, sid: str):
    view = io.view(req.server, req.state_dir)
    local = io.is_local(req.server, hid)
    h = next((x for x in view.get("harnesses") or [] if (x.get("local") if local else str(x.get("id")) == hid)), None)
    s = next((x for x in (h or {}).get("sessions") or [] if x.get("session_id") == sid), None)
    return view, h, s, local


def _tail(req, h: dict, sid: str, aid: str) -> list:
    status, got = io.session_cmd(req.server, req.state_dir, str(h.get("id")), sid, "agent_tail",
                                 {"agent_id": aid, "n": TAIL_N}, 8.0)
    res = (got or {}).get("result") if status == 200 else None
    return [e for e in (res or {}).get("events") or [] if isinstance(e, dict)]


def post_handoff(req):
    from halo_harness.fleet import handoff
    from halo_harness.fleet.history import edited_files
    hid, sid, aid = req.params["hid"], req.params["sid"], req.params["aid"]
    body = req.body if isinstance(req.body, dict) else {}
    mode, text = str(body.get("mode") or ""), str(body.get("brief") or "").strip()
    if mode not in ("take_over", "hand_to"):
        return 422, {"error": f"mode is take_over or hand_to, got {mode!r}", "problems": []}
    view, h, s, local = _find(req, hid, sid)
    if s is None:
        return 404, {"error": f"no live session {sid!r} on {hid}"}
    agent = next((a for a in s.get("agents") or [] if a.get("agent_id") == aid), None)
    if agent is None:
        return 404, {"error": f"no agent {aid!r} in session {sid}"}
    by, hname = io.by(req.state_dir), h.get("name") or str(h.get("id"))[:8]
    note = {"harness": h.get("id"), "harness_name": hname, "session_id": sid, "agent_id": aid,
            "agent": agent.get("name") or aid, "by": by}
    if mode == "take_over":
        if not text:
            return 422, {"error": "a take over needs the new brief", "problems": []}
        status, got = io.session_cmd(req.server, req.state_dir, str(h["id"]), sid, "agent_steer",
                                     {"agent_id": aid, "text": text, "mode": "redirect", "handoff": True})
        if status >= 300 and status != 202:
            return status, got
        journal.append(req.state_dir, "handoff", action="take_over", text=text[:300], **note)
        return 200, {"ok": True, "mode": mode, "result": got}
    to = str(body.get("to") or "").strip()
    target = next((x for x in view.get("harnesses") or [] if to and to in (str(x.get("id")), x.get("name"))), None)
    if not to:
        return 422, {"error": "hand to whom? {to: <harness id or name>}", "problems": []}
    target = target or {"id": to, "name": to}
    entries = _tail(req, h, sid, aid)
    files = []
    w = getattr(req.server, "fleet_watch", None)
    for f in (w.touches.files_of(str(h.get("id")), sid, aid) if w else []) + edited_files(entries):
        if f not in files:
            files.append(f)
    title, md = handoff.brief(harness=h, session=s, agent=agent, handback=handoff.handback_of(entries, agent),
                              files=files, by=by, to=str(target.get("name")) + (f" ({text})" if text else ""))
    from halo_harness.paperclip.mode import org_mode_enabled
    out = {"ok": True, "mode": mode, "to": target.get("name"), "title": title, "note": ""}
    if org_mode_enabled():
        from halo_harness.paperclip.client import PaperclipError
        try:
            got = handoff.to_issue(req.state_dir, title, md, target, assignee=body.get("assignee") or None,
                                   client=PAPERCLIP(req.state_dir) if PAPERCLIP else None)
        except ValueError as e:
            return 409, {"error": str(e)}
        except (PaperclipError, OSError) as e:
            return 502, {"error": f"Paperclip: {e}"}
        out.update(issue=got["issue"], assignee=got["assignee"], assignee_name=got.get("assignee_name"), note=got["note"])
    else:
        proj = s.get("project") if isinstance(s.get("project"), dict) else {}
        root = proj.get("root") if local and proj.get("root") and Path(str(proj["root"])).is_dir() else req.state_dir
        out["path"] = str(handoff.to_file(root, handoff.handoff_id(aid), md))
    status, got = io.session_cmd(req.server, req.state_dir, str(h["id"]), sid, "agent_stop",
                                 {"agent_id": aid, "reason": f"handed to {target.get('name')}"})
    out["stopped"] = {"status": status, "result": got}
    journal.append(req.state_dir, "handoff", action="hand_to", to=target.get("name"),
                   issue=(out.get("issue") or {}).get("identifier") or (out.get("issue") or {}).get("id"),
                   path=out.get("path"), **note)
    return 200, out


def _history(req, hid: str, sid: str):
    """`(hist, harness name)` or `(None, error)`: this harness's from disk, a member's through the hub."""
    from halo_harness.fleet import history, recording
    _view, h, s, local = _find(req, hid, sid)
    if local:
        path = history.find(req.state_dir, sid)
        if path is None:
            return None, (404, {"error": f"no transcript of session {sid!r} on this harness"})
        live = {str(a.get("agent_id")): a.get("state") for a in (s or {}).get("agents") or []
                if a.get("state") in ("running", "waiting", "paused", "queued")}
        return history.read(path, live_states=live), (h or {}).get("name") or io.by(req.state_dir)
    if s is None:
        return None, (404, {"error": f"no live session {sid!r} on {hid}"})
    tails = {str(a.get("agent_id")): _tail(req, h, sid, str(a.get("agent_id"))) for a in s.get("agents") or []}
    return recording.from_tails(s, tails), h.get("name") or hid


def post_recording(req):
    from halo_harness.fleet import recording
    body = req.body if isinstance(req.body, dict) else {}
    agent = str(req.query.get("agent") or body.get("agent") or "").strip() or None
    hist, name = _history(req, req.params["hid"], req.params["sid"])
    if hist is None:
        return name
    path = recording.write(req.state_dir, hist, harness=str(name), agent=agent)
    return 200, {"ok": True, "path": str(path), "name": path.name, "url": f"fleet/recordings/{path.name}",
                 "bytes": path.stat().st_size, "agents": len(recording.scoped(hist, agent).get("agents") or []),
                 "states": len(recording.scoped(hist, agent).get("states") or [])}


def get_recording(req):
    from halo_harness.fleet.recording import path_for
    from halo_harness.studio.raw_body import html_download
    path = path_for(req.state_dir, req.params["name"])
    if path is None:
        return 404, {"error": f"no recording {req.params['name']!r}"}
    return 200, html_download(path.read_bytes(), path.name)


def get_replay(req):
    sid = str(req.query.get("session") or "").strip()
    if not sid:
        return 422, {"error": "name the session: ?session=<id>", "problems": []}
    hid = str(req.query.get("harness") or "local")
    hist, name = _history(req, hid, sid)
    if hist is None:
        return name
    keep = ("session_id", "title", "started", "ended", "cost_usd", "agents", "states", "costs")
    return 200, {"harness": name, **{k: hist.get(k) for k in keep}}


_ID = r"[A-Za-z0-9_.:-]+"
ROUTES = [("POST", rf"^fleet/(?P<hid>{_ID})/(?P<sid>{_ID})/agents/(?P<aid>{_ID})/handoff$", post_handoff),
          ("POST", rf"^fleet/(?P<hid>{_ID})/(?P<sid>{_ID})/recording$", post_recording),
          ("GET", r"^fleet/recordings/(?P<name>[A-Za-z0-9_.-]+\.html)$", get_recording),
          ("GET", r"^fleet/replay$", get_replay)]
