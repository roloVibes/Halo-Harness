"""tests.test_chrome_driver -- Halo 3.1.0.0 round R1: the one Chrome driver base
(tests/helpers/chrome_driver.py) and its one-Chrome-at-a-time lock
(tests/helpers/chrome_lock.py).

1. The lock serialises two drivers in one process (two threads) and two
   processes; it is re-entrant in one thread; a Chrome that fails to start
   lets it go.
2. `Driver.run`: a step that raises records `failed` and stops; a dict a step
   returns joins `out`; `main()` exits 0 / 1 (a step failed) / 2 (no Chrome)
   and prints `out` as the last line.
3. A real driver (`python -m tests.helpers.chrome_driver smoke`) started with
   BRIDGE_* scrubbed and a fake HOME/USERPROFILE (with the AppData folders
   Chrome needs) leaves that home untouched and removes the scratch home it
   made (skipped without Chrome).
Run: python -m tests.test_chrome_driver
"""
from __future__ import annotations

TIER = "full"  # the driver smoke starts headless Chrome: the full tier

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent


def _lock_path() -> Path:
    return Path(tempfile.mkdtemp(prefix="chrome-lock-test-")) / "chrome.lock"


class _FakeChrome:
    """Stands in for cdp.Chrome: records when it was open."""
    spans: list = []

    def __init__(self, exe, width, height):
        self.opened = time.monotonic()

    def go(self, url):
        pass

    def close(self):
        _FakeChrome.spans.append((self.opened, time.monotonic()))


class _SleepDriver:
    @staticmethod
    def make(lock_path, pause: float):
        from tests.helpers.chrome_driver import Driver

        class D(Driver):
            @contextmanager
            def session(self, c):
                yield ((time.sleep, (pause,)), (lambda: {"done": True}, ()))
        return D(chrome_cls=_FakeChrome, find=lambda: "fake-chrome", lock_path=lock_path)


@test
def test_lock_serialises_two_drivers_in_one_process(ctx: Ctx):
    lock_path = _lock_path()
    _FakeChrome.spans = []
    rcs = []
    buf = io.StringIO()

    def go():
        rcs.append(_SleepDriver.make(lock_path, 0.4).main())
    with contextlib.redirect_stdout(buf):
        threads = [threading.Thread(target=go) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(30)
    spans = sorted(_FakeChrome.spans)
    ctx.check(f"both drivers ran and passed, got {rcs}", rcs == [0, 0] and len(spans) == 2)
    ctx.check(f"the second Chrome opened only after the first closed, got {spans}", spans[1][0] >= spans[0][1])
    ctx.check("each printed its JSON line", buf.getvalue().count('{"done": true}') == 2)


_HOLDER = r'''
import sys, time
sys.path.insert(0, sys.argv[1])
from tests.helpers.chrome_lock import chrome_lock
from pathlib import Path
with chrome_lock(Path(sys.argv[2])):
    Path(sys.argv[3]).write_text("held", encoding="utf-8")
    time.sleep(float(sys.argv[4]))
'''


@test
def test_lock_serialises_two_processes(ctx: Ctx):
    from tests.helpers.chrome_lock import chrome_lock
    lock_path = _lock_path()
    marker = lock_path.parent / "held.txt"
    script = lock_path.parent / "holder.py"
    script.write_text(_HOLDER, encoding="utf-8")
    proc = subprocess.Popen([sys.executable, str(script), str(REPO), str(lock_path), str(marker), "1.5"])
    try:
        deadline = time.monotonic() + 20
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        ctx.check("the other process holds the lock", marker.exists())
        try:
            with chrome_lock(lock_path, timeout=0.3):
                got_it = True
        except TimeoutError:
            got_it = False
        ctx.check("this process waits while the other one holds it", got_it is False)
        t0 = time.monotonic()
        with chrome_lock(lock_path, timeout=30):
            waited = time.monotonic() - t0
        ctx.check(f"and gets it once the other one lets go, after {waited:.2f}s", waited < 30)
    finally:
        proc.wait(timeout=30)


@test
def test_lock_is_reentrant_and_a_failed_chrome_lets_it_go(ctx: Ctx):
    from tests.helpers.cdp import Chrome
    from tests.helpers.chrome_lock import chrome_lock, lock_for
    lock_path = _lock_path()
    with chrome_lock(lock_path, timeout=5):
        with chrome_lock(lock_path, timeout=0.5):
            ctx.check("the same thread takes it again without waiting", lock_for(lock_path).held)
        ctx.check("still held by the outer with", lock_for(lock_path).held)
    ctx.check("free after both", not lock_for(lock_path).held)
    try:
        Chrome(str(lock_path.parent / "no-such-chrome.exe"), lock_path=lock_path)
        ctx.check("a missing binary raises", False)
    except OSError:
        pass
    with chrome_lock(lock_path, timeout=1):
        ctx.check("the lock is free again after the failed start", True)


@test
def test_run_records_the_failing_step_and_main_exit_codes(ctx: Ctx):
    from tests.helpers.chrome_driver import Driver

    def ok():
        return {"a": 1}

    def boom():
        raise RuntimeError("the button never showed")

    def never():
        raise AssertionError("a step after a failure must not run")

    class D(Driver):
        @contextmanager
        def session(self, c):
            yield ((ok, ()), (boom, ()), (never, ()))
    lock_path = _lock_path()
    buf, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
        rc = D(chrome_cls=_FakeChrome, find=lambda: "x", lock_path=lock_path).main()
    got = json.loads(buf.getvalue().strip().splitlines()[-1])
    ctx.check(f"a failed step exits 1 and names the step, got {rc} {got}",
              rc == 1 and got.get("a") == 1 and got.get("failed", "").startswith("boom: RuntimeError: the button never showed"))
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = D(find=lambda: None, lock_path=lock_path).main()
    ctx.check(f"no Chrome: exit 2 and the no-Chrome line, got {rc} {buf.getvalue()!r}",
              rc == 2 and json.loads(buf.getvalue().strip().splitlines()[-1]) == {"error": "no Chrome found"})


def _fake_home() -> Path:
    home = Path(tempfile.mkdtemp(prefix="chrome-driver-fake-home-"))
    for sub in ("AppData/Local", "AppData/Roaming", ".config", ".cache", ".local/share"):
        (home / sub).mkdir(parents=True, exist_ok=True)
    return home


@test
def test_a_driver_with_bridge_scrubbed_leaves_the_real_home_untouched(ctx: Ctx):
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (the driver smoke needs headless Chrome)")
    home = _fake_home()
    env = driver_env(REPO)
    env.update(HOME=str(home), USERPROFILE=str(home), APPDATA=str(home / "AppData" / "Roaming"),
               LOCALAPPDATA=str(home / "AppData" / "Local"), XDG_CONFIG_HOME=str(home / ".config"),
               XDG_CACHE_HOME=str(home / ".cache"), XDG_DATA_HOME=str(home / ".local" / "share"))
    ctx.check("the child starts with no BRIDGE_* at all but the no-network seam",
              {k for k in env if k.startswith("BRIDGE_")} == {"BRIDGE_TEST_NO_BACKGROUND_NET"})
    r = subprocess.run([sys.executable, "-m", "tests.helpers.chrome_driver", "smoke"], capture_output=True, encoding="utf-8",
                       errors="replace", timeout=240, env=env, cwd=str(REPO))
    try:
        got = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        got = {}
    ctx.check(f"the driver ran, got {r.returncode} {r.stdout[-300:]!r} {r.stderr[-600:]!r}",
              r.returncode == 0 and "Halo Studio" in str(got.get("title")) and (got.get("tabs") or 0) > 0)
    ctx.check(f"its state dir was a scratch home outside the (fake) real home, got {got.get('state')}",
              bool(got.get("state")) and not str(got["state"]).startswith(str(home)))
    ctx.check("the (fake) real home has no .halo and no .rolo-claude",
              not (home / ".halo").exists() and not (home / ".rolo-claude").exists())
    scratch = Path(str(got.get("state") or home / "x")).parent
    # Windows shard 0 (run 42254683588, again 42679972220 on e4bcbcb8): the folder's removal lags the child's exit, over
    # 10 s under load, so the wait is 40 s and the check says how long it took
    deadline, t0 = time.time() + 40.0, time.time()
    while scratch.exists() and time.time() < deadline:
        time.sleep(0.2)
    ctx.check(f"the scratch home the driver made is gone (after {time.time() - t0:.1f}s)", not scratch.exists())


@test
def test_a_slow_or_failed_first_page_load_names_its_step_and_the_local_servers_own_answer(ctx: Ctx):
    """join batch 1: a macOS leg's first page load timed out at 60 s twice with nothing to say which step was slow.
    The driver now times each start-up step and the first navigate and prints a line for a slow (over 5 s) or failed
    one, and after a slow or failed first navigate to a loopback URL it times the server's own answer to a plain GET.
    Diagnosis only: the failure is still raised as it was, nothing retried, no wait made longer. No Chrome needed."""
    import http.server
    from tests.helpers import cdp
    ctx.check("quick steps print nothing", cdp.timing_line("websocket ready", 0.4) is None
              and cdp.timing_line("websocket ready", cdp.SLOW_STEP_S) is None)
    ctx.check(f"a slow step names itself and its seconds, got {cdp.timing_line('browser start', 7.25)!r}",
              cdp.timing_line("browser start", 7.25) == "cdp timing: browser start took 7.2s")
    failed = cdp.timing_line("DevTools target list", 0.1, TimeoutError("timed out"))
    ctx.check(f"a failed step prints even when quick, got {failed!r}",
              failed == "cdp timing: DevTools target list took 0.1s and failed: TimeoutError: timed out")

    class _Ok(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *a):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Ok)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    now = [100.0]
    saved_clock = cdp._clock
    cdp._clock = lambda: now[0]
    try:
        c = cdp.Chrome.__new__(cdp.Chrome)  # no browser: only go() and its timing are under test
        c._navigated = False
        calls: list = []

        def _call(method, **params):
            calls.append(params.get("url"))
            if len(calls) == 1:
                now[0] += 60.0
                raise TimeoutError("timed out")
            return {}

        c.call = _call
        url = f"http://127.0.0.1:{srv.server_address[1]}/?tour=off#t=secret"
        err = io.StringIO()
        raised = None
        with contextlib.redirect_stderr(err):
            try:
                c.go(url)
            except TimeoutError as e:
                raised = e
            c.go(url)  # a later navigate is not timed
        lines = err.getvalue().splitlines()
        ctx.check(f"the first navigate's failure is raised as it was, got {raised!r}", isinstance(raised, TimeoutError))
        ctx.check(f"one Page.navigate each, nothing retried, got {calls}", calls == [url, url])
        ctx.check(f"the step and its 60 s are named, got {lines}",
                  any(L.startswith("cdp timing: first navigate") and "took 60.0s and failed: TimeoutError" in L for L in lines))
        ctx.check(f"the local server's own answer is timed, got {lines}",
                  any("the local server answered a plain GET in" in L and "HTTP 200" in L for L in lines))
        ctx.check(f"the later navigate printed nothing, got {lines}", len(lines) == 2)
    finally:
        cdp._clock = saved_clock
        srv.shutdown()
        srv.server_close()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
