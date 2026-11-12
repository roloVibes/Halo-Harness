"""tests.test_studio_live_truth -- Agents -> Live, truth first (Halo 3.3.18.0 "The living canvas", the owner: "I always
see like unused older version of orchestrations that aren't even happening when I look at it"), in headless Chrome
through tests/helpers/studio_live_truth.py (skipped without one); no model call:

1. nothing live: a bare ?mode=agents lands on Live's one empty sentence and its two actions; no node, no old run; History
   closed on load;
2. an ended session and an old Orchestra run are not on the canvas and are History's rows, newest first, each with what
   it was, when, how long, its cost and how it ended;
3. a row opens a replay: the banner, muted nodes, no live colour; Back to now clears it;
4. the empty state's actions: Replay the last session; Open the plan (Cast), whose bar says the lineup new sessions use;
5. with an agent live Agents opens on Live (Alt+2); a named door still wins; Cast's "N live" chip and the rail badge count
   live agents only;
6. an agent that finishes leaves after its stated ten seconds and its group with it; a failed one stays until dismissed;
   a failure from before the page loaded is not drawn.
Run: python -m tests.test_studio_live_truth
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.driver_got import got as driver_got  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
_RUN: dict = {}
LINE = "Nothing is running. Start a session, or open the last one as a replay."


def _past(ctx: Ctx) -> dict:
    return driver_got(ctx, "tests.helpers.studio_live_truth", why="Live's truth needs headless Chrome", cache=_RUN, key="past", args=("past",), timeout=300)


def _now(ctx: Ctx) -> dict:
    return driver_got(ctx, "tests.helpers.studio_live_truth", why="Live's truth needs headless Chrome", cache=_RUN, key="now", args=("now",), timeout=420)


@test
def test_nothing_live_is_one_sentence_and_two_actions(ctx: Ctx):
    got = _past(ctx)
    ctx.check(f"a bare door lands on Live, got {got.get('view')!r}", got.get("view") == "live")
    ctx.check(f"the one sentence, got {got.get('line')!r}", got.get("line") == LINE)
    ctx.check(f"its two actions, got {got.get('actions')}", got.get("actions") == ["Open the plan (Cast)", "Replay the last session"])
    ctx.check(f"no node, no run, History closed, the badge 0, got {got.get('nodes')} {got.get('leads')} {got.get('drawer_on_load')} {got.get('rail_count')}",
              got.get("nodes") == 0 and got.get("leads") == 0 and got.get("drawer_on_load") is False and got.get("rail_count") == "0")


@test
def test_the_past_is_in_history_newest_first(ctx: Ctx):
    got = _past(ctx)
    rows = got.get("rows") or []
    ctx.check(f"two rows, got {got.get('count')} {rows}", got.get("count") == 2 and len(rows) == 2)
    ctx.check(f"the run (now) first, the session (an hour ago) second, got {[r[:2] for r in rows]}",
              [r[:2] for r in rows] == [["run", got.get("run")], ["session", got.get("past_sid")]])
    facts = {r[0]: r[2] for r in rows}
    ctx.check(f"each row: kind, when, how long, cost, how it ended, got {facts}",
              str(facts.get("session", "")).startswith("session · 1 h ago · ") and str(facts.get("session", "")).endswith("· $0.0200 · closed")
              and str(facts.get("run", "")).startswith("goal run · just now") and str(facts.get("run", "")).endswith("· finished"))


@test
def test_a_row_opens_a_replay_and_back_to_now(ctx: Ctx):
    got = _past(ctx)
    for kind, n in (("session", 2), ("run", 6)):
        r = got.get(f"replay_{kind}") or {}
        drawn = r.get("drawn") or []
        ctx.check(f"{kind}: the banner says replay, the moment drawn (3.4.1.0 R1: its end) and when it ended, got {r.get('banner')!r}",
                  str(r.get("banner", "")).startswith("replay -- ") and "ended " in str(r.get("banner", "")) and str(r.get("banner", "")).endswith("Back to now"))
        ctx.check(f"{kind}: {n} muted nodes, no live colour, got {drawn}",
                  len(drawn) == n and all(d[2] == "" and "grayscale" in d[3] for d in drawn))
        ctx.check(f"{kind}: the drawer closed behind it; Back to now clears it, got {r.get('drawer_closed')} {r.get('back')!r}",
                  r.get("drawer_closed") is True and r.get("back") == "now")


@test
def test_the_empty_states_actions_and_casts_plan_line(ctx: Ctx):
    got = _past(ctx)
    ctx.check(f"Replay the last session opens the newest session, got {got.get('replay_last')!r}", got.get("replay_last") == got.get("past_sid"))
    ctx.check(f"Open the plan lands on Cast, got {got.get('plan')!r}", got.get("plan") == "cast")
    ctx.check(f"Cast's line, no live chip, got {got.get('plan_line')!r} {got.get('live_chip')}",
              got.get("plan_line") == "the lineup new sessions use: auto (default)" and got.get("live_chip") is False)
    ctx.check(f"no step failed, got {got.get('failed')}", not got.get("failed"))


@test
def test_live_agents_open_on_live_and_a_named_door_wins(ctx: Ctx):
    got = _now(ctx)
    ctx.check(f"Alt+2 lands on Live, got {got.get('alt2')!r}", got.get("alt2") == "live")
    ctx.check(f"?view=cast and ?mode=roles land on Cast, got {got.get('door_cast')!r} {got.get('door_roles')!r}",
              got.get("door_cast") == "cast" and got.get("door_roles") == "cast")


@test
def test_casts_live_chip_and_the_rail_count_live_only(ctx: Ctx):
    got = _now(ctx)
    n = got.get("want_live")
    ctx.check(f"the plan line, got {got.get('plan_line')!r}", got.get("plan_line") == "the lineup new sessions use: halo-dev-cycle")
    ctx.check(f"the chip says {n} live, got {got.get('chip')!r}", isinstance(n, int) and n >= 3 and got.get("chip") == f"{n} live -- see Live")
    ctx.check(f"the rail badge is the same count, got {got.get('rail')}", got.get("rail") == n)
    ctx.check(f"the chip goes to Live, got {got.get('chip_goes')!r}", got.get("chip_goes") == "live")


@test
def test_a_finished_agent_leaves_and_its_group_with_it(ctx: Ctx):
    got = _now(ctx)
    ctx.check(f"the group of two, drawn done, got {got.get('group')} {got.get('done_drawn')!r}", got.get("group") == 2 and got.get("done_drawn") == "done")
    ctx.check(f"still there after 4 s, got {got.get('still_at_4s')}", got.get("still_at_4s") is True)
    s = got.get("left_after_s")
    ctx.check(f"gone with its group after its ten seconds, got {s}", isinstance(s, (int, float)) and 9 <= s <= 18)
    ctx.check(f"a live sibling stays, got {got.get('others_stay')}", got.get("others_stay") is True)


@test
def test_a_failed_agent_stays_until_dismissed(ctx: Ctx):
    got = _now(ctx)
    ctx.check(f"failed, still there after 13 s, got {got.get('failed_state')!r} {got.get('after_13s')!r}",
              got.get("failed_state") == "failed" and got.get("after_13s") == "failed")
    ctx.check(f"the dismiss says what it does, got {got.get('dismiss_title')!r}", str(got.get("dismiss_title", "")).startswith("Seen: take fixer, which failed, off the canvas"))
    ctx.check(f"dismissed, it leaves; after a reload it is past, got {got.get('dismissed')!r} {got.get('after_reload')}",
              got.get("dismissed") == "gone" and got.get("after_reload") is False)
    ctx.check(f"no step failed, got {got.get('failed')}", not got.get("failed"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
