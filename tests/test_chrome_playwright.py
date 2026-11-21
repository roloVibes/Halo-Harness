"""tests.test_chrome_playwright -- halo_harness/mcp_setup.py +
halo_harness/doctor.py (H3 scope E, brought forward from H7): `--chrome`/
`--no-chrome`/`claudeInChromeDefaultEnabled` resolution, the dynamic
`claude-in-chrome`/`playwright` McpServerConfig specs (spawn itself is
never exercised here -- these are pure config-building unit tests), and
`doctor`'s preconditions reporting.
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all
from halo_harness import mcp_setup as S

test, TESTS = new_registry()


# ---- resolve_chrome_enabled -------------------------------------------------

def _without_cfc_env(fn):
    """finding 14: resolve_chrome_enabled now consults CLAUDE_CODE_ENABLE_CFC
    -- isolate it so these tests never depend on whatever's set in the
    real shell running the suite."""
    old = os.environ.pop("CLAUDE_CODE_ENABLE_CFC", None)
    try:
        return fn()
    finally:
        if old is not None:
            os.environ["CLAUDE_CODE_ENABLE_CFC"] = old


@test
def test_chrome_enabled_by_flag(ctx: Ctx):
    _without_cfc_env(lambda: ctx.check(
        "--chrome enables it", S.resolve_chrome_enabled({}, chrome_flag=True, no_chrome_flag=False) is True))


@test
def test_chrome_disabled_by_no_chrome_flag_even_if_default_enabled(ctx: Ctx):
    _without_cfc_env(lambda: ctx.check(
        "--no-chrome wins over everything",
        S.resolve_chrome_enabled({"claudeInChromeDefaultEnabled": True}, chrome_flag=True, no_chrome_flag=True) is False))


@test
def test_chrome_default_from_claude_json(ctx: Ctx):
    def _run():
        ctx.check("claudeInChromeDefaultEnabled=true, no flags -> enabled",
                  S.resolve_chrome_enabled({"claudeInChromeDefaultEnabled": True}, chrome_flag=False, no_chrome_flag=False) is True)
        ctx.check("absent -> disabled",
                  S.resolve_chrome_enabled({}, chrome_flag=False, no_chrome_flag=False) is False)
    _without_cfc_env(_run)


@test
def test_chrome_enable_order_flag_beats_env_beats_interactive_beats_default(ctx: Ctx):
    """finding 14: the binary's own order -- flag -> CLAUDE_CODE_ENABLE_CFC
    -> off for non-interactive -> claudeInChromeDefaultEnabled."""
    def _run():
        os.environ["CLAUDE_CODE_ENABLE_CFC"] = "0"
        ctx.check("env var can DISABLE it even when claudeInChromeDefaultEnabled is true",
                  S.resolve_chrome_enabled({"claudeInChromeDefaultEnabled": True}, chrome_flag=False,
                                            no_chrome_flag=False) is False)
        os.environ["CLAUDE_CODE_ENABLE_CFC"] = "1"
        ctx.check("env var can ENABLE it even when claudeInChromeDefaultEnabled is absent",
                  S.resolve_chrome_enabled({}, chrome_flag=False, no_chrome_flag=False) is True)
        ctx.check("--chrome still beats the env var either way",
                  S.resolve_chrome_enabled({}, chrome_flag=True, no_chrome_flag=False) is True)
        os.environ.pop("CLAUDE_CODE_ENABLE_CFC", None)
        ctx.check("non-interactive (-p) NEVER auto-enables via claudeInChromeDefaultEnabled",
                  S.resolve_chrome_enabled({"claudeInChromeDefaultEnabled": True}, chrome_flag=False,
                                            no_chrome_flag=False, interactive=False) is False)
        ctx.check("interactive (TUI, the default) still honours claudeInChromeDefaultEnabled",
                  S.resolve_chrome_enabled({"claudeInChromeDefaultEnabled": True}, chrome_flag=False,
                                            no_chrome_flag=False, interactive=True) is True)
    _without_cfc_env(_run)


# ---- chrome_server_config ---------------------------------------------------

@test
def test_chrome_server_config_missing_exe(ctx: Ctx):
    """Isolates BOTH `PATH` (shutil.which) and `BRIDGE_TEST_HOME`
    (find_claude_exe's own `~/.local/bin/claude` fallback) -- without the
    home isolation this leaked on a real machine that happens to have a
    genuine `claude` binary installed under its actual home directory
    (verified: WSL/Kali, where the owner's own daily-driver `claude` lives)."""
    old = os.environ.pop("BRIDGE_CLAUDE_EXE", None)
    old_path = os.environ.get("PATH")
    old_home = os.environ.get("BRIDGE_TEST_HOME")
    with tempfile.TemporaryDirectory() as td:
        try:
            os.environ["PATH"] = ""  # nothing findable
            os.environ["BRIDGE_TEST_HOME"] = td  # nothing under ~/.local/bin either
            cfg, err = S.chrome_server_config(bypass_mode=False)
            ctx.check("no exe found -> None + a clear error", cfg is None and err is not None and "claude" in err.lower())
        finally:
            if old is not None:
                os.environ["BRIDGE_CLAUDE_EXE"] = old
            os.environ["PATH"] = old_path or ""
            if old_home is None:
                os.environ.pop("BRIDGE_TEST_HOME", None)
            else:
                os.environ["BRIDGE_TEST_HOME"] = old_home


@test
def test_chrome_server_config_shape(ctx: Ctx):
    old = os.environ.get("BRIDGE_CLAUDE_EXE")
    os.environ["BRIDGE_CLAUDE_EXE"] = "/fake/claude"
    try:
        cfg, err = S.chrome_server_config(bypass_mode=False)
        ctx.check("no error", err is None)
        ctx.check("named claude-in-chrome", cfg.name == "claude-in-chrome")
        ctx.check("stdio transport", cfg.type == "stdio")
        ctx.check("command is the resolved exe", cfg.command == "/fake/claude")
        ctx.check("args = --claude-in-chrome-mcp [verified doc]", cfg.args == ["--claude-in-chrome-mcp"])
        ctx.check("dynamic scope", cfg.scope == "dynamic")
        # finding 9: ALWAYS set now, regardless of bypass_mode -- see
        # chrome_server_config's own docstring (halo's engine
        # already gates every mcp__claude-in-chrome__* call itself).
        ctx.check("bypass env set even when bypass_mode=False (the engine gates it either way)",
                  cfg.env.get("CLAUDE_CHROME_PERMISSION_MODE") == "skip_all_permission_checks")
    finally:
        if old is None:
            os.environ.pop("BRIDGE_CLAUDE_EXE", None)
        else:
            os.environ["BRIDGE_CLAUDE_EXE"] = old


@test
def test_chrome_server_config_bypass_mode_env(ctx: Ctx):
    old = os.environ.get("BRIDGE_CLAUDE_EXE")
    os.environ["BRIDGE_CLAUDE_EXE"] = "/fake/claude"
    try:
        cfg, err = S.chrome_server_config(bypass_mode=True)
        ctx.check("CLAUDE_CHROME_PERMISSION_MODE set in auto/bypass modes",
                  cfg.env.get("CLAUDE_CHROME_PERMISSION_MODE") == "skip_all_permission_checks")
    finally:
        if old is None:
            os.environ.pop("BRIDGE_CLAUDE_EXE", None)
        else:
            os.environ["BRIDGE_CLAUDE_EXE"] = old


# ---- find_claude_exe ---------------------------------------------------

@test
def test_find_claude_exe_env_override_wins(ctx: Ctx):
    old = os.environ.get("BRIDGE_CLAUDE_EXE")
    os.environ["BRIDGE_CLAUDE_EXE"] = "/explicit/path/claude"
    try:
        ctx.check("BRIDGE_CLAUDE_EXE takes precedence", S.find_claude_exe() == "/explicit/path/claude")
    finally:
        if old is None:
            os.environ.pop("BRIDGE_CLAUDE_EXE", None)
        else:
            os.environ["BRIDGE_CLAUDE_EXE"] = old


# ---- playwright_server_config -----------------------------------------

@test
def test_playwright_server_config_shape(ctx: Ctx):
    cfg, err = S.playwright_server_config()
    if shutil.which("npx") is None and shutil.which("npx.cmd") is None:
        ctx.check("no npx -> a clear error, not a crash", cfg is None and err is not None)
        return
    ctx.check("no error", err is None)
    ctx.check("named playwright", cfg.name == "playwright")
    ctx.check("stdio transport", cfg.type == "stdio")
    # 3.6.0.6 W (rewritten to the truth): a fixed, tested version, never @latest; the page files go under Halo's home
    ctx.check(f"the fixed version, never @latest, got {cfg.args}",
              cfg.args[:2] == ["-y", "@playwright/mcp@0.0.86"] and not any("@latest" in a for a in cfg.args))
    ctx.check("ONE constant holds it", S.PLAYWRIGHT_VERSION == "0.0.86")
    i = cfg.args.index("--output-dir") if "--output-dir" in cfg.args else -1
    from halo_harness.config.paths import bridge_home
    ctx.check(f"its page files go under Halo's home, got {cfg.args}",
              i > 0 and Path(cfg.args[i + 1]).parent == bridge_home() / "playwright")


@test
def test_playwright_cdp_endpoint_passthrough(ctx: Ctx):
    cfg, err = S.playwright_server_config(cdp_endpoint="http://localhost:9222")
    if cfg is None:
        raise SkipTest("npx not on PATH")
    ctx.check("--playwright-cdp becomes --cdp-endpoint <value>",
              "--cdp-endpoint" in cfg.args and "http://localhost:9222" in cfg.args)


@test
def test_playwright_headless_passthrough(ctx: Ctx):
    cfg, err = S.playwright_server_config(headless=True)
    if cfg is None:
        raise SkipTest("npx not on PATH")
    ctx.check("--playwright-headless becomes --headless", "--headless" in cfg.args)


@test
def test_playwright_no_extra_flags_by_default(ctx: Ctx):
    cfg, err = S.playwright_server_config()
    if cfg is None:
        raise SkipTest("npx not on PATH")
    ctx.check("no --cdp-endpoint/--headless when not asked for",
              "--cdp-endpoint" not in cfg.args and "--headless" not in cfg.args)


# ---- build_manager wiring (spawn mocked: --chrome/--playwright never actually
#      connect here, only their resolved McpServerConfig is inspected) --------

@test
def test_build_manager_wires_chrome_into_configs_without_connecting(ctx: Ctx):
    old = os.environ.get("BRIDGE_CLAUDE_EXE")
    os.environ["BRIDGE_CLAUDE_EXE"] = "/fake/claude"
    try:
        mgr, notices = S.build_manager(cwd=Path("."), claude_json={}, chrome=True, start=False)
        if mgr is None:
            raise SkipTest("mcp package not installed")
        ctx.check("claude-in-chrome server resolved", "claude-in-chrome" in mgr.configs)
        ctx.check("start=False never connects", mgr.handles["claude-in-chrome"].state == "pending")
    finally:
        if old is None:
            os.environ.pop("BRIDGE_CLAUDE_EXE", None)
        else:
            os.environ["BRIDGE_CLAUDE_EXE"] = old


@test
def test_build_manager_says_once_what_playwright_downloads_before_it_starts(ctx: Ctx):
    """3.6.0.6 W: --playwright says, once and word for word, the version it starts and what the first start downloads;
    nothing is started here (start=False; node and npx stood in)."""
    from unittest import mock
    with mock.patch.object(S.shutil, "which", lambda name, *a, **k: "/usr/bin/" + name.replace(".cmd", "")):
        mgr, notices = S.build_manager(cwd=Path("."), claude_json={}, playwright=True, start=False)
    if mgr is None:
        raise SkipTest("mcp package not installed")
    want = ("--playwright: starting Playwright's own server with npx (version 0.0.86); the first start downloads "
            "about 59 MB from the npm registry.")
    ctx.check(f"the notice, once, word for word, got {notices}", notices.count(want) == 1)
    ctx.check("start=False never connects", mgr.handles["playwright"].state == "pending")
    mgr2, notices2 = S.build_manager(cwd=Path("."), claude_json={}, start=False)
    ctx.check("no --playwright: no notice", want not in (notices2 or []))


@test
def test_playwright_leaves_no_folder_behind(ctx: Ctx):
    """W batch 3 entry 6: the page files' folder (`<halo home>/playwright/<pid>`) goes when the manager that made it
    closes; at each start a folder whose pid is no longer alive is removed, never one of a live halo."""
    from unittest import mock
    home = Path(tempfile.mkdtemp(prefix="pw-home-"))
    try:
        with mock.patch.dict(os.environ, {"BRIDGE_STATE_DIR": str(home / "state")}):
            mine = S.playwright_output_dir()
            gone, live = mine.parent / "999991", mine.parent / "999992"
            for p in (gone, live):
                (p / "page.yml").parent.mkdir(parents=True)
                (p / "page.yml").write_text("x")
            with mock.patch.object(S.shutil, "which", lambda name, *a, **k: "/usr/bin/" + name.replace(".cmd", "")), \
                    mock.patch("halo_harness.children.pid_running", lambda pid: pid in (999992, os.getpid())):
                mgr, _n = S.build_manager(cwd=Path("."), claude_json={}, playwright=True, start=False)
            if mgr is None:
                raise SkipTest("mcp package not installed")
            ctx.check("a gone halo's folder is removed at the start", not gone.exists())
            ctx.check("a live halo's folder is left alone", live.exists())
            mine.mkdir(parents=True, exist_ok=True)
            (mine / "page-1.yml").write_text("a page")
            mgr.close_all()
            ctx.check(f"its own folder is gone once the manager closed, got {mine.exists()}", not mine.exists())
            ctx.check("the live one still stays", live.exists())
    finally:
        shutil.rmtree(home, ignore_errors=True)


@test
def test_build_manager_unavailable_mcp_returns_none(ctx: Ctx):
    import halo_harness.mcp as mcp_pkg
    old_available = mcp_pkg.available
    mcp_pkg.available = lambda: False
    try:
        mgr, notices = S.build_manager(cwd=Path("."), claude_json={})
        ctx.check("None manager when mcp package unavailable", mgr is None)
        ctx.check("exactly the NOT_AVAILABLE_NOTICE", notices == [mcp_pkg.NOT_AVAILABLE_NOTICE])
    finally:
        mcp_pkg.available = old_available


# ---- doctor.py chrome/playwright checks ------------------------------------

@test
def test_doctor_checks_never_raise(ctx: Ctx):
    from halo_harness import doctor
    lines, ok = doctor.run_checks()
    ctx.check("doctor always returns a bool ok flag", isinstance(ok, bool))
    ctx.check("a line mentions --chrome", any("--chrome" in l or "claude=" in l for l in lines))
    ctx.check("a line mentions --playwright", any("--playwright" in l for l in lines))


@test
def test_doctor_chrome_native_host_lookup_never_raises(ctx: Ctx):
    from halo_harness.doctor import _chrome_native_host_registered
    registered, detail = _chrome_native_host_registered()
    ctx.check("returns a bool + a detail string, never raises", isinstance(registered, bool) and isinstance(detail, str))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
