"""tests.test_theme_toggles_app -- the game-theme toggles inside a real
BridgeApp, the theme-name completion and the wizard's Theme step (Halo 2.0.8
theme pack, round 1). The pure contract tests live in
tests/test_theme_toggles.py, whose scoped-home helper is reused here.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from halo_harness import theme as theme_mod
from halo_harness import theme_toggle as tt
from tests.test_theme_toggles import GAMES, _cfg, _scoped

test, TESTS = new_registry()


# ---- the TUI forms ---------------------------------------------------------------

def _app(theme: str):
    from halo_harness.testing.fake_controller import FakeController
    from halo_harness.tui.app import BridgeApp
    return BridgeApp(FakeController(), cwd="~/project", theme_name=theme)


@test
def test_tui_slash_toggles_apply_and_restore_live(ctx: Ctx):
    from halo_harness.tui.slash import handle_slash

    async def body():
        for game in GAMES:
            with _scoped():
                app = _app("claude-light")
                async with app.run_test(size=(100, 24)) as pilot:
                    await pilot.pause(0.05)
                    await handle_slash(app, game, "")
                    ctx.check(f"/{game}: app theme is {game}", app.theme_name == game)
                    ctx.check(f"/{game}: persisted", _cfg()["theme"] == game)
                    ctx.check(f"/{game}: palette applied", app.get_css_variables()["bridge-bg"] != "#eff1f5")
                    await handle_slash(app, game, "")
                    ctx.check(f"/{game} again: app theme restored to claude-light, got {app.theme_name!r}",
                              app.theme_name == "claude-light")
                    ctx.check(f"/{game} again: persisted + cleared",
                              _cfg()["theme"] == "claude-light" and tt.PREVIOUS_KEY not in _cfg())
                    await handle_slash(app, "theme", game)
                    ctx.check(f"/theme {game}: applied and previous recorded",
                              app.theme_name == game and _cfg()[tt.PREVIOUS_KEY] == "claude-light")
                    await handle_slash(app, "theme", "claude-dark-ansi")
                    ctx.check("/theme <normal> leaves the game theme and clears the previous",
                              app.theme_name == "claude-dark-ansi" and tt.PREVIOUS_KEY not in _cfg())
    asyncio.run(body())


@test
def test_tui_game_to_game_chain_returns_to_the_original(ctx: Ctx):
    from halo_harness.tui.slash import handle_slash

    async def body():
        with _scoped():
            app = _app("claude-dark-daltonized")
            async with app.run_test(size=(100, 24)) as pilot:
                await pilot.pause(0.05)
                for name in ("doom", "metroid", "metroid"):
                    await handle_slash(app, name, "")
                ctx.check(f"/doom /metroid /metroid -> back to claude-dark-daltonized, got {app.theme_name!r}",
                          app.theme_name == "claude-dark-daltonized" and _cfg()["theme"] == "claude-dark-daltonized")
    asyncio.run(body())


@test
def test_relaunch_in_the_tui_restores_through_the_config_file(ctx: Ctx):
    from halo_harness.tui.slash import handle_slash

    async def body():
        with _scoped():
            first = _app("claude-light")
            async with first.run_test(size=(100, 24)) as pilot:
                await pilot.pause(0.05)
                await handle_slash(first, "mario", "")
            second = _app(theme_mod.resolve_theme(env={"TERM": "xterm"}, persisted_theme=theme_mod.load_persisted_theme()))
            async with second.run_test(size=(100, 24)) as pilot:
                await pilot.pause(0.05)
                ctx.check(f"the relaunched app starts in mario, got {second.theme_name!r}", second.theme_name == "mario")
                await handle_slash(second, "mario", "")
                ctx.check(f"/mario in the relaunched app restores claude-light, got {second.theme_name!r}",
                          second.theme_name == "claude-light")
    asyncio.run(body())


# ---- completion + wizard -----------------------------------------------------------

@test
def test_theme_name_completion_lists_the_game_themes(ctx: Ctx):
    from halo_harness.tui.completion import complete_slash, current_token, theme_command_arg_index
    ctx.check("cursor in the theme argument -> index 0", theme_command_arg_index("/theme do", 9) == 0)
    ctx.check("bare '/theme ' -> index 0", theme_command_arg_index("/theme ", 7) == 0)
    ctx.check("past the argument -> None", theme_command_arg_index("/theme doom ", 12) is None)
    ctx.check("/themes... is not the command", theme_command_arg_index("/themex do", 10) is None)
    kind, start, token = current_token("/theme me", 9)
    ctx.check(f"current_token reports themearg, got {kind!r} {token!r}", kind == "themearg" and token == "me" and start == 7)

    from halo_harness.commands.builtins import register_builtins
    from halo_harness.commands.registry import Registry
    registry = Registry()
    register_builtins(registry)
    for game in GAMES:
        hits = [inv for inv, desc in complete_slash(game[:3], registry) if inv == f"/{game}"]
        ctx.check(f"/{game} completes from {game[:3]!r}", bool(hits))
        described = [desc for inv, desc in complete_slash(game, registry) if inv == f"/{game}"]
        ctx.check(f"/{game} carries a description in completion", bool(described and described[0]))

    async def body():
        with _scoped():
            app = _app("claude-dark")
            async with app.run_test(size=(100, 24)) as pilot:
                await pilot.pause(0.05)
                names = app._complete_theme_command_arg("")
                ctx.check(f"game themes lead the list: {names[:3]}", names[:3] == list(GAMES))
                ctx.check("the whole family is offered", len(names) == 9)
                ctx.check("a prefix filters", app._complete_theme_command_arg("me")[0] == "metroid")
                ctx.check("an exact name closes the popup", app._complete_theme_command_arg("doom") == [])
    asyncio.run(body())


@test
def test_wizard_theme_step_lists_and_commits_the_game_themes(ctx: Ctx):
    from textual.widgets import OptionList

    from halo_harness.tui.dialogs.init_wizard import InitWizardApp, WizardState

    async def body():
        with _scoped():
            theme_mod.set_config_value("theme", "claude-light")
            state = WizardState(cwd=str(Path(__file__).resolve().parent.parent), step_keys=("theme",), no_live=True)
            app = InitWizardApp(state)
            async with app.run_test(size=(110, 45)) as pilot:
                await pilot.pause(0.2)
                option_list = app.screen.query_one("#wiz-theme-list", OptionList)
                prompts = {str(option_list.get_option_at_index(i).id): str(option_list.get_option_at_index(i).prompt)
                           for i in range(option_list.option_count)}
                for game in GAMES:
                    ctx.check(f"wizard lists {game}", game in prompts)
                    ctx.check(f"wizard shows a description for {game}: {prompts[game]!r}",
                              theme_mod.GAME_THEME_DESCRIPTIONS[game] in prompts[game])
                option_list.highlighted = list(prompts).index("doom")
                await pilot.pause(0.1)
                app.screen.commit()
                ctx.check("wizard commit persists doom", _cfg()["theme"] == "doom")
                ctx.check("wizard commit records the previous theme", _cfg()[tt.PREVIOUS_KEY] == "claude-light")
    asyncio.run(body())


@test
def test_config_cli_accepts_the_game_names(ctx: Ctx):
    import io
    from contextlib import redirect_stderr, redirect_stdout

    from halo_harness import cli as cli_mod
    with _scoped():
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            try:
                code = cli_mod.main(["config", "set", "theme", "mario"])
            except SystemExit as e:
                code = e.code
        ctx.check(f"`halo config set theme mario` exits 0, got {code!r} {err.getvalue()!r}", code in (0, None))
        ctx.check("and persisted it", _cfg().get("theme") == "mario")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
