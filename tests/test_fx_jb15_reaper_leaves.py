"""tests.test_fx_jb15_reaper_leaves -- the closing reaper leaves soon after the Halo it watches (fx jb15, POSIX).

On the owner's Mac a closing_reaper was seen running after its owner had gone. Its rule: after a hard kill of its owner
it does one sweep and exits, within about 3 s when there is nothing left to end and within the closing bound (5 s) when
it had to end something; a kept spawn alone starts no reaper at all (3.6.0.1), and a reaper that runs beside a kept
daemon spares it, after a hard kill and after a normal close (3.6.0.1). A real owner (tests/helpers/closing_owner.py) is killed hard and the reaper is timed.
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
        ctx.check(f"{kind}: the owner started its reaper, got {ready!r}", bool(reaper and reaper.get("start")))
        proc.kill()  # a hard kill: the owner's own closing procedure never runs, the reaper is all there is
        proc.communicate(timeout=15)
        t0 = time.monotonic()
        while time.monotonic() - t0 < 30 and _same(reaper["pid"], reaper["start"]):
            time.sleep(0.05)
        took = time.monotonic() - t0
        ctx.check(f"{kind}: the reaper left {took:.2f} s after its owner was killed (bound {bound_s:.0f} s)",
                  took < bound_s)
        print(f"  {kind}: the reaper left {took:.2f} s after its owner was killed", flush=True)
        ended = [k["pid"] for k in kids if not _same(k["pid"], k["start"])]
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
    """The owner's only child exited before the hard kill: the reaper started, and there is nothing for it to end."""
    _time_the_reaper(ctx, "shortchild", 3.0)


@test
def test_a_kept_spawn_alone_starts_no_reaper(ctx: Ctx):
    """The owner's only child is a daemon kept on purpose (HALO_OWNER=kept-<name>): no reaper starts (3.6.0.1: the
    `ps` identity look is no spawn, so on macOS too), and a hard kill of the owner leaves the daemon running."""
    if os.name == "nt":
        raise SkipTest("the reaper is POSIX only (Windows: the Job object)")
    from tests.test_closing import _end_tree_we_started, _owner, _same
    tmp = Path(tempfile.mkdtemp(prefix="halo-jb15-reaper-keptmark-"))
    kids: list = []
    reaper = proc = None
    try:
        proc, _out, ready = _owner("keptmark", tmp)
        kids = ready["kids"]
        reaper = ready.get("reaper")
        ctx.check(f"keptmark: no reaper started, got {reaper!r}", reaper is None)
        proc.kill()
        proc.communicate(timeout=15)
        ended = [k["pid"] for k in kids if not _same(k["pid"], k["start"])]
        ctx.check(f"keptmark: the kept daemon still runs, ended {ended}", bool(kids) and not ended)
    finally:
        if proc is not None and proc.poll() is None:
            proc.kill()
            proc.communicate(timeout=15)
        for k in kids + ([reaper] if reaper else []):
            _end_tree_we_started(k["pid"], k["start"])
        shutil.rmtree(tmp, ignore_errors=True)


def _kept_beside_a_reaper(ctx: Ctx, hard: bool) -> None:
    """3.6.0.1 (reaper batch 3): a reaper runs NEXT TO a kept daemon (the owner kind `keptmix`: a short non-kept
    child first, so the reaper starts, then a daemon with HALO_OWNER=kept-<name>). `hard`: the owner is killed and
    the reaper's sweep runs; else the owner closes normally and its close-time marker scan runs. Either way the kept
    daemon is still running afterwards."""
    if os.name == "nt":
        raise SkipTest("the reaper and the marker scan are POSIX only (Windows: the Job object)")
    from tests.test_closing import _end_tree_we_started, _owner, _same
    tmp = Path(tempfile.mkdtemp(prefix=f"halo-jb15-keptmix-{'hard' if hard else 'close'}-"))
    kids: list = []
    reaper = proc = None
    try:
        proc, out, ready = _owner("keptmix", tmp)
        kids = ready["kids"]
        reaper = ready.get("reaper")
        ctx.check(f"keptmix: a reaper runs beside the kept daemon, got {ready!r}",
                  bool(reaper and reaper.get("start")) and bool(kids))
        if hard:
            proc.kill()
            proc.communicate(timeout=15)
        else:
            (out / "quit").write_text("", encoding="utf-8")
            proc.communicate(timeout=60)
            ctx.check(f"keptmix: the owner closed normally, exit {proc.returncode}", proc.returncode == 0)
        t0 = time.monotonic()
        while reaper and time.monotonic() - t0 < 30 and _same(reaper["pid"], reaper["start"]):
            time.sleep(0.05)
        ctx.check("keptmix: the reaper is gone (its sweep done, or ended by the close)",
                  not (reaper and _same(reaper["pid"], reaper["start"])))
        ended = [k["pid"] for k in kids if not _same(k["pid"], k["start"])]
        ctx.check(f"keptmix: the kept daemon still runs after the {'reaper' if hard else 'close'}, ended {ended}",
                  bool(kids) and not ended)
    finally:
        if proc is not None and proc.poll() is None:
            proc.kill()
            proc.communicate(timeout=15)
        for k in kids + ([reaper] if reaper else []):
            _end_tree_we_started(k["pid"], k["start"])
        shutil.rmtree(tmp, ignore_errors=True)


@test
def test_a_reapers_sweep_after_a_hard_kill_spares_a_kept_daemon(ctx: Ctx):
    _kept_beside_a_reaper(ctx, hard=True)


@test
def test_a_normal_close_with_a_reaper_running_spares_a_kept_daemon(ctx: Ctx):
    _kept_beside_a_reaper(ctx, hard=False)


@test
def test_a_reaper_that_ends_a_child_leaves_within_the_closing_bound(ctx: Ctx):
    """The owner's child is in its ledger (a schedule fire, a model server): the reaper ends it, then leaves."""
    _time_the_reaper(ctx, "ledger", 5.0)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="fx jb15 reaper tests"))
