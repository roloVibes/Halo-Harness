"""tests.test_studio_api -- `halo studio`'s server and routes (Halo 2.1.0
round B3): an in-process server on a random port over a scoped home; the
loopback/token/origin guard; every read route; create, save, validate (422
with the validator's lines), 409 on a shipped file, layout persistence,
apply (writes the same config `halo teams use` does), delete; the static
page and its security headers.
"""

from __future__ import annotations

import io
import json
import os
import socket
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


class _Studio:
    """A Studio over a state dir of its own: `BRIDGE_STATE_DIR` points at a
    fresh folder for the fixture's lifetime (and is put back after), so an
    earlier module's copy-on-first-use of the shipped lineups into the shared
    scratch home can never turn a shipped lineup into a user one here."""

    def __enter__(self):
        from halo_harness.studio.server import start_server
        self._saved = os.environ.get("BRIDGE_STATE_DIR")
        root = Path(tempfile.mkdtemp(prefix="studio-api-"))
        self.state = root / ".halo"
        self.state.mkdir()
        os.environ["BRIDGE_STATE_DIR"] = str(self.state)
        self.srv = start_server(port=0, cwd=self.state.parent / "proj", state_dir=self.state)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.srv.server_address[1]}"
        return self

    def __exit__(self, *a):
        self.srv.shutdown()
        self.srv.server_close()
        if self._saved is None:
            os.environ.pop("BRIDGE_STATE_DIR", None)
        else:
            os.environ["BRIDGE_STATE_DIR"] = self._saved

    def call(self, method, path, body=None, *, token=None, origin=None, raw=False, owner=True):
        req = urllib.request.Request(self.base + path, method=method,
                                     data=json.dumps(body).encode() if body is not None else None)
        req.add_header("Authorization", "Bearer " + (self.srv.token if token is None else token))
        if owner:  # 3.4.1.2: as the owner's own page asks (studio/owner_proof.py)
            from halo_harness.studio.owner_proof import HEADER, header_for
            req.add_header(HEADER, header_for(self.srv))
        if body is not None:
            req.add_header("Content-Type", "application/json")
        if origin:
            req.add_header("Origin", origin)
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, (r.read() if raw else json.loads(r.read() or b"{}")), dict(r.headers)
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}"), dict(e.headers)


@test
def test_guard_token_origin_and_static(ctx: Ctx):
    with _Studio() as s:
        status, body, headers = s.call("GET", "/", raw=True)
        ctx.check("the page is served", status == 200 and b"<title>Halo Studio</title>" in body)
        ctx.check("the page carries a content-security policy and nosniff",
                  "default-src 'self'" in headers.get("Content-Security-Policy", "") and headers.get("X-Content-Type-Options") == "nosniff")
        ctx.check("every file the page names is served (3.0.7.0 R2: the shell's build only)",
                  all(s.call("GET", "/" + f, raw=True)[0] == 200 for f in ("studio.css", "studio.js")))
        ctx.check("the classic page is gone", s.call("GET", "/legacy/index.html", raw=True)[0] == 404 and s.call("GET", "/app.js", raw=True)[0] == 404)
        ctx.check("a path outside static is refused", s.call("GET", "/../server.py", raw=True)[0] == 404)
        ctx.check("no token is a 401", s.call("GET", "/api/models", token="")[0] == 401)
        ctx.check("a wrong token is a 401", s.call("GET", "/api/models", token="nope")[0] == 401)
        ctx.check("a foreign origin is a 403", s.call("GET", "/api/models", origin="http://evil.example")[0] == 403)
        ctx.check("the server's own origin passes", s.call("GET", "/api/models", origin=s.base)[0] == 200)
        ctx.check("an unknown route is a 404", s.call("GET", "/api/nope")[0] == 404)
        ctx.check("a wrong method is a 405", s.call("DELETE", "/api/models")[0] == 405)


@test
def test_read_routes_and_the_latency_flag(ctx: Ctx):
    """3.6.0.0 R5: the lineup, bio, state, session, tools, validate and yaml routes went with Cast (the crew routes are
    tests/test_crew_*); what is left here: the catalog, field help, a pack canvas's layout, the latency flag."""
    with _Studio() as s:
        ctx.check("models answers a list (empty on a bare home)", s.call("GET", "/api/models")[0] == 200)
        from halo_harness import field_help  # 3.1.1.0 R3: the form's help lines, one source
        ctx.check("field-help answers field_help.py's lines", s.call("GET", "/api/field-help")[1] == field_help.as_json())
        for gone in ("/api/state", "/api/lineups", "/api/bios", "/api/session", "/api/tools"):
            ctx.check(f"{gone} went with Cast: a 404", s.call("GET", gone)[0] == 404)
        ctx.check("a pack canvas's layout reads", s.call("GET", "/api/layout/design:demo")[0] == 200)
        s.srv.slow_ms, t0 = 300, time.monotonic()  # the latency flag (HALO_STUDIO_SLOW_MS): every answer that late
        # 0.25, not 0.3: Windows' sleep can wake a few ms early against time.monotonic (0.297 s seen on this box)
        ctx.check("with the latency flag an answer comes 300 ms late", s.call("GET", "/api/models")[0] == 200 and time.monotonic() - t0 >= 0.25)
        s.srv.slow_ms = 0


@test
def test_models_status_and_refresh(ctx: Ctx):
    # 3.0.4.0: the bio form's model dropdown explains an empty catalog and can refresh it.
    with _Studio() as s:
        status, st, _ = s.call("GET", "/api/models/status")
        ctx.check("models/status answers rows, providers and a reason when the catalog is empty",
                  status == 200 and isinstance(st["rows"], int) and isinstance(st["providers"], list) and (st["rows"] > 0 or bool(st["reason"])))
        from halo_harness.studio import models_refresh as MR  # 3.1.4.0 R4: no provider is asked here (a stand-in answers)
        keep = MR.jobs_for
        MR.jobs_for = lambda state_dir, env, local=True: [("Stand-in", "openrouter", lambda sd, e: (False, None, "HTTP 401 (the key was refused)"))]
        try:
            status, r, _ = s.call("POST", "/api/models/refresh?no_probe=1", {})
        finally:
            MR.jobs_for = keep
        ctx.check("models/refresh answers the row count and one line per attempt",
                  status == 200 and isinstance(r["rows"], int) and r["attempts"] == ["Stand-in: HTTP 401 (the key was refused)"])
        st = s.call("GET", "/api/models/status")[1]
        ctx.check("3.1.4.0 R4: status names every provider it looked at (seven: TypeSafe left in 3.4.0.0), and when the last refresh ran",
                  len(st["looked_at"]) >= 7 and st["refreshed_at"] and st["outcomes"][0]["line"] == "HTTP 401 (the key was refused)")
        ctx.check("3.1.5.0 R1: no subscription provider is looked at",
                  not [p for p in st["looked_at"] if "subscription" in str(p.get("label", "")).lower()])
        status, gym, _ = s.call("GET", "/api/gym")
        ctx.check("3.0.7.0 R2: GET gym answers the gym's scores (none on a bare home)", status == 200 and gym == {"scores": {}})
        status, best, _ = s.call("GET", "/api/models/best-for")
        ctx.check("3.0.7.0 R2: GET models/best-for answers a ref -> kinds mapping", status == 200 and isinstance(best, dict))


@test
def test_a_browser_that_goes_away_mid_answer_leaves_no_traceback(ctx: Ctx):
    """bd9b607's tag run (Windows): a handler thread's write to a client that had closed raised
    ConnectionAbortedError, the server printed the traceback to stderr from that daemon thread while the
    interpreter was finalizing, and the Chrome driver died with a fatal error. A client that went away is
    quiet (`_Server.handle_error`); every other error prints as before."""
    with _Studio() as s:
        status, body, _h = s.call("GET", "/studio.js", raw=True)
        ctx.check(f"the shell's script answers in full, got {status} {len(body)} bytes", status == 200 and len(body) > 500_000)
        port = s.srv.server_address[1]
        err, saved = io.StringIO(), sys.stderr
        sys.stderr = err
        try:
            for _ in range(3):
                sock = socket.create_connection(("127.0.0.1", port), timeout=5)
                sock.sendall(f"GET /studio.js HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n\r\n".encode())
                sock.recv(1)  # the answer has started
                sock.close()  # and the client is gone before the body is through
            time.sleep(1.0)
        finally:
            sys.stderr = saved
    ctx.check(f"nothing on stderr, got {err.getvalue()[-300:]!r}", "Traceback" not in err.getvalue())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="studio api tests"))
