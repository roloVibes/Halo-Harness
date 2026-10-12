"""halo_harness.tui.dialogs.team_step -- the Team wizard step (Halo 2.1.0
round B1, reshaped in 3.0.2.0 after the owner's Kali review: "way too
bunched up and confusing", "no enable roles button", "the gui should be
launched instead").

Top to bottom: a plain-words header; a **Custom roles** switch (off = one
model for everything, the default); the lineup list (the first row is
always "One model for everything", then every reachable lineup with a
scope badge, the active one marked) beside a live preview of the
highlighted row (`team_preview.preview_lines`); two buttons, **Use this
lineup** and **Open Studio (Roles)**; and the usual Back/Skip/Next chrome.
The switch and the list are two views of one choice: switching on
highlights the first lineup (or the active one), switching off highlights
the first row, highlighting a lineup turns the switch on. A plain Next
applies whichever row is highlighted (`docs/WIZARD.md` rule 1) and always
writes `roles.enabled` explicitly.

Editing lives in Studio (the browser) now; the terminal editors stay
reachable for scripts and tests (Enter on a row, Ctrl+E, Ctrl+N, Ctrl+A)
but are no longer buttons. `init_wizard` is imported only inside method
bodies (circular-import split)."""

from __future__ import annotations

from typing import Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, OptionList, Static, Switch
from textual.widgets.option_list import Option

from halo_harness.tui.dialogs import team_preview as tp
from halo_harness.tui.dialogs.team_step_actions import TeamActionsMixin
from halo_harness.tui.dialogs.step_rail import STEP_RAIL_BINDINGS, StepRailMixin
from halo_harness.tui.dialogs.wizard_ux import focus_first

WIDE_COLUMNS = 100  # side by side at or above this width; stacked below it.
SWITCH_LABEL = " Custom roles -- each job gets its own agent and model (off: one model for everything)"


class TeamStep(StepRailMixin, TeamActionsMixin, Screen):
    BINDINGS = [Binding("escape", "ask_quit", "Quit setup", show=False, priority=True),
                *STEP_RAIL_BINDINGS,
                Binding("ctrl+n", "new_lineup", "New lineup", show=False, priority=True),
                Binding("ctrl+e", "customize", "Customize", show=False, priority=True),
                Binding("ctrl+a", "agents", "Agents", show=False, priority=True)]
    DEFAULT_CSS = """
    TeamStep { align: center middle; }
    TeamStep > Vertical { width: 94%; height: 92%; border: round $primary; padding: 1 2; background: $surface; }
    TeamStep #wiz-team-body { height: 1fr; margin-top: 1; }
    TeamStep .wizard-switch-row { height: 3; }
    TeamStep #wiz-team-panes { height: auto; margin-top: 1; }
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
        self._syncing = False

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
        roles_on = not self._lineups[0]["active"]
        with Vertical():
            yield Static(self.state.title(), classes="wizard-header")
            yield Static(self.rail_text(self.state.step_keys, self.state.index, _titles()),
                          classes="wizard-rail", id="wizard-rail")
            yield Static(tp.HEADER_TEXT, id="wiz-team-header-sentence", classes="dialog-title")
            with VerticalScroll(id="wiz-team-body"):
                with Horizontal(classes="wizard-switch-row"):
                    yield Switch(value=roles_on, id="wiz-roles-switch")
                    yield Static(SWITCH_LABEL, classes="wizard-switch-label")
                with Horizontal(id="wiz-team-panes"):
                    yield OptionList(*[Option(self._label(r), id=r["name"]) for r in self._lineups],
                                      id="wiz-team-lineups-list")
                    yield Static("", id="wiz-team-preview")
                with Horizontal(classes="wizard-extra-buttons"):
                    yield Button("Use this lineup", id="wiz-team-use", variant="primary")
                    yield Button("Open Studio (Roles)", id="wiz-team-studio")
                yield Static("Studio edits lineups and agents in your browser and keeps running after setup "
                              "(halo studio --stop). Next uses the highlighted row.", classes="bio-hint")
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

    # -- the switch and the list are one choice -------------------------------
    def on_switch_changed(self, event) -> None:
        if event.switch.id != "wiz-roles-switch" or self._syncing:
            return
        option_list = self.query_one("#wiz-team-lineups-list", OptionList)
        current = self._highlighted_lineup_name()
        if (event.value and current not in (None, tp.ONE_MODEL_ID)) or (not event.value and current == tp.ONE_MODEL_ID):
            return  # the list already agrees (the Changed message is deferred; never re-highlight)
        if event.value:
            active = next((i for i, r in enumerate(self._lineups) if r["active"] and r["name"] != tp.ONE_MODEL_ID), None)
            target = active if active is not None else (1 if len(self._lineups) > 1 else 0)
        else:
            target = 0
        self._syncing = True
        try:
            option_list.highlighted = target
        finally:
            self._syncing = False
        self._refresh_preview()

    def _sync_switch(self) -> None:
        name = self._highlighted_lineup_name()
        if name is None or self._syncing:
            return
        self._syncing = True
        try:
            self.query_one("#wiz-roles-switch", Switch).value = name != tp.ONE_MODEL_ID
        except Exception:
            pass
        finally:
            self._syncing = False

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
            self._sync_switch()
            self._refresh_preview()

    def on_option_list_option_selected(self, event) -> None:
        if event.option_list.id == "wiz-team-lineups-list":
            self.action_customize()

    def action_agents(self) -> None:
        self._open_agents()

    def action_open_studio(self) -> None:
        from halo_harness.studio.launch import launch_detached
        from halo_harness.providers.config import default_state_dir
        from pathlib import Path
        self._hint("Opening Studio in your browser...")

        def _work() -> str:
            return launch_detached("roles", cwd=Path(self.state.cwd), state_dir=Path(default_state_dir()))

        def _done(url: str) -> None:
            self._hint(f"Studio: {url}  (halo studio --stop ends it)" if url else "Studio did not start -- run `halo studio --mode roles` in a shell.")
        self.run_worker(lambda: self.app.call_from_thread(_done, _work()), thread=True, name="wiz-team-studio")

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
        elif bid == "wiz-team-studio":
            self.action_open_studio()

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
