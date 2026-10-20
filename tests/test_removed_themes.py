"""tests.test_removed_themes -- Halo 3.1.5.0 R2: the game themes are gone.

  1. nothing under halo_harness imports a scene / HUD / game-palette /
     toggle / level-band module, no builtin or TUI handler is a game toggle
     or `/level`, and `VALID_THEMES` is the six ordinary names;
  2. a saved game theme is one line, never a crash: `resolve_theme` falls
     back, the TUI shows the notice at startup, `halo doctor --config`
     prints the same line (and one per leftover game-theme key);
  3. the status bar is one row under every theme; `STATUS_BAR_OVERRIDE` is gone;
  4. a resize keeps the status bar in place (one row, docked at the bottom).
"""

from __future__ import annotations

TIER = "full"  # TUI pilots (Textual run_test): the full tier

import ast
import asyncio
import contextlib
import inspect
import io
import os
import re
import sys
from pathlib import Path
from types import SimpleNamespace

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.config_seed import ConfigHome  # noqa: E402
from tests.helpers.layout_watch import watch_own_layout_requests  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()

SIX = {"claude-dark", "claude-light", "claude-dark-daltonized", "claude-light-daltonized",
       "claude-dark-ansi", "claude-light-ansi"}
GAMES = ("doom", "metroid", "mario", "beetlejuice", "alien")
GONE_MODULE = re.compile(r"(^|\.)(scene\w*|hud\w*|theme_games|theme_mario|theme_metroid|theme_toggle|borders)$")
NOTICE = "theme: doom was a game theme, removed in 3.1.5.0; using claude-dark"


@contextlib.contextmanager
def _truecolor():
    """A truecolor terminal with no theme variable set, so the fallback is
    `claude-dark` on every runner."""
    names = ("COLORTERM", "HALO_THEME", "CLAUDE_BRIDGE_THEME", "ROLO_CLAUDE_THEME")
    saved = {k: os.environ.get(k) for k in names}
    for k in names[1:]:
        os.environ.pop(k, None)
    os.environ["COLORTERM"] = "truecolor"
    try:
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _imports(path: Path) -> list:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            out += [base] + [f"{base}.{a.name}" for a in node.names]
    return out


@test
def test_1_nothing_imports_the_game_modules_and_the_commands_are_gone(ctx: Ctx):
    pkg = REPO_DIR / "halo_harness"
    hits = []
    for path in sorted(pkg.rglob("*.py")):
        hits += [f"{path.relative_to(REPO_DIR).as_posix()}: {m}" for m in _imports(path)
                 if m.startswith("halo_harness") and GONE_MODULE.search(m)]
    ctx.check(f"no halo_harness module imports a removed one, got {hits}", not hits)
    leftovers = [p.name for p in (pkg / "tui").glob("*") if GONE_MODULE.search(p.stem) or p.name == "styles_brick.tcss"]
    leftovers += [p.name for p in [pkg / "theme_toggle.py", pkg / "tui" / "widgets" / "scene_band.py"] if p.exists()]
    ctx.check(f"the game modules themselves are gone, got {leftovers}", not leftovers)
    from halo_harness import theme
    from halo_harness.commands.builtins import _BUILTIN_SPECS
    from halo_harness.tui import slash
    gone = ("level",) + GAMES
    ctx.check(f"no builtin /level or game toggle, got {[n for n in gone if n in _BUILTIN_SPECS]}",
              not any(n in _BUILTIN_SPECS for n in gone))
    src = inspect.getsource(slash.handle_slash)
    tui_rows = [n for n in gone if re.search(rf'"{n}"\s*:', src) or hasattr(slash, f"_handle_{n}")]
    ctx.check(f"no TUI handler for them either, got {tui_rows}", not tui_rows)
    ctx.check(f"VALID_THEMES is the six, got {sorted(theme.VALID_THEMES)}", set(theme.VALID_THEMES) == SIX)
    for name in ("GAME_THEMES", "GAME_VARIANTS", "variant_for", "variants_of", "VARIANT_KEY"):
        ctx.check(f"theme.{name} is gone", not hasattr(theme, name))


@test
def test_2_a_saved_game_theme_is_one_line_at_startup_and_in_the_doctor(ctx: Ctx):
    from halo_harness import theme
    with _truecolor():
        for game in GAMES:
            ctx.check(f"resolve_theme skips a saved {game}",
                      theme.resolve_theme(persisted_theme=game) == "claude-dark")
        ctx.check("the notice, verbatim", theme.removed_theme_notice("claude-dark", persisted="doom") == NOTICE)
        ctx.check("no notice for an ordinary theme", theme.removed_theme_notice("claude-dark", persisted="claude-light") is None)
        with ConfigHome() as h:
            h.config({"theme": "doom", "theme_scene": False, "theme_variant": "norfair",
                      "theme_toggle_previous": "claude-dark", "intro": False})
            _check_startup(ctx)
            _check_doctor(ctx, h)
            _check_config_set(ctx)


def _check_startup(ctx: Ctx) -> None:
    """`run_tui` itself, with the app's run and the console guard stubbed:
    the notice rides `startup_notice`, which on_mount shows as a toast."""
    from halo_harness.tui import console_mode, launch
    from halo_harness.tui.app import BridgeApp
    seen = {}
    real_run, real_install = BridgeApp.run, console_mode.install
    BridgeApp.run = lambda self, *a, **k: seen.update(theme=self.theme_name, notice=getattr(self, "startup_notice", None))
    console_mode.install = lambda: SimpleNamespace(restore=lambda: None)
    try:
        args = SimpleNamespace(cwd=None, demo=True, stress=0, theme=None, prompt=None,
                               no_inline_images=False, no_intro=True)
        rc = launch.run_tui(args)
    finally:
        BridgeApp.run, console_mode.install = real_run, real_install
    ctx.check(f"run_tui starts on claude-dark, got {seen}", rc == 0 and seen.get("theme") == "claude-dark")
    ctx.check(f"with the one notice line, got {seen.get('notice')!r}", (seen.get("notice") or "").splitlines()[-1:] == [NOTICE])

    async def body():
        from halo_harness.testing.fake_controller import FakeController
        app = BridgeApp(FakeController(), cwd="~/project", theme_name="claude-dark")
        app.startup_notice = NOTICE
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.pause(0.3)
            messages = [n.message for n in app._notifications]
            ctx.check(f"the TUI shows it once at startup, got {messages}", messages.count(NOTICE) == 1)
    asyncio.run(body())


def _check_doctor(ctx: Ctx, h) -> None:
    from halo_harness.doctor_config import cmd_doctor_config, config_findings
    found = [f for f in config_findings(h.repo) if f["file"] == "~/.halo/config.json"]
    texts = sorted(f["text"] for f in found)
    want = sorted([NOTICE] + [f"{k}: removed in 3.1.5.0 with the game themes, the key is ignored"
                              for k in ("theme_scene", "theme_toggle_previous", "theme_variant")])
    ctx.check(f"doctor --config: one line each, got {texts}", texts == want)
    ctx.check("all warnings, none an unknown key or a bad value",
              all(f["severity"] == "warns" for f in found)
              and {f["check"] for f in found} == {"removed-theme", "removed-key"})
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        cmd_doctor_config(cwd=h.repo)
    lines = [line.strip() for line in out.getvalue().splitlines()]
    ctx.check(f"the CLI prints the same line, got {out.getvalue()[-600:]!r}",
              f"[WARN] ~/.halo/config.json: {NOTICE}" in lines)


def _check_config_set(ctx: Ctx) -> None:
    from halo_harness.config_cli import _cmd_set
    for argv, words in ((["theme", "doom"], "doom was a game theme, removed in 3.1.5.0"),
                        (["theme_scene", "false"], "theme_scene: removed in 3.1.5.0")):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            rc = _cmd_set(argv)
        ctx.check(f"halo config set {' '.join(argv)}: exit 2 with one line, got {rc} {err.getvalue()!r}",
                  rc == 2 and words in err.getvalue() and len(err.getvalue().strip().splitlines()) == 1)


def _app(theme: str = "claude-dark"):
    from halo_harness.testing.fake_controller import FakeController
    from halo_harness.tui.app import BridgeApp
    return BridgeApp(FakeController(), cwd="~/project", theme_name=theme)


def _busy(bar) -> None:
    """Every optional segment on, so a second row would show if one existed."""
    bar.apply_status({"model": "or:vendor/model", "context_tokens": 300_000, "context_limit": 1_000_000,
                      "cost_usd": 0.04, "permission_mode": "auto", "effort": "high", "mcp": {"connected": 3, "total": 3}})
    bar.set_provider_balance("openrouter", "OR $12.40 left")
    bar.set_cwd_branch("~/project", "main")
    bar.set_agents_running(2)
    bar.set_needs_you(2)
    bar.set_offline(True)
    bar.set_remote_attached(1)
    bar.set_background_activity(bg_jobs=1, oldest_elapsed_s=12.0, bg_kinds="suites 1", hang_watch_s=None)
    bar.set_phase_word("writing")


@test
def test_3_the_status_bar_is_one_row_under_every_theme(ctx: Ctx):
    from halo_harness.tui.widgets import statusbar
    for name in ("set_theme", "fire_cue", "set_error", "note_turn", "hud_turn_seconds", "cue_active"):
        ctx.check(f"StatusBar.{name} is gone", not hasattr(statusbar.StatusBar, name))
    defining = [p.relative_to(REPO_DIR).as_posix() for p in (REPO_DIR / "halo_harness").rglob("*.py")
                if "STATUS_BAR_OVERRIDE" in p.read_text(encoding="utf-8")]
    ctx.check(f"STATUS_BAR_OVERRIDE is gone, got {defining}", not defining)

    async def body():
        app = _app()
        async with app.run_test(size=(140, 30)) as pilot:
            await pilot.pause(0.2)
            bar = app.status_bar
            _busy(bar)
            for theme in sorted(SIX):
                app.apply_theme(theme)
                await pilot.pause(0.1)
                lines = str(bar.render()).splitlines()
                ctx.check(f"{theme}: one row, got height {bar.size.height}, {len(lines)} line(s)",
                          bar.size.height == 1 and len(lines) == 1)
            glyph = str(app.query_one("#prompt-glyph").render())
            ctx.check(f"the prompt glyph is the plain one, got {glyph!r}", glyph.strip() == "❯")
            ctx.check("no visor frame", not app.query("#prompt-frame-r") and not app.query("#scene-band"))
    asyncio.run(body())


@test
def test_4_a_resize_keeps_the_status_bar_in_place(ctx: Ctx):
    async def body():
        app = _app()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.2)
            bar = app.status_bar
            _busy(bar)
            await pilot.pause(0.2)
            for size in ((100, 30), (80, 24), (130, 45)):
                with watch_own_layout_requests(bar) as asked:
                    await pilot.resize_terminal(*size)
                    await pilot.pause(0.3)
                region = bar.region
                ctx.check(f"{size}: one row on the last line, no layout request of its own, got {region} {asked}",
                          region.height == 1 and region.y == size[1] - 1 and region.width == size[0] and not asked)
    asyncio.run(body())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
