"""tests.test_security_round3d -- 2.0.10 round 3, security fix pass 1, the
credential findings 18-20 of docs/harness/SECURITY-REVIEW-2.0.10.md
(section D).

18  a redirect to another origin drops Authorization and user headers
19  signal-cli and `${VAR}` expansion get the secret-stripped environment
20  secret files are private from birth; the settings mode is kept
"""
from __future__ import annotations

import contextlib
import json
import logging
import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()

os.environ.setdefault("BRIDGE_TEST_HOME", tempfile.mkdtemp(prefix="halo-sec3c-home-"))

OR_KEY = "sk-" + "or-v1-" + "0123456789abcdef0123456789abcdef"  # fake, built at run time


@contextlib.contextmanager
def _env(**values):
    saved = {k: os.environ.get(k) for k in values}
    try:
        for k, v in values.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# ---- 18: redirects ----------------------------------------------------------


class _Sink:
    def __init__(self, redirect_to: str | None = None):
        self.seen: list = []
        outer = self

        class H(BaseHTTPRequestHandler):
            def do_GET(self):
                outer.seen.append({k.lower(): v for k, v in self.headers.items()})
                if redirect_to and self.path == "/start":
                    self.send_response(302)
                    self.send_header("Location", redirect_to())
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                body = b"ok"
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        self.httpd = HTTPServer(("127.0.0.1", 0), H)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def _get_with_credentials(first: _Sink, path: str = "/start"):
    import urllib.request
    from halo_harness.providers.http import urlopen_tls
    req = urllib.request.Request(f"http://127.0.0.1:{first.port}{path}", headers={
        "Authorization": "fake-auth-header-value", "x-api-key": "fake-api-key-value",
        "X-Custom-Secret": "fake-custom-value", "Accept": "application/json"})
    with urlopen_tls(req, timeout=5) as resp:
        return resp.read()


@test
def test_f18_cross_host_redirect_drops_credentials(ctx: Ctx):
    target = _Sink()
    first = _Sink(redirect_to=lambda: f"http://localhost:{target.port}/landed")
    try:
        _get_with_credentials(first)
        ctx.check("the first hop got the credentials", first.seen[0].get("authorization") == "fake-auth-header-value")
        landed = target.seen[0]
        ctx.check(f"Authorization not forwarded, got {sorted(landed)}", "authorization" not in landed)
        ctx.check("x-api-key not forwarded", "x-api-key" not in landed)
        ctx.check("user-supplied header not forwarded", "x-custom-secret" not in landed)
        ctx.check("plain transport headers survive", landed.get("accept") == "application/json")
    finally:
        first.close()
        target.close()


@test
def test_f18_same_origin_redirect_keeps_credentials(ctx: Ctx):
    first = _Sink(redirect_to=lambda: f"http://127.0.0.1:{first.port}/landed")
    try:
        _get_with_credentials(first)
        ctx.check("same-origin hop keeps Authorization", first.seen[-1].get("authorization") == "fake-auth-header-value")
    finally:
        first.close()


# ---- 19: the secret-stripping environment ---------------------------------------------


@test
def test_f19_signal_cli_gets_the_stripped_environment(ctx: Ctx):
    import subprocess
    from halo_harness.remote import cli_common, signal_link
    with _env(OPENROUTER_API_KEY=OR_KEY, SAFE_VAR_R3="kept"):
        captured: dict = {}
        real_run = subprocess.run
        subprocess.run = lambda argv, **kw: captured.update(kw) or subprocess.CompletedProcess(argv, 0, "", "")
        try:
            cli_common.run_cli({"binary": "signal-cli", "data_dir": tempfile.mkdtemp(prefix="halo-sig-")}, "listAccounts")
        finally:
            subprocess.run = real_run
        env = captured.get("env") or {}
        ctx.check("run_cli passes an explicit env", bool(env))
        ctx.check("provider key stripped from run_cli", "OPENROUTER_API_KEY" not in env)
        ctx.check("ordinary variables kept", env.get("SAFE_VAR_R3") == "kept")
        spawned: dict = {}

        class _P:
            stdout = stdin = None

        signal_link.open_link({"binary": "signal-cli", "data_dir": tempfile.mkdtemp(prefix="halo-sig-"), "account": "+10000000000"},
                              popen=lambda argv, **kw: spawned.update(kw) or _P())
        ctx.check("open_link strips the provider key", "OPENROUTER_API_KEY" not in (spawned.get("env") or {"OPENROUTER_API_KEY": 1}))


@test
def test_f19_mcp_json_var_expansion_uses_the_stripped_env(ctx: Ctx):
    from halo_harness.config.settings import Settings
    from halo_harness.mcp import available
    from halo_harness.mcp_setup import build_manager
    if not available():
        ctx.check("mcp package missing: nothing to expand", True)
        return
    cwd = Path(tempfile.mkdtemp(prefix="halo-sec3c-repo-"))
    (cwd / ".mcp.json").write_text(json.dumps({"mcpServers": {"srv": {"command": "x", "env": {
        "K": "${OPENROUTER_API_KEY}", "OK": "${SAFE_VAR_R3}"}}}}), encoding="utf-8")
    with _env(OPENROUTER_API_KEY=OR_KEY, SAFE_VAR_R3="kept"):
        manager, _n = build_manager(cwd=cwd, claude_json={}, settings=Settings(raw={}, layers=[], errors=[]),
                                    print_mode=True, start=False)
    env = manager.handles["srv"].config.env
    ctx.check(f"provider key not expanded into the server env, got {env}", OR_KEY not in json.dumps(env))
    ctx.check("an ordinary variable still expands", env.get("OK") == "kept")


@test
def test_f19_mcp_list_does_not_print_a_token_in_the_url(ctx: Ctx):
    from halo_harness.mcp_cli import format_mcp_list_line
    line = format_mcp_list_line({"name": "r", "type": "http", "url": "https://h.example.com/mcp?token=abc123secret",
                                 "state": "connected"})
    ctx.check(f"query string not shown, got {line!r}", "abc123secret" not in line and "h.example.com/mcp" in line)


# ---- 20: secret files ---------------------------------------------------------------------


@test
def test_f20_secret_files_go_through_the_private_writer(ctx: Ctx):
    from halo_harness import privateio, theme
    from halo_harness.mcp import oauth
    from halo_harness.permissions import add_allow_rule
    from halo_harness.providers.config import ensure_token
    calls: list = []
    real = privateio.write_private_atomic
    privateio.write_private_atomic = lambda path, data: calls.append(Path(path).name) or real(path, data)
    try:
        home = tempfile.mkdtemp(prefix="halo-sec3c-home-")
        with _env(BRIDGE_TEST_HOME=home, CLAUDE_CONFIG_DIR=tempfile.mkdtemp(prefix="halo-sec3c-claude-")):
            oauth.save_tokens("srv", {"access_token": "fake"})
            tok = ensure_token(Path(home) / "state")
            theme.set_config_value("some.key", "v")
            add_allow_rule("Bash(ls:*)", "user", cwd=Path(home))
    finally:
        privateio.write_private_atomic = real
    ctx.check(f"oauth tokens written privately, calls={calls}", "srv.json" in calls)
    ctx.check("proxy token written privately", "token" in calls and bool(tok))
    ctx.check("config.json written privately", "config.json" in calls)
    ctx.check("settings.json written privately", "settings.json" in calls)


@test
def test_f20_add_allow_rule_keeps_the_file_mode(ctx: Ctx):
    if os.name == "nt":
        ctx.check("no POSIX mode bits on Windows", True)
        return
    from halo_harness.permissions import add_allow_rule
    cwd = Path(tempfile.mkdtemp(prefix="halo-sec3c-proj-"))
    (cwd / ".claude").mkdir()
    path = cwd / ".claude" / "settings.json"
    path.write_text('{"env": {"X": "y"}}', encoding="utf-8")
    os.chmod(path, 0o600)
    add_allow_rule("Bash(ls:*)", "project", cwd=cwd)
    ctx.check(f"0600 stays 0600, got {oct(path.stat().st_mode & 0o777)}", path.stat().st_mode & 0o777 == 0o600)
    ctx.check("the rule was added", "Bash(ls:*)" in path.read_text(encoding="utf-8"))
    os.chmod(path, 0o640)
    add_allow_rule("Bash(pwd:*)", "project", cwd=cwd)
    ctx.check("another mode is kept too", path.stat().st_mode & 0o777 == 0o640)


@test
def test_f20_proxy_token_compare_is_constant_time_and_keeps_semantics(ctx: Ctx):
    import bridge
    real = bridge.SERVER_TOKEN
    try:
        bridge.SERVER_TOKEN = "right-token-value"
        ctx.check("matching token accepted", bridge._token_ok("right-token-value"))
        ctx.check("wrong token rejected", not bridge._token_ok("wrong-token-value"))
        ctx.check("missing token rejected", not bridge._token_ok(None))
        ctx.check("non-ASCII token does not raise", not bridge._token_ok("tokén"))
    finally:
        bridge.SERVER_TOKEN = real


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
