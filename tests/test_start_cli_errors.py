"""tests.test_start_cli_errors -- Halo 3.2.2.0 R1: `halo start` never crashes
(start/errors.py, start/engine.py's third `except`, start_cli.cmd_start).

Every run uses HALO_START_FAKE=1 in this module's own home (the helpers of
tests/test_start_cli.py):
1. a step that raises TypeError: its frame `[failed]` with `TypeError: boom`
   and "the full error is in <log>", the log holds the traceback, exit 1, no
   traceback on the terminal; `--json` carries `reason` and `error_log`.
2. the command a step's screen shows raises: that step fails the same way.
3. a failure outside the walk (building the run): one stderr line naming the
   log, exit 1, nothing on stdout.
4. the wizard's hand-off: `_run_init_wizard_flow` returns the failed start's 1
   and adds nothing (no second traceback).
5. `error_line` and `write_error_log` themselves (append, the temp fallback).
Run: python -m tests.test_start_cli_errors
"""
from __future__ import annotations

import io
import json
import sys
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

ensure_scoped_state_dir_once()
test, TESTS = new_registry()

from tests.test_start_cli import _env, _home, _start  # noqa: E402  (after the scoped home)


@contextmanager
def _patched(module, name, value):
    saved = getattr(module, name)
    setattr(module, name, value)
    try:
        yield
    finally:
        setattr(module, name, saved)


def _boom(*_a, **_k):
    raise TypeError("boom")


def _check_failed(ctx: Ctx, rc, text, err, step: str):
    ctx.check(f"exit 1, got {rc} {err[-300:]!r}", rc == 1)
    ctx.check(f"the step failed with the one line, got {text[-600:]!r}", "[failed]" in text and "TypeError: boom" in text
              and f"halo start stopped at {step}: TypeError: boom" in text)
    logs = sorted((_home() / "start").glob("*/start-error.log"))
    ctx.check(f"the screen names the log, got {logs}", bool(logs) and f"the full error is in {logs[-1]}" in text)
    body = logs[-1].read_text(encoding="utf-8") if logs else ""
    ctx.check("the log holds the traceback", "Traceback" in body and "boom" in body and "halo start: TypeError: boom" in body)
    ctx.check(f"no traceback on the terminal, got {err!r}", "Traceback" not in err and "Traceback" not in text)


@test
def test_a_step_that_raises_fails_with_one_line_and_the_log(ctx: Ctx):
    from halo_harness.start import steps_setup
    with _patched(steps_setup, "repo", _boom):
        rc, text, err = _start(["--yes"])
    _check_failed(ctx, rc, text, err, "repo")
    ctx.check("step 1 stayed done", text.count("[done]") == 1)
    with _patched(steps_setup, "repo", _boom):
        rc_j, text_j, _ = _start(["--json"])
    data = json.loads(text_j) if text_j.strip().startswith("{") else {}
    ctx.check(f"--json: reason and error_log, got {data.get('reason')!r} {data.get('error_log')!r}", rc_j == 1
              and data.get("reason") == "TypeError: boom" and Path(data.get("error_log") or "no-log").is_file()
              and [s["state"] for s in data.get("steps", [])] == ["done", "failed"])


@test
def test_a_screen_command_that_raises_fails_its_step(ctx: Ctx):
    from halo_harness.start import steps_run
    with _patched(steps_run, "goal_command", _boom):
        rc, text, err = _start(["--yes"])
    _check_failed(ctx, rc, text, err, "goal")
    ctx.check("step 3's screen drawn and failed, step 4 never shown", "Step 3 of 7: The goal" in text
              and "Step 4 of 7" not in text and text.count("[done]") == 2)


@test
def test_a_failure_outside_the_walk_is_one_stderr_line(ctx: Ctx):
    from halo_harness.start import engine
    with _patched(engine.StartRun, "__init__", _boom):
        rc, text, err = _start(["--yes"])
    lines = [ln for ln in err.splitlines() if ln.strip()]
    ctx.check(f"exit 1 and one stderr line naming the log, got {rc} {err!r}", rc == 1 and len(lines) == 1
              and lines[0].startswith("halo start: TypeError: boom -- the full error is in ")
              and Path(lines[0].split("the full error is in ", 1)[1]).is_file())
    ctx.check(f"nothing on stdout, no traceback, got {text!r}", text == "" and "Traceback" not in err)
    with _patched(engine.StartRun, "__init__", _boom):
        rc_j, text_j, _ = _start(["--json"])
    data = json.loads(text_j) if text_j.strip().startswith("{") else {}
    ctx.check(f"--json: one object with the line and the log, got {text_j!r}", rc_j == 1 and data.get("ok") is False
              and data.get("reason") == "TypeError: boom" and data.get("error_log"))


@test
def test_the_wizard_hand_off_returns_the_failed_start(ctx: Ctx):
    from types import SimpleNamespace
    from rich.console import Console
    from halo_harness import init_cli
    from halo_harness.start import steps_setup
    from halo_harness.tui.dialogs import init_wizard
    app = SimpleNamespace(state=SimpleNamespace(team_warnings=[], pong_ok=True, run_start=True))
    out = io.StringIO()
    args = SimpleNamespace(step=None, team=None, no_live=True)
    old_in = sys.stdin
    sys.stdin = io.StringIO("\n\n")  # Enter at steps 1 and 2, as the user does after the wizard
    try:
        with _patched(init_wizard, "run_init_wizard", lambda **_k: app), _patched(steps_setup, "repo", _boom), \
                _env(HALO_START_FAKE="1"), redirect_stdout(out), redirect_stderr(out):
            rc = init_cli._run_init_wizard_flow(args, Console(file=out, width=120), Path.cwd())
    finally:
        sys.stdin = old_in
    text = out.getvalue()
    ctx.check(f"the wizard returns the start's exit 1, got {rc} {text[-300:]!r}", rc == 1)
    ctx.check("the start's screens ran and named the log", "Enter runs this step" in text
              and "halo start stopped at repo: TypeError: boom" in text and "the full error is in" in text)
    ctx.check("no traceback from the wizard flow", "Traceback" not in text)


@test
def test_error_line_and_the_log_file(ctx: Ctx):
    from halo_harness.start.errors import error_line, failed_summary, write_error_log
    ctx.check("type and first line", error_line(ValueError("bad\nmore")) == "ValueError: bad")
    ctx.check("an empty message is just the type", error_line(KeyError()) == "KeyError")
    try:
        raise RuntimeError("first")
    except RuntimeError as e:
        p1 = write_error_log(_home(), Path("x/20261025-run"), e, today="2026-01-02")
    try:
        raise RuntimeError("second")
    except RuntimeError as e:
        p2 = write_error_log(_home(), Path("x/20261025-run"), e, today="2026-01-02")
    body = p1.read_text(encoding="utf-8")
    ctx.check(f"named after the run under the day, got {p1}", p1 == p2 and p1 == _home() / "start" / "2026-01-02"
              / "20261025-run-error.log")
    ctx.check("appended, each with its timestamp line", body.count("halo start: RuntimeError:") == 2
              and "first" in body and "second" in body and body.count("Traceback") == 2)
    blocker = _home() / "r1-a-file"
    blocker.write_text("x", encoding="utf-8")
    import tempfile
    tmp = _home() / "r1-tmp"
    tmp.mkdir(exist_ok=True)
    with _patched(tempfile, "tempdir", str(tmp)):  # the fallback lands in this home, never the real temp folder
        p3 = write_error_log(blocker, None, TypeError("t"))
    ctx.check(f"a state dir that cannot hold the folder: the temp file, got {p3}", p3 == tmp / "halo-start-error.log"
              and p3.is_file())
    s = failed_summary(_home(), None, TypeError("boom"))
    ctx.check(f"failed_summary, got {s}", s["ok"] is False and s["reason"] == "TypeError: boom"
              and Path(s["error_log"]).name == "start-error.log")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
