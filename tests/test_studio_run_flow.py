"""tests.test_studio_run_flow -- Halo 3.6.0.6 P (batch 2, entries 2 and 3; the owner's point 31: "pack workflows should
be launchable from any studio view that can see them"): Run it in every view that shows a workflow, in headless Chrome
with real presses (tests/helpers/studio_run_flow.py), over a real Studio with the pack that ships with Halo (doc-review)
installed and enabled; each Run starts a real session that runs the workflow by name.

1. Agents -> 2 · Workflows: Run it beside Try it (Try it unchanged), its form in place with the line word for word,
   Run -> POST crew/run 202 and the receipt in the form's room; Watch it in Live -> Live draws "workflow <name>";
2. the Run a goal drawer (head "Workflows", the pack's tag), the Pack Manager, the pack's section (a row drawn by Studio,
   outside the pack's page), the workflow box on a map of his, the palette's Run a workflow: each Run starts a session;
3. every session's record holds the receipt "crew workflow doc-review--review-docs · ran on the step runner · done", and
   Studio's stop ends them all;
4. a tab a link opened: each of those Runs is refused with the one toast and its Make this tab yours (no second
   message); one press, and the same Run answers 202. No page error.
Run: python -m tests.test_studio_run_flow   (the Linux VM: browser modules do not run on the PC)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.driver_got import got as driver_got  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
_RUN: dict = {}
FLOW = "doc-review--review-docs"
LINE = re.compile(r"^Starts a new session in \S.* that runs this workflow's steps on your models\. It can change files there\. "
                  r"Cost and time depend on the models its steps use\.$")
RECEIPT = re.compile(r"^Started: session [0-9a-f]{32}\.$")
VIEWS = ("flows", "goal", "map", "manager", "section", "palette")


def _got(ctx: Ctx) -> dict:
    got = driver_got(ctx, "tests.helpers.studio_run_flow", why="Run it is driven in headless Chrome", cache=_RUN, timeout=900)
    ctx.check(f"the driver ran every step, failed: {got.get('failed')}", not got.get("failed"))
    return got


def _started(ctx: Ctx, where: str, v: dict) -> None:
    ctx.check(f"{where}: Run -> POST crew/run 202, got {v.get('posted')}", str(v.get("posted") or "").endswith(" 202"))
    ctx.check(f"{where}: the receipt, word for word, got {v.get('receipt')!r}", bool(RECEIPT.match(str(v.get("receipt") or ""))))


@test
def test_run_it_beside_try_it_runs_the_packs_workflow_and_live_draws_it(ctx: Ctx):
    f = (_got(ctx).get("own") or {}).get("flows") or {}
    ctx.check("Run it stands beside Try it, and Try it is untouched", f.get("beside") is True and f.get("try_held") is True)
    ctx.check(f"the form names the workflow and says the line, got {f.get('name')!r} {f.get('line')!r}",
              f.get("name") == FLOW and bool(LINE.match(str(f.get("line") or ""))))
    ctx.check(f"its buttons are Run and Cancel, got {f.get('buttons')}", f.get("buttons") == ["Run", "Cancel"])
    ctx.check("the pressed button held still; the task box has room for three lines",
              f.get("button_held") is True and (f.get("task_height") or 0) >= 48)
    _started(ctx, "Workflows", f)
    ctx.check("the receipt keeps the form's room (nothing under it moves)", f.get("room_held") is True)
    ctx.check(f"Watch it in Live, got {f.get('watch')!r}", f.get("watch") == "Watch it in Live")


@test
def test_watch_it_in_live_draws_the_workflows_group(ctx: Ctx):
    f = (_got(ctx).get("own") or {}).get("flows") or {}
    ctx.check(f"Agents -> 4 · Live draws the session's workflow as a group named after it, got {f.get('groups')} "
              f"{str(f.get('live_text'))[:300]!r}", f.get("live") is True)


@test
def test_every_other_view_that_shows_it_runs_it_the_same_way(ctx: Ctx):
    own = _got(ctx).get("own") or {}
    g = own.get("goal") or {}
    ctx.check(f"the goal drawer's head and the pack's row with its tag, got {g.get('head')!r} {g.get('listed')}",
              g.get("head") == "Workflows" and [FLOW, "pack doc-review", "pack"] in (g.get("listed") or []))
    for where in ("goal", "manager", "section", "map", "palette"):
        _started(ctx, where, own.get(where) or {})
    ctx.check("the pack's section: the row is drawn by Studio, outside the pack's page",
              (own.get("section") or {}).get("drawn_by_studio") is True)
    p = own.get("palette") or {}
    ctx.check(f"the palette lists it with its tag and opens the same form, got {p.get('listed_tag')!r} {p.get('line')!r}",
              p.get("listed_tag") == "pack doc-review" and p.get("name") == FLOW and bool(LINE.match(str(p.get("line") or ""))))


@test
def test_each_session_runs_it_by_name_and_ends_with_studio(ctx: Ctx):
    got = _got(ctx)
    sids, receipts = got.get("sids") or [], got.get("receipts") or {}
    ctx.check(f"one session per Run (six views, then the one after Make this tab yours), got {len(sids)}", len(sids) == 7)
    ctx.check(f"each session's record holds the receipt, got {receipts}", receipts and all(receipts.values()))
    ctx.check(f"Studio's stop ended them, none survives, got {got.get('ended')} {got.get('survivors')}",
              (got.get("ended") or 0) >= 1 and got.get("survivors") == [])
    ctx.check(f"no page error, got {got.get('page_errors')}", got.get("page_errors") == [])


@test
def test_a_tab_a_link_opened_is_refused_with_the_one_toast_then_runs(ctx: Ctx):
    v = _got(ctx).get("viewonly") or {}
    ctx.check("the link's tab says it can only look", v.get("row") is True)
    for where in VIEWS:
        r = v.get(where) or {}
        ctx.check(f"{where}: Run -> 403, the toast's Make this tab yours, no second message, got {r}",
                  str(r.get("posted") or "").endswith(" 403") and r.get("toast") == "Make this tab yours" and r.get("inline_error") is False)
    _started(ctx, "after one press of Make this tab yours", v.get("after_press") or {})


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
