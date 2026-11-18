"""tests.test_chrome_close -- 3.6.0.4 S batch 2: the rig's driver ends every process of ITS Chrome before its close
returns (tests/helpers/chrome_driver.end_profile_processes, called by cdp.Chrome.close and one_shot).

A Windows runner marked tests.test_packs_studio_ui red for leftover processes: the test's own Chrome had ended, but
two of its helpers (`chrome.exe --type=utility ...`, `chrome.exe --type=crashpad-handler ...`, both carrying the
driver's throwaway `--user-data-dir`) were still closing. The leftover check of tests/run_all.py stays as strict as
it is; the driver now waits a bound for the processes that carry its own profile folder, then ends by pid any still
there. Never by name, never another Chrome. No browser runs here: every test feeds a fake process table.
Run: python -m tests.test_chrome_close
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.leftovers import Proc  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


class _World:
    """A fake process table that changes over a fake clock: `tables` is [(at_seconds, {pid: Proc})]; a scan at time
    t sees the last table whose time is <= t. `end` records the pids ended and removes them from every later look."""

    def __init__(self, tables):
        self.tables, self.now, self.ended, self.scans = tables, 0.0, [], 0

    def clock(self) -> float:
        return self.now

    def sleep(self, s: float) -> None:
        self.now += s

    def scan(self) -> dict:
        self.scans += 1
        seen = [t for at, t in self.tables if at <= self.now][-1]
        return {pid: p for pid, p in seen.items() if pid not in self.ended}

    def end(self, p: Proc) -> bool:
        self.ended.append(p.pid)
        return True


def _p(pid: int, cmd: str) -> Proc:
    return Proc(pid, 1, 100 + pid, cmd=cmd, args=cmd)


def _tables(profile: str, other: str):
    """The browser's main process is already gone; its two helpers go a moment later. Another Chrome with its own
    profile (one whose folder name only STARTS with ours, too) and an unrelated program run the whole time."""
    utility = _p(11, f'"chrome.exe" --type=utility --utility-sub-type=quarantine.mojom.Quarantine '
                     f'"--user-data-dir={profile}" --lang=en-US')
    crashpad = _p(12, f'chrome.exe --type=crashpad-handler --user-data-dir={profile} --monitor-self')
    stranger = _p(20, f'chrome.exe --type=renderer --user-data-dir={other} --lang=en-US')
    twin = _p(21, f'chrome.exe --type=gpu-process --user-data-dir={profile}2 --lang=en-US')
    editor = _p(30, f'notepad.exe {profile}')
    base = {20: stranger, 21: twin, 30: editor}
    return utility, crashpad, base


@test
def test_close_waits_for_its_own_helpers_and_ends_none_that_go_in_time(ctx: Ctx):
    from tests.helpers import chrome_driver
    profile, other = str(Path(tempfile.gettempdir()) / "halo-cdp-ab12cd34"), "/elsewhere/a-person-profile"
    utility, crashpad, base = _tables(profile, other)
    world = _World([(0.0, {**base, 11: utility, 12: crashpad}), (0.5, {**base, 12: crashpad}), (1.2, dict(base))])
    ended = chrome_driver.end_profile_processes(profile, scan=world.scan, end=world.end, clock=world.clock,
                                                sleep=world.sleep)
    ctx.check(f"helpers that go within the bound are waited for, none is ended, got ended={world.ended}",
              world.ended == [] and ended == [])
    ctx.check(f"it returns once its own helpers are gone, not at the bound, got t={world.now:.2f}",
              1.2 <= world.now < 2.0)


@test
def test_close_ends_by_pid_what_is_left_after_the_bound_and_never_another_chrome(ctx: Ctx):
    from tests.helpers import chrome_driver
    profile, other = "C:/Temp/halo-cdp-ab12cd34", "C:/Users/someone/AppData/Local/Google/Chrome/User Data"
    utility, crashpad, base = _tables(profile.replace("/", "\\"), other)  # Windows writes backslashes
    world = _World([(0.0, {**base, 11: utility, 12: crashpad}), (3.0, {**base, 12: crashpad})])
    ended = chrome_driver.end_profile_processes(profile, scan=world.scan, end=world.end, clock=world.clock,
                                                sleep=world.sleep)
    ctx.check(f"the helper still there after the bound ({chrome_driver.CLOSE_BOUND_S} s) is ended by pid, and only "
              f"it: never another profile's Chrome, a folder that only starts with ours, or a program naming the "
              f"folder; got ended={world.ended}", world.ended == [12] and [p.pid for p in ended] == [12])
    ctx.check(f"it waited the whole bound first, got t={world.now:.2f}",
              chrome_driver.CLOSE_BOUND_S <= world.now < chrome_driver.CLOSE_BOUND_S + 1.0)
    ctx.check("the bound is the ruling's 10 s", chrome_driver.CLOSE_BOUND_S == 10.0)


@test
def test_nothing_of_its_profile_running_costs_one_look_and_no_wait(ctx: Ctx):
    from tests.helpers import chrome_driver
    _u, _c, base = _tables("/tmp/halo-cdp-ab12cd34", "/tmp/halo-cdp-zz99yy88")
    world = _World([(0.0, dict(base))])
    chrome_driver.end_profile_processes("/tmp/halo-cdp-ab12cd34", scan=world.scan, end=world.end,
                                        clock=world.clock, sleep=world.sleep)
    ctx.check(f"one scan, no sleep, nothing ended, got scans={world.scans} t={world.now} ended={world.ended}",
              world.scans == 1 and world.now == 0.0 and world.ended == [])


class _ExitedProc:
    pid, returncode = 4242, 0

    def wait(self, timeout=None):
        return 0

    def terminate(self):
        raise AssertionError("an exited browser is not terminated")


@test
def test_cdp_close_ends_its_own_chrome_helpers_before_it_returns(ctx: Ctx):
    from tests.helpers import cdp, chrome_driver
    profile = tempfile.mkdtemp(prefix="halo-cdp-")
    utility, crashpad, base = _tables(profile, "/elsewhere/a-person-profile")
    world = _World([(0.0, {**base, 11: utility, 12: crashpad})])  # neither helper goes by itself
    saved = (chrome_driver._scan_all, chrome_driver._end_by_pid, chrome_driver._clock, chrome_driver._sleep)
    chrome_driver._scan_all, chrome_driver._end_by_pid = world.scan, world.end
    chrome_driver._clock, chrome_driver._sleep = world.clock, world.sleep
    try:
        c = cdp.Chrome.__new__(cdp.Chrome)  # no browser: only close() is under test
        c.sock, c.proc, c.profile, c._locked = None, _ExitedProc(), profile, False
        c.close()
    finally:
        chrome_driver._scan_all, chrome_driver._end_by_pid, chrome_driver._clock, chrome_driver._sleep = saved
    ctx.check(f"close() ended both helpers of its own profile by pid (the newest first), got {world.ended}",
              world.ended == [12, 11])
    ctx.check("and removed the profile folder after them", not Path(profile).exists())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
