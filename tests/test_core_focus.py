"""tests.test_core_focus -- Halo 3.4.0.0 B, "the experiments leave the core": what a verb that left the core says,
and that nothing of it is left behind.

1. `halo team` answers one line (it left in 3.4.0.0, and what does its job now) and exits 2; the team package,
   its Studio routes and its Attention rows are gone; the lineups (`halo teams`) are untouched.
3. The import rule (3.4.0.0 B2): no module of halo_harness outside templates/ imports a shipped pack's code.
2. `halo start` with its pack off: one line naming the pack and how to get it (/start the same); B2: `halo coach` and
   `halo improve` the same, and nothing of the coach is left in the core.
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
def test_nothing_of_the_coach_is_left_in_the_core(ctx: Ctx):
    """3.4.0.0 B2: the coach's modules live in the coach pack only; the core keeps prices and lane_facts."""
    gone = ("halo_harness.coach_cli", "halo_harness.coach_library_cli", "halo_harness.improve_cli", "halo_harness.improve",
            "halo_harness.orchestra.coach", "halo_harness.orchestra.coach_probe", "halo_harness.orchestra.probe_runs",
            "halo_harness.orchestra.probe_overlay", "halo_harness.studio.coach_api", "halo_harness.studio.coach_probe_job")
    left = [m for m in gone if m not in sys.modules and importlib.util.find_spec(m) is not None]
    ctx.check(f"no coach module in halo_harness, got {left}", not left)
    ctx.check("prices and lane_facts stay core", importlib.util.find_spec("halo_harness.orchestra.prices") is not None
              and importlib.util.find_spec("halo_harness.orchestra.lane_facts") is not None)
    from halo_harness.settings_catalog import GROUP_TITLES
    ctx.check("no Coach and improve Settings group", "coach" not in GROUP_TITLES and GROUP_TITLES.get("from_packs") == "From packs")


@test
def test_the_lineups_are_untouched(ctx: Ctx):
    rc, out, _err = _main(["teams", "list"])
    ctx.check(f"halo teams list still lists the shipped lineups, got {rc} {out[:200]!r}", rc == 0 and "auto" in out)
    from halo_harness.left import line
    ctx.check("`teams` (with an s) is no verb that left", line("teams") == "")


@test
def test_a_verb_whose_pack_is_off_names_the_pack(ctx: Ctx):
    for verb, pack in (("start", "first-run"), ("coach", "coach"), ("improve", "coach")):  # coach, improve: 3.4.0.0 B2
        rc, out, err = _main([verb])
        ctx.check(f"halo {verb}: exit 2 and one line naming `halo pack install {pack}`, got {rc} {err!r}",
                  rc == 2 and not out and f"halo pack install {pack}" in err and len(err.strip().splitlines()) == 1)


_LEFT_FOR_PACKS = ("halo_harness.start", "halo_harness.start_cli", "halo_harness.coach_cli", "halo_harness.coach_library_cli",
                   "halo_harness.improve", "halo_harness.improve_cli", "halo_harness.studio.coach_api",
                   "halo_harness.studio.coach_probe_job", "halo_harness.studio.start_job")


@test
def test_no_core_module_imports_a_shipped_pack(ctx: Ctx):
    """3.4.0.0 B / B2: what left the core for a shipped pack (the first-run and coach packs) is reached only through
    the pack system (its contributions, `packs.contrib_cli`): no module of halo_harness outside templates/ imports a
    pack's package (`halo_packs.*`) or a name that left (`halo_harness.orchestra.coach*` / `.probe_*`, the coach CLIs,
    `halo_harness.improve`, the start modules), and those names are gone from the tree."""
    import ast
    import re
    pkg = REPO / "halo_harness"
    bad = []
    for path in sorted(pkg.rglob("*.py")):
        rel = path.relative_to(REPO).as_posix()
        if rel.startswith("halo_harness/templates/"):
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"), filename=rel)):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                [node.module or ""] + [f"{node.module}.{a.name}" for a in node.names] if isinstance(node, ast.ImportFrom) \
                and not node.level else []
            for n in names:
                if n.startswith("halo_packs") or n in _LEFT_FOR_PACKS or n.startswith(_LEFT_FOR_PACKS[4] + ".") \
                        or re.match(r"halo_harness\.orchestra\.(coach\w*|probe_runs|probe_overlay)$", n):
                    bad.append(f"{rel}:{node.lineno}: {n}")
    ctx.check("no core import of a shipped pack's code:\n  " + "\n  ".join(bad), not bad)
    still = [p.relative_to(REPO).as_posix() for p in list(pkg.glob("orchestra/coach*.py"))
             + list(pkg.glob("orchestra/probe_*.py")) + [pkg / "improve", pkg / "coach_cli.py", pkg / "improve_cli.py"]
             if p.exists()]
    ctx.check(f"the coach's files are the pack's only, got {still}", not still)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="core focus tests"))
