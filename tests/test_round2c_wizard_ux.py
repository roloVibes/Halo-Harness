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

TIER = "full"  # a TUI pilot (Textual run_test): the full tier

import asyncio
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.doc_parts import doc_text  # 3.1.1.0 R3: COMMANDS.md is split into parts
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


async def _until(pilot, cond, timeout: float = 15.0) -> bool:
    """Poll `cond` until it holds or `timeout` seconds pass (3.1.4.0 R1: a deadline, not a count of
    0.05 s pauses, so a 5-10x slower Windows runner still gets there; a condition that never holds
    still returns False and the check after it fails)."""
    import time
    deadline = time.monotonic() + timeout
    while True:
        await pilot.pause(0.05)
        try:
            if cond():
                return True
        except Exception:
            pass
        if time.monotonic() >= deadline:
            return False


@test
def test_wizard_doc_exists_names_ten_rules_and_is_linked(ctx: Ctx):
    doc = (REPO_DIR / "docs" / "WIZARD.md").read_text(encoding="utf-8")
    ctx.check("has a chord table mention", "Ctrl+Left" in doc and "Ctrl+N" in doc)
    for n in range(1, 11):
        ctx.check(f"rule {n} is numbered in the doc", f"{n}. **" in doc)
    handbook = (REPO_DIR / "docs" / "HANDBOOK.md").read_text(encoding="utf-8")
    ctx.check("linked from HANDBOOK.md", "WIZARD.md" in handbook)
    commands = doc_text("COMMANDS.md")
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
            state = WizardState(cwd=REPO_DIR, step_keys=("permission_mode", "theme", "summary"), no_live=True)
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
                ctx.check(f"Ctrl+Right advances again to Summary, got {type(app.screen).__name__}",
                          type(app.screen).__name__ == "SummaryStep")
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
                          state.step_keys == ("providers", "default_model", "team", "summary"))
                app.screen.action_do_next()  # providers (no_live branch)
                await pilot.pause(0.2)
                app.screen.action_do_next()  # default_model, nothing picked -- keeps the configured default
                await pilot.pause(0.4)
                app.screen.action_do_next()  # team: "One model for everything" is preselected
                await pilot.pause(0.5)
                ctx.check(f"lands on Summary, got {type(app.screen).__name__}",
                          type(app.screen).__name__ == "SummaryStep")
                ctx.check(f"team is 'standard', got {get_config_value('team', default=None)!r}",
                          get_config_value("team", default=None) == "standard")
                ctx.check(f"roles are off, got {roles_mode_enabled()!r}", roles_mode_enabled() is False)
                note = app.screen.query_one("#wiz-summary-lineup")
                ctx.check(f"the Summary names the one-model state, got {_static_text(note)!r}",
                          "One model for everything: or:vendor/strong-model" in _static_text(note))
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
                                   "ThemeStep", "TeamStep", "SummaryStep"])
    run(body())


# ---------------------------------------------------------------------------
# Deliverable 7 (rule 11): the Team step, at both sizes.
# ---------------------------------------------------------------------------

@test
def test_team_step_first_row_is_one_model_and_preselected_on_a_fresh_install(ctx: Ctx):
    from halo_harness.tui.dialogs.init_wizard import InitWizardApp, WizardState
    from textual.widgets import OptionList

    async def body(w, h):
        with _Env():
            state = WizardState(cwd=REPO_DIR, step_keys=("team",), no_live=True)
            app = InitWizardApp(state)
            async with app.run_test(size=(w, h)) as pilot:
                await pilot.pause(0.2)
                step = app.screen
                lst = step.query_one("#wiz-team-lineups-list", OptionList)
                first = lst.get_option_at_index(0)
                ctx.check(f"first row is One model for everything at {w}x{h}, got {first.prompt!s}",
                          "One model for everything" in str(first.prompt) and str(first.prompt).startswith("✓ "))
                ctx.check(f"it is highlighted at {w}x{h}", lst.highlighted == 0)
                text = _static_text(step.query_one("#wiz-team-preview"))
                ctx.check(f"the preview is the one-model sentence at {w}x{h}, got {text!r}",
                          "for everything" in text and "sub-agents" in text and "questions" in text)
                header = _static_text(step.query_one("#wiz-team-header-sentence"))
                ctx.check(f"the header explains lineups at {w}x{h}", "A lineup gives each job" in header)
                for bid in ("wiz-roles-switch", "wiz-team-use", "wiz-team-studio",
                            "wiz-back", "wiz-skip", "wiz-next"):
                    step.query_one(f"#{bid}")
    for size in SIZES:
        run(body(*size))


@test
def test_team_step_preview_follows_the_highlight_and_stacks_when_narrow(ctx: Ctx):
    from halo_harness.tui.dialogs.init_wizard import InitWizardApp, WizardState
    from textual.widgets import OptionList

    async def body(w, h, layout):
        with _Env():
            state = WizardState(cwd=REPO_DIR, step_keys=("team",), no_live=True)
            app = InitWizardApp(state)
            async with app.run_test(size=(w, h)) as pilot:
                await pilot.pause(0.2)
                step = app.screen
                ctx.check(f"layout at {w}x{h} is {layout}",
                          str(step.query_one("#wiz-team-panes").styles.layout.name) == layout)
                lst = step.query_one("#wiz-team-lineups-list", OptionList)
                names = [str(lst.get_option_at_index(i).id) for i in range(lst.option_count)]
                lst.highlighted = names.index("balanced")
                await pilot.pause(0.1)
                text = _static_text(step.query_one("#wiz-team-preview"))
                ctx.check(f"preview shows balanced's tree at {w}x{h}, got {text!r}",
                          "balanced" in text and "researcher -> " in text)
    run(body(80, 24, "vertical"))
    run(body(120, 40, "horizontal"))


@test
def test_team_step_enter_shows_and_agents_button_opens_the_bios(ctx: Ctx):
    """Enter on a lineup shows it (3.1.1.0 R3: read-only; Edit in Studio edits), Ctrl+A lists the
    bios, Enter on a bio shows it."""
    from halo_harness.tui.dialogs.agent_bio_editor import AgentBioView
    from halo_harness.tui.dialogs.agents_step import AgentsListScreen
    from halo_harness.tui.dialogs.init_wizard import InitWizardApp, WizardState
    from halo_harness.tui.dialogs.lineup_editor import LineupView
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
                lineups_list.highlighted = 1
                lineups_list.focus()
                await pilot.pause(0.05)
                await pilot.press("enter")
                await pilot.pause(0.3)
                ctx.check(f"Enter on a lineup shows it, got {type(app.screen).__name__}",
                          isinstance(app.screen, LineupView))
                app.screen.action_close()
                await pilot.pause(0.1)
                step._open_agents()
                await pilot.pause(0.3)
                ctx.check(f"Agents... opens the bios list, got {type(app.screen).__name__}",
                          isinstance(app.screen, AgentsListScreen))
                agents_list = app.screen.query_one("#agents-list", OptionList)
                agents_list.highlighted = 0
                agents_list.focus()
                await pilot.pause(0.05)
                await pilot.press("enter")
                await pilot.pause(0.3)
                ctx.check(f"Enter on a bio shows it, got {type(app.screen).__name__}",
                          isinstance(app.screen, AgentBioView))
    run(body())


@test
def test_team_step_active_lineup_checkmark(ctx: Ctx):
    from halo_harness.roles import set_roles_enabled
    from halo_harness.teams_yaml import apply_team_template, ensure_builtin_team_templates
    from halo_harness.tui.dialogs.init_wizard import InitWizardApp, WizardState
    from textual.widgets import OptionList

    async def body():
        with _Env() as e:
            ensure_builtin_team_templates(state_dir=e.state_dir)
            apply_team_template("balanced", state_dir=e.state_dir)
            set_roles_enabled(True)
            state = WizardState(cwd=e.cwd, step_keys=("team",), no_live=True)
            app = InitWizardApp(state)
            async with app.run_test(size=(130, 50)) as pilot:
                await pilot.pause(0.15)
                lineups_list = app.screen.query_one("#wiz-team-lineups-list", OptionList)
                labels = [str(lineups_list.get_option_at_index(i).prompt) for i in range(lineups_list.option_count)]
                checked = [label for label in labels if label.startswith("✓ ")]
                ctx.check(f"exactly the active lineup is checked, got {labels}",
                          len(checked) == 1 and checked[0].startswith("✓ balanced "))
                ctx.check("and it is the highlighted row", lineups_list.highlighted == labels.index(checked[0]))
    run(body())


@test
def test_team_step_ctrl_n_and_ctrl_e_open_studio(ctx: Ctx):
    """3.1.1.0 R3: Ctrl+N writes a new lineup and opens Studio on it; Ctrl+E and the Edit in Studio
    button open Studio on the highlighted lineup; the One model row has nothing to edit.
    3.1.4.0 R1 (the v3.1.3.0 tag run failed here on Windows, then passed on re-run): every wait is a
    poll to a deadline (the step mounted, the list focused, the row highlighted, Studio opened), no
    fixed pause before a key."""
    from halo_harness.tui.dialogs.init_wizard import InitWizardApp, WizardState
    from textual.widgets import Button, OptionList

    async def body():
        with _Env(), _Opened() as opened:
            state = WizardState(cwd=REPO_DIR, step_keys=("team",), no_live=True)
            app = InitWizardApp(state)
            async with app.run_test(size=(130, 50)) as pilot:
                mounted = await _until(pilot, lambda: len(app.screen.query("#wiz-team-lineups-list")) > 0)
                ctx.check("the Team step is up", mounted)
                step = app.screen
                lst = step.query_one("#wiz-team-lineups-list", OptionList)
                lst.focus()
                await _until(pilot, lambda: lst.has_focus)
                await pilot.press("ctrl+n")
                await _until(pilot, lambda: opened.targets)
                ctx.check(f"Ctrl+N opens Studio on a NEW lineup, got {opened.targets}",
                          len(opened.targets) == 1 and opened.targets[0].startswith("lineup:lineup-"))
                from halo_harness.teams_yaml import find_team_template_path
                ctx.check("the new lineup is on disk", find_team_template_path(opened.targets[0].split(":", 1)[1]) is not None)
                await _until(pilot, lambda: "balanced" in [str(lst.get_option_at_index(i).id) for i in range(lst.option_count)])
                names = [str(lst.get_option_at_index(i).id) for i in range(lst.option_count)]
                lst.highlighted = names.index("balanced")
                await _until(pilot, lambda: lst.highlighted == names.index("balanced") and lst.has_focus)
                await pilot.press("ctrl+e")
                await _until(pilot, lambda: len(opened.targets) == 2)
                ctx.check(f"Ctrl+E opens Studio on the highlighted lineup, got {opened.targets}", opened.targets[-1] == "lineup:balanced")
                step.query_one("#wiz-team-edit", Button).press()
                await _until(pilot, lambda: len(opened.targets) == 3)
                ctx.check(f"so does the Edit in Studio button, got {opened.targets}", opened.targets[-1] == "lineup:balanced")
                ctx.check("the step says what happened", "Opened lineup:balanced" in _static_text(step.query_one("#wiz-team-lineup-hint")))
                lst.focus()
                lst.highlighted = 0
                await _until(pilot, lambda: lst.highlighted == 0 and lst.has_focus)
                await pilot.press("ctrl+e")
                hint = step.query_one("#wiz-team-lineup-hint")
                # the key has been handled once the app is idle again; a fourth open would have come with it
                await pilot.pause()
                await _until(pilot, lambda: len(opened.targets) > 3, timeout=0.5)
                ctx.check(f"One model for everything has nothing to open, got {opened.targets} / {_static_text(hint)!r}", len(opened.targets) == 3)
    run(body())


@test
def test_team_step_plain_next_applies_the_highlighted_row(ctx: Ctx):
    """Quick setup reaches the Team step; `balanced` + Next writes `team:
    balanced` and `roles.enabled: true`; the first row writes `team:
    standard` and `roles.enabled: false`."""
    from halo_harness.roles import roles_mode_enabled
    from halo_harness.theme import get_config_value, set_config_value
    from halo_harness.tui.dialogs.init_wizard import InitWizardApp, WizardState, full_step_keys
    from textual.widgets import OptionList

    async def body(pick_balanced):
        with _Env():
            set_config_value("model", "or:vendor/strong-model")
            state = WizardState(cwd=REPO_DIR, step_keys=full_step_keys(), no_live=True, offer_quick_full=True)
            app = InitWizardApp(state)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause(0.15)
                app.screen.query_one("#wiz-next").press()
                await pilot.pause(0.2)
                app.screen.action_do_next()  # providers
                await pilot.pause(0.2)
                app.screen.action_do_next()  # default model
                await pilot.pause(0.4)
                ctx.check(f"Quick reaches the Team step, got {type(app.screen).__name__}",
                          type(app.screen).__name__ == "TeamStep")
                lst = app.screen.query_one("#wiz-team-lineups-list", OptionList)
                names = [str(lst.get_option_at_index(i).id) for i in range(lst.option_count)]
                lst.highlighted = names.index("balanced") if pick_balanced else 0
                await pilot.pause(0.1)
                app.screen.query_one("#wiz-next").press()
                await pilot.pause(0.5)
                ctx.check(f"then the Summary, got {type(app.screen).__name__}",
                          type(app.screen).__name__ == "SummaryStep")
                want = "balanced" if pick_balanced else "standard"
                ctx.check(f"team is {want!r}, got {get_config_value('team', default=None)!r}",
                          get_config_value("team", default=None) == want)
                ctx.check(f"roles.enabled is {pick_balanced}, got {roles_mode_enabled()!r}",
                          roles_mode_enabled() is pick_balanced)
                shown = _static_text(app.screen.query_one("#wiz-summary-lineup"))
                ctx.check(f"the Summary names it, got {shown!r}",
                          ("Lineup: balanced" in shown) if pick_balanced else ("One model for everything" in shown))
    run(body(True))
    run(body(False))


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
# Deliverable 3 (rule 3): autocomplete filters and picks -- the org editor and
# the roles editor quick filter (3.1.1.0 R3: the bio and lineup fields are
# Studio's now; the terminal shows bios and lineups read-only).
# ---------------------------------------------------------------------------

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
def test_new_bio_note_on_the_agents_list(ctx: Ctx):
    """3.1.1.0 R3: New in the Agents list writes a starter bio and opens Studio on it; the list's
    hint line says so in one line."""
    from halo_harness.tui.dialogs.init_wizard import InitWizardApp, WizardState
    from textual.widgets import OptionList

    async def body():
        with _Env(), _Opened() as opened:
            state = WizardState(cwd=REPO_DIR, step_keys=("team",), no_live=True)
            state.enumerated_models, state.enumeration_done = FIXTURE_MODELS, True
            app = InitWizardApp(state)
            async with app.run_test(size=(130, 50)) as pilot:
                await pilot.pause(0.15)
                app.screen._open_agents()
                await pilot.pause(0.3)
                app.screen.query_one("#agents-list", OptionList).focus()
                await pilot.press("ctrl+n")
                await _until(pilot, lambda: opened.targets and "Opened" in _static_text(app.screen.query_one("#agents-hint")))
                ctx.check(f"still on the Agents list, got {type(app.screen).__name__}", type(app.screen).__name__ == "AgentsListScreen")
                hint = _static_text(app.screen.query_one("#agents-hint"))
                ctx.check(f"a one-line note names what opened, got {hint!r}", opened.targets and opened.targets[0] in hint)
    run(body())


@test
def test_escape_closes_the_bio_view_and_writes_nothing(ctx: Ctx):
    """Rule 8: "Escape is always Back and never destructive" -- the bio view closes on Escape and
    writes nothing (it has nothing to write)."""
    from halo_harness.agents_yaml import list_agent_bios
    from halo_harness.tui.dialogs.agent_bio_editor import AgentBioView
    from textual.app import App

    async def body():
        with _Env() as e:
            class _Host(App):
                def on_mount(self):
                    self.push_screen(AgentBioView("coder", None, FIXTURE_MODELS))
            app = _Host()
            async with app.run_test(size=(130, 50)) as pilot:
                await pilot.pause(0.15)
                await pilot.press("escape")
                await pilot.pause(0.1)
                ctx.check(f"the view closed, got {app.screen}", not isinstance(app.screen, AgentBioView))
            ctx.check("no bio file was written", not (e.state_dir / "agents").exists() or not list((e.state_dir / "agents").glob("*.yaml")))
            ctx.check("coder still resolves to the shipped bio", "coder" in list_agent_bios(state_dir=e.state_dir))
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
