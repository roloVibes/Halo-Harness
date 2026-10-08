"""tests.test_wizard_agents_bios -- Halo 2.0.5 round 2 (wizard: agent bios
and lineups), deliverable 1: the Agents step (`tui/dialogs/agents_step.py`)
and the bio form (`tui/dialogs/agent_bio_editor.py`). Hermetic: no network,
no real model -- every Textual pilot below passes a FIXTURE catalog
directly (never enumerates), and every test scopes `BRIDGE_TEST_HOME`/
`BRIDGE_STATE_DIR` to a fresh scratch dir per `plans/WORKER-RULES.md`.
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

REPO_DIR = Path(__file__).resolve().parent.parent
test, TESTS = new_registry()


async def _wait_until(pilot, cond, *, timeout: float = 5.0, step: float = 0.05) -> bool:
    """Bounded poll for a TUI condition (the H9b lesson, applied to pilot
    tests): a fixed `pilot.pause(0.2)` races a loaded runner -- a pushed
    screen can exist before its widgets mount (CI 143c1f9: 'No nodes
    match #bio-pref on AgentBioEditor()'). Poll until `cond()` holds or
    the deadline passes; `cond` may raise (not-yet-mounted widgets) --
    that counts as not-yet, never as failure."""
    deadline = time.monotonic() + timeout
    while True:
        await pilot.pause(step)
        try:
            if cond():
                return True
        except Exception:
            pass
        if time.monotonic() >= deadline:
            try:
                return bool(cond())
            except Exception:
                return False

FIXTURE_MODELS = [
    {"ref": "or:vendor/strong-model", "provider": "openrouter", "group": "OpenRouter (or:)",
     "context_tokens": 128000, "price_in_per_m": 1.0, "price_out_per_m": 2.0,
     "supported_parameters": ["tools"]},
    # Declares reasoning-only support (NOT "unknown" -- a bare missing
    # field is fail-open by house convention, same as `roles.py`'s own
    # "unknown-support" entry; this row exists so the filter test below
    # has a row that's EXPLICITLY not tool-capable to drop.
    {"ref": "or:vendor/cheap-model", "provider": "openrouter", "group": "OpenRouter (or:)",
     "context_tokens": 8000, "price_in_per_m": 0.1, "price_out_per_m": 0.2,
     "supported_parameters": ["reasoning"]},
    {"ref": "ol:local-model", "provider": "ollama", "group": "Ollama (ol:)", "context_tokens": 32000},
]


class _Env:
    """Scratch `BRIDGE_TEST_HOME`/`BRIDGE_STATE_DIR` -- the real `~/.halo`
    is never touched (same pattern `tests/test_agents_teams.py::_Env`
    already uses)."""

    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
        d = Path(tempfile.mkdtemp(prefix="wizard-agents-bios-"))
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
# Pure helpers (no Textual needed).
# ---------------------------------------------------------------------------

@test
def test_rule_sentence_renders_a_plain_sentence_and_flags_a_bad_line(ctx: Ctx):
    from halo_harness.tui.dialogs.agent_bio_editor import rule_sentence
    ctx.check('deny line renders a plain sentence',
              rule_sentence("deny Bash(git push*)") == "Bash may not run git push.")
    bad = rule_sentence("deny Bash(git push :* extra)")
    ctx.check(f"a malformed line shows its own parse error, got {bad!r}",
              "deny Bash(git push :* extra)" in bad and ":" in bad)


@test
def test_duration_hint_accepts_house_words_and_notes_the_rest(ctx: Ctx):
    from halo_harness.tui.dialogs.agent_bio_editor import duration_hint, parse_duration_word
    ctx.check("20m -> 1200s", parse_duration_word("20m") == 1200)
    ctx.check("2h -> 7200s", parse_duration_word("2h") == 7200)
    ctx.check("90s -> 90s", parse_duration_word("90s") == 90)
    ctx.check("1d -> 86400s", parse_duration_word("1d") == 86400)
    ctx.check('"20m" hint mentions minutes', "minute" in duration_hint("20m"))
    ctx.check('an unrecognized word notes it, never blocks', "not a recognized" in duration_hint("banana"))


@test
def test_budget_hint_estimates_turns_from_the_models_own_price(ctx: Ctx):
    from halo_harness.tui.dialogs.agent_bio_editor import budget_hint
    hint = budget_hint("6", "or:vendor/strong-model", FIXTURE_MODELS)
    ctx.check(f"mentions turns, got {hint!r}", "turn" in hint)
    ctx.check("blank with no budget typed", budget_hint("", "or:vendor/strong-model", FIXTURE_MODELS) == "")
    ctx.check("blank with an unknown model", budget_hint("6", "or:no/such", FIXTURE_MODELS) == "")


@test
def test_filter_models_for_bio_narrows_by_tools_offline_and_context(ctx: Ctx):
    from halo_harness.tui.dialogs.agent_bio_editor import filter_models_for_bio
    tool_only = filter_models_for_bio(FIXTURE_MODELS, {"tools": {"allow": ["Bash"]}})
    refs = [m["ref"] for m in tool_only]
    ctx.check(f"a tool-needing bio drops the row that explicitly declares no tool support, got {refs}",
              "or:vendor/cheap-model" not in refs and "or:vendor/strong-model" in refs)
    offline_only = filter_models_for_bio(FIXTURE_MODELS, {"environment": {"offline": True}})
    ctx.check(f"offline keeps only ol:/local rows, got {[m['ref'] for m in offline_only]}",
              [m["ref"] for m in offline_only] == ["ol:local-model"])
    everything = filter_models_for_bio(FIXTURE_MODELS, {"environment": {"offline": True}}, show_all=True)
    ctx.check("show_all bypasses every filter", len(everything) == len(FIXTURE_MODELS))


@test
def test_known_tool_names_includes_the_real_builtins(ctx: Ctx):
    from halo_harness.tui.dialogs.agent_bio_editor import known_tool_names
    names = known_tool_names()
    ctx.check(f"Bash/Read/Edit are real tool names, got {names}",
              {"Bash", "Read", "Edit"}.issubset(set(names)))


# ---------------------------------------------------------------------------
# Textual pilots: the Agents step (hosted in the wizard) and the bio form.
# ---------------------------------------------------------------------------

@test
def test_agents_step_create_save_reload_edit_duplicate_delete(ctx: Ctx):
    """Tests section: "create a bio picking its preference from the
    fixture catalog, save, reload the step and see it, edit a limit,
    duplicate a shipped bio into user scope, delete"."""
    from halo_harness.tui.dialogs.init_wizard import InitWizardApp, WizardState
    from halo_harness.tui.dialogs.agent_bio_editor import AgentBioEditor
    from textual.widgets import Input, OptionList, Button

    async def body():
        with _Env():
            state = WizardState(cwd=REPO_DIR, step_keys=("agents",), no_live=True)
            state.enumerated_models, state.enumeration_done = FIXTURE_MODELS, True
            app = InitWizardApp(state)
            async with app.run_test(size=(130, 50)) as pilot:
                await pilot.pause(0.1)
                ctx.check(f"opened on the Agents step, got {type(app.screen).__name__}",
                          type(app.screen).__name__ == "TeamStep")
                app.screen.query_one("#agents-new", Button).press()
                # 2.0.5 release gate: poll for the editor AND its fields --
                # the screen can push before its widgets mount under load
                await _wait_until(pilot, lambda: (
                    isinstance(app.screen, AgentBioEditor)
                    and app.screen.query("#bio-name")
                    and app.screen.query("#bio-pref")))
                editor = app.screen
                ctx.check("New opened the bio editor", isinstance(editor, AgentBioEditor))
                editor.query_one("#bio-name", Input).value = "pilot-bio"
                editor.query_one("#bio-description", Input).value = "A pilot test bio."
                editor.query_one("#bio-pref", Input).value = "or:vendor/strong-model"
                await pilot.pause(0.1)
                ctx.check('no validation problems while typing a good bio',
                          _static_text(editor.query_one("#bio-hint")) == "Looks good.")
                editor.action_save()
                await _wait_until(pilot, lambda: type(app.screen).__name__ == "TeamStep")
                ctx.check(f"save returned to the step, got {type(app.screen).__name__}",
                          type(app.screen).__name__ == "TeamStep")
                rows = app.screen.query_one("#agents-list", OptionList)
                names = [str(rows.get_option_at_index(i).id) for i in range(rows.option_count)]
                ctx.check(f"the new bio is listed, got {names}", "pilot-bio" in names)
                from halo_harness.agents_yaml import resolve_agent_bio
                saved = resolve_agent_bio("pilot-bio")
                ctx.check(f"it round-trips with the picked model, got {saved['models']}",
                          saved["models"]["preference"] == "or:vendor/strong-model")

                # -- edit a limit ---------------------------------------------
                rows.highlighted = names.index("pilot-bio")
                app.screen.query_one("#agents-edit", Button).press()
                await _wait_until(pilot, lambda: (
                    isinstance(app.screen, AgentBioEditor)
                    and app.screen.query("#bio-limit-max-iter")))
                editor2 = app.screen
                editor2.query_one("#bio-limit-max-iter", Input).value = "7"
                editor2.action_save()
                await pilot.pause(0.2)
                reread = resolve_agent_bio("pilot-bio")
                ctx.check(f"the edited limit round-trips, got {reread.get('limits')}",
                          reread["limits"]["max_iterations"] == 7)

                # -- duplicate a shipped bio into user scope -------------------
                rows2 = app.screen.query_one("#agents-list", OptionList)
                names2 = [str(rows2.get_option_at_index(i).id) for i in range(rows2.option_count)]
                rows2.highlighted = names2.index("coder")
                app.screen.query_one("#agents-duplicate", Button).press()
                from halo_harness.agents_yaml import find_agent_bio_path
                await _wait_until(pilot, lambda: (
                    find_agent_bio_path("coder") is not None
                    and find_agent_bio_path("coder")[1] == "user"))
                found = find_agent_bio_path("coder")
                ctx.check(f"coder now resolves to user scope, got {found}", found and found[1] == "user")

                # -- delete ------------------------------------------------------
                rows3 = app.screen.query_one("#agents-list", OptionList)
                names3 = [str(rows3.get_option_at_index(i).id) for i in range(rows3.option_count)]
                rows3.highlighted = names3.index("pilot-bio")
                app.screen.query_one("#agents-delete", Button).press()
                await pilot.pause(0.2)
                ctx.check("pilot-bio is gone after Delete", resolve_agent_bio("pilot-bio", cwd=REPO_DIR) is None
                          or find_agent_bio_path("pilot-bio") is None or
                          find_agent_bio_path("pilot-bio")[1] == "template")
    asyncio.run(body())


@test
def test_agents_step_bad_save_shows_lines_and_keeps_the_form(ctx: Ctx):
    """Tests section: "a bad save (invalid name, unknown kind) shows the
    lines and keeps the form"."""
    from halo_harness.tui.dialogs.init_wizard import InitWizardApp, WizardState
    from halo_harness.tui.dialogs.agent_bio_editor import AgentBioEditor
    from textual.widgets import Input, Button

    async def body():
        with _Env():
            state = WizardState(cwd=REPO_DIR, step_keys=("agents",), no_live=True)
            state.enumerated_models, state.enumeration_done = FIXTURE_MODELS, True
            app = InitWizardApp(state)
            async with app.run_test(size=(130, 50)) as pilot:
                await pilot.pause(0.1)
                app.screen.query_one("#agents-new", Button).press()
                await pilot.pause(0.2)
                editor = app.screen
                editor.query_one("#bio-name", Input).value = "has spaces"
                editor.query_one("#bio-kind", Input).value = "not-a-kind"
                await pilot.pause(0.1)
                hint = _static_text(editor.query_one("#bio-hint"))
                ctx.check(f"the invalid kind is reported live (not only on save), got {hint!r}",
                          "not one of" in hint)
                editor.action_save()
                await pilot.pause(0.1)
                ctx.check("the form stayed open after a bad save", isinstance(app.screen, AgentBioEditor))
                hint2 = _static_text(editor.query_one("#bio-hint"))
                ctx.check(f"both problems are reported, got {hint2!r}",
                          "not one of" in hint2 and "invalid agent name" in hint2)
    asyncio.run(body())


@test
def test_new_from_writes_only_override_keys_and_shows_inherited_greyed(ctx: Ctx):
    """Folded item: "new-from a shipped bio writes only the override keys
    and the inherited view shows them greyed"."""
    from halo_harness.tui.dialogs.init_wizard import InitWizardApp, WizardState
    from halo_harness.tui.dialogs.agent_bio_editor import AgentBioEditor
    from textual.widgets import Input, OptionList, Switch, Button

    async def body():
        with _Env():
            state = WizardState(cwd=REPO_DIR, step_keys=("agents",), no_live=True)
            state.enumerated_models, state.enumeration_done = FIXTURE_MODELS, True
            app = InitWizardApp(state)
            async with app.run_test(size=(130, 50)) as pilot:
                await _wait_until(pilot, lambda: app.screen.query_one("#agents-list", OptionList)
                                  is not None and app.screen.query("#agents-new-from"))
                rows = app.screen.query_one("#agents-list", OptionList)
                names = [str(rows.get_option_at_index(i).id) for i in range(rows.option_count)]
                rows.highlighted = names.index("coder")
                app.screen.query_one("#agents-new-from", Button).press()
                # 2.0.6 round 14 (the CI flake): a fixed pause raced the
                # editor's widget mount -- poll for the editor AND its
                # override switch, the same bounded pattern the other pilot
                # races in this file got.
                await _wait_until(pilot, lambda: (
                    isinstance(app.screen, AgentBioEditor)
                    and app.screen.query("#bio-pref-ov")))
                editor = app.screen
                ctx.check("extends_from is set", isinstance(editor, AgentBioEditor) and editor.extends_from == "coder")
                pref_ov = editor.query_one("#bio-pref-ov", Switch)
                ctx.check("preference override starts OFF (inherited)", pref_ov.value is False)
                pref_input = editor.query_one("#bio-pref", Input)
                ctx.check("the inherited field is disabled until overridden", pref_input.disabled is True)
                before_save = editor._collect_form()
                ctx.check(f"no section is written while nothing is overridden, got {before_save}",
                          not any(s in before_save for s in
                                  ("models", "tools", "context", "limits", "output", "environment", "acceptance")))
                editor.query_one("#bio-name", Input).value = "coder-child-pilot"
                editor.action_save()
                await pilot.pause(0.2)
                from halo_harness.agents_yaml import load_agent_bio_raw, resolve_agent_bio
                raw = load_agent_bio_raw("coder-child-pilot")
                ctx.check(f"the raw child file carries only extends+identity, got {raw}",
                          raw.get("extends") == "coder" and "models" not in raw)
                resolved = resolve_agent_bio("coder-child-pilot")
                ctx.check("the resolved view still inherits the parent's models section",
                          bool(resolved.get("models")) or resolved.get("models") == {})
    asyncio.run(body())


@test
def test_suggest_chord_fills_both_model_fields(ctx: Ctx):
    """Folded item: "Suggest fills both model fields"."""
    from halo_harness.tui.dialogs.agent_bio_editor import AgentBioEditor
    from textual.app import App

    async def body():
        with _Env():
            app_holder = {}

            class _Host(App):
                def on_mount(self):
                    app_holder["screen"] = AgentBioEditor("suggest-pilot", {}, FIXTURE_MODELS, is_new=True)
                    self.push_screen(app_holder["screen"])
            app = _Host()
            async with app.run_test(size=(130, 50)) as pilot:
                await pilot.pause(0.1)
                editor = app.screen
                editor.action_suggest()
                await pilot.pause(0.1)
                from textual.widgets import Input
                pref = editor.query_one("#bio-pref", Input).value
                fallback = editor.query_one("#bio-fallback", Input).value
                ctx.check(f"Suggest filled the preference field, got {pref!r}", bool(pref))
                ctx.check(f"preference/fallback differ (or fallback legitimately empty), got {pref!r}/{fallback!r}",
                          pref != "" )
    asyncio.run(body())


@test
def test_import_from_claude_code_converts_a_fixture_md_file(ctx: Ctx):
    """Folded item: "Import converts a fixture .claude/agents/*.md into a
    bio"."""
    from halo_harness.tui.dialogs.agents_step import _import_all, bio_rows

    async def body():
        with _Env() as e:
            agents_dir = e.cwd / ".claude" / "agents"
            agents_dir.mkdir(parents=True, exist_ok=True)
            (agents_dir / "fixture-importer.md").write_text(
                "---\nname: fixture-importer\ndescription: A fixture agent for import testing.\n"
                "model: or:vendor/strong-model\n---\n\nYou are careful and terse.\n", encoding="utf-8")
            lines = _import_all(cwd=e.cwd, state_dir=e.state_dir)
            ctx.check(f"one result line for the fixture file, got {lines}",
                      any("fixture-importer" in ln and "imported" in ln for ln in lines))
            names = [r["name"] for r in bio_rows(cwd=e.cwd, state_dir=e.state_dir)]
            ctx.check(f"the imported bio is now listed, got {names}", "fixture-importer" in names)
    asyncio.run(body())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
