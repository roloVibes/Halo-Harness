"""tests.helpers.studio_ui_fleet_layout -- the Fleet layout checks of tests/test_studio_ui.py
(Halo 3.1.4.0 R1, from the owner's live check of 3.1.3.0: the Activity log line
"main running; Bash; sleep" drawn as a column of single letters, and the view
"really busy"). They read tests/helpers/studio_fleet_layout.py (`layout`,
`widths`, `mission`): one harness, one live session whose main agent runs with
a 40-character state text, Fleet at the default layout in a fresh profile.
tests/test_studio_ui.py calls `register` with its registry, its cached runner
and its Chrome finder."""
from __future__ import annotations

from tests.helpers.runner import Ctx, SkipTest

OPEN = ("fleet-people", "fleet-costs", "fleet-attention", "fleet-map", "fleet-activity")
STRIPS = ("fleet-health", "fleet-capabilities", "fleet-agent", "fleet-mission")
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
        """3.1.4.0 R1: at the default layout the state line `STATE rolo@kali · main` keeps a text column of
        at least 160 px and at most two rows; in the owner's 3.1.3.0 width (Activity five columns, a saved
        arrangement) time, kind and who share one row and the text takes the full width under them. No
        text in any Fleet panel wraps in a column under 100 px (a walk over every element with text), at the
        default and with every strip open; the timeline draws its lane names at full size (one unit per px)."""
        got = run(ctx, "widths")
        log = got.get("log") or {}
        ctx.check(f"the log line is the 40-character state text, got {log.get('text')!r} / {log.get('who')!r}",
                  "Bash; sleep 40 while the test build runs" in str(log.get("text")) and log.get("who") == "rolo@kali · main")
        ctx.check(f"its text column is at least 160 px wide and at most two rows, got {log}", (log.get("w") or 0) >= 160 and 1 <= (log.get("rows") or 0) <= 2)
        ctx.check(f"time, kind and who on one row, got {log}", log.get("head_one_row") is True)
        ctx.check(f"no text wraps in a column under 100 px at the default layout, got {got.get('narrow')}", got.get("narrow") == [])
        ctx.check(f"nor with Health, Capabilities, Agent and Mission open, got {got.get('narrow_opened')}", got.get("narrow_opened") == [])
        ctx.check(f"every panel opens on its full face, Costs too (its cap rows once re-rendered forever), got {got.get('expanded')}",
                  sorted((got.get("expanded") or {}).values()) == ["detail"] * 9)
        ctx.check(f"nor with every panel on its full face (People and Costs rows, Health, the spec cards), got {got.get('narrow_expanded')}",
                  got.get("narrow_expanded") == [])
        svg = got.get("svg") or {}
        ctx.check(f"the timeline at one unit per px (its 116-unit name column >= 100 px), the map unscaled, got {svg}",
                  (svg.get("timeline") or 0) * 116 >= 100 and (svg.get("map") or 0) >= 0.95)
        lay = run(ctx, "layout")
        old = lay.get("old_log") or {}
        ctx.check(f"the 3.1.3.0 width: the log is narrow, got {old.get('log_w')}", 0 < (old.get("log_w") or 0) < 440)
        ctx.check(f"there the text takes the full width under one head row, >= 160 px, at most two rows, got {old}",
                  old.get("text_below") is True and old.get("head_one_row") is True and (old.get("w") or 0) >= 160 and 1 <= (old.get("rows") or 0) <= 2)

    @test
    def test_fleet_default_layout_opens_five_panels_in_headless_chrome(ctx: Ctx):
        """3.1.4.0 R1: a fresh Fleet workspace opens People, Costs, Attention, Map and Activity; Health,
        Capabilities, Agent and Mission are title strips down the right edge (the header's "+" marks them "strip"),
        each opened by ONE click on the chevron of its title bar ("Open the panel"), in that column, with no
        panel over another; Reset layout (the header's ... menu) brings the default back and forgets the saved key; picking
        an agent on the map opens Agent and moves neither the map nor Activity; an arrangement saved before
        (the 3.1.3.0 default, all nine open) is kept as it was and not rewritten."""
        got = run(ctx, "layout")
        fresh = got.get("fresh") or {}
        ctx.check(f"exactly the five panels open, got {_open_ids(fresh)}", _open_ids(fresh) == sorted(OPEN))
        ctx.check(f"the other four as strips, got {_strip_ids(fresh)}", _strip_ids(fresh) == sorted(STRIPS))
        right = {fresh.get(k, {}).get("x") for k in STRIPS}
        ctx.check(f"the strips share the right-hand column, right of every open panel, got {right}",
                  len(right) == 1 and all(fresh[k]["x"] + fresh[k]["w"] <= min(right) for k in OPEN))
        ctx.check(f"nothing saved for a fresh workspace, got {got.get('saved_fresh')!r}", got.get("saved_fresh") is None)
        ctx.check(f"the header's + menu lists the four as strips, got {got.get('rail_strips')}", sorted(got.get("rail_strips") or []) == ["Agent", "Capabilities", "Health", "Mission"])
        opened = got.get("opened") or {}
        for pid in STRIPS:
            o = opened.get(pid) or {}
            p = (o.get("panels") or {}).get(pid) or {}
            ctx.check(f"one click on {pid}'s chevron opens it in its column, no overlap, got {p} / {o.get('overlaps')}",
                      p.get("body") is True and not p.get("collapsed") and p.get("x") in right and o.get("overlaps") == [])
        ctx.check("opening a strip is a change of yours: it is saved", got.get("saved_after_open") is True)
        reset = got.get("after_reset") or {}
        ctx.check(f"Reset layout: the five open and the four strips again, got {_open_ids(reset)}",
                  _open_ids(reset) == sorted(OPEN) and _strip_ids(reset) == sorted(STRIPS))
        pick = got.get("after_pick") or {}
        pp = pick.get("panels") or {}
        ctx.check(f"picking an agent opens Agent, got {pp.get('fleet-agent')}", (pp.get("fleet-agent") or {}).get("body") is True)
        ctx.check(f"and the map and Activity stay put, nothing overlaps, got {pick.get('overlaps')}",
                  all(pp.get(k, {}).get(f) == fresh.get(k, {}).get(f) for k in ("fleet-map", "fleet-activity") for f in "xywh") and pick.get("overlaps") == [])
        old = got.get("old_saved") or {}
        ctx.check(f"a saved 3.1.3.0 arrangement opens as it was: all nine, Mission under the map, got {_open_ids(old)}",
                  len(_open_ids(old)) == 9 and old.get("fleet-mission", {}).get("x") == old.get("fleet-map", {}).get("x")
                  and old.get("fleet-mission", {}).get("y", 0) > old.get("fleet-map", {}).get("y", 0))
        ctx.check("and its saved key is left as it was (not migrated)", got.get("old_kept") is True)

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
        """3.1.4.0 R1: every caption on a compact face (the hint, the labels under the metrics, the kicker and
        the small lines) is at least 12 px, on the two open by default and on all nine turned compact, and no
        compact face clips at its panel's default height."""
        got = run(ctx, "widths")
        g, a = got.get("glance") or {}, got.get("all_glance") or {}
        ctx.check(f"People and Costs: nothing under 12 px, got {g}", g.get("least", 0) >= 12 and g.get("small") == [] and len(g.get("faces") or []) == 2)
        ctx.check(f"all nine compact: nothing under 12 px, got {a}", a.get("least", 0) >= 12 and a.get("small") == [] and len(a.get("faces") or []) == 9)
        ctx.check(f"no compact face clips, got {got.get('glance_overflow')} / {got.get('all_glance_overflow')}",
                  got.get("glance_overflow") == [] and got.get("all_glance_overflow") == [])
