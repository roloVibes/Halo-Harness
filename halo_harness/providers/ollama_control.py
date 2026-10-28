"""halo_harness.providers.ollama_control -- Halo 3.3.5.0 R3: an Ollama
server's models, controlled (docs.ollama.com/api: pull, delete, copy, show,
ps). Every call goes through providers/ollama.py's one client (`request_json`,
`_open_conn`); under the test flag providers/ollama_guard.control_blocked
keeps a call off anything but a loopback fake. Nothing here writes a blob
store or calls a model.

    pull(host, name, on_status=None, cancel=None) -> {ok, cancelled, say, status, digest, total, completed, error}
    delete(host, name)                            -> {ok, say, status, missing}
    show(host, name)                              -> {ok, say, show {template, parameters, params, license,
                                                     capabilities, details, model_info, modelfile, modified_at,
                                                     projector_info}, facts {family, params, quant, parent, context}}
    copy(host, src, dst) / rename(host, src, dst) -> {ok, say, status}
    loaded(host)                                  -> {ok, say, models [{model, size, size_vram, vram_pct, expires,
                                                     context_length}]}

The pull stream (`POST /api/pull {"model", "stream": true}`) is one JSON object
per line: `{"status": "pulling manifest"}`, then per layer `{"status":
"pulling <digest>", "digest", "total", "completed"}` (repeated while it
downloads), `{"status": "verifying sha256 digest"}`, `{"status": "writing
manifest"}`, `{"status": "success"}`; a failure is an `{"error": ...}` line
(or a non-200 with one). `cancel` (a threading.Event) closes the connection:
Ollama stops, keeps the layers it already has in its own blob folder, and the
next pull of the same name starts from them.
"""

from __future__ import annotations

import json
import threading
from typing import Callable, Optional

PULL_READ_TIMEOUT_S = 120.0
CALL_TIMEOUT_S = 30.0
KEPT = ("Ollama keeps the layers it already has in its own blob folder; pulling it again picks up from them")


def _blocked(host) -> Optional[dict]:
    from halo_harness.providers.ollama_guard import control_blocked
    if host is None:
        return {"ok": False, "say": "no such Ollama host", "status": None}
    why = control_blocked(host)
    return {"ok": False, "say": why, "status": None, "blocked": True} if why else None


def _name(host) -> str:
    return str(getattr(host, "name", "?"))


def pull(host, name: str, on_status: Optional[Callable[[dict], None]] = None,
         cancel: Optional[threading.Event] = None) -> dict:
    """Pull `name` (a library name or `hf.co/<repo>:<quant>`) onto `host`, each status line handed to `on_status`."""
    import http.client
    from halo_harness.providers.http import UpstreamConnectError
    from halo_harness.providers.ollama import _auth_headers, _open_conn
    out = {"ok": False, "cancelled": False, "say": "", "status": None, "digest": None, "total": None, "completed": None,
           "error": None}
    stop = _blocked(host)
    if stop:
        return {**out, **stop}
    name = str(name or "").strip()
    if not name:
        return {**out, "say": "say which model to pull"}
    conn = None
    done = threading.Event()

    def _watch():  # a cancel closes the socket at once, even between two status lines
        while not done.is_set():
            if cancel.wait(0.25):
                if not done.is_set() and conn is not None and conn.sock is not None:
                    try:
                        conn.sock.shutdown(2)
                    except Exception:
                        pass
                return

    try:
        conn, root = _open_conn(host, timeout=PULL_READ_TIMEOUT_S)
        if cancel is not None:
            threading.Thread(target=_watch, daemon=True, name="halo-ollama-pull-cancel").start()
        headers = {"Accept-Encoding": "identity", "Content-Type": "application/json", **_auth_headers(host)}
        conn.request("POST", f"{root}/api/pull", body=json.dumps({"model": name, "stream": True}).encode("utf-8"),
                     headers=headers)
        resp = conn.getresponse()
        if resp.status != 200:
            try:
                err = json.loads(resp.read().decode("utf-8", "replace") or "{}").get("error")
            except (ValueError, AttributeError):
                err = None
            return {**out, "error": err or f"HTTP {resp.status}", "say": f"{_name(host)} answered HTTP {resp.status} "
                    f"to the pull of {name}" + (f": {err}" if err else "")}
        while True:
            if cancel is not None and cancel.is_set():
                break
            raw = resp.readline()
            if not raw:
                break
            try:
                obj = json.loads(raw.strip() or b"{}")
            except ValueError:
                continue
            if not isinstance(obj, dict) or not obj:
                continue
            if obj.get("error"):
                return {**out, "error": str(obj["error"]), "say": f"{_name(host)} could not pull {name}: {obj['error']}"}
            out["status"] = obj.get("status") or out["status"]
            for k in ("digest", "total", "completed"):
                if obj.get(k) is not None:
                    out[k] = obj[k]
            if on_status is not None:
                try:
                    on_status(dict(obj))
                except Exception:
                    pass
            if obj.get("status") == "success":
                return {**out, "ok": True, "say": f"{name} pulled on {_name(host)}"}
    except UpstreamConnectError as e:
        return {**out, "error": "unreachable", "say": f"{_name(host)} did not answer ({e})"}
    except (OSError, ValueError, http.client.HTTPException) as e:
        if not (cancel is not None and cancel.is_set()):
            return {**out, "error": type(e).__name__, "say": f"the pull of {name} stopped: {type(e).__name__}: {e}"}
    finally:
        done.set()
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
    if cancel is not None and cancel.is_set():
        return {**out, "cancelled": True, "say": f"the pull of {name} on {_name(host)} was cancelled: {KEPT}"}
    return {**out, "error": "ended", "say": f"{_name(host)} ended the pull of {name} before it said success"}


def _reply_say(reply, what: str, host) -> str:
    if reply.failure == "http":
        return f"{_name(host)} answered HTTP {reply.status} to {what}"
    return f"{_name(host)} did not answer ({reply.failure})"


def delete(host, name: str) -> dict:
    from halo_harness.providers.ollama import request_json
    stop = _blocked(host)
    if stop:
        return {**stop, "missing": False}
    reply = request_json(host, "/api/delete", method="DELETE", body={"model": name}, timeout=CALL_TIMEOUT_S)
    if reply.failure is None:
        return {"ok": True, "say": f"{name} deleted from {_name(host)}", "status": 200, "missing": False}
    missing = reply.status == 404
    say = f"{name} is not on {_name(host)} (HTTP 404)" if missing else _reply_say(reply, f"the delete of {name}", host)
    return {"ok": False, "say": say, "status": reply.status, "missing": missing}


SHOW_KEYS = ("template", "parameters", "license", "capabilities", "details", "model_info", "modelfile", "modified_at",
             "projector_info", "system")


def facts(show: dict) -> dict:
    """The short form of `/api/show`: family, parameters, quant, the parent, the trained context."""
    from halo_harness.providers.ollama import trained_context_for
    d = show.get("details") if isinstance(show.get("details"), dict) else {}
    ctx = trained_context_for({"models": [{"model": "m", "model_info": show.get("model_info") or {}, "details": d}]}, "m")
    return {"family": d.get("family"), "params": d.get("parameter_size"), "quant": d.get("quantization_level"),
            "format": d.get("format"), "parent": d.get("parent_model") or None, "context": ctx}


def show(host, name: str) -> dict:
    from halo_harness.providers.ollama import request_json
    from halo_harness.providers.ollama_tune_names import parse_parameters
    stop = _blocked(host)
    if stop:
        return {**stop, "show": None, "facts": None}
    reply = request_json(host, "/api/show", method="POST", body={"model": name}, timeout=CALL_TIMEOUT_S)
    if not isinstance(reply.body, dict):
        say = f"{name} is not on {_name(host)} (HTTP 404)" if reply.status == 404 else _reply_say(reply, f"show {name}", host)
        return {"ok": False, "say": say, "status": reply.status, "show": None, "facts": None}
    body = reply.body
    view = {k: body.get(k) for k in SHOW_KEYS if body.get(k) not in (None, "", [], {})}
    view["params"] = parse_parameters(body.get("parameters"))
    return {"ok": True, "say": f"{name} on {_name(host)}", "status": 200, "show": view, "facts": facts(body)}


def copy(host, src: str, dst: str) -> dict:
    from halo_harness.providers.ollama import request_json
    stop = _blocked(host)
    if stop:
        return stop
    if not str(src or "").strip() or not str(dst or "").strip():
        return {"ok": False, "say": "copy takes a source and a new name", "status": None}
    reply = request_json(host, "/api/copy", method="POST", body={"source": src, "destination": dst},
                         timeout=CALL_TIMEOUT_S)
    if reply.failure is None:
        return {"ok": True, "say": f"{src} copied to {dst} on {_name(host)} (the same layers; no new download)",
                "status": 200}
    say = f"{src} is not on {_name(host)} (HTTP 404)" if reply.status == 404 else _reply_say(reply, f"the copy of {src}", host)
    return {"ok": False, "say": say, "status": reply.status}


def rename(host, src: str, dst: str) -> dict:
    """A copy to `dst`, then the delete of `src` (Ollama has no rename)."""
    got = copy(host, src, dst)
    if not got["ok"]:
        return got
    gone = delete(host, src)
    if not gone["ok"]:
        return {"ok": False, "say": f"{src} copied to {dst}, but {gone['say']}; both names are there now",
                "status": gone.get("status")}
    return {"ok": True, "say": f"{src} renamed to {dst} on {_name(host)}", "status": 200}


def loaded(host) -> dict:
    from halo_harness.providers.ollama import request_json
    stop = _blocked(host)
    if stop:
        return {**stop, "models": []}
    reply = request_json(host, "/api/ps", timeout=CALL_TIMEOUT_S)
    if not isinstance(reply.body, dict):
        return {"ok": False, "say": _reply_say(reply, "/api/ps", host), "status": reply.status, "models": []}
    rows = []
    for x in reply.body.get("models") or []:
        if not isinstance(x, dict):
            continue
        size, vram = x.get("size"), x.get("size_vram")
        pct = round(100.0 * vram / size) if isinstance(size, int) and size > 0 and isinstance(vram, int) else None
        rows.append({"model": x.get("model") or x.get("name"), "size": size, "size_vram": vram, "vram_pct": pct,
                     "expires": x.get("expires_at"), "context_length": x.get("context_length")})
    return {"ok": True, "say": f"{len(rows)} loaded on {_name(host)}", "status": 200, "models": rows}


__all__ = ["KEPT", "copy", "delete", "facts", "loaded", "pull", "rename", "show"]
