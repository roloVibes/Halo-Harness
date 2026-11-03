"""tests.helpers.fake_tensorfold_server -- Halo 3.3.9.3: a stand-in for TensorFold's `tensorfold` that loads no model and
needs no GPU. The tests set `huggingface.tensorfold_bin` to [python, this file]; Halo runs it exactly as it runs the
real one:

    tensorfold --version              "tensorfold-native 0.0.0-fake" (the Homebrew formula's test wording)
    tensorfold capabilities --json    {"schema": 1, "engine": "zig", "version", "chip", "backends": [FAKE_TF_BACKEND], ...}
    tensorfold serve <repo|dir> --name N --host H --port P --context C [--api-key-file F] [--parallel N] [--metrics-open]
        reads the key file ("label: key" lines, # comments), sleeps FAKE_TF_LOAD_S (default 0.3) BEFORE it binds (the
        real server opens its port once the checkpoint is loaded), prints the capacity, profile and serving lines
        (tests/helpers/tf_lines.py; Metal or CUDA by FAKE_TF_BACKEND, FAKE_TF_SM, FAKE_TF_STREAMS), then binds
        127.0.0.1:P whatever --host says and answers like zig/src/server/status_routes.zig: GET /health ({"status":
        "ok"} only when keys are on, else model, model_ids, max_batch_size, live {connections, waiting, ...}, version,
        backend, device); GET /v1/models (owned_by "tensorfold", context_length, max_model_len; a key when keys are
        on); GET /metrics (Prometheus text: tensorfold:requests_running / requests_waiting, the vLLM mirrors, server_info;
        a key unless --metrics-open); POST /v1/chat/completions an OpenAI reply with `usage`, and the done line.
        FAKE_TF_WAITING sets the waiting count it reports (default 0) and the done line's queued seconds.
        FAKE_TF_EXIT=driver|keyfile: it prints that refusal and exits 1. TENSORFOLD_LOG_TIME=1 stamps each line.
Its log lines are TensorFold's own wording from the source, unverified against a live run.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tf_lines as L  # noqa: E402


def _arg(argv: list, name: str, default=None):
    return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else default


def _say(line: str) -> None:
    if os.environ.get("TENSORFOLD_LOG_TIME") == "1":
        now = datetime.now(timezone.utc)
        line = f"{now.strftime('%Y-%m-%dT%H:%M:%S')}.{now.microsecond // 1000:03d}Z {line}"
    print(line, flush=True)


def _keys(path) -> list:
    if not path:
        return []
    out = []
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        if s and not s.startswith("#"):
            out.append(s.split(":", 1)[1].strip() if ": " in s else s)
    return out


def caps() -> dict:
    be = os.environ.get("FAKE_TF_BACKEND") or "cuda"
    return {"schema": 1, "engine": "zig", "version": "0.0.0-fake", "chip": "Apple M3 Max" if be == "metal" else None,
            "backends": [be], "families": {"qwen3_5": ["mlx-4bit"], "nemotron_h": ["mlx-4bit", "nvfp4"]},
            "serve": {"flags": {"--parallel": {"values": ["auto"]}}}, "env": ["TENSORFOLD_API_KEY", "HF_HUB_CACHE"],
            "optional_libraries": [], "profiles": {"available": ["stable"]}}


def serve(argv: list) -> int:
    model, port = argv[0] if argv else "", int(_arg(argv, "--port", "8080"))
    name, window = _arg(argv, "--name", Path(model).name or model), int(_arg(argv, "--context", "32768"))
    keys, open_metrics = _keys(_arg(argv, "--api-key-file")), "--metrics-open" in argv
    be, sm = os.environ.get("FAKE_TF_BACKEND") or "cuda", int(os.environ.get("FAKE_TF_SM") or 89)
    streams = int(_arg(argv, "--parallel", "") or os.environ.get("FAKE_TF_STREAMS") or 4)
    waiting = int(os.environ.get("FAKE_TF_WAITING") or 0)
    fail = os.environ.get("FAKE_TF_EXIT")
    if fail == "driver":
        _say(L.driver_refused())
        return 1
    if fail == "keyfile":
        _say(L.key_file_refused())
        return 1
    time.sleep(float(os.environ.get("FAKE_TF_LOAD_S") or 0.3))
    state = {"running": 0}

    class H(BaseHTTPRequestHandler):
        def log_message(self, *_a):
            pass

        def _send(self, code, body: bytes, ctype="application/json"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code, obj):
            self._send(code, json.dumps(obj).encode("utf-8"))

        def _keyed(self) -> bool:
            got = (self.headers.get("Authorization") or "").removeprefix("Bearer ").strip()
            return not keys or got in keys or self.headers.get("x-api-key") in keys

        def do_GET(self):  # noqa: N802
            path = self.path.split("?", 1)[0].rstrip("/") or "/"
            if path in ("/health", "/"):
                if keys:
                    return self._json(200, {"status": "ok"})
                return self._json(200, {"status": "ok", "model": name, "model_ids": [name], "max_batch_size": streams,
                                        "warming": False, "memory": {}, "live": {"connections": state["running"] + waiting,
                                        "waiting": waiting, "decode_tokens_per_second": 0.0,
                                        "prefill_tokens_per_second": 0.0}, "version": "0.0.0-fake", "backend": be,
                                        "device": "Apple M3 Max" if be == "metal" else "NVIDIA GeForce RTX 4090"})
            if path in ("/metrics", "/v1/metrics"):
                if not (open_metrics or self._keyed()):
                    return self._json(401, {"error": {"message": "invalid api key", "type": "authentication_error"}})
                text = (f'tensorfold:server_info{{model="{name}",backend="{be}",version="0.0.0-fake",instance="f1"}} 1\n'
                        f"tensorfold:lanes {streams}\ntensorfold:requests_running {state['running']}\n"
                        f"tensorfold:requests_waiting {waiting}\nvllm:num_requests_waiting {waiting}\n")
                return self._send(200, text.encode("utf-8"), "text/plain; version=0.0.4")
            if not self._keyed():
                return self._json(401, {"error": {"message": "invalid api key", "type": "authentication_error"}})
            if path in ("/v1/models", "/models"):
                return self._json(200, {"object": "list", "data": [{"id": name, "object": "model", "created": int(time.time()),
                                        "owned_by": "tensorfold", "context_length": window, "max_model_len": window}]})
            return self._json(404, {"error": {"message": "not found"}})

        def do_POST(self):  # noqa: N802
            n = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(n) or b"{}")
            except ValueError:
                body = {}
            if not self._keyed():
                return self._json(401, {"error": {"message": "invalid api key", "type": "authentication_error"}})
            if not self.path.endswith("/chat/completions"):
                return self._json(404, {"error": {"message": "not found"}})
            text = " ".join(str(m.get("content") or "") for m in body.get("messages") or [] if isinstance(m, dict))
            p_tok, want = max(1, len(text) // 4), int(body.get("max_tokens") or 16)
            out = min(want, 120)
            state["running"] += 1
            time.sleep(0.05)  # Windows' clock ticks ~15 ms: a 0 s reply makes a tok/s of None
            state["running"] -= 1
            _say(L.done(prompt=p_tok, tokens=out, tok_s=40.0, queued=2.5 * waiting))
            return self._json(200, {"id": "chatcmpl-fake", "object": "chat.completion", "model": name, "choices": [
                {"index": 0, "message": {"role": "assistant", "content": "ready " * out},
                 "finish_reason": "length" if out >= want else "stop"}],
                "usage": {"prompt_tokens": p_tok, "completion_tokens": out, "total_tokens": p_tok + out}})

    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    srv.daemon_threads = True
    for line in L.load(name, port, backend=be, sm=sm, streams=streams, window=window):
        _say(line)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        return 0


def main(argv: list) -> int:
    if argv[:1] in (["--version"], ["-V"]):
        print("tensorfold-native 0.0.0-fake")
        return 0
    if argv[:1] == ["--help"]:
        print("usage: tensorfold-native capabilities --json | models | info MODEL | pull REPO[@REVISION] | serve MODEL")
        return 0
    if argv[:2] == ["capabilities", "--json"]:
        print(json.dumps(caps()))
        return 0
    if argv[:1] == ["serve"]:
        return serve(argv[1:])
    print(f"tensorfold: unknown command {' '.join(argv[:1])}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
