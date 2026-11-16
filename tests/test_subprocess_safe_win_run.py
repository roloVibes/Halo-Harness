"""tests.test_subprocess_safe_win_run -- 3.6.0.1: on Windows, subprocess_safe's run / call / check_call /
check_output start the child through this module's Popen (so it joins Halo's Job). Each must answer every argument
case exactly as CPython's own function does: an explicit check_output(input=None) is an empty input (never the
terminal's own stdin), and the argument clashes CPython refuses with ValueError (or TypeError) are refused too.

The Windows functions (`subprocess_safe._WIN`) are plain Python over Popen, so they are compared with CPython's on
every system; on Windows the public functions are compared as well (they route there).

Run: python -m tests.test_subprocess_safe_win_run
"""
from __future__ import annotations

import contextlib
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()

# the child: how many characters it read from its stdin, on its stdout
_READ = [sys.executable, "-I", "-S", "-c", "import sys; sys.stdout.write(str(len(sys.stdin.read())))"]
_BOUND_S = 30  # a child that inherits a stdin that never ends would wait this long (slow Windows runners)


@contextlib.contextmanager
def _stdin_never_ends():
    """fd 0 is a pipe whose writer stays open: a child that inherits it waits for ever (as under a terminal)."""
    r, w = os.pipe()
    saved = os.dup(0)
    os.dup2(r, 0)
    try:
        yield
    finally:
        os.dup2(saved, 0)
        for fd in (saved, r, w):
            os.close(fd)


def _answer(fn, *args, **kw):
    """What a call gives: ('ok', value) or ('raise', exception type)."""
    try:
        out = fn(*args, **kw)
    except Exception as exc:  # noqa: BLE001 -- the type is the answer
        return "raise", type(exc).__name__
    if isinstance(out, subprocess.CompletedProcess):
        return "ok", (out.returncode, out.stdout.strip() if out.stdout is not None else None)
    return "ok", out.strip() if isinstance(out, (str, bytes)) else out


def _sides():
    from halo_harness import subprocess_safe
    sides = [("_WIN", subprocess_safe._WIN)]
    if os.name == "nt":
        sides.append(("public", {n: getattr(subprocess_safe, n) for n in ("run", "call", "check_call",
                                                                           "check_output")}))
    return sides


_CASES = [
    ("check_output(input=None, text=True)", "check_output", dict(input=None, text=True, timeout=_BOUND_S)),
    ("check_output(input=None) bytes", "check_output", dict(input=None, timeout=_BOUND_S)),
    ("check_output(input=None, encoding=)", "check_output", dict(input=None, encoding="utf-8", timeout=_BOUND_S)),
    ("check_output(input='abc', text=True)", "check_output", dict(input="abc", text=True, timeout=_BOUND_S)),
    ("check_output(stdout=PIPE)", "check_output", dict(stdout=subprocess.PIPE, input=b"", timeout=_BOUND_S)),
    ("check_output(check=False)", "check_output", dict(check=False, input=b"", timeout=_BOUND_S)),
    ("run(stdin=DEVNULL, input=)", "run", dict(stdin=subprocess.DEVNULL, input=b"x", capture_output=True,
                                               timeout=_BOUND_S)),
    ("run(capture_output, stdout=)", "run", dict(capture_output=True, stdout=subprocess.DEVNULL,
                                                 stdin=subprocess.DEVNULL, timeout=_BOUND_S)),
    ("run(capture_output, stderr=)", "run", dict(capture_output=True, stderr=subprocess.STDOUT,
                                                 stdin=subprocess.DEVNULL, timeout=_BOUND_S)),
    ("run(input=b'ab', capture_output)", "run", dict(input=b"ab", capture_output=True, timeout=_BOUND_S)),
    ("call(input=)", "call", dict(input=b"", timeout=_BOUND_S)),
    ("check_call(capture_output=)", "check_call", dict(capture_output=True, stdin=subprocess.DEVNULL,
                                                       timeout=_BOUND_S)),
]


@test
def test_every_argument_case_answers_as_cpython_does(ctx: Ctx):
    with _stdin_never_ends():
        for label, name, kw in _CASES:
            want = _answer(getattr(subprocess, name), _READ, **dict(kw))
            for side, fns in _sides():
                got = _answer(fns[name], _READ, **dict(kw))
                ctx.check(f"{side} {label}: CPython {want}, got {got}", got == want)


@test
def test_check_output_input_none_never_hands_the_child_halos_own_stdin(ctx: Ctx):
    from halo_harness import subprocess_safe
    with _stdin_never_ends():
        out = _answer(subprocess_safe._WIN["check_output"], _READ, input=None, text=True, timeout=_BOUND_S)
    ctx.check(f"an empty pipe: the child read 0 characters and ended, got {out}", out == ("ok", "0"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
