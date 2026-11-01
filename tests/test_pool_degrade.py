"""tests.test_pool_degrade -- Halo 3.3.8.0 R3 deliverable 8: the failure modes as lines (local_pool/degrade.py; the
loop's pool path in agent/loop.py), over tests/helpers/pool_run_rig.RunRig; no model call:

1. a running pool: "running", each member's claim and lease; R2's server-log reader tails the controller's log (the
   `pool` entry's log and runtime: servers_hf.roster, server_log_hf.tail_lines), the RPC buffer lines in it;
2. a worker's rpc-server gone: "degraded (pc down)" on the status and in route; an RPC failure line in the
   controller's log degrades it too; llama-server exited: "down", its last line said;
3. a request to hf:local/...@pool that fails (an HTTP 500 from a 127.0.0.1 stand-in): one attempt, no retry, and the
   error says "the pool is degraded (pc down): the request failed once and is not retried" (the real `-p` CLI).
Run: python -m tests.test_pool_degrade
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.pool_rig import PoolHome, free_port  # noqa: E402
from tests.helpers.pool_run_rig import QWEN, RunRig  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent


@test
def test_a_running_pool_and_its_log(ctx: Ctx):
    from halo_harness.local_pool.degrade import status
    from halo_harness.ollama_steward import changes_pool
    from halo_harness.ollama_steward.server_log_hf import tail_lines
    from halo_harness.ollama_steward.servers_hf import by_name, reset
    with RunRig() as rig:
        changes_pool.warm(QWEN, state_dir=rig.peer, by="test")
        st = status(rig.peer)
        ctx.check(f"running, the members' claims, got {st['lines']}", st["state"] == "running" and st["lines"][0] ==
                  "the pool serves Qwen3-Next-80B-A3B Q4_K_M: running" and st["lines"][1].startswith(
                      "  pc: up; 19.7 GB claimed by pool:qwen3-next-80b-a3b-q4km, lease"))  # 3.3.8.0 R4: by its bundle
        reset()
        s = by_name("pool", rig.peer)
        lines, source, _why = tail_lines(s, 50) if s else ([], "", "")
        ctx.check(f"R2's reader tails the controller's log, got {s} {source!r} {lines[-3:]}", s is not None
                  and s.runtime == "llama-server" and s.log and any(f"RPC[127.0.0.1:{rig.rpc_port}]" in ln for ln in lines))


@test
def test_degraded_and_down(ctx: Ctx):
    from halo_harness.local_pool import launch
    from halo_harness.local_pool.degrade import status
    from halo_harness.local_pool.route import route
    from halo_harness.ollama_steward import changes_pool
    with RunRig() as rig:
        changes_pool.warm(QWEN, state_dir=rig.peer, by="test")
        rig.fake.kill_all()
        st = status(rig.peer)
        ctx.check(f"pc's rpc-server gone: degraded (pc down), got {st['line']!r}", st["state"] == "degraded"
                  and st["line"].endswith("degraded (pc down)") and st["degraded"] == ["pc"])
        ctx.check("route says it too", route({"model": QWEN}, state_dir=rig.peer)["degraded"] == ["pc"])
    with RunRig() as rig:
        changes_pool.warm(QWEN, state_dir=rig.peer, by="test")
        r = launch.run(rig.peer)
        with open(r["log"], "a", encoding="utf-8") as f:
            f.write("ggml_backend_rpc_get_device_memory: Remote RPC server crashed or returned malformed response\n")
        st = status(rig.peer)
        ctx.check(f"an RPC failure in the controller's log degrades it, got {st['line']!r} {st['log']}",
                  st["state"] == "degraded" and st["log"] and "Remote RPC server crashed" in st["log"][-1])
        from halo_harness.local_pool.spawn import halt
        halt(r["pid"])
        st = status(rig.peer)
        ctx.check(f"llama-server exited: down, its last line said, got {st['line']!r}", st["state"] == "down"
                  and "down: the pool's llama-server exited (" in st["line"])


class _Fails(BaseHTTPRequestHandler):
    posts: list = []

    def log_message(self, *_a):
        pass

    def _send(self, code: int, obj) -> None:
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        if self.path.rstrip("/").endswith("/models"):
            return self._send(200, {"object": "list", "data": [{"id": QWEN, "object": "model"}]})
        return self._send(200, {"status": "ok"})

    def do_POST(self):  # noqa: N802
        n = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(n)
        type(self).posts.append(self.path)
        return self._send(500, {"error": {"code": 500, "message": "RPC backend lost", "type": "server_error"}})


@test
def test_a_failed_pool_request_is_said_once(ctx: Ctx):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Fails)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    _Fails.posts = []
    url = f"http://127.0.0.1:{srv.server_address[1]}/v1"
    try:
        with PoolHome() as h:
            h.config(**{"huggingface.local_servers": [{"name": "pool", "url": url, "pool": True, "max_ctx": 32768,
                                                       "runtime": "llama-server", "model": QWEN}]})
            run = {"model": QWEN, "display": "Qwen3-Next", "pid": os.getpid(), "url": url, "log": "", "placed": [
                {"member": "pc", "kind": "address", "host": "worker1.local", "rpc_port": 50052, "gb": 19.7}],
                "rpc": [{"member": "pc", "addr": f"127.0.0.1:{free_port()}"}], "started": 0}
            (h.state / "pool").mkdir(parents=True, exist_ok=True)
            (h.state / "pool" / "run.json").write_text(json.dumps(run), encoding="utf-8")
            env = {k: v for k, v in os.environ.items() if not k.startswith(("HALO_", "HF_", "OPENROUTER_", "ANTHROPIC_"))}
            env.pop("BRIDGE_STATE_DIR", None)
            env.update(BRIDGE_TEST_HOME=h.root, BRIDGE_TEST_NO_BACKGROUND_NET="1", PYTHONPATH=str(REPO),
                       OLLAMA_HOST="http://127.0.0.1:9")
            r = subprocess.run([sys.executable, "-m", "halo_harness", "-p", "hi", "--model", f"hf:local/{QWEN}@pool",
                                "--cwd", h.root], env=env, cwd=str(REPO), capture_output=True, text=True, timeout=120,
                               stdin=subprocess.DEVNULL)
            out = r.stdout + r.stderr
            ctx.check(f"one attempt, no retry, got {_Fails.posts}", len(_Fails.posts) == 1)
            ctx.check(f"the line: degraded (pc down), failed once, not retried, got {r.returncode} {out[-600:]!r}",
                      r.returncode != 0 and "the pool is degraded (pc down): the request failed once and is not retried"
                      in out)
    finally:
        srv.shutdown()
        srv.server_close()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
