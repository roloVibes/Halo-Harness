"""tests.test_jb10_proven_stop -- a process is signalled only when its identity is PROVEN: a start time recorded, a
start time read now, both equal (Halo 3.6.0.0, fix package "jb10", batch 1, item 1).

1. The quit path / `halo stop` / the updater's in-halo stop (children_stop.stop_entry) of a local model server entry:
   with no recorded start time, or with one recorded and an unreadable live one, nothing is signalled.
2. The exit sweep of this process's own managed servers (local_runtime.stop_all_managed_servers_except_kept): an entry
   with no recorded start time and no handle held is not signalled; one this process holds a Popen handle for is.
3. The standalone updater (update_runner._Run.stop): a pid whose start time was unknown when first seen, or cannot be
   read now, is not ended, and a plain line says so; a proven one is.
Every process a test starts is its own and is ended by its own handle; nothing is killed by name.
Run: python -m tests.test_jb10_proven_stop
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

ensure_scoped_state_dir_once()
test, TESTS = new_registry()


def _sleeper() -> subprocess.Popen:
    return subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _end(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        proc.kill()
    proc.wait(10)


def _server_row(model: str, pid: int, proc_start, **extra) -> dict:
    from halo_harness.providers.local_runtime import _owner_fingerprint
    owner_pid, owner_start = _owner_fingerprint()
    return {"model": model, "runtime": "llama-server", "pid": pid, "port": 1, "base_url": "http://127.0.0.1:1/v1",
            "started": "x", "keep": False, "owner_pid": owner_pid, "owner_start": owner_start,
            "proc_start": proc_start, "cmdline": [], "ready": True, **extra}


@test
def test_the_quit_path_never_signals_a_local_server_whose_start_time_is_unknown(ctx: Ctx):
    from halo_harness import bg_run, children_stop
    from halo_harness.providers import local_runtime as lr
    state = Path(tempfile.mkdtemp(prefix="jb10-qp-"))
    proc = _sleeper()
    try:
        time.sleep(0.3)
        # (1) nothing recorded: the ledger entry and the registry row carry no start time
        lr.save_registry(state, [_server_row("m.gguf", proc.pid, None)])
        res = children_stop.stop_entry({"pid": proc.pid, "what": "llama", "source": "local-servers", "model": "m.gguf",
                                        "start_time": None, "cmd": ["llama-server"]}, state_dir=state, timeout=1.0)
        time.sleep(0.3)
        ctx.check(f"no start time recorded: the server is not signalled (said ok={res['ok']})", proc.poll() is None)
        ctx.check("and the result says it is still running", res["ok"] is False)
        # (2) recorded, but the live one cannot be read now (ps failed, access denied)
        rec = bg_run.process_start_time(proc.pid)
        ctx.check(f"the sleeper's start time is readable for the setup, got {rec!r}", rec is not None)
        lr.save_registry(state, [_server_row("m.gguf", proc.pid, rec)])
        with mock.patch.object(bg_run, "process_start_time", lambda pid: None):
            res = children_stop.stop_entry({"pid": proc.pid, "what": "llama", "source": "local-servers",
                                            "model": "m.gguf", "start_time": rec, "cmd": ["llama-server"]},
                                           state_dir=state, timeout=1.0)
        time.sleep(0.3)
        ctx.check(f"a recorded start time and an unreadable live one: not signalled (said ok={res['ok']})",
                  proc.poll() is None)
        # (3) proven: recorded and read now, equal -> it is stopped
        lr.save_registry(state, [_server_row("m.gguf", proc.pid, rec)])
        res = children_stop.stop_entry({"pid": proc.pid, "what": "llama", "source": "local-servers", "model": "m.gguf",
                                        "start_time": rec, "cmd": ["llama-server"]}, state_dir=state, timeout=5.0)
        try:
            proc.wait(5)
        except subprocess.TimeoutExpired:
            pass
        ctx.check(f"a proven server is stopped (said ok={res['ok']}, exit {proc.poll()})", proc.poll() is not None)
    finally:
        _end(proc)
        shutil.rmtree(state, ignore_errors=True)


@test
def test_the_exit_sweep_signals_its_own_server_only_by_handle_or_proof(ctx: Ctx):
    from halo_harness.providers import local_runtime as lr
    state = Path(tempfile.mkdtemp(prefix="jb10-sweep-"))
    lone, held = _sleeper(), _sleeper()
    try:
        time.sleep(0.3)
        lr.save_registry(state, [_server_row("lone.gguf", lone.pid, None), _server_row("held.gguf", held.pid, None)])
        lr._register_popen(held)
        with mock.patch("halo_harness.providers.local_server.exit_sweep", lambda sd: None):
            lr.stop_all_managed_servers_except_kept(state_dir=state)
        time.sleep(0.3)
        ctx.check("an own entry with no start time and no handle held: not signalled", lone.poll() is None)
        ctx.check(f"an own entry whose Popen handle this process holds: stopped by the handle (exit {held.poll()})",
                  held.poll() is not None)
    finally:
        lr._forget_popen(held.pid)
        _end(lone)
        _end(held)
        shutil.rmtree(state, ignore_errors=True)


def _runner(start_fn, alive=(400,)):
    from halo_harness import update_runner as R
    killed, said, clock = [], [], [0.0]
    run = R._Run({}, None, lambda p: p in alive and p not in killed, killed.append,
                 lambda s: clock.__setitem__(0, clock[0] + s), lambda: clock[0], said.append, start_fn, False)
    return run, killed, said


@test
def test_the_updater_ends_a_pid_only_when_its_identity_is_proven(ctx: Ctx):
    run, killed, said = _runner(lambda p: None)
    run.note([400])
    run.stop(400)
    ctx.check(f"start time unknown when first seen and now: not ended, got {killed}", killed == [])
    ctx.check(f"a plain line names it and how to find it, got {said}",
              any("400" in s and "not stopped" in s and "halo ps" in s for s in said))
    looks = {"n": 0}

    def known_then_unreadable(pid):
        looks["n"] += 1
        return "t1" if looks["n"] == 1 else None
    run, killed, said = _runner(known_then_unreadable)
    run.note([400])
    run.stop(400)
    ctx.check(f"known when first seen, unreadable now: not ended, got {killed}", killed == [])
    run, killed, said = _runner(lambda p: "t1")
    run.note([400])
    run.stop(400)
    ctx.check(f"proven (same start time on both looks): ended, got {killed}", killed == [400])
    run, killed, said = _runner(lambda p: None)
    run.note([400])
    ctx.check("waiting stays cautious: an unknown start time still counts as running while the pid lives",
              run.wait_gone([400], 3.0) == [400])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
