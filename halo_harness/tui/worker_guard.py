"""halo_harness.tui.worker_guard -- a thread worker that raises reports the
error and leaves the TUI running (review 3 item 73).

Textual's `run_worker` defaults to `exit_on_error=True`: an exception in any
worker becomes `WorkerFailed` and exits the whole app, orphaning whatever a
running Bash call had started. `BridgeApp.run_worker` routes every thread
worker that does not choose for itself through `guard`, so `/doctor`,
`/resume`, `/providers` and the rest show a notification instead.
"""

from __future__ import annotations

import concurrent.futures
import inspect
import logging
from typing import Callable

_LOG = logging.getLogger("bridge")
# What Textual's `call_from_thread` raises when the app is gone under it (3.6.0.4 S3-2).
_GONE = ("App is not running", "Event loop is closed")


def _closing(app) -> bool:
    """Textual's own marks of an app on its way out: `exit()` was called, it is closing or closed, or its loop is gone."""
    return bool(getattr(app, "_exit", False) or getattr(app, "_closing", False) or getattr(app, "_closed", False)
                or getattr(app, "_loop", True) is None)


def call_into_closing_app(app, exc: BaseException) -> bool:
    """3.6.0.4 S3-2: a worker's call into an app that is closing (its call_from_thread cancelled, or the app or its
    loop already gone) is the end of the worker, not an error. The same error while the app runs is one."""
    gone = isinstance(exc, concurrent.futures.CancelledError) or (isinstance(exc, RuntimeError) and str(exc) in _GONE)
    return gone and _closing(app)


def guard(app, work: Callable, label: str) -> Callable:
    """`work` wrapped so an exception becomes an error notification."""
    if not callable(work) or inspect.iscoroutinefunction(work):
        return work

    def _guarded():
        try:
            return work()
        except Exception as exc:  # noqa: BLE001 -- the whole point
            if call_into_closing_app(app, exc):
                return None
            _LOG.exception("worker %s raised", label or "(unnamed)")
            report(app, label, exc)
            return None

    return _guarded


def guarded_worker(node, work: Callable, *, name: str = "", group: str = "default", exit_on_error=None,
                   thread: bool = True, **kw):
    """`node.run_worker(work, ...)` for a screen, widget or app, with a thread
    worker that does not choose for itself guarded the same way
    `BridgeApp.run_worker` guards the app's own: an exception becomes an error
    notification and the app keeps running. Screens and widgets inherit
    Textual's `exit_on_error=True` from `DOMNode.run_worker`, which never goes
    through the app's override, so every dialog worker calls this instead."""
    if exit_on_error is None:
        exit_on_error = not thread
        if thread:
            work = guard(_app_of(node), work, name or group)
    return node.run_worker(work, name=name, group=group, exit_on_error=exit_on_error, thread=thread, **kw)


def _app_of(node):
    try:
        app = node.app
    except Exception:  # no active app context (a node built outside a running app)
        app = None
    return app if app is not None else node


def report(app, label: str, exc: BaseException) -> None:
    text = f"{label or 'A background task'} failed: {type(exc).__name__}: {exc}"
    try:
        app.call_from_thread(app.notify, text, severity="error", timeout=8)
    except Exception:  # the app is already shutting down, or no loop yet
        pass
