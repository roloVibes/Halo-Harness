"""tests.test_update_process_list_encoding -- 3.6.0.0 fix package update-install: Windows' process list is read as
UTF-8. Windows PowerShell 5.1 writes in the console's OEM code page (437/850: u-umlaut is byte 0x81) and Python
read it in the ANSI code page (cp1252, where 0x81 is undefined): ONE process anywhere on the machine whose command
line held such a letter (a user folder whose name has one) emptied the whole list, so `halo update` saw no
other halo running, stopped none and waited for none, and installed while another halo.exe held the files.

The first test feeds the parse a fake PowerShell that encodes the way the real one does and decodes the way
subprocess does, on every platform; the two Windows tests start a real child with such a letter in its argv."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all
from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once

ensure_scoped_state_dir_once()

from halo_harness import update as upd

test, TESTS = new_registry()

MARK = "M\u00fcnchen-\u00fc-\u00ec-\u00c5"  # u-umlaut, i-grave, A-ring: 0x81, 0x8D, 0x8F in OEM 437, none in cp1252


class _Proc:
    def __init__(self, stdout):
        self.stdout, self.stderr, self.returncode = stdout, "", 0


def _powershell_like(rows: list):
    """A stand-in for `subprocess.run(["powershell", ...])`: the JSON goes out in UTF-8 only when the script asks
    for it (`[Console]::OutputEncoding = UTF8`), else in OEM 437 as Windows PowerShell 5.1 writes it; it is read
    back with the `encoding`/`errors` the caller passed (text mode without one: cp1252, this PC's ANSI page). A
    byte that does not decode raises, as the real reader thread does."""
    calls = []

    def run(cmd, **kw):
        calls.append((cmd, kw))
        payload = json.dumps(rows, ensure_ascii=False)
        script = cmd[-1] if isinstance(cmd, (list, tuple)) else str(cmd)
        utf8 = "OutputEncoding" in script and "UTF8" in script
        raw = payload.encode("utf-8" if utf8 else "cp437")
        if not (kw.get("text") or kw.get("encoding") or kw.get("universal_newlines")):
            return _Proc(raw)
        return _Proc(raw.decode(kw.get("encoding") or "cp1252", kw.get("errors") or "strict"))
    return run, calls


@test
def test_one_process_with_a_u_umlaut_does_not_empty_the_windows_process_list(ctx: Ctx):
    me = os.getpid()
    rows = [{"ProcessId": me + 1, "ParentProcessId": 1, "CommandLine": "C:\\tools\\halo.exe studio --no-open"},
            {"ProcessId": me + 2, "ParentProcessId": 1, "CommandLine": f"python.exe -c pass {MARK}"}]
    run, calls = _powershell_like(rows)
    got = upd.list_processes(run_fn=run, windows=True)
    ctx.check(f"both rows read, the marked command line intact, got {got}",
              [(p, c) for p, _pp, c in got] == [(me + 1, rows[0]["CommandLine"]), (me + 2, rows[1]["CommandLine"])])
    ctx.check(f"the other halo is named from it, got {got}", upd.halo_what(got[0][2]) == "studio")
    ctx.check(f"PowerShell is asked for UTF-8 and it is read as UTF-8, got {calls[0]}",
              "OutputEncoding" in calls[0][0][-1] and calls[0][1].get("encoding") == "utf-8"
              and calls[0][1].get("errors") == "replace")


def _child_with_the_mark():
    return subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)", MARK],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


@test
def test_windows_the_real_process_list_reads_a_command_line_with_a_u_umlaut(ctx: Ctx):
    if os.name != "nt":
        raise SkipTest("the PowerShell process list is Windows only")
    child = _child_with_the_mark()
    try:
        time.sleep(0.5)
        rows = upd.list_processes()
        mine = [c for p, _pp, c in rows if p == child.pid]
        ctx.check(f"the list is not empty, got {len(rows)} rows", len(rows) > 5)
        ctx.check(f"this child is in it with its argv read back, got {mine}", len(mine) == 1 and MARK in mine[0])
    finally:
        child.kill()
        child.wait(timeout=10)


@test
def test_windows_the_studio_check_reads_a_command_line_with_a_u_umlaut(ctx: Ctx):
    """The same read for one pid (studio/launch.py, `pid_is_studio`): a Studio whose --cwd holds such a letter."""
    if os.name != "nt":
        raise SkipTest("the PowerShell command-line read is Windows only")
    from halo_harness.studio import launch
    child = _child_with_the_mark()
    try:
        time.sleep(0.5)
        got = launch._windows_cmdline(child.pid)
        ctx.check(f"the command line read back with the letter, got {got!r}", MARK in got)
    finally:
        child.kill()
        child.wait(timeout=10)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
