"""tests.helpers.studio_ui_coach -- the post-run coach's checks of
tests/test_studio_ui.py (Halo 3.0.9.0 round R3), kept here so that file stays
small. One headless Chrome run (`python -m tests.helpers.studio_coach`,
tests/helpers/studio_coach.py) over a Studio on the finished R2 run with three
findings seeded and an ended mission (no model call); the runner caches it, so
the tests read one run."""
from __future__ import annotations

from tests.helpers.runner import Ctx, SkipTest

ARGS = ("-m", "tests.helpers.studio_coach")


def register(test, json_of, chrome) -> None:
    def run(ctx: Ctx) -> dict:
        if not chrome():
            raise SkipTest("no Chrome found (the coach test needs headless Chrome)")
        r, got = json_of(*ARGS)
        ctx.check(f"the run finished, got {r.stdout[-300:]!r} {r.stderr[-600:]!r}", r.returncode == 0 and "failed" not in got)
        return got

    @test
    def test_orchestra_coach_tab_shows_three_cards_in_headless_chrome(ctx: Ctx):
        """3.0.9.0 R3: the Report panel's Coach tab over the seeded finished run: three cards (model, tools,
        structure), each with its why lines and an Apply; the model card's evidence names both lanes."""
        got = run(ctx)
        ctx.check(f"three cards, got {got.get('cards')} {got.get('kinds')}", got.get("cards") == 3
                  and got.get("kinds") == ["model", "structure", "tools"] and got.get("why") == 3 and got.get("applies") == 3)
        ctx.check(f"the model card's why, got {got.get('model_why')!r}", "hit the return cap (2)" in str(got.get("model_why"))
                  and "finished first try" in str(got.get("model_why")))

    @test
    def test_coach_apply_opens_the_bio_form_with_the_model_filled_in(ctx: Ctx):
        """3.0.9.0 R3: Apply on the model card opens Roles on bio coach-cheap's form with or:vendor/strong
        picked, the coach's note naming models.preference and the field marked; the bio on disk is unchanged."""
        got = run(ctx)
        ctx.check(f"the bio form, got {got.get('bio_form')} in {got.get('section')}", got.get("bio_form") == "coach-cheap"
                  and got.get("section") == "roles")
        ctx.check(f"the model filled in and marked, got {got.get('picked')} / {got.get('note_value')} / {got.get('note_field')} "
                  f"/ {got.get('marked')}", got.get("picked") == "or:vendor/strong" and got.get("note_value") == "or:vendor/strong"
                  and got.get("note_field") == "models.preference" and got.get("marked") == 1)
        ctx.check(f"nothing saved, got {got.get('saved_model')}", got.get("saved_model") == "or:vendor/cheap")

    @test
    def test_coach_dismiss_survives_a_reload_and_a_plan_apply_is_staged(ctx: Ctx):
        """3.0.9.0 R3: Dismiss hides the tools card and it stays hidden after a reload (localStorage, "Show
        dismissed (1)"); Apply on the structure card opens the plan editor with job-5 after job-4 staged, no
        Approve or Reject, nothing sent; Back returns to the console."""
        got = run(ctx)
        ctx.check(f"dismissed, got {got.get('after_dismiss')} / {got.get('after_reload')} / {got.get('stored')}",
                  got.get("after_dismiss") == ["model", "structure"] and got.get("after_reload") == ["model", "structure"]
                  and got.get("stored") == ['["tools-3-WebFetch"]'] and got.get("show_dismissed") == "Show dismissed (1)")
        ctx.check(f"staged, got {got.get('staged')!r} / {got.get('staged_edge')} / {got.get('staged_buttons')}",
                  "after: job-4" in str(got.get("staged")) and got.get("staged_edge") == "job-4>job-5"
                  and got.get("staged_buttons") == {"plan-approve": 0, "plan-reject": 0, "plan-copy": 1, "plan-back": 1})
        ctx.check(f"nothing sent, the console back, got {got.get('draft_written')} / {got.get('console_back')}",
                  got.get("draft_written") is False and got.get("console_back") == "back")

    @test
    def test_mission_coach_face_lists_its_cards_in_headless_chrome(ctx: Ctx):
        """3.0.9.0 R3: an ended mission's Coach face lists its five cards (the part asked longer than the
        median, the refused edit, the judged conflict, the part that changed nothing, the missing output)."""
        got = run(ctx)
        ctx.check(f"the mission's cards, got {got.get('mission_face')} {got.get('mission_cards')} {got.get('mission_kinds')}",
                  got.get("mission_face") == "coach" and got.get("mission_cards") == 5
                  and got.get("mission_kinds") == ["coordination", "prompt", "structure", "structure", "tools"])
