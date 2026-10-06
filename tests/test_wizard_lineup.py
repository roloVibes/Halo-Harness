"""tests.test_wizard_lineup -- Halo 2.0.5 round 2 (wizard: agent bios and
lineups): deliverable 2 (the roles editor's Models/Agents picker source)
and deliverable 3 (the lineup editor, `tui/dialogs/lineup_editor.py`) plus
the `about:` context-builder fold-in. Hermetic: no network, no real model.
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
     "context_tokens": 128000, "price_in_per_m": 1.0, "price_out_per_m": 2.0},
    {"ref": "or:vendor/cheap-model", "provider": "openrouter", "group": "OpenRouter (or:)",
     "context_tokens": 8000, "price_in_per_m": 0.1, "price_out_per_m": 0.2},
]


class _Env:
    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
        d = Path(tempfile.mkdtemp(prefix="wizard-lineup-"))
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


# ---------------------------------------------------------------------------
# Pure helpers.
# ---------------------------------------------------------------------------

@test
def test_draft_about_text_is_never_blank(ctx: Ctx):
    from halo_harness.tui.dialogs.lineup_editor import draft_about_text
    empty = draft_about_text({"agents": []})
    ctx.check(f"an empty lineup still gets a sentence, got {empty!r}", bool(empty.strip()))
    full = draft_about_text({"agents": [{"agent": "coder", "role": "main", "as": "boss"}],
                              "delegation": {"mode": "by-skill"},
                              "pipeline": {"stages": [{"name": "implement"}, {"name": "review"}]}})
    ctx.check(f"mentions the assignment, got {full!r}", "boss" in full and "coder" in full)
    ctx.check("mentions delegation mode", "by-skill" in full)
    ctx.check("mentions the pipeline order", "implement -> review" in full)


@test
def test_lineup_warnings_catch_missing_bio_duplicate_alias_and_main_count(ctx: Ctx):
    from halo_harness.tui.dialogs.lineup_editor import lineup_warnings
    with _Env():
        warnings = lineup_warnings([
            {"agent": "no-such-bio", "role": "main", "as": "a"},
            {"agent": "no-such-bio", "role": "subagent", "as": "a"},  # duplicate alias "a"
        ])
        ctx.check(f"missing bio flagged, got {warnings}", any("not found" in w for w in warnings))
        ctx.check(f"duplicate alias flagged, got {warnings}", any("duplicate alias" in w for w in warnings))
        none_main = lineup_warnings([{"agent": "x", "role": "subagent", "as": "a"}])
        ctx.check(f"no role: main flagged, got {none_main}", any("role: main" in w for w in none_main))


@test
def test_lineup_warnings_flag_a_same_gateway_fallback(ctx: Ctx):
    from halo_harness.agents_yaml import save_agent_bio
    from halo_harness.tui.dialogs.lineup_editor import lineup_warnings
    with _Env() as e:
        save_agent_bio("same-gateway-bio", {"description": "x",
                                             "models": {"preference": "or:vendor/a", "fallback": "or:vendor/b"}},
                        state_dir=e.state_dir)
        warnings = lineup_warnings([{"agent": "same-gateway-bio", "role": "main", "as": "boss"}],
                                    state_dir=e.state_dir)
        ctx.check(f"same-gateway fallback flagged, got {warnings}",
                  any("same gateway" in w for w in warnings))


@test
def test_about_round_trips_through_teams_yaml_and_extends_inherits_it(ctx: Ctx):
    from halo_harness.agents_yaml import save_agent_bio
    from halo_harness.teams_yaml import resolve_team_template, save_team_template
    with _Env() as e:
        save_agent_bio("lineup-member", {"description": "x", "models": {"preference": "or:vendor/a"}},
                        state_dir=e.state_dir)
        save_team_template("about-base", {"description": "d", "about": "How this team works: carefully.",
                                           "agents": [{"agent": "lineup-member", "role": "main"}]},
                            state_dir=e.state_dir)
        resolved = resolve_team_template("about-base", state_dir=e.state_dir)
        ctx.check(f"about round-trips, got {resolved.get('about')!r}",
                  resolved["about"] == "How this team works: carefully.")
        save_team_template("about-child", {"description": "child", "extends": "about-base"}, state_dir=e.state_dir)
        child = resolve_team_template("about-child", state_dir=e.state_dir)
        ctx.check(f"a child that never sets its own about inherits the parent's, got {child.get('about')!r}",
                  child["about"] == "How this team works: carefully.")


@test
def test_member_system_context_addition_appends_how_this_team_works(ctx: Ctx):
    """Tests section: "The active team's about text reaches a member's
    system context (unit test on the context builder)"."""
    from halo_harness.agents_yaml import save_agent_bio
    from halo_harness.teams_yaml import member_system_context_addition, save_team_template
    from halo_harness.theme import set_config_value
    with _Env() as e:
        save_agent_bio("ctx-member", {"description": "x", "models": {"preference": "or:vendor/a"},
                                       "context": {"system_prompt": "Be terse."}}, state_dir=e.state_dir)
        save_agent_bio("ctx-outsider", {"description": "y", "models": {"preference": "or:vendor/a"}},
                        state_dir=e.state_dir)
        save_team_template("ctx-team", {"description": "d", "about": "Ship small, verify every round.",
                                         "agents": [{"agent": "ctx-member", "role": "main"}]}, state_dir=e.state_dir)
        set_config_value("team", "ctx-team")
        addition = member_system_context_addition("ctx-member", state_dir=e.state_dir)
        ctx.check(f"the bio's own system_prompt is included, got {addition!r}", "Be terse." in addition)
        ctx.check(f"the team's about text lands under the house heading, got {addition!r}",
                  "How this team works" in addition and "Ship small" in addition)
        outsider_addition = member_system_context_addition("ctx-outsider", state_dir=e.state_dir)
        ctx.check(f"a bio NOT in the active team never gets the about text, got {outsider_addition!r}",
                  "How this team works" not in outsider_addition)


@test
def test_apply_team_template_writes_roles_and_active_team(ctx: Ctx):
    from halo_harness.agents_yaml import save_agent_bio
    from halo_harness.teams_yaml import apply_team_template, save_team_template
    from halo_harness.theme import get_config_value
    with _Env() as e:
        save_agent_bio("apply-member", {"description": "x", "models": {"preference": "or:vendor/pinned"}},
                        state_dir=e.state_dir)
        save_team_template("apply-lineup", {"description": "d",
                                             "agents": [{"agent": "apply-member", "role": "main", "as": "boss"}]},
                            state_dir=e.state_dir)
        ok, problems, notes = apply_team_template("apply-lineup", state_dir=e.state_dir)
        ctx.check(f"apply succeeded, got {problems}", ok)
        ctx.check(f"roles.boss landed in config, got {get_config_value('roles.boss', default=None)}",
                  get_config_value("roles.boss", default=None) == "or:vendor/pinned")
        ctx.check(f"team: is now active, got {get_config_value('team', default=None)}",
                  get_config_value("team", default=None) == "apply-lineup")


# ---------------------------------------------------------------------------
# Textual pilots: deliverable 2 (roles editor Agents source) and
# deliverable 3 (the lineup editor + the RolesStep "Roles and lineup"
# panes).
# ---------------------------------------------------------------------------

@test
def test_roles_editor_agents_source_pick_and_new_bio_round_trip(ctx: Ctx):
    """Tests section: "The roles editor: switch to the Agents source,
    pick a bio, see the model and agent: recorded; 'New bio...' round
    trip"."""
    from textual.app import App
    from textual.screen import Screen
    from textual.widgets import Input, OptionList

    from halo_harness.agents_yaml import save_agent_bio
    from halo_harness.tui.dialogs.agent_bio_editor import AgentBioEditor
    from halo_harness.tui.dialogs.model_picker import ModelPicker
    from halo_harness.tui.dialogs.roles_editor import RolesEditor

    class HostApp(App):
        def on_mount(self):
            self.push_screen(Screen())

    async def body():
        with _Env():
            save_agent_bio("pilot-researcher", {"description": "Does research.",
                                                 "models": {"preference": "or:vendor/strong-model"}})
            app = HostApp()
            async with app.run_test(size=(120, 45)) as pilot:
                await pilot.pause(0.05)
                app.push_screen(RolesEditor("demo", {}, FIXTURE_MODELS))
                await pilot.pause(0.1)
                editor = app.screen
                editor.query_one("#roles-list", OptionList).highlighted = 0
                await pilot.press("enter")
                await pilot.pause(0.1)
                picker = app.screen
                ctx.check("the model picker opened", isinstance(picker, ModelPicker))
                ctx.check("source starts on Models", picker._source == "models")
                picker.action_toggle_source()
                await pilot.pause(0.05)
                ctx.check("Ctrl+A toggled to Agents", picker._source == "agents")
                rows = picker.query_one("#model-list", OptionList)
                ids = [str(rows.get_option_at_index(i).id) for i in range(rows.option_count)]
                ctx.check(f"New bio... leads, the real bio is listed, got {ids}",
                          ids[0] == "__new_bio__" and "pilot-researcher" in ids)
                rows.highlighted = ids.index("pilot-researcher")
                await pilot.press("enter")
                await pilot.pause(0.1)
                await pilot.press("enter")  # blank effort commits the pick
                await pilot.pause(0.1)
                recorded = editor.roles.get("orchestrator")
                ctx.check(f"model AND agent: recorded, got {recorded}",
                          recorded["model"] == "or:vendor/strong-model" and recorded["agent"] == "pilot-researcher")
                ctx.check(f"the row text shows the agent, got {editor._row_text('orchestrator')!r}",
                          "agent:pilot-researcher" in editor._row_text("orchestrator"))

                # "New bio..." round trip.
                editor.query_one("#roles-list", OptionList).highlighted = 0
                await pilot.press("enter")
                await pilot.pause(0.1)
                picker2 = app.screen
                picker2.action_toggle_source()
                await pilot.pause(0.05)
                rows2 = picker2.query_one("#model-list", OptionList)
                rows2.highlighted = 0  # "New bio..."
                await pilot.press("enter")
                await pilot.pause(0.2)
                ctx.check("New bio... opened the bio editor", isinstance(app.screen, AgentBioEditor))
                app.screen.query_one("#bio-pref", Input).value = "or:vendor/strong-model"
                app.screen.action_save()
                await pilot.pause(0.2)
                await pilot.press("enter")  # blank effort
                await pilot.pause(0.1)
                new_recorded = editor.roles.get("orchestrator")
                ctx.check(f"the fresh bio is now recorded, got {new_recorded}",
                          new_recorded["agent"].startswith("new-bio-"))
    asyncio.run(body())


def _host_screen(screen):
    from textual.app import App

    class _Host(App):
        result = None

        def on_mount(self):
            def _after(r):
                self.result = r
            self.push_screen(screen, _after)
    return _Host()


@test
def test_lineup_editor_new_lineup_model_and_bio_roles_about_budget_save_activate(ctx: Ctx):
    """Tests section: "new lineup with one role by model and one by bio,
    the about text, one advanced section (budget), save, teams_yaml loads
    it clean, halo teams show prints the about text, the activation
    prompt sets team:"."""
    from textual.widgets import Button, Input, TextArea

    from halo_harness.agents_yaml import save_agent_bio
    from halo_harness.tui.dialogs.lineup_editor import LineupEditor, _ActivateLineupConfirm

    async def body():
        with _Env():
            save_agent_bio("lineup-worker", {"description": "a worker bio",
                                              "models": {"preference": "or:vendor/strong-model"}})
            app = _host_screen(LineupEditor("pilot-lineup", {"agents": []}, FIXTURE_MODELS, is_new=True))
            async with app.run_test(size=(140, 55)) as pilot:
                await pilot.pause(0.1)
                editor = app.screen
                editor.action_add_assignment()
                await pilot.pause(0.05)
                editor.query_one("#lineup-field-role", Input).value = "main"
                editor.query_one("#lineup-field-as", Input).value = "boss"
                editor._agent_or_model_picked("or:vendor/strong-model")  # pick by MODEL
                await pilot.pause(0.05)

                editor.action_add_assignment()
                await pilot.pause(0.05)
                editor.query_one("#lineup-field-role", Input).value = "subagent"
                editor.query_one("#lineup-field-as", Input).value = "worker"
                editor._agent_or_model_picked({"agent": "lineup-worker"})  # pick by BIO
                await pilot.pause(0.05)
                editor._commit_current_assignment()
                editor._refresh_assignments()

                warnings = _static_text(editor.query_one("#lineup-warnings"))
                ctx.check(f"no warnings once both rows resolve, got {warnings!r}", warnings == "")

                editor.query_one("#lineup-section-budget", TextArea).text = "max_budget_usd: 20\n"
                await pilot.pause(0.05)
                editor.action_draft_about()
                await pilot.pause(0.05)
                about_text = editor.query_one("#lineup-about", TextArea).text
                ctx.check(f"about was drafted, never blank, got {about_text!r}", bool(about_text.strip()))
                ctx.check("no stale marker right after drafting",
                          _static_text(editor.query_one("#lineup-about-stale")) == "")
                editor.action_add_assignment()
                await pilot.pause(0.05)
                ctx.check("a further change marks the about stale",
                          "stale" in _static_text(editor.query_one("#lineup-about-stale")))
                editor.action_delete_assignment()
                await pilot.pause(0.05)

                editor.query_one("#lineup-save", Button).press()
                await pilot.pause(0.2)
                ctx.check("save offers to activate", isinstance(app.screen, _ActivateLineupConfirm))
                app.screen.query_one("#confirm-yes", Button).press()
                await pilot.pause(0.2)

                from halo_harness.teams_yaml import load_team_template_raw, resolve_role_table, \
                    resolve_team_template, validate_team_template
                raw = load_team_template_raw("pilot-lineup")
                ctx.check(f"teams_yaml loads it clean, got {validate_team_template(raw)}",
                          validate_team_template(raw) == [])
                resolved = resolve_team_template("pilot-lineup")
                table, notes = resolve_role_table(resolved)
                ctx.check(f"both roles resolve to the strong model, got {table}, notes {notes}",
                          table.get("boss") == "or:vendor/strong-model"
                          and table.get("worker") == "or:vendor/strong-model" and not notes)
                ctx.check(f"budget round-tripped, got {resolved.get('budget')}",
                          resolved["budget"]["max_budget_usd"] == 20)

                from halo_harness.theme import get_config_value
                ctx.check(f"the activation prompt set team:, got {get_config_value('team', default=None)!r}",
                          get_config_value("team", default=None) == "pilot-lineup")

                import io
                from contextlib import redirect_stdout
                from halo_harness.teams_cli import cmd_teams
                buf = io.StringIO()
                with redirect_stdout(buf):
                    cmd_teams(["show", "pilot-lineup"])
                printed = buf.getvalue()
                ctx.check(f"halo teams show prints the about text, got {printed!r}", about_text.strip() in printed)
    asyncio.run(body())


@test
def test_lineup_editor_editing_an_installed_template(ctx: Ctx):
    """Tests section: "editing an installed template"."""
    from halo_harness.teams_yaml import ensure_builtin_team_templates, list_team_templates, \
        load_team_template_raw
    from halo_harness.tui.dialogs.lineup_editor import LineupEditor
    from textual.widgets import Button, Input

    async def body():
        with _Env() as e:
            ensure_builtin_team_templates(state_dir=e.state_dir)
            installed = list_team_templates(state_dir=e.state_dir, include_templates=False)
            ctx.check(f"a shipped template was copied in to edit, got {installed}", installed)
            name = installed[0]
            template = load_team_template_raw(name, state_dir=e.state_dir)
            app = _host_screen(LineupEditor(name, template, FIXTURE_MODELS, state_dir=e.state_dir))
            async with app.run_test(size=(140, 55)) as pilot:
                await pilot.pause(0.1)
                editor = app.screen
                ctx.check("opened with its own existing assignments", len(editor._agents()) >= 1)
                from textual.widgets import TextArea
                editor.query_one("#lineup-about", TextArea).text = "Edited by the pilot."
                editor.query_one("#lineup-save", Button).press()
                await pilot.pause(0.2)
                from halo_harness.tui.dialogs.lineup_editor import _ActivateLineupConfirm
                if isinstance(app.screen, _ActivateLineupConfirm):
                    app.screen.query_one("#confirm-no", Button).press()
                    await pilot.pause(0.2)
                reread = load_team_template_raw(name, state_dir=e.state_dir)
                ctx.check(f"the edit round-tripped, got {reread.get('about')!r}",
                          reread["about"] == "Edited by the pilot.")
    asyncio.run(body())


@test
def test_roles_step_lineup_pane_applies_and_legacy_pane_still_works(ctx: Ctx):
    """Deliverable 3 ("replaces the legacy-template editing in
    RolesStep") plus "a legacy role template still loads (through the
    2.0.4 round-4 migration) and saves as a lineup" -- both panes of the
    retitled "Roles and lineup" step, in one pilot."""
    from halo_harness.roles import configured_role_table
    from halo_harness.theme import get_config_value, set_config_value
    from halo_harness.tui.dialogs.init_wizard import InitWizardApp, WizardState
    from textual.widgets import Button, OptionList

    async def body():
        with _Env():
            set_config_value("model", "or:vendor/strong-model")
            state = WizardState(cwd=REPO_DIR, step_keys=("roles",), no_live=True)
            app = InitWizardApp(state)
            async with app.run_test(size=(130, 50)) as pilot:
                await pilot.pause(0.15)
                ctx.check(f"the step title says Roles and lineup, got {state.title()}",
                          "Roles and lineup" in state.title())
                lineup_list = app.screen.query_one("#wiz-lineup-templates", OptionList)
                ctx.check("the lineup pane lists the shipped lineups by default", lineup_list.option_count > 0)
                lineup_list.highlighted = 0
                app.screen.query_one("#wiz-lineup-use", Button).press()
                await pilot.pause(0.2)
                ctx.check(f"a lineup apply note landed in state.written, got {state.written}",
                          any("applied" in w for w in state.written))

            # A fresh run: use the LEGACY pane's "quality" preset -- same
            # pinned behaviour test_tui.py's own round-4 tests already
            # cover, re-verified here through the now-toggled pane.
            state2 = WizardState(cwd=REPO_DIR, step_keys=("roles",), no_live=True)
            app2 = InitWizardApp(state2)
            async with app2.run_test(size=(130, 50)) as pilot:
                await pilot.pause(0.15)
                app2.screen.query_one("#wiz-roles-pane-legacy-btn", Button).press()
                await pilot.pause(0.05)
                picker = app2.screen.query_one("#wiz-roles-templates")
                names = [str(picker.get_option_at_index(i).id) for i in range(picker.option_count)]
                picker.highlighted = names.index("quality")
                await pilot.pause(0.05)
                app2.screen.query_one("#wiz-roles-use", Button).press()
                await pilot.pause(0.2)
                table = configured_role_table()
                ctx.check(f"the legacy pane still applies a real role table, got {table}",
                          table.get("judge") == "or:vendor/strong-model")
                ctx.check(f"migration still fires from the legacy pane, got {state2.written}",
                          any("migrated" in w for w in state2.written))
                from halo_harness.teams_yaml import list_team_templates
                ctx.check("a 'migrated' lineup now exists",
                          "migrated" in list_team_templates(include_templates=False))
    asyncio.run(body())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
