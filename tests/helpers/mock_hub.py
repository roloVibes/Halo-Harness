"""tests.helpers.mock_hub -- Halo 3.3.5.0 R5: a fake Hugging Face Hub on 127.0.0.1:0 for providers/hf_download.py
(`HF_ENDPOINT` names it). It answers the two calls a download makes, the way huggingface.co does:

    GET /api/models/<repo>?blobs=true     the repo's info: id, sha (the commit), gated (false | "manual"),
                                          cardData {license, extra_gated_prompt}, tags, siblings [{rfilename,
                                          blobId (the git blob sha1), size, lfs {sha256, size}}]
    GET /<repo>/resolve/main/<file>       the bytes; `Range: bytes=N-` answers 206 with Content-Range; a gated repo
                                          answers 401 (X-Error-Code: GatedRepo) without `Authorization: Bearer
                                          <its token>`; an unknown repo or file 404

`hub.add(repo, files, gated=, token=, license=, kind=)` adds a repo (a .gguf / .safetensors file gets an `lfs`
entry, like the hub); `hub.corrupt(repo, file)` serves other bytes than the listing's sha256 says;
`hub.delay_s` waits between CHUNK-sized writes (a cancel test, a progress bar); `hub.no_range` ignores Range (a
server that answers 200 to a resume). `hub.requests` logs (path, range, auth) and `hub.aborted` every transfer the
client hung up on. Nothing here reaches the network.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CHUNK = 64 * 1024
COMMIT = "c0ffee" + "0" * 34
LFS_SUFFIXES = (".gguf", ".safetensors")


def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def gguf_bytes(n: int, seed: str = "q", *, ctx: int = 40960, layers: int = 36) -> bytes:
    """`n` bytes of a GGUF file: a real header (a qwen3-shaped model_info: the trained context, the layers, 32 / 8
    heads, 4096 wide, file type Q4_K_M) that providers/gguf_header.py reads, then filler for the weights."""
    import struct

    def s(v: str) -> bytes:
        b = v.encode("utf-8")
        return struct.pack("<Q", len(b)) + b

    def kv(key: str, value) -> bytes:
        return s(key) + (struct.pack("<I", 8) + s(value) if isinstance(value, str) else struct.pack("<II", 4, value))
    kvs = [kv("general.architecture", "qwen3"), kv("general.file_type", 15), kv("qwen3.context_length", ctx),
           kv("qwen3.block_count", layers), kv("qwen3.attention.head_count", 32), kv("qwen3.attention.head_count_kv", 8),
           kv("qwen3.embedding_length", 4096), kv("qwen3.attention.key_length", 128), kv("qwen3.attention.value_length", 128)]
    head = b"GGUF" + struct.pack("<IQQ", 3, 0, len(kvs)) + b"".join(kvs)
    body = (hashlib.sha256(seed.encode()).digest() * (n // 32 + 1))[: max(0, n - len(head))]
    return head + body


class MockHub:
    def __init__(self) -> None:
        self.repos: dict = {}
        self.requests: list = []
        self.aborted: list = []
        self.delay_s = 0.0
        self.no_range = False
        self._lock = threading.Lock()
        self.server = None
        self.base_url = ""

    def add(self, repo: str, files: dict, *, gated=False, token: str = "", license: str = "apache-2.0",
            kind: str = "gguf", prompt: str = "") -> dict:
        siblings = []
        for name, data in files.items():
            s = {"rfilename": name, "blobId": git_blob_sha1(data), "size": len(data)}
            if name.lower().endswith(LFS_SUFFIXES):
                s["lfs"] = {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data), "pointerSize": 134}
            siblings.append(s)
        card = {"license": license}
        if prompt:
            card["extra_gated_prompt"] = prompt
        info = {"id": repo, "modelId": repo, "sha": COMMIT, "private": False, "gated": gated, "disabled": False,
                "tags": [kind, f"license:{license}"], "cardData": card, "siblings": siblings,
                "lastModified": "2026-10-01T00:00:00.000Z", "downloads": 10}
        self.repos[repo] = {"info": info, "files": dict(files), "served": dict(files), "token": token}
        return info

    def corrupt(self, repo: str, name: str) -> None:
        data = self.repos[repo]["files"][name]
        self.repos[repo]["served"][name] = data[:-1] + bytes([(data[-1] + 1) % 256])

    def start(self) -> "MockHub":
        hub = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *_a):
                pass

            def _json(self, code: int, obj, headers=None) -> None:
                body = json.dumps(obj).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                for k, v in (headers or {}).items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):  # noqa: N802
                parsed = urllib.parse.urlparse(self.path)
                path = urllib.parse.unquote(parsed.path)
                with hub._lock:
                    hub.requests.append({"path": path, "range": self.headers.get("Range"),
                                         "auth": self.headers.get("Authorization")})
                if path.startswith("/api/models/"):
                    got = hub.repos.get(path[len("/api/models/"):])
                    return self._json(200, got["info"]) if got else self._json(404, {"error": "Repository not found"})
                if "/resolve/main/" not in path:
                    return self._json(404, {"error": "not found"})
                repo, _, name = path.lstrip("/").partition("/resolve/main/")
                got = hub.repos.get(repo)
                if got is None or name not in got["served"]:
                    return self._json(404, {"error": "Entry not found"}, {"X-Error-Code": "EntryNotFound"})
                if got["info"]["gated"] and self.headers.get("Authorization") != f"Bearer {got['token']}":
                    return self._json(401, {"error": f"Access to model {repo} is restricted."}, {"X-Error-Code": "GatedRepo"})
                self._bytes(repo, name, got["served"][name], got["info"])

            def _bytes(self, repo: str, name: str, data: bytes, info: dict) -> None:
                start = 0
                rng = self.headers.get("Range") or ""
                if rng.startswith("bytes=") and not hub.no_range:
                    start = int(rng[6:].split("-", 1)[0] or 0)
                if start >= len(data) and start:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{len(data)}")
                    self.end_headers()
                    return
                sib = next(s for s in info["siblings"] if s["rfilename"] == name)
                self.send_response(206 if start else 200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(len(data) - start))
                self.send_header("X-Repo-Commit", info["sha"])
                self.send_header("ETag", f'"{(sib.get("lfs") or {}).get("sha256") or sib["blobId"]}"')
                if start:
                    self.send_header("Content-Range", f"bytes {start}-{len(data) - 1}/{len(data)}")
                self.end_headers()
                try:
                    for i in range(start, len(data), CHUNK):
                        self.wfile.write(data[i:i + CHUNK])
                        self.wfile.flush()
                        if hub.delay_s:
                            time.sleep(hub.delay_s)
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    with hub._lock:
                        hub.aborted.append((repo, name))

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.server.daemon_threads = True
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return self

    def stop(self) -> None:
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()

    def resolves(self) -> list:
        return [r for r in self.requests if "/resolve/main/" in r["path"]]


__all__ = ["CHUNK", "COMMIT", "MockHub", "git_blob_sha1", "gguf_bytes"]
