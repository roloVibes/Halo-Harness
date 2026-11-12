"""halo_harness.studio.fleet_recording_api -- flight recordings and the canvas
replay of Studio's Fleet section (Halo 3.0.5.0 "Fleet" round R4, D5 / D12;
3.1.0.0 R2 cut it out of fleet_extras_api.py), appended to
studio/fleet_view_api.py's ROUTES; the same loopback + token guard.

    POST fleet/<h>/<sid>/recording[?agent=<aid>]
        -> {ok, path, name, url: "fleet/recordings/<name>", bytes, agents, states}   ~/.halo/recordings/<sid>[-<aid>].html
    GET  fleet/recordings/<name>      the recording's HTML (text/html, attachment; its own CSP)
    GET  fleet/replay?session=<sid>[&harness=<h>]
        -> {session_id, harness, title, started, ended, cost_usd, agents: [...], states: [{t, agent_id, state,
            activity, tool?}], costs: [{t, usd}], agent_costs: [{t, agent_id, usd}], marks: [...], bands: [...]}
        the session's time axis: the scrubber under Agents -> Live replays it (3.4.1.0 R1, live/timeline.py)
    GET  fleet/replay?run=<run id>
        -> a goal run's replay payload (live/replay_run.build_run, kind "run": the lead and its lanes, each lane's state
           changes and its cost at its end), what the scrubber draws a goal run from (3.4.1.1, defect 60)

A member's session comes through the hub (`agent_tail` per agent, which needs
its share `full`); this harness's from its transcripts on disk.
"""

from __future__ import annotations

from halo_harness.studio import fleet_watch_sources as sources
from halo_harness.studio.fleet_handoff_api import _find, _tail


def _history(req, hid: str, sid: str):
    """`(hist, harness name)` or `(None, error)`: this harness's from disk, a member's through the hub."""
    from halo_harness.live import history, recording
    _view, h, s, local = _find(req, hid, sid)
    if local:
        path = history.find(req.state_dir, sid)
        if path is None:
            return None, (404, {"error": f"no transcript of session {sid!r} on this harness"})
        live = {str(a.get("agent_id")): a.get("state") for a in (s or {}).get("agents") or []
                if a.get("state") in ("running", "waiting", "paused", "queued")}
        return history.read(path, live_states=live), (h or {}).get("name") or sources.by(req.state_dir)
    if s is None:
        return None, (404, {"error": f"no live session {sid!r} on {hid}"})
    tails = {str(a.get("agent_id")): _tail(req, h, sid, str(a.get("agent_id"))) for a in s.get("agents") or []}
    return recording.from_tails(s, tails), h.get("name") or hid


def post_recording(req):
    from halo_harness.live import recording
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
    from halo_harness.live.recording import path_for
    from halo_harness.studio.raw_body import html_download
    path = path_for(req.state_dir, req.params["name"])
    if path is None:
        return 404, {"error": f"no recording {req.params['name']!r}"}
    return 200, html_download(path.read_bytes(), path.name)


def get_replay(req):
    sid, run = str(req.query.get("session") or "").strip(), str(req.query.get("run") or "").strip()
    if run:  # 3.4.1.1 (60): a goal run's axis from its record (live/replay_run.py): each lane's states and costs at their times
        from halo_harness.live import replay_file, replay_run
        run_dir = replay_run.find(req.cwd, run)
        if run_dir is None:
            return 404, {"error": f"no goal run {run!r} in this repo"}
        try:
            return 200, replay_run.build_run(req.state_dir, run_dir)
        except replay_file.ReplayError as e:
            return 404, {"error": str(e)}
    if not sid:
        return 422, {"error": "name the session: ?session=<id> (or a goal run: ?run=<id>)", "problems": []}
    hid = str(req.query.get("harness") or "local")
    hist, name = _history(req, hid, sid)
    if hist is None:
        return name
    from halo_harness.live import timeline
    keep = ("session_id", "title", "started", "ended", "cost_usd", "agents", "states", "costs", "agent_costs")
    return 200, {"harness": name, **{k: hist.get(k) for k in keep}, **timeline.of(hist)}  # 3.4.1.0 R1: marks, bands


_ID = r"[A-Za-z0-9_.:-]+"
ROUTES = [("POST", rf"^fleet/(?P<hid>{_ID})/(?P<sid>{_ID})/recording$", post_recording),
          ("GET", r"^fleet/recordings/(?P<name>[A-Za-z0-9_.-]+\.html)$", get_recording),
          ("GET", r"^fleet/replay$", get_replay)]
