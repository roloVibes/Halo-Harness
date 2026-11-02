"""halo_harness.studio.voice_act_api -- Local -> Voice's buttons (Halo 3.3.9.0 R3; docs/STUDIO-local-voice.md), reached
through studio/voice_api.dispatch_voice. Each answer carries `cli`, the command that does the same.

    POST local/voice/server {kind, op: start | stop, model?, device?}   R1's `halo local serve --stt | --tts` (the cost
                                     line in the answer) / `halo local stop <kind>`
    POST local/voice/download {model, yes?}   without `yes`: the size line (the model, its GB, the repo, the folder)
                                     to confirm; with it: the 3.3.5.0 download job (`download` frames, Hugging Face's)
    POST local/voice/loop {session, op: on | off | ptt}   `/voice <op>` in that session through its control socket
    POST local/voice/talk {pcm_b64, rate, session}   Talk: one utterance the browser recorded (16-bit mono PCM) ->
                                     a job (202 {job}) that runs voice/turn.run against the session; `talk` frames:
                                     {job, seq, state: start | note | heard | audio | done | error, text?, audio_b64?,
                                     rate?, transcript?, reply?, line?, card?, bytes}
    GET  local/voice/talk?job=       the job's view (a page that opened late catches up)

The speech servers Talk needs and does not find running are started with their cost line first (voice/ensure.py); they
keep running for the next turn. Nothing here runs a model.
"""

from __future__ import annotations

import base64
import itertools
import threading
import time

SEAMS: dict = {}  # "download": fn(model, dest_dir=, token=, on_status=, cancel=) -> {ok, say} (the tests' download)
_JOBS: dict = {}
_LOCK = threading.Lock()
_SEQ = itertools.count(1)
PIECE = 12000  # 0.25 s of 24 kHz PCM16 per `talk` audio frame


def _body(req) -> dict:
    return req.body if isinstance(req.body, dict) else {}


def _publish(req):
    if req.server is None:
        return None
    from halo_harness.studio.events import bridge_for
    return bridge_for(req.server).publish_local


def post_server(req):
    from halo_harness.voice.ensure import cost_line, picks
    b = _body(req)
    kind, op = str(b.get("kind") or ""), str(b.get("op") or "")
    if kind not in ("stt", "tts") or op not in ("start", "stop"):
        return 422, {"error": "server takes {kind: stt | tts, op: start | stop}", "problems": ["kind", "op"]}
    if op == "stop":
        from halo_harness.providers.local_server import stop
        got = stop(kind, state_dir=req.state_dir)
        return (200 if got.get("ok") else 409), {**got, "ok": bool(got.get("ok")), "lines": [got.get("say") or ""],
                                                 "error": None if got.get("ok") else got.get("say"),
                                                 "cli": f"halo local stop {kind}"}
    from halo_harness.voice.launch import serve
    model, device = picks(req.state_dir)[kind]
    model, device = str(b.get("model") or model), (str(b.get("device") or "") or device)
    cost = cost_line(kind, model, device)
    code, lines, reg = serve(kind, model, device=device, state_dir=req.state_dir, wait_s=60.0)
    cli = f"halo local serve --{kind} {model}" + (f" --device {device}" if device else "")
    if code != 0 or reg is None:
        said = [ln for ln in lines if not ln.startswith("  ")] or lines
        return 409, {"error": said[-1] if said else f"{kind} did not start", "lines": lines, "cost": cost, "cli": cli}
    return 200, {"ok": True, "lines": [cost] + [ln for ln in lines if not ln.startswith("  ")], "cost": cost, "cli": cli}


def post_download(req):
    from halo_harness.studio.local_hf_api import pick_dir
    from halo_harness.voice import catalog, install
    b = _body(req)
    row = catalog.get(str(b.get("model") or ""))
    if row is None:
        return 404, {"error": f"{b.get('model')!r} is not in the speech catalog (halo voice models)"}
    cli = f"halo voice download {row.name}"
    where = install.present(row)
    if where is not None:
        return 200, {"ok": True, "present": str(where), "lines": [f"{row.name} is present: {where}"], "cli": cli}
    if not row.built:
        return 422, {"error": catalog.no_engine_line(row), "cli": cli}
    d, why = pick_dir(str(b.get("dir") or ""))
    if d is None:
        return 409, {"error": why, "cli": cli}
    size = f"{row.name}: {row.download_gb:g} GB from {row.repo}{catalog.unverified(row)} into {d}"
    if b.get("yes") is not True:
        return 200, {"confirm": size, "model": row.name, "dir": str(d), "gb": row.download_gb, "cli": cli}
    from halo_harness.models_library.hf_hub import token
    from halo_harness.studio import local_download_job as DJ
    fn = SEAMS.get("download") or install.download

    def run(repo, file, *, dest_dir, token, on_status, cancel, plan=None):
        return fn(row.name, dest_dir=dest_dir, token=token, on_status=on_status, cancel=cancel)
    view = DJ.start(d, row.repo, publish=_publish(req), token=token(), download=run)
    return 200, {**view, "confirm": size, "model": row.name, "cli": cli}


def post_loop(req):
    from halo_harness.remote.client import ControlClient
    from halo_harness.voice.turn import TurnError, pick, sessions
    b = _body(req)
    op, sid = str(b.get("op") or ""), str(b.get("session") or "")
    if op not in ("on", "off", "ptt"):
        return 422, {"error": "loop takes {session, op: on | off | ptt}", "problems": ["op"]}
    try:
        row = pick(sessions(req.state_dir), sid)
        c = ControlClient(str(row["endpoint"]), row.get("token"), timeout=60.0)
        try:
            r = c.call("slash", name="voice", args=op)
        finally:
            c.close()
    except TurnError as e:
        return e.status, {"error": e.line}
    except (OSError, TimeoutError, ValueError) as e:
        return 502, {"error": f"the session did not answer: {e}"}
    out = str((r.get("result") or {}).get("output") or r.get("error") or "")
    return (200 if r.get("ok") else 409), {"ok": bool(r.get("ok")), "lines": out.splitlines(),
                                           "cli": f"halo voice {'on' if op == 'ptt' else op} --session {row['session_id'][:8]}"
                                           + (" ptt" if op == "ptt" else "")}


def _view(job: dict) -> dict:
    return {k: v for k, v in job.items() if not k.startswith("_")}


def _send(job: dict, **data) -> None:
    with _LOCK:
        job["seq"] += 1
        job.update({k: v for k, v in data.items() if k not in ("audio_b64",)})
        frame = {"job": job["job"], "seq": job["seq"], "session": job["session"], "done": job["done"], **data}
    pub = job.get("_publish")
    if pub is not None:
        try:
            pub({"session_id": "local", "event": "talk", "ts": time.time(), "data": frame})
        except Exception:
            pass


def _work(job: dict, pcm: bytes, row: dict, state_dir) -> None:
    from halo_harness.theme import get_config_value
    from halo_harness.voice import turn as T
    from halo_harness.voice.ensure import ensure, picks
    from halo_harness.voice.latency import budget, record
    buf, rate = [b""], [24000]

    def flush() -> None:
        if buf[0]:
            job["bytes"] += len(buf[0])
            _send(job, state="audio", audio_b64=base64.b64encode(buf[0]).decode("ascii"), rate=rate[0], bytes=job["bytes"])
            buf[0] = b""

    def emit(kind: str, data) -> None:
        if kind == "audio":
            buf[0] += data
            if len(buf[0]) >= PIECE:
                flush()
        elif kind == "rate":
            flush()
            rate[0] = int(data.get("rate") or 24000)
        else:
            flush()
            _send(job, state=kind, text=data.get("text"))
    try:
        urls, _started, lines = ensure(state_dir, say=lambda t: _send(job, state="note", text=t))
        if urls is None:
            raise T.TurnError(409, lines[-1] if lines else "the speech servers did not start")
        voice = str(get_config_value("voice.tts_voice", default=None) or "af_heart")
        trailer = T.run(pcm, stt_url=urls["stt"], tts_url=urls["tts"], endpoint=row["endpoint"], token=row.get("token"),
                        voice=voice, budget_ms=budget(picks(state_dir)["budget_ms"]), emit=emit,
                        session_id=str(row["session_id"]))
        flush()
        try:
            record(state_dir, trailer["card"], via="studio")
        except OSError:
            pass
        job.update(done=True, ok=True)
        _send(job, state="done", transcript=trailer["transcript"], reply=trailer["reply"], line=trailer["line"],
              card=trailer["card"], bytes=job["bytes"])
    except T.TurnError as e:
        job.update(done=True, ok=False)
        _send(job, state="error", error=e.line)
    except Exception as e:  # one bad turn never takes the page down
        job.update(done=True, ok=False)
        _send(job, state="error", error=f"{type(e).__name__}: {e}")


def post_talk(req):
    from halo_harness.voice import turn as T
    b = _body(req)
    try:
        raw = base64.b64decode(str(b.get("pcm_b64") or ""), validate=True)
    except ValueError:
        return 400, {"error": "pcm_b64 is not base64: Talk sends the utterance as 16-bit mono PCM"}
    rate = int(b["rate"]) if str(b.get("rate") or "").isdigit() else 16000
    try:
        pcm, secs = T.pcm_of(raw, f"audio/pcm;rate={rate}")
        row = T.pick(T.sessions(req.state_dir), str(b.get("session") or ""))
    except T.TurnError as e:
        return e.status, {"error": e.line}
    job = {"job": f"talk-{next(_SEQ)}", "session": str(row["session_id"]), "seconds": round(secs, 2), "state": "start",
           "seq": 0, "bytes": 0, "done": False, "ok": None, "started": round(time.time(), 3), "_publish": _publish(req)}
    with _LOCK:
        _JOBS[job["job"]] = job
    _send(job, state="start", text=f"heard {secs:.1f} s of audio from this browser")
    threading.Thread(target=_work, args=(job, pcm, row, req.state_dir), name="halo-voice-talk", daemon=True).start()
    return 202, {**_view(job), "cli": f"halo voice client --host <this machine> --input-file <wav> --session {row['session_id'][:8]}"}


def get_talk(req):
    job = _JOBS.get(str(req.query.get("job") or ""))
    return (200, _view(job)) if job else (404, {"error": "no such Talk turn here"})


ROUTES = {("POST", "local/voice/server"): post_server, ("POST", "local/voice/download"): post_download,
          ("POST", "local/voice/loop"): post_loop, ("POST", "local/voice/talk"): post_talk,
          ("GET", "local/voice/talk"): get_talk}
