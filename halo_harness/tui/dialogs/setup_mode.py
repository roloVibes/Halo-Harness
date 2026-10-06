"""halo_harness.tui.dialogs.setup_mode -- Halo 2.0.5 round 2c, deliverable
5: rule 5 of `docs/WIZARD.md` -- the wizard's own FIRST screen, before
Providers: "Quick setup" (keys -> default model -> done, which activates
the `standard` lineup with roles off -- see `docs/AGENTS.md`'s own "the
`default` model reference and the `standard` lineup" section for why
"roles off" and "every role on the `standard` lineup" are the same
observable state) or "Full setup" (every other step). Quick is the
default (highlighted first, rule 1 -- "no confirm button": Next alone
picks it).

A NEW module -- `init_wizard.py` only imports and pushes it from
`InitWizardApp.on_mount` (never from a truncated `/setup`/`--step` entry,
which already starts mid-flow for a specific, narrow purpose and has no
use for this gate at all; see `WizardState.offer_quick_full`)."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, OptionList, Static
from textual.widgets.option_list import Option

from halo_harness.tui.dialogs.wizard_ux import focus_first, mark_checked

QUICK_STEP_KEYS = ("providers", "default_model", "summary")


class SetupModeStep(Screen):
    BINDINGS = [Binding("escape", "ask_quit", "Quit setup", show=False, priority=True)]
    DEFAULT_CSS = """
    SetupModeStep { align: center middle; }
    SetupModeStep > Vertical { width: 70%; height: auto; max-height: 80%; border: round $primary;
                                padding: 1 2; background: $surface; }
    SetupModeStep OptionList { height: 4; margin-top: 1; }
    SetupModeStep .wizard-footer { height: 3; align: right middle; margin-top: 1; }
    SetupModeStep .wizard-footer Button { margin-left: 1; }
    """

    def __init__(self, state) -> None:
        super().__init__()
        self.state = state

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("halo init", classes="wizard-header")
            yield Static("Quick setup: keys, a default model, done -- every role (including the sub-agents "
                          "halo spawns on its own) uses that model. Full setup walks every step (Permissions, "
                          "Theme, Team, Organizations, ...).", classes="dialog-title")
            yield OptionList(Option("Quick setup", id="quick"), Option("Full setup", id="full"),
                              id="wiz-setup-mode-list")
            with Horizontal(classes="wizard-footer"):
                yield Button("Next", id="wiz-next", variant="primary")

    def on_mount(self) -> None:
        option_list = self.query_one("#wiz-setup-mode-list", OptionList)
        option_list.highlighted = 0
        mark_checked(option_list, "quick")
        focus_first(self, ["#wiz-setup-mode-list"])

    def on_option_list_option_highlighted(self, event) -> None:
        if event.option_list.id == "wiz-setup-mode-list" and event.option_id:
            mark_checked(event.option_list, event.option_id)

    def on_option_list_option_selected(self, event) -> None:
        if event.option_list.id == "wiz-setup-mode-list":
            self._choose(str(event.option_id))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "wiz-next":
            self._choose(self._highlighted())

    def _highlighted(self) -> str:
        option_list = self.query_one("#wiz-setup-mode-list", OptionList)
        if option_list.highlighted is None:
            return "quick"
        opt = option_list.get_option_at_index(option_list.highlighted)
        return str(opt.id) if opt.id else "quick"

    def _choose(self, which: str) -> None:
        from halo_harness.tui.dialogs.init_wizard import _build_step
        self.state.quick_setup = (which == "quick")
        if which == "quick":
            self.state.step_keys = QUICK_STEP_KEYS
        self.state.index = 0
        first = _build_step(self.state, self.state.step_keys[0])
        self.state.pushed += 1
        self.app.pop_screen()  # this chooser -- never counted in state.pushed
        self.app.push_screen(first)

    def action_ask_quit(self) -> None:
        from halo_harness.tui.dialogs.init_wizard import _QuitConfirm

        def _after(confirmed) -> None:
            if confirmed:
                self.app.exit()
        self.app.push_screen(_QuitConfirm(), _after)
