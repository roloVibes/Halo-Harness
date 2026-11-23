"""tests.test_studio_flows -- Halo 3.6.0.0 R2: Agents -> 2 · Workflows and its builder in headless Chrome, as a first-time
user (driver tests/helpers/studio_flows.py over tests/helpers/crew_rig.py; skipped without Chrome). The room rules over
this tab at 1280 / 1500 / 1920 are tests/test_studio_room.py's (the `flows` view).

1. the 2 key opens 2 · Workflows: the switch reads 1 · Agents | 2 · Workflows | 3 · Map (3.6.0.0 R5), the list open, the
   five starters, no conversation, no dialog; the empty form says how to start;
2. a starter copied: its steps in the form and drawn; a repeat drawn as a loop mark; a step moved up and back; Save: in
   the list tagged `not on the map`, with the one line that nothing is on a map yet; the file holds the repeat; the
   cost band says what Auto leaves unknown;
3. the steps drawn (R8): fit in their box when the list drawer closes; a zoom by hand survives a drawer; Fit again;
4. the builder: one preview -- the workflow and its steps ticked, the proposed agent's widening lines unticked, the
   card, ghost steps in the form and in the drawing, a ghost row; "make it" fills the agent form, Save comes back with
   its lines out of the preview; Apply writes the workflow; Undo removes it;
5. Write it for me on a saved workflow: the box filled and focused; its step line a ghost step; Discard drops it;
6. Try it: the band first; each step's state and the agents that ran; three checks, the receipt's why; the total;
   marked seen;
7. Delete asks on the page; Keep it; the switch is the four tabs (3.6.0.2 R52), and W (the old board's key) lands on 2 · Workflows;
8. 3.6.0.2 R47: the head line says what a workflow is and where maps are (its Map opens 3 · Map); a workflow main just
   built opens in the form on the next visit (a mounted tab, a fresh page), never over an unsaved edit;
9. 3.6.0.9 V: the workflow open in the form follows its file (a plain write, a Builder card, its own Save, an unsaved
   edit, the file removed), and the list's "on the map" tag follows the maps.
Run: python -m tests.test_studio_flows
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.driver_got import got as driver_got  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
_RUN: dict = {}


def _got(ctx: Ctx) -> dict:
    slow = {"HALO_STUDIO_SLOW_MS": os.environ["HALO_STUDIO_SLOW_MS"]} if os.environ.get("HALO_STUDIO_SLOW_MS") else None
    return driver_got(ctx, "tests.helpers.studio_flows", why="the Workflows tab is driven in headless Chrome", cache=_RUN, timeout=600,
                      env=slow)  # driver_env drops every HALO_ variable: the latency flag is passed on by name


@test
def test_the_2_key_opens_the_workflows_tab(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"2 lands on 2 · Workflows, got {got.get('view')!r}", got.get("view") == "workflows")
    f = got.get("first") or {}
    ctx.check(f"the switch's names, got {f.get('switch')}", f.get("switch") == ["1 · Agents", "2 · Workflows", "3 · Map", "4 · Live"])  # 3.6.0.2 R52: four tabs
    ctx.check(f"the list open, no conversation, no dialog, got {f}", f.get("list") is True and f.get("conversation") is False and f.get("dialogs") == 0)
    ctx.check(f"the five starters, got {f.get('starters')}", f.get("starters") == ["code", "media", "plan", "research", "review"])
    ctx.check(f"the empty form says how to start, got {f.get('empty')!r}", f.get("empty") == "Make your first workflow")


@test
def test_copy_steps_repeat_and_save(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"a starter's copy with its steps, got {got.get('copied')}",
              got.get("copied") == [["Review", "Test"], "A copy of review, not saved yet: it is yours to change, then Save."])
    ctx.check(f"a repeat is drawn as a loop mark, got {got.get('loop')!r}", got.get("loop") == "↺ until the tests pass, ≤3×")
    ctx.check(f"a step moved up, got {got.get('moved')}", got.get("moved") == ["Test", "Review"])
    ctx.check(f"saved: tagged not on the map, the one line, got {got.get('row')}", got.get("row") == ["not on the map", True])
    ctx.check(f"the file holds the steps and the repeat, got {got.get('file')}", got.get("file") == ["Review", "Test", {"until": "the tests pass", "max": 3}])
    ctx.check(f"the band: Auto leaves it unknown until the first run, got {got.get('cost')!r}",
              got.get("cost") == "unknown until the first run: Auto picks the model (reviewer, tester)")


@test
def test_the_steps_drawn_fit_their_box(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"drawn whole in their box, then whole after the drawer closed, got {got.get('before')} {got.get('closed')}",
              (got.get("before") or [0, False])[1] is True and (got.get("closed") or [0, False])[1] is True)
    hand = got.get("hand") or ["", ""]
    ctx.check(f"a zoom by hand survives the drawer opening, got {hand}", hand[0] and hand[0] == hand[1] and hand[0] != (got.get("closed") or [""])[0])
    ctx.check(f"Fit: automatic again, whole, got {got.get('fit')}", (got.get("fit") or [0, False])[1] is True and (got.get("fit") or [""])[0] != hand[0])


@test
def test_the_builder_one_preview_make_it_apply_undo(ctx: Ctx):
    got = _got(ctx)
    ticks = got.get("ticks") or []
    ctx.check(f"the workflow and its steps ticked, the agent's create ticked, its two widening lines unticked, got {ticks}",
              ticks == [["workflow:review-loop", "0", True]] * 3 + [["agent:my-reviewer", "0", True], ["agent:my-reviewer", "1", False], ["agent:my-reviewer", "1", False]])
    ctx.check(f"the proposal card, got {got.get('card')!r}", got.get("card") == "my-reviewer")
    ctx.check(f"a ghost row and two ghost boxes drawn, got {got.get('ghosts')}", got.get("ghosts") == [["review-loop"], 2])
    ctx.check(f"make it: the agent form filled in, nothing beyond reading switched on, got {got.get('made')}",
              (got.get("made") or [""])[0].startswith("Made for the workflow review-loop, not saved yet") and (got.get("made") or ["", ""])[1] == "false")
    ctx.check(f"Save there: back, the agent's lines out of the preview, got {got.get('unticked')}", got.get("unticked") == [False, False, False])
    ctx.check(f"Apply: the workflow, its agents all there, got {got.get('applied')}", got.get("applied") == [["Review", "Test"], [], ["read"]])
    ctx.check(f"Undo: the workflow is gone, got {got.get('undone')}", got.get("undone") == 404)


@test
def test_write_it_for_me_gives_a_ghost_step(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the box filled and focused, got {got.get('prefill')!r}", got.get("prefill") == "Draft the steps from what it is for")
    ctx.check(f"its step line a ghost step in the form and the drawing, got {got.get('ghost')!r}", got.get("ghost") == "Test")
    ctx.check("Discard: the ghost goes", got.get("gone") is True)


@test
def test_try_it_step_by_step(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the band said first, got {got.get('estimate')!r}", "It costs one run: unknown until the first run" in (got.get("estimate") or ""))
    ctx.check(f"done, each step and its agent, got {got.get('state')} {got.get('steps')}",
              got.get("state") == "done" and got.get("steps") == [["1", "done", ["reviewer"]], ["2", "done", ["tester"]]])
    ctx.check(f"three checks, and why it stopped, got {got.get('checks')} {got.get('why')!r}",
              got.get("checks") == 3 and got.get("why") == '3 rounds: at most 3 times: the check never said yes ("the tests pass")')
    ctx.check(f"the total and where it ran, got {got.get('total')!r}", "$0.0000" in (got.get("total") or "") and "throwaway copy of shop" in (got.get("total") or ""))
    ctx.check(f"drawn in view: seen, got {got.get('seen')}", got.get("seen") == [True])


@test
def test_delete_asks_and_the_four_tabs(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the question, got {got.get('ask')!r}", got.get("ask") == "Delete my-review? Its file goes; nothing else changes.")
    ctx.check(f"Keep it: still there, got {got.get('kept')}", got.get("kept") == [True, 200])
    ctx.check(f"four tabs, and W lands on 2 · Workflows, got {got.get('tabs')!r} {got.get('back')!r}",
              got.get("tabs") == ["1 · Agents", "2 · Workflows", "3 · Map", "4 · Live"] and got.get("back") == "my-review")


HEAD = "Workflows are fixed lists of steps. A session runs a map, and a box on a map can run a workflow: see Map."


@test
def test_workflows_head_says_where_maps_are(ctx: Ctx):
    """3.6.0.2 R47: the head line over the main panel, with no workflow open and with one open; its Map opens 3 · Map."""
    got = _got(ctx)
    ctx.check(f"no workflow open: the head line, got {got.get('head_empty')!r}", got.get("head_empty") == HEAD)
    ctx.check(f"a workflow open: the same line, got {got.get('head_open')!r}", got.get("head_open") == HEAD)
    ctx.check(f"its Map lands on 3 · Map, got {got.get('head_map')!r}", got.get("head_map") == "map")


@test
def test_built_workflow_opens_next_visit(ctx: Ctx):
    """3.6.0.2 R47: a workflow main just built (a builder_done frame) is open in the form on the next Workflows visit."""
    got = _got(ctx)
    ctx.check(f"the page heard the frame, got {got.get('heard')!r}", got.get("heard") == "my-review")
    ctx.check(f"a mounted tab, left and come back to: the built one open, got {got.get('mounted')!r}", got.get("mounted") == "my-review")
    ctx.check(f"P4 batch 12: a NEW one built while away, back before the list was read (the read held): not listed yet "
              f"{got.get('new_listed_before')!r}, open after the read, got {got.get('new_after_read')!r}",
              got.get("new_heard") == "brand-new" and got.get("read_asked") is True and got.get("new_listed_before") is False and got.get("new_after_read") == "brand-new")
    ctx.check(f"an unsaved edit: the form keeps it, the list marks the built one, got {got.get('dirty')}",
              got.get("dirty") == ["other", "edited here", "1"])
    ctx.check(f"P8: that was read after his return was handled (the remembered name taken: the event), got {got.get('dirty_read')!r}",
              got.get("dirty_read") is True)
    ctx.check(f"a fresh page on Session heard it and stayed there, got {got.get('fresh_heard')!r} {got.get('fresh_section')!r}",
              got.get("fresh_heard") == "other" and "Session" in (got.get("fresh_section") or ""))
    ctx.check(f"Workflows never opened in that page: it opens on the built one, got {got.get('fresh')!r}",
              got.get("fresh") == "other" and got.get("fresh_part") is True)


@test
def test_the_open_workflow_follows_its_file(ctx: Ctx):
    """3.6.0.9 V (the owner's point 34): the workflow open in the form is the one on disk, whoever wrote it."""
    f = _got(ctx).get("follows") or {}
    ctx.check(f"(1) a plain write: the form shows the file's steps and words, got {f.get('plain')}", f.get("plain") == [["a", "b", "c"], "followed"])
    ctx.check(f"(2) a Builder card's write of the open one, left and come back: the file's, got {f.get('built')}",
              f.get("built") == [["a", "b", "c", "d"], "built"])
    ctx.check(f"(e) its own Save, come back from the watcher ({f.get('own_frame')}): no read, no line, got {f.get('own_save')}",
              f.get("own_frame") is True and f.get("own_save") == {"reads": 0, "line": False, "for": "saved here"})
    ctx.check(f"(3) an unsaved edit: kept, the steps kept, the line and its button, got {f.get('dirty')}",
              f.get("dirty") == {"line": "my-review changed on disk while you had edits here. Save writes yours over it.",
                                 "for": "typed by hand", "kept": True, "button": "Reload it (your edits go)"})
    ctx.check(f"(3) Reload reads the file's version, got {f.get('reloaded')}", f.get("reloaded") == [["a", "b", "c", "d", "e"], "on disk", False])
    r = f.get("removed") or {}
    ctx.check(f"(d) removed: the form stays with the line, no Reload, got {r}",
              r.get("line") == "my-review was removed on disk. Save writes it again." and r.get("form") == "my-review"
              and r.get("steps") == ["a", "b", "c", "d", "e"] and r.get("reload") is False)
    ctx.check(f"(d) Save writes it again, the line goes, got {f.get('written_again')}", f.get("written_again") == [True, False])
    ctx.check(f"(f) a map file putting it on a box: the list's tag follows, got {f.get('tag_before')!r} -> {f.get('tag_after')!r}",
              f.get("tag_before") == "unused" and f.get("tag_after") == "on")
    ctx.check(f"(f) by the map alone: every earlier workflow write had been heard before it, and the marker left "
              f"again, got {f.get('settled')!r} {f.get('settled_left')!r}",
              f.get("settled") is True and f.get("settled_left") is False)


_PACK: dict = {}
PACK_LINE = "From the pack doc-review: read-only here. Copy makes it yours."


def _pack(ctx: Ctx) -> dict:
    return driver_got(ctx, "tests.helpers.studio_flows_pack", why="a pack's items are driven in headless Chrome", cache=_PACK, timeout=400)


@test
def test_a_packs_workflow_is_the_packs_and_read_only(ctx: Ctx):
    """3.6.0.6 P: with doc-review enabled, its workflow sits under "From packs" (after Yours, before the ones that ship
    with Halo), tagged "pack doc-review"; its form says it is read-only, Save off, no Delete; Copy makes his own."""
    got = _pack(ctx)
    ctx.check(f"the groups in order, got {got.get('groups')}", got.get("groups") == ["Yours", "From packs", "Ships with Halo · Copy makes it yours"])
    ctx.check(f"the pack's row under From packs, tagged, got {got.get('group')!r} {got.get('tag')!r} {got.get('scope')!r}",
              got.get("group") == "From packs" and got.get("tag") == "pack doc-review" and got.get("scope") == "pack")
    f = got.get("form") or {}
    ctx.check(f"its form: the line, Save off, no Delete, Copy, got {f}", f.get("line") == PACK_LINE and f.get("save") is True
              and f.get("delete") is False and f.get("copy") is True)
    pf = got.get("pack_follows") or []
    ctx.check(f"3.6.0.9 V (4): the pack's workflow changed, its read-only form shows the new steps, got {pf}",
              len(pf) == 3 and pf[0] is True and (pf[1] or [""])[-1] == "pack-new-step" and pf[2] is True)
    cp = got.get("copy") or {}
    ctx.check(f"Copy: his own my-review-docs, open to edit, got {cp}", cp.get("name") == "my-review-docs" and cp.get("save") is False
              and cp.get("line") is False)
    ctx.check(f"Save wrote his copy and nothing under the pack's name, got {got.get('copy_file')} {got.get('pack_file')}",
              got.get("copy_file") is True and got.get("pack_file") is False)


@test
def test_a_packs_agent_and_the_maps_list_say_the_pack(ctx: Ctx):
    got = _pack(ctx)
    ctx.check(f"the Agents list tags the pack's agent, got {got.get('agent_tag')!r}", got.get("agent_tag") == "pack doc-review")
    a = got.get("agent_form") or {}
    # 3.6.0.15 O2-6: the server's `writable` false takes Save (and Discard, Delete) away from a pack's form
    ctx.check(f"its form: the line, no Save, no Delete, got {a}", a.get("line") == PACK_LINE and a.get("save") is False and a.get("delete") is False)
    tags = got.get("map_tags") or []
    ctx.check(f"the Map's add list tags the pack's workflow and agents, got {tags}",
              len(tags) >= 3 and all(tag == "pack doc-review" for _ref, tag in tags))
    ctx.check(f"no page error, the driver ran to the end, got {got.get('page_errors')} {got.get('failed')}",
              got.get("page_errors") == [] and "failed" not in got)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
