"""tests.test_theme_toggles -- the game-theme toggle contract (Halo 2.0.8 theme
pack, round 1), pinned once for `/doom`, `/metroid` and `/mario`:

  /<game> off -> remember the active theme as `theme_toggle_previous`, apply
  and persist the game theme; /<game> on -> restore the previous (default
  claude-dark) and clear it; game -> game keeps the original previous;
  `/theme <name>` records the previous the same way; all of it survives a
  relaunch through ~/.halo/config.json.

Every test scopes BRIDGE_TEST_HOME and BRIDGE_STATE_DIR to its own fresh dir.
"""
from __future__ import annotations

import contextlib
import itertools
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from halo_harness import theme as theme_mod
from halo_harness import theme_toggle as tt

test, TESTS = new_registry()
GAMES = ("doom", "metroid", "mario")


@contextlib.contextmanager
def _scoped():
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
    tmp = Path(tempfile.mkdtemp(prefix="halo-toggle-"))
    os.environ["BRIDGE_TEST_HOME"] = str(tmp)
    os.environ["BRIDGE_STATE_DIR"] = str(tmp / ".halo")
    try:
        yield tmp / ".halo"
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _cfg() -> dict:
    return theme_mod.load_config()


# ---- the names ----------------------------------------------------------------

@test
def test_game_theme_names_are_valid_and_exact(ctx: Ctx):
    ctx.check("GAME_THEMES is exactly doom, metroid, mario", theme_mod.GAME_THEMES == GAMES)
    for name in GAMES:
        ctx.check(f"{name} is a valid theme", theme_mod.is_valid_theme(name))
        ctx.check(f"{name} has a one-line description", len(theme_mod.GAME_THEME_DESCRIPTIONS[name]) > 20
                  and "\n" not in theme_mod.GAME_THEME_DESCRIPTIONS[name])
        for suffix in ("-ansi", "-daltonized"):
            ctx.check(f"{name}{suffix} is NOT a theme (the three are their own look)",
                      not theme_mod.is_valid_theme(name + suffix))
    ctx.check("the base family is unchanged (6 + 3)", len(theme_mod.VALID_THEMES) == 9)
    ctx.check("explicit theme choice resolves", theme_mod.resolve_theme(cli_theme="doom", env={}) == "doom")
    ctx.check("persisted game theme resolves without truecolor",
              theme_mod.resolve_theme(env={"TERM": "xterm"}, persisted_theme="mario") == "mario")


# ---- the pure contract, parametrised over all three ---------------------------

@test
def test_toggle_on_remembers_previous_and_off_restores_it(ctx: Ctx):
    for game in GAMES:
        with _scoped():
            applied = tt.toggle_game_theme(game, "claude-light-ansi")
            ctx.check(f"{game}: toggling on applies it", applied == game)
            ctx.check(f"{game}: persisted as theme", _cfg()["theme"] == game)
            ctx.check(f"{game}: previous remembered", _cfg()[tt.PREVIOUS_KEY] == "claude-light-ansi")
            back = tt.toggle_game_theme(game, game)
            ctx.check(f"{game}: toggling again restores the previous, got {back!r}", back == "claude-light-ansi")
            ctx.check(f"{game}: persisted theme is the restored one", _cfg()["theme"] == "claude-light-ansi")
            ctx.check(f"{game}: the previous key is cleared", tt.PREVIOUS_KEY not in _cfg())


@test
def test_toggle_off_without_a_previous_falls_back_to_claude_dark(ctx: Ctx):
    for game in GAMES:
        for junk in (None, "not-a-theme", 42, "doom", "mario"):
            with _scoped():
                theme_mod.set_config_value("theme", game)
                if junk is not None:
                    theme_mod.set_config_value(tt.PREVIOUS_KEY, junk)
                back = tt.toggle_game_theme(game, game)
                ctx.check(f"{game}/previous={junk!r}: falls back to claude-dark, got {back!r}", back == "claude-dark")
                ctx.check(f"{game}/previous={junk!r}: key cleared", tt.PREVIOUS_KEY not in _cfg())


@test
def test_game_to_game_keeps_the_original_previous(ctx: Ctx):
    for first, second in itertools.permutations(GAMES, 2):
        with _scoped():
            tt.toggle_game_theme(first, "claude-light")
            applied = tt.toggle_game_theme(second, first)
            ctx.check(f"/{first} then /{second}: second is applied", applied == second and _cfg()["theme"] == second)
            ctx.check(f"/{first} then /{second}: previous is still claude-light",
                      _cfg()[tt.PREVIOUS_KEY] == "claude-light")
            back = tt.toggle_game_theme(second, second)
            ctx.check(f"/{first} /{second} /{second} lands on what was active before /{first}, got {back!r}",
                      back == "claude-light")


@test
def test_explicit_theme_command_records_and_clears_the_previous(ctx: Ctx):
    for game in GAMES:
        with _scoped():
            tt.select_theme(game, "claude-dark-ansi")
            ctx.check(f"/theme {game} from a normal theme records it", _cfg()[tt.PREVIOUS_KEY] == "claude-dark-ansi")
            other = next(g for g in GAMES if g != game)
            tt.select_theme(other, game)
            ctx.check(f"/theme {other} while {game} is active keeps the original previous",
                      _cfg()[tt.PREVIOUS_KEY] == "claude-dark-ansi" and _cfg()["theme"] == other)
            tt.select_theme("claude-light", other)
            ctx.check("/theme <normal> from a game theme clears the stale previous",
                      tt.PREVIOUS_KEY not in _cfg() and _cfg()["theme"] == "claude-light")
            tt.select_theme(game, "claude-light")
            back = tt.toggle_game_theme(game, game)
            ctx.check(f"/theme {game} then /{game} returns to claude-light, got {back!r}", back == "claude-light")


@test
def test_state_survives_a_relaunch_and_other_keys_survive_the_toggle(ctx: Ctx):
    for game in GAMES:
        with _scoped():
            theme_mod.set_config_value("model", "or:demo/atlas-pro")
            theme_mod.set_config_value("improve.model", "or:demo/x")
            tt.toggle_game_theme(game, "claude-light")
            # a "relaunch": nothing in memory, only the file
            launched = theme_mod.resolve_theme(env={"TERM": "xterm"}, persisted_theme=theme_mod.load_persisted_theme())
            ctx.check(f"{game}: the next launch starts in {game}, got {launched!r}", launched == game)
            ctx.check(f"{game}: the remembered previous is readable after relaunch",
                      theme_mod.get_config_value(tt.PREVIOUS_KEY) == "claude-light")
            back = tt.toggle_game_theme(game, launched)
            ctx.check(f"{game}: toggle after relaunch restores, got {back!r}", back == "claude-light")
            ctx.check("model survived", _cfg()["model"] == "or:demo/atlas-pro")
            ctx.check("nested improve.model survived", _cfg()["improve"]["model"] == "or:demo/x")


@test
def test_a_non_theme_toggle_target_is_rejected(ctx: Ctx):
    with _scoped():
        raised = False
        try:
            tt.toggle_game_theme("claude-dark", "claude-light")
        except ValueError:
            raised = True
        ctx.check("only the three game names toggle", raised)
        ctx.check("nothing was written", _cfg() == {})


# ---- the headless forms ---------------------------------------------------------

@test
def test_headless_slash_commands_follow_the_same_contract(ctx: Ctx):
    from halo_harness.commands.builtins import _BUILTIN_SPECS, HeadlessFacade
    for game in GAMES:
        with _scoped():
            ctx.check(f"/{game} is a registered built-in", game in _BUILTIN_SPECS)
            run = _BUILTIN_SPECS[game][3]
            ctx.check(f"/{game} has a one-line description", len(_BUILTIN_SPECS[game][1]) > 20)
            facade = HeadlessFacade(cwd=Path("."), theme="claude-light")
            out = run("", facade)
            ctx.check(f"/{game} headless applies it: {out!r}", game in out and _cfg()["theme"] == game)
            facade2 = HeadlessFacade(cwd=Path("."), theme=game)
            out2 = run("", facade2)
            ctx.check(f"/{game} headless again restores: {out2!r}", "claude-light" in out2 and _cfg()["theme"] == "claude-light")
            theme_cmd = _BUILTIN_SPECS["theme"][3]
            ctx.check("/theme <game> headless is accepted", "Theme set to" in theme_cmd(game, HeadlessFacade(cwd=Path("."), theme="claude-dark")))
            ctx.check("... and records the previous", _cfg().get(tt.PREVIOUS_KEY) == "claude-dark")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
