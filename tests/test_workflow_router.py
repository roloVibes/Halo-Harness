"""tests.test_workflow_router -- which square takes a hand-off and why (Halo 3.3.16.0 R3,
workflows/router.py, tools/workflow.py): the gaps are the task's needs minus what the model takes (a seeded
best-at cache: the `/model` takes column), plus the asks; the pick covers the most gaps, then the band
nearest the session's; the why line in plain words; no square -> one line naming what could not be read;
depth 0 refuses a nested call and a square's own agent gets depth - 1; the cap is the smaller of the
square's and the session's remaining (0 left: budget hit); a named square must be enabled; the child runs
on the parent's runtime with no permission field of its own (the parent's mode and rules apply). Fakes
only, no model call.

Run: python -m tests.test_workflow_router
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import PacksHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def seed_takes(h) -> None:
    """The best-at cache with a text-only model and one that reads images and PDFs."""
    from halo_harness.models_best_at import SCHEMA
    rows = {"or:vendor/text-only": {"kinds": [], "line": "", "facts": {"modalities_in": ["text"], "tools": True}},
            "or:vendor/sees": {"kinds": [], "line": "", "facts": {"modalities_in": ["text", "image", "file"], "tools": True}}}
    h.write(".halo/models/best-at.json", json.dumps({"schema": SCHEMA, "built": time.time(), "sources": {}, "rows": rows}))


def squares(h, *names):
    from halo_harness.workflows.spec import find
    return [find(n, cwd=h.repo)[0] for n in names]


@test
def test_gaps_are_the_needs_minus_what_the_model_takes(ctx: Ctx):
    from halo_harness.workflows import router
    with PacksHome() as h:
        seed_takes(h)
        ctx.check(f"text-only takes, got {router.model_takes('or:vendor/text-only')}", router.model_takes("or:vendor/text-only")[:1] == ["text"])
        g = router.gaps("summarize the report", ["docs/report.pdf"], takes=router.model_takes("or:vendor/text-only"))
        ctx.check(f"a PDF on a text-only model is a gap, got {g}", g == ["pdf"])
        g = router.gaps("summarize the report", ["docs/report.pdf", "shot.png"], takes=router.model_takes("or:vendor/sees"))
        ctx.check(f"a model that reads both has none, got {g}", g == [])
        ctx.check("an unknown model reads as text only", router.gaps("look at shot.png", (), takes=router.model_takes("or:vendor/nobody")) == ["vision"])
        ctx.check("the asks count", router.gaps("review and plan the parser change", (), takes=["text"]) == ["plan", "review"])
        ctx.check("a need given is the gap", router.gaps("anything", (), need="Research") == ["research"])


@test
def test_the_pick_and_its_why_line(ctx: Ctx):
    from halo_harness.workflows import router
    with PacksHome() as h:
        seed_takes(h)
        on = squares(h, "media", "plan", "review")
        r = router.route("summarize report.pdf", ["report.pdf"], model_ref="or:vendor/text-only", squares=on)
        ctx.check(f"media, got {r.square.ref if r.square else r.why}", r.square is not None and r.square.ref == "media" and not r.refused)
        ctx.check(f"the why line, got {r.why!r}", r.why == "handing the PDF to media: your model takes text only")
        r = router.route("review the parser change", (), model_ref="or:vendor/text-only", squares=on)
        ctx.check(f"an ask, got {r.why!r}", r.square.ref == "review" and r.why == "handing the review to review: the ask names review")
        h.write(".halo/workflows/pdfpro.yaml", "name: pdfpro\ndoes: PDFs, carefully.\ngives: [text]\ncovers: [pdf]\n"
                "budget: {band: high}\nstages:\n  - id: a\n")
        both = squares(h, "media", "pdfpro")
        ctx.check("a high session gets the high square", router.route("read a.pdf", (), squares=both, band="high", takes=["text"]).square.ref == "pdfpro")
        ctx.check("a low session gets the low one", router.route("read a.pdf", (), squares=both, band="low", takes=["text"]).square.ref == "media")


@test
def test_no_square_is_one_line_and_the_model_goes_on(ctx: Ctx):
    from halo_harness.workflows import router
    with PacksHome() as h:
        r = router.route("summarize report.pdf", ["docs/report.pdf"], squares=squares(h, "plan"), takes=["text"])
        ctx.check(f"refused, one line naming the file, got {r.why!r}", r.refused and r.square is None
                  and r.why == "no role or square reads PDFs here (could not read docs/report.pdf): `halo workflows enable "
                  "media`, or give a role a model that takes PDFs")  # 3.3.16.2: says what would read it
        r = router.route("tidy this up", (), squares=squares(h, "media"), takes=["text"])
        ctx.check(f"nothing to hand off, got {r.why!r}", r.refused and r.why.startswith("no hand-off: nothing in the task needs more"))
        r = router.route("x", (), name="plan", squares=squares(h, "media"), takes=["text"])
        ctx.check(f"a named square must be enabled, got {r.why!r}", r.refused and "plan is not enabled for this lineup" in r.why)
        r = router.route("x", (), need="smell", squares=squares(h, "media"), takes=["text"])
        ctx.check(f"an unknown need, got {r.why!r}", r.refused and "is not a need a square covers" in r.why)


@test
def test_depth_zero_refuses_and_a_square_gets_depth_minus_one(ctx: Ctx):
    from halo_harness.workflows import router
    with PacksHome() as h:
        on = squares(h, "media")
        r = router.route("read a.pdf", (), squares=on, hops=0, takes=["text"])
        ctx.check(f"depth 0 refuses a nested call, got {r.why!r}", r.refused and "allows no further square" in r.why)
        r = router.route("read a.pdf", (), squares=on, takes=["text"])
        ctx.check(f"main may; the square's own agent gets 0 (depth 1), got {r.hops}", not r.refused and r.hops == 0)
        from halo_harness.workflows.contract import read
        ctx.check("depth 2 gives one more hop", router.child_hops(read({"limits": {"depth": 2}}), None) == 1)
        ctx.check("never more than the caller's hops - 1", router.child_hops(read({"limits": {"depth": 3}}), 1) == 0)


@test
def test_the_cap_is_the_smaller_and_none_left_is_budget_hit(ctx: Ctx):
    from halo_harness.workflows import router
    with PacksHome() as h:
        on = squares(h, "media")  # cap_usd 1
        ctx.check("the session's 0.40 left wins", router.route("read a.pdf", (), squares=on, remaining=0.4, takes=["text"]).cap_usd == 0.4)
        ctx.check("the square's 1.00 wins", router.route("read a.pdf", (), squares=on, remaining=5.0, takes=["text"]).cap_usd == 1.0)
        r = router.route("read a.pdf", (), squares=on, remaining=0.0, takes=["text"])
        ctx.check(f"budget hit, one line, got {r.why!r}", r.refused and r.why == "media cannot start: budget hit (the session has $0.00 left)")


@test
def test_the_child_runs_on_the_parents_runtime_with_no_mode_of_its_own(ctx: Ctx):
    from tests.helpers.workflow_fakes import FakeRuntime, run_tool
    with PacksHome() as h:
        seen = {}

        def spawn(*, runtime, tool_id, tool_input, tool_name, on_child=None):
            seen.update(runtime=runtime, input=dict(tool_input), name=tool_name)
            from halo_harness.tools.base import ToolResult
            return [], ToolResult("read it: page 1 says hello")

        rt = FakeRuntime(h.repo)
        result = run_tool(rt, {"task": "summarize report.pdf", "files": ["report.pdf"]}, spawn=spawn, takes=["text"])
        ctx.check("the parent's own runtime (its permission engine, its rules)", seen.get("runtime") is rt)
        ctx.check(f"no permission field of its own, got {sorted(seen.get('input') or {})}",
                  set(seen.get("input") or {}) <= {"description", "prompt", "subagent_type", "model"}
                  and seen["input"]["subagent_type"] == "general-purpose" and seen["name"] == "Agent")
        ctx.check(f"the result starts with the receipt line, got {result.content[:80]!r}", result.content.startswith("square media · in pdf"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
