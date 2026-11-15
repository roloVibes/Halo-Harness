"""tests.test_workflows_lineup_roles -- squares on a lineup that did not ask for them (Halo 3.3.16.2, "from a
session's own review": a custom lineup with no `workflows:` key got the Workflow tool, which answered "no
square is enabled for this lineup"):

(a) a lineup with no `workflows:` key inherits config `workflows.enabled` (default media); `workflows: []`
    has none, on purpose;
(b) the Workflow tool is offered only when a square is enabled for the lineup (workflows/offer.py takes it
    out of the registry, the catalog's names and its deferred pool otherwise);
(c) a role of the lineup that covers the read takes the task (the Agent tool's path, `role: <alias>`), the
    receipt says so; a named square or an ask still goes to a square;
(d) nothing covers it: one line saying what would;
(e) `halo doctor`'s line under the lineup and `halo workflows list`'s "on for <lineup>" / "off".
Fakes only, no model call. Run: python -m tests.test_workflows_lineup_roles
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import PacksHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.workflow_fakes import FakeRuntime, child_row, run_tool  # noqa: E402

test, TESTS = new_registry()
MAIN = {"agent": "default-model", "role": "main"}


def team(cards: dict, bios: dict = None):
    """A TeamControl stand-in: `{alias: entry}` and the bios `bio_for` answers."""
    bios = bios or {}
    return SimpleNamespace(name="mine", aliases={"main": MAIN, **cards}, budget={},
                           bio_for=lambda alias: bios.get((cards.get(alias) or {}).get("agent")))


@test
def test_the_set_is_configs_and_an_empty_list_is_none(ctx: Ctx):
    """3.6.0.0 R5d: a session's squares are config's `workflows.enabled` (lineups are gone)."""
    from halo_harness.theme import set_config_value
    from halo_harness.workflows import registry
    with PacksHome() as h:
        got = registry.enabled_from(cwd=h.repo)
        ctx.check(f"nothing set: config's default, got {got}", got == (["media"], "config"))
        set_config_value("workflows.enabled", [])
        ctx.check(f"workflows.enabled: []: none, got {registry.enabled_from(cwd=h.repo)}",
                  registry.enabled_from(cwd=h.repo) == ([], "config"))
        set_config_value("workflows.enabled", ["plan"])
        ctx.check("config moves, the set follows", [w.ref for w in registry.enabled_squares(cwd=h.repo)] == ["plan"])


@test
def test_the_tool_is_offered_only_when_a_square_is_on(ctx: Ctx):
    from halo_harness.theme import set_config_value
    from halo_harness.tools.registry import ToolRegistry, default_tools
    from halo_harness.workflows.offer import drop_unless_enabled
    with PacksHome() as h:
        set_config_value("workflows.enabled", [])
        reg = ToolRegistry(default_tools())
        catalog = SimpleNamespace(registry=reg, names=reg.names(), deferred={"Workflow": object()})
        ctx.check("no square on: the tool goes", drop_unless_enabled(reg, catalog, cwd=h.repo))
        ctx.check("from the registry, the wire names and the deferred pool",
                  reg.get("Workflow") is None and "Workflow" not in catalog.names and "Workflow" not in catalog.deferred)
        ctx.check("the tool list says nothing about squares", not any("square" in str(d.get("description", "")).lower()
                                                                      for d in reg.definitions()))
        from halo_harness.isolation.capabilities import narrow_session
        reg3 = ToolRegistry(default_tools())
        narrow_session(reg3, None, team="auto", agent=None, cwd=h.repo)
        ctx.check("the session builder's narrowing applies it", reg3.get("Workflow") is None)
        set_config_value("workflows.enabled", ["media"])
        reg2 = ToolRegistry(default_tools())
        ctx.check("media on keeps it", not drop_unless_enabled(reg2, None, cwd=h.repo) and reg2.get("Workflow") is not None)


def spawner(rt, seen: list, text: str = "page 1: revenue up"):
    from halo_harness.tools.base import ToolResult

    def spawn(*, runtime, tool_id, tool_input, tool_name, on_child=None):
        seen.append(dict(tool_input))
        child = child_row(rt, "c1", cost_usd=0.02)
        if on_child:
            on_child(child)
        return [], ToolResult(text)
    return spawn


@test
def test_a_role_that_covers_it_takes_the_task(ctx: Ctx):
    from halo_harness.workflows import lineup_roles as L
    with PacksHome() as h:
        rt = FakeRuntime(h.repo, team=team({"media": {"agent": "my-media", "role": "custom", "as": "media"}}))
        seen: list = []
        got = run_tool(rt, {"task": "summarize the report", "files": ["docs/report.pdf"]}, spawn=spawner(rt, seen), takes=["text"])
        first = got.content.splitlines()[0]
        ctx.check(f"the receipt names the role, got {first!r}",
                  first == "role media · in pdf (report.pdf) · back - · $0.0200 -- handing the PDF to your media role: "
                           "the lineup covers it")
        ctx.check(f"through the Agent tool's path with the role, got {seen}", seen and seen[0].get("role") == "media"
                  and "docs/report.pdf" in seen[0]["prompt"] and got.content.endswith("page 1: revenue up"))
        rec = rt.parent.log.receipts()[0]
        ctx.check(f"one receipt node with the role, got {rec}", rec["role"] == "media" and rec["square"] == "" and rec["status"] == "done")
        seen.clear()
        got = run_tool(rt, {"task": "summarize", "files": ["docs/report.pdf"], "name": "media"}, spawn=spawner(rt, seen),
                       takes=["text"])
        ctx.check(f"a named square still goes to the square, got {got.content.splitlines()[0]!r}",
                  got.content.startswith("square media ·") and seen[0].get("role") is None)
        bios = {"reader": {"kind": "custom", "models": {"needs": ["pdf"]}}}
        t2 = team({"reader": {"agent": "reader", "role": "custom"}}, bios)
        ctx.check("a card whose bio needs pdf covers a PDF", L.covering_role(["pdf"], t2) == "reader")
        ctx.check("...but not an image", L.covering_role(["vision"], t2) == "")
        ctx.check("an ask in the task goes to a square", L.covering_role(["pdf", "review"], t2) == "")
        t3 = team({"eyes": {"agent": "x", "role": "custom", "models": {"capabilities": ["vision"]}}})
        ctx.check("a card's own models.capabilities count", L.covering_role(["vision"], t3) == "eyes")
        ctx.check("no lineup, no role", L.covering_role(["pdf"], None) == "")


@test
def test_nothing_covers_it_says_what_would(ctx: Ctx):
    from halo_harness.workflows import router
    from halo_harness.workflows.spec import find
    with PacksHome() as h:
        plan = [find("plan", cwd=h.repo)[0]]
        r = router.route("listen to talk.mp3 and look at shot.png", ["talk.mp3", "shot.png"], squares=plan, takes=["text"],
                         team=team({"coder": {"agent": "c", "role": "coder"}}))
        ctx.check(f"one line, what would read it, got {r.why!r}", r.refused and r.role == "" and r.why ==
                  "no role or square reads images or audio here (could not read talk.mp3, shot.png): "
                  "add media to config workflows.enabled, or give a role a model that takes images or audio")


@test
def test_doctor_says_which_squares_are_on(ctx: Ctx):
    from halo_harness.theme import set_config_value
    from halo_harness.workflows.doctor_rows import rows, squares_line
    with PacksHome() as h:
        ctx.check(f"config's default, got {squares_line(cwd=h.repo)!r}",
                  squares_line(cwd=h.repo) == "Squares a session enables: media (config workflows.enabled)")
        set_config_value("workflows.enabled", ["plan"])
        ctx.check(f"config's own, got {squares_line(cwd=h.repo)!r}",
                  squares_line(cwd=h.repo) == "Squares a session enables: plan (config workflows.enabled)")
        set_config_value("workflows.enabled", [])
        ctx.check(f"none, got {squares_line(cwd=h.repo)!r}", squares_line(cwd=h.repo).startswith(
            "Squares a session enables: none (config workflows.enabled), so the Workflow tool is not offered"))
        keys = [k for k, _line in rows(h.repo)]
        ctx.check(f"doctor: the map row, then the squares, got {keys}", keys == ["lineup", "lineup_squares"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
