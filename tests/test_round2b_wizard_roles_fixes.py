"""tests.test_round2b_wizard_roles_fixes -- Halo 2.0.5 round 2b (`plans/
briefs/2.0.5/round-2b-wizard-roles-fixes.md`): the owner's bug reports on
round 2 --

1. Roles on/off is one switch, everywhere.
2. The shipped `standard` lineup (the `default` model reference).
3. Bio editor layout (model fields visible on open at 80x24).
4. Bio editor model picking -- root cause: Ctrl+P was stolen by
   Textual's own command palette, never the enumeration or the filter.
5. The bug sweep (Enter-does-the-obvious-thing, focus on open, a plain
   Next applies the highlighted lineup).

Hermetic: no network, no real model -- every pilot passes a FIXTURE
catalog directly and scopes `BRIDGE_TEST_HOME`/`BRIDGE_STATE_DIR` to a
fresh scratch dir per `plans/WORKER-RULES.md`.
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

REPO_DIR = Path(__file__).resolve().parent.parent
test, TESTS = new_registry()

FIXTURE_MODELS = [
    {"ref": "or:vendor/strong-model", "provider": "openrouter", "group": "OpenRouter (or:)",
     "context_tokens": 128000, "price_in_per_m": 1.0, "price_out_per_m": 2.0,
     "supported_parameters": ["tools"]},
    {"ref": "or:vendor/cheap-model", "provider": "openrouter", "group": "OpenRouter (or:)",
     "context_tokens": 8000, "price_in_per_m": 0.1, "price_out_per_m": 0.2,
     "supported_parameters": ["reasoning"]},
]
# Every fixture row declares "reasoning" only, never "tools" -- the row
# the empty-filter-fallback pilot needs (a tool-needing bio that NO
# fixture row can satisfy).
NO_TOOLS_MODELS = [
    {"ref": "or:vendor/no-tools", "provider": "openrouter", "group": "OpenRouter (or:)",
     "context_tokens": 8000, "price_in_per_m": 0.1, "price_out_per_m": 0.2,
     "supported_parameters": ["reasoning"]},
]

SIZES = ((80, 24), (120, 40))


class _Env:
    """Scratch `BRIDGE_TEST_HOME`/`BRIDGE_STATE_DIR` -- the real `~/.halo`
    is never touched (same pattern `tests/test_wizard_agents_bios.py::
    _Env` already uses)."""

    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
        d = Path(tempfile.mkdtemp(prefix="round2b-"))
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


def _static_text(widget) -> str:
    return str(widget.renderable) if hasattr(widget, "renderable") else str(widget.render())


def run(coro) -> None:
    asyncio.run(coro)


# ---------------------------------------------------------------------------
# Deliverable 1: roles on/off is one switch -- pure/CLI/slash.
# ---------------------------------------------------------------------------

@test
def test_set_roles_enabled_and_state_line_off_on_and_with_a_lineup(ctx: Ctx):
    from halo_harness.roles import roles_mode_enabled, roles_state_line, set_roles_enabled
    from halo_harness.theme import set_config_value
    with _Env():
        set_roles_enabled(False)
        ctx.check("roles_mode_enabled reflects off", roles_mode_enabled() is False)
        ctx.check(f'off line matches the brief, got {roles_state_line()!r}',
                  roles_state_line() == "roles: off (standard: every role uses the default model)")
        set_roles_enabled(True)
        ctx.check("roles_mode_enabled reflects on", roles_mode_enabled() is True)
        ctx.check(f'on-with-no-lineup line, got {roles_state_line()!r}',
                  roles_state_line() == "roles: on (legacy role table)")
        set_config_value("team", "my-lineup")
        ctx.check(f'on-with-a-lineup names it, got {roles_state_line()!r}',
                  roles_state_line() == "roles: on (lineup my-lineup)")


@test
def test_apply_role_template_turns_roles_on(ctx: Ctx):
    """The owner's own weak-spot report: "load <name> writes the role
    mappings but does NOT set roles.enabled: true"."""
    from halo_harness.roles import apply_role_template, roles_mode_enabled, save_role_template, set_roles_enabled
    with _Env() as e:
        save_role_template("pilot-template", {"description": "d", "roles": {"coder": "or:vendor/strong-model"}},
                            state_dir=e.state_dir)
        set_roles_enabled(False)
        ctx.check("starts off", roles_mode_enabled() is False)
        ok, problems = apply_role_template("pilot-template", state_dir=e.state_dir)
        ctx.check(f"load succeeds, got {problems}", ok)
        ctx.check("loading a template turns roles ON", roles_mode_enabled() is True)


@test
def test_cli_halo_roles_on_off_and_bare_table_first_line(ctx: Ctx):
    import io
    from contextlib import redirect_stdout
    from halo_harness.roles_cli import cmd_roles
    with _Env():
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cmd_roles(["off"])
        ctx.check(f"halo roles off exits 0, got {rc}", rc == 0)
        ctx.check(f'prints the off line, got {buf.getvalue()!r}',
                  "roles: off (standard: every role uses the default model)" in buf.getvalue())
        buf2 = io.StringIO()
        with redirect_stdout(buf2):
            rc2 = cmd_roles(["on"])
        ctx.check(f"halo roles on exits 0, got {rc2}", rc2 == 0)
        ctx.check(f'prints the on line, got {buf2.getvalue()!r}', "roles: on" in buf2.getvalue())
        buf3 = io.StringIO()
        with redirect_stdout(buf3):
            rc3 = cmd_roles([])
        ctx.check(f"bare halo roles exits 0, got {rc3}", rc3 == 0)
        ctx.check(f'bare table FIRST line is the state line, got {buf3.getvalue()!r}',
                  buf3.getvalue().splitlines()[0].startswith("roles: on"))


@test
def test_slash_roles_on_off(ctx: Ctx):
    from halo_harness.commands.builtins import _cmd_roles
    from halo_harness.roles import roles_mode_enabled

    class _Facade:
        session = None
    with _Env():
        reply_off = _cmd_roles("off", _Facade())
        ctx.check(f"/roles off replies with the off line, got {reply_off!r}",
                  reply_off == "roles: off (standard: every role uses the default model)")
        ctx.check("roles are actually off now", roles_mode_enabled() is False)
        reply_on = _cmd_roles("on", _Facade())
        ctx.check(f"/roles on replies with an on line, got {reply_on!r}", reply_on.startswith("roles: on"))
        ctx.check("roles are actually on now", roles_mode_enabled() is True)


# ---------------------------------------------------------------------------
# Deliverable 2: the `standard` lineup / the `default` model reference.
# ---------------------------------------------------------------------------

@test
def test_default_reference_substitutes_the_session_default_model(ctx: Ctx):
    from halo_harness.agents_yaml import resolve_agent_bio, save_agent_bio
    from halo_harness.theme import set_config_value
    with _Env() as e:
        save_agent_bio("uses-default", {"description": "d", "models": {"preference": "default",
                                                                          "fallback": "default"}},
                        state_dir=e.state_dir)
        set_config_value("model", "or:vendor/alpha")
        bio = resolve_agent_bio("uses-default", state_dir=e.state_dir)
        ctx.check(f"preference resolves to the session default, got {bio['models']}",
                  bio["models"]["preference"] == "or:vendor/alpha" and bio["models"]["fallback"] == "or:vendor/alpha")
        set_config_value("model", "or:vendor/beta")
        bio2 = resolve_agent_bio("uses-default", state_dir=e.state_dir)
        ctx.check(f"a changed default is picked up the next resolve, got {bio2['models']}",
                  bio2["models"]["preference"] == "or:vendor/beta")


@test
def test_default_reference_left_as_typed_with_no_session_default_configured(ctx: Ctx):
    from halo_harness.agents_yaml import resolve_agent_bio, save_agent_bio
    with _Env() as e:
        save_agent_bio("uses-default-bare", {"description": "d", "models": {"preference": "default"}},
                        state_dir=e.state_dir)
        bio = resolve_agent_bio("uses-default-bare", state_dir=e.state_dir)
        ctx.check(f'left as "default" (never silently emptied), got {bio["models"]}',
                  bio["models"]["preference"] == "default")


@test
def test_standard_lineup_resolves_every_role_to_the_default_and_follows_a_change(ctx: Ctx):
    """Tests section: "the standard lineup resolving every role to the
    configured default model and following a change of the default"."""
    from halo_harness.roles import ROLE_NAMES
    from halo_harness.teams_yaml import ensure_builtin_team_templates, resolve_role_table, resolve_team_template, \
        validate_team_template
    from halo_harness.theme import set_config_value
    with _Env() as e:
        ensure_builtin_team_templates(state_dir=e.state_dir)
        template = resolve_team_template("standard", state_dir=e.state_dir)
        ctx.check("the shipped standard lineup resolves", template is not None)
        ctx.check(f"it validates clean, got {validate_team_template(template, state_dir=e.state_dir)}",
                  validate_team_template(template, state_dir=e.state_dir) == [])
        set_config_value("model", "or:vendor/alpha")
        table, notes = resolve_role_table(resolve_team_template("standard", state_dir=e.state_dir),
                                           state_dir=e.state_dir)
        ctx.check(f"no roles left out, got notes={notes}", not notes)
        missing = [r for r in ROLE_NAMES if r not in table]
        ctx.check(f"every built-in role name is assigned, missing={missing}", not missing)
        ctx.check(f"every role equals the default model, got {table}",
                  all(v == "or:vendor/alpha" for v in table.values()))
        set_config_value("model", "or:vendor/beta")
        table2, _notes2 = resolve_role_table(resolve_team_template("standard", state_dir=e.state_dir),
                                              state_dir=e.state_dir)
        ctx.check(f"changing the default moves every role with it, got {table2}",
                  all(v == "or:vendor/beta" for v in table2.values()))


@test
def test_halo_teams_show_standard_explains_it_in_one_sentence(ctx: Ctx):
    import io
    from contextlib import redirect_stdout
    from halo_harness.teams_cli import cmd_teams
    with _Env():
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cmd_teams(["show", "standard"])
        ctx.check(f"exits 0, got {rc}", rc == 0)
        first_line = buf.getvalue().splitlines()[0]
        ctx.check(f"the description is a real sentence about the default model, got {first_line!r}",
                  "default" in first_line.lower())


# ---------------------------------------------------------------------------
# Deliverable 3: bio editor layout, at 80x24 AND 120x40.
# ---------------------------------------------------------------------------

@test
def test_bio_editor_name_description_kind_and_model_fields_visible_on_open(ctx: Ctx):
    """"the first rows (name, description, kind, the model fields) are
    visible on open at 80x24" -- and still at 120x40."""
    from halo_harness.tui.dialogs.agent_bio_editor import AgentBioEditor
    from textual.app import App

    async def body(w, h):
        with _Env():
            app_holder = {}

            class _Host(App):
                def on_mount(self):
                    app_holder["screen"] = AgentBioEditor("new-bio", {}, FIXTURE_MODELS, is_new=True)
                    self.push_screen(app_holder["screen"])
            app = _Host()
            async with app.run_test(size=(w, h)) as pilot:
                await pilot.pause(0.15)
                editor = app.screen
                pane = editor.query_one("#bio-form-pane")
                for wid in ("#bio-name", "#bio-description", "#bio-kind", "#bio-pref"):
                    w_ = editor.query_one(wid)
                    r, pr = w_.region, pane.region
                    visible = r.y >= pr.y and r.y + r.height <= pr.y + pr.height
                    ctx.check(f"{wid} is visible on open at {w}x{h} (no scroll needed), "
                              f"got widget={r} pane={pr}", visible)
    for size in SIZES:
        run(body(*size))


@test
def test_bio_editor_every_field_focusable_and_visible_when_focused(ctx: Ctx):
    from halo_harness.tui.dialogs.agent_bio_editor import AgentBioEditor
    from textual.app import App

    async def body(w, h):
        with _Env():
            app_holder = {}

            class _Host(App):
                def on_mount(self):
                    app_holder["screen"] = AgentBioEditor("new-bio", {}, FIXTURE_MODELS, is_new=True)
                    self.push_screen(app_holder["screen"])
            app = _Host()
            async with app.run_test(size=(w, h)) as pilot:
                await pilot.pause(0.15)
                pane = app.screen.query_one("#bio-form-pane")
                checked = 0
                for _ in range(26):
                    fw = app.focused
                    fid = getattr(fw, "id", None) or ""
                    if fid.startswith("bio-"):
                        checked += 1
                        r, pr = fw.region, pane.region
                        visible = r.y >= pr.y and r.y + r.height <= pr.y + pr.height
                        ctx.check(f"{fid} is visible when focused at {w}x{h}, got widget={r} pane={pr}", visible)
                    await pilot.press("tab")
                    await pilot.pause(0.02)
                ctx.check(f"at least a dozen bio- fields were actually tabbed through at {w}x{h}, got {checked}",
                          checked >= 12)
    for size in SIZES:
        run(body(*size))


# ---------------------------------------------------------------------------
# Deliverable 4: bio editor model picking -- the coordinator's own primary
# repro (Providers has enumerated -> Agents -> New bio -> Ctrl+P), at both
# sizes, through the REAL wizard flow (never hand-setting `state.
# enumerated_models` the way the round-2 tests do -- this is the exact gap
# that let the Ctrl+P/command-palette collision through unnoticed).
# ---------------------------------------------------------------------------

async def _wizard_to_agents_step(pilot, app, state):
    """Drives Providers' own `no_live` branch (a real, synchronous,
    cache-only `build_model_rows` call -- no network) with the fixture
    catalog monkeypatched in, then every step between it and "team"
    (round 2c: the merged step the old, now-gone "agents" step folded
    into), exactly as a real `halo init` run would -- the Team step's
    own `self.state.enumeration_done`/`enumerated_models` are therefore
    POPULATED BY THE REAL CODE PATH, never poked directly."""
    import halo_harness.providers.model_enumeration as me
    real = me.build_model_rows
    me.build_model_rows = lambda *a, **k: list(FIXTURE_MODELS)
    try:
        app.screen.action_do_next()  # Providers -> no_live branch
        await pilot.pause(0.2)
    finally:
        me.build_model_rows = real
    while type(app.screen).__name__ != "TeamStep":
        app.screen.action_do_next()
        await pilot.pause(0.15)


@test
def test_ctrl_p_opens_the_picker_with_fixture_rows_and_the_filter_completes(ctx: Ctx):
    """The coordinator's own primary repro: open the Agents step from a
    wizard run where the Providers step has produced an enumeration,
    open New bio, press Ctrl+P, and the picker screen is on top with the
    fixture rows visible and the filter input completing -- at both
    sizes. ROOT CAUSE (see agent_bio_editor.AgentBioEditor.on_mount's own
    comment): Textual's App always claims ctrl+p for its command
    palette ahead of any Screen's own binding on the same key."""
    from halo_harness.tui.dialogs.init_wizard import InitWizardApp, WizardState
    from halo_harness.tui.dialogs.model_picker import ModelPicker
    from textual.widgets import Button, Input, OptionList

    async def body(w, h):
        with _Env():
            state = WizardState(cwd=REPO_DIR,
                                 step_keys=("providers", "local_models", "default_model", "permission_mode",
                                            "theme", "agents"),
                                 no_live=True)
            app = InitWizardApp(state)
            async with app.run_test(size=(w, h)) as pilot:
                await pilot.pause(0.1)
                await _wizard_to_agents_step(pilot, app, state)
                ctx.check(f"the Providers step's own enumeration reached the Agents step at {w}x{h}, "
                          f"got enumeration_done={state.enumeration_done}", state.enumeration_done)
                app.screen.query_one("#agents-new", Button).press()
                await pilot.pause(0.2)
                editor = app.screen
                ctx.check(f"New opened the bio editor at {w}x{h}, got {type(editor).__name__}",
                          type(editor).__name__ == "AgentBioEditor")
                await pilot.press("ctrl+p")
                await pilot.pause(0.2)
                picker = app.screen
                ctx.check(f"Ctrl+P opens the model picker (not the command palette) at {w}x{h}, "
                          f"got {type(picker).__name__}", isinstance(picker, ModelPicker))
                rows = picker.query_one("#model-list", OptionList)
                ctx.check(f"the fixture rows are there at {w}x{h}, got option_count={rows.option_count}",
                          rows.option_count >= len(FIXTURE_MODELS))
                picker.query_one("#model-filter", Input).value = "cheap"
                await pilot.pause(0.1)
                ctx.check(f"typing narrows to the matching fixture row at {w}x{h}, got {picker._filtered}",
                          len(picker._filtered) == 1 and picker._filtered[0]["ref"] == "or:vendor/cheap-model")
                picker.action_cancel()
                await pilot.pause(0.1)
                ctx.check(f"Esc returns to the bio editor at {w}x{h}, got {type(app.screen).__name__}",
                          type(app.screen).__name__ == "AgentBioEditor")
    for size in SIZES:
        run(body(*size))


@test
def test_lineup_and_org_editors_have_the_same_ctrl_p_fix(ctx: Ctx):
    """The identical collision existed on `LineupEditor`/`OrgEditor`'s
    own `ctrl+p` (found driving Orgs in the same sweep, deliverable 5) --
    same fix, pinned here so a future change can't silently reopen it."""
    from halo_harness.tui.dialogs.lineup_editor import LineupEditor
    from halo_harness.tui.dialogs.model_picker import ModelPicker
    from halo_harness.tui.dialogs.org_editor import OrgEditor
    from textual.app import App

    async def body(screen_factory, label):
        with _Env():
            app_holder = {}

            class _Host(App):
                def on_mount(self):
                    app_holder["screen"] = screen_factory()
                    self.push_screen(app_holder["screen"])
            app = _Host()
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause(0.15)
                await pilot.press("ctrl+p")
                await pilot.pause(0.15)
                ctx.check(f"{label}: Ctrl+P opens the model picker, got {type(app.screen).__name__}",
                          isinstance(app.screen, ModelPicker))
    run(body(lambda: LineupEditor("pilot", {"agents": []}, FIXTURE_MODELS, is_new=True), "LineupEditor"))
    run(body(lambda: OrgEditor("pilot", {"positions": [{"title": "Boss"}]}, FIXTURE_MODELS), "OrgEditor"))


@test
def test_empty_filter_never_yields_an_empty_picker_silently(ctx: Ctx):
    """"the bio-needs filter never yields an empty list silently: when
    it would, show all rows with one line saying why"."""
    from halo_harness.tui.dialogs.agent_bio_editor import AgentBioEditor
    from halo_harness.tui.dialogs.model_picker import ModelPicker
    from textual.app import App
    from textual.widgets import Input, OptionList

    async def body():
        with _Env():
            app_holder = {}
            # A bio that needs tool support -- NO_TOOLS_MODELS has zero
            # rows that declare it, so the plain filter would be empty.
            raw = {"tools": {"allow": ["Bash"]}}

            class _Host(App):
                def on_mount(self):
                    app_holder["screen"] = AgentBioEditor("needs-tools", raw, NO_TOOLS_MODELS)
                    self.push_screen(app_holder["screen"])
            app = _Host()
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause(0.15)
                await pilot.press("ctrl+p")
                await pilot.pause(0.15)
                picker = app.screen
                ctx.check(f"the picker opened despite the filter matching nothing, got {type(picker).__name__}",
                          isinstance(picker, ModelPicker))
                rows = picker.query_one("#model-list", OptionList)
                selectable = [rows.get_option_at_index(i) for i in range(rows.option_count)
                              if rows.get_option_at_index(i).id]
                ctx.check(f"every row is shown instead of none, got {len(selectable)} selectable "
                          f"of option_count={rows.option_count}", len(selectable) == len(NO_TOOLS_MODELS))
                hint = _static_text(picker.query_one("#model-hint"))
                ctx.check(f"one line explains why, got {hint!r}", "Showing every model" in hint and "--" in hint)
    run(body())


# ---------------------------------------------------------------------------
# Deliverable 1 + 5: the wizard's "Roles and lineup" step -- the toggle
# covers BOTH panes (not just legacy), and the owner's "clunky wizard"
# follow-up: Enter/focus/no-confirm-button rules.
# ---------------------------------------------------------------------------

@test
def test_roles_step_toggle_off_hides_both_panes_and_shows_one_sentence(ctx: Ctx):
    """Round 2c folded the Agents/Roles-and-lineup steps into one "Team"
    step -- the SAME switch-covers-everything invariant this test pins,
    now at `#wiz-team-*` ids (`team_step.TeamStep`)."""
    from halo_harness.tui.dialogs.init_wizard import InitWizardApp, WizardState
    from textual.widgets import Switch

    async def body(w, h):
        with _Env():
            state = WizardState(cwd=REPO_DIR, step_keys=("roles",), no_live=True)
            app = InitWizardApp(state)
            async with app.run_test(size=(w, h)) as pilot:
                await pilot.pause(0.15)
                step = app.screen
                panes = step.query_one("#wiz-team-on-body")
                sentence = step.query_one("#wiz-team-off-sentence")
                ctx.check(f"panes shown, sentence hidden by default at {w}x{h}",
                          panes.styles.display == "block" and sentence.styles.display == "none")
                step.query_one("#wiz-team-switch", Switch).value = False
                await pilot.pause(0.1)
                ctx.check(f"off hides the Lineups/Agents panes at {w}x{h}", panes.styles.display == "none")
                ctx.check(f"off shows the one sentence at {w}x{h}", sentence.styles.display == "block")
                ctx.check(f"the sentence describes delegation+questions at {w}x{h}, got {_static_text(sentence)!r}",
                          "Halo uses" in _static_text(sentence) and "sub-agents" in _static_text(sentence))
                step.query_one("#wiz-team-switch", Switch).value = True
                await pilot.pause(0.1)
                ctx.check(f"on shows the panes again at {w}x{h}", panes.styles.display == "block")
    for size in SIZES:
        run(body(*size))


@test
def test_roles_step_next_applies_the_highlighted_lineup_with_no_button_press(ctx: Ctx):
    """Owner's "clunky wizard" follow-up, rule (c): "the highlighted row
    IS the selection ... Next moves on without a confirm button" -- never
    requiring "Use this lineup" first."""
    from halo_harness.roles import configured_role_table
    from halo_harness.theme import set_config_value
    from halo_harness.tui.dialogs.init_wizard import InitWizardApp, WizardState
    from textual.widgets import OptionList

    async def body():
        with _Env():
            set_config_value("model", "or:vendor/strong-model")
            state = WizardState(cwd=REPO_DIR, step_keys=("roles",), no_live=True)
            app = InitWizardApp(state)
            async with app.run_test(size=(130, 50)) as pilot:
                await pilot.pause(0.15)
                lineup_list = app.screen.query_one("#wiz-team-lineups-list", OptionList)
                ctx.check("the lineup pane lists the shipped lineups", lineup_list.option_count > 0)
                # "standard" always resolves to a REAL role table (every
                # role -> the just-configured default model); some other
                # shipped lineups (e.g. "balanced") deliberately leave
                # their bios' own models unpinned, so picking THOSE here
                # would prove nothing about whether Next actually applied.
                names = [str(lineup_list.get_option_at_index(i).id) for i in range(lineup_list.option_count)]
                ctx.check(f"the standard lineup is one of them, got {names}", "standard" in names)
                lineup_list.highlighted = names.index("standard")
                await pilot.pause(0.05)
                # the footer's plain "Next" -- NOT "Use this lineup".
                app.screen.action_do_next()
                await pilot.pause(0.2)
                ctx.check(f"a lineup apply note landed in state.written, got {state.written}",
                          any("applied" in w for w in state.written))
                ctx.check("the role table is actually populated now", bool(configured_role_table()))
    run(body())


@test
def test_team_step_checkmark_marks_the_active_lineup_not_the_highlight(ctx: Ctx):
    """Round 2c (rule 11): the Team step's Lineups pane is a MANAGEMENT
    list (Enter edits), not a one-of-choice picker -- its check mark
    tracks the lineup actually ACTIVE in config (`team:`), never the
    arrow-key highlight the way the four rule-1 pickers (default model/
    permission mode/theme/legacy roles templates) do; moving the
    highlight must NOT move this mark (`docs/WIZARD.md`'s own Team-step
    section spells out the distinction)."""
    from halo_harness.teams_yaml import apply_team_template, ensure_builtin_team_templates
    from halo_harness.tui.dialogs.init_wizard import InitWizardApp, WizardState
    from textual.widgets import OptionList

    async def body():
        with _Env() as e:
            ensure_builtin_team_templates(state_dir=e.state_dir)
            apply_team_template("balanced", state_dir=e.state_dir)
            state = WizardState(cwd=e.cwd, step_keys=("roles",), no_live=True)
            app = InitWizardApp(state)
            async with app.run_test(size=(130, 50)) as pilot:
                await pilot.pause(0.15)
                lineup_list = app.screen.query_one("#wiz-team-lineups-list", OptionList)
                ctx.check("more than one lineup exists", lineup_list.option_count > 1)
                labels = [str(lineup_list.get_option_at_index(i).prompt) for i in range(lineup_list.option_count)]
                checked = [label for label in labels if label.startswith("✓ ")]
                ctx.check(f"exactly the active ('balanced') lineup is checked, got {labels}",
                          len(checked) == 1 and checked[0].startswith("✓ balanced "))
                # Move the highlight to a DIFFERENT row -- the mark must
                # stay on "balanced", never follow the highlight.
                names = [str(lineup_list.get_option_at_index(i).id) for i in range(lineup_list.option_count)]
                lineup_list.highlighted = (names.index("balanced") + 1) % len(names)
                await pilot.pause(0.05)
                labels2 = [str(lineup_list.get_option_at_index(i).prompt) for i in range(lineup_list.option_count)]
                checked2 = [label for label in labels2 if label.startswith("✓ ")]
                ctx.check(f"the mark stays on 'balanced' after moving the highlight, got {labels2}",
                          len(checked2) == 1 and checked2[0].startswith("✓ balanced "))
    run(body())


@test
def test_agents_step_enter_opens_the_highlighted_bio_no_button_needed(ctx: Ctx):
    """Owner's "clunky wizard" follow-up, rule (a): "Enter on a
    highlighted list row does the obvious thing ... the buttons stay but
    are never the only path" -- the wizard's own Agents step, not just
    the standalone `/agents` screen (which already had this)."""
    from halo_harness.tui.dialogs.agent_bio_editor import AgentBioEditor
    from halo_harness.tui.dialogs.init_wizard import InitWizardApp, WizardState
    from textual.widgets import OptionList

    async def body():
        with _Env():
            state = WizardState(cwd=REPO_DIR, step_keys=("agents",), no_live=True)
            state.enumerated_models, state.enumeration_done = FIXTURE_MODELS, True
            app = InitWizardApp(state)
            async with app.run_test(size=(130, 50)) as pilot:
                await pilot.pause(0.1)
                rows = app.screen.query_one("#agents-list", OptionList)
                ctx.check("a shipped bio is listed to press Enter on", rows.option_count > 0)
                rows.highlighted = 0
                rows.focus()  # round 2c: the Team step focuses Lineups by default -- claim Agents explicitly
                await pilot.pause(0.05)
                await pilot.press("enter")
                await pilot.pause(0.2)
                ctx.check(f"Enter alone opened the bio editor (no button press), got "
                          f"{type(app.screen).__name__}", isinstance(app.screen, AgentBioEditor))
    run(body())


@test
def test_agents_step_and_bio_editor_focus_on_open_is_never_a_button(ctx: Ctx):
    """Rule (b): "when a screen opens, focus lands on the list or the
    first field, never on a button". 2.0.5 release gate: the fixed
    pauses raced a loaded CI runner twice (2aadbee + 5d9dcb1: focus
    still on the VerticalScroll container a beat after the editor
    pushed) -- both waits are bounded polls now, same as the H9b
    lesson: poll the condition, never sleep a guessed constant."""
    from halo_harness.tui.dialogs.init_wizard import InitWizardApp, WizardState
    from textual.widgets import Button, Input, OptionList

    async def body():
        with _Env():
            state = WizardState(cwd=REPO_DIR, step_keys=("agents",), no_live=True)
            state.enumerated_models, state.enumeration_done = FIXTURE_MODELS, True
            app = InitWizardApp(state)
            async with app.run_test(size=(130, 50)) as pilot:
                import time as _time

                async def _wait_until(cond, *, timeout=5.0, step=0.05):
                    deadline = _time.monotonic() + timeout
                    while True:
                        await pilot.pause(step)
                        try:
                            if cond():
                                return True
                        except Exception:
                            pass
                        if _time.monotonic() >= deadline:
                            try:
                                return bool(cond())
                            except Exception:
                                return False

                await _wait_until(lambda: isinstance(app.focused, OptionList))
                ctx.check(f"the Team step focuses a list, never a button, got {type(app.focused).__name__}",
                          isinstance(app.focused, OptionList) and not isinstance(app.focused, Button))
                app.screen.query_one("#agents-new", Button).press()
                await _wait_until(lambda: isinstance(app.focused, Input))
                ctx.check(f"the bio editor focuses a field, got {type(app.focused).__name__}",
                          isinstance(app.focused, Input))
    run(body())


@test
def test_sweep_team_toggle_orgs_summary_handoff(ctx: Ctx):
    """Deliverable 5: "Drive the whole flow in pilots ... Agents -> Roles
    and lineup (toggle on/off ...) -> Orgs -> Summary. Fix everything
    that breaks or misleads." Round 2c merged Agents and Roles-and-
    lineup into the ONE "Team" step this now drives (`step_keys` has a
    single "team" entry, not two); this one proves the STEP HANDOFF
    after `TeamStep`'s own switch/panes still reaches Orgs and Summary
    cleanly, at 80x24."""
    from halo_harness.tui.dialogs.init_wizard import InitWizardApp, WizardState
    from textual.widgets import Switch

    async def body():
        with _Env():
            state = WizardState(cwd=REPO_DIR, step_keys=("team", "orgs", "summary"), no_live=True)
            state.enumerated_models, state.enumeration_done = FIXTURE_MODELS, True
            app = InitWizardApp(state)
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause(0.1)
                ctx.check(f"opens on Team, got {type(app.screen).__name__}",
                          type(app.screen).__name__ == "TeamStep")
                # toggle off then back on, then Next (Skip-equivalent: no
                # lineup/template highlighted -- "off" must still commit
                # cleanly and move on, never raise).
                app.screen.query_one("#wiz-team-switch", Switch).value = False
                await pilot.pause(0.05)
                app.screen.query_one("#wiz-team-switch", Switch).value = True
                await pilot.pause(0.05)
                app.screen.action_do_next()  # Team -> Orgs
                await pilot.pause(0.2)
                ctx.check(f"lands on Organizations, got {type(app.screen).__name__}",
                          type(app.screen).__name__ == "OrgsStep")
                app.screen.action_do_next()  # Orgs -> Summary
                await pilot.pause(0.2)
                ctx.check(f"lands on Summary with no crash, got {type(app.screen).__name__}",
                          type(app.screen).__name__ == "SummaryStep")
    run(body())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
