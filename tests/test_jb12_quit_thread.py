"""tests.test_jb12_quit_thread -- a quit never waits for a free thread, and the way out leaves evidence (Halo 3.6.0.0,
fix package "jb12").

CI's Windows realcheck row "session, background Bash job / Ctrl+C" found Halo, bash.exe and sleep.exe alive 5 s after
the keys Ctrl+C Ctrl+C Enter, all gone by 30 s; on a 24-core PC the same row ended in 0.9 s. Reproduced on that PC
with os.cpu_count() reporting 4 (a CI runner's vCPUs) and HALO_CLOSE_TRACE on: "quit asked" at the card's Enter, then
"quit: start" 8.35 s later, every thread of asyncio's default executor (min(32, cpus + 4) = 8) inside
textual/_win_sleep.py. On Windows every Textual timer sleeps on a thread of that pool, and the quit ran as a thread
worker on the same pool: it sat in the pool's queue until a timer woke, with the background job (its bash and its
sleep) and Halo still running. The quit (and Ctrl+Q's force quit) now run on threads of their own.

1. The quit card's Enter and Ctrl+Q reach controller.quit at once while every thread of the loop's default executor
   is busy (here: two threads, both held).
2. HALO_CLOSE_TRACE (off by default): one line per phase of the way out, and every thread's stack when a close is
   still running TRACE_STACKS_S later; nothing at all when unset.
3. scripts/realcheck: a closing row's launch gets HALO_CLOSE_TRACE (and HALO_INPUT_TRACE, the keys its console read);
   a row that left something carries the trace and its terminal's last screen in its evidence and its one-line detail.
Run: python -m tests.test_jb12_quit_thread
"""
from __future__ import annotations

TIER = "full"  # a TUI pilot (Textual run_test): the full tier

import asyncio
import os
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.test_ctrl_c_copy_quit import _app, _card_open, _Env  # noqa: E402

test, TESTS = new_registry()


def _hold_the_pool(n: int = 2):
    """The running loop's default executor, `n` threads, every one of them held (Textual's Windows timers do this to
    the real pool): returns the event that lets them go."""
    loop = asyncio.get_running_loop()
    loop.set_default_executor(ThreadPoolExecutor(max_workers=n))
    gate = threading.Event()
    for _ in range(n):
        loop.run_in_executor(None, gate.wait, 20)
    return gate


async def _quit_called_within(fake, seconds: float) -> "float | None":
    t0 = time.monotonic()
    while time.monotonic() - t0 < seconds:
        if fake.quit_called:
            return time.monotonic() - t0
        await asyncio.sleep(0.02)
    return None


@test
def test_the_quit_cards_enter_reaches_the_quit_while_every_pool_thread_is_busy(ctx: Ctx):
    async def body():
        with _Env():
            fake, app = _app()
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause(0.2)
                await pilot.press("ctrl+c")
                await pilot.press("ctrl+c")
                await pilot.pause(0.1)
                ctx.check("the second press opened the card", _card_open(app))
                gate = _hold_the_pool()
                try:
                    # the card's Enter (its binding's action), not awaited: a pilot press waits for the app to be idle
                    app.screen.action_confirm()
                    took = await _quit_called_within(fake, 1.5)
                    ctx.check(f"controller.quit ran within 1.5 s of Enter with the pool busy, took {took}", took is not None)
                finally:
                    gate.set()
                await pilot.pause(0.3)
            ctx.check(f"the app left with 0, got {app.return_code}", app.return_code == 0)
    asyncio.run(body())


@test
def test_ctrl_q_reaches_the_quit_while_every_pool_thread_is_busy(ctx: Ctx):
    async def body():
        # the force quit's 2.5 s os._exit guard is not this test's to fire: no real Timer while its thread may run
        with _Env(), mock.patch("threading.Timer") as timer:
            fake, app = _app()
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause(0.2)
                gate = _hold_the_pool()
                try:
                    app.action_force_quit()
                    took = await _quit_called_within(fake, 1.5)
                    ctx.check(f"Ctrl+Q's force quit reached controller.quit within 1.5 s with the pool busy, took {took}",
                              took is not None)
                finally:
                    gate.set()
                end = time.monotonic() + 5
                while not timer.called and time.monotonic() < end:  # its thread is done: the guard was (not) armed
                    await asyncio.sleep(0.05)
                await pilot.pause(0.3)
    asyncio.run(body())


def _run_app(auto) -> dict:
    """The real app loop (run_async: what app.run() runs), headless, driven by `auto`; then the app exits."""
    seen: dict = {}

    async def pilot_body(pilot):
        await auto(pilot, seen)
        pilot.app.exit()

    with _Env():
        _fake, app = _app()
        asyncio.run(app.run_async(headless=True, size=(100, 30), auto_pilot=pilot_body))
    return seen


@test
def test_a_textual_sleep_is_cancelled_at_once_while_a_default_pools_worth_of_threads_is_held(ctx: Ctx):
    """CI's slow exit once the quit started at once: "app exit asked" to "app.run returned" took 8.4 s with
    os.cpu_count() at 4. On Windows every Textual timer sleeps on a thread of the loop's default pool, and CANCELLING
    one needs a free thread of that pool too (textual/_win_sleep.py runs its cancel in the executor): with every
    thread asleep, the shutdown's cancels waited for a timer to wake. The app's loop now has a pool of
    APP_POOL_THREADS: a default pool's worth of held threads (the sleeping timers) leaves room for the cancel.
    Elsewhere a Textual sleep is asyncio's and holds no thread: it is cancelled at once either way."""
    from halo_harness.tui import app as app_mod
    from textual._time import sleep as textual_sleep
    pool = getattr(app_mod, "APP_POOL_THREADS", None)
    default = min(32, (os.cpu_count() or 1) + 4)  # the default pool's size

    async def auto(pilot, seen):
        await pilot.pause(0.3)
        loop = asyncio.get_running_loop()
        seen["max_workers"] = getattr(loop._default_executor, "_max_workers", None)
        gate = threading.Event()
        try:
            for _ in range(default):
                loop.run_in_executor(None, gate.wait, 8)
            await asyncio.sleep(0.3)
            task = asyncio.ensure_future(textual_sleep(30))
            await asyncio.sleep(0.3)
            t0 = time.monotonic()
            task.cancel()
            done, _ = await asyncio.wait({task}, timeout=3.0)
            seen["cancel_s"] = round(time.monotonic() - t0, 2) if done else None
        finally:
            gate.set()
    seen = _run_app(auto)
    ctx.check(f"the app's loop has a pool of APP_POOL_THREADS ({pool}), more than twice the default {default}, got "
              f"{seen.get('max_workers')}", pool is not None and seen.get("max_workers") == pool > 2 * default)
    ctx.check(f"a Textual sleep was cancelled within 3 s with {default} pool threads held, took {seen.get('cancel_s')}",
              seen.get("cancel_s") is not None and seen["cancel_s"] < 1.0)


@test
def test_the_close_trace_is_off_by_default_and_writes_each_phase_when_named(ctx: Ctx):
    from halo_harness import closing
    d = Path(tempfile.mkdtemp(prefix="halo-jb12-"))
    f = d / "trace.txt"
    with mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop(closing.TRACE, None)
        closing.trace("nothing")
        ctx.check("unset: no file is written", not f.exists())
        os.environ[closing.TRACE] = str(f)
        closing.trace("quit: start")
        closing.trace("quit: end after 0.01 s")
    lines = f.read_text(encoding="utf-8").splitlines()
    ctx.check(f"set: one line per phase with the time, the monotonic time, the pid and the thread, got {lines}",
              len(lines) == 2 and lines[0].endswith("quit: start") and " mono=" in lines[0]
              and f"pid={os.getpid()}" in lines[0] and "[MainThread]" in lines[0])


class _Registry:
    def __init__(self) -> None:
        self.killed = 0

    def kill_all(self) -> None:
        self.killed += 1


class _Session:
    def __init__(self, registry) -> None:
        self._stopping, self.abort = threading.Event(), threading.Event()
        self.job_registry = registry
        self.interactive, self.busy, self.turn_count = False, False, 0

    def run(self, commands, put, mcp_status_fn=None) -> int:
        while commands.get() is not None:
            pass
        return 0

    def _fire_session_end(self, why: str) -> None:
        pass

    def close_runtimes(self) -> None:
        pass


@test
def test_a_controller_quit_traces_its_phases_in_order(ctx: Ctx):
    from halo_harness import closing
    from halo_harness.controller import Controller
    d = Path(tempfile.mkdtemp(prefix="halo-jb12-"))
    f = d / "trace.txt"
    with mock.patch.dict(os.environ, {closing.TRACE: str(f), "BRIDGE_TEST_HOME": str(d),
                                      "OLLAMA_HOST": "http://127.0.0.1:9", "HALO_NO_UPDATER": "1"}):
        c = Controller(session=_Session(_Registry()), cwd=d, state_dir=d / ".halo").start()
        c.quit()
    text = f.read_text(encoding="utf-8") if f.exists() else ""
    want = ["quit: start", "quit: background jobs stopped", "quit: worker joined", "quit: end"]
    at = [text.find(w) for w in want]
    ctx.check(f"the quit's phases are in the trace, in order: {list(zip(want, at))}", all(a >= 0 for a in at)
              and at == sorted(at))


@test
def test_a_close_still_running_later_leaves_every_threads_stack_in_the_trace(ctx: Ctx):
    d = Path(tempfile.mkdtemp(prefix="halo-jb12-"))
    f = d / "trace.txt"
    code = ("import time, threading\n"
            "from halo_harness import closing\n"
            "closing.TRACE_STACKS_S = 0.5\n"
            "threading.Thread(target=time.sleep, args=(3,), name='held-thread', daemon=True).start()\n"
            "closing.trace('quit asked', stacks=True)\n"
            "time.sleep(1.5)\n")
    env = dict(os.environ, PYTHONPATH=str(REPO), HALO_CLOSE_TRACE=str(f))
    r = subprocess.run([sys.executable, "-c", code], env=env, cwd=str(d), capture_output=True, text=True, timeout=60)
    text = f.read_text(encoding="utf-8", errors="replace") if f.exists() else ""
    ctx.check(f"the child ran (exit {r.returncode}, {r.stderr[-300:]!r})", r.returncode == 0)
    ctx.check(f"the phase line and then every thread's stack, got {text[:600]!r}", "quit asked" in text
              and text.count("most recent call first") >= 2 and "time.sleep" not in text.split("quit asked")[0])


class _Term:
    started_at = 0.0
    pid = 0

    def poll(self):
        return 0

    def plain(self) -> str:
        return ""

    def cleanup(self) -> None:
        pass


class _Home:
    def __init__(self, d: Path) -> None:
        self.dir = d


class _CloseCtx:
    """What one_close asks of the check's context, recorded: the environment the launch got."""

    def __init__(self, d: Path) -> None:
        self.d, self.envs = d, []
        self.provider = mock.Mock()

    def home(self, name):
        return _Home(self.d)

    def env(self, h, **extra):
        return dict(extra)

    def terminal(self, h, *args, env=None):
        self.envs.append(env)
        return _Term()

    def end_leftovers(self, h):
        return []


@test
def test_every_closing_row_launches_with_the_close_trace_on(ctx: Ctx):
    from realcheck import steps_close
    d = Path(tempfile.mkdtemp(prefix="halo-jb12-"))
    c = _CloseCtx(d)
    steps_close.one_close(c, "session", "Ctrl+C")
    env = c.envs[0] if c.envs else {}
    ctx.check(f"HALO_CLOSE_TRACE and HALO_INPUT_TRACE name the row's trace file, got {env}",
              env.get("HALO_CLOSE_TRACE") == str(d / "close-trace.txt")
              and env.get("HALO_INPUT_TRACE") == env.get("HALO_CLOSE_TRACE"))


@test
def test_a_row_that_leaves_something_carries_the_trace_and_the_last_screen(ctx: Ctx):
    from realcheck import core, steps_close
    d = Path(tempfile.mkdtemp(prefix="halo-jb12-"))
    f = d / "close-trace.txt"
    f.write_text("1.000 realcheck: sent Ctrl+C\n"
                 "1.001 mono=5.0 pid=7 [MainThread] quit asked\n"
                 "Thread 0x01 (most recent call first):\n"
                 "1.002 realcheck: saw Quit Halo?, sent Enter\n", encoding="utf-8")
    shown = "hello " + "x" * 700 + " Quit Halo? Enter quits, Esc stays"  # Terminal.plain(): control sequences stripped
    ev = steps_close.leftover_evidence(f, shown)
    ctx.check(f"the trace's lines, got {ev['close_trace']}", len(ev["close_trace"]) == 4)
    ctx.check(f"the last screen: its final 600 characters, got {len(ev['last_screen'])} ending "
              f"{ev['last_screen'][-40:]!r}", ev["last_screen"].endswith("Esc stays") and len(ev["last_screen"]) <= 603)
    missing = steps_close.leftover_evidence(d / "none.txt", "")
    ctx.check("no trace file: an empty trace, said as such in the detail", missing["close_trace"] == []
              and "no line" in steps_close._detail(missing))
    row = {"target": "session, background Bash job", "how": "Ctrl+C", "left": ["pid 1 (python.exe) x [s]"], **ev}
    saved = steps_close.one_close, steps_close.serve_alone
    steps_close.one_close = lambda c, target, how: dict(row) if (target, how) == (row["target"], row["how"]) else {
        "target": target, "how": how, "left": []}
    steps_close.serve_alone = lambda c: {"target": "serve", "how": "it returned", "left": []}
    probe = {"delivered": True, "via": "typed", "why": "", "break_works": True}
    try:
        steps_close.closing(mock.Mock(ctrl_c=lambda: probe))
        got = None
    except core.Fail as e:
        got = e
    finally:
        steps_close.one_close, steps_close.serve_alone = saved
    detail = got.detail if got is not None else ""
    ctx.check(f"the row's one-line detail names Halo's last phase and the end of the screen, got {detail!r}",
              "[trace: 1.001 mono=5.0 pid=7 [MainThread] quit asked; screen: " in detail and "Esc stays]" in detail)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
