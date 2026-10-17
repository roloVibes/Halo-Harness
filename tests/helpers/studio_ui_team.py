"""tests.helpers.studio_ui_team -- the Team tab checks of tests/test_studio_ui.py
(Halo 3.0.8.0 round R2), kept here so that file stays small. One headless
Chrome run (`python -m tests.helpers.studio_team`, tests/helpers/studio_team.py)
over the Studio Team rig and team_rig's fakes (no model call); the runner
caches it, so the four tests read one run."""
from __future__ import annotations

from tests.helpers.runner import Ctx, SkipTest

ARGS = ("-m", "tests.helpers.studio_team")


def register(test, json_of, chrome) -> None:
    def run(ctx: Ctx) -> dict:
        if not chrome():
            raise SkipTest("no Chrome found (the Team test needs headless Chrome)")
        r, got = json_of(*ARGS)
        ctx.check(f"the run finished, got {r.stdout[-300:]!r} {r.stderr[-600:]!r}", r.returncode == 0 and "failed" not in got)
        return got

    @test
    def test_team_board_draws_and_run_reaches_the_gate_in_headless_chrome(ctx: Ctx):
        """3.0.8.0 R2: the seeded team draws three member columns, four stage boxes, three
        block nodes and eight edges (two stage_done, two reads, three writes, one
        block_change); Run on draft turns it running (copy amber, the writer's agent
        chip), then gated, the gate card opens and the status bar's TEAM cell says so."""
        got = run(ctx)
        ctx.check(f"the board, got {got.get('board')} / {got.get('edge_kinds')}",
                  got.get("board") == {"team-member": 3, "team-stage": 4, "team-block": 3, "team-edge": 8}
                  and got.get("edge_kinds") == ["change", "done", "done", "reads", "reads", "writes", "writes", "writes"])
        ctx.check(f"running, then gated, got {got.get('draft_running')} / {got.get('copy_writing')} / {got.get('agent_chip')} / {got.get('draft_gated')}",
                  got.get("draft_running") == "running" and got.get("copy_writing") == "writing" and got.get("agent_chip") == "draft"
                  and got.get("draft_gated") == "gated")
        ctx.check(f"the gate card and the TEAM cell, got {got.get('gate_card')} / {got.get('status_team')!r}",
                  got.get("gate_card") == "draft" and "1 at a gate" in str(got.get("status_team")))

    @test
    def test_team_gate_in_fleet_attention_opens_the_section(ctx: Ctx):
        """3.0.8.0 R2: the gated stage is a team_gate row in Fleet's Attention queue; `o`
        opens the Team section on that stage, its gate card showing."""
        got = run(ctx)
        ctx.check(f"the row, got {got.get('attn_row')!r}", "stage draft waits at its gate" in str(got.get("attn_row")))
        ctx.check(f"o opens Team on draft, got {got.get('attn_open')} / {got.get('attn_section')!r}",
                  got.get("attn_open") == "draft" and str(got.get("attn_section")).startswith("Team"))

    @test
    def test_team_accept_lights_the_edge_and_a_block_change_fires(ctx: Ctx):
        """3.0.8.0 R2: Accept runs review (the stage_done:draft edge lights, review's change
        line lands in the feed), then post waits at its gate; a hand edit of NOTES.md turns
        the notes badge amber, its change line lands in the feed and build fires after the
        5 s settle window; released, the badge is free again."""
        got = run(ctx)
        ctx.check(f"review ran, the edge lit, its change line, got {got.get('review_running')} / {got.get('edge_lit')} / {got.get('review_change')!r}",
                  got.get("review_running") == "running" and got.get("edge_lit") == "lit" and "writer@review" in str(got.get("review_change"))
                  and got.get("review_done") == "done" and got.get("post_gated") == "gated")
        ctx.check(f"the block change, got {got.get('touch')} / {got.get('notes_amber')} / {got.get('notes_change')!r}",
                  got.get("touch") == "allow" and got.get("notes_amber") == "writing" and "NOTES.md" in str(got.get("notes_change")))
        ctx.check(f"build fired after the settle window, got {got.get('build_fired')} after {got.get('build_after_s')} s / {got.get('build_trigger')!r}",
                  got.get("build_fired") in ("running", "done") and (got.get("build_after_s") or 0) >= 3 and "block notes changed" in str(got.get("build_trigger"))
                  and got.get("notes_released") == "free")

    @test
    def test_team_stop_ends_the_run(ctx: Ctx):
        """3.0.8.0 R2: Stop asks for a reason on a card; the run ends stopped with that
        reason and the stage that waited (post) is skipped."""
        got = run(ctx)
        ctx.check(f"stopped, got {got.get('stopped')} / {got.get('post_after')} / {got.get('stop_reason')!r}",
                  got.get("stopped") == "stopped" and got.get("post_after") == "skipped" and got.get("stop_reason") == "enough for today")
