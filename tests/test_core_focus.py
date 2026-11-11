"""tests.test_core_focus -- Halo 3.4.0.0 B, "the experiments leave the core": what a verb that left the core says,
and that nothing of it is left behind.

1. `halo team` answers one line (it left in 3.4.0.0, and what does its job now) and exits 2; the team package,
   its Studio routes and its Attention rows are gone; the lineups (`halo teams`) are untouched.
2. `halo start` with its pack off: one line naming the pack and how to get it (/start the same).
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

ensure_scoped_state_dir_once()
test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent


def _main(argv: list) -> "tuple[int, str, str]":
    from halo_harness.cli import main
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = main(argv)
    return rc, out.getvalue(), err.getvalue()


@test
def test_halo_team_says_it_left_and_what_does_its_job(ctx: Ctx):
    rc, out, err = _main(["team", "run", "draft"])
    ctx.check(f"exit 2, one line on stderr, got {rc} {err!r}", rc == 2 and not out and len(err.strip().splitlines()) == 1)
    ctx.check("the line says when it left and names lineups and runs",
              err.startswith("halo team: the team file left in 3.4.0.0") and "Agents -> Cast" in err
              and "halo teams" in err and "Agents -> Runs" in err and "owns lines" in err)


@test
def test_nothing_of_the_team_file_is_left(ctx: Ctx):
    gone = ("halo_harness.team", "halo_harness.studio.team_api", "halo_harness.studio.team_live",
            "halo_harness.studio.team_budget_api", "halo_harness.fleet.team_attention", "halo_harness.work.adapters.stage",
            "halo_harness.orchestra.coach_team_rules")
    ctx.check("every team-file module is gone", all(importlib.util.find_spec(m) is None for m in gone))
    from halo_harness.fleet import attention
    from halo_harness.work import states, store
    ctx.check("no team_gate / team_budget attention kind", "team_gate" not in attention.KEYS and "team_budget" not in attention.KEYS)
    ctx.check("no stage unit kind, no team run kind", "stage" not in states.KINDS and "team" not in store.RUN_KINDS)
    ctx.check("orchestra_run lives on in orchestra/to_report.py",
              importlib.util.find_spec("halo_harness.orchestra.to_report") is not None)
    ctx.check("FleetDelegate lives on in fleet/delegate.py", importlib.util.find_spec("halo_harness.fleet.delegate") is not None)


@test
def test_the_lineups_are_untouched(ctx: Ctx):
    rc, out, _err = _main(["teams", "list"])
    ctx.check(f"halo teams list still lists the shipped lineups, got {rc} {out[:200]!r}", rc == 0 and "auto" in out)
    from halo_harness.left import line
    ctx.check("`teams` (with an s) is no verb that left", line("teams") == "")


@test
def test_a_verb_whose_pack_is_off_names_the_pack(ctx: Ctx):
    for verb, pack in (("start", "first-run"),):
        rc, out, err = _main([verb])
        ctx.check(f"halo {verb}: exit 2 and one line naming `halo pack install {pack}`, got {rc} {err!r}",
                  rc == 2 and not out and f"halo pack install {pack}" in err and len(err.strip().splitlines()) == 1)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="core focus tests"))
