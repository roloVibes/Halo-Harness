"""tests.test_open_url_browser -- Halo opens a page in the browser the person chose (halo_harness/closing.open_url).

On Windows, inside a Job object (a CI runner's; uv's and pip's `halo.exe` launchers make one), open_url started the
system's default browser through `rundll32 url.dll,FileProtocolHandler` and never read BROWSER: a person's own
BROWSER was ignored, and scripts/realcheck's stand-in browser (BROWSER) was passed over for the real one -- Edge left
running in every `init` / `studio` closing row of CI's Windows realcheck, and a real browser opened on the desktop of
anyone running `realcheck --installed`. BROWSER is read as Python's webbrowser reads it everywhere else: entries split
by os.pathsep, each one a program given the URL as its last argument, or a command line whose %s is the URL; when
BROWSER names programs and none starts, no other browser opens in their place.

Nothing here opens a real browser: every spawn is recorded by a stand-in Popen, and the one real start (Windows, in a
Job) runs realcheck's stand-in browser, which writes the URL to a file and exits.
Run: python -m tests.test_open_url_browser
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
WIN = os.name == "nt"
URL = "http://127.0.0.1:9/?mode=setup&first=1#t=probe"


class _Recorder:
    """Stands in for subprocess.Popen: writes the spawn down, starts nothing (or fails, for a program set to fail)."""
    seen: list = []
    fail: set = set()

    def __init__(self, args, *a, **kw):
        first = args if isinstance(args, str) else args[0]
        _Recorder.seen.append((args, kw))
        if any(f in first for f in _Recorder.fail):
            raise FileNotFoundError(first)
        self.pid, self._handle, self.returncode = 0, None, None

    def poll(self):
        return 0


def _open_recorded(browser, fail=()) -> "tuple[bool, list]":
    from halo_harness import closing
    saved_popen, saved_job, saved_env = subprocess.Popen, closing._in_a_job, os.environ.get("BROWSER")
    saved_frees = closing.breakaway_frees
    _Recorder.seen, _Recorder.fail = [], set(fail)
    subprocess.Popen = _Recorder
    closing._in_a_job = lambda: True
    closing.breakaway_frees = lambda: True  # fx jb8: open_url asks it first (a breakaway that frees starts in place)
    if browser is None:
        os.environ.pop("BROWSER", None)
    else:
        os.environ["BROWSER"] = browser
    try:
        return closing.open_url(URL), list(_Recorder.seen)
    finally:
        subprocess.Popen, closing._in_a_job, closing.breakaway_frees = saved_popen, saved_job, saved_frees
        os.environ.pop("BROWSER", None) if saved_env is None else os.environ.__setitem__("BROWSER", saved_env)


@test
def test_browser_is_read_as_webbrowser_reads_it(ctx: Ctx):
    from halo_harness import closing
    sep = os.pathsep
    prog = str(Path(tempfile.gettempdir()) / "my browser" / "b.exe")
    ctx.check("unset or empty: no choice", closing._chosen_browsers(URL, "") == [] and closing._chosen_browsers(URL, sep) == [])
    ctx.check("a program gets the URL as its last argument, its path kept whole (spaces too)",
              closing._chosen_browsers(URL, prog) == [[prog, URL]])
    got = closing._chosen_browsers(URL, f"{prog}{sep}  other --new-tab %s  {sep}")
    ctx.check(f"several, in order; %s marks where the URL goes, got {got}",
              got == [[prog, URL], f"other --new-tab {URL}"])


@test
def test_in_a_job_the_persons_browser_starts_out_of_the_job_and_never_the_system_one(ctx: Ctx):
    """Windows: the Job road honours BROWSER; the system's default (rundll32) is only for an unset BROWSER."""
    if not WIN:
        ctx.check("POSIX: open_url asks webbrowser, which reads BROWSER itself (no Job road)", True)
        return
    from halo_harness import closing
    prog = str(Path(tempfile.gettempdir()) / "rc browser" / "realcheck-browser.exe")
    os.environ["HALO_OWNER"] = "4242-0123456789"
    try:
        ok, seen = _open_recorded(prog)
    finally:
        os.environ.pop("HALO_OWNER", None)
    args, kw = seen[0] if seen else ([], {})
    ctx.check(f"BROWSER set: that program got the URL, got {[s[0] for s in seen]}", ok and args == [prog, URL])
    ctx.check("it starts out of the Job, off this console, without Halo's owner variables",
              bool(int(kw.get("creationflags") or 0) & closing._BREAKAWAY)
              and kw.get("env", {}).get("HALO_OWNER", "").startswith(closing.KEPT_PREFIX)
              and closing.WATCH not in kw.get("env", {}))
    ok, seen = _open_recorded(None)
    ctx.check(f"BROWSER unset: the system's default browser through rundll32, got {[s[0] for s in seen]}",
              ok and [s[0] for s in seen] == [["rundll32", "url.dll,FileProtocolHandler", URL]])
    ok, seen = _open_recorded(f"{prog}{os.pathsep}second.exe", fail={"realcheck-browser", "second"})
    ctx.check(f"BROWSER names programs that will not start: False, and no other browser opens, got {[s[0] for s in seen]}",
              ok is False and [s[0][0] for s in seen] == [prog, "second.exe"])


_IN_A_JOB = r'''
import ctypes, os, sys, time
from ctypes import wintypes
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.CreateJobObjectW.restype = wintypes.HANDLE
k32.GetCurrentProcess.restype = wintypes.HANDLE
k32.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
job = k32.CreateJobObjectW(None, None)  # no BREAKAWAY_OK: what a CI runner's Job may be
assert job and k32.AssignProcessToJobObject(job, k32.GetCurrentProcess())
sys.path.insert(0, sys.argv[1])
from halo_harness import closing
assert closing._in_a_job(), "not in a Job"
url = sys.argv[2]
# never the real browser: only a tree that reads BROWSER may go on to open_url
assert closing._chosen_browsers(url) == [[os.environ["BROWSER"], url]], "BROWSER not read"
print("opened", closing.open_url(url), flush=True)
'''


@test
def test_a_halo_in_a_job_opens_the_page_in_the_browser_stand_in(ctx: Ctx):
    """Windows, for real: a process in a Job object (no breakaway allowed) with BROWSER = realcheck's stand-in opens
    the page there; the stand-in writes the URL down (the real default browser would have been started before)."""
    if not WIN:
        ctx.check("POSIX has no Job objects", True)
        return
    sys.path.insert(0, str(REPO / "scripts"))
    from realcheck import fakes
    root = Path(tempfile.mkdtemp(prefix="halo-open-url-"))
    browser, out = fakes.browser_command(root)
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HALO_", "BRIDGE_"))}
    env.update(BROWSER=browser, BRIDGE_TEST_HOME=str(root / "home"), PYTHONPATH=str(REPO), HALO_NO_UPDATER="1",
               OLLAMA_HOST="http://127.0.0.1:9")
    r = subprocess.run([sys.executable, "-c", _IN_A_JOB, str(REPO), URL], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=120, env=env)
    end = time.monotonic() + 20
    while not fakes.opened_urls(out) and time.monotonic() < end:
        time.sleep(0.1)
    ctx.check(f"open_url said yes, got {r.returncode} {r.stdout[-200:]!r} {r.stderr[-300:]!r}",
              r.returncode == 0 and "opened True" in r.stdout)
    ctx.check(f"the stand-in got the whole URL, got {fakes.opened_urls(out)}", fakes.opened_urls(out) == [URL])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
