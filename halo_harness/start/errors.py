"""halo_harness.start.errors -- how `halo start` reports an error its steps did
not expect (Halo 3.2.2.0 R1): one line on the screen, the traceback in a file.

* `error_line(exc)` is `<Type>: <message>` (the message's first line).
* `write_error_log(state_dir, run_dir, exc)` appends a timestamp line and the
  traceback to `<state>/start/<yyyy-mm-dd>/<run dir name or 'start'>-error.log`
  and returns the path (the temp folder's `halo-start-error.log` when the
  state dir cannot be written; OSError when neither can).
* `failed_summary(state_dir, run_dir, exc)` is the summary of a start that
  failed outside its walk: `{ok: False, stopped_at: None, reason, error_log}`.

The engine (a step that raised), `halo start` (building the run, printing
the summary), Studio's start job and the TUI panel all go through these.
"""

from __future__ import annotations

import datetime as _dt
import tempfile
import traceback
from pathlib import Path
from typing import Optional


def error_line(exc: BaseException) -> str:
    """`<Type>: <message>` (just the type when the message is empty)."""
    text = str(exc).strip().splitlines()
    return f"{type(exc).__name__}: {text[0]}" if text else type(exc).__name__


def write_error_log(state_dir, run_dir, exc: BaseException, *, today: Optional[str] = None) -> Path:
    from halo_harness.start.sample_repo import start_root
    if state_dir is None:
        from halo_harness.config.paths import bridge_home
        state_dir = bridge_home()
    name = (Path(run_dir).name if run_dir else "") or "start"
    text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    stamp = _dt.datetime.now().isoformat(timespec="seconds")
    body = f"--- {stamp} halo start: {error_line(exc)}\n{text}\n"
    day = start_root(state_dir) / (today or _dt.date.today().isoformat())
    tmp = Path(tempfile.gettempdir())
    targets = ((day, day / f"{name}-error.log"), (tmp, tmp / "halo-start-error.log"))
    for folder, path in targets:
        try:
            folder.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8", newline="\n") as fh:
                fh.write(body)
            return path
        except OSError:
            continue
    raise OSError(f"could not write {targets[0][1]}")


def log_path_or_empty(state_dir, run_dir, exc: BaseException, *, today: Optional[str] = None) -> str:
    """`write_error_log`'s path as text, '' when no file could be written."""
    try:
        return str(write_error_log(state_dir, run_dir, exc, today=today))
    except Exception:
        return ""


def failed_summary(state_dir, run_dir, exc: BaseException) -> dict:
    return {"ok": False, "stopped_at": None, "reason": error_line(exc),
            "error_log": log_path_or_empty(state_dir, run_dir, exc)}
