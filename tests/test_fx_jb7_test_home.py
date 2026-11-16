"""tests.test_fx_jb7_test_home -- 3.6.0.0 fx jb7: a test whose teardown pops the home it set never leaves the
module's later tests on the real `~/.halo`.

CI's Linux shard 3 passed every test and failed its real-state guard ("~/.halo did not exist before this run and
does now"): test_w6a_release_fixes' `_end` popped BRIDGE_TEST_HOME (the run's per-module home with it), and a later
test of that module ran a connector command through tools._proc.run_streamed, whose shell-ledger row
(children.register -> bridge_home()/run/children.json) then landed under the real home. The runner now gives a test
that ends with no state-dir variable set the one it found."""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


@test
def test_a_test_that_pops_the_home_leaves_the_next_test_on_the_home_it_was_given(ctx: Ctx):
    from halo_harness import children
    given = Path(tempfile.mkdtemp(prefix="fx-jb7-given-"))
    seen = {}

    def pops_its_home(_ctx):  # test_w6a_release_fixes' _end, before this fix
        os.environ["BRIDGE_TEST_HOME"] = str(given / "its-own")
        os.environ.pop("BRIDGE_TEST_HOME", None)

    def runs_later(_ctx):
        seen["home"] = os.environ.get("BRIDGE_TEST_HOME")
        seen["ledger"] = children.registry_path()

    try:
        with mock.patch.dict(os.environ, {"BRIDGE_TEST_HOME": str(given)}):
            os.environ.pop("BRIDGE_STATE_DIR", None)
            run_all([("pops", pops_its_home), ("later", runs_later)], Ctx())
        ctx.check(f"the later test runs on the home the module was given, got {seen.get('home')!r}",
                  seen.get("home") == str(given))
        ledger = Path(str(seen.get("ledger")))
        ctx.check(f"the shell ledger it would write is under that home, not the real one: {ledger}",
                  given in ledger.parents)
    finally:
        shutil.rmtree(given, ignore_errors=True)


@test
def test_a_test_that_sets_another_home_keeps_it(ctx: Ctx):
    given = tempfile.mkdtemp(prefix="fx-jb7-given-")
    other = tempfile.mkdtemp(prefix="fx-jb7-other-")
    seen = {}
    try:
        with mock.patch.dict(os.environ, {"BRIDGE_TEST_HOME": given}):
            os.environ.pop("BRIDGE_STATE_DIR", None)
            run_all([("sets", lambda _c: os.environ.__setitem__("BRIDGE_STATE_DIR", other)),
                     ("later", lambda _c: seen.update(state=os.environ.get("BRIDGE_STATE_DIR")))], Ctx())
        ctx.check(f"a home a test leaves set is not overwritten, got {seen}", seen.get("state") == other)
    finally:
        shutil.rmtree(given, ignore_errors=True)
        shutil.rmtree(other, ignore_errors=True)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
