"""halo_harness.studio.voice_api -- Local -> Voice's view (Halo 3.3.9.0 R3; docs/STUDIO-local-voice.md), reached through
studio/local_api.dispatch_local (prefix `local/`). The same loopback / origin / token guard as every Studio route; never
a model call, nothing here starts a process (studio/voice_act_api.py does, when a button is pressed).

    GET local/voice?session=<id>&loop=1   {servers, catalog, devices, sessions, loop, turns, stats, talk, cli}; `loop` is
                                   read only with loop=1 (the page asks on open and after a loop button, not on its
                                   15 s refresh: each read is a `/voice status` the session's transcript notes)
        servers   stt and tts: running (its url, model, device) or stopped (the model it would start, the cost line), or
                  on another halo (voice.<kind>_server: stt@pc, its line); the steward's findings keyed stt|<model> /
                  tts|<model> and voice|<stage>
        catalog   the speech catalog: each model's kind, engine, sizes, built, present (its folder) or the download line
        devices   this machine's microphones and speakers (voice/audio.devices): the terminal loop's, not the browser's
        sessions  this machine's running sessions (the registry), the Talk target; `loop` the watched one's voice state
                  (`/voice status` through its control socket)
        turns     the newest latency cards (voice/turns.jsonl), newest first; stats `halo voice stats`
        talk      what Talk does and what it costs, said before the first click: the microphone permission, the servers
                  it would start and their seconds; a local op costs time, not dollars
"""

from __future__ import annotations

TURNS = 10


def _findings(state_dir) -> list:
    try:
        from halo_harness.ollama_steward.rules import findings
        rows = [f for f in findings(state_dir) if str(f.get("key") or "").split("|", 1)[0] in ("stt", "tts", "voice")]
    except Exception:
        return []
    keep = ("id", "rule", "severity", "finding", "key", "model")
    return [{k: f.get(k) for k in keep} for f in rows]


def servers(state_dir, found=None) -> list:
    from halo_harness.providers.local_server import _entry
    from halo_harness.voice.ensure import cost_line, picks, running
    from halo_harness.voice.remote import parse, setting
    pk, out = picks(state_dir), []
    found = _findings(state_dir) if found is None else found
    for kind in ("stt", "tts"):
        model, device = pk[kind]
        row = {"kind": kind, "setting": setting(kind), "model": model, "running": False, "url": None, "device": None,
               "remote": None, "cost": cost_line(kind, model, device), "bundle": pk["bundle"],
               "findings": [f for f in found if str(f.get("key") or "").startswith(kind + "|")],
               "cli": f"halo local serve --{kind} {model}" + (f" --device {device}" if device else "")}
        if parse(row["setting"]):
            row.update(remote=f"{kind} on {parse(row['setting'])} over the LAN (voice.{kind}_server: {row['setting']})",
                       cli=f"halo config set voice.{kind}_server local")
        else:
            url = running(kind, state_dir)
            if url:
                reg = _entry(state_dir, kind) or {}
                row.update(running=True, url=url, model=reg.get("model") or model, device=reg.get("device"),
                           cli=f"halo local stop {kind}")
        out.append(row)
    return out


def catalog() -> list:
    from halo_harness.voice import catalog as C
    from halo_harness.voice.install import present
    out = []
    for r in C.ROWS:
        where = present(r)
        out.append({"name": r.name, "kind": r.kind, "engine": r.engine, "repo": r.repo, "download_gb": r.download_gb,
                    "gpu_gb": r.gpu_gb, "cpu_gb": r.cpu_gb, "built": r.built, "verified": r.verified, "note": r.note,
                    "present": str(where) if where else None,
                    "size_line": f"{r.name}: {r.download_gb:g} GB from {r.repo}{C.unverified(r)}",
                    "cli": f"halo voice download {r.name}" if r.built else C.no_engine_line(r)})
    return out


def sessions(state_dir=None) -> list:
    from halo_harness.voice.turn import public, sessions as live
    try:
        return [public(r) for r in live(state_dir)]
    except Exception:
        return []


def loop_state(sid: str, state_dir=None) -> dict:
    """The watched session's voice: `/voice status` through its control socket."""
    out = {"session": sid, "on": False, "mode": None, "lines": []}
    if not sid:
        return out
    from halo_harness.remote.client import ControlClient
    from halo_harness.voice.turn import TurnError, pick, sessions as live
    try:
        row = pick(live(state_dir), sid)
        c = ControlClient(str(row["endpoint"]), row.get("token"), timeout=5.0)
        try:
            r = c.call("slash", name="voice", args="status")
        finally:
            c.close()
    except (TurnError, OSError, TimeoutError, ValueError) as e:
        out["lines"] = [getattr(e, "line", None) or f"the session did not answer: {e}"]
        return out
    lines = str((r.get("result") or {}).get("output") or r.get("error") or "").splitlines()
    head = lines[0] if lines else ""
    on = head.startswith("voice is on")
    out.update(on=on, mode=head.split(":", 1)[1].split("(")[0].strip() if on and ":" in head else None, lines=lines)
    return out


def talk_says(srv: list) -> dict:
    """What Talk does and costs, before the first click."""
    starts = [s["cost"].replace("starting ", "", 1) for s in srv if not s["running"] and not s["remote"]]
    far = [s["remote"] for s in srv if s["remote"]]
    said = ("Talk asks this browser for the microphone (once), records until you press Talk again (up to 30 s), "
            "sends it to the speech-to-text server, puts the transcript to the session exactly as typed text, and "
            "plays the reply's audio here.")
    cost = (" It starts " + "; ".join(starts) + " (they keep running for the next turn: Stop here)." if starts else
            " The speech servers are running.") + (" " + "; ".join(far) + "." if far else "")
    return {"confirm": said + cost + " A local turn costs time, not dollars: about a second when the models are warm.",
            "starts": starts, "max_s": 30, "rate": 16000}


def get_voice(req):
    from halo_harness.voice import audio
    from halo_harness.voice.latency import line, rows, stats, stats_lines
    found = _findings(req.state_dir)
    srv = servers(req.state_dir, found)
    turns = [{**r, "line": line(r)} for r in reversed(rows(req.state_dir, TURNS))]
    st = stats(req.state_dir)
    try:
        devs = audio.devices()
    except Exception as e:
        devs = {"inputs": [], "outputs": [], "error": f"{type(e).__name__}: {e}"}
    return 200, {"servers": srv, "catalog": catalog(), "devices": devs, "sessions": sessions(req.state_dir),
                 "loop": loop_state(str(req.query.get("session") or "") if req.query.get("loop") else "", req.state_dir), "turns": turns,
                 "stats": {**st, "lines": stats_lines(st)}, "talk": talk_says(srv), "findings": found,
                 "cli": "halo voice models · halo voice stats · halo doctor --voice"}


def dispatch_voice(req):
    """The answer for a `local/voice*` path, or None for any other path."""
    if req.path != "local/voice" and not req.path.startswith("local/voice/"):
        return None
    if req.path == "local/voice":
        return get_voice(req) if req.method == "GET" else (405, {"error": "method not allowed"})
    from halo_harness.studio.voice_act_api import ROUTES
    fn = ROUTES.get((req.method, req.path))
    if fn is not None:
        return fn(req)
    if any(p == req.path for _m, p in ROUTES):
        return 405, {"error": "method not allowed"}
    return 404, {"error": f"no route for {req.method} /api/{req.path}"}
