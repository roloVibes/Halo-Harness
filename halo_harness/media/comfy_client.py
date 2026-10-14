"""halo_harness.media.comfy_client -- a stdlib (urllib) client for a ComfyUI
server. Every call is plain HTTP, so the server may be another host on the
LAN: outputs come back through `GET /view`, never from a disk path.

URL resolution (`resolve_url`): `COMFY_URL` in the environment, else
`comfy.url` in ~/.halo/config.json, else http://127.0.0.1:8188. Errors are
a `ComfyError(message, status)`; status is the HTTP code, or 0 when the
server could not be reached at all.
"""

from __future__ import annotations

import ipaddress
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Callable, Optional

from halo_harness.media.comfy_errors import http_error_text, execution_error_text

DEFAULT_URL = "http://127.0.0.1:8188"

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
VIDEO_EXT = {".mp4", ".webm", ".mov", ".mkv", ".avi", ".gif"}
AUDIO_EXT = {".wav", ".flac", ".mp3", ".ogg", ".opus", ".m4a", ".aac"}


class ComfyError(Exception):
    def __init__(self, message: str, status: int = 0):
        super().__init__(message)
        self.message = message
        self.status = status

    def __str__(self) -> str:
        return f"{self.message} (HTTP {self.status})" if self.status else self.message


def resolve_url(env: Optional[dict] = None) -> str:
    src = os.environ if env is None else env
    url = str(src.get("COMFY_URL") or "").strip()
    if not url:
        try:
            from halo_harness.theme import get_config_value
            url = str(get_config_value("comfy.url", "") or "").strip()
        except Exception:
            url = ""
    return (url or DEFAULT_URL).rstrip("/")


def _is_local(host: str) -> bool:
    if host in ("localhost", ""):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return host.endswith(".local") or host.endswith(".lan")
    return ip.is_private or ip.is_loopback or ip.is_link_local


def kind_of(filename: str, key: str = "") -> str:
    ext = os.path.splitext(str(filename))[1].lower()
    if key == "audio" or ext in AUDIO_EXT:
        return "audio"
    if key in ("gifs", "videos", "video") or ext in VIDEO_EXT:
        return "video"
    if ext in IMAGE_EXT:
        return "image"
    return "other"


class ComfyClient:
    def __init__(self, url: Optional[str] = None, timeout: float = 30):
        self.url = (url or resolve_url()).rstrip("/")
        self.timeout = timeout
        host = urllib.parse.urlparse(self.url).hostname or ""
        # A LAN or loopback server is reached directly, never through an
        # HTTP(S)_PROXY meant for the internet (a local intercepting proxy
        # would otherwise swallow every request).
        handlers = [urllib.request.ProxyHandler({})] if _is_local(host) else []
        self._opener = urllib.request.build_opener(*handlers)

    # ---- transport -------------------------------------------------------------------------
    def _request(self, method: str, path: str, *, body: Optional[bytes] = None, ctype: str = "application/json",
                 timeout: Optional[float] = None) -> bytes:
        req = urllib.request.Request(self.url + path, data=body, method=method)
        if body is not None:
            req.add_header("Content-Type", ctype)
        try:
            with self._opener.open(req, timeout=timeout or self.timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            try:
                raw = e.read()
            except Exception:
                raw = b""
            raise ComfyError(http_error_text(method, path, raw, e.reason), e.code) from None
        except (urllib.error.URLError, OSError, ValueError) as e:
            reason = getattr(e, "reason", e)
            raise ComfyError(f"ComfyUI at {self.url} is not reachable: {reason}", 0) from None

    def _json(self, method: str, path: str, payload=None, timeout: Optional[float] = None):
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        raw = self._request(method, path, body=body, timeout=timeout)
        try:
            return json.loads(raw.decode("utf-8") or "null")
        except ValueError:
            raise ComfyError(f"{method} {path}: the reply is not JSON", 200) from None

    # ---- read ------------------------------------------------------------------------------
    def system_stats(self) -> dict:
        return self._json("GET", "/system_stats")

    def model_folders(self) -> list:
        return list(self._json("GET", "/models") or [])

    def models(self, folder: str) -> list:
        return list(self._json("GET", "/models/" + urllib.parse.quote(folder, safe="")) or [])

    def object_info(self, node: Optional[str] = None) -> dict:
        path = "/object_info" + ("/" + urllib.parse.quote(node, safe="") if node else "")
        return self._json("GET", path, timeout=max(self.timeout, 120)) or {}

    def workflows(self) -> list:
        names = self._json("GET", "/userdata?dir=workflows") or []
        return sorted(str(n) for n in names if str(n).lower().endswith(".json"))

    @staticmethod
    def _wf_path(name: str) -> str:
        # The userdata route takes ONE path segment: the slash is encoded.
        fn = name if name.lower().endswith(".json") else name + ".json"
        return "/userdata/" + urllib.parse.quote("workflows/" + fn, safe="")

    def workflow(self, name: str) -> dict:
        return self._json("GET", self._wf_path(name))

    def save_workflow(self, name: str, graph: dict, overwrite: bool = False) -> None:
        path = self._wf_path(name) + "?overwrite=" + ("true" if overwrite else "false")
        self._request("POST", path, body=json.dumps(graph, indent=1).encode("utf-8"))

    def queue(self) -> dict:
        return self._json("GET", "/queue") or {}

    def history(self, prompt_id: str) -> dict:
        data = self._json("GET", "/history/" + urllib.parse.quote(str(prompt_id), safe="")) or {}
        return data.get(prompt_id) or {}

    def view(self, filename: str, subfolder: str = "", type: str = "output") -> bytes:
        q = urllib.parse.urlencode({"filename": filename, "subfolder": subfolder or "", "type": type or "output"})
        return self._request("GET", "/view?" + q, timeout=max(self.timeout, 300))

    # ---- write -----------------------------------------------------------------------------
    def queue_prompt(self, api_graph: dict, client_id: Optional[str] = None) -> str:
        payload = {"prompt": api_graph, "client_id": client_id or uuid.uuid4().hex}
        reply = self._json("POST", "/prompt", payload)
        pid = (reply or {}).get("prompt_id")
        if not pid:
            raise ComfyError(f"POST /prompt gave no prompt_id: {json.dumps(reply)[:300]}", 200)
        return str(pid)

    def upload_image(self, path: str, overwrite: bool = True) -> str:
        """POST /upload/image (multipart); returns the name LoadImage takes."""
        boundary = "halo" + uuid.uuid4().hex
        name = os.path.basename(path)
        with open(path, "rb") as fh:
            data = fh.read()
        parts = [f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{name}\"\r\n"
                 "Content-Type: application/octet-stream\r\n\r\n".encode("utf-8"), data,
                 f"\r\n--{boundary}\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\n"
                 f"{'true' if overwrite else 'false'}\r\n--{boundary}--\r\n".encode("utf-8")]
        raw = self._request("POST", "/upload/image", body=b"".join(parts), ctype=f"multipart/form-data; boundary={boundary}")
        try:
            reply = json.loads(raw.decode("utf-8"))
        except ValueError:
            return name
        sub = reply.get("subfolder") or ""
        return f"{sub}/{reply.get('name', name)}" if sub else str(reply.get("name", name))

    # ---- waiting ---------------------------------------------------------------------------
    def wait(self, prompt_id: str, timeout_s: float = 1800, poll_s: float = 1.0,
             on_progress: Optional[Callable[[str], None]] = None) -> dict:
        deadline = time.monotonic() + float(timeout_s)
        last = ""
        while True:
            entry = self.history(prompt_id)
            status = entry.get("status") or {}
            if entry and (status.get("completed") or status.get("status_str") in ("success", "error") or entry.get("outputs")):
                if status.get("status_str") == "error":
                    raise ComfyError(execution_error_text(prompt_id, status), 500)
                return entry
            state = queue_state(self.queue(), prompt_id) if on_progress else ""
            if on_progress and state != last:
                on_progress(state)
                last = state
            if time.monotonic() >= deadline:
                raise ComfyError(f"prompt {prompt_id} did not finish within {timeout_s:g}s (still {state or 'queued'})", 0)
            time.sleep(poll_s)

    @staticmethod
    def outputs(history_entry: dict) -> list:
        out = []
        for node, block in (history_entry.get("outputs") or {}).items():
            if not isinstance(block, dict):
                continue
            animated = any(bool(a) for a in (block.get("animated") or []))
            for key, items in block.items():
                if not isinstance(items, list):
                    continue
                for it in items:
                    if isinstance(it, dict) and it.get("filename"):
                        kind = kind_of(it["filename"], key)
                        if animated and kind == "image" and str(it["filename"]).lower().endswith((".webp", ".png")):
                            kind = "video"
                        out.append({"node": str(node), "filename": it["filename"], "subfolder": it.get("subfolder", ""),
                                    "type": it.get("type", "output"), "kind": kind})
        return out


def queue_state(q: dict, prompt_id: str) -> str:
    for row in q.get("queue_running") or []:
        if len(row) > 1 and row[1] == prompt_id:
            return "running"
    for row in q.get("queue_pending") or []:
        if len(row) > 1 and row[1] == prompt_id:
            return "pending"
    return "unknown"
