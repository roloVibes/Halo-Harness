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

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all  # noqa: E402

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


@test
def test_a_start_handed_to_a_thread_is_worded_opening_never_opened(ctx: Ctx):
    """join: on the threaded Windows path open_url returns True before anything opened; the words say "Opening"."""
    from halo_harness import closing, subprocess_safe
    from halo_harness.providers.copilot_auth import signin_line
    from halo_harness.studio.edit_open import _describe
    if WIN:
        saved = (subprocess_safe.Popen, closing._in_a_job, closing.breakaway_frees, os.environ.get("BROWSER"))
        _Recorder.seen, _Recorder.fail = [], set()
        subprocess_safe.Popen, closing._in_a_job = _Recorder, (lambda: True)
        os.environ["BROWSER"] = str(Path(tempfile.gettempdir()) / "no-such-browser.exe")
        try:
            got = {}
            for frees in (False, True):
                closing.breakaway_frees = lambda f=frees: f
                got[frees] = (closing.open_url(URL), closing.open_unsure())
                with closing._LOCK:
                    ths, closing._BROWSERS[:] = list(closing._BROWSERS), []
                for th in ths:
                    th.join(10)
        finally:
            subprocess_safe.Popen, closing._in_a_job, closing.breakaway_frees, b = saved
            os.environ.pop("BROWSER", None) if b is None else os.environ.__setitem__("BROWSER", b)
            closing._OPENING.unsure = False
        ctx.check(f"held by a Job: True and unsure; started in place: True and sure, got {got}",
                  got == {False: (True, True), True: (True, False)} and len(_Recorder.seen) == 2)
    ctx.check("copilot: unsure says Opening and to open the page below",
              signin_line(True, True, 300).startswith("Opening the Microsoft sign-in page in your browser; if nothing "
                                                      "opens, open the page below yourself. Waiting up to 5 minutes"))
    ctx.check("copilot: sure says Opened", signin_line(True, False, 300).startswith("Opened the Microsoft sign-in page"))
    ctx.check("copilot: nothing took it", signin_line(False, False, 300).startswith("Open this page to sign in:"))
    ctx.check("studio --edit: unsure says Opening with the address",
              _describe(URL, "opened", "agent:x", {"unsure": True}) ==
              f"Opening agent:x in Studio in your browser; if nothing opens, open it yourself: {URL}")
    ctx.check("studio --edit: sure says Opened", _describe(URL, "opened", "agent:x", {}).startswith("Opened agent:x"))


@test
def test_a_threaded_browser_start_sees_a_stop_and_a_close_does_not_wait_for_it(ctx: Ctx):
    """jb10 batch 3 (Windows, an outer Job that forbids breakaway): open_url checked the stop only on entry; the
    thread it handed the start to still opened the browser after Ctrl+C or a quit in the first 1-2 s, and close()
    waited for it. Now the thread checks the stop before each command, close() does not wait for a thread that has
    not started its command, and start_outside_job takes its spec back on a stop. Never a real browser."""
    import subprocess as real_sp
    import threading
    import time
    from halo_harness import closing, subprocess_safe
    if not WIN:
        ctx.check("the threaded start is the Windows path only", True)
        return
    saved = (subprocess_safe.Popen, closing._in_a_job, closing.breakaway_frees, os.environ.get("BROWSER"),
             closing.stop_asked, dict(closing._STATE), closing._run_wmi)
    real_stop = closing.stop_asked
    gate, entered = threading.Event(), threading.Event()

    def gated_stop() -> bool:  # the browser thread's first stop check waits here, as a slow scheduler would
        if threading.current_thread().name == "halo-browser-start" and not entered.is_set():
            entered.set()
            gate.wait(10)
        return real_stop()

    def take() -> list:
        with closing._LOCK:
            ths, closing._BROWSERS[:] = list(closing._BROWSERS), []
        return ths

    try:
        subprocess_safe.Popen, closing._in_a_job, closing.breakaway_frees = _Recorder, (lambda: True), (lambda: False)
        tmp = Path(tempfile.gettempdir())
        # 1. the stop arrives before the thread's first command: no command, and the close does not wait
        _Recorder.seen, _Recorder.fail = [], set()
        os.environ["BROWSER"] = str(tmp / "no-such-browser-a.exe")
        closing.stop_asked = gated_stop
        ctx.check("handed to a thread", closing.open_url(URL) is True and closing.open_unsure())
        entered.wait(5)
        closing._STATE["owner_gone"] = True
        t0 = time.monotonic()
        with closing._LOCK:
            ths = list(closing._BROWSERS)
        closing.wait_for_browsers(2.0)
        waited = time.monotonic() - t0
        gate.set()
        for th in ths:
            th.join(5)
        ctx.check(f"no browser command after the stop, and the close did not wait, got "
                  f"{[s[0] for s in _Recorder.seen]} {waited:.2f}s",
                  _Recorder.seen == [] and waited < 1.0)
        # 2. the stop arrives while the first browser program is being tried: the second is never started
        closing._STATE.clear()
        closing._STATE.update(saved[5])
        closing.stop_asked = real_stop
        _Recorder.seen, _Recorder.fail = [], {"slow-first"}
        held, release = threading.Event(), threading.Event()
        rec_init = _Recorder.__init__

        def slow_init(self, args, *a, **kw):
            if "slow-first" in str(args[0]):
                held.set()
                release.wait(10)
            rec_init(self, args, *a, **kw)

        _Recorder.__init__ = slow_init
        try:
            os.environ["BROWSER"] = os.pathsep.join([str(tmp / "slow-first.exe"), str(tmp / "second.exe")])
            closing.open_url(URL)
            held.wait(5)
            closing._STATE["owner_gone"] = True
            release.set()
            for th in take():
                th.join(5)
        finally:
            _Recorder.__init__ = rec_init
        ctx.check(f"only the program that was already starting, never the next, got {[s[0] for s in _Recorder.seen]}",
                  [str(s[0][0]) for s in _Recorder.seen] == [str(tmp / "slow-first.exe")])
        # 3. start_outside_job in the browser thread: a stop during the WMI start takes the spec back, starts
        # nothing in the Job either (it raises, so Popen does not fall back to a start inside the Job)
        closing._STATE.clear()
        closing._STATE.update(saved[5])
        calls: list = []

        def fake_wmi(cmdline, cwd, wait_s, stop):  # 3.6.0.18: the WMI create's PowerShell is closing._run_wmi
            calls.append(cmdline)
            closing._STATE["owner_gone"] = True
            return "0\n"

        closing._run_wmi = fake_wmi
        closing._OPENING.cancel_on_stop = True
        before = set(tmp.glob("halo-kept-*"))
        try:
            closing.start_outside_job([str(tmp / "b.exe"), URL], {"stdin": real_sp.DEVNULL, "stdout": real_sp.DEVNULL,
                                                                  "stderr": real_sp.DEVNULL}, wait_s=1.0)
            outcome = "returned"
        except closing.StartCancelled:
            outcome = "cancelled"
        finally:
            closing._OPENING.cancel_on_stop = False
        left = set(tmp.glob("halo-kept-*")) - before
        ctx.check(f"a stop during the outside start: cancelled, one WMI call, no folder left, got {outcome} "
                  f"{len(calls)} {left}", outcome == "cancelled" and len(calls) == 1 and not left)
        calls.clear()
        closing._OPENING.cancel_on_stop = True
        try:
            closing.start_outside_job([str(tmp / "b.exe"), URL], {"stdin": real_sp.DEVNULL}, wait_s=1.0)
            outcome = "returned"
        except closing.StartCancelled:
            outcome = "cancelled"
        finally:
            closing._OPENING.cancel_on_stop = False
        ctx.check(f"a stop before the outside start: no WMI call at all, got {outcome} {len(calls)}",
                  outcome == "cancelled" and calls == [])
    finally:
        gate.set()
        for th in take():
            th.join(5)
        (subprocess_safe.Popen, closing._in_a_job, closing.breakaway_frees, b, closing.stop_asked, st,
         closing._run_wmi) = saved
        closing._STATE.clear()
        closing._STATE.update(st)
        os.environ.pop("BROWSER", None) if b is None else os.environ.__setitem__("BROWSER", b)
        closing._OPENING.unsure = False


_MEMBER_BROWSER = r'''
import json, sys
sys.path.insert(0, sys.argv[1])
from halo_harness import closing
if sys.argv[3] == "fails":
    closing._assign_self = lambda job: False  # stood in: this halo could not join a Job of its own
closing.install(sweep_at_start=False)
seen = []


class _Door:  # the product's door to a window, recorded: no browser starts, and webbrowser.open stays Python's own
    @staticmethod
    def open_in_a_window(url):
        seen.append(url)
        return True


import webbrowser
stubbed = getattr(webbrowser.open, "__module__", "webbrowser") != "webbrowser"  # as open_url tells it
got = closing._python_browser(sys.argv[2], stubbed, _Door)
print(json.dumps({"member": bool(closing._STATE.get("member")), "stubbed": stubbed, "got": got, "seen": seen}))
'''


@test
def test_a_member_halo_never_starts_the_shells_browser_inside_its_own_job(ctx: Ctx):
    """3.6.0.23 J P7 (Windows): the shell's browser (webbrowser / os.startfile) started by this process is born in
    its Job and would close with Halo. While Halo is a member of a Job of its own, the not-stubbed fallback starts
    nothing and answers False (the caller prints the address); a halo that is no member opens it as before."""
    if not WIN:
        raise SkipTest("Windows only: Job objects")
    import json
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HALO_", "BRIDGE_"))}
    root = Path(tempfile.mkdtemp(prefix="halo-member-browser-"))
    env.update(BRIDGE_TEST_HOME=str(root / "home"), PYTHONPATH=str(REPO), HALO_NO_UPDATER="1",
               OLLAMA_HOST="http://127.0.0.1:9")
    got = {}
    for way in ("member", "fails"):
        r = subprocess.run([sys.executable, "-c", _MEMBER_BROWSER, str(REPO), URL, way], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=120, env=env)
        try:
            got[way] = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            got[way] = {"raw": r.stdout[-200:], "err": r.stderr[-300:]}
    m, f = got["member"], got["fails"]
    ctx.check(f"the not-stubbed branch is the one tested, got {got}", m.get("stubbed") is False)
    ctx.check(f"a member: nothing started, False, got {m}", m.get("member") is True and m.get("got") is False
              and m.get("seen") == [])
    ctx.check(f"no member (the path before): the door opens it, got {f}", f.get("member") is False
              and f.get("got") is True and f.get("seen") == [URL])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
