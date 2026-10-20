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
        ctx.check(f"3.1.3.0: Ask, Apply and Edit on each card, and the help line, got {got.get('asks')} {got.get('edits')}",
                  got.get("asks") == 3 and got.get("edits") == 3 and "writes after you confirm" in str(got.get("help")))
        ctx.check(f"the model card's why, got {got.get('model_why')!r}", "hit the return cap (2)" in str(got.get("model_why"))
                  and "finished first try" in str(got.get("model_why")))

    @test
    def test_coach_apply_opens_the_bio_form_with_the_model_filled_in(ctx: Ctx):
        """3.0.9.0 R3 (Edit since 3.1.3.0): Edit on the model card opens Roles on bio coach-cheap's form with or:vendor/strong
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
        dismissed (1)"); Edit on the structure card opens the plan editor with job-5 after job-4 staged, no
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
    def test_coach_apply_confirms_writes_and_undoes_in_headless_chrome(ctx: Ctx):
        """3.1.3.0 R1: Apply on the model card shows the confirm card (bio coach-cheap's file, the diff to
        or:vendor/strong) and writes nothing; Apply there writes the bio (APPLIED, "1 applied"); Undo puts
        it back (UNDONE); Ask the model shows the lead's paragraph, kept in the run's coach.ask.json."""
        got = run(ctx)
        ctx.check(f"the confirm card, got {got.get('confirm_file')!r} {got.get('confirm_diff')!r}",
                  str(got.get("confirm_file")).endswith("coach-cheap.yaml") and "+  preference: or:vendor/strong"
                  in str(got.get("confirm_diff")) and got.get("before_confirm") == "or:vendor/cheap")
        ctx.check(f"written, got {got.get('applied_chip')} {got.get('after_apply')} {got.get('summary')!r}",
                  got.get("applied_chip") == "APPLIED" and got.get("after_apply") == "or:vendor/strong"
                  and "1 applied" in str(got.get("summary")))
        ctx.check(f"undone, got {got.get('undone_chip')} {got.get('after_undo')}", got.get("undone_chip") == "UNDONE"
                  and got.get("after_undo") == "or:vendor/cheap")
        ctx.check(f"the lead's paragraph, got {got.get('paragraph')!r}", str(got.get("paragraph")).startswith("The fake lead on")
                  and got.get("ask_kept") is True)

    @test
    def test_coach_probe_button_shows_the_cost_runs_and_leads_with_its_table(ctx: Ctx):
        """3.1.6.0 R2: Probe in the Coach tab's header row opens the confirm with the cost line ("probe: 2 runs, up to
        $0.0345") and runs nothing; Run the probe runs it beside the console; the probe's card then leads the tab with
        the contrast table (the run itself first, then the two candidates) and the judge's paragraph; one run listed."""
        got = run(ctx)
        ctx.check(f"the button and the cost line, got {got.get('probe_button')} {got.get('probe_cost')!r}",
                  got.get("probe_button") is True and str(got.get("probe_cost")).startswith("probe: 2 runs, up to $0.0345")
                  and got.get("probe_ran_before") is False)
        ctx.check(f"the card and its table, got {got.get('probe_rows')} {got.get('probe_first')} {got.get('probe_reference')} "
                  f"{got.get('probe_judge')} {got.get('probe_listed')}", got.get("probe_rows") == 3 and got.get("probe_first") == "probe"
                  and got.get("probe_reference") == "reference" and got.get("probe_judge") == "THE JUDGE" and got.get("probe_listed") == 1)

    @test
    def test_mission_coach_face_lists_its_cards_in_headless_chrome(ctx: Ctx):
        """3.0.9.0 R3: an ended mission's Coach face lists its five cards (the part asked longer than the
        median, the refused edit, the judged conflict, the part that changed nothing, the missing output)."""
        got = run(ctx)
        ctx.check(f"the mission's cards, got {got.get('mission_face')} {got.get('mission_cards')} {got.get('mission_kinds')}",
                  got.get("mission_face") == "coach" and got.get("mission_cards") == 5
                  and got.get("mission_kinds") == ["coordination", "prompt", "structure", "structure", "tools"])
