"""tests.helpers.fake_engine -- a stand-in for every engine of the descriptor table that loads no model and needs no GPU.
The tests set `huggingface.engine_bins.<id>` = [python, this file, <id>] (tests/helpers/engine_home.EngineHome); Halo
runs it exactly as it runs the real program, with the descriptor's start command:

    <id> --version                    the engine's own version line
    freetoken / tensorfold: serve ... binds 127.0.0.1:--port whatever --host says (a test never binds another address)
        after FAKE_ENGINE_LOAD_S (0.2); /health (FreeToken "loading" first), /v1/models (the descriptor's owned_by),
        /metrics (FAKE_ENGINE_WAITING), chat completions with `usage`; a key (FREETOKEN_API_KEY, --api-key-file,
        --api-key-env) guards every route but /health; its lines are tests/helpers/engine_lines.py's
    strata: launch --plan --output json   {"plan": {"download": {"gb": FAKE_ENGINE_DOWNLOAD_GB}}}
            launch ... --no-tui           starts the server in a process of its own (as Strata's supervisor does),
                                          prints the "Engine log" line and returns; its state is FAKE_ENGINE_STATE
            launch --status --output json / launch --stop --preset NAME
    FAKE_ENGINE_EXIT=1: the start prints an error line and exits 1. Every argv is appended to FAKE_ENGINE_STATE/argv.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine_lines as L  # noqa: E402

VERSIONS = {"freetoken": "freetoken version 0.0.0+gfake", "strata": "strata 0.2.10 (build fake; python 3)",
            "tensorfold": "tensorfold-native 1.2.1"}
STATE = Path(os.environ.get("FAKE_ENGINE_STATE") or ".")


def _arg(argv: list, name: str, default=None):
    return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else default


def _key(engine: str, argv: list) -> str:
    if os.environ.get("FAKE_ENGINE_NO_KEY"):  # 3.3.14.0 R2 (REVIEW #24): an engine that ignores the key it is given
        return ""
    if engine == "freetoken":
        return os.environ.get("FREETOKEN_API_KEY") or ""
    if _arg(argv, "--api-key-file"):
        return Path(_arg(argv, "--api-key-file")).read_text(encoding="utf-8").split(":", 1)[1].strip()
    return os.environ.get(_arg(argv, "--api-key-env", "") or "_none_") or ""


def serve(engine: str, argv: list, log=None) -> int:
    say = (lambda s: print(s, file=log, flush=True)) if log else (lambda s: print(s, flush=True))  # noqa: E731
    port = int(_arg(argv, "--port", "0"))
    name = _arg(argv, "--served-model-name") or _arg(argv, "--name") or Path(_arg(argv, "--model", "m")).name
    key, ready, t0 = _key(engine, argv), threading.Event(), time.time()
    if os.environ.get("FAKE_ENGINE_EXIT"):
        say(f"RuntimeError: nvcc 12.4 would build kernels; Install a CUDA 13.x toolkit ({engine} fake)")
        return 1
    owned = {"freetoken": "FreeToken", "tensorfold": "tensorfold"}.get(engine)

    class H(BaseHTTPRequestHandler):
        def log_message(self, *_a):
            pass

        def _send(self, code, obj, ctype="application/json"):
            body = (obj if isinstance(obj, str) else json.dumps(obj)).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _ok(self) -> bool:
            return not key or (self.headers.get("Authorization") or "") == f"Bearer {key}"

        def do_GET(self):  # noqa: N802
            if self.path == "/health":
                if engine == "strata":
                    return self._send(200, {"status": "ok", "service": "strata", "loaded": ready.is_set()})
                return self._send(200, {"status": "ok" if ready.is_set() else "loading", "model": name})
            if not self._ok():
                return self._send(401, {"error": {"message": "invalid api key"}})
            if self.path == "/metrics":
                return self._send(200, f"# TYPE x gauge\ntensorfold:requests_running 1\ntensorfold:requests_waiting "
                                       f"{os.environ.get('FAKE_ENGINE_WAITING') or 0}\ntensorfold:lanes 4\n", "text/plain")
            row = {"id": name, "object": "model", **({"owned_by": owned, "context_length": 32768} if owned else
                                                     {"meta": {"n_ctx": 32768}, "architecture": "qwen", "status": {}})}
            return self._send(200, {"object": "list", "data": [row]})

        def do_POST(self):  # noqa: N802
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n) or b"{}")
            if not self._ok():
                return self._send(401, {"error": {"message": "invalid api key"}})
            text = " ".join(str(m.get("content") or "") for m in body.get("messages") or [] if isinstance(m, dict))
            p_tok, want = max(1, len(text) // 4), int(body.get("max_tokens") or 16)
            out = min(want, 120)
            time.sleep(0.03)  # a measurable reply: the bench's rates never divide by a clock tick of 0
            say(L.st_done(out) if engine == "strata" else L.tf_done(out) if engine == "tensorfold" else
                L.ft("Decode batch, #running-req: 1, gen throughput (token/s): 24.00"))
            return self._send(200, {"id": "c", "object": "chat.completion", "model": name, "choices": [
                {"index": 0, "message": {"role": "assistant", "content": "ready " * out},
                 "finish_reason": "length" if out >= want else "stop"}],
                "usage": {"prompt_tokens": p_tok, "completion_tokens": out, "total_tokens": p_tok + out}})

    if engine == "tensorfold":  # TensorFold opens its port only once the checkpoint is loaded
        time.sleep(float(os.environ.get("FAKE_ENGINE_LOAD_S") or 0.2))
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    if engine == "freetoken":
        time.sleep(float(os.environ.get("FAKE_ENGINE_LOAD_S") or 0.2))
    lines = {"freetoken": L.ft_load(port), "tensorfold": [L.tf_capacity(), L.tf_serving(name, port)],
             "strata": ["[strata] starting the engine: reading the model's weights ...", L.st_ready(port)]}[engine]
    for line in lines:
        say(line)
    ready.set()
    while True:
        time.sleep(3600)


def kill(pid: int) -> None:
    import signal
    try:
        os.kill(int(pid), signal.SIGTERM)
    except (OSError, ValueError):
        pass


def _servers() -> list:
    try:
        return json.loads((STATE / "servers.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def launch(argv: list) -> int:
    if "--plan" in argv:
        print(json.dumps({"plan": {"download": {"gb": float(os.environ.get("FAKE_ENGINE_DOWNLOAD_GB") or 0),
                                                "text": "the set"}}}))
        return 0
    if "--status" in argv:
        print(json.dumps({"running": _servers()}))
        return 0
    if "--stop" in argv:
        name, rows = _arg(argv, "--preset"), _servers()
        for r in rows:
            if r["name"] == name:
                kill(r["pid"])
        (STATE / "servers.json").write_text(json.dumps([r for r in rows if r["name"] != name]), encoding="utf-8")
        print(f"stopped {name}")
        return 0
    port, profile = int(_arg(argv, "--port")), f"launch-{_arg(argv, '--port')}"
    engine_log, server_log = STATE / "launch" / f"{profile}.engine.log", STATE / "runtime" / f"{profile}.server.log"
    for p in (engine_log, server_log):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("", encoding="utf-8")
    child = subprocess.Popen([sys.executable, __file__, "strata", "--server", str(server_log)] + argv,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    rows = [r for r in _servers() if r["port"] != port] + [{"name": profile, "profile": profile, "port": port,
                                                            "pid": child.pid, "state": "running"}]
    (STATE / "servers.json").write_text(json.dumps(rows), encoding="utf-8")
    print("Strata is serving.")
    print(f"  Engine log  {engine_log}  (follow it to watch the engine)")
    return 0


def main(argv: list) -> int:
    engine, rest = argv[0], argv[1:]
    STATE.mkdir(parents=True, exist_ok=True)
    with open(STATE / "argv", "a", encoding="utf-8") as f:
        f.write(json.dumps([engine] + rest) + "\n")
    if rest[:1] == ["--version"]:
        print(VERSIONS[engine])
        return 0
    if rest[:1] == ["--server"]:
        with open(rest[1], "a", encoding="utf-8") as log:
            return serve(engine, rest[2:], log)
    if rest[:1] == ["launch"]:
        return launch(rest[1:])
    if rest[:1] == ["serve"]:
        return serve(engine, rest[1:] if engine != "tensorfold" else rest[2:] + ["--model", rest[1]])
    print(f"unknown {engine} command: {' '.join(rest[:1])}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
