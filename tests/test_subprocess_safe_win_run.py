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


_COUNT = "import sys; open(sys.argv[1], 'w').write(str(len(sys.stdin.buffer.read())))"
_HOLDS = b"abc"  # what this process's own stdin holds: a child that inherits it reads 3 bytes, the null device 0


@contextlib.contextmanager
def _stdin_holds(data: bytes):
    """fd 0 is a pipe holding `data` and then its end: a child that inherits it reads `data`."""
    r, w = os.pipe()
    os.write(w, data)
    os.close(w)
    saved = os.dup(0)
    os.dup2(r, 0)
    try:
        yield
    finally:
        os.dup2(saved, 0)
        for fd in (saved, r):
            os.close(fd)


def _read_by_child(door: str, out: Path, **kw) -> int:
    """How many bytes a REAL child started through `door` of subprocess_safe read from its stdin."""
    from halo_harness import subprocess_safe as sp
    argv = [sys.executable, "-I", "-S", "-c", _COUNT, str(out)]
    with _stdin_holds(_HOLDS):
        if door == "Popen":
            p = sp.Popen(argv, stdout=subprocess.DEVNULL, **kw)
            try:
                p.communicate(timeout=_BOUND_S)  # a stdin=PIPE is closed empty
            finally:
                if p.poll() is None:
                    p.kill()
                    p.wait(_BOUND_S)
        elif door == "check_output":
            sp.check_output(argv, timeout=_BOUND_S, **kw)
        else:
            getattr(sp, door)(argv, stdout=subprocess.DEVNULL, timeout=_BOUND_S, **kw)
    return int(out.read_text())


@test
def test_while_the_terminal_app_is_up_a_child_gets_the_null_device_unless_its_stdin_is_named(ctx: Ctx):
    """3.6.0.18 K: while the terminal app has the terminal no child inherits its input (a `claude auth status` took the
    person's Ctrl+C); a caller that names stdin (None too: inherit on purpose) or gives input is left as written; with
    the switch off nothing changes."""
    import tempfile
    from halo_harness import subprocess_safe as sp
    switch = getattr(sp, "set_terminal_app", None)
    ctx.check("subprocess_safe has the switch (set_terminal_app / terminal_app_is_up)",
              callable(switch) and callable(getattr(sp, "terminal_app_is_up", None)))
    if not callable(switch):
        return
    was = sp.terminal_app_is_up()
    with tempfile.TemporaryDirectory() as d:
        n = iter(range(100))
        try:
            switch(True)
            ctx.check("the switch reads ON", sp.terminal_app_is_up() is True)
            for door in ("run", "call", "check_call", "check_output", "Popen"):
                got = _read_by_child(door, Path(d) / f"{next(n)}.txt")
                ctx.check(f"ON, {door}, no stdin named: the null device (0 bytes), got {got}", got == 0)
                got = _read_by_child(door, Path(d) / f"{next(n)}.txt", stdin=None)
                ctx.check(f"ON, {door}, stdin=None named: inherited as written (3), got {got}", got == len(_HOLDS))
            for door in ("run", "check_output", "Popen"):
                kw = dict(input=b"zz") if door != "Popen" else dict(stdin=subprocess.PIPE)
                got = _read_by_child(door, Path(d) / f"{next(n)}.txt", **kw)
                want = 2 if door != "Popen" else 0
                ctx.check(f"ON, {door}, {list(kw)} given: as written ({want}), got {got}", got == want)
            switch(False)
            ctx.check("the switch reads OFF", sp.terminal_app_is_up() is False)
            for door in ("run", "call", "check_call", "check_output", "Popen"):
                got = _read_by_child(door, Path(d) / f"{next(n)}.txt")
                ctx.check(f"OFF, {door}: inherited as written (3), got {got}", got == len(_HOLDS))
        finally:
            switch(was)


@test
def test_the_rule_leaves_a_tests_replacement_of_the_standard_function_the_call_as_written(ctx: Ctx):
    from halo_harness import subprocess_safe as sp
    switch = getattr(sp, "set_terminal_app", None)
    if not callable(switch):
        ctx.check("subprocess_safe has the switch", False)
        return
    was, real = sp.terminal_app_is_up(), subprocess.run
    seen: list = []
    try:
        switch(True)
        subprocess.run = lambda args, **kw: seen.append(dict(kw))
        sp.run(["x"], capture_output=True)
    finally:
        subprocess.run = real
        switch(was)
    ctx.check(f"the replacement got the call as written, got {seen}", seen == [{"capture_output": True}])


@test
def test_while_the_app_is_suspended_the_persons_editor_has_the_terminals_input(ctx: Ctx):
    """3.6.0.18 K repair: the person's editor runs inside `with app.suspend():` (Ctrl+E, /editor, /improve's edit, the
    /mcp dialog's editor) as `sp.run(cmd, shell=True, env=scrubbed_env())`, naming no stdin. While the app is suspended
    the person has the terminal: run_tui's hand-over switches the rule off for the suspend and puts it back after."""
    import tempfile
    from halo_harness import subprocess_safe as sp
    from halo_harness.closing import scrubbed_env
    from halo_harness.tui import launch
    hand_over = getattr(launch, "give_the_terminal_on_suspend", None)
    ctx.check("launch has give_the_terminal_on_suspend", callable(hand_over))
    if not callable(hand_over):
        return
    seen: list = []

    class App:  # Textual's App.suspend is a context-manager method of the same shape
        @contextlib.contextmanager
        def suspend(self):
            seen.append("suspend")
            yield
            seen.append("resume")

    app, was = App(), sp.terminal_app_is_up()
    with tempfile.TemporaryDirectory() as d:
        try:
            sp.set_terminal_app(True)
            hand_over(app)
            with app.suspend():
                ctx.check("suspended: the rule reads OFF", sp.terminal_app_is_up() is False)
                got = _read_by_child("run", Path(d) / "editor.txt", env=scrubbed_env())
                ctx.check(f"suspended: the editor-shaped child inherits the input (3), got {got}", got == len(_HOLDS))
            ctx.check(f"the app's own suspend ran around it, got {seen}", seen == ["suspend", "resume"])
            ctx.check("resumed: the rule reads ON again", sp.terminal_app_is_up() is True)
            got = _read_by_child("run", Path(d) / "after.txt", env=scrubbed_env())
            ctx.check(f"resumed: the same call gets the null device (0), got {got}", got == 0)
            sp.set_terminal_app(False)
            with app.suspend():
                pass
            ctx.check("a suspend while the rule is off leaves it off", sp.terminal_app_is_up() is False)
            hand_over(object())  # a stand-in app without suspend (the closing tests' fake) is left as it is
        finally:
            sp.set_terminal_app(was)
    src = (Path(__file__).resolve().parent.parent / "halo_harness" / "tui" / "launch.py").read_text(encoding="utf-8")
    ctx.check("run_tui hands the terminal over on a suspend before app.run()",
              0 <= src.find("give_the_terminal_on_suspend(app)") < src.find("app.run()"))


@test
def test_launch_switches_the_rule_on_around_the_app_and_off_in_its_finally(ctx: Ctx):
    src = (Path(__file__).resolve().parent.parent / "halo_harness" / "tui" / "launch.py").read_text(encoding="utf-8")
    on, run, off = (src.find("set_terminal_app(True)"), src.find("app.run()"), src.find("set_terminal_app(False)"))
    ctx.check("run_tui turns the rule ON before app.run()", 0 <= on < run)
    ctx.check("... and OFF after it (in its finally)", run < off and src.rfind("finally:", run, off) > run)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
