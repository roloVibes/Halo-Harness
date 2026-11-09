"""The design pack's test runner (house style: `@test` functions, `ctx.check(what, ok)`, an exit code). Each module
starts with:

    from tests.run import PACK, mod, new_registry, main
    home = scratch()                       # this process's own home: before anything of Halo reads one
    test, TESTS = new_registry()
    ...
    if __name__ == "__main__":
        sys.exit(main(TESTS))

`mod("server/store.py")` is one of the pack's modules, imported through its folder as Studio's routes import it.
"""

from __future__ import annotations

import sys
import time
import traceback
from pathlib import Path

PACK = Path(__file__).resolve().parent.parent


class SkipTest(Exception):
    """A test that cannot run here (no Chrome, no node): a skip line, not a failure."""


class Ctx:
    def __init__(self):
        self.failures: "list[str]" = []

    def check(self, what: str, ok) -> bool:
        if not ok:
            self.failures.append(str(what))
        return bool(ok)


def scratch():
    from halo_harness.ext import testing
    return testing.scratch_home("halo-design-tests-")


def mod(rel: str):
    from halo_harness.ext import testing
    return testing.pack_module(PACK, rel)


def new_registry():
    tests: list = []

    def test(fn):
        tests.append(fn)
        return fn
    return test, tests


def main(tests) -> int:
    passed = failed = skipped = 0
    for fn in tests:
        ctx, t0 = Ctx(), time.monotonic()
        try:
            fn(ctx)
        except SkipTest as e:
            skipped += 1
            print(f"[SKIP] {fn.__name__}: {e}")
            continue
        except Exception:
            ctx.failures.append("raised:\n" + traceback.format_exc())
        took = time.monotonic() - t0
        if ctx.failures:
            failed += 1
            print(f"[FAIL] {fn.__name__} ({took:.1f}s)")
            for line in ctx.failures:
                print("    " + line.replace("\n", "\n    "))
        else:
            passed += 1
            print(f"[PASS] {fn.__name__} ({took:.1f}s)")
    print(f"RESULT: {passed + failed + skipped} tests, {passed} passed, {failed} failed" + (f", {skipped} skipped" if skipped else ""))
    sys.stdout.flush()
    return 1 if failed else 0
