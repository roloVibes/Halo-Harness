"""halo_harness.tui.slash_capture -- a slash line sent to a terminal session over its control socket (3.6.0.2
P8-P12, "one prompt": the terminal's own command table in both boxes).

The TUI sets `controller.slash_hook` at mount; `ControllerHandle.run_slash` calls it on the socket's thread, and
`run` here hands the line to the UI thread:

* P8  the UI thread must TAKE the line within `TAKE_S`; a line it has not taken by then is marked abandoned under
      a lock and runs nothing, then or later (`BUSY`, `ran: false`). A taken line runs the terminal's own
      `handle_slash`, never `Controller.run_slash`'s headless table, so `/model <ref>` switches the model.
* P9  while the line's CAPTURE is open, every note (`Transcript.add_note`) and toast (`BridgeApp.notify`) it makes
      is recorded, in order, each with its own line breaks; the capture is a context variable set where the UI
      thread takes the line, it records each Worker the handler starts (`BridgeApp.run_worker`) and carries itself
      into a `call_from_thread` made from a thread whose `active_worker` is one of them (Textual copies no context
      into a thread worker). It closes when the handler and those workers have ended, or `CAPTURE_S` after the
      take. A note or toast made by anything else meanwhile is not in it. The terminal draws them as for a typed
      line.
* P10 a line still running `CAPTURE_S` after the take answers with the output so far and `STILL`, `ran: true`.
      `TAKE_S` + `CAPTURE_S` stays under Studio's 5 s.
* P11 a command that opens a screen or dialog (`needs_screen`) or works on the terminal's own box (`BOX_COMMANDS`)
      runs nothing and answers its line with `ran: false`; a screen pushed while the capture is open is not pushed
      and gives the same answer; `/exit` and `/quit` answer first (`then`), then end the terminal's Halo.
* P12 the line is drawn in the terminal as one row `❯ /<line>` before its output.
"""
from __future__ import annotations

import asyncio
import contextvars
import threading
import time
from typing import Optional

TAKE_S = 1.0
CAPTURE_S = 3.5
BUSY = "The terminal is busy: nothing was run. Press Enter to try again."
STILL = "Still running in the terminal: the rest of its output will show there."
SCREEN_LINE = "/{name} opens a window in the terminal: type it there."
BOX_LINE = "/{name} works on the terminal's own box: type it there."
BOX_COMMANDS = ("paste", "images", "screenshot")
EXIT_COMMANDS = ("exit", "quit")
# every command whose handler pushes a screen or opens a card or window in the terminal (tui/slash.py's push sites;
# `test_every_handler_that_pushes_a_screen_is_caught` holds this table to them)
SCREEN_ALWAYS = ("resume", "rewind", "undo", "redo", "update", "mcp", "orchestra", "explain", "keys", "permissions",
                 "tasks", "editor")  # undo / redo: the rewind confirmation card
SCREEN_BARE = ("model", "effort")  # bare: the picker / the selector card; with an argument they act at once

CAPTURE: "contextvars.ContextVar[Optional[Capture]]" = contextvars.ContextVar("halo_slash_capture", default=None)


def needs_screen(name: str, args: str = "") -> bool:
    """True when `/<name> <args>` opens a screen, a dialog or a card in the terminal (nothing to run from Studio)."""
    name, words = (name or "").lstrip("/").strip().lower(), (args or "").split()
    if name in SCREEN_ALWAYS:
        return True
    if name in SCREEN_BARE:
        return not words
    if name == "local":  # bare (or refresh) opens the merged-view dialog; other text is a one-shot question
        return not words or words[0].lower() in ("refresh", "--refresh")
    if name == "ollama":  # `/ollama hosts ...` opens the per-host dialog; the rest prints
        return bool(words) and words[0].lower() == "hosts"
    return False


class Capture:
    """One socket slash line's capture (P9): its lines, the workers its handler started, whether it may run."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.lock = threading.Lock()
        self.lines: list = []
        self.workers: list = []
        self.open = True
        self.ran = True
        self.taken = threading.Event()
        self.taken_at = 0.0
        self.abandoned = False
        self.handler_done = threading.Event()
        self.then = None

    def add(self, text) -> None:
        with self.lock:
            if self.open:
                self.lines.append(str(text))

    def add_worker(self, worker) -> None:
        with self.lock:
            if self.open:
                self.workers.append(worker)

    def owns(self, worker) -> bool:
        with self.lock:
            return self.open and any(w is worker for w in self.workers)

    def finished(self) -> bool:
        with self.lock:
            workers = list(self.workers)
        return self.handler_done.is_set() and all(w.is_finished for w in workers)

    def close(self) -> list:
        with self.lock:
            self.open = False
            return list(self.lines)


def _open_captures(app) -> list:
    return [c for c in list(getattr(app, "_slash_captures", ())) if c.open]


def current(app) -> Optional[Capture]:
    """The open capture this code runs under: the context's, or the one owning this thread's worker."""
    cap = CAPTURE.get()
    if cap is not None:
        return cap if cap.open else None
    try:
        from textual.worker import active_worker
        worker = active_worker.get()
    except (LookupError, ImportError):
        return None
    for cap in _open_captures(app):
        if cap.owns(worker):
            return cap
    return None


def record_worker(app, worker) -> None:
    cap = current(app)
    if cap is not None:
        cap.add_worker(worker)


def note(app, text) -> None:
    """A note or a toast (P9): into the open capture, when there is one."""
    cap = current(app)
    if cap is not None:
        cap.add(text)


def call_from_thread(app, call, callback, *args, **kwargs):
    """`BridgeApp.call_from_thread`: a worker of a capture's line carries the capture into its callback."""
    cap = current(app)
    if cap is None:
        return call(callback, *args, **kwargs)
    token = CAPTURE.set(cap)  # asyncio copies this thread's context into the callback's task
    try:
        return call(callback, *args, **kwargs)
    finally:
        CAPTURE.reset(token)


def screen_blocked(app) -> bool:
    """`BridgeApp.push_screen` while a capture is open (P11): not pushed; the line says to type it there."""
    cap = current(app)
    if cap is None:
        return False
    line = SCREEN_LINE.format(name=cap.name)
    if cap.ran:
        cap.ran = False
        cap.add(line)
        empty = contextvars.Context()  # the note is the capture's already: mount it outside the capture
        empty.run(asyncio.ensure_future, app.transcript.add_note(line, kind="command"))
    return True


def done_future():
    fut = asyncio.get_running_loop().create_future()
    fut.set_result(None)
    return fut


async def _take(app, cap: Capture, name: str, args: str) -> None:
    with cap.lock:
        if cap.abandoned:  # P8: not taken in time: nothing runs, now or later
            return
        cap.taken_at = time.monotonic()
        cap.taken.set()
    token = CAPTURE.set(cap)
    try:
        app._slash_captures = _open_captures(app) + [cap]
        await app.transcript.add_user(f"/{name} {args}".strip())  # P12: the row, before its output
        app.transcript.scroll_end(animate=False)
        low = name.lower()
        if low in BOX_COMMANDS or needs_screen(low, args):
            cap.ran = False
            line = (BOX_LINE if low in BOX_COMMANDS else SCREEN_LINE).format(name=name)
            await app.transcript.add_note(line, kind="command")
        elif low in EXIT_COMMANDS:
            cap.then = lambda: app.call_from_thread(app._begin_quit)  # P11: after the answer went out
        else:
            from halo_harness.tui.slash import handle_slash
            await handle_slash(app, name, args)
    finally:
        CAPTURE.reset(token)
        cap.handler_done.set()


def run(app, name: str, args: str = "", *, take_s: float = TAKE_S, capture_s: float = CAPTURE_S) -> dict:
    """On the control socket's thread: `{output, ran}` (and `then`, run after the answer is sent, for `/exit`)."""
    name, args = (name or "").lstrip("/").strip(), (args or "").strip()
    cap = Capture(name)
    loop = getattr(app, "_loop", None)
    if loop is None:
        return {"output": BUSY, "ran": False}
    asyncio.run_coroutine_threadsafe(_take(app, cap, name, args), loop)
    if not cap.taken.wait(take_s):
        with cap.lock:
            if not cap.taken.is_set():
                cap.abandoned = True
                return {"output": BUSY, "ran": False}
    deadline = cap.taken_at + capture_s
    while not cap.finished() and time.monotonic() < deadline:
        time.sleep(0.02)
    still = not cap.finished()
    lines = cap.close()
    app._slash_captures = _open_captures(app)
    if still:
        lines.append(STILL)
    out = {"output": "\n".join(lines), "ran": cap.ran}
    if cap.then is not None:
        out["then"] = cap.then
    return out
