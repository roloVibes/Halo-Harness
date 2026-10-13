"""halo_harness.tui.worker_guard -- a thread worker that raises reports the
error and leaves the TUI running (review 3 item 73).

Textual's `run_worker` defaults to `exit_on_error=True`: an exception in any
worker becomes `WorkerFailed` and exits the whole app, orphaning whatever a
running Bash call had started. `BridgeApp.run_worker` routes every thread
worker that does not choose for itself through `guard`, so `/doctor`,
`/resume`, `/providers` and the rest show a notification instead.
"""

from __future__ import annotations

import inspect
import logging
from typing import Callable

_LOG = logging.getLogger("bridge")


def guard(app, work: Callable, label: str) -> Callable:
    """`work` wrapped so an exception becomes an error notification."""
    if not callable(work) or inspect.iscoroutinefunction(work):
        return work

    def _guarded():
        try:
            return work()
        except Exception as exc:  # noqa: BLE001 -- the whole point
            _LOG.exception("worker %s raised", label or "(unnamed)")
            report(app, label, exc)
            return None

    return _guarded


def report(app, label: str, exc: BaseException) -> None:
    text = f"{label or 'A background task'} failed: {type(exc).__name__}: {exc}"
    try:
        app.call_from_thread(app.notify, text, severity="error", timeout=8)
    except Exception:  # the app is already shutting down, or no loop yet
        pass
