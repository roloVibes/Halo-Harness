"""tests.helpers.fake_llama_server -- Halo 3.3.5.0 R5: a stand-in for llama.cpp's `llama-server` that loads no
model. Run as `python fake_llama_server.py -m <file> --alias <id> -c <n_ctx> -ngl <n> -np <slots> --port <p>
--host 127.0.0.1 [...]` (the tests set `huggingface.llama_server_bin` to [python, this file]); it binds the port
given and answers the way llama-server does:

    GET /health      503 {"error": {"code": 503, "message": "Loading model"}} while it "loads", then {"status": "ok"}
    GET /props       {"default_generation_settings": {"n_ctx": <-c>}, "total_slots": <-np>, "model_path": <-m>}
    GET /v1/models   {"object": "list", "data": [{"id": <--alias or -m>, "meta": {"n_ctx_train": <-c>}}]}
    GET /slots       one {"id", "n_ctx", "is_processing": false} per slot
    GET /metrics     a few Prometheus lines

It prints llama.cpp's own log lines for the load (the ones a log reader keys on: `load_tensors: offloaded N/N
layers to GPU`, `llama_kv_cache: CUDA0 KV buffer size`, `main: server is listening on`) and one line per request.
FAKE_LLAMA_LOAD_S (env) is how long it "loads" (default 0.3); FAKE_LLAMA_EXIT=1 makes it exit at once with an
error, the way a bad argument does.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def _arg(argv: list, *names, default=None):
    for n in names:
        if n in argv and argv.index(n) + 1 < len(argv):
            return argv[argv.index(n) + 1]
    return default


def main(argv: list) -> int:
    port = int(_arg(argv, "--port", default="8080"))
    n_ctx = int(_arg(argv, "-c", "--ctx-size", default="4096"))
    slots = int(_arg(argv, "-np", "--parallel", default="1"))
    ngl = _arg(argv, "-ngl", "--n-gpu-layers", default="0")
    path = _arg(argv, "-m", "--model", default="")
    alias = _arg(argv, "--alias", default=path)
    say = lambda line: print(line, flush=True)  # noqa: E731
    say(f"build: 9999 (fake) with fake compiler for {sys.platform}")
    say(f"main: loading model '{path}' (-c {n_ctx} -ngl {ngl} -np {slots})")
    if os.environ.get("FAKE_LLAMA_EXIT") == "1":
        say("error: failed to load model (the fake was told to fail)")
        return 1
    load_s = float(os.environ.get("FAKE_LLAMA_LOAD_S") or 0.3)
    ready = threading.Event()

    class H(BaseHTTPRequestHandler):
        def log_message(self, *_a):
            pass

        def _json(self, code, obj):
            body = json.dumps(obj).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):  # noqa: N802
            say(f"srv  log_server_r: request: GET {self.path} 127.0.0.1 {200 if ready.is_set() else 503}")
            if not ready.is_set() and self.path != "/props":
                return self._json(503, {"error": {"code": 503, "message": "Loading model", "type": "unavailable_error"}})
            if self.path == "/health":
                return self._json(200, {"status": "ok"})
            if self.path == "/props":
                return self._json(200, {"default_generation_settings": {"n_ctx": n_ctx}, "total_slots": slots,
                                        "model_path": path, "build_info": "fake"})
            if self.path.rstrip("/").endswith("/models"):
                return self._json(200, {"object": "list", "data": [{"id": alias, "object": "model", "meta": {"n_ctx_train": n_ctx}}]})
            if self.path == "/slots":
                return self._json(200, [{"id": i, "n_ctx": n_ctx // slots, "is_processing": False} for i in range(slots)])
            if self.path == "/metrics":
                body = b"llamacpp:prompt_tokens_total 0\nllamacpp:tokens_predicted_total 0\nllamacpp:requests_processing 0\n"
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return None
            return self._json(404, {"error": {"code": 404, "message": "File Not Found"}})

    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    time.sleep(load_s)
    say(f"load_tensors: offloaded {ngl}/{ngl} layers to GPU")
    say(f"llama_kv_cache: CUDA0 KV buffer size = {n_ctx * 48 * 1024 // 2 ** 20:.2f} MiB")
    say("sched_reserve: graph nodes = 1000, graph splits = 2")
    ready.set()
    say(f"main: server is listening on http://127.0.0.1:{port} - starting the main loop")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
