"""tests.test_security_round3 -- 2.0.10 round 3, security fix pass 1, the
trust-boundary findings 6-8 of docs/harness/SECURITY-REVIEW-2.0.10.md
(section B). Findings 9-10 are pinned in tests/test_security_round3b.py and
the credential findings 17-20 in tests/test_security_round3c.py.

6   an untrusted repo cannot approve its own `.mcp.json` servers
7   a project `statusLine` command does not survive an untrusted folder
8   OAuth endpoints are https (or loopback http) only; the token endpoint
    is pinned at login and used for refresh
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()

os.environ.setdefault("BRIDGE_TEST_HOME", tempfile.mkdtemp(prefix="halo-sec3-home-"))


@contextlib.contextmanager
def _env(**values):
    """Set/clear env vars for one block (None clears), restoring every one."""
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


def _repo(project_settings: dict | None = None, mcp: dict | None = None) -> Path:
    cwd = Path(tempfile.mkdtemp(prefix="halo-sec3-repo-"))
    if project_settings is not None:
        (cwd / ".claude").mkdir()
        (cwd / ".claude" / "settings.json").write_text(json.dumps(project_settings), encoding="utf-8")
    if mcp is not None:
        (cwd / ".mcp.json").write_text(json.dumps({"mcpServers": mcp}), encoding="utf-8")
    return cwd


# ---- 6: an untrusted repo approves its own .mcp.json servers ---------------


@test
def test_f6_untrusted_project_settings_cannot_enable_mcp_servers(ctx: Ctx):
    from halo_harness.config.settings import resolve_settings
    cwd = _repo({"enableAllProjectMcpServers": True, "enabledMcpjsonServers": ["evil"],
                 "disabledMcpjsonServers": ["noisy"]})
    claude_dir = tempfile.mkdtemp(prefix="halo-sec3-claude-")
    with _env(CLAUDE_CONFIG_DIR=claude_dir):
        untrusted = resolve_settings(cwd, trusted=False)
        trusted = resolve_settings(cwd, trusted=True)
    ctx.check("untrusted: enableAllProjectMcpServers dropped",
              "enableAllProjectMcpServers" not in untrusted.raw)
    ctx.check("untrusted: enabledMcpjsonServers dropped", "enabledMcpjsonServers" not in untrusted.raw)
    ctx.check("untrusted: disabledMcpjsonServers (restrictive) kept",
              untrusted.raw.get("disabledMcpjsonServers") == ["noisy"])
    ctx.check("trusted: the project may enable its own servers",
              trusted.raw.get("enableAllProjectMcpServers") is True)


@test
def test_f6_untrusted_repo_mcp_json_stays_pending(ctx: Ctx):
    from halo_harness.config.settings import resolve_settings
    from halo_harness.mcp import manager as M
    cwd = _repo({"enableAllProjectMcpServers": True}, {"evil": {"command": "evil-cmd"}})
    claude_dir = tempfile.mkdtemp(prefix="halo-sec3-claude-")
    with _env(CLAUDE_CONFIG_DIR=claude_dir):
        settings = resolve_settings(cwd, trusted=False)
    resolved, _ = M.resolve_server_configs(cwd=cwd, claude_json={}, settings=settings, print_mode=False,
                                           trusted=False)
    ctx.check("settings-sourced enable-all from an untrusted repo does not approve",
              resolved["evil"].pending_approval is True)
    resolved, _ = M.resolve_server_configs(cwd=cwd, claude_json={}, settings=settings, print_mode=True,
                                           trusted=False)
    ctx.check("-p in an untrusted folder does not auto-approve", resolved["evil"].pending_approval is True)
    resolved, _ = M.resolve_server_configs(cwd=cwd, claude_json={}, settings=settings, print_mode=True,
                                           trusted=True)
    ctx.check("-p in a trusted folder still approves", resolved["evil"].pending_approval is False)
    key = M.mcp_approval_key({"command": "evil-cmd"})
    resolved, _ = M.resolve_server_configs(cwd=cwd, claude_json={}, settings=settings, print_mode=True,
                                           trusted=False, approvals={key: True})
    ctx.check("an explicit hash approval still works in an untrusted folder",
              resolved["evil"].pending_approval is False)
    user_json = {"projects": {str(cwd).replace("\\", "/"): {"enabledMcpjsonServers": ["evil"]}}}
    resolved, _ = M.resolve_server_configs(cwd=cwd, claude_json=user_json, settings=settings,
                                           print_mode=True, trusted=False)
    ctx.check("the user's own ~/.claude.json enabled list still approves",
              resolved["evil"].pending_approval is False)


# ---- 7: a project statusLine command runs in an untrusted folder -----------


@test
def test_f7_untrusted_project_statusline_and_helpers_dropped(ctx: Ctx):
    from halo_harness.config.settings import resolve_settings
    layer = {"statusLine": {"type": "command", "command": "echo pwned"}, "apiKeyHelper": "echo k",
             "otelHeadersHelper": "echo h", "env": {"A": "b"}}
    cwd = _repo(layer)
    claude_dir = Path(tempfile.mkdtemp(prefix="halo-sec3-claude-"))
    (claude_dir / "settings.json").write_text(json.dumps({"statusLine": {"type": "command", "command": "echo mine"}}),
                                              encoding="utf-8")
    with _env(CLAUDE_CONFIG_DIR=str(claude_dir)):
        untrusted = resolve_settings(cwd, trusted=False)
        trusted = resolve_settings(cwd, trusted=True)
    ctx.check("untrusted: the user's own statusLine is the one that survives",
              (untrusted.statusline or {}).get("command") == "echo mine")
    ctx.check("untrusted: apiKeyHelper/otelHeadersHelper dropped",
              "apiKeyHelper" not in untrusted.raw and "otelHeadersHelper" not in untrusted.raw)
    ctx.check("trusted: the project statusLine applies", (trusted.statusline or {}).get("command") == "echo pwned")
    with _env(CLAUDE_CONFIG_DIR=tempfile.mkdtemp(prefix="halo-sec3-claude-")):
        bare = resolve_settings(cwd, trusted=False)
    ctx.check("untrusted with no user layer: no statusLine at all", bare.statusline is None)


# ---- 8: OAuth endpoints ------------------------------------------------------


@test
def test_f8_endpoint_error_accepts_https_and_loopback_http_only(ctx: Ctx):
    from halo_harness.mcp import oauth
    ok = ["https://idp.example.com/authorize", "http://127.0.0.1:8123/token", "http://localhost/auth",
          "http://[::1]:9/t"]
    bad = ["file:///etc/passwd", "ms-settings:network", "javascript:alert(1)", "http://evil.example.com/token",
           "C:\\Windows\\System32\\calc.exe", "//evil.example.com/x", "https://", "", None,
           "https://ok.example.com/a b", "custom-scheme://x/y"]
    for url in ok:
        ctx.check(f"accepted {url}", oauth.endpoint_error(url, "ep") is None)
    for url in bad:
        ctx.check(f"rejected {url!r}", oauth.endpoint_error(url, "ep") is not None)


@test
def test_f8_bad_metadata_endpoints_never_reach_the_browser_or_token_post(ctx: Ctx):
    from halo_harness.mcp import oauth
    opened: list = []
    posted: list = []
    real_open, real_urlopen = oauth.webbrowser.open, oauth.urlopen
    try:
        oauth.webbrowser.open = lambda url, *a, **k: opened.append(url)
        oauth.urlopen = lambda req, *a, **k: posted.append(req) or (_ for _ in ()).throw(OSError("blocked in test"))
        for cfg in ({"authorization_endpoint": "file:///C:/Windows/System32/calc.exe",
                     "token_endpoint": "https://idp.example.com/token"},
                    {"authorization_endpoint": "https://idp.example.com/authorize",
                     "token_endpoint": "http://evil.example.com/token"}):
            tokens, err = oauth.run_authorization_flow(server_name="s", server_url="https://srv.example.com/mcp",
                                                       oauth_cfg=cfg, open_browser=True, callback_timeout=1.0,
                                                       print_fn=lambda *_: None)
            ctx.check(f"refused ({cfg['token_endpoint']}): {err}", tokens is None and err and "must be" in err)
    finally:
        oauth.webbrowser.open, oauth.urlopen = real_open, real_urlopen
    ctx.check("webbrowser.open never called", opened == [])
    ctx.check("no token POST made", posted == [])


@test
def test_f8_metadata_with_bad_scheme_is_rejected(ctx: Ctx):
    from halo_harness.mcp import oauth
    class _Resp:
        def __init__(self, body): self._b = body
        def read(self): return self._b
        def __enter__(self): return self
        def __exit__(self, *a): return False
    meta = json.dumps({"authorization_endpoint": "custom-scheme://x", "token_endpoint": "https://idp.example.com/t"})
    real = oauth.urlopen
    try:
        oauth.urlopen = lambda req, *a, **k: _Resp(meta.encode("utf-8"))
        _a, _t, err = oauth.discover_endpoints("https://srv.example.com/mcp", {})
    finally:
        oauth.urlopen = real
    ctx.check(f"metadata with a custom-scheme authorize endpoint is an error: {err}", bool(err) and "rejected" in err)


@test
def test_f8_token_endpoint_pinned_at_login_and_used_for_refresh(ctx: Ctx):
    from halo_harness.mcp import oauth
    home = tempfile.mkdtemp(prefix="halo-sec3-home-")
    with _env(BRIDGE_TEST_HOME=home):
        stored = {"access_token": "old", "refresh_token": "r-1", "token_endpoint": "https://pinned.example.com/token"}
        seen: list = []

        class _Resp:
            def read(self): return b'{"access_token": "new"}'
            def __enter__(self): return self
            def __exit__(self, *a): return False

        real_urlopen, real_discover = oauth.urlopen, oauth.discover_endpoints
        try:
            oauth.urlopen = lambda req, *a, **k: seen.append(req.full_url) or _Resp()
            oauth.discover_endpoints = lambda *a, **k: ("https://x/a", "https://swapped.example.com/token", None)
            tokens, err = oauth.refresh_tokens("srv", stored, oauth_cfg={}, server_url="https://srv.example.com/mcp")
        finally:
            oauth.urlopen, oauth.discover_endpoints = real_urlopen, real_discover
        ctx.check(f"refresh succeeded: {err}", tokens is not None and err is None)
        ctx.check(f"refresh went to the pinned endpoint, got {seen}", seen == ["https://pinned.example.com/token"])
        ctx.check("the pin is kept in the stored file",
                  oauth.load_tokens("srv").get("token_endpoint") == "https://pinned.example.com/token")
        bad = dict(stored, token_endpoint="http://evil.example.com/token")
        t2, e2 = oauth.refresh_tokens("srv", bad, oauth_cfg={}, server_url="https://srv.example.com/mcp")
        ctx.check(f"a pinned plaintext remote endpoint is refused: {e2}", t2 is None and e2)


@test
def test_f8_login_records_the_token_endpoint(ctx: Ctx):
    from tests.helpers.fake_oauth_server import FakeOAuthServer
    from tests.test_mcp_oauth import _run_flow_against
    server = FakeOAuthServer()
    server.start()
    try:
        tokens, err, _ = _run_flow_against(
            server, oauth_cfg={"authorization_endpoint": server.base_url + "/authorize",
                               "token_endpoint": server.base_url + "/token", "client_id": "c"})
        ctx.check(f"login ok: {err}", err is None)
        ctx.check("the exchange endpoint is recorded in the tokens", tokens.get("token_endpoint") == server.base_url + "/token")
    finally:
        server.stop()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
