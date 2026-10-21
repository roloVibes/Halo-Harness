"""tests.test_packs_conflicts -- one name offered twice (Halo 3.2.0.0 R1,
halo_harness/packs/conflicts.py): two enabled packs offering the same plugin
agent; your own bio, lineup or skill with a name a pack offers (yours is
used, and the line says so: never a silent override); a same-id pack in the
repo shadowing the home's; and `halo pack doctor` printing each.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import PacksHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _second_pack(h, pack_id: str = "doc-extra") -> Path:
    """A second pack, made from the fixture under another id: same plugin agent name (doc-helper)."""
    src = h.source(folder=pack_id)
    text = (src / "pack.yaml").read_text(encoding="utf-8").replace("id: doc-review", f"id: {pack_id}")
    (src / "pack.yaml").write_text(text, encoding="utf-8")
    (src / ".claude-plugin" / "plugin.json").write_text('{"name": "%s"}' % pack_id, encoding="utf-8")
    return src


def _lines(h):
    from halo_harness.packs.conflicts import conflict_lines
    from halo_harness.packs.registry import active
    return conflict_lines(active(cwd=h.repo), cwd=h.repo)


@test
def test_two_packs_offering_one_agent_name(ctx: Ctx):
    with PacksHome() as h:
        h.install(h.source(), enable=True)
        src = _second_pack(h)
        from halo_harness.packs.install import install
        ok, lines = install(str(src), cwd=h.repo)
        ctx.check(f"the second pack installs, got {lines}", ok)
        h.cli("enable", "doc-extra")
        found = _lines(h)
        ctx.check(f"one line for the shared agent name, got {found}",
                  found == ["agent doc-helper: offered by packs doc-extra and doc-review; doc-extra's is used"])
        ctx.check("the bios do not clash: each is under its own id", not any(ln.startswith("bio ") for ln in found))


@test
def test_your_bio_lineup_and_skill_win_and_are_named(ctx: Ctx):
    from halo_harness import agents_yaml as A
    from halo_harness import teams_yaml as T
    with PacksHome() as h:
        h.install(h.source(), enable=True)
        h.write(".halo/agents/doc-review--writer.yaml", "description: mine\n")
        h.write(".halo/teams/doc-review--review.yaml", "description: mine\nroles: {main: coder}\n", base=h.repo)
        h.write(".claude/skills/doc-review/check-links/SKILL.md", "---\ndescription: my skill\n---\nmine\n")
        found = _lines(h)
        ctx.check(f"your bio is named and used, got {found}",
                  any(ln.startswith("bio doc-review--writer: your ") and ln.endswith("yours is used") for ln in found))
        ctx.check("your repo lineup is named and used", any(ln.startswith("lineup doc-review--review: your ") for ln in found))
        ctx.check("your skill is named and used", any(ln.startswith("skill doc-review:check-links: one of your own") for ln in found))
        ctx.check("the bio resolves to yours", A.find_agent_bio_path("doc-review--writer", cwd=h.repo)[1] == "user")
        ctx.check("the lineup resolves to yours", T.find_team_template_path("doc-review--review", cwd=h.repo)[1] == "project")
        code, out, _err = h.cli("doctor")
        ctx.check(f"doctor prints them and exits 1, got {code}", code == 1 and out.count("yours is used") == 3)


@test
def test_a_repo_pack_shadows_the_homes(ctx: Ctx):
    with PacksHome() as h:
        h.install(h.source())
        shutil.copytree(h.packs / "doc-review", h.repo / ".halo" / "packs" / "doc-review")
        from halo_harness.packs.registry import snapshot
        snap = snapshot(cwd=h.repo)
        pack = snap.pack("doc-review")
        ctx.check(f"the repo's is the one used, got {pack.root}", pack.scope == "project" and pack.shadowed)
        code, out, _err = h.cli("doctor")
        ctx.check(f"doctor says the home's is not used, got {out}", "is not used" in out and code == 1)
        from halo_harness.packs.registry import active
        ctx.check("enable acts on the one used (the repo's)", h.cli("enable", "doc-review")[0] == 0)
        ctx.check("and that is the one that runs", [p.scope for p in active(cwd=h.repo)] == ["project"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
