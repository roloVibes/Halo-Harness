"""halo_harness.tui.steward_notice -- Halo 3.3.4.0 R4: the Ollama steward's
notes reach a live TUI.

Every POLL_S a worker thread reads what the steward's job (ollama_steward/
job.py: Studio's, the hub's or `halo ollama steward --watch`) appended to
this state dir's `<state>/ollama/steward.jsonl` since the TUI started (a
byte offset: the file's end at launch, so an old note is never shown again),
and, on a fleet member, the hub's newest note (`<state>/ollama/hub-note.json`,
fleet/ollama_share.py). Each new note or change:

- its first line in the status bar for NOTICE_S (`StatusBar.set_notice`),
  the newest one when several land at once;
- one system line in the transcript (`Transcript.add_note`, the line `/update`'s
  "update available" note uses).

A member's line reads "steward on <hub>: <first line>". `/ollama` is R5's.
"""

from __future__ import annotations

import json
from typing import Optional

POLL_S = 10.0
NOTICE_S = 30.0
STAGES = ("note", "change")


class NoticeWatch:
    """The new note lines of one state dir since `start()`."""

    def __init__(self, state_dir) -> None:
        self.state_dir = state_dir
        self.offset: Optional[int] = None
        self.hub_id: Optional[str] = None

    def _path(self):
        from halo_harness.ollama_steward.steward import journal_path
        return journal_path(self.state_dir)

    def start(self) -> "NoticeWatch":
        from halo_harness.ollama_steward.notes import hub_note
        try:
            self.offset = self._path().stat().st_size
        except OSError:
            self.offset = 0
        self.hub_id = (hub_note(self.state_dir) or {}).get("id")
        return self

    def _new_rows(self) -> list:
        path = self._path()
        try:
            size = path.stat().st_size
        except OSError:
            return []
        if self.offset is None or size < self.offset:
            self.offset = 0
        try:
            with open(path, "rb") as f:
                f.seek(self.offset)
                data = f.read(4 * 2 ** 20)
        except OSError:
            return []
        end = data.rfind(b"\n")
        if end < 0:
            return []
        self.offset += end + 1
        out = []
        for raw in data[:end].decode("utf-8", "replace").splitlines():
            try:
                row = json.loads(raw)
            except ValueError:
                continue
            if isinstance(row, dict) and row.get("kind") == "note" and row.get("stage") in STAGES:
                out.append(row)
        return out

    def new_lines(self) -> "list[str]":
        from halo_harness.ollama_steward.notes import first_line, hub_note, member_line
        lines = [first_line(r) for r in self._new_rows()]
        hub = hub_note(self.state_dir)
        if hub and hub.get("id") != self.hub_id:
            self.hub_id = hub.get("id")
            lines.append(member_line(hub))
        return [x for x in lines if x]


def show(app, lines: "list[str]") -> None:
    """On the UI thread: the newest line in the status bar for NOTICE_S."""
    if lines:
        try:
            app.status_bar.set_notice(lines[-1], NOTICE_S)
        except Exception:
            pass


def poll_once(app, watch: NoticeWatch) -> "list[str]":
    """Worker thread: read, then hand the lines to the UI thread (the status bar, one transcript line each)."""
    lines = watch.new_lines()
    if lines:
        app.call_from_thread(show, app, lines)
        for line in lines:
            app.call_from_thread(app.transcript.add_note, line, kind="note")
    return lines


def start_steward_poll(app) -> Optional[NoticeWatch]:
    """Called from the app's mount; nothing when the controller has no state dir."""
    state_dir = getattr(getattr(app, "controller", None), "state_dir", None)
    if state_dir is None:
        return None
    watch = NoticeWatch(state_dir).start()

    def safe() -> None:
        try:
            poll_once(app, watch)
        except Exception:
            pass

    def tick() -> None:
        app.run_worker(safe, thread=True, name="steward-notes", group="steward-notes", exit_on_error=False)
    app.set_interval(POLL_S, tick)
    return watch
