"""halo_harness.studio.media_api -- `/api/media/...`, Studio's ComfyUI view
(Halo 3.0.4.0 round R5). Same guard as every Studio route.

    GET  media/status                       {url, reachable, version, python, pytorch, gpus, registered, cache, checked, age_s, checking}
    GET  media/models?kind=image-gen|video-gen|audio-gen|upscale|all   {kind, rows, scanned, url}
    POST media/scan                         {rows, workflows, scanned}  (a rescan of the server into the cache)
    GET  media/workflows                    {workflows: [{name, source: starter|saved}], reachable}
    GET  media/workflows/<name>/inputs      {workflow, source, label, nodes}  (comfy_graph.describe_inputs)
    POST media/render {workflow, set, project, artboard}   -> 202 {prompt_id, project, artboard}
    GET  media/renders/<prompt id>          the render's last state (the `media_render` frames' data)

`media/status` never holds a request thread for more than `STATUS_WAIT_S`:
a background thread refreshes the answer (`system_stats`, 2 s timeout) when
it is older than `STATUS_TTL_S`, and the cached answer is returned. `URL`
pins the server (tests); None = `COMFY_URL`, the config's `comfy.url`, or
http://127.0.0.1:8188.
"""

from __future__ import annotations

import re
import threading
import time

URL = None
STATUS_TTL_S = 15.0
STATUS_WAIT_S = 2.0
KINDS = ("image-gen", "video-gen", "audio-gen", "upscale", "all", "tts", "encoder", "lora", "vae", "other")
_status: dict = {}
_status_lock = threading.Lock()


def _bad(lines, status: int = 422):
    lines = [lines] if isinstance(lines, str) else list(lines)
    return status, {"error": lines[0] if lines else "invalid", "problems": lines}


def _url() -> str:
    from halo_harness.media.comfy_client import resolve_url
    return (URL or resolve_url()).rstrip("/")


def _client(timeout: float = 30):
    from halo_harness.media.comfy_client import ComfyClient
    return ComfyClient(_url(), timeout=timeout)


def _cache_info(state_dir) -> dict:
    from halo_harness.providers.media_models import load_cached
    doc = load_cached(state_dir)
    scanned = doc.get("scanned")
    return {"scanned": scanned, "age_s": round(time.time() - scanned, 1) if isinstance(scanned, (int, float)) else None,
            "rows": len(doc.get("rows") or []), "workflows": len(doc.get("workflows") or []), "url": doc.get("url")}


def _probe(url: str, cwd) -> dict:
    from halo_harness.media.comfy_client import ComfyClient, ComfyError
    from halo_harness.media.setup_cli import registered_entry
    out = {"url": url, "reachable": False, "version": None, "python": None, "pytorch": None, "gpus": [], "error": None}
    try:
        stats = ComfyClient(url, timeout=STATUS_WAIT_S).system_stats() or {}
        sysd = stats.get("system") or {}
        out.update(reachable=True, version=sysd.get("comfyui_version"),
                   python=str(sysd.get("python_version") or "").split(" ")[0] or None,
                   pytorch=sysd.get("pytorch_version"),
                   gpus=[{"name": d.get("name"), "type": d.get("type"), "vram_total": d.get("vram_total"),
                          "vram_free": d.get("vram_free")} for d in stats.get("devices") or [] if isinstance(d, dict)])
    except ComfyError as e:
        out["error"] = str(e)
    except Exception as e:  # a reply that is not the expected shape
        out["error"] = f"{type(e).__name__}: {e}"
    entry = registered_entry(cwd)
    out["registered"] = None if entry is None else {
        "command": entry.get("command"), "args": list(entry.get("args") or []),
        "url": str((entry.get("env") or {}).get("COMFY_URL") or "") or None}
    out["checked"] = time.time()
    return out


def _refresh(url: str, cwd, done: threading.Event) -> None:
    try:
        data = _probe(url, cwd)
        with _status_lock:
            _status[url] = data
    finally:
        with _status_lock:
            _status.pop(("busy", url), None)
        done.set()


def get_status(req):
    url = _url()
    with _status_lock:
        cached = _status.get(url)
        fresh = cached is not None and time.time() - cached.get("checked", 0) < STATUS_TTL_S
        done = _status.get(("busy", url))
        if not fresh and done is None:
            done = threading.Event()
            _status[("busy", url)] = done
            threading.Thread(target=_refresh, args=(url, req.cwd, done), daemon=True, name="halo-media-status").start()
    if cached is None and done is not None:
        done.wait(STATUS_WAIT_S)
        with _status_lock:
            cached = _status.get(url)
    data = dict(cached) if cached else {"url": url, "reachable": None, "checked": None}
    data["checking"] = done is not None and not done.is_set()
    data["age_s"] = round(time.time() - data["checked"], 1) if data.get("checked") else None
    data["cache"] = _cache_info(req.state_dir)
    return 200, data


def get_models(req):
    from halo_harness.providers.media_models import rows_for
    kind = str(req.query.get("kind") or "all")
    if kind not in KINDS:
        return _bad(f"kind is one of {', '.join(KINDS[:5])}, got {kind!r}")
    info = _cache_info(req.state_dir)
    return 200, {"kind": kind, "rows": rows_for(kind, req.state_dir), "scanned": info["scanned"], "url": info["url"]}


def post_scan(req):
    from halo_harness.media.comfy_client import ComfyError
    from halo_harness.providers.media_models import load_cached, scan
    try:
        rows = scan(_client(), req.state_dir)
    except ComfyError as e:
        return 502, {"error": str(e)}
    doc = load_cached(req.state_dir)
    return 200, {"rows": len(rows), "workflows": doc.get("workflows") or [], "scanned": doc.get("scanned"),
                 "url": doc.get("url")}


def get_workflows(req):
    from halo_harness.media import comfy_ops
    from halo_harness.media.comfy_client import ComfyError
    from halo_harness.providers.media_models import load_cached
    rows = [{"name": n, "source": "starter"} for n in comfy_ops.starter_names()]
    try:
        saved, reachable = _client(timeout=STATUS_WAIT_S).workflows(), True
    except ComfyError:
        saved, reachable = list(load_cached(req.state_dir).get("workflows") or []), False
    rows += [{"name": n[:-5] if n.lower().endswith(".json") else n, "source": "saved"} for n in saved]
    return 200, {"workflows": rows, "reachable": reachable, "url": _url()}


def _graph(client, name: str, source: str):
    """(graph, source, label) for a starter or a saved name (never a file path)."""
    from halo_harness.media import comfy_ops
    from halo_harness.media.comfy_client import ComfyError
    if source != "starter":
        try:
            return client.workflow(name), "saved", f"saved workflow {name!r}"
        except ComfyError as e:
            if source == "saved" or e.status not in (0, 400, 404):
                raise
    starter = comfy_ops.load_starter(name)
    if starter is None:
        raise ComfyError(f"no workflow {name!r}: not saved on the server and not a starter "
                         f"({', '.join(comfy_ops.starter_names())})", 404)
    return starter, "starter", f"starter {name!r}"


def get_inputs(req):
    from halo_harness.media.comfy_client import ComfyError
    from halo_harness.media.comfy_graph import ComfyGraphError, describe_inputs, to_api
    client = _client()
    try:
        graph, source, label = _graph(client, req.params["name"], str(req.query.get("source") or ""))
        nodes = describe_inputs(to_api(graph, client.object_info))
    except ComfyGraphError as e:
        return _bad(str(e))
    except ComfyError as e:
        return (404 if e.status == 404 else 502), {"error": str(e)}
    return 200, {"workflow": req.params["name"], "source": source, "label": label, "nodes": nodes}


def post_render(req):
    from halo_harness.design.store import Project
    from halo_harness.media import comfy_ops
    from halo_harness.media.comfy_client import ComfyError
    from halo_harness.studio import media_render as R
    body = req.body
    workflow, slug = str(body.get("workflow") or "").strip(), str(body.get("project") or "").strip()
    if not workflow or "/" in workflow or "\\" in workflow:
        return _bad("say which workflow: a starter or a saved name")
    sets = body.get("set") if isinstance(body.get("set"), dict) else {}
    project = Project.open(slug, state_dir=req.state_dir) if slug else None
    if project is None:
        return 404, {"error": f"no design project {slug!r}: make it in Design first"}
    artboard = str(body.get("artboard") or "render").strip() or "render"
    client = _client()
    try:
        graph, source, label = _graph(client, workflow, str(body.get("source") or ""))
        pid = client.queue_prompt(comfy_ops.build_graph(client, graph, sets, cwd=req.cwd))
    except ComfyError as e:
        return (404 if e.status == 404 else 502), {"error": str(e)}
    publish = None
    if req.server is not None:
        from halo_harness.studio.events import bridge_for
        publish = bridge_for(req.server).publish_local
    R.start(client, project, pid=pid, workflow=workflow, sets=sets, artboard=artboard, publish=publish,
            poll_s=float(body.get("poll_s") or 1.0) if isinstance(body.get("poll_s"), (int, float)) else 1.0)
    return 202, {"prompt_id": pid, "project": project.slug, "artboard": artboard, "workflow": workflow, "source": source}


def get_render(req):
    from halo_harness.studio import media_render as R
    row = R.render_state(req.params["pid"])
    return (200, row) if row else (404, {"error": f"no render {req.params['pid']!r} in this Studio"})


ROUTES = [
    ("GET", r"^media/status$", get_status), ("GET", r"^media/models$", get_models), ("POST", r"^media/scan$", post_scan),
    ("GET", r"^media/workflows$", get_workflows), ("GET", r"^media/workflows/(?P<name>[^/]+)/inputs$", get_inputs),
    ("POST", r"^media/render$", post_render), ("GET", r"^media/renders/(?P<pid>[A-Za-z0-9_.-]+)$", get_render),
]


def dispatch_media(req):
    for method, pattern, fn in ROUTES:
        m = re.match(pattern, req.path)
        if m and method == req.method:
            req.params = dict(m.groupdict())
            return fn(req)
    if any(re.match(p, req.path) for _, p, _ in ROUTES):
        return 405, {"error": "method not allowed"}
    return 404, {"error": f"no route for {req.method} /api/{req.path}"}
