"""tests.test_teams_tiers -- Halo 3.0.7.0 round R1: `tiers:` in a lineup
(teams_tiers.py + teams_yaml.validate_team_template): a valid stack, each
refusal with its exact line, the implicit last tier and its "warning:"
line, the one implicit tier when none are declared, `extends` merging the
section, and every shipped lineup still validating clean.

Run: python -m tests.test_teams_tiers
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402

ensure_default_provider_credentials()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


class _Env:
    """A scratch home (BRIDGE_TEST_HOME + BRIDGE_STATE_DIR for this test only)."""

    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
        d = Path(tempfile.mkdtemp(prefix="teams-tiers-"))
        os.environ["BRIDGE_TEST_HOME"] = str(d)
        os.environ["BRIDGE_STATE_DIR"] = str(d / ".halo")
        self.state_dir = d / ".halo"
        self.cwd = d / "project"
        self.cwd.mkdir(parents=True)
        from halo_harness.agents_yaml import save_agent_bio
        for bio in ("lead-bio", "worker-bio"):
            save_agent_bio(bio, {"description": bio, "models": {"preference": "or:vendor/m"}}, state_dir=self.state_dir)
        return self

    def __exit__(self, *exc):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


AGENTS = [{"agent": "lead-bio", "role": "main"},
          {"agent": "lead-bio", "role": "planner"},
          {"agent": "worker-bio", "role": "subagent", "as": "worker"},
          {"agent": "worker-bio", "role": "reviewer"}]
TIERS = [{"name": "top", "members": ["main"]},
         {"name": "leads", "members": ["planner"], "max_parallel": 2},
         {"name": "workers", "members": ["worker", "reviewer"]}]


def _validate(e: _Env, tiers, agents=None):
    from halo_harness.teams_yaml import validate_team_template
    return validate_team_template({"agents": agents or AGENTS, "tiers": tiers}, cwd=e.cwd, state_dir=e.state_dir)


@test
def test_a_valid_stack_validates_and_resolves(ctx: Ctx):
    from halo_harness.teams_tiers import effective_tiers, tier_warnings
    with _Env() as e:
        ctx.check(f"three declared tiers validate clean, got {_validate(e, TIERS)}", _validate(e, TIERS) == [])
        tiers = effective_tiers({"agents": AGENTS, "tiers": TIERS})
        ctx.check(f"the effective tiers keep order, members and caps, got {tiers}",
                  [(t["name"], t["members"], t["max_parallel"], t["index"], t["implicit"]) for t in tiers]
                  == [("top", ["main"], None, 0, False), ("leads", ["planner"], 2, 1, False),
                      ("workers", ["worker", "reviewer"], None, 2, False)])
        ctx.check("no warning when every alias is placed", tier_warnings({"agents": AGENTS, "tiers": TIERS}) == [])


@test
def test_each_refusal_has_its_exact_line(ctx: Ctx):
    with _Env() as e:
        cases = [
            ("not a list", {"name": "x"}, '"tiers" must be a list of {name, members, max_parallel} entries'),
            ("an entry that is not a mapping", [{"name": "top", "members": ["main"]}, "leads"],
             'tiers[1] must be a mapping with "name" and "members"'),
            ("no name", [{"name": "top", "members": ["main"]}, {"members": ["worker"]}], 'tiers[1]: "name" is required'),
            ("a duplicate name", [{"name": "top", "members": ["main"]}, {"name": "top", "members": ["worker"]}],
             "duplicate tier name: 'top'"),
            ("members not a list", [{"name": "top", "members": ["main"]}, {"name": "w", "members": "worker"}],
             "tiers[1] 'w': \"members\" must be a list of aliases"),
            ("an unknown alias", [{"name": "top", "members": ["main"]}, {"name": "w", "members": ["ghost"]}],
             "tiers[1] 'w': 'ghost' is not an alias in this lineup (known: main, planner, worker, reviewer)"),
            ("an alias in two tiers", [{"name": "top", "members": ["main"]}, {"name": "a", "members": ["worker"]},
                                       {"name": "b", "members": ["worker"]}],
             "'worker' is in two tiers: 'a' and 'b' (an alias sits in one tier)"),
            ("a bad max_parallel", [{"name": "top", "members": ["main"]}, {"name": "w", "members": ["worker"],
                                                                          "max_parallel": 0}],
             "tiers[1] 'w': \"max_parallel\" must be a positive integer"),
            ("a bool max_parallel", [{"name": "top", "members": ["main"]}, {"name": "w", "members": ["worker"],
                                                                           "max_parallel": True}],
             "tiers[1] 'w': \"max_parallel\" must be a positive integer"),
            ("main not alone in tier 0", [{"name": "top", "members": ["main", "planner"]}],
             "tier 0 ('top') must hold the main agent 'main' alone (found: main, planner)"),
            ("main not in tier 0", [{"name": "top", "members": ["planner"]}, {"name": "w", "members": ["main"]}],
             "tier 0 ('top') must hold the main agent 'main' alone (found: planner)"),
        ]
        for label, tiers, line in cases:
            got = _validate(e, tiers)
            ctx.check(f"{label}: {line!r} is one of {got}", line in got)


@test
def test_main_alias_counts_for_tier_zero(ctx: Ctx):
    with _Env() as e:
        agents = [{"agent": "lead-bio", "role": "main", "as": "boss"}, {"agent": "worker-bio", "role": "subagent"}]
        ok = _validate(e, [{"name": "top", "members": ["boss"]}, {"name": "w", "members": ["subagent"]}], agents)
        ctx.check(f"main's own alias holds tier 0, got {ok}", ok == [])
        bad = _validate(e, [{"name": "top", "members": ["main"]}], agents)
        ctx.check(f"the bare role name is not the alias, got {bad}",
                  any("'main' is not an alias" in p for p in bad) and any("'boss' alone" in p for p in bad))


@test
def test_unplaced_aliases_join_the_implicit_last_tier_with_a_warning(ctx: Ctx):
    from halo_harness.teams_tiers import effective_tiers, tier_warnings
    with _Env() as e:
        tiers = [{"name": "top", "members": ["main"]}, {"name": "leads", "members": ["planner"]}]
        ctx.check(f"leaving aliases out is not a problem, got {_validate(e, tiers)}", _validate(e, tiers) == [])
        template = {"agents": AGENTS, "tiers": tiers}
        eff = effective_tiers(template)
        ctx.check(f"worker and reviewer land in the implicit tier 'rest', got {eff}",
                  eff[-1] == {"name": "rest", "members": ["worker", "reviewer"], "max_parallel": None, "index": 2,
                              "implicit": True})
        ctx.check(f"one warning line names them, got {tier_warnings(template)}", tier_warnings(template) == [
            "warning: tiers: 'worker', 'reviewer' in no tier -- they join the implicit last tier 'rest'"])
        taken = {"agents": AGENTS, "tiers": [{"name": "top", "members": ["main"]}, {"name": "rest", "members": ["planner"]}]}
        ctx.check("a declared 'rest' pushes the implicit name to rest-2", effective_tiers(taken)[-1]["name"] == "rest-2")


@test
def test_no_tiers_is_one_implicit_tier(ctx: Ctx):
    from halo_harness.teams_tiers import effective_tiers, tier_warnings
    with _Env() as e:
        from halo_harness.teams_yaml import validate_team_template
        ctx.check("no tiers key validates", validate_team_template({"agents": AGENTS}, cwd=e.cwd, state_dir=e.state_dir) == [])
        ctx.check("an empty list validates", _validate(e, []) == [])
        eff = effective_tiers({"agents": AGENTS})
        ctx.check(f"one tier 'all' holding everyone, got {eff}", eff == [
            {"name": "all", "members": ["main", "planner", "worker", "reviewer"], "max_parallel": None, "index": 0,
             "implicit": True}])
        ctx.check("and no warning", tier_warnings({"agents": AGENTS}) == [])


@test
def test_extends_merges_the_tiers_section(ctx: Ctx):
    from halo_harness.teams_yaml import TOP_SECTIONS, SECTION_ENFORCEMENT, resolve_team_template, save_team_template, \
        validate_team_template
    with _Env() as e:
        ctx.check("tiers is a top section with an enforcement line",
                  "tiers" in TOP_SECTIONS and SECTION_ENFORCEMENT["tiers"][0] == "enforced")
        ok, problems = save_team_template("tier-parent", {"agents": AGENTS, "tiers": TIERS}, state_dir=e.state_dir)
        ctx.check(f"the parent saves, got {problems}", ok)
        ok, problems = save_team_template("tier-child", {"extends": "tier-parent", "description": "child"},
                                          state_dir=e.state_dir)
        child = resolve_team_template("tier-child", cwd=e.cwd, state_dir=e.state_dir)
        ctx.check(f"a child that never mentions tiers inherits them, got {child and child.get('tiers')}",
                  ok and child["tiers"] == TIERS)
        mine = [{"name": "top", "members": ["main"]}, {"name": "all-the-rest", "members": ["planner", "worker"]}]
        ok, problems = save_team_template("tier-child2", {"extends": "tier-parent", "tiers": mine}, state_dir=e.state_dir)
        child2 = resolve_team_template("tier-child2", cwd=e.cwd, state_dir=e.state_dir)
        ctx.check(f"a child's own tiers replace the parent's list, got {problems} {child2 and child2.get('tiers')}",
                  ok and child2["tiers"] == mine)
        bad = validate_team_template({"extends": "tier-parent", "tiers": [{"name": "top", "members": ["ghost"]}]},
                                     cwd=e.cwd, state_dir=e.state_dir)
        ctx.check(f"a child's tiers are checked against the parent's aliases, got {bad}",
                  any("'ghost' is not an alias" in p for p in bad))


@test
def test_every_shipped_lineup_still_validates_with_zero_problems(ctx: Ctx):
    from halo_harness.teams_tiers import tier_warnings
    from halo_harness.teams_yaml import list_bundled_team_templates, load_team_template_raw, validate_team_template
    with _Env() as e:
        names = list_bundled_team_templates()
        ctx.check(f"the shipped lineups are found, got {names}", len(names) >= 6)
        for name in names:
            raw = load_team_template_raw(name, cwd=e.cwd, state_dir=e.state_dir)
            problems = validate_team_template(raw, name=name, cwd=e.cwd, state_dir=e.state_dir)
            ctx.check(f"{name}: zero problems and no tier warning, got {problems}",
                      problems == [] and tier_warnings(raw) == [])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="teams tiers tests"))
