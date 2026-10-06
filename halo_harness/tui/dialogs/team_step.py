"""halo_harness.tui.dialogs.team_step -- Halo 2.0.5 round 2c, rule 11
(`plans/ROADMAP.md` "Added 2026-10-06 ~10:15"): ONE "Team" wizard step
replacing the round-2/2b "Agents" step and "Roles and lineup" step, with
the "Custom roles: off / on" switch at the top. Off shows one sentence and
nothing else -- delegation still works through the `standard` lineup (see
`docs/AGENTS.md`'s own "the `default` model reference and the `standard`
lineup" section). On shows two panes: left "Lineups" (the active one
checked; Enter edits, Ctrl+N new, Ctrl+D duplicate into user scope under
the same name -- `_AgentsListMixin._duplicate_highlighted`'s own "shadow
the shipped one" semantic, applied to lineups), right "Agents" (the bios;
Enter edits, Ctrl+N new, Ctrl+D duplicate, Del delete -- `agents_step.
_AgentsListMixin`, reused verbatim). Side by side at 120x40, stacked
behind a pane-switch at 80x24 (`WIDE_COLUMNS`).

A NEW module (hard constraint: `init_wizard.py` grows by registration
lines only). Same "duplicate `StepScreen`'s own small Back/Skip/Next/Esc-
quit chrome, reach `advance`/`go_back`/`finish` through a lazy, function-
body-only import" split `agents_step.AgentsStep`'s own module docstring
explains -- this module imports `init_wizard` only inside method bodies,
so `init_wizard.py`'s own top-level `from halo_harness.tui.dialogs.
team_step import TeamStep` (to register it) can never be circular.
`StepRailMixin`/`wizard_ux` carry no such constraint (neither depends on
`init_wizard.py`), so this class inherits the rail directly."""

from __future__ import annotations

from typing import Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, OptionList, Static, Switch
from textual.widgets.option_list import Option

from halo_harness.tui.dialogs.agents_step import AGENTS_LIST_BINDINGS, _AgentsListMixin
from halo_harness.tui.dialogs.step_rail import STEP_RAIL_BINDINGS, StepRailMixin
from halo_harness.tui.dialogs.wizard_ux import focus_first, footer_hint, one_sentence, toast

WIDE_COLUMNS = 100  # >= this: Lineups/Agents side by side; below: stacked behind a pane switch.


def _lineup_row_label(r: dict) -> str:
    mark = "✓ " if r["active"] else ""  # the active lineup's own check mark (rule 11), not the highlight.
    desc = f": {r['description']}" if r["description"] else ""
    return f"{mark}{r['name']} [{r['scope']}]{desc}"


def _default_model_label(state) -> str:
    if state.final_model:
        return state.final_model
    from halo_harness.theme import get_config_value
    current = get_config_value("model", default=None)
    return current if isinstance(current, str) and current.strip() else "the session model"


class TeamStep(StepRailMixin, _AgentsListMixin, Screen):
    # Round 2c frees Ctrl+N/Ctrl+D from the old (round 7) "Next"/"Back"
    # meaning -- Ctrl+Left/Ctrl+Right (`STEP_RAIL_BINDINGS`, rule 4) cover
    # step navigation "from anywhere" now, so Ctrl+N/Ctrl+D/Del are free
    # for rule 9's uniform "new/duplicate/delete" everywhere, including
    # here (`AGENTS_LIST_BINDINGS`). Both are plain tuples spliced in
    # here, NOT `BINDINGS` lists on either mixin -- see `agents_step.
    # AGENTS_LIST_BINDINGS`'s own comment for why a mixin's `BINDINGS`
    # alone is silently ignored by Textual's binding merge; the action
    # METHODS (`action_agents_*`/`action_rail_*`) still resolve normally
    # through the mixins via ordinary attribute lookup, which this class
    # overrides three of (`action_agents_new/_duplicate/_delete`) to
    # dispatch by focused pane -- see `_focused_pane` below.
    BINDINGS = [Binding("escape", "ask_quit", "Quit setup", show=False, priority=True),
                *STEP_RAIL_BINDINGS, *AGENTS_LIST_BINDINGS]
    DEFAULT_CSS = """
    TeamStep { align: center middle; }
    TeamStep > Vertical { width: 94%; height: 92%; border: round $primary; padding: 1 2; background: $surface; }
    TeamStep #wiz-team-off-sentence { margin-top: 1; color: $text-muted; }
    TeamStep .wizard-switch-row { height: 3; margin-top: 1; }
    TeamStep #wiz-team-pane-switch { height: 3; margin-top: 1; }
    TeamStep #wiz-team-panes { height: 1fr; margin-top: 1; }
    TeamStep #wiz-team-lineups-pane { width: 1fr; height: 100%; padding: 0 1; border-right: solid $primary-darken-1; }
    TeamStep #wiz-team-agents-pane { width: 1fr; height: 100%; padding: 0 1; }
    TeamStep #wiz-team-lineups-list { height: 1fr; margin-top: 1; }
    TeamStep #agents-list { height: 1fr; margin-top: 1; }
    TeamStep .wizard-extra-buttons { height: 3; margin-top: 1; }
    TeamStep .wizard-extra-buttons Button { margin-right: 1; }
    TeamStep .wizard-footer { height: 3; align: right middle; margin-top: 1; }
    TeamStep .wizard-footer Button { margin-left: 1; }
    """

    def __init__(self, state) -> None:
        super().__init__()
        self.state = state
        self._lineups: "list[dict]" = []
        self._narrow_pane = "lineups"

    # -- _AgentsListMixin's own small hooks ---------------------------------
    def _cwd(self):
        return self.state.cwd

    def _models_for_picker(self) -> list:
        if self.state.enumeration_done:
            return self.state.enumerated_models
        list_models = getattr(getattr(self.app, "controller", None), "list_models", None)
        try:
            rows = list_models() if callable(list_models) else []
        except Exception:
            rows = []
        if rows:
            return rows
        from halo_harness.tui.dialogs.agents_step import _cache_only_model_rows
        rows = _cache_only_model_rows()
        self.state.enumerated_models, self.state.enumeration_done = rows, True
        return rows

    # -- compose -------------------------------------------------------------
    def compose(self) -> ComposeResult:
        from halo_harness.roles import roles_mode_enabled
        enabled = roles_mode_enabled()
        with Vertical():
            yield Static(self.state.title(), classes="wizard-header")
            yield Static(self.rail_text(self.state.step_keys, self.state.index, _TEAM_STEP_TITLES()),
                          classes="wizard-rail", id="wizard-rail")
            yield Static(self._header_sentence(enabled), id="wiz-team-header-sentence", classes="dialog-title")
            yield Horizontal(Switch(value=enabled, id="wiz-team-switch"),
                              Static(" Custom roles: off / on", classes="wizard-switch-label"),
                              classes="wizard-switch-row")
            yield Static(self._off_sentence_text(), id="wiz-team-off-sentence")
            with Vertical(id="wiz-team-on-body"):
                with Horizontal(id="wiz-team-pane-switch"):
                    yield Button("Lineups", id="wiz-team-switch-lineups-btn", variant="primary")
                    yield Button("Agents", id="wiz-team-switch-agents-btn")
                with Horizontal(id="wiz-team-panes"):
                    with Vertical(id="wiz-team-lineups-pane"):
                        yield Static("Lineups", classes="bio-section-title")
                        for w in self._lineups_pane_widgets():
                            yield w
                    with Vertical(id="wiz-team-agents-pane"):
                        yield Static("Agents", classes="bio-section-title")
                        for w in self._agents_list_widgets():
                            yield w
            with Horizontal(classes="wizard-footer"):
                yield Button("Back", id="wiz-back", disabled=self.state.index == 0)
                yield Button("Skip", id="wiz-skip")
                last = self.state.index + 1 >= len(self.state.step_keys)
                yield Button("Finish" if last else "Next", id="wiz-next", variant="primary")

    def _header_sentence(self, enabled: bool) -> str:
        if not enabled:
            return one_sentence("Team", "custom roles off (every role uses the default model)")
        from halo_harness.theme import get_config_value
        active = get_config_value("team", default=None)
        current = f"custom roles on, lineup {active!r}" if active else "custom roles on, no lineup applied yet"
        return one_sentence("Team", current)

    def _off_sentence_text(self) -> str:
        return (f"Halo uses {_default_model_label(self.state)} for everything, including the sub-agents it "
                f"spawns on its own, and still asks you questions when it needs to.")

    # -- the Lineups pane -----------------------------------------------------
    def _lineups_pane_widgets(self) -> list:
        from halo_harness.roles import configured_role_table
        from halo_harness.teams_yaml import migrate_legacy_role_table
        try:
            # Round 2b/2.0.4 round 4 (deliverable 7): a real, pre-existing
            # legacy role table migrates into a generated "migrated" team
            # template -- a no-op once "migrated" already exists. Round 2c
            # moved the TRIGGER from an explicit legacy-template apply
            # (gone, with the pane it lived on) to simply opening this
            # pane; `state.written` is still how the Summary step learns
            # about it (fixed here -- the migration itself ran, correctly,
            # but its own result was silently discarded before this fix).
            migrated_name, migration_notes = migrate_legacy_role_table(configured_role_table(), cwd=self.state.cwd)
            if migrated_name:
                self.state.written.append(f"legacy role table migrated to team template {migrated_name!r} "
                                           f"({len(migration_notes)} file(s))")
        except Exception:
            pass
        self._lineups = self._team_rows()
        option_list = OptionList(*[Option(_lineup_row_label(r), id=r["name"]) for r in self._lineups],
                                  id="wiz-team-lineups-list")
        return [option_list,
                Horizontal(Button("New", id="wiz-team-lineup-new", variant="primary"),
                           Button("Duplicate", id="wiz-team-lineup-duplicate"),
                           classes="wizard-extra-buttons"),
                Static(footer_hint(new=True, edit=True, delete=False), classes="bio-hint"),
                Static("", id="wiz-team-lineup-hint")]

    def _team_rows(self) -> "list[dict]":
        from halo_harness.tui.dialogs.lineup_editor import team_rows
        return team_rows(cwd=self.state.cwd)

    def _highlighted_lineup_name(self) -> "Optional[str]":
        try:
            option_list = self.query_one("#wiz-team-lineups-list", OptionList)
        except Exception:
            return None
        if option_list.highlighted is None:
            return None
        opt = option_list.get_option_at_index(option_list.highlighted)
        return str(opt.id) if opt.id else None

    def _refresh_lineups(self) -> None:
        try:
            option_list = self.query_one("#wiz-team-lineups-list", OptionList)
        except Exception:
            return
        previous = self._highlighted_lineup_name()
        self._lineups = self._team_rows()
        option_list.clear_options()
        for r in self._lineups:
            option_list.add_option(Option(_lineup_row_label(r), id=r["name"]))
        names = [r["name"] for r in self._lineups]
        if names:
            option_list.highlighted = names.index(previous) if previous in names else 0
        try:
            self.query_one("#wiz-team-header-sentence", Static).update(
                self._header_sentence(bool(self.query_one("#wiz-team-switch", Switch).value)))
        except Exception:
            pass

    def _open_lineup_editor(self, *, is_new: bool) -> None:
        name = f"lineup-{__import__('uuid').uuid4().hex[:6]}" if is_new else (self._highlighted_lineup_name()
                                                                               or "custom")
        self.run_worker(lambda: self._lineup_editor_worker(name, is_new), thread=True, name="wiz-team-lineup-editor")

    def _lineup_editor_worker(self, name: str, is_new: bool) -> None:
        from halo_harness.teams_yaml import load_team_template_raw
        template = {} if is_new else (load_team_template_raw(name, cwd=self.state.cwd) or {})
        self.app.call_from_thread(self._open_lineup_editor_screen, name, template, is_new)

    def _open_lineup_editor_screen(self, name: str, template: dict, is_new: bool) -> None:
        from halo_harness.tui.dialogs.lineup_editor import LineupEditor

        def _after(saved) -> None:
            self._refresh_lineups()
            if saved:
                try:
                    toast(self.query_one("#wiz-team-lineup-hint", Static), f"Saved lineup {saved!r}.")
                except Exception:
                    pass
        self.app.push_screen(LineupEditor(name, template, self._models_for_picker(), cwd=self.state.cwd,
                                           is_new=is_new), _after)

    def _duplicate_highlighted_lineup(self) -> None:
        """Ctrl+D on the Lineups pane: the SAME "copy a shipped one into
        user scope under the same name, so it shadows the read-only
        original" semantic `_AgentsListMixin._duplicate_highlighted`
        already uses for a bio -- never a clone under a NEW name."""
        name = self._highlighted_lineup_name()
        hint = self.query_one("#wiz-team-lineup-hint", Static)
        if name is None:
            toast(hint, "Highlight a lineup first.")
            return
        from halo_harness.teams_yaml import load_team_template_raw, save_team_template
        raw = load_team_template_raw(name, cwd=self.state.cwd) or {}
        ok, problems = save_team_template(name, raw, cwd=self.state.cwd)
        toast(hint, f"Duplicated {name!r} into user scope." if ok else "; ".join(problems))
        self._refresh_lineups()

    # -- mount / layout --------------------------------------------------------
    def on_mount(self) -> None:
        self._sync_visibility()
        self._apply_layout()
        enabled = bool(self.query_one("#wiz-team-switch", Switch).value)
        if enabled:
            focus_first(self, ["#wiz-team-lineups-list"])
        else:
            focus_first(self, ["#wiz-team-switch"])

    def on_resize(self, event) -> None:
        self._apply_layout()

    def _sync_visibility(self) -> None:
        try:
            on_body = self.query_one("#wiz-team-on-body")
            off_sentence = self.query_one("#wiz-team-off-sentence")
            switch = self.query_one("#wiz-team-switch", Switch)
        except Exception:
            return
        on_body.styles.display = "block" if switch.value else "none"
        off_sentence.styles.display = "none" if switch.value else "block"

    def _apply_layout(self) -> None:
        """Rule 11: side by side at 120x40 (`WIDE_COLUMNS`), stacked
        behind a pane switch at 80x24 -- both panes stay permanently
        mounted inside one `Horizontal` (`#wiz-team-panes`); only
        `display` toggles, so nothing is ever rebuilt by a resize."""
        try:
            switch_bar = self.query_one("#wiz-team-pane-switch")
            lineups_pane = self.query_one("#wiz-team-lineups-pane")
            agents_pane = self.query_one("#wiz-team-agents-pane")
        except Exception:
            return
        wide = self.size.width >= WIDE_COLUMNS
        switch_bar.styles.display = "none" if wide else "block"
        if wide:
            lineups_pane.styles.display = "block"
            agents_pane.styles.display = "block"
        else:
            self._show_narrow_pane(self._narrow_pane)

    def _show_narrow_pane(self, which: str) -> None:
        self._narrow_pane = which
        try:
            lineups_pane = self.query_one("#wiz-team-lineups-pane")
            agents_pane = self.query_one("#wiz-team-agents-pane")
            lineups_btn = self.query_one("#wiz-team-switch-lineups-btn", Button)
            agents_btn = self.query_one("#wiz-team-switch-agents-btn", Button)
        except Exception:
            return
        lineups_pane.styles.display = "block" if which == "lineups" else "none"
        agents_pane.styles.display = "block" if which == "agents" else "none"
        lineups_btn.variant = "primary" if which == "lineups" else "default"
        agents_btn.variant = "primary" if which == "agents" else "default"

    # -- events ------------------------------------------------------------
    def on_switch_changed(self, event) -> None:
        if event.switch.id != "wiz-team-switch":
            return
        self._sync_visibility()
        try:
            self.query_one("#wiz-team-header-sentence", Static).update(self._header_sentence(event.switch.value))
        except Exception:
            pass

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Rule 2/11: "Enter edits" on a highlighted lineup. `_AgentsList
        Mixin`'s own version of this same handler (checking "agents-list"
        instead) fires too -- Textual dispatches every `on_<event>` found
        across the whole MRO, not just the most-derived one."""
        if event.option_list.id == "wiz-team-lineups-list":
            self._open_lineup_editor(is_new=False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        # See `init_wizard.ProvidersStep.on_button_pressed`'s own comment
        # -- never re-handle an id `_AgentsListMixin`'s own override (also
        # fired by Textual on every press, same MRO dispatch) already
        # claims ("agents-*").
        bid = event.button.id or ""
        if bid == "wiz-back":
            self.action_do_back()
        elif bid == "wiz-skip":
            from halo_harness.tui.dialogs.init_wizard import advance
            advance(self.app, self.state, skip=True)
        elif bid == "wiz-next":
            self.action_do_next()
        elif bid == "wiz-team-lineup-new":
            self._open_lineup_editor(is_new=True)
        elif bid == "wiz-team-lineup-duplicate":
            self._duplicate_highlighted_lineup()
        elif bid == "wiz-team-switch-lineups-btn":
            self._show_narrow_pane("lineups")
        elif bid == "wiz-team-switch-agents-btn":
            self._show_narrow_pane("agents")

    # -- Ctrl+N/Ctrl+D/Del dispatch: which pane is focused ------------------
    def _focused_pane(self) -> str:
        node = self.focused
        while node is not None and node is not self:
            node_id = getattr(node, "id", None)
            if node_id == "wiz-team-agents-pane":
                return "agents"
            if node_id == "wiz-team-lineups-pane":
                return "lineups"
            node = node.parent
        return "lineups"

    def action_agents_new(self) -> None:
        if self._focused_pane() == "agents":
            self._open_editor_for_new()
        else:
            self._open_lineup_editor(is_new=True)

    def action_agents_duplicate(self) -> None:
        if self._focused_pane() == "agents":
            self._duplicate_highlighted()
        else:
            self._duplicate_highlighted_lineup()

    def action_agents_delete(self) -> None:
        if self._focused_pane() == "agents":
            self._delete_highlighted()
        # Lineups pane: no Del chord (rule 11 names only New/Duplicate for
        # it -- deleting a whole team template stays a deliberate, named
        # action elsewhere, never a bare chord here).

    # -- the small bit of StepScreen's own chrome this step needs -- lazy
    # imports only (module docstring: never a top-level `from init_wizard
    # import ...` here).
    def action_do_next(self) -> None:
        from halo_harness.tui.dialogs.init_wizard import advance
        self.commit()
        advance(self.app, self.state)

    def action_do_back(self) -> None:
        from halo_harness.tui.dialogs.init_wizard import go_back
        go_back(self.app, self.state)

    def action_ask_quit(self) -> None:
        from halo_harness.tui.dialogs.init_wizard import _QuitConfirm, finish

        def _after(confirmed) -> None:
            if confirmed:
                finish(self.app, self.state)
        self.app.push_screen(_QuitConfirm(), _after)

    # -- commit --------------------------------------------------------------
    def commit(self) -> None:
        from halo_harness.roles import set_roles_enabled
        enabled = bool(self.query_one("#wiz-team-switch", Switch).value)
        set_roles_enabled(enabled)
        if not enabled:
            return
        name = self._highlighted_lineup_name()
        if name:
            self._commit_lineup(name)

    def _commit_lineup(self, name: str) -> None:
        from halo_harness.teams_yaml import apply_team_template, resolve_role_table, resolve_team_template
        ok, problems, notes = apply_team_template(name, cwd=self.state.cwd)
        if not ok:
            self.state.written.append(f"could not apply lineup {name!r}: {'; '.join(problems)}")
            return
        self.state.written.append(f"lineup {name!r} applied (roles.*, team: {name!r})"
                                   + (f" -- {'; '.join(notes)}" if notes else ""))
        session = getattr(getattr(self.app, "controller", None), "session", None)
        if session is None:
            return
        template = resolve_team_template(name, cwd=self.state.cwd)
        if not template:
            return
        role_table, _notes = resolve_role_table(template, cwd=self.state.cwd)
        runtime = getattr(session, "agent_runtime", None)
        live_role_table = getattr(runtime, "role_table", None)
        if isinstance(live_role_table, dict):
            live_role_table.update(role_table)
        elif hasattr(session, "roles") and isinstance(session.roles, dict):
            session.roles.update(role_table)


def _TEAM_STEP_TITLES() -> dict:
    from halo_harness.tui.dialogs.init_wizard import STEP_TITLES
    return STEP_TITLES
