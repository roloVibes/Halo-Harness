"""halo_harness.studio.local_sweep_api -- Halo 3.6.0.25 T: the sweep's routes (dispatched from
studio/local_bench_api.dispatch_bench; the run is providers/local_sweep_run.py, the job studio/local_bench_job.py with
kind "sweep"). Every answer carries `cli`, the `halo local bench --sweep` line that does the same.

    GET  local/host/<name>/sweep?model=        {sweep (the kept one, or null), job (its running or last job), offer
                                                (the line said before a start: loads, about how long, that it unloads
                                                what is loaded and puts it back, what it writes), cli}
    POST local/host/<name>/sweep {model, loads?, again?}   a sweep job; 409 with one line while the host had a call in
                                                the last minute, a session uses it, or a bench or sweep runs there
                                                (again: true starts over: Studio's "Sweep again" on a done sweep)
    POST local/host/<name>/sweep/stop {model}  its Stop: it ends after the running load and keeps what was measured
    POST local/host/<name>/sweep/use {model}   "Use in Halo": the pick as the profile's window (agent_proposals.
                                                land_user: it shows in Changes and can be reverted; nothing is
                                                written to the Ollama store)
    POST local/host/<name>/sweep/tuner {model} "Tune with <model>" (ollama_steward/tuner.py; job kind "tuner"); 409
                                                when no tuner model is set (nothing is sent) or a job runs there
    POST local/host/<name>/sweep/tuner/stop {model}   its Stop (ends before the next round)
    POST local/host/<name>/sweep/notes/remove {model, kind}   removes a text the tuner wrote
The GET also carries `tuner` (ollama_steward/tuner.offer: the tuner, what is sent, the cost, what it writes; or the
one closed line when none is set), `tuner_job` and `notes` (the texts kept, each with `by_line`).
"""

from __future__ import annotations

import re
import urllib.parse

_SWEEP = re.compile(r"^local/host/(?P<name>[^/]+)/sweep(?:/(?P<verb>stop|use|tuner|tuner/stop|notes/remove))?$")
USE_SAYS = ("sets the profile's window of {model} on {host} to {pick:,} (the sweep's pick) through Changes, where it "
            "can be reverted; nothing is written to the Ollama store")


def cli(name: str, model: str) -> str:
    return f"halo local bench --host {name} --sweep {model}"


def _digest(host, model: str):
    from halo_harness.providers.ollama import ollama_names_match
    from halo_harness.studio.ollama_hosts_view import catalog_of
    row = next((r for r in catalog_of(host).get("models") or [] if isinstance(r, dict)
                and ollama_names_match(r.get("model") or r.get("name"), model)), {})
    return row.get("digest")


def _rec(req, host, model: str):
    """The sweep under this digest and this server; None when either is not known (never one of another build)."""
    from halo_harness.ollama_steward.tune_report import sweep_record
    from halo_harness.studio.ollama_hosts_view import card_of
    return sweep_record(req.state_dir, host, card_of(host), model, _digest(host, model))


def _view(rec) -> "dict | None":
    if not rec:
        return None
    from halo_harness.providers import local_sweep as S
    rows = [{**r, "line": S.row_line(r)} for r in sorted(rec.get("windows") or [], key=lambda r: r["window"])]
    return {"windows": rows, "pick": rec.get("pick"), "why": rec.get("why"), "done": bool(rec.get("done")),
            "loads": len(rows), "loads_cap": S.MAX_LOADS, "trained": rec.get("trained"), "at": rec.get("at"),
            "safe": rec.get("safe"), "safe_line": S.safe_line(rec)}


def _job(name: str, model: str, kind: str = "sweep"):
    from halo_harness.providers.ollama import ollama_names_match
    from halo_harness.studio.local_bench_job import current
    return next((j for j in current(name)["jobs"] if j.get("kind") == kind and ollama_names_match(j["model"], model)),
                None)


def get_sweep(req, host, name: str, model: str):
    from halo_harness.providers.local_sweep_run import estimate
    from halo_harness.studio.ollama_hosts_view import card_of
    try:
        offer = estimate(host, model, card=card_of(host), state_dir=req.state_dir)[1]
    except Exception:
        offer = ""
    rec = _rec(req, host, model)
    return 200, {"sweep": _view(rec), "job": _job(name, model), "offer": offer, "cli": cli(name, model),
                 "use": USE_SAYS.format(model=model, host=name, pick=rec["pick"]) if rec and rec.get("pick") else None,
                 "tuner": _tuner_offer(req, host, model), "tuner_job": _job(name, model, "tuner"),
                 "notes": _notes(req, host, name, model)}


def _tuner_offer(req, host, model: str) -> dict:
    from halo_harness.ollama_steward import tuner as T
    from halo_harness.studio.ollama_hosts_view import card_of
    try:
        return T.offer(req.state_dir, host, model, card=card_of(host))
    except Exception as e:  # noqa: BLE001 -- the line says what broke
        return {"tuner": T.tuner_model(), "line": f"the tuner's offer could not be read: {type(e).__name__}"}


def _notes(req, host, name: str, model: str) -> dict:
    from halo_harness.ollama_steward import tuner_notes as N
    return {k: {**v, "by_line": N.by_line(v)} for k, v in N.read(req.state_dir, name, model, digest=_digest(host, model)).items()}


def post_tuner(req, host, name: str, model: str):
    from halo_harness.ollama_steward import tuner as T
    from halo_harness.studio import local_bench_job as J
    from halo_harness.studio.local_control_api import _pub
    from halo_harness.studio.ollama_hosts_view import card_of
    tuner = T.tuner_model()
    if not tuner:
        return 409, {"error": "no tuner model is set (Settings: Tuner model): nothing was sent"}
    other = J.running_on(name)
    if other is not None and not (other.get("kind") == "tuner" and other.get("model") == model):
        return 409, {"error": f"a {other.get('kind') or 'bench'} of {other['model']} runs on {name} now: one at a time "
                              "per card"}
    from halo_harness.providers.local_bench_runs import busy
    why = busy(req.state_dir, name) if other is None else ""  # ruling 1's wait for an idle host (each proposal again)
    if why:
        return 409, {"error": why}
    card = card_of(host)
    off = T.offer(req.state_dir, host, model, tuner=tuner, card=card)

    def runner(h, m, **kw):
        return T.run(kw["state_dir"], h, m, tuner=tuner, stop=kw.get("stop"), on_line=kw.get("on_line"), card=kw.get("card"))
    view = J.start(host, model, _pub(req), state_dir=req.state_dir, cost=off.get("cost") or "", card=card, runner=runner,
                   kind="tuner")
    return 200, {**view, "tuner": tuner}


def post_sweep(req, host, name: str, model: str, body: dict):
    from halo_harness.providers.local_bench_runs import busy
    from halo_harness.providers.local_sweep_run import estimate, sweep
    from halo_harness.studio import local_bench_job as J
    from halo_harness.studio.local_control_api import _pub
    from halo_harness.studio.ollama_hosts_view import card_of
    other = J.running_on(name)
    if other is not None and not (other.get("kind") == "sweep" and other.get("model") == model):
        return 409, {"error": f"a {other.get('kind') or 'bench'} of {other['model']} runs on {name} now: one at a time "
                              "per card"}
    why = busy(req.state_dir, name) if other is None else ""
    if why:
        return 409, {"error": why}
    loads = body.get("loads") if isinstance(body.get("loads"), int) and body["loads"] > 0 else 6
    again = body.get("again") is True

    def runner(h, m, **kw):
        return sweep(h, m, max_loads=loads, again=again, **kw)
    card = card_of(host)
    offer = estimate(host, model, card=card, state_dir=req.state_dir, max_loads=loads)[1]
    view = J.start(host, model, _pub(req), state_dir=req.state_dir, cost=offer, card=card, runner=runner, kind="sweep")
    return 200, {**view, "cli": cli(name, model)}


def post_use(req, host, name: str, model: str):
    from halo_harness.ollama_steward.agent_proposals import land_user
    from halo_harness.ollama_steward.profiles import key_for
    rec = _rec(req, host, model)
    if not rec or not rec.get("pick"):
        return 409, {"error": f"{model} on {name} has no sweep pick under this build and server: find the best window "
                              "first"}
    got = land_user(req.state_dir, {"key": key_for(name, model), "field": "num_ctx", "to": rec["pick"]}, by="user",
                    why=f"the sweep's pick: {rec['why']}")
    code = 200 if got.get("ok") else 409
    return code, {"ok": bool(got.get("ok")), "say": got.get("line"), "id": got.get("id"), "error": None if got.get("ok")
                  else got.get("line"), "cli": f"halo local tune --host {name}"}


def dispatch_sweep(req):
    m = _SWEEP.match(req.path)
    if not m:
        return None
    from halo_harness.providers.ollama import resolve_ollama_host
    name, verb = urllib.parse.unquote(m.group("name")), m.group("verb")
    host = resolve_ollama_host(name)
    if host is None:
        return 404, {"error": f"no host named {name!r} here"}
    body = req.body if isinstance(req.body, dict) else {}
    model = str((req.query.get("model") if req.method == "GET" else body.get("model")) or "").strip()
    if not model:
        return 422, {"error": "the sweep takes {model}", "problems": ["model: the model to sweep"]}
    if req.method == "GET" and verb is None:
        return get_sweep(req, host, name, model)
    if req.method != "POST":
        return 405, {"error": "method not allowed"}
    if verb == "stop":
        from halo_harness.studio.local_bench_job import stop
        ok = stop(name, model)
        return 200, {"ok": ok, "say": "stops after the running load; what was measured is kept" if ok
                     else f"no sweep of {model} runs on {name}"}
    if verb == "tuner/stop":
        from halo_harness.studio.local_bench_job import stop
        ok = stop(name, model, "tuner")
        return 200, {"ok": ok, "say": "stops before the next round; what it wrote is kept" if ok
                     else f"no tuner runs on {model} on {name}"}
    if verb == "tuner":
        return post_tuner(req, host, name, model)
    if verb == "notes/remove":
        from halo_harness.ollama_steward import tuner_notes as N
        kind = str(body.get("kind") or "")
        ok = N.remove(req.state_dir, name, model, kind)
        return 200, {"ok": ok, "say": f"removed the {kind}" if ok else f"no {kind or 'text'} kept for {model}"}
    if verb == "use":
        return post_use(req, host, name, model)
    return post_sweep(req, host, name, model, body)
