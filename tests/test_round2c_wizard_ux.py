"""tests.test_round2c_wizard_ux -- Halo 2.0.5 round 2c (`plans/briefs/
2.0.5/round-2c-wizard-ux.md`): the wizard interaction model, `docs/
WIZARD.md`'s own ten rules, the Quick/Full setup chooser, the step rail,
the autocomplete dropdown (four field sites), and the merged "Team" step
(rule 11).

Hermetic: no network, no real model -- every pilot scopes `BRIDGE_TEST_
HOME`/`BRIDGE_STATE_DIR` to a fresh scratch dir per `plans/WORKER-RULES.
md`, and passes a FIXTURE model catalog directly rather than enumerating.
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
SIZES = ((80, 24), (120, 40))


class _Env:
    """Scratch `BRIDGE_TEST_HOME`/`BRIDGE_STATE_DIR` -- the real `~/.halo`
    is never touched (same pattern `tests/test_round2b_wizard_roles_
    fixes.py::_Env` already uses)."""

    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
        d = Path(tempfile.mkdtemp(prefix="round2c-"))
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
# Deliverable 1: docs/WIZARD.md exists, names the ten rules, and is linked.
# ---------------------------------------------------------------------------

@test
def test_wizard_doc_exists_names_ten_rules_and_is_linked(ctx: Ctx):
    doc = (REPO_DIR / "docs" / "WIZARD.md").read_text(encoding="utf-8")
    ctx.check("has a chord table mention", "Ctrl+Left" in doc and "Ctrl+N" in doc)
    for n in range(1, 11):
        ctx.check(f"rule {n} is numbered in the doc", f"{n}. **" in doc)
    handbook = (REPO_DIR / "docs" / "HANDBOOK.md").read_text(encoding="utf-8")
    ctx.check("linked from HANDBOOK.md", "WIZARD.md" in handbook)
    commands = (REPO_DIR / "docs" / "COMMANDS.md").read_text(encoding="utf-8")
    ctx.check("linked from COMMANDS.md", "WIZARD.md" in commands)


# ---------------------------------------------------------------------------
# Deliverable 2 (rules 1, 2, 7) -- highlight-is-selection + focus-on-open,
# on screens round 2b never touched: default model, theme.
# ---------------------------------------------------------------------------

@test
def test_default_model_step_highlight_is_checked_and_focused_on_open(ctx: Ctx):
    from halo_harness.tui.dialogs.init_wizard import InitWizardApp, WizardState

    async def body(w, h):
        with _Env():
            import halo_harness.init_providers as ip
            real = ip.configured_providers
            ip.configured_providers = lambda: []
            try:
                state = WizardState(cwd=REPO_DIR, step_keys=("default_model",), no_live=True)
                app = InitWizardApp(state)
                async with app.run_test(size=(w, h)) as pilot:
                    await pilot.pause(0.15)
                    # No catalog cached -> the "No model catalog" branch;
                    # prove the one-sentence header still rendered (rule 6)
                    # without crashing on an empty entries list.
                    header = app.screen.query_one("#wiz-default-model-sentence")
                    ctx.check(f"rule 6 header names the step at {w}x{h}, got {_static_text(header)!r}",
                              "Default model" in _static_text(header))
            finally:
                ip.configured_providers = real
    for size in SIZES:
        run(body(*size))


@test
def test_theme_step_highlight_checked_follows_arrow_and_focused(ctx: Ctx):
    from halo_harness.tui.dialogs.init_wizard import InitWizardApp, WizardState
    from textual.widgets import OptionList

    async def body(w, h):
        with _Env():
            state = WizardState(cwd=REPO_DIR, step_keys=("theme",), no_live=True)
            app = InitWizardApp(state)
            async with app.run_test(size=(w, h)) as pilot:
                await pilot.pause(0.15)
                option_list = app.screen.query_one("#wiz-theme-list", OptionList)
                ctx.check(f"focus lands on the theme list at {w}x{h} (rule 7), got {type(app.focused).__name__}",
                          app.focused is option_list)
                first = str(option_list.get_option_at_index(option_list.highlighted).prompt)
                ctx.check(f"the initial highlight is checked at {w}x{h}, got {first!r}", first.startswith("✓ "))
                option_list.highlighted = (option_list.highlighted + 1) % option_list.option_count
                await pilot.pause(0.05)
                moved = str(option_list.get_option_at_index(option_list.highlighted).prompt)
                ctx.check(f"the check mark follows the highlight at {w}x{h}, got {moved!r}",
                          moved.startswith("✓ "))
    for size in SIZES:
        run(body(*size))


# ---------------------------------------------------------------------------
# Deliverable 4: the step rail shows the current step; Ctrl+Right advances.
# ---------------------------------------------------------------------------

@test
def test_rail_shows_current_step_and_ctrl_right_advances(ctx: Ctx):
    from halo_harness.tui.dialogs.init_wizard import InitWizardApp, WizardState

    async def body():
        with _Env():
            state = WizardState(cwd=REPO_DIR, step_keys=("permission_mode", "theme", "orgs"), no_live=True)
            app = InitWizardApp(state)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause(0.15)
                rail = app.screen.query_one("#wizard-rail")
                ctx.check(f"rail names the current step, got {_static_text(rail)!r}",
                          "Permission mode" in _static_text(rail))
                await pilot.press("ctrl+right")
                await pilot.pause(0.2)
                ctx.check(f"Ctrl+Right advanced to Theme, got {type(app.screen).__name__}",
                          type(app.screen).__name__ == "ThemeStep")
                rail2 = app.screen.query_one("#wizard-rail")
                ctx.check(f"the new screen's own rail names Theme, got {_static_text(rail2)!r}",
                          "Theme" in _static_text(rail2))
                await pilot.press("ctrl+right")
                await pilot.pause(0.2)
                ctx.check(f"Ctrl+Right advances again to Organizations, got {type(app.screen).__name__}",
                          type(app.screen).__name__ == "OrgsStep")
                await pilot.press("ctrl+left")
                await pilot.pause(0.2)
                ctx.check(f"Ctrl+Left goes back to the SAME Theme instance, got {type(app.screen).__name__}",
                          type(app.screen).__name__ == "ThemeStep")
    run(body())


# ---------------------------------------------------------------------------
# Deliverable 5: Quick setup / Full setup.
# ---------------------------------------------------------------------------

@test
def test_quick_setup_ends_on_summary_with_standard_active_and_roles_off(ctx: Ctx):
    from halo_harness.roles import roles_mode_enabled
    from halo_harness.theme import get_config_value, set_config_value
    from halo_harness.tui.dialogs.init_wizard import InitWizardApp, WizardState, full_step_keys

    async def body():
        with _Env():
            set_config_value("model", "or:vendor/strong-model")
            state = WizardState(cwd=REPO_DIR, step_keys=full_step_keys(), no_live=True, offer_quick_full=True)
            app = InitWizardApp(state)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause(0.15)
                ctx.check(f"opens on the chooser, got {type(app.screen).__name__}",
                          type(app.screen).__name__ == "SetupModeStep")
                app.screen.query_one("#wiz-next").press()  # Quick is the highlighted default
                await pilot.pause(0.2)
                ctx.check(f"Quick shrinks step_keys, got {state.step_keys}",
                          state.step_keys == ("providers", "default_model", "summary"))
                app.screen.action_do_next()  # providers (no_live branch)
                await pilot.pause(0.2)
                app.screen.action_do_next()  # default_model, nothing picked -- keeps the configured default
                await pilot.pause(0.5)
                ctx.check(f"lands on Summary, got {type(app.screen).__name__}",
                          type(app.screen).__name__ == "SummaryStep")
                ctx.check(f"team is 'standard', got {get_config_value('team', default=None)!r}",
                          get_config_value("team", default=None) == "standard")
                ctx.check(f"roles are off, got {roles_mode_enabled()!r}", roles_mode_enabled() is False)
                note = app.screen.query_one("#wiz-summary-quick-note")
                ctx.check(f"the Summary says Quick setup ran, got {_static_text(note)!r}",
                          "Quick setup" in _static_text(note))
    run(body())


@test
def test_full_setup_walks_every_step(ctx: Ctx):
    from halo_harness.tui.dialogs.init_wizard import InitWizardApp, WizardState, full_step_keys

    async def body():
        with _Env():
            state = WizardState(cwd=REPO_DIR, step_keys=full_step_keys(), no_live=True, offer_quick_full=True)
            app = InitWizardApp(state)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause(0.15)
                option_list = app.screen.query_one("#wiz-setup-mode-list")
                names = [str(option_list.get_option_at_index(i).id) for i in range(option_list.option_count)]
                option_list.highlighted = names.index("full")
                app.screen.query_one("#wiz-next").press()
                await pilot.pause(0.2)
                seen = []
                for _ in range(12):
                    seen.append(type(app.screen).__name__)
                    if seen[-1] == "SummaryStep":
                        break
                    app.screen.action_do_next()
                    await pilot.pause(0.25)
                ctx.check(f"every step was reached in order, got {seen}",
                          seen == ["ProvidersStep", "LocalModelsStep", "DefaultModelStep", "PermissionModeStep",
                                   "ThemeStep", "TeamStep", "OrgsStep", "SummaryStep"])
    run(body())


# ---------------------------------------------------------------------------
# Deliverable 7 (rule 11): the Team step, at both sizes.
# ---------------------------------------------------------------------------

@test
def test_team_step_switch_off_shows_only_the_sentence(ctx: Ctx):
    from halo_harness.tui.dialogs.init_wizard import InitWizardApp, WizardState
    from textual.widgets import Switch

    async def body(w, h):
        with _Env():
            state = WizardState(cwd=REPO_DIR, step_keys=("team",), no_live=True)
            app = InitWizardApp(state)
            async with app.run_test(size=(w, h)) as pilot:
                await pilot.pause(0.15)
                step = app.screen
                on_body = step.query_one("#wiz-team-on-body")
                off_sentence = step.query_one("#wiz-team-off-sentence")
                ctx.check(f"on by default at {w}x{h}", on_body.styles.display == "block"
                          and off_sentence.styles.display == "none")
                step.query_one("#wiz-team-switch", Switch).value = False
                await pilot.pause(0.1)
                ctx.check(f"off hides the panes at {w}x{h}", on_body.styles.display == "none")
                ctx.check(f"off shows the sentence at {w}x{h}", off_sentence.styles.display == "block")
                ctx.check(f"the sentence covers delegation+questions at {w}x{h}, got {_static_text(off_sentence)!r}",
                          "sub-agents" in _static_text(off_sentence) and "questions" in _static_text(off_sentence))
    for size in SIZES:
        run(body(*size))


@test
def test_team_step_on_shows_both_panes_at_both_sizes(ctx: Ctx):
    """2.0.7 wizard deep review UPDATED: ONE pane at a time at EVERY width
    (the old 120x40 side-by-side stack was the "thing to fix" in rolo's
    2026-10-07 order -- a first-time user meets Lineups first, never both
    lists at once); the pane-switch bar is always visible, both panes stay
    mounted (only display toggles)."""
    from halo_harness.tui.dialogs.init_wizard import InitWizardApp, WizardState
    from textual.widgets import Button

    async def body(w, h):
        with _Env():
            state = WizardState(cwd=REPO_DIR, step_keys=("team",), no_live=True)
            app = InitWizardApp(state)
            async with app.run_test(size=(w, h)) as pilot:
                await pilot.pause(0.15)
                step = app.screen
                lineups_pane = step.query_one("#wiz-team-lineups-pane")
                agents_pane = step.query_one("#wiz-team-agents-pane")
                switch_bar = step.query_one("#wiz-team-pane-switch")
                ctx.check(f"the pane-switch bar is always visible at {w}x{h}",
                          switch_bar.styles.display != "none")
                ctx.check(f"Lineups shown first at {w}x{h}",
                          lineups_pane.styles.display == "block" and agents_pane.styles.display == "none")
                step.query_one("#wiz-team-switch-agents-btn", Button).press()
                await pilot.pause(0.1)
                ctx.check(f"the switch reaches Agents at {w}x{h}",
                          agents_pane.styles.display == "block" and lineups_pane.styles.display == "none")
    for size in SIZES:
        run(body(*size))


@test
def test_team_step_enter_edits_from_each_pane(ctx: Ctx):
    from halo_harness.tui.dialogs.agent_bio_editor import AgentBioEditor
    from halo_harness.tui.dialogs.init_wizard import InitWizardApp, WizardState
    from halo_harness.tui.dialogs.lineup_editor import LineupEditor
    from textual.widgets import OptionList

    async def body():
        with _Env():
            state = WizardState(cwd=REPO_DIR, step_keys=("team",), no_live=True)
            state.enumerated_models, state.enumeration_done = FIXTURE_MODELS, True
            app = InitWizardApp(state)
            async with app.run_test(size=(130, 50)) as pilot:
                await pilot.pause(0.15)
                step = app.screen
                lineups_list = step.query_one("#wiz-team-lineups-list", OptionList)
                lineups_list.highlighted = 0
                lineups_list.focus()
                await pilot.pause(0.05)
                await pilot.press("enter")
                await pilot.pause(0.3)
                ctx.check(f"Enter on a lineup opens the editor, got {type(app.screen).__name__}",
                          isinstance(app.screen, LineupEditor))
                app.screen.action_cancel()
                await pilot.pause(0.1)
                agents_list = step.query_one("#agents-list", OptionList)
                agents_list.highlighted = 0
                agents_list.focus()
                await pilot.pause(0.05)
                await pilot.press("enter")
                await pilot.pause(0.3)
                ctx.check(f"Enter on a bio opens the editor, got {type(app.screen).__name__}",
                          isinstance(app.screen, AgentBioEditor))
    run(body())


@test
def test_team_step_active_lineup_checkmark(ctx: Ctx):
    from halo_harness.teams_yaml import apply_team_template, ensure_builtin_team_templates
    from halo_harness.tui.dialogs.init_wizard import InitWizardApp, WizardState
    from textual.widgets import OptionList

    async def body():
        with _Env() as e:
            ensure_builtin_team_templates(state_dir=e.state_dir)
            apply_team_template("standard", state_dir=e.state_dir)
            state = WizardState(cwd=e.cwd, step_keys=("team",), no_live=True)
            app = InitWizardApp(state)
            async with app.run_test(size=(130, 50)) as pilot:
                await pilot.pause(0.15)
                lineups_list = app.screen.query_one("#wiz-team-lineups-list", OptionList)
                labels = [str(lineups_list.get_option_at_index(i).prompt) for i in range(lineups_list.option_count)]
                checked = [label for label in labels if label.startswith("✓ ")]
                ctx.check(f"exactly the active lineup is checked, got {labels}",
                          len(checked) == 1 and checked[0].startswith("✓ standard "))
    run(body())


@test
def test_team_step_ctrl_n_and_ctrl_d_dispatch_by_focused_pane(ctx: Ctx):
    from halo_harness.tui.dialogs.agent_bio_editor import AgentBioEditor
    from halo_harness.tui.dialogs.init_wizard import InitWizardApp, WizardState
    from halo_harness.tui.dialogs.lineup_editor import LineupEditor
    from textual.widgets import OptionList

    async def body():
        with _Env():
            state = WizardState(cwd=REPO_DIR, step_keys=("team",), no_live=True)
            app = InitWizardApp(state)
            async with app.run_test(size=(130, 50)) as pilot:
                await pilot.pause(0.15)
                step = app.screen
                step.query_one("#wiz-team-lineups-list", OptionList).focus()
                await pilot.pause(0.05)
                await pilot.press("ctrl+n")
                await pilot.pause(0.3)
                ctx.check(f"Ctrl+N from Lineups opens a NEW lineup, got {type(app.screen).__name__}",
                          isinstance(app.screen, LineupEditor))
                app.screen.action_cancel()
                await pilot.pause(0.1)
                step.query_one("#agents-list", OptionList).focus()
                await pilot.pause(0.05)
                await pilot.press("ctrl+n")
                await pilot.pause(0.3)
                ctx.check(f"Ctrl+N from Agents opens a NEW bio, got {type(app.screen).__name__}",
                          isinstance(app.screen, AgentBioEditor))
    run(body())


@test
def test_step_team_agents_roles_aliases_all_land_on_team_step(ctx: Ctx):
    from halo_harness.tui.dialogs.init_wizard import _build_step, _resolve_start_index, full_step_keys
    from halo_harness.tui.dialogs.init_wizard import TeamStep, WizardState

    with _Env():
        for alias in ("team", "agents", "roles"):
            step_keys = full_step_keys()
            idx = _resolve_start_index(alias, step_keys)
            screen = _build_step(WizardState(cwd=REPO_DIR, step_keys=step_keys, index=idx, no_live=True),
                                  step_keys[idx])
            ctx.check(f"--step {alias} resolves to the Team step, got {type(screen).__name__}",
                      isinstance(screen, TeamStep))


@test
def test_roles_off_still_resolves_a_subagent_to_the_default_model(ctx: Ctx):
    """"roles off still spawns a sub-agent on the default model" --
    `config/agents_md.resolve_agent_model`'s own chain with an EMPTY role
    table (exactly what `roles.resolve_role_table()` returns when
    `roles.enabled` is off) falls through to the parent's own model/
    profile, never refuses or raises."""
    from halo_harness.config.agents_md import resolve_agent_model
    from halo_harness.model import parse_model_ref

    with _Env() as e:
        parent_ref = parse_model_ref("or:vendor/strong-model")
        ref, profile = resolve_agent_model(role_name="coder", role_table={}, parent_ref=parent_ref,
                                            parent_profile=None, state_dir=e.state_dir)
        ctx.check(f"a role-bearing sub-agent with roles off still resolves to the parent/default model, got {ref}",
                  ref is parent_ref)


# ---------------------------------------------------------------------------
# Deliverable 3 (rule 3): autocomplete filters and picks, all four field
# sites -- bio editor, org editor, lineup grid, roles editor quick filter.
# ---------------------------------------------------------------------------

@test
def test_autocomplete_bio_editor_preference_field(ctx: Ctx):
    from halo_harness.tui.dialogs.agent_bio_editor import AgentBioEditor
    from textual.app import App
    from textual.widgets import Input

    async def body():
        with _Env():
            app_holder = {}

            class _Host(App):
                def on_mount(self):
                    app_holder["screen"] = AgentBioEditor("new-bio", {}, FIXTURE_MODELS, is_new=True)
                    self.push_screen(app_holder["screen"])
            app = _Host()
            async with app.run_test(size=(130, 50)) as pilot:
                await pilot.pause(0.15)
                field = app.screen.query_one("#bio-pref", Input)
                field.focus()
                for ch in "cheap":
                    await pilot.press(ch)
                await pilot.pause(0.1)
                dropdown = app.screen.query_one("#bio-pref-ac")
                ctx.check(f"typing opens the dropdown with the matching row, got display={dropdown.styles.display} "
                          f"count={dropdown.option_count}",
                          dropdown.styles.display == "block" and dropdown.option_count == 1)
                await pilot.press("enter")
                await pilot.pause(0.1)
                ctx.check(f"Enter picks it into the field, got {field.value!r}",
                          field.value == "or:vendor/cheap-model")
                ctx.check(f"Enter also closed the dropdown, got {dropdown.styles.display!r}",
                          dropdown.styles.display == "none")
    run(body())


@test
def test_autocomplete_org_editor_role_field(ctx: Ctx):
    from halo_harness.tui.dialogs.org_editor import OrgEditor
    from textual.app import App
    from textual.widgets import Input

    async def body():
        with _Env():
            org = {"positions": [{"title": "Boss", "reports": []}]}
            app_holder = {}

            class _Host(App):
                def on_mount(self):
                    app_holder["screen"] = OrgEditor("demo", org, FIXTURE_MODELS)
                    self.push_screen(app_holder["screen"])
            app = _Host()
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause(0.15)
                field = app.screen.query_one("#org-field-role", Input)
                field.focus()
                for ch in "strong":
                    await pilot.press(ch)
                await pilot.pause(0.1)
                dropdown = app.screen.query_one("#org-field-role-ac")
                ctx.check(f"org role field dropdown matches, got count={dropdown.option_count}",
                          dropdown.option_count == 1)
                await pilot.press("escape")
                await pilot.pause(0.1)
                ctx.check(f"Escape closes the dropdown without leaving the editor, got "
                          f"{type(app.screen).__name__} display={dropdown.styles.display}",
                          type(app.screen).__name__ == "OrgEditor" and dropdown.styles.display == "none")
                await pilot.press("escape")
                await pilot.pause(0.1)
                ctx.check(f"a SECOND Escape (dropdown already closed) now cancels the editor, got "
                          f"{type(app.screen).__name__}", not isinstance(app.screen, OrgEditor))
    run(body())


@test
def test_autocomplete_lineup_grid_agent_field(ctx: Ctx):
    from halo_harness.agents_yaml import save_agent_bio
    from halo_harness.tui.dialogs.lineup_editor import LineupEditor
    from textual.app import App
    from textual.widgets import Input

    async def body():
        with _Env() as e:
            save_agent_bio("solo-coder", {"description": "d", "models": {"preference": "or:vendor/strong-model"}},
                            state_dir=e.state_dir)
            app_holder = {}

            class _Host(App):
                def on_mount(self):
                    app_holder["screen"] = LineupEditor("pilot", {"agents": [{"role": "subagent"}]},
                                                         FIXTURE_MODELS, state_dir=e.state_dir, is_new=True)
                    self.push_screen(app_holder["screen"])
            app = _Host()
            async with app.run_test(size=(130, 50)) as pilot:
                await pilot.pause(0.15)
                field = app.screen.query_one("#lineup-field-agent", Input)
                field.focus()
                for ch in "solo-cod":  # a PREFIX, not the full name -- picked via the dropdown below
                    await pilot.press(ch)
                await pilot.pause(0.1)
                dropdown = app.screen.query_one("#lineup-field-agent-ac")
                ctx.check(f"lineup agent field suggests the BIO NAME, got count={dropdown.option_count}, "
                          f"got id={dropdown.get_option_at_index(0).id if dropdown.option_count else None}",
                          dropdown.option_count == 1 and str(dropdown.get_option_at_index(0).id) == "solo-coder")
                await pilot.press("enter")
                await pilot.pause(0.1)
                ctx.check(f"Enter picks the bio name into the field, got {field.value!r}",
                          field.value == "solo-coder")
    run(body())


@test
def test_autocomplete_roles_editor_quick_filter(ctx: Ctx):
    from halo_harness.tui.dialogs.roles_editor import RolesEditor
    from textual.app import App
    from textual.widgets import Input, OptionList

    async def body():
        with _Env():
            app_holder = {}

            class _Host(App):
                def on_mount(self):
                    app_holder["screen"] = RolesEditor("pilot", {}, FIXTURE_MODELS)
                    self.push_screen(app_holder["screen"])
            app = _Host()
            async with app.run_test(size=(130, 50)) as pilot:
                await pilot.pause(0.15)
                roles_list = app.screen.query_one("#roles-list", OptionList)
                names = [str(roles_list.get_option_at_index(i).id) for i in range(roles_list.option_count)]
                roles_list.highlighted = names.index("coder")
                field = app.screen.query_one("#roles-quick-filter", Input)
                field.focus()
                for ch in "strong":
                    await pilot.press(ch)
                await pilot.pause(0.1)
                dropdown = app.screen.query_one("#roles-quick-filter-ac")
                ctx.check(f"quick filter matches, got count={dropdown.option_count}", dropdown.option_count == 1)
                await pilot.press("enter")
                await pilot.pause(0.15)
                await pilot.press("enter")  # the effort prompt, blank
                await pilot.pause(0.1)
                ctx.check(f"the highlighted role (coder) was assigned, got {app.screen.roles.get('coder')!r}",
                          app.screen.roles.get("coder") == "or:vendor/strong-model")
    run(body())


# ---------------------------------------------------------------------------
# Rule 8: the save toast, and Escape never losing a prior save.
# ---------------------------------------------------------------------------

@test
def test_save_toast_on_returning_to_the_agents_pane(ctx: Ctx):
    from halo_harness.tui.dialogs.init_wizard import InitWizardApp, WizardState
    from textual.widgets import Input, OptionList

    async def body():
        with _Env():
            state = WizardState(cwd=REPO_DIR, step_keys=("team",), no_live=True)
            state.enumerated_models, state.enumeration_done = FIXTURE_MODELS, True
            app = InitWizardApp(state)
            async with app.run_test(size=(130, 50)) as pilot:
                await pilot.pause(0.15)
                step = app.screen
                step.query_one("#agents-list", OptionList).focus()
                await pilot.press("ctrl+n")
                await pilot.pause(0.3)
                editor = app.screen
                editor.query_one("#bio-description", Input).value = "a pilot bio"
                await pilot.pause(0.05)
                editor.action_save()
                await pilot.pause(0.2)
                ctx.check(f"back on the Team step after save, got {type(app.screen).__name__}",
                          type(app.screen).__name__ == "TeamStep")
                hint = app.screen.query_one("#agents-hint")
                ctx.check(f"a one-line toast names what was saved, got {_static_text(hint)!r}",
                          "Saved" in _static_text(hint))
    run(body())


@test
def test_escape_cancel_never_writes_a_partial_bio(ctx: Ctx):
    """Rule 8: "Escape is always Back and never destructive" -- typing
    into a NEW bio's fields then Escaping away never creates the file at
    all (nothing was ever saved to lose)."""
    from halo_harness.agents_yaml import list_agent_bios
    from halo_harness.tui.dialogs.agent_bio_editor import AgentBioEditor
    from textual.app import App
    from textual.widgets import Input

    async def body():
        with _Env() as e:
            app_holder = {}

            class _Host(App):
                def on_mount(self):
                    app_holder["screen"] = AgentBioEditor("escape-pilot", {}, FIXTURE_MODELS, is_new=True)
                    self.push_screen(app_holder["screen"])
            app = _Host()
            async with app.run_test(size=(130, 50)) as pilot:
                await pilot.pause(0.15)
                app.screen.query_one("#bio-description", Input).value = "never saved"
                await pilot.pause(0.05)
                await pilot.press("escape")
                await pilot.pause(0.1)
                ctx.check(f"the screen closed (cancelled), got {app.screen}", not isinstance(app.screen,
                          AgentBioEditor))
                ctx.check(f"no file was ever written for the never-saved bio, got {list_agent_bios(state_dir=e.state_dir)}",
                          "escape-pilot" not in list_agent_bios(state_dir=e.state_dir))
    run(body())


# ---------------------------------------------------------------------------
# Rule 10: the Summary's "Change" jumps.
# ---------------------------------------------------------------------------

@test
def test_summary_change_jumps_back_into_a_step(ctx: Ctx):
    from halo_harness.tui.dialogs.init_wizard import InitWizardApp, WizardState
    from textual.widgets import OptionList

    async def body():
        with _Env():
            state = WizardState(cwd=REPO_DIR, step_keys=("theme", "summary"), no_live=True)
            app = InitWizardApp(state)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause(0.15)
                app.screen.action_do_next()  # theme -> summary
                await pilot.pause(0.5)
                ctx.check(f"on Summary, got {type(app.screen).__name__}", type(app.screen).__name__ == "SummaryStep")
                change_list = app.screen.query_one("#wiz-summary-change-list", OptionList)
                names = [str(change_list.get_option_at_index(i).id) for i in range(change_list.option_count)]
                ctx.check(f"theme is one of the Change rows, got {names}", "theme" in names)
                change_list.highlighted = names.index("theme")
                change_list.focus()
                await pilot.pause(0.05)
                await pilot.press("enter")
                await pilot.pause(0.2)
                ctx.check(f"Change jumped back to the Theme step, got {type(app.screen).__name__}",
                          type(app.screen).__name__ == "ThemeStep")
    run(body())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
