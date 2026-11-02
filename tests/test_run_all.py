"""tests.test_run_all -- Halo 3.3.8.1 (the CI addendum, item 11): tests/run_all.py's shards
(tests/helpers/run_all_support.py): `--shard i/n` runs the modules whose index in the sorted discovered list is i
mod n, composing with `--fast` / `--tier`; `--shard-of tests.test_x` prints its shard. Nothing here runs a module.

1. four shards cover every discovered module exactly once, each about a quarter, the same split on every runner;
2. a tier composes: the fast shard is the fast modules of that shard;
3. `--shard-of`: the shard that runs a module, with or without the `tests.` prefix, `--shards n`; an unknown name;
4. the flags: `--shard 2/4`, `--shard=2/4`, a bad shard, a bad count -> exit 2 with one line.
Run: python -m tests.test_run_all
"""
from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers import run_all_support as S  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _every() -> list:
    import tests.run_all as R
    return R.discover_test_modules()


@test
def test_four_shards_cover_every_module_once(ctx: Ctx):
    every = _every()
    parts = [S.select_shard(every, (i, 4), every) for i in range(4)]
    flat = [m for p in parts for m in p]
    ctx.check(f"every module once, got {len(flat)} of {len(every)}", sorted(flat) == sorted(every) and len(set(flat)) == len(flat))
    sizes = [len(p) for p in parts]
    ctx.check(f"about a quarter each, got {sizes}", max(sizes) - min(sizes) <= 1)
    ctx.check("the same split from any order of the list", S.select_shard(list(reversed(every)), (2, 4), every)
              == list(reversed(parts[2])))
    ctx.check("no shard: every module, unchanged", S.select_shard(every, None) == every)
    ctx.check("this module is in its own shard", "tests.test_run_all" in parts[int(S.shard_of("tests.test_run_all", every)[0])])


@test
def test_a_tier_composes_with_a_shard(ctx: Ctx):
    import tests.run_all as R
    every = _every()
    fast = R.select_modules(every, "fast")
    got = S.select_shard(fast, (1, 4), every)
    ctx.check(f"the fast modules of shard 1, got {len(got)} of {len(fast)}", got == [m for m in S.select_shard(every, (1, 4), every)
                                                                                   if m in fast])
    ctx.check(f"about a quarter of the fast tier, got {len(got)} of {len(fast)}", abs(len(got) - len(fast) / 4) <= len(fast) * 0.1)


@test
def test_shard_of_names_a_modules_shard(ctx: Ctx):
    import tests.run_all as R
    every = _every()
    k = sorted(every).index("tests.test_flake_rules")
    ctx.check("with and without the prefix", S.shard_of("tests.test_flake_rules", every) == f"{k % 4}/4"
              == S.shard_of("test_flake_rules", every))
    ctx.check("another count", S.shard_of("test_flake_rules", every, 3) == f"{k % 3}/3")
    ctx.check("an unknown module", S.shard_of("test_nope_nothing", every) is None)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = R.main(["--shard-of", "tests.test_flake_rules"])
    ctx.check(f"run_all.py --shard-of prints it and runs nothing, got {rc} {out.getvalue()!r}", rc == 0
              and out.getvalue().strip() == f"{k % 4}/4")


@test
def test_the_flags(ctx: Ctx):
    import tests.run_all as R
    ctx.check("--shard 2/4 --fast", S.parse_run_args(["--shard", "2/4", "--fast"]) == {"tier": "fast", "shard": (2, 4),
                                                                                       "shard_of": None, "shards": 4})
    ctx.check("--shard=0/2 --tier full", S.parse_run_args(["--shard=0/2", "--tier", "full"])["shard"] == (0, 2))
    ctx.check("no flag: everything", S.parse_run_args([]) == {"tier": None, "shard": None, "shard_of": None, "shards": 4})
    for bad in (["--shard", "4/4"], ["--shard", "x"], ["--shard"], ["--shards", "0", "--shard-of", "x"], ["--slow"]):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = R.main(bad)
        ctx.check(f"{bad}: exit 2 with one line, got {rc} {err.getvalue()!r}", rc == 2 and err.getvalue().startswith("run_all.py: "))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
