"""tests.helpers.fake_ft_server -- Halo 3.3.9.1: a stand-in for FreeToken's `ft` that loads no model and needs no GPU.
The tests set `huggingface.freetoken_bin` to [python, this file]; Halo runs it exactly as it runs the real one:

    ft --version                      "freetoken version 0.0.0+gfake" (cli.py's wording)
    ft bench bw [--model M]           the report's ceilings line and one row (moe/benchbw.py's print format);
                                      FAKE_FT_GATHER sets the PCIe-gather GB/s (default 27.9)
    ft serve --model <dir> --served-model-name N --host H --port P [--moe-collect-stats]
        binds 127.0.0.1:P whatever --host says (a test never binds another address) and answers like FreeToken's
        server/control_api.py and openai_api.py: GET /health {"status": "loading", "progress": {...}} while it "loads"
        (FAKE_FT_LOAD_S, default 0.3), then {"status": "ok", "model", "instance_id", "uptime_s", "maintenance",
        "version"}; GET /v1/models one ModelCard {id, object, owned_by: "FreeToken", root, max_model_len,
        context_length (FAKE_FT_CTX, default 32768)}; POST /v1/chat/completions an OpenAI reply with `usage`, and
        the scheduler's Prefill / Decode lines plus, with --moe-collect-stats, the MoE decode line (FAKE_FT_HIT, the
        hit rate, default 0.82). FREETOKEN_API_KEY in its environment: a Bearer key on every route but /health.
        FAKE_FT_EXIT=nvcc|pin: it prints that failure and exits 1.

Its log lines are tests/helpers/ft_lines.py's (FreeToken's own wording, from the source, unverified).
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ft_lines as L  # noqa: E402


def _arg(argv: list, name: str, default=None):
    return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else default


def bench_bw() -> int:
    g = float(os.environ.get("FAKE_FT_GATHER") or 27.9)
    print("\n  host fake   gpu cuda:0 (NVIDIA GeForce RTX 3080)   cpu fake (8c, 1 NUMA)")
    print("  ceilings: CPU STREAM read 41.0  |  PCIe linear H2D 24.6  D2H 25.1  GB/s")
    print("\n  nvfp4  H=2048 I=512 top_k=8 threads=8  (fake; threshold 2.0x)")
    print(f"    {'format':<8} {'expert':>9} {'CPU-MoE':>13} {'PCIe-gather':>13} {'CPU/PCIe':>9}  backend")
    print(f"    {'nvfp4':<8} {'1.69 MB':>9} {38.2:>8.1f} GB/s {g:>8.1f} GB/s {38.2 / g:>8.2f}x  offload")
    print("\n  saved: /tmp/fake-benchbw.json (1 rows benched, 1 in the profile)\n")
    return 0


def serve(argv: list) -> int:
    port, path = int(_arg(argv, "--port", "1919")), _arg(argv, "--model", "")
    name = _arg(argv, "--served-model-name", Path(path).name)
    ctx, key = int(os.environ.get("FAKE_FT_CTX") or 32768), os.environ.get("FREETOKEN_API_KEY") or ""
    stats, hit = "--moe-collect-stats" in argv, float(os.environ.get("FAKE_FT_HIT") or 0.82)
    say = lambda line: print(line, flush=True)  # noqa: E731
    say(L.stamp(f"Free memory before loading model: 9.50 GiB"))
    fail = os.environ.get("FAKE_FT_EXIT")
    if fail == "nvcc":
        say(L.nvcc_mismatch())
        return 1
    if fail == "pin":
        say(L.pin_stop())
        return 1
    ready, t0 = threading.Event(), time.time()

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

        def _keyed(self) -> bool:
            got = self.headers.get("Authorization") or ""
            return not key or got == f"Bearer {key}" or self.headers.get("x-api-key") == key

        def do_GET(self):  # noqa: N802
            if self.path == "/health":
                if not ready.is_set():
                    return self._json(200, {"status": "loading", "phase": "weights", "model": name,
                                            "progress": {"done_bytes": 2 * 2 ** 30, "total_bytes": 18 * 2 ** 30}})
                return self._json(200, {"status": "ok", "model": name, "instance_id": "fake-1", "uptime_s": int(time.time() - t0),
                                        "maintenance": "serving", "version": "0.0.0+gfake"})
            if not self._keyed():
                return self._json(401, {"error": {"message": "invalid api key"}})
            if self.path.rstrip("/").endswith("/models"):
                return self._json(200, {"object": "list", "data": [
                    {"id": name, "object": "model", "created": int(t0), "owned_by": "FreeToken", "root": path,
                     "max_model_len": ctx, "context_length": ctx}]})
            return self._json(404, {"detail": "Not Found"})

        def do_POST(self):  # noqa: N802
            n = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(n) or b"{}")
            except ValueError:
                body = {}
            if not self._keyed():
                return self._json(401, {"error": {"message": "invalid api key"}})
            if not self.path.endswith("/chat/completions"):
                return self._json(404, {"detail": "Not Found"})
            text = " ".join(str(m.get("content") or "") for m in body.get("messages") or [] if isinstance(m, dict))
            p_tok, want = max(1, len(text) // 4), int(body.get("max_tokens") or 16)
            out = min(want, 120)
            say(L.prefill(p_tok, 900.0))
            say(L.decode(24.0))
            if stats:
                say(L.moe(hit))
            return self._json(200, {"id": "chatcmpl-fake", "object": "chat.completion", "model": name, "choices": [
                {"index": 0, "message": {"role": "assistant", "content": "ready " * out},
                 "finish_reason": "length" if out >= want else "stop"}],
                "usage": {"prompt_tokens": p_tok, "completion_tokens": out, "total_tokens": p_tok + out}})

    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    time.sleep(float(os.environ.get("FAKE_FT_LOAD_S") or 0.3))
    for line in L.load(port):
        say(line)
    ready.set()
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        return 0


def main(argv: list) -> int:
    if argv[:1] in (["--version"], ["-V"]):
        print("freetoken version 0.0.0+gfake")
        return 0
    if argv[:2] == ["bench", "bw"]:
        return bench_bw()
    if argv[:1] == ["serve"]:
        return serve(argv[1:])
    print(f"unknown ft command: {' '.join(argv[:1])}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
