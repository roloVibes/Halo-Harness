"""halo_harness.studio.local_server_api -- Halo 3.3.5.0 R5: the local servers Local -> Hugging Face starts for a
model on disk (providers/local_server.py, the command line providers/local_server_cmd.py), dispatched by
studio/local_hf_api.dispatch_hf. Every answer carries `cli`, the `halo local` line that does the same.

    POST local/hf/serve {path, runtime?, window?, port?, keep?, dry?, wait_s?}
                                     dry: the flags and where each comes from, nothing started; else the server
                                     started and /health polled up to wait_s (WAIT_S): ready, or "still loading"
    GET  local/servers               the servers Halo started (alive or not), each with its flags and log path
    POST local/server/<id>/stop      terminate, then kill after 10 s (a server Halo did not start: 404, said why)
    GET  local/server/<id>/log?n=    the last n lines of its log (40 by default)
    GET  local/server/<id>/status    /health and /slots now
"""

from __future__ import annotations

import re
import urllib.parse

_SRV = re.compile(r"^local/server/(?P<id>[^/]+)/(?P<act>stop|log|status)$")
METHODS = {"stop": "POST", "log": "GET", "status": "GET"}
WAIT_S = 20.0


def serve_cli(path: str, runtime: str = "", window=None, port=None, keep: bool = False) -> str:
    words = ["halo local serve", str(path)]
    if runtime == "mlx":
        words.append("--runtime mlx")
    if window:
        words.append(f"--window {window}")
    if port:
        words.append(f"--port {port}")
    if keep:
        words.append("--keep")
    return " ".join(words)


def _int(v):
    try:
        n = int(v)
        return n if n > 0 else None
    except (TypeError, ValueError):
        return None


def post_serve(req):
    from halo_harness.providers import local_server as S
    from halo_harness.providers.local_server_cmd import llama_argv, mlx_argv, plan_flags, runtime_of
    from halo_harness.studio import local_hf_view
    from halo_harness.studio.local_hf_api import find
    body = req.body if isinstance(req.body, dict) else {}
    path = str(body.get("path") or "").strip()
    raw = find(path) if path else None
    if raw is None:
        return (422, {"error": "serve takes {path}", "problems": ["path: a model Local -> Hugging Face lists"]}) if not path \
            else (404, {"error": f"Local -> Hugging Face lists no model at {path}"})
    runtime = runtime_of(raw["kind"], str(body.get("runtime") or ""))
    window, port, keep = _int(body.get("window")), _int(body.get("port")), body.get("keep") is True
    flags = plan_flags(raw["path"], raw["kind"], model=raw["model"], window=window)
    line = serve_cli(raw["path"], runtime, window, port, keep)
    preview = (mlx_argv(["python -m mlx_lm.server"], path=raw["path"], port=port or 0) if runtime == "mlx"
               else llama_argv(["llama-server"], path=raw["path"], model=raw["model"], port=port or 0, flags=flags))
    about = {"runtime": runtime, "model": raw["model"], "flags": {k: flags[k] for k in ("window", "ngl", "parallel", "kv_type", "flash_attn", "num_predict")},
             "sources": flags["sources"], "notes": flags["notes"], "host": flags["host"], "layers": flags["layers"],
             "trained": flags["trained"], "argv": [("<port>" if a == "0" and preview[i - 1] == "--port" else a) for i, a in enumerate(preview)],
             "ref": f"hf:local/{raw['model']}", "cli": line}
    if body.get("dry") is True:
        return 200, {"ok": True, "dry": True, **about}
    wait = body.get("wait_s") if isinstance(body.get("wait_s"), (int, float)) and body["wait_s"] > 0 else WAIT_S
    info = S.start(raw["path"], runtime=runtime, port=port or 0, window=flags["window"], ngl=flags["ngl"],
                   parallel=flags["parallel"], kv_type=flags["kv_type"], flash_attn=flags["flash_attn"],
                   num_predict=flags["num_predict"], model=raw["model"], keep=keep, state_dir=req.state_dir,
                   wait_s=float(wait), sources=flags["sources"])
    local_hf_view.reset()
    if not info.ok:
        return 502, {"error": info.say, **about, **S.view(info)}
    return 200, {**about, **S.view(info), "stop_cli": f"halo local stop {info.id}", "log_cli": f"halo local log {info.id}"}


def get_servers(req):
    from halo_harness.providers.local_server import servers
    rows = servers(req.state_dir)
    return 200, {"servers": [{**{k: e.get(k) for k in ("id", "model", "kind", "port", "pid", "ready", "alive", "keep", "model_path",
                                                       "flags", "sources", "log", "started")},
                              "url": f"http://127.0.0.1:{e.get('port')}", "ref": f"hf:local/{e.get('model')}",
                              "stop_cli": f"halo local stop {e.get('id')}", "log_cli": f"halo local log {e.get('id')}"} for e in rows]}


def server_act(req, sid: str, act: str):
    from halo_harness.providers import local_server as S
    if act == "stop":
        got = S.stop(sid, state_dir=req.state_dir)
        if got["ok"]:
            from halo_harness.studio import local_hf_view
            local_hf_view.reset()
        return (200 if got["ok"] else 404), ({**got, "cli": f"halo local stop {sid}"} if got["ok"] else
                                              {"error": got["say"], **got, "cli": f"halo local stop {sid}"})
    if act == "log":
        n = max(1, min(_int(req.query.get("n")) or 40, 2000))
        got = S.tail(sid, n, state_dir=req.state_dir)
        return (200 if got["ok"] else 404), {**got, "cli": f"halo local log {sid} -n {n}"}
    got = S.status(sid, state_dir=req.state_dir)
    return (200 if got["ok"] else 404), {**got, "cli": "halo local servers"}


def dispatch_servers(req):
    if req.path == "local/hf/serve":
        return post_serve(req) if req.method == "POST" else (405, {"error": "method not allowed"})
    if req.path == "local/servers":
        return get_servers(req) if req.method == "GET" else (405, {"error": "method not allowed"})
    m = _SRV.match(req.path)
    if not m:
        return None
    if req.method != METHODS[m.group("act")]:
        return 405, {"error": "method not allowed"}
    return server_act(req, urllib.parse.unquote(m.group("id")), m.group("act"))
