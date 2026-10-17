"""tests.helpers.studio_ui_roles -- the Roles click checks of
tests/test_studio_ui.py (Halo 3.0.7.0 round R2: Roles is a React section),
kept here so that file stays small. One headless Chrome run
(`python -m tests.helpers.studio_roles roles`, cached by the runner) over a
seeded catalog, a lineup with two declared tiers and a card on a bio whose
model the catalog does not have; `POST models/test` is stubbed there. Live
Roles, J and the replay are tests/helpers/studio_ui_fleet.py's (the fleet
rig's real session)."""
from __future__ import annotations

from tests.helpers.runner import Ctx, SkipTest

ROLES = ("-m", "tests.helpers.studio_roles", "roles")


def register(test, json_of, chrome) -> None:
    def run(ctx: Ctx) -> dict:
        if not chrome():
            raise SkipTest("no Chrome found (the Roles test needs headless Chrome)")
        r, got = json_of(*ROLES)
        ctx.check(f"the run finished, got {r.stdout[-300:]!r} {r.stderr[-600:]!r}", r.returncode == 0)
        return got

    @test
    def test_roles_drag_between_tiers_saves_and_main_snaps_back(ctx: Ctx):
        """R2: the implementer card dragged from the leads box into the implicit
        rest box rewrites tiers[*].members through PUT lineup/<name> (the file
        on disk changes) and the card sits in the rest box; the main card
        dragged into leads snaps back with a toast naming the rule and nothing
        is saved."""
        got = run(ctx)
        ctx.check(f"worker left the leads tier on disk, got {got.get('tiers_after_drag')}",
                  got.get("tiers_after_drag") == {"top": ["boss"], "leads": ["research"]})
        ctx.check(f"and its card is in the rest box, got {got.get('moved_box')}", got.get("moved_box") == "rest")
        ctx.check(f"main snaps back with the rule, got {got.get('main_toast')!r}", "tier 0" in str(got.get("main_toast")) and "main agent" in str(got.get("main_toast")))
        ctx.check("nothing saved, the card still in tier 0", got.get("main_unchanged") is True and got.get("main_in_top") is True)

    @test
    def test_roles_problems_lists_the_dead_model_id(ctx: Ctx):
        """R2: the Problems panel lists the card whose bio names a model the
        catalog does not have, with its fix."""
        got = run(ctx)
        text = str(got.get("problem"))
        ctx.check(f"the dead id and its fix, got {text!r}", "or:vendor/gone" in text and "fix:" in text)

    @test
    def test_roles_undo_restores_a_lineup_edit(ctx: Ctx):
        """R2: an edit of the lineup's description marks it unsaved; Ctrl+Z
        puts the old text back."""
        got = run(ctx)
        ctx.check(f"the edit took, got {got.get('dirty')!r}", got.get("dirty") == "A description typed in the test")
        ctx.check(f"Ctrl+Z restored it, got {got.get('description_after_undo')!r}",
                  got.get("description_after_undo") == got.get("description_before") and bool(got.get("description_before")))

    @test
    def test_roles_test_this_model_shows_the_probe_inline(ctx: Ctx):
        """R2: the bio form's model table lists the catalog; "Test this model"
        shows the (stubbed) probe's answer inline, no dialog."""
        got = run(ctx)
        ctx.check(f"the model table lists the catalog, got {got.get('model_rows')}", got.get("model_rows") == 7)
        ctx.check(f"ok and the latency inline, got {got.get('probe')!r}", got.get("probe") == "ok in 42 ms" and got.get("dialogs") == 0)
