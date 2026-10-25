"""halo_harness.tui.dialogs.start_panel -- `/start`, the guided first run in a
panel over the session (Halo 3.1.1.0 R1).

The panel runs the same guided start as `halo start --yes` (halo_harness/
start/engine.py) on a worker thread: the seven steps one under another
with their state, and the newest step's screen (its one sentence of why,
the command it runs and its lines) below them. It runs straight through
(no Enter between steps; the lead's plan is approved as it comes); for
the step-by-step screens and Studio's plan canvas, `halo start` in a
terminal. Esc stops a running start (the Orchestra run is asked to stop)
and closes the panel once it has ended. `run_factory(emit)` builds the
StartRun, so a test hands it one with fake adapters and a scratch home.
"""

from __future__ import annotations

from typing import Callable, Optional

from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

from halo_harness.start import steps as S

ICON = {"ready": "..", "running": ">>", "done": "ok", "failed": "!!", "stopped": "--"}


def panel_text(frames: "dict[str, dict]", summary: Optional[dict] = None, tail: int = 14) -> str:
    """The panel body for the frames seen so far."""
    lines = []
    for n, (key, title, _why) in enumerate(S.STEPS, 1):
        state = (frames.get(key) or {}).get("state", "pending")
        lines.append(f"[{ICON.get(state, '  ')}] {n}. {title:<26} {state}")
    current = max(frames.values(), key=lambda f: f["step"], default=None)
    if current is not None:
        lines += ["", f"Step {current['step']} of {current['total']}: {current['title']}", f"  {current['why']}"]
        if current.get("command"):
            lines.append(f"  $ {current['command']}")
        body = list(current.get("lines") or [])
        if len(body) > tail:
            lines.append(f"  ... ({len(body) - tail} line(s) above)")
            body = body[-tail:]
        lines += [f"  {line}" for line in body]
    if summary is not None:
        if summary.get("reason") == "no_provider":
            lines += ["", str(summary.get("message") or "")]
        elif summary.get("ok"):
            lines += ["", f"Done: lineup {summary.get('lineup')}, run {summary.get('run')} in {summary.get('repo')}.",
                      "Esc closes; halo explain <thing> says what any word means."]
        else:
            lines += ["", f"Stopped at {summary.get('stopped_at') or 'the start'}: {summary.get('reason')}"]
            if summary.get("error_log"):
                lines.append(f"the full error is in {summary['error_log']}")
    return "\n".join(lines)


def default_run_factory(emit: Callable[[dict], None]):
    from halo_harness.start.engine import Options, StartRun
    return StartRun(Options(yes=True, studio=False), emit=emit)


class StartPanel(ModalScreen):
    BINDINGS = [Binding("escape", "close", "Stop / close", show=False), Binding("q", "close", "Stop / close", show=False)]
    DEFAULT_CSS = """
    StartPanel { align: center middle; }
    StartPanel > Vertical { width: 96%; height: 92%; border: round $primary; background: $surface; padding: 1 2; }
    StartPanel #start-body { height: 1fr; }
    """

    def __init__(self, run_factory: Optional[Callable] = None) -> None:
        super().__init__()
        self._factory = run_factory or default_run_factory
        self.frames: "dict[str, dict]" = {}
        self.summary: Optional[dict] = None
        self.start_run = None

    def compose(self):
        with Vertical():
            yield Static("The guided first run (Esc: stop, then close)", classes="dialog-title")
            yield Static("Starting...", id="start-body")

    def on_mount(self) -> None:
        from halo_harness.tui.worker_guard import guarded_worker
        try:
            self.start_run = self._factory(self._from_thread)
        except Exception as e:  # 3.2.2.0 R1: the start could not be built: its one line, never a crash screen
            from halo_harness.start.errors import failed_summary
            self._finished(failed_summary(None, None, e))
            return
        guarded_worker(self, self._work, thread=True, name="start-panel")

    def _work(self) -> None:
        try:
            summary = self.start_run.run()
        except Exception as e:  # 3.2.2.0 R1: the engine fails a raising step itself; this is anything left
            from halo_harness.start.errors import failed_summary
            summary = failed_summary(self.start_run.state_dir, self.start_run.run_dir, e)
        try:
            self.app.call_from_thread(self._finished, summary)
        except Exception:
            pass

    def _from_thread(self, frame: dict) -> None:
        try:
            self.app.call_from_thread(self._frame, frame)
        except Exception:
            pass

    def _frame(self, frame: dict) -> None:
        self.frames[frame["key"]] = frame
        self._draw()

    def _finished(self, summary: dict) -> None:
        self.summary = summary
        self._draw()

    def _draw(self) -> None:
        from rich.text import Text
        try:
            self.query_one("#start-body", Static).update(Text(panel_text(self.frames, self.summary)))
        except Exception:
            pass

    def action_close(self) -> None:
        if self.summary is None and self.start_run is not None:
            self.start_run.cancel()
            self.query_one("#start-body", Static).update("Stopping the start at its next check...")
            return
        self.dismiss(self.summary)
