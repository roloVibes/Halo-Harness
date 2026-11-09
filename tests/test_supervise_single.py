"""tests.test_supervise_single -- Halo 3.3.13.1 (plans/REVIEW-2026-11.md #16, CORE-2): one supervisor per state
folder. `run_foreground` takes an exclusive lock on `<state>/supervise/supervisor.lock` before it reads the pulse
and holds it for its life (supervise/single.py); a second start exits 1 naming the holder's pid; two started at once
on one scratch home: exactly one runs.
A scratch home; the supervisors run a few short ticks with no feed and no model.
Run: python -m tests.test_supervise_single
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
_SCRUB = ("OPENROUTER", "DATABRICKS", "ANTHROPIC", "BRIDGE", "HALO", "ROLO", "TYPESAFE", "OPENAI")
RUN = ("import sys; from halo_harness.config.paths import bridge_home; from halo_harness.supervise.cli import "
       "run_foreground; sys.exit(run_foreground(bridge_home(), ticks=15, feed=lambda: []))")


class _Home:
    def __enter__(self):
        self.saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
        self.root = Path(tempfile.mkdtemp(prefix="supervise-single-")).resolve()
        self.state = self.root / ".halo"
        self.state.mkdir(parents=True)
        (self.state / "config.json").write_text(json.dumps({"supervise": {"tick_s": 0.2}}), encoding="utf-8")
        os.environ.update(BRIDGE_TEST_HOME=str(self.root), BRIDGE_STATE_DIR=str(self.state))
        return self

    def __exit__(self, *exc):
        for k, v in self.saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)

    def env(self) -> dict:
        env = {k: v for k, v in os.environ.items() if not k.startswith(_SCRUB)}
        env.update(BRIDGE_TEST_HOME=str(self.root), BRIDGE_STATE_DIR=str(self.state), BRIDGE_TEST_NO_BACKGROUND_NET="1",
                   OLLAMA_HOST="http://127.0.0.1:9", HALO_ENV_FILE=str(self.root / "scratch-env"),
                   PYTHONPATH=str(REPO))
        return env


@test
def test_a_second_start_names_the_holder(ctx: Ctx):
    from halo_harness.supervise import single
    from halo_harness.supervise.cli import run_foreground
    with _Home() as h:
        held = single.take(h.state)
        ctx.check("this process holds the lock", held is not None and single.holder(h.state) == os.getpid())
        err, out = io.StringIO(), io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
            rc = run_foreground(h.state, ticks=1, feed=lambda: [])
        ctx.check(f"the second start exits 1 naming the pid, got {rc} {err.getvalue()!r}",
                  rc == 1 and f"pid {os.getpid()}" in err.getvalue() and "goal queue is running" not in out.getvalue())
        single.release(h.state, held)
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            rc = run_foreground(h.state, ticks=1, feed=lambda: [])
        ctx.check(f"once released it runs, and lets go at the end, got {rc}",
                  rc == 0 and single.holder(h.state) is None and single.take(h.state) is not None)


@test
def test_two_started_at_once_exactly_one_runs(ctx: Ctx):
    with _Home() as h:
        procs = [subprocess.Popen([sys.executable, "-c", RUN], cwd=str(h.root), env=h.env(), stdin=subprocess.DEVNULL,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(2)]
        got = [(p.pid,) + tuple(p.communicate(timeout=120)) + (p.returncode,) for p in procs]
        ran = [g for g in got if "the goal queue is running" in g[1]]
        other = [g for g in got if g not in ran]
        ctx.check(f"exactly one ran, got {[(g[3], g[1][-80:], g[2][-160:]) for g in got]}",
                  len(ran) == 1 and ran[0][3] == 0)
        ctx.check(f"the other exited 1 naming its pid, got {other[:1]}",
                  len(other) == 1 and other[0][3] == 1 and f"pid {ran[0][0]}" in other[0][2])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
