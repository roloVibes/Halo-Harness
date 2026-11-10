"""tests.helpers.studio_ui_fleet_layout -- the fleet layout checks of tests/test_studio_ui.py
(Halo 3.1.4.0 R1, from the owner's live check of 3.1.3.0: the Activity log line
"main running; Bash; sleep" drawn as a column of single letters, and the view
"really busy"; 3.3.16.0 R2 "the Fleet fold": the Fleet workspace went, so they read Agents -> Live, where its
pieces are). They read tests/helpers/studio_fleet_layout.py (`layout`,
`widths`, `mission`): one harness, one live session whose main agent runs with
a 40-character state text, Live at its default in a fresh profile.
tests/test_studio_ui.py calls `register` with its registry, its cached runner
and its Chrome finder."""
from __future__ import annotations

from tests.helpers.runner import Ctx, SkipTest

OPEN = ("roles-graph",)  # 3.3.16.0 R2: one thing open on load, the tree; the rest strips
STRIPS = ("roles-bios", "roles-inspector", "roles-lineups", "roles-models", "roles-problems")
HELPER = ("-m", "tests.helpers.studio_fleet_layout")


def _open_ids(panels: dict) -> list:
    return sorted(k for k, p in (panels or {}).items() if not p.get("collapsed") and p.get("body"))


def _strip_ids(panels: dict) -> list:
    return sorted(k for k, p in (panels or {}).items() if p.get("collapsed") and not p.get("body"))


def register(test, json_of, chrome) -> None:
    def run(ctx: Ctx, mode: str) -> dict:
        if not chrome():
            raise SkipTest("no Chrome found (the Fleet layout test needs headless Chrome)")
        r, got = json_of(*HELPER, mode)
        ctx.check(f"the {mode} run finished, got {r.stdout[-300:]!r} {r.stderr[-600:]!r}", r.returncode == 0 and not got.get("failed"))
        return got


    @test
    def test_fleet_log_line_keeps_its_text_column_in_headless_chrome(ctx: Ctx):
        """3.1.4.0 R1 (3.3.16.0 R2: Activity is Live's optional panel): the state line `STATE rolo@kali · main` keeps a
        text column of at least 160 px on one or two rows with time, kind and who on one row. No text in Live's panels
        or the Attention queue wraps in a column under 100 px (a walk over every element with text), at the default and
        with the queue open and an agent picked; the timeline draws its lane names at full size (one unit per px)."""
        got = run(ctx, "widths")
        log = got.get("log") or {}
        ctx.check(f"the log line is the 40-character state text, got {log.get('text')!r} / {log.get('who')!r}",
                  "Bash; sleep 40 while the test build runs" in str(log.get("text")) and log.get("who") == "rolo@kali · main")
        ctx.check(f"its text column is at least 160 px wide and at most two rows, got {log}", (log.get("w") or 0) >= 160 and 1 <= (log.get("rows") or 0) <= 2)
        ctx.check(f"time, kind and who on one row, got {log}", log.get("head_one_row") is True)
        ctx.check(f"no text wraps in a column under 100 px at the default, got {got.get('narrow')}", got.get("narrow") == [])
        ctx.check(f"nor with the queue open and an agent picked, got {got.get('narrow_opened')}", got.get("narrow_opened") == [])
        svg = got.get("svg") or {}
        ctx.check(f"the timeline at one unit per px (its 116-unit name column >= 100 px), got {svg}", (svg.get("timeline") or 0) * 116 >= 100)

    @test
    def test_fleet_default_layout_opens_five_panels_in_headless_chrome(ctx: Ctx):
        """3.1.4.0 R1 (3.3.16.0 R2: the fleet is Agents -> Live): a fresh Live opens the tree and nothing else -- its other
        panels are strips, Activity and the Attention queue are not on the page; the header's "+" adds Activity (its row
        says add) and that is saved; Reset layout (the ... menu) brings the default back and forgets the saved key;
        picking an agent opens the inspector beside the tree."""
        got = run(ctx, "layout")
        fresh = got.get("fresh") or {}
        ctx.check(f"only the tree open, got {_open_ids(fresh)}", _open_ids(fresh) == sorted(OPEN))
        ctx.check(f"the others as strips, got {_strip_ids(fresh)}", _strip_ids(fresh) == sorted(STRIPS))
        ctx.check(f"Activity and the queue closed on load, got {got.get('closed_on_load')}", got.get("closed_on_load") == [True, True])
        ctx.check(f"nothing saved for a fresh workspace, got {got.get('saved_fresh')!r}", got.get("saved_fresh") is None)
        ctx.check(f"the + menu adds Activity, got {got.get('plus_activity')!r} / {got.get('added')}",
                  got.get("plus_activity") == "add" and (got.get("added") or {}).get("body") is True)
        ctx.check("adding it is a change of yours: it is saved", got.get("saved_after_add") is True)
        reset = got.get("after_reset") or {}
        ctx.check(f"Reset layout: the tree open, the strips again, Activity gone, got {_open_ids(reset)}",
                  _open_ids(reset) == sorted(OPEN) and _strip_ids(reset) == sorted(STRIPS) and "fleet-activity" not in reset)
        pick = got.get("after_pick") or {}
        ctx.check(f"picking an agent opens the inspector beside the tree, got {pick}",
                  (pick.get("inspector") or {}).get("body") is True and pick.get("graph_open") is True)

    @test
    def test_fleet_mission_how_it_works_folds_in_headless_chrome(ctx: Ctx):
        """3.1.4.0 R1: with no goal text and no mission the Mission panel shows its five how-it-works lines in
        full; once a goal is typed they fold into one "How this works" line that opens on click; with a mission
        in the list they start folded."""
        got = run(ctx, "mission")
        empty, typed, opened, kept = (got.get(k) or {} for k in ("empty", "typed", "opened", "with_mission"))
        ctx.check(f"no goal, no mission: the five lines in full, no fold line, got {empty}", empty.get("shown") == 5 and empty.get("fold") is False)
        ctx.check(f"a goal typed: one closed How this works line, the lines hidden, got {typed}",
                  typed.get("fold") is True and typed.get("open") is False and typed.get("shown") == 0 and typed.get("summary") == "How this works")
        ctx.check(f"a click on it shows the five lines, got {opened}", opened.get("open") is True and opened.get("shown") == 5)
        ctx.check(f"a mission in the list, no goal text: folded, got {kept} / {got.get('goal_empty')}",
                  kept.get("fold") is True and kept.get("shown") == 0 and got.get("goal_empty") is True)


    @test
    def test_fleet_glance_text_at_12px_in_headless_chrome(ctx: Ctx):
        """3.1.4.0 R1 (3.3.16.0 R2: the fleet at a glance is Live's inspector with nothing picked): every caption on it
        is at least 12 px and no line clips."""
        got = run(ctx, "widths")
        g = got.get("glance") or {}
        ctx.check(f"the glance: nothing under 12 px, got {g}", g.get("glance") is True and g.get("least", 0) >= 12 and g.get("small") == [])
        ctx.check(f"no glance line clips, got {got.get('glance_overflow')}", got.get("glance_overflow") == [])
