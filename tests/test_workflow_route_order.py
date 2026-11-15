"""tests.test_workflow_route_order -- the one order the Workflow router follows since 3.3.16.2 (a lineup role that
covers the need) met 3.3.16.3 (a square's "when"), explicit before implicit (workflows/router.py `route`,
docs/WORKFLOWS-squares.md "The order"):

1. a square asked for by NAME runs (its when `off`: one line, not connected, how to connect it);
2. a square whose explicit when fires -- `always`, then `words`, then `needs` -- wins over a role (`rule`);
3. otherwise a lineup ROLE that covers the need ("to your media role");
4. otherwise a square with a PLAIN ref whose `covers` meet the gaps (today's reason);
5. otherwise the one line saying what would.

`named` only by name, `off` never; the tool is not offered when every square on is `off`; `halo doctor`'s squares
line names a when; `halo workflows list` has both the on/off mark and the when column; an edit to a lineup with no
`workflows:` key starts from the set it inherits. Fakes only, no model call.
Run: python -m tests.test_workflow_route_order
"""
from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import PacksHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.workflow_fakes import FakeRuntime, child_row, run_tool  # noqa: E402

test, TESTS = new_registry()
MAIN = {"agent": "default-model", "role": "main"}
MEDIA_ROLE = {"media": {"agent": "my-media", "role": "custom", "as": "media"}}
CODER = {"coder": {"agent": "c", "role": "coder"}}
PDF = ("summarize report.pdf", ["report.pdf"])
LINEUP = "name: {name}\nagents:\n  - {{agent: default-model, role: main}}\n"


def team(cards: dict, name: str = "mine"):
    return SimpleNamespace(name=name, aliases={"main": MAIN, **cards}, budget={}, bio_for=lambda alias: None)


def squares(h, *names):
    from halo_harness.workflows.spec import find
    return [find(n, cwd=h.repo)[0] for n in names]


def rules(**kw):
    from halo_harness.workflows.when import read
    return {k: read(v) for k, v in kw.items()}


def route(h, task, files=(), on=("media", "review", "plan"), cards=None, **kw):
    from halo_harness.workflows import router
    return router.route(task, files, squares=squares(h, *on), takes=["text"],
                        team=team(cards) if cards is not None else None, **kw)


@test
def test_1_a_name_beats_a_when_and_a_role(ctx: Ctx):
    with PacksHome() as h:
        r = route(h, *PDF, name="review", cards=MEDIA_ROLE, rules=rules(media={"needs": ["pdf"]}, plan={"mode": "always"}))
        ctx.check(f"named review runs, got {r.why!r}", r.square.ref == "review" and r.role == "" and r.rule == "asked for by name")
        r = route(h, *PDF, name="plan", cards=MEDIA_ROLE, rules=rules(plan={"mode": "named"}))
        ctx.check(f"named mode: by name it runs, got {r.why!r}", r.square.ref == "plan" and not r.refused)
        r = route(h, *PDF, name="media", cards=MEDIA_ROLE, rules=rules(media={"mode": "off"}))
        ctx.check(f"off by name: the line says not connected and how, got {r.why!r}", r.refused and r.square is None
                  and r.why.startswith("media is not connected: main never uses it")
                  and "config workflows.when.media" in r.why)


@test
def test_2_an_explicit_when_beats_a_covering_role(ctx: Ctx):
    with PacksHome() as h:
        r = route(h, *PDF, cards=MEDIA_ROLE, rules=rules(plan={"mode": "always"}))
        ctx.check(f"always first beats the media role, got {r.why!r}", r.square.ref == "plan" and r.rule == "always first")
        r = route(h, "audit report.pdf", ["report.pdf"], cards=MEDIA_ROLE, rules=rules(review={"words": ["audit"]}))
        ctx.check(f"words beat the media role, got {r.why!r}", r.square.ref == "review" and r.rule == 'when the task says "audit"')
        r = route(h, *PDF, cards=MEDIA_ROLE, rules=rules(media={"needs": ["pdf"]}))
        ctx.check(f"explicit needs beat a covering role, got {r.why!r}", r.square.ref == "media" and r.role == ""
                  and r.rule == "when main needs pdf" and r.why == "handing the PDF to media: when main needs pdf")
        r = route(h, *PDF, cards=MEDIA_ROLE, rules=rules(plan={"mode": "always"}, review={"words": ["summarize"]}))
        ctx.check("always before words", r.square.ref == "plan")
        r = route(h, *PDF, cards=MEDIA_ROLE, rules=rules(review={"words": ["summarize"]}, media={"needs": ["pdf"]}))
        ctx.check("words before needs", r.square.ref == "review")


@test
def test_3_a_covering_role_beats_a_plain_ref(ctx: Ctx):
    with PacksHome() as h:
        r = route(h, *PDF, cards=MEDIA_ROLE)
        ctx.check(f"plain media loses to the media role, got {r.why!r}", r.square is None and r.role == "media" and not r.refused
                  and r.why == "handing the PDF to your media role: the lineup covers it")
        r = route(h, *PDF, cards=MEDIA_ROLE, rules=rules(media={}))
        ctx.check("auto with no needs or words is a plain ref", r.role == "media" and r.square is None)
        r = route(h, *PDF, cards=MEDIA_ROLE, rules=rules(media={"needs": ["vision"]}))
        ctx.check(f"a when that does not fire leaves it to the role, got {r.why!r}", r.role == "media")


@test
def test_4_a_plain_ref_when_no_role_covers_it(ctx: Ctx):
    with PacksHome() as h:
        r = route(h, *PDF, cards=CODER)
        ctx.check(f"today's pick and reason, got {r.why!r}", r.square.ref == "media" and r.role == "" and r.rule == ""
                  and r.why == "handing the PDF to media: your model takes text only")
        r = route(h, "review this diff", (), cards=MEDIA_ROLE)
        ctx.check(f"an ask goes to a square, not the role, got {r.why!r}", r.square.ref == "review" and r.role == "")


@test
def test_5_nothing_covers_it_says_what_would(ctx: Ctx):
    with PacksHome() as h:
        r = route(h, *PDF, on=("plan",), cards=CODER)
        ctx.check(f"the line says what would, got {r.why!r}", r.refused and r.square is None and r.role == ""
                  and r.why.startswith("no role or square reads PDFs here (could not read report.pdf)"))
        r = route(h, *PDF, on=("media",), cards=CODER, rules=rules(media={"mode": "named"}))
        ctx.check(f"named is never picked by need, got {r.why!r}", r.refused and r.square is None)
        r = route(h, *PDF, on=("media",), cards=CODER, rules=rules(media={"mode": "off"}))
        ctx.check(f"off is never picked, got {r.why!r}", r.refused and r.square is None)


@test
def test_the_tool_end_to_end_receipts(ctx: Ctx):
    with PacksHome() as h:
        from halo_harness.theme import set_config_value  # 3.6.0.0 R5d: the rule is config's (lineups are gone)
        set_config_value("workflows.when", {"media": {"needs": ["pdf"]}})
        rt = FakeRuntime(h.repo, team=team(MEDIA_ROLE))
        seen: list = []

        def spawn(*, runtime, tool_id, tool_input, tool_name, on_child=None):
            from halo_harness.tools.base import ToolResult
            seen.append(dict(tool_input))
            child = child_row(rt, f"c{len(seen)}", cost_usd=0.01)
            if on_child:
                on_child(child)
            return [], ToolResult("read it")
        got = run_tool(rt, {"task": "summarize", "files": ["report.pdf"]}, spawn=spawn, takes=["text"])
        rec = rt.parent.log.receipts()[-1]
        ctx.check(f"the square, its rule on the receipt, got {got.content.splitlines()[0]!r}",
                  got.content.startswith("square media ·") and rec["rule"] == "when main needs pdf" and rec["role"] == "")
        set_config_value("workflows.when", {})
        got = run_tool(rt, {"task": "summarize", "files": ["report.pdf"]}, spawn=spawn, takes=["text"])
        ctx.check(f"a plain ref: the role, got {got.content.splitlines()[0]!r}", got.content.startswith("role media ·")
                  and "your media role" in got.content and rt.parent.log.receipts()[-1]["role"] == "media")


@test
def test_the_offer_and_the_doctor_line(ctx: Ctx):
    """3.6.0.0 R5d: config's set and rules (the lineup half went with the lineups)."""
    from halo_harness.theme import set_config_value
    from halo_harness.tools.registry import ToolRegistry, default_tools
    from halo_harness.workflows.doctor_rows import squares_line
    from halo_harness.workflows.offer import drop_unless_enabled
    with PacksHome() as h:
        set_config_value("workflows.enabled", ["media"])
        set_config_value("workflows.when", {"media": {"mode": "off"}})
        reg = ToolRegistry(default_tools())
        ctx.check("every square off: the tool is not offered", drop_unless_enabled(reg, None, cwd=h.repo)
                  and reg.get("Workflow") is None)
        set_config_value("workflows.enabled", ["media", "plan"])
        reg = ToolRegistry(default_tools())
        ctx.check("one connected square keeps it", not drop_unless_enabled(reg, None, cwd=h.repo))
        ctx.check(f"and off, got {squares_line(cwd=h.repo)!r}", "media (not connected), plan" in squares_line(cwd=h.repo))
        set_config_value("workflows.when", {"media": {"needs": ["pdf"]}})
        line = squares_line(cwd=h.repo)
        ctx.check(f"doctor names the when, got {line!r}", line.startswith("Squares a session enables: media (when needs pdf), plan ("))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
