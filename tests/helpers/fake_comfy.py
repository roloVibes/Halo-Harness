"""tests.helpers.fake_comfy -- a stdlib stand-in for a ComfyUI 0.37 server
(Halo 3.0.4.0 round R1) with the response shapes seen on a live one
(2026-10-14): /system_stats, /models, /models/<folder> and
/experiment/models/<folder> (file sizes) (the live file lists as a fixture), /object_info[/<node>] (the classes the starter
workflows use), /userdata?dir=workflows and /userdata/workflows%2F<name>
(one UI-format fixture; GET and POST, 409 without overwrite), POST /prompt
(records the graph, 400 with node_errors for an unknown class), /queue,
/history/<id> (completed after one poll, one output per Save node; an input
value "__fail__" makes it an execution error), /view (a 1x1 PNG or a few MP4
bytes) and POST /upload/image. In-memory, a daemon thread, every request
recorded in `requests`.
"""

from __future__ import annotations

import base64
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "comfy"
PNG_1X1 = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
MP4_BYTES = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"\x00" * 16
UI_NAME = "Fixture UI workflow.json"


def fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class FakeComfy:
    def __init__(self, *, pending_polls: int = 1):
        self.object_info = fixture("object_info.json")
        self.model_files = fixture("models.json")
        self.model_sizes: dict = {}  # file name -> bytes for /experiment/models/<folder>; default 1 MB + name length
        self.workflows = {UI_NAME: fixture("ui_workflow.json"), "Second saved.json": fixture("ui_workflow.json")}
        self.prompts: list = []
        self.history: dict = {}
        self.uploads: list = []
        self.requests: list = []
        self.pending_polls = pending_polls
        self._polls: dict = {}
        self._srv = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self._srv.daemon_threads = True
        threading.Thread(target=self._srv.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self._srv.server_address[1]}"

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        self._srv.shutdown()
        self._srv.server_close()

    # ---- behaviour -------------------------------------------------------------------------
    def queue_prompt(self, body: dict) -> "tuple[int, dict]":
        graph = body.get("prompt")
        if not isinstance(graph, dict) or not graph:
            return 400, {"error": {"type": "invalid_prompt", "message": "no prompt"}, "node_errors": {}}
        errors = {nid: {"errors": [{"message": f"class {n.get('class_type')} does not exist"}], "class_type": n.get("class_type")}
                  for nid, n in graph.items() if n.get("class_type") not in self.object_info}
        if errors:
            return 400, {"error": {"type": "prompt_outputs_failed_validation", "message": "Prompt outputs failed validation"},
                         "node_errors": errors}
        pid = f"fake-{len(self.prompts) + 1:04d}"
        self.prompts.append({"prompt_id": pid, "graph": graph, "client_id": body.get("client_id")})
        self.history[pid] = self._entry(pid, graph)
        self._polls[pid] = 0
        return 200, {"prompt_id": pid, "number": len(self.prompts), "node_errors": {}}

    def _entry(self, pid: str, graph: dict) -> dict:
        for nid, n in graph.items():
            if "__fail__" in [v for v in (n.get("inputs") or {}).values() if isinstance(v, str)]:
                return {"prompt": [0, pid, graph, {}, []], "outputs": {},
                        "status": {"status_str": "error", "completed": False, "messages": [
                            ["execution_start", {"prompt_id": pid}],
                            ["execution_error", {"prompt_id": pid, "node_id": nid, "node_type": n["class_type"],
                                                 "exception_type": "RuntimeError", "exception_message": "fake failure"}]]}}
        outputs = {}
        for nid, n in graph.items():
            prefix = str((n.get("inputs") or {}).get("filename_prefix") or "ComfyUI")
            sub, _, base = prefix.rpartition("/")
            if n.get("class_type") == "SaveImage":
                outputs[nid] = {"images": [{"filename": f"{base}_00001_.png", "subfolder": sub, "type": "output"}]}
            elif n.get("class_type") == "SaveVideo":
                outputs[nid] = {"images": [{"filename": f"{base}_00001_.mp4", "subfolder": sub, "type": "output"}],
                                "animated": [True]}
        return {"prompt": [0, pid, graph, {}, list(outputs)], "outputs": outputs,
                "status": {"status_str": "success", "completed": True, "messages": []}, "meta": {}}

    def history_for(self, pid: str) -> dict:
        if pid not in self.history:
            return {}
        self._polls[pid] = self._polls.get(pid, 0) + 1
        return {pid: self.history[pid]} if self._polls[pid] > self.pending_polls else {}

    def queue(self) -> dict:
        pending = [[i, p["prompt_id"], {}, {}, []] for i, p in enumerate(self.prompts)
                   if self._polls.get(p["prompt_id"], 0) <= self.pending_polls]
        return {"queue_running": pending[:1], "queue_pending": pending[1:]}

    # ---- HTTP ------------------------------------------------------------------------------
    def _handler(self):
        fake = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, status, obj=None, raw=None, ctype="application/json"):
                body = raw if raw is not None else json.dumps(obj).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _body(self) -> bytes:
                n = int(self.headers.get("Content-Length") or 0)
                return self.rfile.read(n) if n else b""

            def do_GET(self):
                parts = urlsplit(self.path)
                path, q = unquote(parts.path), parse_qs(parts.query)
                fake.requests.append(("GET", self.path))
                if path == "/system_stats":
                    return self._send(200, {"system": {"os": "posix", "comfyui_version": "0.37.0",
                                                       "python_version": "3.12.10 (main)", "pytorch_version": "2.14.0+cu130"},
                                            "devices": [{"name": "cuda:0 Fake GPU", "type": "cuda", "index": 0,
                                                         "vram_total": 24 * 2**30, "vram_free": 22 * 2**30}]})
                if path.startswith("/experiment/models/"):
                    folder = path[len("/experiment/models/"):]
                    if folder not in fake.model_files:
                        return self._send(404, {"error": "no folder"})
                    return self._send(200, [{"name": n, "pathIndex": 0, "size": fake.model_sizes.get(n, 1_000_000 + len(n))}
                                            for n in fake.model_files[folder]])
                if path == "/models":
                    return self._send(200, list(fake.model_files))
                if path.startswith("/models/"):
                    folder = path[len("/models/"):]
                    return self._send(200, fake.model_files[folder]) if folder in fake.model_files else self._send(404, {"error": "no folder"})
                if path == "/object_info":
                    return self._send(200, fake.object_info)
                if path.startswith("/object_info/"):
                    node = path[len("/object_info/"):]
                    return self._send(200, {node: fake.object_info[node]} if node in fake.object_info else {})
                if path == "/userdata" and q.get("dir") == ["workflows"]:
                    return self._send(200, sorted(fake.workflows))
                if path.startswith("/userdata/workflows/"):
                    name = path[len("/userdata/workflows/"):]
                    return self._send(200, fake.workflows[name]) if name in fake.workflows else self._send(404, {"error": "not found"})
                if path == "/queue":
                    return self._send(200, fake.queue())
                if path.startswith("/history/"):
                    return self._send(200, fake.history_for(path[len("/history/"):]))
                if path == "/view":
                    fn = (q.get("filename") or [""])[0]
                    if fn.endswith(".png"):
                        return self._send(200, raw=PNG_1X1, ctype="image/png")
                    if fn.endswith(".mp4"):
                        return self._send(200, raw=MP4_BYTES, ctype="video/mp4")
                    return self._send(404, {"error": "no such file"})
                return self._send(404, {"error": f"no route {path}"})

            def do_POST(self):
                parts = urlsplit(self.path)
                path, q = unquote(parts.path), parse_qs(parts.query)
                body = self._body()
                fake.requests.append(("POST", self.path))
                if path == "/prompt":
                    try:
                        payload = json.loads(body.decode("utf-8"))
                    except ValueError:
                        return self._send(400, {"error": {"message": "bad json"}})
                    status, obj = fake.queue_prompt(payload)
                    return self._send(status, obj)
                if path.startswith("/userdata/workflows/"):
                    name = path[len("/userdata/workflows/"):]
                    if name in fake.workflows and q.get("overwrite", ["true"])[0] != "true":
                        return self._send(409, {"error": "file exists"})
                    fake.workflows[name] = json.loads(body.decode("utf-8"))
                    return self._send(200, f"workflows/{name}")
                if path == "/upload/image":
                    text = body.decode("latin-1")
                    marker = 'filename="'
                    i = text.find(marker)
                    name = text[i + len(marker):text.find('"', i + len(marker))] if i >= 0 else "upload.png"
                    fake.uploads.append({"name": name, "bytes": len(body)})
                    return self._send(200, {"name": name, "subfolder": "", "type": "input"})
                return self._send(404, {"error": f"no route {path}"})

        return H
