"""tests.test_local_ollama_answers -- Halo 3.6.0.0 R8 fix pass: `halo local` against servers that answer, but not as
Ollama does, and a measurement that waits its turn and leaves the server as it found it.

Loopback only: plain http.server stubs that answer a proxy's HTML page, 401 or a 302, and
`tests/helpers/mock_ollama_loads.LoadCountingOllama`; never a real Ollama, never a real model.

Pinned (the judge's findings on R8):
- M2/S8: `halo local unload | ps | warm | pull` read an answer as Ollama's only when it is one: HTML, a 401 or a
  redirect is one plain line naming what came back and exit 1 (refused / unreadable), never "nothing is loaded",
  "nothing to do", "did not answer" or "HTTP None";
- S5: one measurement per server at a time (a lock in the state dir: the second is refused with a line and loads
  nothing), and the server is left as it was found: the model back at its window, or unloaded when it was not
  loaded; the report says what it did;
- S6: `halo ollama discover --calibrate` / Setup's "Measure the found models" (providers/ollama_discover_measure)
  never steps above the host's max_ctx.
Run: python -m tests.test_local_ollama_answers
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
ensure_default_provider_credentials()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.mock_ollama_loads import LoadCountingOllama  # noqa: E402
from tests.test_local_ollama_verbs import TINY, Rig, _cli  # noqa: E402

test, TESTS = new_registry()


def _stub(kind: str):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _go(self):
            n = int(self.headers.get("Content-Length") or 0)
            if n:
                self.rfile.read(n)
            if kind == "html":
                data, code, ctype = b"<html><body>Sign in to the proxy</body></html>", 200, "text/html"
            elif kind == "auth":
                data, code, ctype = b'{"error":"unauthorized"}', 401, "application/json"
            else:
                data, code, ctype = b"", 302, "text/plain"
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            if kind == "redirect":
                self.send_header("Location", "http://127.0.0.1:9/login")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        do_GET = do_POST = do_DELETE = _go
    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


class Stubs:
    """Three servers that answer, not as Ollama does, as ollama.hosts entries of a state dir of their own."""

    def __enter__(self):
        self.servers = {k: _stub(k) for k in ("html", "auth", "redirect")}
        self.saved = os.environ.get("BRIDGE_STATE_DIR")
        self.state = tempfile.mkdtemp(prefix="r8-answers-")
        os.environ["BRIDGE_STATE_DIR"] = self.state
        from halo_harness.providers.ollama import reset_catalog_cache, reset_ollama_version_cache
        reset_catalog_cache()
        reset_ollama_version_cache()
        Path(self.state, "config.json").write_text(json.dumps({"ollama": {"hosts": [
            {"name": k, "url": f"http://127.0.0.1:{s.server_address[1]}", "max_ctx": 65536}
            for k, s in self.servers.items()]}}), encoding="utf-8")
        return self

    def __exit__(self, *exc):
        for s in self.servers.values():
            s.shutdown()
        if self.saved is None:
            os.environ.pop("BRIDGE_STATE_DIR", None)
        else:
            os.environ["BRIDGE_STATE_DIR"] = self.saved


WHAT = {"html": "not Ollama's JSON", "auth": "HTTP 401", "redirect": "HTTP 302"}
NEVER = ("nothing is loaded", "nothing to do", "did not answer", "HTTP None", "nothing loaded")


@test
def test_every_verb_names_what_a_non_ollama_answer_was_and_reports_nothing_from_it(ctx: Ctx):
    with Stubs():
        for kind in ("html", "auth", "redirect"):
            for args in (["unload", "--all"], ["unload", "qwen3:8b"], ["ps"], ["warm", "qwen3:8b"], ["pull", "qwen3:8b"]):
                rc, out, err = _cli([*args, "--host", kind])
                text = (out + err).strip()
                ctx.check(f"{kind} local {' '.join(args)}: exit 1 (refused / unreadable), got {rc}: {text[-200:]!r}",
                          rc == 1)
                ctx.check(f"{kind} local {' '.join(args)}: says what came back ({WHAT[kind]!r}), got {text[-200:]!r}",
                          WHAT[kind] in text)
                bad = [w for w in NEVER if w in text]
                ctx.check(f"{kind} local {' '.join(args)}: never {bad}, got {text[-200:]!r}", not bad)


def _host(name: str):
    from halo_harness.providers.ollama import resolve_ollama_host
    return resolve_ollama_host(name)


@test
def test_a_measurement_puts_a_loaded_model_back_at_its_window(ctx: Ctx):
    with Rig() as r:
        r.box.preload(TINY, 16384)
        rc, out, err = _cli(["measure", TINY, "--host", "gpu-box"])
        ctx.check(f"measured, exit 0, got {rc} {out + err!r}", rc == 0)
        ctx.check(f"it measured (loads at other windows), got {len(r.box.calibrates)}", len(r.box.calibrates) >= 1)
        res = r.box.resident.get(TINY) or {}
        ctx.check(f"{TINY} is back at 16,384 with the server's own layers, got {res}",
                  res.get("num_ctx") == 16384 and res.get("num_gpu") is None)
        ctx.check(f"the report says so, got {out!r}", "back at 16,384" in out and "as it found it" in out)


@test
def test_a_measurement_unloads_a_model_that_was_not_loaded(ctx: Ctx):
    with Rig() as r:
        rc, out, err = _cli(["measure", TINY, "--host", "gpu-box"])
        ctx.check(f"measured, exit 0, got {rc} {out + err!r}", rc == 0)
        ctx.check(f"{TINY} is not left on the card, got {r.box.resident}", TINY not in r.box.resident)
        ctx.check(f"the report says it unloaded it, got {out!r}", "unloaded (it was not loaded before)" in out)


@test
def test_a_second_measurement_on_the_same_server_is_refused_with_a_line(ctx: Ctx):
    from halo_harness.config.paths import bridge_home
    from halo_harness.providers.ollama_measure_guard import measuring
    with Rig() as r:
        with measuring(_host("gpu-box"), "big:27b", bridge_home()) as first:
            ctx.check(f"the first measurement holds the server, got {first.say!r}", first.ok)
            rc, out, err = _cli(["measure", TINY, "--host", "gpu-box"])
            ctx.check(f"the second is refused: exit 1, got {rc} {out + err!r}", rc == 1)
            ctx.check(f"with a line naming the one running, got {err!r}",
                      "running already" in err and "big:27b" in err)
            ctx.check(f"and loads nothing, got {r.box.calibrates} {r.box.loads}", not r.box.calibrates)
        rc, out, err = _cli(["measure", TINY, "--host", "gpu-box"])
        ctx.check(f"once the first ends, it runs, got {rc} {err!r}", rc == 0 and r.box.calibrates)


@test
def test_discover_measure_never_steps_above_the_hosts_max_ctx(ctx: Ctx):
    from halo_harness.providers.ollama_discover_measure import measure_models
    box = LoadCountingOllama({TINY: {"size_gb": 1.0, "trained": 262144}}).start()
    saved = os.environ.get("BRIDGE_STATE_DIR")
    state = tempfile.mkdtemp(prefix="r8-discover-")
    os.environ["BRIDGE_STATE_DIR"] = state
    try:
        from halo_harness.providers.ollama import reset_catalog_cache, reset_ollama_version_cache
        reset_catalog_cache()
        reset_ollama_version_cache()
        Path(state, "config.json").write_text(json.dumps({"ollama": {"hosts": [
            {"name": "gpu-box", "url": box.base_url, "max_ctx": 16384}]}}), encoding="utf-8")
        rows = measure_models(_host("gpu-box"), [TINY], timeout=20, state_dir=state)
        steps = [c["num_ctx"] for c in box.calibrates]
        ctx.check(f"it measured, got {rows}", bool(steps))
        ctx.check(f"never a step above max_ctx 16,384, got {steps}", steps and max(steps) <= 16384)
        ctx.check(f"and the line says what it left, got {rows}", bool(rows) and "as it found it" in rows[0]["line"])
    finally:
        box.stop()
        if saved is None:
            os.environ.pop("BRIDGE_STATE_DIR", None)
        else:
            os.environ["BRIDGE_STATE_DIR"] = saved


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
