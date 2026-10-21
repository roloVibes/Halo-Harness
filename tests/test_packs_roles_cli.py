"""tests.test_packs_roles_cli -- the CLI over a pack's bios and lineups (Halo
3.2.0.0 R2, docs/COMMANDS-packs.md): `halo pack inspect` lists each bio
with the model it resolves to and the grants it needs, and each lineup with
its members, tiers, workflows and acceptance (an installed pack and a
source folder); `halo pack doctor` adds a row per capability set no catalog
model has and per ungranted need; `halo agents list` / `halo teams list`
print one group per pack (unchanged with none); `halo orchestra new
--lineup` starts with the lineup's acceptance.test and review.
Run: python -m tests.test_packs_roles_cli
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import PacksHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
LONG = [{"ref": "ol:long-1", "provider": "ollama", "context_tokens": 262144}]


def _run(fn, argv, cwd=None) -> "tuple[int, str]":
    import os
    out = io.StringIO()
    old = os.getcwd()
    try:
        if cwd is not None:
            os.chdir(cwd)
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = fn(list(argv))
    finally:
        os.chdir(old)
    return code, out.getvalue()


@test
def test_inspect_lists_each_bio_with_its_model_and_needs(ctx: Ctx):
    with PacksHome() as h:
        h.catalog(LONG)
        h.install(h.source(), enable=True, grants=["hooks"])
        code, out, _err = h.cli("inspect", "doc-review")
        ctx.check(f"each bio, the model it resolves to and why, got {out}",
                  code == 0 and "  doc-review--reviewer: runs on ol:long-1 (the best catalog model with long-context)" in out
                  and "doc-review--writer: runs on ol:long-1 (the best catalog model with long-context, family claude-sonnet)" in out)
        ctx.check("its needs and whether granted, its memory namespace",
                  "    needs: bash (not granted)" in out and "    memory namespace: doc-review/reviews" in out)
        ctx.check("the lineup: members, tiers, workflows, acceptance",
                  "  doc-review--review: doc-review--writer (main), doc-review--reviewer (reviewer); 2 tiers; workflows review; "
                  "acceptance.test: python -m pytest -q; acceptance.review: true" in out)
        code, out, _err = h.cli("inspect", "doc-review", "--json")
        d = json.loads(out)
        rev = next(b for b in d["bios"] if b["name"] == "doc-review--reviewer")
        ctx.check(f"--json: the same, got {rev}", rev["model"] == "ol:long-1" and rev["how"] == "capabilities"
                  and rev["needs"] == [{"need": "bash", "granted": False}] and d["lineups"][0]["workflows"] == ["review"])
        h.catalog([])
        code, out, _err = h.cli("inspect", str(h.source("rare-caps")))
        ctx.check(f"a source folder too: no row has the tags, your default and why, got {out}",
                  code == 0 and "rare-caps--watcher: runs on default (no model in the catalog has video, image-out, long-context" in out
                  and "needs: network (not granted)" in out)


@test
def test_doctor_rows_for_an_unresolved_capability_set_and_an_ungranted_need(ctx: Ctx):
    with PacksHome() as h:
        h.catalog([])
        h.install(h.source("rare-caps"), enable=True)
        code, out, _err = h.cli("doctor")
        ctx.check(f"the two rows with their fixes, exit 1, got {out}",
                  code == 1 and "[WARN] rare-caps: no model in the catalog has video, image-out, long-context (bio rare-caps--watcher: "
                  "it runs on your default model)" in out
                  and "[WARN] rare-caps: bio rare-caps--watcher uses network, which is not granted" in out
                  and "-> halo pack enable rare-caps --grant network" in out)
        code, out, _err = h.cli("doctor", "--json")
        ctx.check("--json: their checks", sorted(p["check"] for p in json.loads(out)["problems"]) == ["bio-model", "bio-need"])
        h.catalog([{"ref": "or:vendor/omni", "provider": "openrouter", "context_tokens": 2_000_000,
                    "modalities_in": ["text", "video"], "modalities_out": ["text", "image"], "image_output": True}])
        h.cli("enable", "rare-caps", "--grant", "network")
        code, out, _err = h.cli("doctor")
        ctx.check(f"a row that has them and the grant: clean, got {out}", code == 0 and "RESULT: 0 problem(s)" in out)


@test
def test_agents_and_teams_list_print_one_group_per_pack(ctx: Ctx):
    from halo_harness.agents_cli import cmd_agents
    from halo_harness.teams_cli import cmd_teams
    with PacksHome() as h:
        _code, plain = _run(cmd_agents, ["list"], cwd=h.repo)
        _code, teams_plain = _run(cmd_teams, ["list"], cwd=h.repo)
        ctx.check("no pack: one name per line, no group", "pack " not in plain and "pack " not in teams_plain and "coder\n" in plain)
        h.install(h.source(), enable=True)
        code, out = _run(cmd_agents, ["list"], cwd=h.repo)
        ctx.check(f"halo agents list: yours as before, then the pack's group, got {out[-120:]!r}",
                  code == 0 and out.startswith(plain) and out[len(plain):] == "pack doc-review:\n  doc-review--reviewer\n  doc-review--writer\n")
        code, out = _run(cmd_teams, ["list"], cwd=h.repo)
        ctx.check(f"halo teams list: the same, got {out[-80:]!r}",
                  code == 0 and out.startswith(teams_plain) and out.endswith("pack doc-review:\n  doc-review--review\n"))


@test
def test_orchestra_new_starts_with_the_lineups_acceptance(ctx: Ctx):
    from halo_harness.orchestra_cli import cmd_orchestra
    with PacksHome() as h:
        h.install(h.source(), enable=True)
        base = ["new", "--what", "w", "--done-when", "d", "--stop-when", "s", "--lineup", "doc-review--review", "--repo", str(h.repo)]
        code, out = _run(cmd_orchestra, base, cwd=h.repo)
        goals = sorted((h.repo / ".halo" / "orchestra").glob("*/goal.json"))
        goal = json.loads(goals[-1].read_text(encoding="utf-8")) if goals else {}
        ctx.check(f"the test and the review come from the lineup, and the output says so, got {out!r}",
                  code == 0 and goal.get("test") == "python -m pytest -q" and goal.get("plan") == "review"
                  and "(from lineup doc-review--review's acceptance.test)" in out)
        code, out = _run(cmd_orchestra, base + ["--test", "make check"], cwd=h.repo)
        goals = sorted((h.repo / ".halo" / "orchestra").glob("*/goal.json"), key=lambda p: p.stat().st_mtime_ns)
        goal = json.loads(goals[-1].read_text(encoding="utf-8")) if goals else {}
        ctx.check(f"--test wins, got {goal.get('test')!r}", code == 0 and goal.get("test") == "make check")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
