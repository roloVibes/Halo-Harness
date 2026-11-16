"""tests.test_studio_launch_door -- how `halo init` / `halo setup` / `halo studio --edit` start a Studio
(studio/launch.launch_detached), 3.6.0.0 fix pass:
1. a Studio behind a launcher (an installed Halo's python.exe on Windows runs the interpreter as its child) is in the
   ledger by the pid studio.json names, so the close asks its own shutdown route: no 3 s stall and hard kill, no
   studio.json left, one `halo ps` row (tests/helpers/studio_door_probe.py, a real Studio in a scratch home);
2. a Studio that gives no address in time is stopped with its ledger row (it is not left starting behind the
   terminal setup), and the door waits 45 s by default (the macOS CI runner's fresh Studio took ~35 s);
3. Studio's and bridge's servers bind without a reverse name lookup (HTTPServer.server_bind's socket.getfqdn).
Every process a test starts uses a scratch home and is ended by pid; nothing is killed by name.
Run: python -m tests.test_studio_launch_door
"""
from __future__ import annotations

import inspect
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
PROBE = REPO / "tests" / "helpers" / "studio_door_probe.py"
SCRUB = ("OPENROUTER_", "DATABRICKS_", "ANTHROPIC_", "BRIDGE_", "HALO_", "ROLO_CLAUDE_", "TYPESAFE_", "OPENAI_",
         "PACKS_TEST_")


def _env(home: Path) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith(SCRUB)}
    env.update(BRIDGE_TEST_HOME=str(home), BRIDGE_TEST_NO_BACKGROUND_NET="1", PYTHONPATH=str(REPO),
               PYTHONIOENCODING="utf-8", HALO_NO_BROWSER="1", HALO_NO_UPDATER="1", OLLAMA_HOST="http://127.0.0.1:9")
    return env


@test
def test_a_studio_behind_a_launcher_is_closed_by_its_own_shutdown_route(ctx: Ctx):
    tmp = Path(tempfile.mkdtemp(prefix="halo-door-launcher-"))
    home, out = tmp / "home", tmp / "out"
    home.mkdir()
    out.mkdir()
    proc = subprocess.run([sys.executable, str(PROBE), str(out)], env=_env(home), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=180)
    got = json.loads((out / "probe.json").read_text(encoding="utf-8")) if (out / "probe.json").is_file() else {}
    ctx.check(f"Studio started behind the launcher, got rc {proc.returncode} {got} {proc.stderr[-400:]!r}",
              got.get("url") is True)
    if not got.get("url"):
        return
    ledger = got.get("ledger") or []
    ctx.check(f"one ledger row, by the pid studio.json names, the launcher's kept beside it; got {ledger} vs "
              f"{got.get('studio_pid')}", len(ledger) == 1 and ledger[0]["pid"] == got["studio_pid"]
              and isinstance(ledger[0].get("launcher_pid"), int) and ledger[0]["launcher_pid"] != got["studio_pid"])
    ctx.check(f"`halo ps` shows one Studio, got {got.get('ps_studio_rows')}", got.get("ps_studio_rows") == 1)
    ctx.check(f"the close took Studio's own route: quick, nothing answers, studio.json gone; got {got}",
              got.get("close_s", 99) < 2.5 and got.get("port_answers_after") is False
              and got.get("studio_json_after") is False)


@test
def test_a_studio_that_gives_no_address_is_stopped_with_its_row(ctx: Ctx):
    from halo_harness import children, selfexec
    from halo_harness.studio import launch
    state = Path(tempfile.mkdtemp(prefix="halo-door-slow-")) / ".halo"
    state.mkdir(parents=True)
    pidfile = state.parent / "slow.pid"
    saved = selfexec.python_argv
    slow = ("import os, sys, time; open(sys.argv[1], 'w').write(str(os.getpid())); "
            "print('starting...', flush=True); time.sleep(120)")
    selfexec.python_argv = lambda *a, **k: [sys.executable, "-c", slow, str(pidfile)]
    try:
        t0 = time.monotonic()
        url = launch.launch_detached("setup", cwd=state, state_dir=state, open_browser=False, timeout=3)
        took = time.monotonic() - t0
        why = launch.failure_line()
    finally:
        selfexec.python_argv = saved
    pid = int(pidfile.read_text()) if pidfile.is_file() else None
    ctx.check(f"no URL, and why, got {url!r} {why!r} after {took:.1f}s", url == "" and "within 3 s" in why)
    deadline = time.time() + 5
    while pid and children.pid_running(pid) and time.time() < deadline:
        time.sleep(0.1)
    alive = bool(pid) and children.pid_running(pid)
    if alive:  # never leave it running, whatever the check says (ours, by pid)
        from halo_harness.children_stop import terminate
        terminate(pid, timeout=2.0)
    ctx.check(f"the Studio that gave no address is not left running (pid {pid})", pid is not None and not alive)
    rows = [e for e in children.load(state) if e.get("what") == "studio"]
    ctx.check(f"and its ledger row is gone, got {rows}", rows == [])


@test
def test_the_door_waits_long_enough_for_a_slow_first_start(ctx: Ctx):
    from halo_harness.studio import edit_open, launch, setup_door
    for fn in (launch.launch_detached, setup_door.open_setup, edit_open.open_edit):
        t = inspect.signature(fn).parameters["timeout"].default
        ctx.check(f"{fn.__module__}.{fn.__name__} waits {t} s by default (>= 45)", t >= 45.0)


@test
def test_studio_and_bridge_bind_without_a_reverse_name_lookup(ctx: Ctx):
    import socket
    asked: list = []
    real = socket.getfqdn
    socket.getfqdn = lambda name="": asked.append(name) or real(name)
    try:
        from halo_harness.studio import server as S
        tmp = Path(tempfile.mkdtemp(prefix="halo-door-bind-"))
        srv = S._Server(("127.0.0.1", 0), S.Handler, token="t", cwd=tmp, state_dir=tmp)
        port = srv.server_address[1]
        ctx.check(f"Studio's server asked no name lookup, got {asked}", asked == [])
        ctx.check(f"and still names itself, got {srv.server_name!r}:{srv.server_port}",
                  srv.server_name == "127.0.0.1" and srv.server_port == port)
        srv.server_close()
        import bridge
        b = bridge._Server(("127.0.0.1", 0), bridge.Handler)
        ctx.check(f"bridge's server asked no name lookup, got {asked}", asked == [])
        b.server_close()
    finally:
        socket.getfqdn = real


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
