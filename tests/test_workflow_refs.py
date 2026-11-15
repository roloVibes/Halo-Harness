"""tests.test_workflow_refs -- a lineup's `workflows:` as `<pack>/<name>` refs
(Halo 3.2.1.0 R2, packs/lineup_run.py, teams_yaml.resolve_team_template,
packs/bio_rules.py): a pack's lineup keeps its bare names and resolves
`workflow_refs` beside them; a lineup of yours may name `<pack>/<name>` (or
`<pack>--<name>`), and a ref no running pack holds is one `halo teams
validate` line (3.6.0.0 R5d: the clone test went with packs/clone.py); `halo teams show` prints the refs; a pack's lineup may name its own
`<id>/<name>` (the compile still finds it), never another pack's. No model
call.

Run: python -m tests.test_workflow_refs
"""

from __future__ import annotations

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
