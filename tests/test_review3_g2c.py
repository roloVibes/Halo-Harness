"""tests.test_review3_g2c -- pins for the 3.0.2.0 review fix pass, round G2
(local catalog), third part:

  * item 136  the managed-server registry lock is never held while a child
              is being signalled, and a lock this call did not create is
              never removed
  * item 137  a managed server is recorded the moment it is spawned and the
              record is removed again when the wait for readiness fails
  * item 138  the models.dev cache (and the two sibling catalogs) is written
              through a pid-suffixed tmp file and os.replace
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once
from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.test_review3_g2 import _tmp

ensure_scoped_state_dir_once()
test, TESTS = new_registry()

_SLEEPER = "import time\ntime.sleep(60)\n"


def _stub(sd: Path) -> Path:
    p = sd / "sleeper.py"
    p.write_text(_SLEEPER, encoding="utf-8")
    return p


def _entry(model, pid, **extra):
    from halo_harness.providers.local_runtime import _owner_fingerprint
    owner_pid, owner_start = _owner_fingerprint()
    return {"model": model, "runtime": "llama-server", "pid": pid, "port": 1, "base_url": "http://127.0.0.1:1/v1",
            "started": "x", "keep": False, "owner_pid": owner_pid, "owner_start": owner_start,
            "proc_start": None, "cmdline": [], **extra}


# ---- item 136 --------------------------------------------------------------

@test
def test_g2_136_sweep_signals_children_without_holding_the_lock(ctx: Ctx):
    from halo_harness.providers import local_runtime as lr
    sd = _tmp("g2-136-")
    lr.save_registry(sd, [_entry("a.gguf", 111), _entry("b.gguf", 222)])
    lock = lr.registry_path(sd).with_name(lr.registry_path(sd).name + ".lock")
    seen = {"lock_while_signalling": [], "terminated": []}
    real = lr._terminate_pid

    def slow_terminate(pid):
        seen["lock_while_signalling"].append(lock.exists())
        seen["terminated"].append(pid)
        if len(seen["terminated"]) == 1:
            # another halo process registers a server while the sweep is mid-shutdown
            lr._upsert_registry_entry(sd, _entry("other.gguf", 333, owner_pid=-5, owner_start="elsewhere"))

    lr._terminate_pid = slow_terminate
    try:
        lr.stop_all_managed_servers_except_kept(state_dir=sd)
    finally:
        lr._terminate_pid = real
    ctx.check(f"both owned pids were signalled, got {seen['terminated']}", sorted(seen["terminated"]) == [111, 222])
    ctx.check(f"the lock file was absent while signalling, got {seen['lock_while_signalling']}",
              seen["lock_while_signalling"] == [False, False])
    left = [e["model"] for e in lr.load_registry(sd)]
    ctx.check(f"the concurrent writer's entry survived, the swept rows are gone, got {left}", left == ["other.gguf"])


@test
def test_g2_136_lock_owned_by_someone_else_is_left_in_place(ctx: Ctx):
    from halo_harness.providers import local_runtime as lr
    sd = _tmp("g2-136b-")
    lock = lr.registry_path(sd).with_name(lr.registry_path(sd).name + ".lock")
    with lr._registry_lock(sd):
        ctx.check("lock file exists while held", lock.exists())
        lock.write_text("someone-else", encoding="ascii")  # stolen and re-created by another process
    ctx.check("a lock this call did not create is not removed", lock.exists())
    lock.unlink()
    with lr._registry_lock(sd):
        pass
    ctx.check("its own lock is removed on exit", not lock.exists())


# ---- item 137 --------------------------------------------------------------

def _start(sd, fake_wait):
    from halo_harness.providers import local_runtime as lr
    real = lr._wait_ready
    lr._wait_ready = fake_wait
    try:
        return lr.start_managed_server(model="m.gguf", runtime="llama-server",
                                       binary_argv=[sys.executable, str(_stub(sd))], model_path="m.gguf", state_dir=sd)
    finally:
        lr._wait_ready = real


@test
def test_g2_137_entry_exists_during_the_wait_and_flips_to_ready(ctx: Ctx):
    from halo_harness.providers import local_runtime as lr
    sd = _tmp("g2-137-")
    during = []

    def fake_wait(base_url, *, timeout, proc):
        during.append(lr.load_registry(sd))
        return True, False

    entry, reason = _start(sd, fake_wait)
    try:
        ctx.check(f"started, reason={reason}", entry is not None)
        rows = during[0]
        ctx.check(f"a provisional row existed mid-wait, got {rows}",
                  len(rows) == 1 and rows[0]["ready"] is False and rows[0]["pid"] == entry.pid)
        after = lr.load_registry(sd)
        ctx.check(f"it is marked ready afterwards, got {after}", len(after) == 1 and after[0]["ready"] is True)
    finally:
        if entry is not None:
            lr._terminate_pid(entry.pid)


@test
def test_g2_137_failed_or_interrupted_wait_removes_the_row_and_the_child(ctx: Ctx):
    from halo_harness.providers import local_runtime as lr
    sd = _tmp("g2-137b-")
    pids = []

    def never_ready(base_url, *, timeout, proc):
        pids.append(proc.pid)
        return False, False

    entry, reason = _start(sd, never_ready)
    ctx.check(f"a timeout reports failure, got {entry} {reason}", entry is None and reason)
    ctx.check("and leaves no row behind", lr.load_registry(sd) == [])

    def interrupted(base_url, *, timeout, proc):
        pids.append(proc.pid)
        raise KeyboardInterrupt()

    raised = False
    try:
        _start(sd, interrupted)
    except KeyboardInterrupt:
        raised = True
    ctx.check("a KeyboardInterrupt still propagates", raised)
    ctx.check("with no row behind", lr.load_registry(sd) == [])
    from halo_harness.bg_run import pid_alive
    import time
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and pid_alive(pids[-1]):
        time.sleep(0.1)
    ctx.check("and the child was terminated", not pid_alive(pids[-1]))


@test
def test_g2_137_stale_dead_row_is_dropped_but_a_live_starting_row_is_kept(ctx: Ctx):
    from halo_harness.providers import local_runtime as lr
    sd = _tmp("g2-137c-")
    proc = subprocess.Popen([sys.executable, "-c", _SLEEPER])
    try:
        lr.save_registry(sd, [_entry("dead", 999999, base_url="http://127.0.0.1:2/v1", ready=False),
                              _entry("live", proc.pid, base_url="http://127.0.0.1:3/v1", ready=False)])
        lr.drop_stale_registry_entry(sd, "dead", "http://127.0.0.1:2/v1")
        lr.drop_stale_registry_entry(sd, "live", "http://127.0.0.1:3/v1")
        ctx.check("only the live starting row remains", [e["model"] for e in lr.load_registry(sd)] == ["live"])
    finally:
        proc.kill()
        proc.wait()


# ---- item 138 --------------------------------------------------------------

@test
def test_g2_138_models_dev_cache_is_replaced_atomically(ctx: Ctx):
    from halo_harness.providers import models_dev
    sd = _tmp("g2-138-")
    old = {"prov": {"models": {"m": {"limit": {"context": 1000}}}}}
    models_dev.write_models_dev_json(sd, old)
    seen = {}
    real_dump = json.dump

    def half_dump(data, f, *a, **kw):
        text = json.dumps(data)
        f.write(text[: len(text) // 2])
        f.flush()
        seen["mid_write_read"] = models_dev.load_models_dev_json(sd)
        raise OSError("disk went away mid-write")

    models_dev.json.dump = half_dump
    try:
        models_dev.write_models_dev_json(sd, {"prov": {"models": {"n": {"x": "y" * 500}}}})
    finally:
        models_dev.json.dump = real_dump
    ctx.check(f"a reader mid-write still gets the previous file, got {seen.get('mid_write_read')}",
              seen.get("mid_write_read") == old)
    ctx.check("and so does one afterwards", models_dev.load_models_dev_json(sd) == old)


@test
def test_g2_138_catalog_writers_use_pid_suffixed_tmp_names(ctx: Ctx):
    from halo_harness.providers import huggingface_catalog, models_dev, openai_catalog
    sd = _tmp("g2-138b-")
    names = []
    real = os.replace

    def spy(src, dst):
        names.append(Path(src).name)
        return real(src, dst)

    os.replace = spy
    try:
        models_dev.write_models_dev_json(sd, {"a": 1})
        openai_catalog.write_oai_models_json(sd, ["gpt-x"])
        huggingface_catalog.write_hf_models_json(sd, [{"id": "org/m", "context_length": 8}])
    finally:
        os.replace = real
    ctx.check(f"three replaces, got {names}", len(names) == 3)
    ctx.check(f"each tmp name carries the pid, got {names}", all(str(os.getpid()) in n for n in names))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
