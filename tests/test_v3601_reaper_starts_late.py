"""tests.test_v3601_reaper_starts_late -- Halo's own `ps` identity look is not a spawn (3.6.0.1, macOS).

Where there is no /proc (macOS; Linux with HALO_TEST_NO_PROC=1) every start time is a `ps` look, and that look went
through subprocess_safe.run, which counted it as a spawn: closing.install()'s first look started the closing reaper
and marked the Halo as "spawned", so every macOS Halo -- `halo ps`, `halo stop` with nothing to stop, any read-only
command -- started a reaper and ran the close-time marker scan with nothing to find. The look now passes a
subprocess_safe.Probe environment: a bounded read-only look of Halo's own, never a spawn. Every other run still counts
(the reaper also ends children that are in no ledger).
Run: python -m tests.test_v3601_reaper_starts_late
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


@test
def test_a_probe_run_is_not_a_spawn_and_a_plain_run_is(ctx: Ctx):
    """subprocess_safe.run with a Probe environment does not call closing.note_spawn; the same run with a plain
    environment does (control)."""
    from halo_harness import closing, subprocess_safe
    probe = getattr(subprocess_safe, "Probe", None)
    ctx.check("subprocess_safe has a Probe environment type", isinstance(probe, type))
    calls: list = []
    with mock.patch.object(closing, "note_spawn", lambda: calls.append("note_spawn")):
        if isinstance(probe, type):
            subprocess_safe.run([sys.executable, "-c", "pass"], env=probe(os.environ), capture_output=True, timeout=30)
        ctx.check(f"a probe run counts as no spawn, got {calls}", not calls)
        calls.clear()
        subprocess_safe.run([sys.executable, "-c", "pass"], env=dict(os.environ), capture_output=True, timeout=30)
        ctx.check(f"a plain run still counts as a spawn, got {calls}", calls == ["note_spawn"])


@test
def test_the_ps_identity_look_passes_a_probe(ctx: Ctx):
    """bg_run._ps_look (the start time / state look where there is no /proc) runs `ps` with a Probe environment."""
    from halo_harness import bg_run, subprocess_safe
    seen: dict = {}

    def fake_run(argv, **kw):
        seen.update(argv=list(argv), env=kw.get("env"))
        return SimpleNamespace(stdout="Ss   Mon Oct  5 10:00:00 2026\n", returncode=0)
    bg_run._PS_SEEN.clear()
    try:
        with mock.patch.object(bg_run.subprocess, "run", fake_run):
            bg_run._ps_look(4242)
    finally:
        bg_run._PS_SEEN.clear()
    probe = getattr(subprocess_safe, "Probe", None)
    ctx.check(f"the look ran ps, got {seen.get('argv')!r}", (seen.get("argv") or [""])[0] == "ps")
    ctx.check(f"its environment is a Probe, got {type(seen.get('env')).__name__}",
              isinstance(probe, type) and isinstance(seen.get("env"), probe))
    ctx.check("the look still reads C locale text in UTC",
              (seen.get("env") or {}).get("LC_ALL") == "C" and (seen.get("env") or {}).get("TZ") == "UTC0")


_CHILD = r'''
import json, os, sys
from halo_harness import closing
from halo_harness import subprocess_safe

def state():
    r = closing._STATE.get("reaper")
    return {"reaper": hasattr(r, "pid"), "spawned": bool(closing._STATE.get("spawned"))}

closing.install()
print(json.dumps(state()), flush=True)
p = subprocess_safe.Popen(["sleep", "30"], stdin=subprocess_safe.DEVNULL, stdout=subprocess_safe.DEVNULL,
                          stderr=subprocess_safe.DEVNULL)
try:
    print(json.dumps(state()), flush=True)
finally:
    p.kill()
    p.wait(timeout=10)
closing.close()
'''


@test
def test_a_halo_that_starts_nothing_starts_no_reaper(ctx: Ctx):
    """A fresh interpreter installs the closing procedure as a real `halo` does (with the start sweep): no reaper and
    not "spawned"; its first real child starts the reaper. POSIX; Linux takes the macOS path with HALO_TEST_NO_PROC=1,
    the macOS CI leg runs it natively."""
    if os.name == "nt":
        raise SkipTest("the reaper is POSIX only (Windows: the Job object)")
    tmp = Path(tempfile.mkdtemp(prefix="halo-v3601-reaper-late-"))
    try:
        env = {k: v for k, v in os.environ.items() if not k.startswith(("HALO_", "BRIDGE_"))}
        env.update(BRIDGE_TEST_HOME=str(tmp / "home"), BRIDGE_TEST_NO_BACKGROUND_NET="1", PYTHONPATH=str(REPO),
                   HALO_NO_UPDATER="1", OLLAMA_HOST="http://127.0.0.1:9", HALO_TEST_NO_PROC="1")
        r = subprocess.run([sys.executable, "-c", _CHILD], capture_output=True, text=True, timeout=60, cwd=str(tmp),
                           env=env)
        lines = [json.loads(ln) for ln in (r.stdout or "").splitlines() if ln.startswith("{")]
        ctx.check(f"the child ran, rc {r.returncode}: {(r.stderr or '')[-400:]}", r.returncode == 0 and len(lines) == 2)
        if len(lines) != 2:
            return
        ctx.check(f"after install(): no reaper, not spawned, got {lines[0]}",
                  lines[0] == {"reaper": False, "spawned": False})
        ctx.check(f"after the first real child: a reaper, spawned, got {lines[1]}",
                  lines[1] == {"reaper": True, "spawned": True})
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="v3601 reaper starts late"))
