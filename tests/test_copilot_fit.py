"""tests.test_copilot_fit -- `cp:work` and `copilot_ask` in what 3.3.16.1-3.3.16.3 added (Halo 3.3.17.0, the merge
onto master): the shared ranking (model_rank.py) never puts `cp:work` ahead for a kind that needs tool calls and its
missing price never wins "cheapest"; Auto's `work-data` pick goes through that one comparator; Live shows a `cp:work`
turn as text rows, no thoughts (nothing invented), its hand-back as a TALK row and a `copilot_ask` call as a tool row;
a Cast hover's model row carries the tenant's price words; a square or a block template may name a bio on `cp:work`
and its Costs line says "tenant credits" where the cost is not in dollars. Mock server only, no model.

Run: python -m tests.test_copilot_fit
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.copilot_rig import CopilotRig  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
TOOLY = {"facts": {"tools": True, "modalities_in": ["text"], "modalities_out": ["text"], "price_in_per_m": 1.0,
                   "price_out_per_m": 2.0, "provider": "openrouter"},
         "kinds": ["code", "research", "bulk"], "scores": {"code": 0.5, "research": 0.5, "bulk": 0.5}}


@test
def test_the_shared_ranking_never_leads_a_tool_kind_or_cheapest_with_cp_work(ctx: Ctx):
    from halo_harness import model_rank as R
    from halo_harness.capabilities_strengths import blended_price
    from halo_harness.models_best_at import best_per_kind, entry_for
    from halo_harness.providers.copilot_catalog import row
    natural = entry_for(row())
    ctx.check(f"cp:work's own entry is in no best-at kind, got {natural['kinds']}", natural["kinds"] == [])
    ctx.check(f"its price is none in dollars, got {blended_price(row())}", blended_price(row()) is None)
    forced = {**natural, "kinds": ["code", "research", "bulk"], "scores": {"code": 0.99, "research": 0.99, "bulk": 0.99}}
    best = best_per_kind({"cp:work": forced, "or:v/tooly": TOOLY}, keyed={})
    ctx.check(f"code (tool calls): never cp:work, even scored higher, got {best['code']}",
              best["code"]["strongest"] == "or:v/tooly" and best["code"]["cheapest"] == "or:v/tooly")
    ctx.check(f"no kind's cheapest is cp:work (no price never wins it), got {[(k, v['cheapest']) for k, v in best.items()]}",
              all(v["cheapest"] != "cp:work" for v in best.values()))
    ctx.check("research (no tool calls needed) may be led by it", best["research"]["strongest"] == "cp:work")
    alone = best_per_kind({"cp:work": forced}, keyed={})
    ctx.check(f"alone, it leads no code at all, got {sorted(alone)}", "code" not in alone)
    ctx.check("ranks_for: code no, research yes", not R.ranks_for("code", forced) and R.ranks_for("research", forced))


@test
def test_autos_work_data_pick_goes_through_the_one_comparator(ctx: Ctx):
    from halo_harness import model_rank as R
    from halo_harness.models_auto_work import work_pick
    from halo_harness.providers.copilot_catalog import row
    calls: list = []
    saved = R.ranked
    R.ranked = lambda items, key, **kw: calls.append([i["ref"] for i in items]) or saved(items, key, **kw)
    try:
        p = work_pick(["work-data"], rows=[row(), {**row(), "ref": "zz:work-2", "context_tokens": 128000}])
    finally:
        R.ranked = saved
    ctx.check(f"ranked by model_rank (two candidates), got {calls}", calls and sorted(calls[0]) == ["cp:work", "zz:work-2"])
    ctx.check(f"the comparator's order decides (the larger context) and says so, got {p.ref} {p.reason!r}",
              p.ref == "zz:work-2" and "same score as cp:work: larger context" in p.reason and p.alternatives == ["cp:work"])
    ctx.check("a need that also asks for tools: no pick", work_pick(["work-data", "tools"], rows=[row()]) is None)
    with CopilotRig() as r:
        ctx.check("not signed in: no row, no pick", work_pick(["work-data"]) is None)
        r.signin()
        p = work_pick(["work-data"])
        ctx.check(f"signed in: cp:work, a consult role, got {p.ref if p else None}", p is not None and p.ref == "cp:work"
                  and "no tools" in p.reason)


def _tree():
    from halo_harness.agent.agent_registry import tree_for
    tree = tree_for(NS(agent_id=None))
    got: list = []
    tree.add_listener(lambda kind, aid, data: got.append((kind, aid, data)))
    return tree, got


@test
def test_live_a_cp_work_role_has_no_thoughts_and_hands_back_as_talk(ctx: Ctx):
    from halo_harness import headless
    from halo_harness.live.talk import on_turn_ended, on_turn_started
    with CopilotRig() as r:
        r.signin()
        s = headless.build_session(cwd=REPO, model_ref_raw="cp:work", bare=True, print_mode=True, max_turns=2).session
        tree, got = _tree()
        tree.add("c1", session=s, parent="main", name="work-researcher", state="queued", kind="subagent")
        tree.follow("c1", True)
        task = "what is on my calendar tomorrow"
        tree.started("c1", s, task)
        on_turn_started(tree, "c1", task)
        for ev in s.turn(task):
            tree.observe("c1", ev)
        for kind, data in (("tool_use_ready", {"id": "k1", "name": "copilot_ask", "input": {"prompt": "who owns Y"}}),
                           ("tool_result", {"id": "k1", "name": "copilot_ask", "content": "Pat owns Y.\n[1] owners.xlsx"})):
            tree.observe("c1", NS(kind=kind, data=data))
        on_turn_ended(tree, "c1", s)
        tree.ended("c1")
    kinds = [k for k, _a, _d in got]
    ctx.check(f"no thinking_chunk: Copilot streams no thoughts and none is made up, got {kinds.count('thinking_chunk')}",
              "thinking_chunk" not in kinds)
    entries = [d for k, _a, d in got if k == "agent_event"]
    text = "".join(e.get("text", "") for e in entries if e.get("kind") == "text")
    ctx.check(f"the turn is text rows like any model's, got {text[:80]!r}", "Work IQ heard: what is on my calendar" in text)
    tools = [e.get("kind") for e in entries if e.get("name") == "copilot_ask"]
    ctx.check(f"a copilot_ask call is a tool row and its result, like any tool's, got {tools}",
              tools == ["tool_call", "tool_result"])
    talks = [d for k, _a, d in got if k == "agent_talk"]
    ctx.check(f"a task, then the hand-back as TALK (c1 -> main, re the task), got {[t['why'] for t in talks]}",
              [t["why"] for t in talks] == ["task", "hand-back"] and talks[1]["from"] == "c1" and talks[1]["to"] == "main"
              and talks[1]["re"] == talks[0]["id"] and "Work IQ heard" in talks[1]["text"])


@test
def test_the_cast_hover_row_carries_the_tenants_price_words(ctx: Ctx):
    from halo_harness.model_takes import takes_words
    from halo_harness.providers.copilot_catalog import PRICE_NOTE, row
    from halo_harness.studio.model_card_api import row_view
    v = row_view("cp:work", row(), None)
    ctx.check(f"the Studio row says {PRICE_NOTE!r}, got {v.get('price_note')!r}", v.get("price_note") == "your tenant's credits or licence")
    ctx.check(f"takes text, files, web; tools no, got {takes_words(row())} {row()['tools']}",
              takes_words(row()) == ["text", "files", "web"] and row()["tools"] is False)
    ctx.check("a dollar-priced row carries no note", "price_note" not in row_view("or:v/x", {"ref": "or:v/x", "price_in_per_m": 1.0}, None))


@test
def test_a_square_or_template_on_cp_work_costs_tenant_credits(ctx: Ctx):
    from halo_harness.workflows import blocks as B
    from halo_harness.workflows.contract import read
    lead = {"bio": "auto-reviewer", "model": "cp:work"}
    sq = {"gives": ["text"], "budget": {"band": "mid", "cap_usd": 1.5}, "lineup": {"lead": lead}}
    c = read(sq)
    ctx.check(f"all on cp:work: tenant credits, no dollar band, got {c.costs()!r} {c.to_json()['tenant']!r}",
              c.costs() == "tenant credits" and c.to_json()["tenant"] == "all")
    c = read({**sq, "lineup": {"lead": lead, "members": [{"bio": "auto-coder", "model": "auto"}]}})
    ctx.check(f"part on cp:work: the band, then tenant credits, got {c.costs()!r}",
              c.costs() == "band mid · cap $1.50 · + tenant credits" and c.to_json()["tenant"] == "some")
    c = read({**sq, "lineup": {"lead": {"bio": "auto-reviewer", "model": "auto"}}})
    ctx.check(f"none on it: as before, got {c.costs()!r}", c.costs() == "band mid · cap $1.50" and c.to_json()["tenant"] == "")
    from tests.helpers.packs_home import PacksHome
    with PacksHome() as h:
        t = dict(B.load("review-panel")[0])
        t["square"] = dict(t["square"], lineup={"lead": lead})
        ctx.check(f"a template may name a bio on cp:work, got {B.problems(t, cwd=h.repo)}", B.problems(t, cwd=h.repo) == [])
        ctx.check(f"its summary costs tenant credits, got {B.summary(t)['costs']!r}", B.summary(t)["costs"] == "tenant credits")
        t["square"] = dict(t["square"], lineup={"lead": {"bio": "auto-reviewer", "model": "or:vendor/x"}})
        ctx.check("a paid model is still a problem", any("names a model" in p for p in B.problems(t, cwd=h.repo)))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
