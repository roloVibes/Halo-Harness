"""tests.test_fx_jb5_ps_identity -- process identity where there is no /proc (macOS), 3.6.0.0 fx jb5.

On macOS every start time and every liveness check is a `ps` look, and since subprocess_safe.run counts as a spawn
(lifecycle fx batch 3) the first look inside closing.install() started the reaper -- before install had put this
process's own id in HALO_OWNER, so the reaper of a nested halo or a sub-agent carried the PARENT's marker: a hard
kill ended the parent's things and left its own running, and a reaper of a root given a stale marker ended the next
halo that inherited that marker. The macOS CI leg showed it as three red closing tests.

HALO_TEST_NO_PROC=1 makes Linux take the macOS path (bg_run.no_proc); these tests run on every POSIX system.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()

_CHILD = r'''
import json, os, sys
from halo_harness import closing, subprocess_safe
closing.install(sweep_at_start=False)
# 3.6.0.1: the `ps` identity look is no spawn, so install() alone starts no reaper; one real child starts it
subprocess_safe.run([sys.executable, "-c", "pass"], capture_output=True, timeout=30)
proc = closing._STATE.get("reaper")
argv = list(proc.args) if proc else []
out = {"me": closing.my_ident(), "env_marker": os.environ.get("HALO_OWNER"), "reaper_argv": argv}
closing._stop_reaper()
print(json.dumps(out))
'''


def _posix_env(home: Path, **extra) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HALO_", "BRIDGE_"))}
    env.update(BRIDGE_TEST_HOME=str(home), BRIDGE_TEST_NO_BACKGROUND_NET="1", PYTHONPATH=str(REPO),
               HALO_NO_UPDATER="1", OLLAMA_HOST="http://127.0.0.1:9", HALO_TEST_NO_PROC="1", **extra)
    return env


@test
def test_a_reaper_carries_this_halos_own_id_never_an_inherited_one(ctx: Ctx):
    """A halo that inherited another's HALO_OWNER (a nested halo, a sub-agent, a tmux pane) starts its reaper with
    ITS OWN id, in argv and in the reaper's environment (the first real child after install() starts it; until
    3.6.0.1 macOS's first `ps` look inside install() did). Red before the fix: the reaper got the inherited marker."""
    if os.name == "nt":
        raise SkipTest("the reaper is POSIX only (Windows: the Job object)")
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="halo-jb5-reaper-"))
    inherited = "1-0123456789"
    r = subprocess.run([sys.executable, "-c", _CHILD], capture_output=True, text=True, timeout=60, cwd=str(tmp),
                       env=_posix_env(tmp / "home", HALO_OWNER=inherited))
    lines = [ln for ln in (r.stdout or "").splitlines() if ln.startswith("{")]
    ctx.check(f"the child ran, got rc {r.returncode}: {(r.stderr or '')[-400:]}", r.returncode == 0 and lines)
    if not lines:
        return
    got = json.loads(lines[-1])
    argv = got["reaper_argv"]
    ctx.check(f"a reaper started, argv {argv!r}", len(argv) >= 7)
    if len(argv) >= 7:
        ctx.check(f"the reaper's marker is this halo's own id {got['me']!r}, got {argv[6]!r}",
                  argv[6] == got["me"] and argv[6] != inherited)
    ctx.check("what this halo starts carries its own id", got["env_marker"] == got["me"])


@test
def test_a_reapers_environment_names_its_owner_not_the_inherited_marker(ctx: Ctx):
    """In-process: ensure_reaper while os.environ still holds an inherited marker (install's first `ps`) gives the
    reaper this process's id in argv and in its environment."""
    if os.name == "nt":
        raise SkipTest("the reaper is POSIX only (Windows: the Job object)")
    from halo_harness import closing
    me = closing.my_ident()  # read before Popen is replaced (macOS: a `ps` look)
    seen: dict = {}

    def fake_popen(argv, **kw):
        seen.update(argv=list(argv), env=dict(kw.get("env") or {}))
        return SimpleNamespace(pid=0, kill=lambda: None, wait=lambda timeout=None: 0)
    saved = dict(closing._STATE)
    with mock.patch.dict(os.environ, {"HALO_OWNER": "1-0123456789"}), mock.patch("subprocess.Popen", fake_popen):
        closing._STATE.update(reaper=None, closed=False)
        try:
            closing.ensure_reaper()
        finally:
            closing._STATE.clear()
            closing._STATE.update(saved)
    ctx.check(f"argv marker is {me!r}, got {seen.get('argv', [None] * 7)[6]!r}", seen.get("argv", [None] * 7)[6] == me)
    ctx.check(f"env marker is {me!r}, got {seen.get('env', {}).get('HALO_OWNER')!r}",
              seen.get("env", {}).get("HALO_OWNER") == me)


@test
def test_a_ps_start_time_is_one_form_whatever_the_columns(ctx: Ctx):
    """`ps -o stat= -o lstart=` (one look for both): the start time is the five lstart fields, the day's padding
    collapsed -- with a state column (the real output), with none, and with macOS's space-padded day."""
    from halo_harness import bg_run
    for out, want_stat in (("Ss   Mon Oct  5 10:00:00 2026\n", "Ss"), ("Mon Oct  5 10:00:00 2026\n", ""),
                           ("S+     Mon Oct  5 10:00:00 2026\n", "S+")):
        bg_run._PS_SEEN.clear()
        with mock.patch.object(bg_run.subprocess, "run",
                               lambda *a, _o=out, **kw: SimpleNamespace(stdout=_o, returncode=0)):
            stat, start = bg_run._ps_look(4242)
        ctx.check(f"{out!r}: start {start!r}", start == "Mon Oct 5 10:00:00 2026")
        ctx.check(f"{out!r}: state {stat!r}", stat == want_stat)
    bg_run._PS_SEEN.clear()


@test
def test_the_same_process_read_twice_through_ps_proves_equal(ctx: Ctx):
    """On the no-/proc path the start time of one live process read twice (fresh each time) is equal, and the proof
    a signal needs holds; a different start time does not."""
    if os.name == "nt":
        raise SkipTest("POSIX ps path")
    from halo_harness import bg_run, children
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        with mock.patch.dict(os.environ, {"HALO_TEST_NO_PROC": "1"}):
            first = bg_run.process_start_time(child.pid)
            bg_run.ps_forget(child.pid)
            time.sleep(0.2)
            second = bg_run.process_start_time(child.pid)
            ctx.check(f"a ps start time, got {first!r}", isinstance(first, str) and first.startswith("ps:"))
            ctx.check(f"read twice it is equal: {first!r} / {second!r}", first == second)
            ctx.check("provably the same process", children.provably_same(child.pid, first))
            ctx.check("another start time is not", not children.provably_same(child.pid, "ps:Thu Jan 1 00:00:00 1970"))
    finally:
        child.kill()
        child.wait(timeout=10)
        bg_run._PS_SEEN.clear()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
