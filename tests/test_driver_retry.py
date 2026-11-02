"""tests.test_driver_retry -- Halo 3.3.8.1 (the CI addendum, item 12): a Chrome driver retries once, in the open
(tests/helpers/driver_retry.py, chrome_driver.Driver.main, tests/helpers/driver_got.py). No Chrome, no subprocess:
the re-run is a stand-in.

1. which failures are retried: a step's TimeoutError, never an assertion, a setup error, a stand-in Chrome, the second
   run itself, or with HALO_DRIVER_NO_RETRY=1 (a local red stays red);
2. the re-run: a fresh process, a fresh scratch home (BRIDGE_TEST_HOME set to a new one when the driver made its own; never unset), its result with
   `retried: <the first failure>`; a second failure stays a failure, still naming the first;
3. the runner's [PASS] line gains " (driver retried once: <first failure>)" through `ctx.retried` (driver_got.got).
Run: python -m tests.test_driver_retry
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers import driver_retry as DR  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
T = {"failed": "bench: TimeoutError: waited 20s for: !!document.querySelector('[data-testid=bench-row]')"}


@contextlib.contextmanager
def _env(**kv):
    saved = {k: os.environ.get(k) for k in (*kv, DR.OFF, DR.MARK)}
    for k in (DR.OFF, DR.MARK):
        os.environ.pop(k, None)
    os.environ.update({k: v for k, v in kv.items() if v is not None})
    try:
        yield
    finally:
        for k, v in saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


@test
def test_which_failures_are_retried(ctx: Ctx):
    with _env():
        ctx.check("a step's TimeoutError", DR.why(T) == T["failed"])
        ctx.check("not an assertion", DR.why({"failed": "bench: AssertionError: no rows"}) == "")
        ctx.check("not a setup error", DR.why({"failed": "setup: TimeoutError: Chrome did not open"}) == "")
        ctx.check("not a stand-in Chrome", DR.why(T, real_chrome=False) == "")
        ctx.check("not a run that passed", DR.why({"rows": 3}) == "")
    with _env(HALO_DRIVER_NO_RETRY="1"):
        ctx.check("HALO_DRIVER_NO_RETRY=1: off, the red stays red", DR.why(T) == "" and DR.after(T, own_home=True) is T)
    with _env(HALO_DRIVER_RETRY_OF="x"):
        ctx.check("the second run never retries", DR.why(T) == "")


@test
def test_the_rerun_is_fresh_and_says_so(ctx: Ctx):
    seen: dict = {}

    def fake_run(argv, **kw):
        seen.update(argv=argv, env=kw["env"])
        return SimpleNamespace(returncode=0, stdout="noise\n" + json.dumps({"rows": 3}) + "\n", stderr="")
    saved = DR.subprocess.run
    DR.subprocess.run = fake_run
    try:
        with _env(BRIDGE_TEST_HOME=os.environ.get("BRIDGE_TEST_HOME") or "x"), contextlib.redirect_stdout(io.StringIO()) as out, \
                contextlib.redirect_stderr(io.StringIO()) as err:
            got = DR.after(dict(T), own_home=True)
        ctx.check(f"the second result with `retried`, got {got}", got == {"rows": 3, "retried": T["failed"]})
        ctx.check("a fresh process with the mark and no inherited home", seen["argv"][0] == sys.executable
                  and seen["env"][DR.MARK] == T["failed"]
                  and seen["env"].get("BRIDGE_TEST_HOME") not in (None, "", os.environ.get("BRIDGE_TEST_HOME"))
                  and "BRIDGE_STATE_DIR" not in seen["env"])  # a fresh scratch home, never the real one
        ctx.check("in the open: the stderr line, the child's other stdout", "retried once after: bench: TimeoutError" in err.getvalue()
                  and out.getvalue() == "noise\n")
        DR.subprocess.run = lambda argv, **kw: SimpleNamespace(returncode=1, stdout=json.dumps({"failed": "bench: TimeoutError: again"}),
                                                               stderr="")
        with _env(), contextlib.redirect_stderr(io.StringIO()):
            again = DR.after(dict(T), own_home=False)
        ctx.check(f"a second timeout fails as today, naming the first, got {again}", again["failed"] == "bench: TimeoutError: again"
                  and again["retried"] == T["failed"])
    finally:
        DR.subprocess.run = saved


@test
def test_the_pass_line_says_the_driver_retried(ctx: Ctx):
    from tests.helpers import runner
    inner = Ctx()
    reg_test, reg = runner.new_registry()

    @reg_test
    def test_reads_the_second_result(c):
        c.retried = T["failed"]
        c.check("fine", True)
    results, passed, failed, _s = run_all(reg, inner)
    ctx.check(f"PASS with the suffix, got {results}", passed == 1 and failed == 0
              and results[0][2] == "driver retried once: " + T["failed"])
    with contextlib.redirect_stdout(io.StringIO()) as out:
        print_results(results, passed, failed, 0)
    ctx.check(f"the printed line, got {out.getvalue().splitlines()[0]!r}",
              out.getvalue().splitlines()[0].endswith(f"({'driver retried once: ' + T['failed']})"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
