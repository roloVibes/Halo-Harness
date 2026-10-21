"""tests.test_packs_roles_studio -- Studio's Roles groups by source and works
a pack's rows (Halo 3.2.0.0 R2). Headless Chrome through the driver base
(tests/helpers/studio_packs_roles.py; skipped without one), over a fresh
home with the shipped lineups and the doc-review fixture pack enabled:

1. Lineups and Bios: group boxes yours, project, pack doc-review, shipped,
   in that order, the empty ones collapsed; a pack lineup row has Preview,
   Clone, Customize, Apply (a bio row the first three);
2. Preview: the lineup on the canvas, the Inspector and the canvas bar say
   "from pack doc-review, read-only"; the bio in the form, its fields
   disabled, Customize instead of Save, the model its tags resolve to;
3. Clone without a collision (your writer, with from_pack), with one of
   yours (the confirm, nothing written until Replace), with a shipped name
   (the confirm, another name); Customize opens the copied lineup;
4. Apply on the pack's row names the pack and the lineup it replaces, and
   writes config.json only;
5. a file of yours named like the pack's reviewer sits in yours and says it
   shadows the pack, whose group says so; a disabled pack has no group.
Run: python -m tests.test_packs_roles_studio
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
_RUN: dict = {}
ORDER = ["yours", "project", "pack:doc-review", "shipped"]


def _got(ctx: Ctx) -> dict:
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (the Roles pack checks need headless Chrome)")
    if "r" not in _RUN:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_packs_roles"], capture_output=True, encoding="utf-8",
                           errors="replace", timeout=400, env=driver_env(REPO), cwd=str(REPO))
        try:
            info = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            info = {}
        _RUN["r"] = (r, info)
    r, info = _RUN["r"]
    if info.get("skip"):
        raise SkipTest(info["skip"])
    ctx.check(f"the driver ran, got {r.returncode} {info.get('failed')!r} {r.stderr[-500:]!r}", r.returncode == 0 and "failed" not in info)
    return info


@test
def test_lineups_and_bios_group_by_source(ctx: Ctx):
    got = _got(ctx)
    for key in ("lineup_groups", "bio_groups"):
        groups = got.get(key) or []
        ctx.check(f"{key}: the boxes in order, got {groups}", [g[0] for g in groups] == ORDER)
        ctx.check(f"{key}: each labeled, the empty ones collapsed",
                  [g[3] for g in groups] == ["YOURS", "PROJECT", "PACK DOC-REVIEW", "SHIPPED"]
                  and all((g[1] is False) == (g[2] is True) for g in groups) and groups[0][2] and groups[1][2])
    ctx.check(f"a pack lineup's actions, got {got.get('pack_actions')}", got.get("pack_actions") == ["Preview", "Clone", "Customize", "Apply"])
    ctx.check(f"a pack bio's actions, got {got.get('bio_actions')}", got.get("bio_actions") == ["Preview", "Clone", "Customize"])


@test
def test_preview_opens_read_only(ctx: Ctx):
    got = _got(ctx)
    ctx.check("the lineup on the canvas", got.get("canvas") == "doc-review--review")
    ctx.check(f"the Inspector and the bar say whose and read-only, got {got.get('readonly')!r} {got.get('bar_scope')!r}",
              str(got.get("readonly")).startswith("from pack doc-review, read-only") and got.get("bar_scope") == "from pack doc-review, read-only")
    ctx.check(f"the bio form: read-only, fields disabled, Customize not Save, got {got.get('bio_readonly')!r} {got.get('bio_buttons')}",
              got.get("bio_readonly") == "from pack doc-review, read-only" and got.get("bio_disabled") is True
              and got.get("bio_buttons") == [True, False])
    ctx.check(f"the model its tags resolve to, got {got.get('bio_model')!r}",
              got.get("bio_model") == "runs on ol:long-1: the best catalog model with long-context")


@test
def test_clone_with_and_without_a_collision_and_customize(ctx: Ctx):
    got = _got(ctx)
    ctx.check("no collision: your writer, from_pack on disk and on the row",
              got.get("writer_row") == "yours" and got.get("writer_file") is True and got.get("writer_chip") is True)
    ctx.check(f"yours has the name: the confirm, nothing written before it, got {got.get('yours_title')!r}",
              got.get("yours_title") == "writer is already yours" and got.get("unwritten_before_confirm") is True
              and got.get("replace_label") == "Replace your writer" and got.get("replaced_closed") is True)
    ctx.check(f"a shipped name: the confirm, another name taken, got {got.get('shipped_title')!r} {got.get('rename_label')!r}",
              got.get("shipped_title") == "Halo ships a bio named reviewer" and got.get("rename_label") == "Clone as doc-reviewer"
              and got.get("renamed_row") is True and got.get("no_reviewer_file") is True)
    ctx.check("Customize: the copy (review) open, editable, on the Lineup tab, from_pack in its file",
              got.get("customized") == "review" and got.get("customized_readonly") is False and got.get("customized_tab") == "true"
              and got.get("lineup_file") is True)
    ctx.check("the pack's own files untouched", got.get("pack_untouched") is True)


@test
def test_apply_names_the_pack_and_what_it_replaces(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the dialog names the pack, got {got.get('apply_pack')!r}", str(got.get("apply_pack")).startswith("From pack doc-review"))
    ctx.check(f"and the lineup it replaces as the default, got {got.get('apply_replaces')!r}",
              "It replaces halo-dev-cycle as the lineup new sessions use." in str(got.get("apply_replaces")))
    ctx.check("applied: active, config.json's team, no file of yours changed",
              got.get("active") == "doc-review--review" and got.get("config_team") == "doc-review--review" and got.get("files_unchanged") is True)


@test
def test_a_shadowing_file_of_yours_and_a_disabled_pack(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"your file sits in yours and says it shadows the pack, got {got.get('shadow_group')!r} {got.get('shadow_chip')!r}",
              got.get("shadow_group") == "yours" and got.get("shadow_chip") == "shadows pack doc-review")
    ctx.check(f"the pack's group says so, got {got.get('shadowed_line')!r}",
              got.get("shadowed_line") == "doc-review--reviewer: shadowed by ~/.halo/agents/doc-review--reviewer.yaml (yours is the one used)")
    ctx.check(f"disabled: its group is gone, got {got.get('disabled_groups')}", got.get("disabled_groups") == ["yours", "project", "shipped"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
