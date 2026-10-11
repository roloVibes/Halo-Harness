"""halo_harness.tui.dialogs.team_step -- Halo 2.1.0 round B1: the Team
wizard step, rebuilt so a first-time user SEES agents and understands them.

Top to bottom: a plain-words header; the lineup list (the first row is
always "One model for everything", then every reachable lineup with a scope
badge, the active one marked); a live preview of the highlighted row (the
tree `role -> agent -> model` with price/context, the lineup's `about:`
text, warnings and one cost line -- `team_preview.preview_lines`); the
buttons Use this lineup / Customize... / New lineup / Agents...; and the
usual Back/Skip/Next chrome. The "Custom roles: off / on" switch is gone:
"One model for everything" IS the off state. A plain Next applies whichever
row is highlighted (`docs/WIZARD.md` rule 1: highlight is selection);
Enter on a row opens its editor (rule 2). `roles.enabled` is always
written explicitly here.

Layout: side by side from `WIDE_COLUMNS` up, stacked below; the body
scrolls, so every control is reachable at 80x24.

`init_wizard` is imported only inside method bodies (see the earlier
docstring of this module in git history for the circular-import split)."""

from __future__ import annotations

from typing import Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, OptionList, Static
from textual.widgets.option_list import Option

from halo_harness.tui.dialogs import team_preview as tp
from halo_harness.tui.dialogs.team_step_actions import TeamActionsMixin
from halo_harness.tui.dialogs.step_rail import STEP_RAIL_BINDINGS, StepRailMixin
from halo_harness.tui.dialogs.wizard_ux import focus_first

WIDE_COLUMNS = 100  # side by side at or above this width; stacked below it.


class TeamStep(StepRailMixin, TeamActionsMixin, Screen):
    BINDINGS = [Binding("escape", "ask_quit", "Quit setup", show=False, priority=True),
                *STEP_RAIL_BINDINGS,
                Binding("ctrl+n", "new_lineup", "New lineup", show=True, priority=True),
                Binding("ctrl+e", "customize", "Customize", show=True, priority=True)]
    DEFAULT_CSS = """
    TeamStep { align: center middle; }
    TeamStep > Vertical { width: 94%; height: 92%; border: round $primary; padding: 1 2; background: $surface; }
    TeamStep #wiz-team-body { height: 1fr; margin-top: 1; }
    TeamStep #wiz-team-panes { height: auto; }
    TeamStep #wiz-team-lineups-list { height: 10; width: 1fr; }
    TeamStep #wiz-team-preview { height: auto; min-height: 6; width: 1fr; padding: 0 1; }
    TeamStep .wizard-extra-buttons { height: 3; margin-top: 1; }
    TeamStep .wizard-extra-buttons Button { margin-right: 1; }
    TeamStep .wizard-footer { height: 3; align: right middle; margin-top: 1; }
    TeamStep .wizard-footer Button { margin-left: 1; }
    """

    def __init__(self, state) -> None:
        super().__init__()
        self.state = state
        self._lineups: "list[dict]" = []
        self._catalog: "Optional[dict]" = None

    # -- compose --------------------------------------------------------------
    def compose(self) -> ComposeResult:
        from halo_harness.teams_yaml import migrate_legacy_role_table
        from halo_harness.roles import configured_role_table
        try:  # a pre-existing legacy role table becomes a "migrated" lineup (no-op once it exists).
            migrated, notes = migrate_legacy_role_table(configured_role_table(), cwd=self.state.cwd)
            if migrated:
                self.state.written.append(f"legacy role table migrated to team template {migrated!r} "
                                           f"({len(notes)} file(s))")
        except Exception:
            pass
        self._lineups = self._rows()
        with Vertical():
            yield Static(self.state.title(), classes="wizard-header")
            yield Static(self.rail_text(self.state.step_keys, self.state.index, _titles()),
                          classes="wizard-rail", id="wizard-rail")
            yield Static(tp.HEADER_TEXT, id="wiz-team-header-sentence", classes="dialog-title")
            with VerticalScroll(id="wiz-team-body"):
                with Horizontal(id="wiz-team-panes"):
                    yield OptionList(*[Option(self._label(r), id=r["name"]) for r in self._lineups],
                                      id="wiz-team-lineups-list")
                    yield Static("", id="wiz-team-preview")
                with Horizontal(classes="wizard-extra-buttons"):
                    yield Button("Use this lineup", id="wiz-team-use", variant="primary")
                    yield Button("Customize...", id="wiz-team-customize")
                    yield Button("New lineup", id="wiz-team-lineup-new")
                    yield Button("Agents...", id="wiz-team-agents")
                yield Static("Enter edit · Ctrl+N new lineup · Ctrl+E customize · Next uses the highlighted row",
                              classes="bio-hint")
                yield Static("", id="wiz-team-lineup-hint")
            with Horizontal(classes="wizard-footer"):
                yield Button("Back", id="wiz-back", disabled=self.state.index == 0)
                yield Button("Skip", id="wiz-skip")
                last = self.state.index + 1 >= len(self.state.step_keys)
                yield Button("Finish" if last else "Next", id="wiz-next", variant="primary")

    def on_mount(self) -> None:
        option_list = self.query_one("#wiz-team-lineups-list", OptionList)
        option_list.highlighted = next((i for i, r in enumerate(self._lineups) if r["active"]), 0)
        self._apply_layout()
        self._refresh_preview()
        focus_first(self, ["#wiz-team-lineups-list"])

    def on_resize(self, event) -> None:
        self._apply_layout()

    def _apply_layout(self) -> None:
        wide = self.size.width >= WIDE_COLUMNS
        try:
            self.query_one("#wiz-team-panes").styles.layout = "horizontal" if wide else "vertical"
        except Exception:
            return

    # -- the list and its preview ----------------------------------------------
    def _highlighted_lineup_name(self) -> "Optional[str]":
        try:
            option_list = self.query_one("#wiz-team-lineups-list", OptionList)
        except Exception:
            return None
        if option_list.highlighted is None:
            return None
        opt = option_list.get_option_at_index(option_list.highlighted)
        return str(opt.id) if opt.id else None

    def _refresh_preview(self) -> None:
        name = self._highlighted_lineup_name()
        if name is None:
            return
        if self._catalog is None:
            self._catalog = tp.catalog_by_ref()
        width = max(30, (self.size.width * 94 // 100 - 8) // (2 if self.size.width >= WIDE_COLUMNS else 1))
        text = "\n".join(tp.preview_lines(name, cwd=self.state.cwd, width=width,
                                           default_model=self.state.final_model, models_by_ref=self._catalog))
        try:
            self.query_one("#wiz-team-preview", Static).update(text)
        except Exception:
            pass

    def _refresh_lineups(self) -> None:
        option_list = self.query_one("#wiz-team-lineups-list", OptionList)
        previous = self._highlighted_lineup_name()
        self._lineups = self._rows()
        option_list.clear_options()
        for r in self._lineups:
            option_list.add_option(Option(self._label(r), id=r["name"]))
        names = [r["name"] for r in self._lineups]
        option_list.highlighted = names.index(previous) if previous in names else 0
        self._refresh_preview()

    def on_option_list_option_highlighted(self, event) -> None:
        if event.option_list.id == "wiz-team-lineups-list":
            self._refresh_preview()

    def on_option_list_option_selected(self, event) -> None:
        if event.option_list.id == "wiz-team-lineups-list":
            self.action_customize()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "wiz-back":
            self.action_do_back()
        elif bid == "wiz-skip":
            from halo_harness.tui.dialogs.init_wizard import advance
            advance(self.app, self.state, skip=True)
        elif bid == "wiz-next":
            self.action_do_next()
        elif bid == "wiz-team-use":
            self.commit()
            self._refresh_lineups()
            self._hint("Applied.")
        elif bid == "wiz-team-customize":
            self.action_customize()
        elif bid == "wiz-team-lineup-new":
            self.action_new_lineup()
        elif bid == "wiz-team-agents":
            self._open_agents()

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

def _titles() -> dict:
    from halo_harness.tui.dialogs.init_wizard import STEP_TITLES
    return STEP_TITLES
