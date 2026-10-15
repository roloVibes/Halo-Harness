"""halo_harness.tui.dialogs.fleet_table -- `/fleet` (Halo 3.0.5.0 "Fleet"
round R2, plan item D9): the same table as `halo fleet` in a dialog. Every
harness, session and agent this machine sees (Studio's fleet view when it
runs, else this machine's hub, else this harness alone; fleet/table.py),
refreshed every REFRESH_S seconds off the UI thread.

    Up/Down  select a row      s  steer that agent (type the note, Enter)
    k        stop it (press k twice: the first press asks)
    p        pause or resume it      r  refresh now      Esc / q  close
"""

from __future__ import annotations

import time

from rich.text import Text
from textual._context import NoActiveAppError
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

from halo_harness.tui.worker_guard import guarded_worker

REFRESH_S = 2.0
CONFIRM_S = 4.0


class FleetTable(ModalScreen):
    BINDINGS = [
        Binding("escape,q", "cancel", "Close", show=False),
        Binding("s", "steer", "Steer", show=False),
        Binding("k", "stop", "Stop", show=False),
        Binding("p", "pause", "Pause/resume", show=False),
        Binding("r", "refresh", "Refresh", show=False),
    ]
    DEFAULT_CSS = """
    FleetTable { align: center middle; }
    FleetTable > Vertical { width: 96%; height: 90%; border: round $primary; background: $surface; padding: 0 2; }
    FleetTable OptionList { height: 1fr; border: none; }
    FleetTable Input { display: none; }
    FleetTable Input.-open { display: block; }
    """

    def __init__(self, view: dict, source: str) -> None:
        super().__init__()
        self.view, self.source = view, source
        self.table: list = []
        self._confirm = (None, 0.0)

    def compose(self):
        with Vertical():
            yield Static("Fleet", classes="dialog-title")
            yield Static("", id="fleet-head")
            yield OptionList(id="fleet-rows")
            yield Input(placeholder="steer: the note for that agent, Enter sends, Esc cancels", id="fleet-steer")
            yield Static("", id="fleet-note")
            yield Static("Up/Down select  s steer  k stop (twice)  p pause/resume  r refresh  Esc close",
                         classes="dialog-subtitle")

    def on_mount(self) -> None:
        self._apply(self.view, self.source)
        self.set_interval(REFRESH_S, self.action_refresh)

    # ---- data ------------------------------------------------------------------
    def _apply(self, view: dict, source: str) -> None:
        from halo_harness.fleet.table import render, rows
        self.view, self.source, self.table = view, source, rows(view)
        where = {"studio": "Studio's fleet view", "hub": "this machine's hub", "local": "this harness only"}
        lines = render(self.table).split("\n")
        self.query_one("#fleet-head", Static).update(Text(f"{where.get(source, source)}\n{lines[0]}"))
        ol = self.query_one("#fleet-rows", OptionList)
        keep = ol.highlighted
        ol.clear_options()
        ol.add_options([Option(Text(line)) for line in lines[1:]])
        if self.table:
            ol.highlighted = min(keep or 0, len(self.table) - 1)

    def _deliver(self, fn, *args) -> None:
        try:
            self.app.call_from_thread(fn, *args)
        except (NoActiveAppError, RuntimeError):
            return

    def _refresh_worker(self) -> None:
        from halo_harness.fleet.table import snapshot
        try:
            view, source = snapshot()
        except Exception:
            return
        self._deliver(self._apply, view, source)

    def action_refresh(self) -> None:
        guarded_worker(self.app, self._refresh_worker, thread=True, name="fleet-refresh", group="fleet-refresh")

    # ---- actions -------------------------------------------------------------------
    def _row(self):
        i = self.query_one("#fleet-rows", OptionList).highlighted
        return self.table[i] if self.table and i is not None and 0 <= i < len(self.table) else None

    def _note(self, text: str) -> None:
        self.query_one("#fleet-note", Static).update(Text(text))

    def _send(self, row: dict, cmd: str, **fields) -> None:
        from halo_harness.fleet.table import send

        def work() -> None:
            ok, msg = send(row, cmd, self.source, **fields)
            self._deliver(self._note, msg)
            self._refresh_worker()
        self._note(f"{cmd} {row.get('agent')} ...")
        guarded_worker(self.app, work, thread=True, name="fleet-send", group="fleet-send")

    def action_steer(self) -> None:
        if self._row() is None:
            return
        box = self.query_one("#fleet-steer", Input)
        box.add_class("-open")
        box.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        box = self.query_one("#fleet-steer", Input)
        text, row = event.value.strip(), self._row()
        box.value = ""
        box.remove_class("-open")
        self.query_one("#fleet-rows", OptionList).focus()
        if text and row is not None:
            self._send(row, "steer", text=text)

    def action_stop(self) -> None:
        row = self._row()
        if row is None:
            return
        key = (row.get("harness"), row.get("session_id"), row.get("agent_id"))
        if self._confirm[0] == key and time.monotonic() - self._confirm[1] < CONFIRM_S:
            self._confirm = (None, 0.0)
            self._send(row, "stop", reason="stopped from /fleet")
            return
        self._confirm = (key, time.monotonic())
        self._note(f"press k again to stop {row.get('agent')} on {row.get('harness_name')}")

    def action_pause(self) -> None:
        row = self._row()
        if row is not None:
            self._send(row, "resume" if row.get("state") == "paused" else "pause")

    def action_cancel(self) -> None:
        box = self.query_one("#fleet-steer", Input)
        if box.has_class("-open"):
            box.remove_class("-open")
            self.query_one("#fleet-rows", OptionList).focus()
            return
        self.dismiss(None)
