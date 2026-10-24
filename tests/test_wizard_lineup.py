"""tests.test_wizard_lineup -- Halo 2.0.5 round 2 (wizard: agent bios and
lineups): deliverable 2 (the roles editor's Models/Agents picker source)
and deliverable 3 (the lineup editor) plus the `about:` context-builder
fold-in. 3.1.1.0 R3: Studio is the one editor of lineups -- the lineups are
made and saved through Studio's routes (the ones its Lineups panel and
inspector call; the inspector in a browser: tests/test_studio_edit_route.py)
and the terminal shows them in the read-only view (`tui/dialogs/
lineup_editor.py`: `e` opens Studio, `t` probes a model). Hermetic: no
network, no real model, no Studio started.
"""
from __future__ import annotations

TIER = "full"  # a TUI pilot (Textual run_test): the full tier

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
    from halo_harness.tui.dialogs.lineup_view_text import draft_about_text
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
    from halo_harness.tui.dialogs.lineup_view_text import lineup_warnings
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
    from halo_harness.tui.dialogs.lineup_view_text import lineup_warnings
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
    trip". 3.1.1.0 R3: "New bio..." writes a starter bio on the role's
    model, records it for the role and opens Studio's bio form on it
    (`tui.studio_open.OPENER` records the target; no Studio starts)."""
    from textual.app import App
    from textual.screen import Screen
    from textual.widgets import OptionList

    from halo_harness.agents_yaml import save_agent_bio
    from halo_harness.tui import studio_open
    from halo_harness.tui.dialogs.model_picker import ModelPicker
    from halo_harness.tui.dialogs.roles_editor import RolesEditor

    class HostApp(App):
        def on_mount(self):
            self.push_screen(Screen())

    opened = []
    saved_opener = studio_open.OPENER
    studio_open.OPENER = lambda target, **_kw: opened.append(target.text) or {"url": "u", "how": "focused", "pages": 1,
                                                                              "target": target.text}

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

                # "New bio..." round trip: the starter bio, recorded, and Studio on it.
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
                ctx.check(f"back on the roles editor, no form in the terminal, got {type(app.screen).__name__}",
                          app.screen is editor)
                await pilot.press("enter")  # blank effort
                for _ in range(20):
                    await pilot.pause(0.05)
                    if opened:
                        break
                new_recorded = editor.roles.get("orchestrator")
                ctx.check(f"the fresh bio is now recorded on the role's model, got {new_recorded}",
                          new_recorded["agent"].startswith("agent-") and new_recorded["model"] == "or:vendor/strong-model")
                ctx.check(f"and Studio opened on it, got {opened}", opened == [f"bio:{new_recorded['agent']}"])
    try:
        asyncio.run(body())
    finally:
        studio_open.OPENER = saved_opener


def _host_screen(screen):
    from textual.app import App

    class _Host(App):
        result = None

        def on_mount(self):
            def _after(r):
                self.result = r
            self.push_screen(screen, _after)
    return _Host()


def _studio(e, method: str, path: str, body: "dict | None" = None) -> "tuple[int, dict]":
    """One of Studio's routes, the ones its Lineups panel and inspector use."""
    from halo_harness.studio.api import Request, dispatch
    return dispatch(Request(method=method, path=path, query={}, body=body or {}, cwd=e.cwd, state_dir=e.state_dir))


@test
def test_lineup_through_studio_routes_then_the_view(ctx: Ctx):
    """Tests section: "new lineup with one role by model and one by bio,
    the about text, one advanced section (budget), save, teams_yaml loads
    it clean, halo teams show prints the about text, the activation
    sets team:". 3.1.1.0 R3: made and saved through Studio's routes (New,
    Save, Apply), then shown in the terminal's read-only lineup view."""
    from halo_harness.agents_yaml import ensure_bio_for_model, save_agent_bio
    from halo_harness.tui.dialogs.lineup_editor import LineupView

    with _Env() as e:
        save_agent_bio("lineup-worker", {"description": "a worker bio", "models": {"preference": "or:vendor/strong-model"}})
        pinned = ensure_bio_for_model("or:vendor/strong-model")  # Studio's model picker on a card does the same
        status, made = _studio(e, "POST", "lineup", {"name": "pilot-lineup"})
        ctx.check(f"New makes the lineup, got {status}", status == 201)
        raw = dict(made["raw"], about="The boss splits the work; the worker writes it.", budget={"max_budget_usd": 20},
                   agents=[{"role": "main", "as": "boss", "agent": pinned},
                           {"role": "subagent", "as": "worker", "agent": "lineup-worker"}])
        status, saved = _studio(e, "PUT", "lineup/pilot-lineup", {"raw": raw})
        ctx.check(f"Save validates and writes it, got {status} {saved.get('problems')}", status == 200)
        status, applied = _studio(e, "POST", "lineup/pilot-lineup/apply")
        ctx.check(f"Apply makes it the active team, got {status} {applied.get('active_team')}",
                  status == 200 and applied.get("active_team") == "pilot-lineup")

        from halo_harness.teams_yaml import load_team_template_raw, resolve_role_table, resolve_team_template, \
            validate_team_template
        ctx.check("teams_yaml loads it clean", validate_team_template(load_team_template_raw("pilot-lineup")) == [])
        resolved = resolve_team_template("pilot-lineup")
        table, notes = resolve_role_table(resolved)
        ctx.check(f"both roles resolve to the strong model, got {table}, notes {notes}",
                  table.get("boss") == "or:vendor/strong-model" and table.get("worker") == "or:vendor/strong-model" and not notes)
        ctx.check(f"budget round-tripped, got {resolved.get('budget')}", resolved["budget"]["max_budget_usd"] == 20)
        import io
        from contextlib import redirect_stdout
        from halo_harness.teams_cli import cmd_teams
        buf = io.StringIO()
        with redirect_stdout(buf):
            cmd_teams(["show", "pilot-lineup"])
        ctx.check("halo teams show prints the about text", "The boss splits the work" in buf.getvalue())

        async def body():
            app = _host_screen(LineupView("pilot-lineup", None, FIXTURE_MODELS))
            async with app.run_test(size=(140, 55)) as pilot:
                await pilot.pause(0.2)
                view = app.screen
                ctx.check(f"no warnings once both rows resolve, got {_static_text(view.query_one('#lineup-warnings'))!r}",
                          _static_text(view.query_one("#lineup-warnings")) == "")
                ctx.check("the budget section shows as its YAML", _static_text(view.query_one("#lineup-section-budget")) == "max_budget_usd: 20")
                ctx.check("the about text shows", _static_text(view.query_one("#lineup-about")).startswith("The boss splits"))
        asyncio.run(body())


@test
def test_lineup_installed_template_saved_in_studio_and_e_in_the_view(ctx: Ctx):
    """Tests section: "editing an installed template" -- Studio saves the installed copy (the
    terminal's `e` opens it there); the view shows the edit."""
    from halo_harness.teams_yaml import ensure_builtin_team_templates, list_team_templates, load_team_template_raw
    from halo_harness.tui import studio_open
    from halo_harness.tui.dialogs.lineup_editor import LineupView

    with _Env() as e:
        ensure_builtin_team_templates(state_dir=e.state_dir)
        installed = list_team_templates(state_dir=e.state_dir, include_templates=False)
        ctx.check(f"a shipped template was copied in to edit, got {installed}", installed)
        name = installed[0]
        raw = load_team_template_raw(name, state_dir=e.state_dir)
        raw["about"] = "Edited by the pilot."
        status, _saved = _studio(e, "PUT", f"lineup/{name}", {"raw": {k: v for k, v in raw.items() if not k.startswith("_")}})
        ctx.check(f"the installed copy saves, got {status}", status == 200)
        ctx.check("the edit round-tripped", load_team_template_raw(name, state_dir=e.state_dir)["about"] == "Edited by the pilot.")
        opened = []
        saved_opener = studio_open.OPENER
        studio_open.OPENER = lambda target, **_kw: opened.append(target.text) or {"url": "u", "how": "focused", "pages": 1,
                                                                                  "target": target.text}

        async def body():
            app = _host_screen(LineupView(name, None, FIXTURE_MODELS, state_dir=e.state_dir))
            async with app.run_test(size=(140, 55)) as pilot:
                await pilot.pause(0.2)
                view = app.screen
                ctx.check("opened with its own existing assignments", len(view._agents()) >= 1)
                ctx.check("the view shows the edit", _static_text(view.query_one("#lineup-about")) == "Edited by the pilot.")
                await pilot.press("e")
                for _ in range(20):
                    await pilot.pause(0.05)
                    if opened:
                        break
                ctx.check(f"e opens Studio on the lineup, got {opened}", opened == [f"lineup:{name}"])
        try:
            asyncio.run(body())
        finally:
            studio_open.OPENER = saved_opener


@test
def test_lineup_view_t_key_probes_the_highlighted_assignment(ctx: Ctx):
    """3.0.7.0 R1 ("Test this model"): `t` in the lineup view runs the
    one-token probe (model_probe, stubbed here) on the highlighted row's
    model on a worker and shows the line in the cost footer; the tiers
    section shows as its YAML list."""
    from halo_harness import model_probe
    from halo_harness.agents_yaml import save_agent_bio
    from halo_harness.tui.dialogs.lineup_editor import LineupView
    from textual.widgets import OptionList

    async def body():
        with _Env() as e:
            save_agent_bio("probe-bio", {"description": "p", "models": {"preference": "or:vendor/strong-model"}},
                           state_dir=e.state_dir)
            calls = []
            saved = model_probe.probe_model
            model_probe.probe_model = lambda ref, **kw: calls.append(ref) or {
                "ok": True, "latency_ms": 42, "error": "", "cost_line": "", "ref": ref, "reply": "ok"}
            try:
                template = {"agents": [{"agent": "probe-bio", "role": "main"}],
                            "tiers": [{"name": "top", "members": ["main"]}]}
                app = _host_screen(LineupView("probe-lineup", template, FIXTURE_MODELS, state_dir=e.state_dir))
                async with app.run_test(size=(140, 55)) as pilot:
                    await pilot.pause(0.1)
                    view = app.screen
                    view.query_one("#lineup-assignments", OptionList).focus()
                    await pilot.press("t")
                    for _ in range(40):
                        await pilot.pause(0.05)
                        if "ok in" in _static_text(view.query_one("#lineup-cost-footer")):
                            break
                    footer = _static_text(view.query_one("#lineup-cost-footer"))
                    ctx.check(f"the probe ran on the assignment's model, got {calls}", calls == ["or:vendor/strong-model"])
                    ctx.check(f"the line lands in the footer, got {footer!r}",
                              "test: or:vendor/strong-model: ok in 42 ms ('ok')" in footer)
                    ctx.check("the tiers section shows as its YAML list",
                              _static_text(view.query_one("#lineup-section-tiers")) == "- name: top\n  members:\n  - main")
            finally:
                model_probe.probe_model = saved
    asyncio.run(body())


@test
def test_team_step_lineup_pane_applies_on_next_and_migrates_a_legacy_table(ctx: Ctx):
    """Halo 2.0.5 round 2c (rule 11): the "Agents" step and "Roles and
    lineup" step merged into one "Team" step -- its Lineups pane (left)
    is what deliverable 3's "replaces the legacy-template editing in
    RolesStep" became; a plain Next (footer, no separate "Use this
    lineup" button any more) applies the highlighted lineup, same as
    round 2b's own "a plain Next applies the visible pane" rule. The
    migration this test also pins (2.0.4 round 4: "a legacy role table
    still loads and saves as a lineup") now fires the instant the step's
    Lineups pane is BUILT (every time Custom roles is on), not only on an
    explicit apply -- there is no "Legacy roles" pane left to apply
    FROM."""
    from halo_harness.roles import configured_role_table
    from halo_harness.theme import set_config_value
    from halo_harness.tui.dialogs.init_wizard import InitWizardApp, WizardState
    from textual.widgets import OptionList

    async def body():
        with _Env():
            set_config_value("model", "or:vendor/strong-model")
            state = WizardState(cwd=REPO_DIR, step_keys=("team",), no_live=True)
            app = InitWizardApp(state)
            async with app.run_test(size=(130, 50)) as pilot:
                await pilot.pause(0.15)
                ctx.check(f"the step title says Team, got {state.title()}", "Team" in state.title())
                lineup_list = app.screen.query_one("#wiz-team-lineups-list", OptionList)
                ctx.check("the Lineups pane lists the shipped lineups by default", lineup_list.option_count > 0)
                # 3.1.9.0 R2: row 0 (One model for everything) applies no lineup any more; a lineup row does
                names = [str(lineup_list.get_option_at_index(i).id) for i in range(lineup_list.option_count)]
                lineup_list.highlighted = names.index("balanced")
                app.screen.action_do_next()  # the footer's plain Next -- no separate "Use" button any more
                await pilot.pause(0.2)
                ctx.check(f"a lineup apply note landed in state.written, got {state.written}",
                          any("applied" in w for w in state.written))

            # A fresh run with a hand-edited LEGACY role table and no
            # "migrated" lineup yet -- same pinned behaviour test_tui.py's
            # own round-4 tests already cover, re-verified here through
            # the Team step's own Lineups pane.
            set_config_value("roles.judge", "or:vendor/strong-model")
            state2 = WizardState(cwd=REPO_DIR, step_keys=("team",), no_live=True)
            app2 = InitWizardApp(state2)
            async with app2.run_test(size=(130, 50)) as pilot:
                await pilot.pause(0.15)
                table = configured_role_table()
                ctx.check(f"the legacy table is still a real role table, got {table}",
                          table.get("judge") == "or:vendor/strong-model")
                from halo_harness.teams_yaml import list_team_templates
                ctx.check("opening the Team step alone already migrated it to a 'migrated' lineup",
                          "migrated" in list_team_templates(include_templates=False))
    asyncio.run(body())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
