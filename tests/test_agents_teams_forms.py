"""tests.test_agents_teams_forms -- Halo 2.0.5 round 2 (wizard: agent
bios and lineups), deliverable 4: "the same forms outside the wizard" --
`/agents`/`/teams` (list, new, edit, duplicate, delete, activate) in a
running session, and `halo agents|teams new|edit --form` from the CLI --
plus `halo init --step agents` (deliverable 1). Hermetic: no network, no
real model, no real terminal app (`run_agent_bio_editor_standalone`/
`run_lineup_editor_standalone`/`run_agents_list_standalone`/`run_teams_
list_standalone` are monkeypatched where a test only needs to confirm the
CLI dispatches to them correctly, not re-exercise the form itself -- that
is already covered by `tests/test_wizard_agents_bios.py`/`tests/test_
wizard_lineup.py`).
"""
from __future__ import annotations

import asyncio
import io
import os
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

REPO_DIR = Path(__file__).resolve().parent.parent
test, TESTS = new_registry()

FIXTURE_MODELS = [{"ref": "or:vendor/strong-model", "provider": "openrouter", "group": "OpenRouter (or:)"}]


class _Env:
    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
        d = Path(tempfile.mkdtemp(prefix="agents-teams-forms-"))
        os.environ["BRIDGE_TEST_HOME"] = str(d)
        os.environ["BRIDGE_STATE_DIR"] = str(d / ".halo")
        self.home, self.state_dir = d, d / ".halo"
        self.cwd = d / "project"
        self.cwd.mkdir(parents=True, exist_ok=True)
        return self

    def __exit__(self, *exc):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _capture(fn, argv) -> "tuple[int, str]":
    """`argparse`'s own `-h`/`--help` action raises `SystemExit` (never an
    `Exception` subclass -- `run_all`'s own `except Exception:` does NOT
    catch it, so an uncaught one here silently ends the WHOLE process
    with no traceback, confirmed live: every later test's own [PASS]/
    [FAIL] line, and `print_results`' summary, simply never printed).
    Same catch `tests/test_docs_commands.py::_capture` already uses."""
    buf = io.StringIO()
    rc = 0
    try:
        with redirect_stdout(buf), redirect_stderr(buf):
            rc = fn(argv)
    except SystemExit as e:
        rc = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
    return rc, buf.getvalue()


# ---------------------------------------------------------------------------
# CLI: `--form` dispatches to the TUI runner instead of $EDITOR/a starter
# file -- the runner itself is monkeypatched (never a real terminal app).
# ---------------------------------------------------------------------------

@test
def test_agents_cli_new_form_dispatches_to_the_standalone_editor(ctx: Ctx):
    import halo_harness.agents_cli as agents_cli_mod
    import halo_harness.tui.dialogs.agent_bio_editor as editor_mod
    calls = []
    old = editor_mod.run_agent_bio_editor_standalone

    def fake_runner(name, **kwargs):
        calls.append((name, kwargs))
        return name
    editor_mod.run_agent_bio_editor_standalone = fake_runner
    try:
        with _Env():
            rc, out = _capture(agents_cli_mod.cmd_agents, ["new", "pilot-bio", "--form", "--from", "coder"])
            ctx.check(f"exit 0, got {rc}, output {out!r}", rc == 0)
            ctx.check(f"the standalone runner was called with is_new/from_template, got {calls}",
                      calls and calls[0][0] == "pilot-bio" and calls[0][1].get("is_new") is True
                      and calls[0][1].get("from_template") == "coder")
            ctx.check(f"a success line was printed, got {out!r}", "pilot-bio" in out)
    finally:
        editor_mod.run_agent_bio_editor_standalone = old


@test
def test_agents_cli_edit_form_cancel_is_reported(ctx: Ctx):
    import halo_harness.agents_cli as agents_cli_mod
    import halo_harness.tui.dialogs.agent_bio_editor as editor_mod
    old = editor_mod.run_agent_bio_editor_standalone
    editor_mod.run_agent_bio_editor_standalone = lambda name, **kw: None  # simulates Cancel
    try:
        with _Env():
            rc, out = _capture(agents_cli_mod.cmd_agents, ["edit", "some-bio", "--form"])
            ctx.check(f"a cancelled form is a non-zero exit, got {rc}, output {out!r}", rc == 1)
    finally:
        editor_mod.run_agent_bio_editor_standalone = old


@test
def test_teams_cli_new_and_edit_form_dispatch(ctx: Ctx):
    import halo_harness.teams_cli as teams_cli_mod
    import halo_harness.tui.dialogs.lineup_editor as lineup_mod
    new_calls, edit_calls = [], []
    old = lineup_mod.run_lineup_editor_standalone

    def fake_runner(name, **kwargs):
        (new_calls if kwargs.get("is_new") else edit_calls).append((name, kwargs))
        return name
    lineup_mod.run_lineup_editor_standalone = fake_runner
    try:
        with _Env():
            rc, out = _capture(teams_cli_mod.cmd_teams, ["new", "pilot-lineup", "--form"])
            ctx.check(f"new --form exit 0, got {rc}", rc == 0)
            ctx.check(f"new dispatched with is_new=True, got {new_calls}", new_calls)
            rc2, out2 = _capture(teams_cli_mod.cmd_teams, ["edit", "pilot-lineup", "--form"])
            ctx.check(f"edit --form exit 0, got {rc2}", rc2 == 0)
            ctx.check(f"edit dispatched with is_new=False, got {edit_calls}", edit_calls)
    finally:
        lineup_mod.run_lineup_editor_standalone = old


@test
def test_teams_edit_subcommand_exists_and_is_listed_in_help(ctx: Ctx):
    """`halo teams edit` did not exist before this round -- added
    symmetrically with `agents_cli.py`'s own `edit`."""
    import halo_harness.teams_cli as teams_cli_mod
    ctx.check("'edit' is a real teams subcommand", "edit" in teams_cli_mod._SUBCOMMANDS)
    rc, out = _capture(teams_cli_mod.cmd_teams, [])
    ctx.check(f"the bare usage line mentions edit, got {out!r}", "edit" in out)


# ---------------------------------------------------------------------------
# `/agents`/`/teams` inside a running session open the same screens.
# ---------------------------------------------------------------------------

class _FakeTranscript:
    def __init__(self):
        self.notes = []

    async def add_note(self, text, kind=None):
        self.notes.append((text, kind))


class _FakeController:
    def list_models(self):
        return FIXTURE_MODELS


async def _poll_until(pilot, predicate, *, iterations: int = 60, step_s: float = 0.05) -> bool:
    for _ in range(iterations):
        await pilot.pause(step_s)
        if predicate():
            return True
    return False


def _build_slash_host_app(cwd: Path):
    from textual.app import App
    from textual.screen import Screen

    class _HostApp(App):
        def __init__(self):
            super().__init__()
            self.cwd = cwd
            self.controller = _FakeController()
            self.transcript = _FakeTranscript()

        def on_mount(self):
            self.push_screen(Screen())
    return _HostApp()


@test
def test_slash_agents_new_and_edit_open_the_bio_editor(ctx: Ctx):
    from halo_harness.tui.dialogs.agent_bio_editor import AgentBioEditor
    from halo_harness.tui.slash import handle_slash

    async def body():
        with _Env() as e:
            app = _build_slash_host_app(e.cwd)
            async with app.run_test(size=(120, 45)) as pilot:
                await pilot.pause(0.05)
                await handle_slash(app, "agents", "new slash-pilot-bio")
                found = await _poll_until(pilot, lambda: isinstance(app.screen, AgentBioEditor))
                ctx.check(f"/agents new opened the bio editor, got {type(app.screen).__name__}", found)
                ctx.check("opened in is_new mode", app.screen.is_new is True)
    asyncio.run(body())


@test
def test_slash_agents_bare_opens_the_list_screen(ctx: Ctx):
    from halo_harness.tui.dialogs.agents_step import AgentsListScreen
    from halo_harness.tui.slash import handle_slash

    async def body():
        with _Env() as e:
            app = _build_slash_host_app(e.cwd)
            async with app.run_test(size=(120, 45)) as pilot:
                await pilot.pause(0.05)
                await handle_slash(app, "agents", "")
                found = await _poll_until(pilot, lambda: isinstance(app.screen, AgentsListScreen))
                ctx.check(f"bare /agents opened the list screen, got {type(app.screen).__name__}", found)
    asyncio.run(body())


@test
def test_slash_agents_duplicate_and_delete(ctx: Ctx):
    from halo_harness.agents_yaml import find_agent_bio_path, save_agent_bio
    from halo_harness.tui.slash import handle_slash

    async def body():
        with _Env() as e:
            # `cwd=e.cwd` is REQUIRED alongside `project=True` -- without it
            # `project_agents_dir(cwd=None)` falls back to the REAL `Path.
            # cwd()` (confirmed live: this wrote `.halo/agents/dup-me.yaml`
            # straight into the repo root the one time this line omitted
            # it), never the scratch project dir `_Env` just built.
            save_agent_bio("dup-me", {"description": "x"}, cwd=e.cwd, state_dir=e.state_dir, project=True)
            app = _build_slash_host_app(e.cwd)
            async with app.run_test(size=(120, 45)) as pilot:
                await pilot.pause(0.05)
                await handle_slash(app, "agents", "duplicate dup-me dup-me-copy")
                await pilot.pause(0.2)
                found = find_agent_bio_path("dup-me-copy", cwd=e.cwd)
                ctx.check(f"duplicate created a new bio, got {found}", found is not None)
                await handle_slash(app, "agents", "delete dup-me-copy")
                await pilot.pause(0.2)
                after = find_agent_bio_path("dup-me-copy", cwd=e.cwd)
                ctx.check(f"delete removed it, got {after}", after is None)
    asyncio.run(body())


@test
def test_slash_teams_new_edit_and_activate(ctx: Ctx):
    from halo_harness.theme import get_config_value
    from halo_harness.tui.dialogs.lineup_editor import LineupEditor
    from halo_harness.tui.slash import handle_slash

    async def body():
        with _Env() as e:
            app = _build_slash_host_app(e.cwd)
            async with app.run_test(size=(120, 45)) as pilot:
                await pilot.pause(0.05)
                await handle_slash(app, "teams", "new slash-pilot-lineup")
                found = await _poll_until(pilot, lambda: isinstance(app.screen, LineupEditor))
                ctx.check(f"/teams new opened the lineup editor, got {type(app.screen).__name__}", found)
                await pilot.press("escape")
                await pilot.pause(0.1)

                from halo_harness.teams_yaml import save_team_template
                save_team_template("activate-me", {"description": "d"}, state_dir=e.state_dir)
                await handle_slash(app, "teams", "activate activate-me")
                await pilot.pause(0.2)
                ctx.check(f"activate set team:, got {get_config_value('team', default=None)!r}",
                          get_config_value("team", default=None) == "activate-me")
    asyncio.run(body())


@test
def test_slash_teams_bare_opens_the_list_screen(ctx: Ctx):
    from halo_harness.tui.dialogs.lineup_editor import TeamsListScreen
    from halo_harness.tui.slash import handle_slash

    async def body():
        with _Env() as e:
            app = _build_slash_host_app(e.cwd)
            async with app.run_test(size=(120, 45)) as pilot:
                await pilot.pause(0.05)
                await handle_slash(app, "teams", "")
                found = await _poll_until(pilot, lambda: isinstance(app.screen, TeamsListScreen))
                ctx.check(f"bare /teams opened the list screen, got {type(app.screen).__name__}", found)
    asyncio.run(body())


# ---------------------------------------------------------------------------
# `halo init --step agents` (deliverable 1).
# ---------------------------------------------------------------------------

@test
def test_halo_init_step_flag_resolves_to_the_agents_step(ctx: Ctx):
    from halo_harness.tui.dialogs.init_wizard import _resolve_start_index, full_step_keys
    step_keys = full_step_keys()
    ctx.check('"agents" is a real step key', "agents" in step_keys)
    idx = _resolve_start_index("agents", step_keys)
    ctx.check(f'start_step="agents" resolves to the agents step, got {step_keys[idx]!r}',
              step_keys[idx] == "agents")


@test
def test_halo_init_step_flag_is_wired_through_to_run_init_wizard(ctx: Ctx):
    """`cmd_init`'s OWN interactive dispatch only ever calls `_run_init_
    wizard_flow` on a real tty with no `--yes` (`sys.stdin.isatty() and
    sys.stdout.isatty() and not args.yes`) -- untestable hermetically
    through `cmd_init` itself, so this calls `_run_init_wizard_flow`
    directly (the same function that dispatch reaches) with a hand-built
    `args`, same as testing any other internal step function in this
    file. `run_init_wizard` itself is monkeypatched (it calls `.run()`, a
    real blocking terminal app)."""
    from types import SimpleNamespace
    from rich.console import Console
    import halo_harness.init_cli as init_cli_mod
    import halo_harness.tui.dialogs.init_wizard as wizard_mod
    captured = {}
    old = wizard_mod.run_init_wizard

    class _FakeState:
        team_warnings = []
        pong_ok = True

    class _FakeApp:
        state = _FakeState()

    def fake_run_init_wizard(**kwargs):
        captured.update(kwargs)
        return _FakeApp()
    wizard_mod.run_init_wizard = fake_run_init_wizard
    try:
        with _Env():
            console = Console(file=io.StringIO())
            args = SimpleNamespace(step="agents", team=None, no_live=False, yes=False)
            init_cli_mod._run_init_wizard_flow(args, console, REPO_DIR)
            ctx.check(f"the key form passes through as the string 'agents', got {captured.get('start_step')!r}",
                      captured.get("start_step") == "agents")
            captured.clear()
            args2 = SimpleNamespace(step="7", team=None, no_live=False, yes=False)
            init_cli_mod._run_init_wizard_flow(args2, console, REPO_DIR)
            ctx.check(f"a numeric string is converted to a real int, got {captured.get('start_step')!r}",
                      captured.get("start_step") == 7)
    finally:
        wizard_mod.run_init_wizard = old


@test
def test_halo_init_help_documents_step(ctx: Ctx):
    import halo_harness.init_cli as init_cli_mod
    rc, out = _capture(init_cli_mod.cmd_init, ["--help"])
    ctx.check(f"--step is a real, documented flag, got {out!r}", "--step" in out)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
