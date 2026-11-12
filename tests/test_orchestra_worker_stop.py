"""tests.test_orchestra_worker_stop -- a worker's "STOP: none" is no stop (Halo 3.3.15.0; rolo's Kali finding
f-20261109-9f7492: a worker answering "did STOP WHEN apply? no" with the literal STOP: prefix killed its lane and its
dependents). orchestra/worker_stop.py; the prompt line in orchestra/workers.py says to write no STOP line at all.
Run: python -m tests.test_orchestra_worker_stop
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


@test
def test_a_real_stop_is_read(ctx: Ctx):
    from halo_harness.orchestra.worker_stop import stop_line
    ctx.check("the reason is returned", stop_line("done with part 1\nSTOP: no provider configured") == "no provider configured")
    ctx.check("a bare STOP: is the worker stopping", stop_line("STOP:") == "the worker stopped")
    ctx.check("case and indent do not matter", stop_line("  stop: budget: $4.00 hit") == "budget: $4.00 hit")
    ctx.check("no line, no stop", stop_line("all written, tests pass") is None)


@test
def test_a_negation_is_no_stop(ctx: Ctx):
    from halo_harness.orchestra.worker_stop import is_no_stop, stop_line
    for reply in ("STOP: none -- my unit is written; tests pass.",
                  "STOP: not applicable (add_item piece returned once, job complete)",
                  "STOP: n/a", "STOP: No.", "STOP: does not apply", "STOP: nothing to stop for", "STOP: not needed"):
        ctx.check(f"{reply!r} is no stop", stop_line(reply) is None)
    ctx.check("a reason that only starts like a negation word still stops",
              stop_line("STOP: nonexistent file basket.py") == "nonexistent file basket.py")
    ctx.check("'nothing' as a word, not a prefix", is_no_stop("nothing") and not is_no_stop("nothingness broke"))
    ctx.check("a negation line is skipped and a later real stop still read",
              stop_line("STOP: none\nSTOP: the repo is read-only") == "the repo is read-only")
    ctx.check("'no' alone is no stop; 'no provider configured' is one",
              is_no_stop("no") and is_no_stop("No.") and stop_line("STOP: no provider configured") == "no provider configured")


@test
def test_the_workers_module_and_prompt_carry_it(ctx: Ctx):
    from halo_harness.orchestra import workers
    from halo_harness.orchestra.worker_stop import stop_line as fn
    ctx.check("workers.stop_line is worker_stop.stop_line", workers.stop_line is fn)

    class Job:
        id, title, claims = "job-1", "Implement add_item", ("basket.py#add_item",)

    class Lane:
        n, job = 1, Job()

    class Goal:
        what, done_when, stop_when, test = "a basket", "tests pass", "the repo is read-only", ""

    text = workers.worker_prompt(Goal(), Lane())
    ctx.check("the prompt says to write no STOP line when it does not apply",
              "write no STOP line at all" in text and '"STOP: none"' in text)
    # 3.4.1.1 (58): two workers each ran the joint test in their own worktree, called it "the gate" and stopped the run
    Goal.stop_when, Goal.test = "the gate fails twice", "python -m unittest"
    text = workers.worker_prompt(Goal(), Lane())
    ctx.check("the worker's own test runs are not the gate, and the gate's failures are the run's to count",
              "Running it in your worktree is not the gate" in text and "a failure from a unit you do not hold is not yours" in text
              and "is the run's to count, never your own test runs" in text)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
