"""tests.test_fx_jb15_reaper_leaves -- the closing reaper leaves soon after the Halo it watches (fx jb15, POSIX).

On the owner's Mac a closing_reaper was seen running after its owner had gone. Its rule: after a hard kill of its owner
it does one sweep and exits, within about 3 s when there is nothing left to end and within the closing bound (5 s) when
it had to end something. A real owner (tests/helpers/closing_owner.py) is killed hard and the reaper is timed.
Linux runs macOS's path with HALO_TEST_NO_PROC=1 (identity and liveness from `ps`); the macOS CI leg runs it natively.
Run: python -m tests.test_fx_jb15_reaper_leaves
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _time_the_reaper(ctx: Ctx, kind: str, bound_s: float) -> None:
    if os.name == "nt":
        raise SkipTest("the reaper is POSIX only (Windows: the Job object)")
    from tests.test_closing import _end_tree_we_started, _owner, _same
    tmp = Path(tempfile.mkdtemp(prefix=f"halo-jb15-reaper-{kind}-"))
    kids: list = []
    reaper = proc = None
    try:
        proc, _out, ready = _owner(kind, tmp)
        kids = ready["kids"]
        reaper = ready.get("reaper")
        if reaper is None and kind == "keptmark" and os.path.exists("/proc/self/stat") \
                and os.environ.get("HALO_TEST_NO_PROC") != "1":
            raise SkipTest("Linux with /proc starts no reaper for a kept spawn alone (macOS, and Linux with "
                           "HALO_TEST_NO_PROC=1, start one at the first `ps` look)")
        ctx.check(f"{kind}: the owner started its reaper, got {ready!r}", bool(reaper and reaper.get("start")))
        proc.kill()  # a hard kill: the owner's own closing procedure never runs, the reaper is all there is
        proc.communicate(timeout=15)
        t0 = time.monotonic()
        while time.monotonic() - t0 < 30 and _same(reaper["pid"], reaper["start"]):
            time.sleep(0.05)
        took = time.monotonic() - t0
        ctx.check(f"{kind}: the reaper left {took:.2f} s after its owner was killed (bound {bound_s:.0f} s)",
                  took < bound_s)
        ended = [k["pid"] for k in kids if not _same(k["pid"], k["start"])]
        if kind == "keptmark":
            ctx.check(f"keptmark: the kept daemon still runs, ended {ended}", not ended)
        else:
            ctx.check(f"{kind}: what it had to end is gone, ended {ended} of {[k['pid'] for k in kids]}",
                      len(ended) == len(kids))
    finally:
        if proc is not None and proc.poll() is None:  # a skip or a failed check before the kill: end the owner too
            proc.kill()
            proc.communicate(timeout=15)
        for k in kids + ([reaper] if reaper else []):
            _end_tree_we_started(k["pid"], k["start"])
        shutil.rmtree(tmp, ignore_errors=True)


@test
def test_a_reaper_with_nothing_to_end_leaves_within_3_s(ctx: Ctx):
    """The owner's only child is a daemon kept on purpose (HALO_OWNER=kept-<name>): nothing for the reaper to end."""
    _time_the_reaper(ctx, "keptmark", 3.0)


@test
def test_a_reaper_that_ends_a_child_leaves_within_the_closing_bound(ctx: Ctx):
    """The owner's child is in its ledger (a schedule fire, a model server): the reaper ends it, then leaves."""
    _time_the_reaper(ctx, "ledger", 5.0)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="fx jb15 reaper tests"))
