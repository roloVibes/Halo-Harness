"""tests.test_theme_session -- the theme a real session gets when a home holds BOTH a `theme` in Claude Code's
settings files and a theme picked in Halo (Setup, Settings, /theme: ~/.halo/config.json).

3.5.0.1 fixed the order (the pick in Halo wins) in `theme.resolve_theme`, and one test of that function was all that
stood between a release and the bug coming back: nothing started a session in such a home. These tests do, through
the two places a session's theme is decided: `headless.build_session` (the `-p` session and the facade `/status`,
`/config` and `/theme` read in the TUI too) and `tui.launch.run_tui` (the palette the full-screen session draws).
Nothing here sends a request: the provider points at a dead port and the TUI app is a stand-in that stops at once.
"""
import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()

CLAUDE_CODE_THEME = "claude-light"  # left in ~/.claude/settings.json long ago
PICKED = "claude-dark-ansi"          # picked in Halo since
_ENV = ("BRIDGE_TEST_HOME", "HOME", "USERPROFILE", "CLAUDE_CONFIG_DIR", "HALO_THEME", "CLAUDE_BRIDGE_THEME",
        "ROLO_CLAUDE_THEME", "OPENROUTER_API_KEY", "BRIDGE_OPENROUTER_BASE_URL", "OLLAMA_HOST")


def _in_home(fn):
    """Run fn(home, project) in a scratch home holding both themes; every variable it sets is restored after."""
    saved = {k: os.environ.get(k) for k in _ENV}
    root = Path(tempfile.mkdtemp(prefix="halo-theme-session-"))
    home, proj = root / "home", root / "proj"
    (home / ".claude").mkdir(parents=True)
    proj.mkdir()
    (home / ".claude" / "settings.json").write_text(json.dumps({"theme": CLAUDE_CODE_THEME}), encoding="utf-8")
    for k in ("CLAUDE_CONFIG_DIR", "HALO_THEME", "CLAUDE_BRIDGE_THEME", "ROLO_CLAUDE_THEME"):
        os.environ.pop(k, None)
    os.environ.update(BRIDGE_TEST_HOME=str(home), HOME=str(home), USERPROFILE=str(home),
                      OPENROUTER_API_KEY="sk-or-not-a-key", BRIDGE_OPENROUTER_BASE_URL="http://127.0.0.1:9",
                      OLLAMA_HOST="http://127.0.0.1:9")
    try:
        from halo_harness import theme
        theme.persist_theme(PICKED)
        return fn(home, proj)
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _build(proj: Path):
    from halo_harness import headless
    return headless.build_session(cwd=proj, model_ref_raw="or:mock/theme-session", print_mode=True, max_turns=1)


@test
def test_a_session_built_in_a_home_with_both_themes_carries_the_one_picked_in_halo(ctx: Ctx):
    """`halo -p` and the TUI build through `build_session`; its facade answers `/status` ("Theme: ...") and
    `/config`. It resolved the theme from Claude Code's settings alone, so it named claude-light while the terminal
    drew the pick."""
    def run(home, proj):
        b = _build(proj)
        ctx.check(f"the settings the session read hold Claude Code's theme, got {b.facade.settings.theme!r}",
                  b.facade.settings.theme == CLAUDE_CODE_THEME)
        ctx.check(f"the session's theme is the pick made in Halo, got {b.facade.theme!r}", b.facade.theme == PICKED)
    _in_home(run)


class _Stop(Exception):
    pass


@test
def test_the_full_screen_session_draws_the_theme_picked_in_halo_over_claude_codes(ctx: Ctx):
    """`run_tui` with the real session builder in that home: the theme handed to the app is the pick."""
    import halo_harness.tui.app as app_mod
    import halo_harness.tui.bootstrap as boot
    from halo_harness.tui import launch
    got = {}

    def build_controller(args):
        b = _build(Path(args.cwd))
        return SimpleNamespace(cwd=Path(args.cwd)), None, b.facade

    class App:
        def __init__(self, *a, theme_name=None, **kw):
            got["theme_name"] = theme_name
            raise _Stop()

    def run(home, proj):
        saved = (boot.build_controller, app_mod.BridgeApp)
        boot.build_controller, app_mod.BridgeApp = build_controller, App
        try:
            launch.run_tui(SimpleNamespace(demo=False, theme=None, cwd=str(proj), prompt=None))
        except _Stop:
            pass
        finally:
            boot.build_controller, app_mod.BridgeApp = saved
    _in_home(run)
    ctx.check(f"the app is handed the pick made in Halo, got {got.get('theme_name')!r}", got.get("theme_name") == PICKED)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
