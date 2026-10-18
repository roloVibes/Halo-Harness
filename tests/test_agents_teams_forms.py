"""tests.test_agents_teams_forms -- Halo 2.0.5 round 2 (wizard: agent
bios and lineups), deliverable 4: `/agents`/`/teams` (list, new, edit,
view, duplicate, delete, activate) in a running session, `/edit`, and
`halo agents|teams new|edit` from the CLI -- plus `halo init --step agents`
(deliverable 1). 3.1.1.0 R3: Studio is the one editor of bios and lineups:
`edit` (and `new --studio`, `/agents new`) open Studio on the thing, `view`
shows it read-only in the terminal. Hermetic: no network, no real model,
no Studio started (`studio_edit_cli.open_in_studio` and
`tui.studio_open.OPENER` record what would open).
"""
from __future__ import annotations

TIER = "full"  # a TUI pilot (Textual run_test): the full tier

import asyncio
import contextlib
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
# CLI: `edit` and `new --studio` open Studio (3.1.1.0 R3) -- the opener is
# monkeypatched (no Studio, no browser).
# ---------------------------------------------------------------------------

@contextlib.contextmanager
def _studio_calls():
    """`studio_edit_cli.open_in_studio` recorded instead of reaching a Studio (3.1.1.0 R3)."""
    import halo_harness.studio_edit_cli as mod
    calls, old = [], mod.open_in_studio
    mod.open_in_studio = lambda kind, name, **kw: calls.append((kind, name, kw.get("no_open"))) or 0
    try:
        yield calls
    finally:
        mod.open_in_studio = old


@test
def test_agents_cli_new_studio_opens_the_new_bio_in_studio(ctx: Ctx):
    """3.1.1.0 R3: `halo agents new <name> --studio` writes the starter bio, then opens Studio on it."""
    import halo_harness.agents_cli as agents_cli_mod
    with _Env() as e, _studio_calls() as calls:
        rc, out = _capture(agents_cli_mod.cmd_agents, ["new", "pilot-bio", "--studio", "--from", "coder"])
        ctx.check(f"exit 0, got {rc}, output {out!r}", rc == 0 and "Created agent 'pilot-bio' from 'coder'" in out)
        ctx.check(f"Studio opened on it, got {calls}", calls == [("bio", "pilot-bio", False)])
        ctx.check("the starter file is the shipped bio's copy", (e.state_dir / "agents" / "pilot-bio.yaml").is_file())
        rc, out = _capture(agents_cli_mod.cmd_agents, ["new", "other-bio", "--form"])
        ctx.check(f"--form is gone (the TUI form is), got {rc}", rc == 2)


@test
def test_agents_cli_edit_opens_studio_on_the_bio(ctx: Ctx):
    """3.1.1.0 R3: `halo agents edit <name>` opens Studio on it (a missing bio gets a starter file first);
    `--no-open` is passed through."""
    import halo_harness.agents_cli as agents_cli_mod
    with _Env() as e, _studio_calls() as calls:
        rc, out = _capture(agents_cli_mod.cmd_agents, ["edit", "some-bio", "--no-open"])
        ctx.check(f"exit 0, got {rc}, output {out!r}", rc == 0 and "Created agent 'some-bio'" in out)
        ctx.check(f"Studio, --no-open passed through, got {calls}", calls == [("bio", "some-bio", True)])
        ctx.check("the starter file exists", (e.state_dir / "agents" / "some-bio.yaml").is_file())


@test
def test_teams_cli_new_and_edit_open_studio_on_the_lineup(ctx: Ctx):
    import halo_harness.teams_cli as teams_cli_mod
    with _Env(), _studio_calls() as calls:
        rc, out = _capture(teams_cli_mod.cmd_teams, ["new", "pilot-lineup", "--studio"])
        ctx.check(f"new --studio exit 0, got {rc} {out!r}", rc == 0 and "Created lineup 'pilot-lineup'" in out)
        rc2, out2 = _capture(teams_cli_mod.cmd_teams, ["edit", "pilot-lineup"])
        ctx.check(f"edit exit 0, got {rc2} {out2!r}", rc2 == 0)
        ctx.check(f"both opened Studio on the lineup, got {calls}",
                  calls == [("lineup", "pilot-lineup", False), ("lineup", "pilot-lineup", False)])


@test
def test_teams_edit_subcommand_exists_and_is_listed_in_help(ctx: Ctx):
    """`halo teams edit` did not exist before this round -- added
    symmetrically with `agents_cli.py`'s own `edit`."""
    import halo_harness.teams_cli as teams_cli_mod
    ctx.check("'edit' is a real teams subcommand", "edit" in teams_cli_mod._SUBCOMMANDS)
    rc, out = _capture(teams_cli_mod.cmd_teams, ["--help"])
    ctx.check(f"the usage line mentions edit, got {out!r}", "edit" in out)


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

    def run_slash(self, name, args):
        """The headless builtin the real controller falls through to."""
        from halo_harness.commands.builtins import HeadlessFacade, _BUILTIN_SPECS
        return _BUILTIN_SPECS[name][3](args, HeadlessFacade(cwd=Path.cwd()))


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


class _Opened:
    """`tui.studio_open.OPENER` for a test (3.1.1.0 R3): records each target, answers as a focused Studio."""

    def __enter__(self):
        from halo_harness.tui import studio_open
        self.mod, self.old, self.targets = studio_open, studio_open.OPENER, []
        studio_open.OPENER = lambda target, **_kw: self.targets.append(target.text) or {
            "url": f"http://127.0.0.1:1/{target.query()}#t=x", "how": "focused", "pages": 1, "target": target.text}
        return self

    def __exit__(self, *exc):
        self.mod.OPENER = self.old


@test
def test_slash_agents_new_edit_view_and_slash_edit(ctx: Ctx):
    """3.1.1.0 R3: `/agents new <name>` writes the starter bio and opens Studio on it, `/agents edit`
    opens Studio, `/agents view` shows the bio read-only; `/edit` takes a target or a bare name."""
    from halo_harness.tui.dialogs.agent_bio_editor import AgentBioView
    from halo_harness.tui.slash import handle_slash

    async def body():
        with _Env() as e, _Opened() as opened:
            app = _build_slash_host_app(e.cwd)
            async with app.run_test(size=(120, 45)) as pilot:
                await pilot.pause(0.05)
                await handle_slash(app, "agents", "new slash-pilot-bio")
                await _poll_until(pilot, lambda: opened.targets)
                ctx.check(f"/agents new opened Studio on the new bio, got {opened.targets}", opened.targets == ["bio:slash-pilot-bio"])
                from halo_harness.agents_yaml import find_agent_bio_path
                ctx.check("and wrote its starter file", find_agent_bio_path("slash-pilot-bio", cwd=e.cwd) is not None)
                await _poll_until(pilot, lambda: any("Opened bio:slash-pilot-bio" in n for n, _k in app.transcript.notes))
                ctx.check(f"the transcript says what opened, got {app.transcript.notes!r}",
                          any("Opened bio:slash-pilot-bio" in n for n, _k in app.transcript.notes))
                await handle_slash(app, "agents", "edit coder")
                await _poll_until(pilot, lambda: len(opened.targets) == 2)
                ctx.check(f"/agents edit opens Studio on it, got {opened.targets}", opened.targets[-1] == "bio:coder")
                await handle_slash(app, "edit", "lineup:balanced")
                await _poll_until(pilot, lambda: len(opened.targets) == 3)
                ctx.check(f"/edit lineup:<name>, got {opened.targets}", opened.targets[-1] == "lineup:balanced")
                await handle_slash(app, "edit", "reviewer")
                await _poll_until(pilot, lambda: len(opened.targets) == 4)
                ctx.check(f"/edit <bare bio name>, got {opened.targets}", opened.targets[-1] == "bio:reviewer")
                await handle_slash(app, "edit", "team")
                await _poll_until(pilot, lambda: len(opened.targets) == 5)
                ctx.check(f"/edit team, got {opened.targets}", opened.targets[-1] == "team")
                await handle_slash(app, "edit", "no-such-thing")
                await _poll_until(pilot, lambda: any("no bio or lineup named" in n for n, _k in app.transcript.notes))
                ctx.check("an unknown name says so and opens nothing", len(opened.targets) == 5
                          and any("no bio or lineup named 'no-such-thing'" in n for n, _k in app.transcript.notes))
                await handle_slash(app, "agents", "view coder")
                found = await _poll_until(pilot, lambda: isinstance(app.screen, AgentBioView))
                ctx.check(f"/agents view shows the bio read-only, got {type(app.screen).__name__}", found)
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
def test_slash_teams_new_edit_view_and_activate(ctx: Ctx):
    from halo_harness.theme import get_config_value
    from halo_harness.tui.dialogs.lineup_editor import LineupView
    from halo_harness.tui.slash import handle_slash

    async def body():
        with _Env() as e, _Opened() as opened:
            app = _build_slash_host_app(e.cwd)
            async with app.run_test(size=(120, 45)) as pilot:
                await pilot.pause(0.05)
                await handle_slash(app, "teams", "new slash-pilot-lineup")
                await _poll_until(pilot, lambda: opened.targets)
                ctx.check(f"/teams new opened Studio on the new lineup, got {opened.targets}",
                          opened.targets == ["lineup:slash-pilot-lineup"])
                await handle_slash(app, "teams", "edit slash-pilot-lineup")
                await _poll_until(pilot, lambda: len(opened.targets) == 2)
                ctx.check(f"/teams edit opens Studio on it, got {opened.targets}", opened.targets[-1] == "lineup:slash-pilot-lineup")
                await handle_slash(app, "teams", "view slash-pilot-lineup")
                found = await _poll_until(pilot, lambda: isinstance(app.screen, LineupView))
                ctx.check(f"/teams view shows it read-only, got {type(app.screen).__name__}", found)
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
def test_slash_teams_bare_prints_overview_and_apply_preview_work(ctx: Ctx):
    from halo_harness.roles import roles_mode_enabled
    from halo_harness.theme import get_config_value
    from halo_harness.tui.dialogs.teams_list import TeamsListScreen
    from halo_harness.tui.slash import handle_slash

    async def body():
        with _Env() as e:
            app = _build_slash_host_app(e.cwd)
            async with app.run_test(size=(120, 45)) as pilot:
                await pilot.pause(0.05)
                await handle_slash(app, "teams", "")
                found = await _poll_until(pilot, lambda: bool(app.transcript.notes))
                ctx.check(f"bare /teams printed the overview note, got {app.transcript.notes!r}",
                          found and "No lineup applied yet" in app.transcript.notes[-1][0])
                ctx.check("and did not open the list screen", not isinstance(app.screen, TeamsListScreen))
                await handle_slash(app, "teams", "preview halo-dev-cycle")
                found = await _poll_until(pilot, lambda: len(app.transcript.notes) >= 2)
                ctx.check(f"/teams preview printed the tree, got {app.transcript.notes!r}",
                          found and "main (boss) -> orchestrator" in app.transcript.notes[-1][0])
                await handle_slash(app, "teams", "apply halo-dev-cycle")
                found = await _poll_until(pilot, lambda: len(app.transcript.notes) >= 3)
                ctx.check(f"/teams apply printed the roles, got {app.transcript.notes!r}",
                          found and "Lineup: halo-dev-cycle" in app.transcript.notes[-1][0])
                ctx.check("and wrote team: and turned roles on",
                          get_config_value("team", default=None) == "halo-dev-cycle" and roles_mode_enabled())
    asyncio.run(body())


@test
def test_slash_teams_bare_opens_the_list_screen(ctx: Ctx):
    from halo_harness.tui.dialogs.teams_list import TeamsListScreen
    from halo_harness.tui.slash import handle_slash

    async def body():
        with _Env() as e:
            app = _build_slash_host_app(e.cwd)
            async with app.run_test(size=(120, 45)) as pilot:
                await pilot.pause(0.05)
                await handle_slash(app, "teams", "list")
                found = await _poll_until(pilot, lambda: isinstance(app.screen, TeamsListScreen))
                ctx.check(f"/teams list opened the list screen, got {type(app.screen).__name__}", found)
    asyncio.run(body())


# ---------------------------------------------------------------------------
# `halo init --step agents` (deliverable 1).
# ---------------------------------------------------------------------------

@test
def test_halo_init_step_flag_resolves_to_the_team_step(ctx: Ctx):
    """2.0.5 round 2c merged the Agents step and the Roles step into one
    "team" step; `--step agents` and `--step roles` stay as aliases that
    land on it."""
    from halo_harness.tui.dialogs.init_wizard import _resolve_start_index, full_step_keys
    step_keys = full_step_keys()
    ctx.check('"team" is a real step key', "team" in step_keys)
    for alias in ("team", "agents", "roles"):
        idx = _resolve_start_index(alias, step_keys)
        ctx.check(f'start_step={alias!r} resolves to the team step, got {step_keys[idx]!r}',
                  step_keys[idx] == "team")


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
