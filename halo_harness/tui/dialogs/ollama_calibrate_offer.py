"""halo_harness.tui.dialogs.ollama_calibrate_offer -- Halo 3.2.3.0 R2: the
Ollama tab's Save with the found rows (`save_found_rows`, shared by
`init_tabs.InitTabsApp` and `init_wizard.ProvidersStep`) and the one-line
offer that follows when it added hosts: "Calibrate the found models now
(loads each model once; about N minutes: Enter runs it, Esc skips)". Enter
runs `providers.ollama_discover_measure.measure_hosts` in a worker with one
progress line per model; Esc skips it, or once it runs closes the view
(the measuring carries on in the background while setup stays open and
records each model as it ends) -- Esc never undoes anything.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.content import Content
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from halo_harness.tui.dialogs.ollama_found import FoundPanel
from halo_harness.tui.worker_guard import guarded_worker


def save_found_rows(node, provider: str, values: dict, *, prefix: str, team_cfg=None,
                    no_live: bool = False) -> "tuple[bool, str]":
    """The tab's Save: for the Ollama tab, the ticked new rows first
    (`add_hosts`), then the typed fields as before (`save_tab_credentials`;
    skipped when only ticks were saved, so a blank form never adds the
    local daemon on top); after hosts were added, the calibrate offer."""
    from halo_harness.init_providers import save_tab_credentials
    if provider != "ollama":
        return save_tab_credentials(provider, values, team_cfg=team_cfg)
    lines, by_host = [], {}
    try:
        lines, _names, by_host = node.query_one(f"#{prefix}-found", FoundPanel).save_ticked()
    except Exception:
        lines, by_host = [], {}
    if lines and not any((v or "").strip() for v in values.values()):
        ok, message = True, "; ".join(lines)
    else:
        ok, message = save_tab_credentials(provider, values, team_cfg=team_cfg)
    if ok and by_host and not no_live:
        node.app.push_screen(CalibrateOffer(by_host))
    return ok, message


class CalibrateOffer(ModalScreen):
    """"Calibrate the found models now (loads each model once; about N
    minutes: Enter runs it, Esc skips)" -- then one line per model."""
    BINDINGS = [Binding("escape", "skip", "Skip", priority=True, show=False)]
    DEFAULT_CSS = """
    CalibrateOffer { align: center middle; }
    CalibrateOffer > Vertical { width: 80%; height: auto; max-height: 80%; border: round $primary;
                                padding: 1 2; background: $surface; }
    CalibrateOffer #calibrate-lines { margin-top: 1; color: $text-muted; }
    CalibrateOffer Horizontal { height: auto; margin-top: 1; }
    CalibrateOffer Button { margin-right: 1; }
    """

    def __init__(self, models_by_host: dict) -> None:
        super().__init__()
        from halo_harness.providers.ollama_discover_measure import estimate_minutes
        self.models_by_host = dict(models_by_host)
        count = sum(len(v) for v in self.models_by_host.values())
        self.offer = (f"Calibrate the found models now (loads each model once; about "
                      f"{estimate_minutes(count)} minute{'' if estimate_minutes(count) == 1 else 's'}: "
                      f"Enter runs it, Esc skips)")
        self.lines: "list[str]" = []
        self.running = False
        self.finished = False

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(Content(self.offer), id="calibrate-offer")
            yield Static("", id="calibrate-lines")
            with Horizontal():
                yield Button("Calibrate now", id="calibrate-run", variant="primary")
                yield Button("Skip", id="calibrate-skip")

    def on_mount(self) -> None:
        try:
            self.query_one("#calibrate-run", Button).focus()
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == "calibrate-run" and not self.running:
            self.action_run()
        elif event.button.id == "calibrate-skip":
            self.action_skip()

    def action_run(self) -> None:
        self.running = True
        try:
            self.query_one("#calibrate-run", Button).disabled = True
            self.query_one("#calibrate-skip", Button).label = "Close"
        except Exception:
            pass
        self.append_line("measuring, one line per model…")
        guarded_worker(self.app, self._run_worker, thread=True, name="ollama-calibrate-found")

    def _run_worker(self) -> None:
        from halo_harness.providers.ollama_discover_measure import measure_hosts
        measure_hosts(list(self.models_by_host), models_by_host=self.models_by_host,
                      on_line=lambda line: self._from_thread(self.append_line, line))
        self._from_thread(self._done)

    def _from_thread(self, fn, *args) -> None:
        try:
            self.app.call_from_thread(fn, *args)
        except Exception:
            pass

    def _done(self) -> None:
        self.finished = True
        self.append_line("done: every measurement is recorded in ~/.halo/ollama-fit.json")

    def append_line(self, text: str) -> None:
        self.lines.append(text)
        try:
            self.query_one("#calibrate-lines", Static).update(Content("\n".join(self.lines)))
        except Exception:
            pass

    def action_skip(self) -> None:
        self.dismiss(self.running)
