"""tests.test_http_bind -- Halo 3.6.0.0 (fix package http-servers): no HTTP server Halo starts asks a name service
anything between bind() and listen(). The standard library's `http.server.HTTPServer.server_bind` ends in
`self.server_name = socket.getfqdn(host)`, a reverse name lookup of the address it bound; where the resolver is slow
for that question (the hosted macOS CI runner: about 35 s; VPN and managed-DNS machines) Studio printed its address
35 s late, `halo init` gave up on Studio after 15 s and the bridge, the fake llama-server and the pool's fakes were
"not up in time". Every server binds through `halo_harness/http_bind.py` (`bind_no_lookup`) instead.

1. each server class of the product (Studio, `halo host serve`, the voice server, bridge.py, the MCP OAuth callback,
   the Copilot sign-in callback) is built on a loopback port while socket.getfqdn / gethostbyaddr / gethostbyname_ex
   raise: nothing asks, the constructor returns at once and the port already accepts a connection;
2. the same for the stand-ins in tests/helpers (in process) and a fresh-process fake llama-server answering within
   a few seconds while the lookup would take 30 s;
3. a source sweep: no module of the product or of tests/helpers builds a stdlib HTTP server (or subclasses one)
   without binding through `bind_no_lookup`, so a new server cannot bring the lookup back.
Run: python -m tests.test_http_bind
"""
from __future__ import annotations

import http.server
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

ensure_scoped_state_dir_once()
test, TESTS = new_registry()

LOOKUPS = ("getfqdn", "gethostbyaddr", "gethostbyname_ex")
BOUND_S = 2.0  # a bind that does no lookup takes milliseconds; a slow box still well under this


class _Ok(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        self.send_response(200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *_a):
        pass


@contextmanager
def _no_name_service():
    """socket's name lookups record their argument and raise (socket.gaierror, an OSError, as a dead resolver
    would); yields the list of what was asked."""
    asked: list = []
    saved = {n: getattr(socket, n) for n in LOOKUPS}

    def make(name):
        def refuse(*a, **_k):
            asked.append((name, a[0] if a else None))
            raise socket.gaierror(f"{name} was asked at bind (tests/test_http_bind.py)")
        return refuse
    for n in LOOKUPS:
        setattr(socket, n, make(n))
    try:
        yield asked
    finally:
        for n, f in saved.items():
            setattr(socket, n, f)


def _accepts(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1.0):
            return True
    except OSError:
        return False


def _bridge_module():
    import importlib
    return importlib.import_module("bridge")


def _builders() -> dict:
    """name -> a callable that builds the server on 127.0.0.1:0 and returns it (bound, listening, not serving)."""
    from halo_harness.host import service
    from halo_harness.studio import server as studio
    from halo_harness.voice import server as voice
    home = Path(tempfile.mkdtemp(prefix="http-bind-"))
    return {
        "Studio (studio/server.py _Server)": lambda: studio._Server(
            ("127.0.0.1", 0), studio.Handler, token="t", cwd=home, state_dir=home),
        "halo host serve (host/service.py _Server)": lambda: service._Server(("127.0.0.1", 0), None, None),
        "the voice server (voice/server.py _Http)": lambda: voice._Http(("127.0.0.1", 0), _Ok),
        "bridge.py _Server": lambda: _bridge_module()._Server(("127.0.0.1", 0), _Ok),
    }


@test
def test_each_product_server_binds_without_a_name_lookup(ctx: Ctx):
    for name, build in _builders().items():
        with _no_name_service() as asked:
            t0 = time.monotonic()
            try:
                srv = build()
                err = None
            except Exception as e:  # noqa: BLE001 (the stdlib's bind raises the lookup's own error)
                srv, err = None, f"{type(e).__name__}: {e}"
            took = time.monotonic() - t0
        ctx.check(f"{name}: built with no name lookup, got error={err} asked={asked}", srv is not None and not asked)
        if srv is None:
            continue
        try:
            port = srv.server_address[1]
            ctx.check(f"{name}: built in {took:.2f} s (< {BOUND_S} s)", took < BOUND_S)
            ctx.check(f"{name}: port {port} accepts a connection right after the constructor", _accepts(port))
            ctx.check(f"{name}: server_name is the bound address, got {srv.server_name!r}",
                      srv.server_name == "127.0.0.1" and srv.server_port == port)
        finally:
            srv.server_close()


@test
def test_studio_start_server_asks_no_name_service(ctx: Ctx):
    """The whole of Studio's start (the bind, the files watch, the steward's switch, the Local tap), not the class
    alone: nothing in it may wait on a resolver before `halo studio` can print its address."""
    from halo_harness.studio.server import start_server
    home = Path(tempfile.mkdtemp(prefix="http-bind-studio-"))
    (home / "proj").mkdir()
    (home / "state").mkdir()
    with _no_name_service() as asked:
        t0 = time.monotonic()
        srv = start_server(port=0, cwd=home / "proj", state_dir=home / "state")
        took = time.monotonic() - t0
    try:
        port = srv.server_address[1]
        ctx.check(f"start_server asked no name service, got {asked}", not asked)
        ctx.check(f"start_server returned in {took:.2f} s (< {BOUND_S} s)", took < BOUND_S)
        ctx.check(f"port {port} accepts a connection", _accepts(port))
    finally:
        srv.server_close()


@test
def test_the_mcp_oauth_callback_binds_without_a_name_lookup(ctx: Ctx):
    from halo_harness.mcp import oauth
    abort = threading.Event()
    abort.set()  # the flow binds, prints the URL, then sees the abort at once: nothing leaves this machine
    lines: list = []
    raised: list = []
    saved_hook = threading.excepthook
    threading.excepthook = lambda a: raised.append(f"{a.thread.name if a.thread else '?'}: {a.exc_type.__name__}: {a.exc_value}")
    cfg = {"authorization_endpoint": "http://127.0.0.1:9/authorize", "token_endpoint": "http://127.0.0.1:9/token"}
    with _no_name_service() as asked:
        t0 = time.monotonic()
        tokens, err = oauth.run_authorization_flow(server_name="gpu-box-docs", server_url="http://127.0.0.1:9/mcp",
                                                   oauth_cfg=cfg, callback_timeout=5, open_browser=False,
                                                   print_fn=lines.append, abort=abort)
        took = time.monotonic() - t0
    time.sleep(1.0)  # the callback thread's last handle_request() returns on the closed socket
    threading.excepthook = saved_hook
    ctx.check(f"the callback port opened (the flow reached the abort), got {err!r}", err == "login cancelled")
    ctx.check(f"no name lookup was asked, got {asked}", not asked)
    ctx.check(f"it took {took:.2f} s (< {BOUND_S} s)", took < BOUND_S)
    ctx.check(f"the callback thread ended quietly when the port closed under it, got {raised}", not raised)


@test
def test_the_copilot_callback_binds_without_a_name_lookup(ctx: Ctx):
    from halo_harness.providers import copilot_auth
    with _no_name_service() as asked:
        t0 = time.monotonic()
        try:
            lb = copilot_auth.Loopback()
            err = None
        except Exception as e:  # noqa: BLE001
            lb, err = None, f"{type(e).__name__}: {e}"
        took = time.monotonic() - t0
    ctx.check(f"the Copilot loopback built with no name lookup, got error={err} asked={asked}", lb is not None and not asked)
    if lb is None:
        return
    try:
        ctx.check(f"built in {took:.2f} s (< {BOUND_S} s)", took < BOUND_S)
        ctx.check(f"port {lb.port} accepts a connection", _accepts(lb.port))
    finally:
        lb.close()


def _helper_builders() -> dict:
    from tests.helpers import mock_anthropic, mock_get_endpoints, mock_ollama, mock_openai
    return {
        "tests/helpers/mock_openai.py MockUpstream": mock_openai.MockUpstream,
        "tests/helpers/mock_anthropic.py MockAnthropic": mock_anthropic.MockAnthropic,
        "tests/helpers/mock_ollama.py MockUpstream": mock_ollama.MockUpstream,
        "tests/helpers/mock_get_endpoints.py MockGetEndpoints": lambda: mock_get_endpoints.MockGetEndpoints({}),
    }


@test
def test_the_in_process_test_fakes_bind_without_a_name_lookup(ctx: Ctx):
    for name, cls in _helper_builders().items():
        with _no_name_service() as asked:
            try:
                fake = cls()
                fake.start()
                err = None
            except Exception as e:  # noqa: BLE001
                fake, err = None, f"{type(e).__name__}: {e}"
        ctx.check(f"{name}: started with no name lookup, got error={err} asked={asked}", fake is not None and not asked)
        if fake is not None:
            fake.stop()


_SLOW_LOOKUP = """
import os, socket, sys, time, runpy
def slow(*a, **k):
    time.sleep(30)
    raise socket.gaierror("slow resolver")
socket.getfqdn = socket.gethostbyaddr = slow
sys.argv = sys.argv[1:]
sys.path.insert(0, os.path.dirname(os.path.abspath(sys.argv[0])))  # as `python <script>` would
runpy.run_path(sys.argv[0], run_name="__main__")
"""


@test
def test_a_fresh_fake_llama_server_answers_while_the_resolver_would_take_30_s(ctx: Ctx):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    tmp = Path(tempfile.mkdtemp(prefix="http-bind-llama-"))
    shim = tmp / "slow_resolver.py"
    shim.write_text(_SLOW_LOOKUP, encoding="utf-8")
    helper = ROOT / "tests" / "helpers" / "fake_llama_server.py"
    env = dict(os.environ, FAKE_LLAMA_LOAD_S="0.1")
    proc = subprocess.Popen([sys.executable, str(shim), str(helper), "-m", "fake.gguf", "--alias", "gpu-box-model",
                             "-c", "2048", "--port", str(port), "--host", "127.0.0.1"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
    try:
        t0, body = time.monotonic(), None
        while time.monotonic() - t0 < 10 and body is None:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/v1/models", timeout=1) as r:
                    body = r.read()
            except OSError:
                time.sleep(0.1)
        took = time.monotonic() - t0
        ctx.check(f"/v1/models answered in {took:.1f} s (< 10 s; the resolver would have taken 30 s)",
                  body is not None and b"gpu-box-model" in body)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)


_STDLIB_SERVER = re.compile(r"\b(?:Threading)?HTTPServer\b|\bTCPServer\b")
_STDLIB_IMPORT = re.compile(r"^\s*(?:from\s+(?:http\.server|socketserver)\s+import\s+[^\n]*\b(?:Threading)?HTTPServer\b"
                            r"|from\s+socketserver\s+import\s+[^\n]*\bTCPServer\b)", re.M)
_STDLIB_ATTR = re.compile(r"\b(?:http\.server\.(?:Threading)?HTTPServer|socketserver\.TCPServer)\b")


def _swept() -> list:
    files = [ROOT / "bridge.py", *sorted((ROOT / "halo_harness").rglob("*.py")),
             *sorted((ROOT / "tests" / "helpers").rglob("*.py"))]
    return [f for f in files if f.name != "http_bind.py"]


def _offences(text: str) -> list:
    """What in a module builds or subclasses a stdlib HTTP server without `bind_no_lookup`: every stdlib import of a
    server class, and every `http.server.X` / `socketserver.TCPServer` used other than as a base class whose own
    server_bind binds through bind_no_lookup (or as a plain unbound call such as `X.server_close(srv)`)."""
    out = [m.group(0).strip() for m in _STDLIB_IMPORT.finditer(text)]
    for m in _STDLIB_ATTR.finditer(text):
        line = text[text.rfind("\n", 0, m.start()) + 1:text.find("\n", m.end())]
        after = text[m.end():m.end() + 1]
        if after == ".":  # an unbound method call (http.server.ThreadingHTTPServer.server_close(srv)): no bind
            continue
        if line.lstrip().startswith("class "):
            body = text[m.end():]
            nxt = re.search(r"^\S", body[body.find("\n") + 1:], re.M)
            block = body[:body.find("\n") + 1 + (nxt.start() if nxt else len(body))]
            if re.search(r"def server_bind\(self\)[^\n]*\n(?:[^\n]*\n)*?[^\n]*bind_no_lookup\(self\)", block):
                continue
        if line.lstrip().startswith(("#", '"', "'")):
            continue
        out.append(line.strip())
    return out


@test
def test_no_module_builds_a_stdlib_http_server_that_looks_up_a_name(ctx: Ctx):
    bad = {}
    for f in _swept():
        text = f.read_text(encoding="utf-8", errors="replace")
        if not _STDLIB_SERVER.search(text):
            continue
        hits = _offences(text)
        if hits:
            bad[str(f.relative_to(ROOT)).replace("\\", "/")] = hits
    ctx.check(f"every HTTP server binds through halo_harness/http_bind.py, offenders: {bad}", not bad)


@test
def test_the_sweep_sees_what_it_should(ctx: Ctx):
    ctx.check("a stdlib import is caught", _offences("from http.server import BaseHTTPRequestHandler, HTTPServer\n"))
    ctx.check("a direct build is caught", _offences("import http.server\nsrv = http.server.ThreadingHTTPServer(a, H)\n"))
    ctx.check("a subclass that keeps the stdlib bind is caught", _offences(
        "class S(http.server.ThreadingHTTPServer):\n    def server_bind(self):\n        super().server_bind()\n"))
    ctx.check("a subclass binding through bind_no_lookup passes", not _offences(
        "class S(http.server.ThreadingHTTPServer):\n    def server_bind(self):\n        x()\n        bind_no_lookup(self)\n"))
    ctx.check("an unbound server_close call passes", not _offences("http.server.ThreadingHTTPServer.server_close(srv)\n"))
    ctx.check("the quick classes pass", not _offences("from halo_harness.http_bind import HTTPServer, ThreadingHTTPServer\n"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
