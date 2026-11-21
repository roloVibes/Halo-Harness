"""scripts/realcheck/named_end.py -- how the checker itself ended, said by its parent (3.6.0.9).

At 3.6.0.8's gate the checker passed all of its steps on Windows, wrote its result file, printed its last line, and
then ended with a status the shell could only report as 127 (Git Bash's number for a Windows exit status of the crash
kind that it does not know), with no line of its own; twice in one CI attempt, never on the rerun. A process cannot
say how it ended. Its parent can: with `--name-the-end` realcheck.py runs itself as a child of this module's
`run_named`, which lets the checker's own exit codes (0, 1, 2) through and, for any other end, prints ONE line with
the true status and what kind it is, and answers 1 (the step stays red: nothing is hidden).

A console control event (Ctrl+C, Ctrl+Break) that reaches the pair while the child runs does not end the parent: it
is noted with its time and said in that line, because one arriving while Python is ending (its own handlers are gone
by then) ends a process with exactly such a status.
"""
from __future__ import annotations

import signal
import subprocess
import sys
import time

OWN = (0, 1, 2)  # the checker's own exit codes: none failed, a step failed, a wrong command line
KINDS = {
    0xC000013A: "a console control event (Ctrl+C, Ctrl+Break or the console closing) ended it",
    0xC00000FD: "a stack overflow",
    0xC0000005: "an access violation",
    0xC0000374: "a fault in the heap",
    0xC0000409: "the C runtime stopped it (a fatal error or an abort)",
    0xC0000142: "a library could not start",
    0xC0000135: "a library was not found",
}


def end_line(code: int, events: list) -> str:
    """The one line for an end that is not the checker's own. `code`: the child's return code as subprocess gives it
    (POSIX: negative for a signal; Windows: the exit status, 32 bits)."""
    if code < 0:
        try:
            name = signal.Signals(-code).name
        except ValueError:
            name = "a signal this line does not know"
        what = f"ended by signal {-code} ({name})"
    else:
        status = code & 0xFFFFFFFF
        what = f"ended with status 0x{status:08X}: {KINDS.get(status, 'not a status this line knows')}"
    seen = f"; console control events that reached its parent meanwhile: {', '.join(events)}" if events else ""
    return f"realcheck: the checker itself {what}, after the lines above{seen}"


def run_named(argv: list, say=None) -> int:
    """Run `argv` (the checker) as a child with this process's own streams; its own exit code passes through, any
    other end is said in one line and answered with 1."""
    say = say or (lambda line: print(line, flush=True))
    events: list = []

    def note(signum, _frame) -> None:
        try:
            name = signal.Signals(signum).name
        except ValueError:
            name = str(signum)
        events.append(f"{time.strftime('%H:%M:%S')} {name}")

    old = {}
    for name in ("SIGINT", "SIGBREAK"):
        sig = getattr(signal, name, None)
        if sig is not None:
            try:
                old[sig] = signal.signal(sig, note)
            except (ValueError, OSError):  # not the main thread: the events are then not noted
                pass
    try:
        code = subprocess.Popen(argv).wait()
    finally:
        for sig, handler in old.items():
            try:
                signal.signal(sig, handler)
            except (ValueError, OSError):
                pass
    sys.stdout.flush()
    if code in OWN:
        return code
    say(end_line(code, events))
    return 1
