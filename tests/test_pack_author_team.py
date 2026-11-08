"""tests.test_pack_author_team -- the shipped `pack-author` lineup (Halo 3.3.12.0 R4): `halo --team pack-author`
resolves to three roles (the author as main, a researcher, a reviewer), validates with zero problems and no tier
warning, its bios load, and the author's bio carries the one-page contract and the loop the pack kit's HALO-PACK.md
says, so a session pointed at a kit folder works the same way. A scratch home; no model.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.config_seed import ConfigHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


@test
def test_the_lineup_resolves_and_validates(ctx: Ctx):
    from halo_harness import teams_yaml as T
    from halo_harness.teams_tiers import tier_warnings
    with ConfigHome() as h:
        ctx.check("pack-author ships", "pack-author" in T.list_bundled_team_templates())
        raw = T.load_team_template_raw("pack-author", cwd=h.repo)
        ctx.check("zero problems, no tier warning", T.validate_team_template(raw, name="pack-author", cwd=h.repo) == []
                  and tier_warnings(raw) == [])
        lineup = T.resolve_team_template("pack-author", cwd=h.repo)
        table, notes = T.resolve_role_table(lineup, cwd=h.repo)
        ctx.check(f"three roles: main, researcher, reviewer, got {sorted(table)} {notes}",
                  sorted(table) == ["main", "researcher", "reviewer"])
        agents = {e["role"]: e["agent"] for e in lineup["agents"]}
        ctx.check(f"the author is main, got {agents}", agents == {"main": "pack-author", "researcher": "pack-researcher",
                                                                 "reviewer": "pack-reviewer"})


@test
def test_the_bios_carry_the_contract_and_the_loop(ctx: Ctx):
    from halo_harness import agents_yaml as A
    with ConfigHome() as h:
        for name in ("pack-author", "pack-researcher", "pack-reviewer"):
            ctx.check(f"{name} loads with zero problems", A.resolve_agent_bio(name, cwd=h.repo) is not None
                      and A.validate_agent_bio(A.load_agent_bio_raw(name, cwd=h.repo), name=name, cwd=h.repo) == [])
        prompt = A.resolve_agent_bio("pack-author", cwd=h.repo)["context"]["system_prompt"]
        for words in ("HALO-PACK.md", "pack.yaml is the manifest", "halo pack test .", "halo pack install . --link --project",
                      "halo pack doctor", "halo_harness.ext", "requires:", "ask for the least", "no telemetry"):
            ctx.check(f"the author's bio says {words!r}", words in prompt)
        research = A.resolve_agent_bio("pack-researcher", cwd=h.repo)["context"]["system_prompt"]
        ctx.check("the researcher evaluates license, telemetry and install lines and never copies a tool's code",
                  all(w in research for w in ("license", "telemetry", "install", "Never copy")))


@test
def test_halo_team_pack_author_is_a_lineup_the_cli_knows(ctx: Ctx):
    import contextlib
    import io
    from halo_harness.teams_cli import cmd_teams
    with ConfigHome():
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = cmd_teams(["show", "pack-author"])
        ctx.check(f"halo teams show pack-author, got {out.getvalue()[:200]}", code == 0 and "pack-author" in out.getvalue())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
