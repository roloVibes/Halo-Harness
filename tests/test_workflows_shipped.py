"""tests.test_workflows_shipped -- the shipped squares (Halo 3.3.16.0 R3, halo_harness/templates/workflows/): media,
plan, code, review and research each pass the check (`halo workflow check`'s compile with a task), carry a real
`does`, say what they give, cover their need, run on the engine the brief names (orchestra for code, session for
the rest) with `limits.depth: 1`; media covers the four modalities with its lead an `auto` model; the files ship
as package data. No model call.

Run: python -m tests.test_workflows_shipped
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import PacksHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
SHIPPED = {"media": ("session", "media"), "plan": ("session", "plan"), "code": ("orchestra", "code"),
           "review": ("session", "review"), "research": ("session", "research")}


@test
def test_each_shipped_square_checks_and_compiles(ctx: Ctx):
    from halo_harness.workflows import registry
    from halo_harness.workflows.compile import compile_workflow
    from halo_harness.workflows.spec import find
    with PacksHome() as h:
        for name, (engine, cover) in SHIPPED.items():
            wf, why = find(name, cwd=h.repo)
            ctx.check(f"{name} found shipped, got {why}", wf is not None and wf.origin == "shipped")
            c = wf.contract
            ctx.check(f"{name}: check clean, got {registry.check(wf, cwd=h.repo)}", registry.check(wf, cwd=h.repo) == [])
            done = compile_workflow(wf, {"task": "a sample task"}, repo=h.repo, cwd=h.repo)
            ctx.check(f"{name}: compiles, got {done.problems}", not done.problems and done.jobs)
            ctx.check(f"{name}: a square on {engine} covering {cover}, depth 1", c.square and c.engine == engine
                      and cover in c.covers and c.depth == 1 and len(c.does.split()) >= 8 and c.does.endswith("."))
            ctx.check(f"{name}: one or two stages", 1 <= len(wf.data.get("stages") or []) <= 2)


@test
def test_media_covers_the_modalities_on_an_auto_lead(ctx: Ctx):
    from halo_harness.workflows.spec import find
    with PacksHome() as h:
        c = find("media", cwd=h.repo)[0].contract
        ctx.check(f"covers, got {c.covers}", {"pdf", "vision", "audio", "video", "media"} <= set(c.covers))
        ctx.check(f"takes the modalities, got {c.takes}", {"pdf", "images", "audio", "video"} <= set(c.takes))
        ctx.check(f"its lead, got {c.lead()}", c.lead() == ("auto-media", "auto"))


@test
def test_the_squares_ship_as_package_data(ctx: Ctx):
    text = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    ctx.check("templates/workflows/*.yaml in package-data", '"templates/workflows/*.yaml"' in text)
    files = sorted(p.stem for p in (REPO / "halo_harness" / "templates" / "workflows").glob("*.yaml"))
    ctx.check(f"the five, got {files}", files == sorted(SHIPPED))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
