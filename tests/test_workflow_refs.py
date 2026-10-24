"""tests.test_workflow_refs -- a lineup's `workflows:` as `<pack>/<name>` refs
(Halo 3.2.1.0 R2, packs/lineup_run.py, teams_yaml.resolve_team_template,
packs/bio_rules.py): a pack's lineup keeps its bare names and resolves
`workflow_refs` beside them; a lineup of yours may name `<pack>/<name>` (or
`<pack>--<name>`), and a ref no running pack holds is one `halo teams
validate` line; a clone's bare name resolves inside the pack it came from;
`halo teams show` prints the refs; a pack's lineup may name its own
`<id>/<name>` (the compile still finds it), never another pack's. No model
call.

Run: python -m tests.test_workflow_refs
"""

from __future__ import annotations

import contextlib
import io
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import PacksHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
MINE = """name: mine
description: A lineup of yours that runs pack workflows.
agents:
  - {agent: doc-review--writer, role: main}
workflows: [doc-review/review, doc-review--review, other-pack/flow, loose]
"""


def _show(name: str, cwd) -> "tuple[int, str]":
    from halo_harness.teams_cli import cmd_teams
    out, old = io.StringIO(), os.getcwd()
    try:
        os.chdir(cwd)
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = cmd_teams(["show", name])
    finally:
        os.chdir(old)
    return code, out.getvalue()


@test
def test_a_packs_lineup_resolves_its_refs_beside_its_names(ctx: Ctx):
    from halo_harness import teams_yaml as T
    with PacksHome() as h:
        h.install(h.source(), enable=True, grants=["bash"])
        got = T.resolve_team_template("doc-review--review", cwd=h.repo)
        ctx.check(f"workflows stay the bare names, the refs beside them, got {got.get('workflows')} {got.get('workflow_refs')}",
                  got.get("workflows") == ["review"] and got.get("workflow_refs") == ["doc-review/review"])
        code, out = _show("doc-review--review", h.repo)
        ctx.check(f"halo teams show prints the ref, got {out!r}",
                  code == 0 and "  workflows: doc-review/review (halo workflow run doc-review/review)\n" in out)


@test
def test_a_lineup_of_yours_names_refs_and_a_ref_no_pack_holds_is_one_line(ctx: Ctx):
    from halo_harness import teams_yaml as T
    with PacksHome() as h:
        h.install(h.source(), enable=True, grants=["bash"])
        h.write("teams/mine.yaml", MINE, base=h.state)
        raw = T.load_team_template_raw("mine", cwd=h.repo)
        problems = T.validate_team_template(raw, name="mine", cwd=h.repo)
        ctx.check(f"one line, the ref no running pack holds, got {problems}",
                  problems == ["\"workflows\" 'other-pack/flow': pack other-pack is not installed here (halo pack list)"])
        got = T.resolve_team_template("mine", cwd=h.repo)
        ctx.check(f"the refs, one per workflow, got {got.get('workflow_refs')}",
                  got.get("workflow_refs") == ["doc-review/review", "other-pack/flow"]
                  and got.get("workflows") == ["doc-review/review", "doc-review--review", "other-pack/flow", "loose"])
        code, out = _show("mine", h.repo)
        ctx.check(f"halo teams show: the refs and the bare name with no pack, got {out!r}", code == 0
                  and "  workflows: doc-review/review, other-pack/flow (halo workflow run doc-review/review)\n" in out
                  and "  workflows: loose names no pack: a lineup of yours names <pack>/loose\n" in out)
        from halo_harness.packs.grants import disable
        disable("doc-review")
        problems = [p for p in T.validate_team_template(raw, name="mine", cwd=h.repo) if p.startswith('"workflows"')]
        ctx.check(f"the pack disabled: its refs are lines too, got {problems}", len(problems) == 3
                  and problems[0] == "\"workflows\" 'doc-review/review': pack doc-review is not enabled here (halo pack list)")


@test
def test_a_clones_bare_name_resolves_inside_its_pack(ctx: Ctx):
    from halo_harness import teams_yaml as T
    from halo_harness.packs.clone import clone
    with PacksHome() as h:
        h.install(h.source(), enable=True, grants=["bash"])
        done = clone("lineup", "doc-review--review", as_name="my-review", cwd=h.repo, state_dir=h.state)
        ctx.check(f"cloned, got {done}", done.get("ok") is True)
        got = T.resolve_team_template("my-review", cwd=h.repo)
        ctx.check(f"from_pack doc-review: review is doc-review/review, got {got.get('workflow_refs')}",
                  got.get("workflows") == ["review"] and got.get("workflow_refs") == ["doc-review/review"])
        raw = T.load_team_template_raw("my-review", cwd=h.repo)
        ctx.check("it validates", T.validate_team_template(raw, name="my-review", cwd=h.repo) == [])


@test
def test_a_packs_lineup_names_its_own_ref_never_another_packs(ctx: Ctx):
    from halo_harness.packs.discover import read_pack
    from halo_harness.workflows import spec
    from halo_harness.workflows.compile import _lineup
    with PacksHome() as h:
        src = h.source()
        team = src / "teams" / "review.yaml"
        team.write_text(team.read_text(encoding="utf-8").replace("workflows: [review]", "workflows: [doc-review/review]"),
                        encoding="utf-8")
        ctx.check(f"its own <id>/<name>: no manifest line, got {read_pack(src, 'source').problems}",
                  read_pack(src, "source").problems == [])
        h.install(src, enable=True, grants=["bash"])
        wf, why = spec.find("doc-review/review", cwd=h.repo)
        ctx.check(f"the compile still finds the lineup that names it, got {_lineup(wf) if wf else why}",
                  wf is not None and _lineup(wf) == "doc-review--review")
        other = h.source(folder="alt/doc-review")
        team = other / "teams" / "review.yaml"
        team.write_text(team.read_text(encoding="utf-8").replace("workflows: [review]", "workflows: [other-pack/flow]"),
                        encoding="utf-8")
        ctx.check(f"another pack's: one line, got {read_pack(other, 'source').problems}", read_pack(other, "source").problems
                  == ["teams/review.yaml line 15: workflows 'other-pack/flow' names pack other-pack's workflow: a pack's "
                      "lineup runs its own (doc-review/<name>, or the bare name)"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
