"""halo_harness.tui.dialogs.orchestra -- the `/orchestra` panel (Halo 3.0.3.0).

Like `/tasks`: a full-height panel over the session listing the latest
Orchestra run of this folder's repo -- the workflow's steps, one row per
worker lane (state, pieces sent back, cost, holder, title) and the last run
log lines. It refreshes once a second when events.jsonl has new lines (the
same `state`/`merge`/`gate`/`report` lines the runner writes and publishes
as `orchestra_*` feed events). `find_run` is a plain zero-arg callable
returning the run folder (or None), so a test hands it a lambda. The
text itself is orchestra/view.py's, shared with the headless `/orchestra`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

from halo_harness.orchestra.view import panel_text, run_finder  # noqa: F401  (run_finder: tui/slash.py)


class OrchestraPanel(ModalScreen):
    BINDINGS = [Binding("escape", "close", "Close", show=False), Binding("r", "refresh", "Refresh", show=False)]
    DEFAULT_CSS = """
    OrchestraPanel { align: center middle; }
    OrchestraPanel > Vertical { width: 96%; height: 92%; border: round $primary; background: $surface;
        padding: 1 2; }
    OrchestraPanel #orchestra-body { height: 1fr; }
    """

    def __init__(self, find_run: Callable[[], Optional[Path]]) -> None:
        super().__init__()
        self._find_run = find_run
        self._seen = -1
        self._timer = None

    def compose(self):
        with Vertical():
            yield Static("Orchestra -- the latest run's lanes (r: refresh, Esc: close)", classes="dialog-title")
            yield Static("", id="orchestra-body")

    def on_mount(self) -> None:
        self.action_refresh()
        self._timer = self.set_interval(1.0, self._poll)

    def on_unmount(self) -> None:
        if self._timer is not None:
            self._timer.stop()

    def _event_count(self, run_dir) -> int:
        if run_dir is None:
            return 0
        from halo_harness.orchestra import events as run_events
        return len(run_events.read(run_dir))

    def _poll(self) -> None:
        run_dir = self._find_run()
        if self._event_count(run_dir) != self._seen:
            self.action_refresh()

    def action_refresh(self) -> None:
        run_dir = self._find_run()
        self._seen = self._event_count(run_dir)
        from rich.text import Text
        self.query_one("#orchestra-body", Static).update(Text(panel_text(run_dir)))  # plain text, no markup

    def action_close(self) -> None:
        self.dismiss(None)
