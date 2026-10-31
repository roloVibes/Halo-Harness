"""halo_harness.studio.local_control_api -- Halo 3.3.5.0 R3: Local's routes that change what a host has
(dispatched first by studio/local_api.dispatch_local; docs/STUDIO-local.md). Every answer carries `cli`, the
`halo models` line that does the same. A host this machine serves is called directly (providers/
ollama_control.py, providers/ollama_tune.py); a host a fleet member serves goes through that member
(fleet/control_models.py) under its `fleet.allow_control` -- 403 with the reason when it is `none`.

    POST local/host/<name>/pull {name}             a pull job (studio/local_pull_job.py); a second ask joins it
    POST local/pull/<id>/cancel                    stop it (Ollama keeps the layers it has)
    GET  local/pulls                               every job running and the last ended ones
    POST local/host/<name>/delete {name, force?}   422 + the uses card when something uses it (force: delete
                                                   anyway); 409 while a live session is on it
    GET  local/host/<name>/show?model=             /api/show's facts (template, parameters, licence, ...)
    POST local/host/<name>/copy {src, dst}         POST local/host/<name>/rename {src, dst}
    POST local/host/<name>/twin {name, window?, dry?}  the tuned twin (dry: the plan only), recorded in the tune store
    GET  local/host/<name>/loaded                  /api/ps (a member's host: its newest resources sample)
    GET  local/host/<name>/uses?model=             the uses card alone (studio/local_uses.py), before a Delete
"""

from __future__ import annotations

import re
import urllib.parse

_HOST = re.compile(r"^local/host/(?P<name>[^/]+)/(?P<act>pull|delete|show|copy|rename|twin|loaded|uses)$")
_CANCEL = re.compile(r"^local/pull/(?P<id>[^/]+)/cancel$")
METHODS = {"pull": "POST", "delete": "POST", "show": "GET", "copy": "POST", "rename": "POST", "twin": "POST",
           "loaded": "GET", "uses": "GET"}
TWIN_COST = ("a second name on disk: a manifest of a few KB pointing at {model}'s layers -- no new blobs, no "
             "download; it loads at {window:,} with every layer on the GPU")


def _body(req) -> dict:
    return req.body if isinstance(req.body, dict) else {}


def cli(act: str, name: str, *, model: str = "", dst: str = "", window=None, force: bool = False) -> str:
    verb = {"delete": "rm"}.get(act, act)
    words = ["halo models", verb] + [w for w in (model, dst) if w]
    if act == "twin" and window:
        words += ["--window", str(window)]
    if force:
        words.append("--force")
    return " ".join(words + ["--host", name])


def _target(req, name: str):
    """(the OllamaHost or None, controls {ok, via, why, member?, member_host?}, served_here)."""
    from halo_harness.fleet.ollama_share import served_here
    from halo_harness.providers.ollama import resolve_ollama_host
    from halo_harness.studio.local_api import _hub
    from halo_harness.studio.local_hosts_view import controls
    host = resolve_ollama_host(name)
    if host is not None:
        here = served_here(host.url)
        return host, controls(host.url, host.name, here, _hub(req)), here
    from halo_harness.ollama_steward.resources import STORE
    s = STORE.latest(name) or {}
    if s.get("from"):
        return None, controls(s.get("url") or "", name, False, _hub(req)), False
    return None, None, False


def _refused(ctl: dict):
    return (403 if "allow_control" in (ctl.get("why") or "") else 409), {"error": ctl.get("why") or "not from here"}


def _pub(req):
    from halo_harness.studio.local_api import _publish
    try:
        return _publish(req)
    except Exception:  # a server without a live feed: the jobs list still shows the job
        return None


def _forward(req, ctl: dict, cmd: str, fields: dict):
    from halo_harness.studio.local_api import _remote
    return _remote(req, {"controls": ctl}, cmd, fields)


def _done(got: dict, cmd_line: str, **extra):
    from halo_harness.studio.local_pull_job import after_change
    if got.get("ok"):
        after_change()
        return 200, {**got, "cli": cmd_line, **extra}
    return (502 if not got.get("missing") else 404), {"error": got.get("say") or "it did not work", **got, **extra,
                                                      "cli": cmd_line}


def post_pull(req, name: str, host, ctl: dict, here: bool):
    from halo_harness.studio import local_pull_job as J
    model = str(_body(req).get("name") or _body(req).get("model") or "").strip()
    if not model:
        return 422, {"error": "pull takes {name}", "problems": ["name: a library name, or hf.co/<repo>:<quant>"]}
    line = cli("pull", name, model=model)
    if here and host is not None:
        return 200, {**J.start(host, model, _pub(req), state_dir=req.state_dir), "cli": line}
    if ctl.get("via") == "host" and host is not None:  # 3.3.7.0 R2: the host pulls (manage/pull); its job's steps come here
        from halo_harness.studio.local_host_acts import puller, send as host_send
        code, ans = host_send(ctl, "pull", {"model": model})
        if code != 200 or not ans.get("job"):
            return (code if code >= 400 else 409), {"error": ans.get("error") or ans.get("say") or "the host did not start it", "cli": line}
        return 200, {**J.start(host, model, _pub(req), state_dir=req.state_dir, pull=puller(ctl, ans["job"])), "cli": line}

    def send(extra: dict):
        return _forward(req, ctl, "pull", {"model": model, **extra})
    code, view = J.start_remote(name, model, send, ctl.get("via") or "", _pub(req), member=ctl.get("member") or "",
                                member_host=ctl.get("member_host") or "")
    return code, {**view, "cli": line}


def post_delete(req, name: str, host, ctl: dict, here: bool):
    from halo_harness.studio.local_uses import uses_of
    body = _body(req)
    model, force = str(body.get("name") or body.get("model") or "").strip(), body.get("force") is True
    if not model:
        return 422, {"error": "delete takes {name}", "problems": ["name: the model to delete"]}
    uses = uses_of(f"ol:{model}@{name}", cwd=req.cwd, state_dir=req.state_dir)
    line = cli("delete", name, model=model, force=force)
    if uses["live"]:
        return 409, {"error": uses["line"] + ": the delete waits until they end or move to another model", "uses": uses,
                     "cli": line}
    if uses["any"] and not force:
        return 422, {"error": uses["line"], "uses": uses, "problems": [uses["line"]], "cli": cli("delete", name, model=model, force=True)}
    if not here or host is None:
        code, answer = _forward(req, ctl, "delete", {"model": model, "force": force})
        return code, {**answer, "uses": uses, "cli": line}
    from halo_harness.providers.ollama_control import delete
    from halo_harness.providers.ollama_tune_store import forget_twin
    got = delete(host, model)
    if got["ok"]:
        forget_twin(req.state_dir, host_url=host.url, twin=model)
    return _done(got, line, uses=uses)


def get_show(req, name: str, host, ctl: dict, here: bool):
    from halo_harness.providers.ollama_control import show
    model = str(req.query.get("model") or "").strip()
    if not model:
        return 422, {"error": "show takes ?model=", "problems": ["model: the model to show"]}
    if not here or host is None:
        return 409, {"error": f"{name} is served by another machine: its own Studio shows the model's /api/show"}
    got = show(host, model)
    return (200 if got["ok"] else 502 if got.get("status") != 404 else 404), {**got, "cli": cli("show", name, model=model)}


def post_copy(req, name: str, host, ctl: dict, here: bool, rename: bool):
    from halo_harness.providers import ollama_control as C
    body = _body(req)
    src, dst = str(body.get("src") or "").strip(), str(body.get("dst") or "").strip()
    act = "rename" if rename else "copy"
    if not src or not dst:
        return 422, {"error": f"{act} takes {{src, dst}}", "problems": ["src: the model", "dst: the new name"]}
    line = cli(act, name, model=src, dst=dst)
    if not here or host is None:
        code, answer = _forward(req, ctl, "copy", {"src": src, "dst": dst, "rename": rename})
        return code, {**answer, "cli": line}
    return _done((C.rename if rename else C.copy)(host, src, dst), line)


def post_twin(req, name: str, host, ctl: dict, here: bool):
    from halo_harness.providers.ollama_tune import TuneError, create_twin, plan_twin
    body = _body(req)
    model = str(body.get("name") or body.get("model") or "").strip()
    window = body.get("window") if isinstance(body.get("window"), int) and body["window"] > 0 else None
    if not model:
        return 422, {"error": "twin takes {name, window}", "problems": ["name: the model to twin"]}
    line = cli("twin", name, model=model, window=window)
    if not here or host is None:
        code, answer = _forward(req, ctl, "twin", {"model": model, "window": window})
        return code, {**answer, "cli": line}
    try:
        plan = plan_twin(host, model, window, state_dir=req.state_dir)
    except TuneError as e:
        return (422 if e.kind in ("no_window", "already_twin") else 404 if e.kind == "missing" else 502), {
            "error": e.message, "kind": e.kind, "cli": line}
    about = {"twin": plan.twin, "ref": plan.ref, "window": plan.window, "layers": plan.layers, "line": plan.line,
             "cost": TWIN_COST.format(model=plan.model, window=plan.window), "cli": cli("twin", name, model=model, window=plan.window)}
    if body.get("dry") is True:
        return 200, {"ok": True, "dry": True, **about}
    got = create_twin(host, plan, state_dir=req.state_dir)
    if got.ok:  # 3.3.6.0 R1: verified in the background; a `twin-verify` frame says the result
        from halo_harness.studio.local_twin_verify import start_verify
        about["verify"] = start_verify(host, plan.twin, plan.window, _pub(req), state_dir=req.state_dir)
    return _done({"ok": got.ok, "say": got.message}, about["cli"], **{k: v for k, v in about.items() if k != "cli"})


def get_loaded(req, name: str, host, ctl: dict, here: bool):
    from halo_harness.providers.ollama_control import loaded
    line = cli("loaded", name)
    if host is not None and here:
        got = loaded(host)
        return (200 if got["ok"] else 502), {**got, "cli": line}
    from halo_harness.ollama_steward.resources import STORE
    s = STORE.latest(name) or {}
    rows = [{"model": x.get("name"), "size": None, "size_vram": x.get("bytes"), "vram_pct": None, "expires": None,
             "context_length": None} for x in s.get("holders") or [] if x.get("kind") == "model"]
    return 200, {"ok": True, "models": rows, "say": f"from {s.get('from') or name}'s newest sample", "cli": line}


def get_uses(req, name: str, host, ctl: dict, here: bool):
    from halo_harness.studio.local_uses import uses_of
    model = str(req.query.get("model") or "").strip()
    if not model:
        return 422, {"error": "uses takes ?model=", "problems": ["model: the model"]}
    u = uses_of(f"ol:{model}@{name}", cwd=req.cwd, state_dir=req.state_dir)
    return 200, {"uses": u, "cli": cli("delete", name, model=model, force=u["any"])}


def dispatch_control(req):
    """The answer for a route of this file, else None."""
    from halo_harness.studio import local_pull_job as J
    if req.path == "local/pulls":
        return (200, J.current()) if req.method == "GET" else (405, {"error": "method not allowed"})
    m = _CANCEL.match(req.path)
    if m:
        if req.method != "POST":
            return 405, {"error": "method not allowed"}
        got = J.cancel(urllib.parse.unquote(m.group("id")))
        return (200, {**got, "cancelling": not got["done"]}) if got else (404, {"error": "no such pull job"})
    m = _HOST.match(req.path)
    if not m:
        return None
    name, act = urllib.parse.unquote(m.group("name")), m.group("act")
    if req.method != METHODS[act]:
        return 405, {"error": "method not allowed"}
    host, ctl, here = _target(req, name)
    if ctl is None:
        return 404, {"error": f"no host named {name!r} here"}
    if not ctl.get("ok") and act not in ("loaded", "uses"):
        return _refused(ctl)
    if act in ("copy", "rename"):
        return post_copy(req, name, host, ctl, here, act == "rename")
    return {"pull": post_pull, "delete": post_delete, "show": get_show, "twin": post_twin, "loaded": get_loaded,
            "uses": get_uses}[act](
        req, name, host, ctl, here)
