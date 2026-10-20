"""tests.test_mcp_claude_auth -- the claude.ai login check the connectors
bridge runs (`mcp/claude_auth.py`) and the `claude` launcher it uses
(`mcp/claude_process.py`), 3.1.5.0 R1: moved out of the removed cc: route's
alias module. `claude auth status` JSON parsing (never the credentials
file), "claude not found", the two-token HALO_CLAUDE_EXE launcher, the
gateway rule (no spawn at all when `claude` is wired to a gateway) and the
cache-only `claude_login_available`.
"""
import builtins
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

os.environ["BRIDGE_TEST_HOME"] = tempfile.mkdtemp(prefix="claude-auth-scratchhome-")

test, TESTS = new_registry()


def _clear_env():
    for k in ("BRIDGE_TEST_CC_AUTH_STATUS", "ANTHROPIC_API_KEY", "BRIDGE_CLAUDE_EXE", "HALO_CLAUDE_EXE",
              "ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN"):
        os.environ.pop(k, None)


@test
def test_claude_auth_status_parses_real_shaped_json(ctx: Ctx):
    from halo_harness.mcp.claude_auth import claude_auth_status
    _clear_env()
    try:
        os.environ["BRIDGE_TEST_CC_AUTH_STATUS"] = json.dumps({
            "loggedIn": True, "authMethod": "claude.ai", "email": "owner@example.com", "subscriptionType": "max",
        })
        status = claude_auth_status()
        ctx.check("logged_in True", status.logged_in is True)
        ctx.check("auth_method claude.ai", status.auth_method == "claude.ai")
        ctx.check("subscription_type max", status.subscription_type == "max")
    finally:
        _clear_env()


@test
def test_claude_auth_status_not_logged_in_and_unparseable(ctx: Ctx):
    from halo_harness.mcp.claude_auth import claude_auth_status
    _clear_env()
    try:
        os.environ["BRIDGE_TEST_CC_AUTH_STATUS"] = json.dumps({"loggedIn": False})
        status = claude_auth_status()
        ctx.check("logged_in False", status is not None and status.logged_in is False)
        os.environ["BRIDGE_TEST_CC_AUTH_STATUS"] = "not json at all"
        status = claude_auth_status()
        ctx.check("unparseable -> logged_in False, not None", status is not None and status.logged_in is False)
    finally:
        _clear_env()


@test
def test_claude_not_found_returns_none(ctx: Ctx):
    """A launcher whose executable does not exist at all -> subprocess.run
    raises FileNotFoundError, read as "claude not found"."""
    from halo_harness.mcp.claude_auth import claude_auth_status
    _clear_env()
    missing = Path(tempfile.gettempdir()) / "definitely-not-a-real-claude-binary-xyz.exe"
    try:
        os.environ["BRIDGE_CLAUDE_EXE"] = '"' + str(missing) + '"'
        status = claude_auth_status()
        ctx.check(f"claude not found -> None, got {status!r}", status is None)
    finally:
        _clear_env()


@test
def test_resolve_claude_launch_argv_honors_a_two_token_value(ctx: Ctx):
    """Windows can't exec a bare .py path -- the launcher variable accepts a
    quoted "<interpreter> <script>" two-token form (the fake claude)."""
    from halo_harness.mcp.claude_process import resolve_claude_launch_argv
    _clear_env()
    try:
        fake = str(Path(__file__).resolve().parent / "helpers" / "fake_claude_cc.py")
        os.environ["BRIDGE_CLAUDE_EXE"] = '"' + sys.executable + '" "' + fake + '"'
        argv = resolve_claude_launch_argv()
        ctx.check(f"two tokens, got {argv!r}", len(argv) == 2)
        ctx.check("first token is the interpreter", argv[0] == sys.executable)
        ctx.check("second token is the fake script (no stray quotes)", argv[1] == fake)
    finally:
        _clear_env()


@test
def test_claude_child_env_strips_anthropic_and_claude_vars(ctx: Ctx):
    from halo_harness.mcp.claude_process import claude_child_env
    env = {"PATH": "/bin", "ANTHROPIC_API_KEY": "sk-x", "CLAUDE_EFFORT": "high", "CLAUDECODE": "1",
           "CLAUDE_CODE_SESSION_ID": "s", "OPENROUTER_API_KEY": "or-x"}
    out = claude_child_env(env, env_file_path=Path(tempfile.mkdtemp()) / "no-env-file")
    ctx.check(f"PATH kept, got {sorted(out)}", out.get("PATH") == "/bin")
    ctx.check("ANTHROPIC_* and CLAUDE* stripped", not [k for k in out if k.startswith(("ANTHROPIC_", "CLAUDE"))])
    ctx.check("provider keys stripped too (tool_child_env)", "OPENROUTER_API_KEY" not in out)


@test
def test_credentials_file_is_never_opened(ctx: Ctx):
    """halo never reads ~/.claude/.credentials.json -- a sentinel file under
    BRIDGE_TEST_HOME is never touched by the auth check."""
    from halo_harness.mcp.claude_auth import claude_auth_status, claude_login_available
    home_dir = Path(tempfile.mkdtemp(prefix="claude-cred-home-"))
    creds_path = home_dir / ".claude" / ".credentials.json"
    creds_path.parent.mkdir(parents=True, exist_ok=True)
    creds_path.write_text(json.dumps({"sentinel": "must-never-be-read"}), encoding="utf-8")
    _clear_env()
    old_home = os.environ.get("BRIDGE_TEST_HOME")
    os.environ["BRIDGE_TEST_HOME"] = str(home_dir)
    os.environ["BRIDGE_TEST_CC_AUTH_STATUS"] = json.dumps({"loggedIn": True})
    real_open = builtins.open
    opened = []

    def _guarded_open(file, *a, **kw):
        if str(file) == str(creds_path):
            opened.append(str(file))
        return real_open(file, *a, **kw)

    builtins.open = _guarded_open
    try:
        claude_auth_status()
        claude_login_available()
    finally:
        builtins.open = real_open
        _clear_env()
        if old_home is not None:
            os.environ["BRIDGE_TEST_HOME"] = old_home
    ctx.check(f"credentials file never opened, got opens={opened}", opened == [])


@test
def test_is_claude_gateway_driven_from_a_given_env(ctx: Ctx):
    from halo_harness.mcp.claude_auth import is_claude_gateway_driven
    ctx.check("True with ANTHROPIC_BASE_URL", is_claude_gateway_driven({"ANTHROPIC_BASE_URL": "https://gw.test"}))
    ctx.check("True with ANTHROPIC_AUTH_TOKEN", is_claude_gateway_driven({"ANTHROPIC_AUTH_TOKEN": "tok-fake"}))
    ctx.check("False for an explicit empty env", is_claude_gateway_driven({}) is False)


@test
def test_is_claude_gateway_driven_true_from_apikeyhelper_in_user_settings(ctx: Ctx):
    from halo_harness.mcp.claude_auth import is_claude_gateway_driven
    _clear_env()
    config_dir = Path(tempfile.mkdtemp(prefix="claude-gateway-config-"))
    (config_dir / "settings.json").write_text(json.dumps({"apiKeyHelper": "echo fake"}), encoding="utf-8")
    old = os.environ.get("CLAUDE_CONFIG_DIR")
    os.environ["CLAUDE_CONFIG_DIR"] = str(config_dir)
    try:
        ctx.check("True purely from apiKeyHelper", is_claude_gateway_driven() is True)
    finally:
        _clear_env()
        if old is None:
            os.environ.pop("CLAUDE_CONFIG_DIR", None)
        else:
            os.environ["CLAUDE_CONFIG_DIR"] = old


@test
def test_refresh_never_spawns_when_gateway_driven(ctx: Ctx):
    import halo_harness.mcp.claude_auth as auth

    def _poison(*, timeout=10.0, env=None):
        raise AssertionError("claude auth status must never be spawned when gateway-driven")

    _clear_env()
    os.environ["ANTHROPIC_BASE_URL"] = "https://gw.example.test"
    real = auth.claude_auth_status
    auth.claude_auth_status = _poison
    auth.reset_cached_claude_auth_status()
    try:
        status = auth.refresh_cached_claude_auth_status()
        ctx.check(f"a synthetic not-logged-in status, got {status!r}", status is not None and not status.logged_in)
        ctx.check("auth_method is the gateway sentinel", status.auth_method == auth.GATEWAY_AUTH_METHOD)
        cached = auth.cached_claude_auth_status()
        ctx.check("the cache holds it", cached is not None and cached.auth_method == auth.GATEWAY_AUTH_METHOD)
    finally:
        auth.claude_auth_status = real
        auth.reset_cached_claude_auth_status()
        _clear_env()


@test
def test_claude_login_available_is_cache_only_and_needs_claude_ai(ctx: Ctx):
    import halo_harness.mcp.claude_auth as auth
    _clear_env()
    auth.reset_cached_claude_auth_status()
    real = auth.claude_auth_status

    def _poison(*, timeout=10.0, env=None):
        raise AssertionError("claude_login_available() must never spawn claude auth status")

    try:
        auth.claude_auth_status = _poison
        ctx.check("a cold cache reads as not available, no spawn", auth.claude_login_available() is False)
        auth.claude_auth_status = real
        os.environ["BRIDGE_TEST_CC_AUTH_STATUS"] = json.dumps({"loggedIn": True, "authMethod": "api_key"})
        ctx.check("an api_key login is not a claude.ai login", auth.claude_login_available() is False)
        os.environ["BRIDGE_TEST_CC_AUTH_STATUS"] = json.dumps({"loggedIn": True, "authMethod": "claude.ai"})
        ctx.check("a claude.ai login is", auth.claude_login_available() is True)
    finally:
        auth.claude_auth_status = real
        auth.reset_cached_claude_auth_status()
        _clear_env()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
