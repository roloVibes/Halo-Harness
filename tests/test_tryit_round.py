"""tests.test_tryit_round -- Halo 2.0.6 round 14: "Try it" on a bio and a
lineup smoke run from the forms, COST SHOWN FIRST (the item deferred from
2.0.5 round 2).

The cost line is the contract: it appears BEFORE any call runs, names the
model and its real catalog prices (or says the price is unknown), and
never fakes a $0.00. The smoke call itself rides the proven print-mode
subprocess path (`agents_doctor._default_call`), so credentials and the
whole request pipeline are exercised exactly as a real turn.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.mock_openai import MockUpstream, SCENARIOS, ScriptedTurns
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()

REPO_DIR = Path(__file__).resolve().parent.parent


@test
def test_the_cost_line_is_honest_in_all_three_shapes(ctx: Ctx):
    from halo_harness.smoke_run import smoke_cost_line
    home = Path(tempfile.mkdtemp(prefix="tryit-"))
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
    os.environ["BRIDGE_TEST_HOME"] = str(home)
    os.environ.pop("BRIDGE_STATE_DIR", None)
    try:
        catalog = {
            "or:vendor/priced": {"price_in_per_m": 0.60, "price_out_per_m": 2.40},
            "or:vendor/free-ish": {"price_in_per_m": 0, "price_out_per_m": 0},
        }
        (home / ".halo").mkdir(parents=True, exist_ok=True)
        (home / ".halo" / "models.json").write_text(json.dumps(catalog), encoding="utf-8")
        line = smoke_cost_line("or:vendor/priced")
        ctx.check(f"a priced model estimates from its real prices, got {line!r}",
                  "or:vendor/priced" in line and "$0.0011" in line and "0.6/$2.4" in line)
        ctx.check("the estimate names its token basis",
                  "600 in / 300 out" in line)
        unknown = smoke_cost_line("or:vendor/not-in-catalog")
        ctx.check(f"an unpriced model says unknown, got {unknown!r}",
                  "cost unknown" in unknown and "$" not in unknown.split("cost unknown")[0])
        ctx.check("...and never a fake price", "$0.00" not in unknown)
        empty = smoke_cost_line("")
        ctx.check(f"no model picked says so, got {empty!r}", "no model picked" in empty)
        free = smoke_cost_line("or:vendor/free-ish")
        ctx.check(f"a genuinely-free model still computes honestly, got {free!r}",
                  "~$0.0000" in free)
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


@test
def test_the_bio_editor_try_it_shows_cost_before_the_call(ctx: Ctx):
    """Pilot: press Try it on the bio editor with a PREFILLED (but
    catalog-priced) preference and a stubbed smoke runner -- the hint must
    carry the COST LINE before the worker's verdict replaces it, and the
    stub records that the call ran AFTER the cost was already shown."""
    import asyncio
    from types import SimpleNamespace
    from halo_harness.tui.dialogs.agent_bio_editor import AgentBioEditor

    home = Path(tempfile.mkdtemp(prefix="tryit-ed-"))
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
    os.environ["BRIDGE_TEST_HOME"] = str(home)
    os.environ.pop("BRIDGE_STATE_DIR", None)
    order = []
    real_cost_line = None
    try:
        (home / ".halo").mkdir(parents=True, exist_ok=True)
        (home / ".halo" / "models.json").write_text(json.dumps(
            {"or:vendor/priced": {"price_in_per_m": 0.60, "price_out_per_m": 2.40}}),
            encoding="utf-8")

        import halo_harness.smoke_run as sr
        real_cost_line = sr.smoke_cost_line

        def _fake_cost(ref, **kw):
            order.append("cost")
            return real_cost_line(ref, **kw)

        def _fake_run(ref, prompt=None, **kw):
            order.append("call")
            return "smoke reply: all good here"

        sr.smoke_cost_line = _fake_cost
        sr.run_bio_smoke = _fake_run
        import halo_harness.tui.dialogs.agent_bio_editor as ed_mod
        ed_mod_run = ed_mod.run_bio_smoke if hasattr(ed_mod, "run_bio_smoke") else None

        async def body():
            from textual.app import App
            bio = {"name": "try-bio", "description": "x",
                   "models": {"preference": "or:vendor/priced"},
                   "acceptance": {"expect": "smoke", "prompt": "say something smoky"}}
            app_cwd = Path(tempfile.mkdtemp(prefix="tryit-cwd-"))
            holder = {}

            class _Host(App):
                def on_mount(self):
                    holder["screen"] = AgentBioEditor("try-bio", bio, [], cwd=app_cwd,
                                                      state_dir=home / ".halo")
                    self.push_screen(holder["screen"])
            app = _Host()
            async with app.run_test(size=(120, 45)) as pilot:
                await pilot.pause(0.15)
                editor = app.screen
                from textual.widgets import Button
                editor.query_one("#bio-try", Button).press()
                for _ in range(20):
                    await pilot.pause(0.05)
                from textual.widgets import Static
                hint = str(editor.query_one("#bio-hint", Static).render())
                ctx.check(f"the cost line is shown, got {hint[:120]!r}",
                          "cost first" in hint and "$0.0011" in hint)
                ctx.check(f"the smoke call's verdict lands, got {hint!r}",
                          "replied" in hint and "smoke reply" in hint)
                ctx.check(f"the cost was computed BEFORE the call ran, got {order}",
                          order == ["cost", "call"])
        asyncio.run(body())
    finally:
        import halo_harness.smoke_run as sr
        sr.smoke_cost_line = real_cost_line
        if real_cost_line is not None:
            pass
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


@test
def test_the_lineup_smoke_button_costs_every_distinct_model(ctx: Ctx):
    """Pilot: the lineup editor's Smoke run button prints one cost line
    per DISTINCT model the lineup resolves to (stubbed runner again --
    the pin is the cost-first contract and the dedup), then the results."""
    import asyncio
    from halo_harness.tui.dialogs.lineup_editor import LineupEditor

    home = Path(tempfile.mkdtemp(prefix="tryit-lu-"))
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
    os.environ["BRIDGE_TEST_HOME"] = str(home)
    os.environ.pop("BRIDGE_STATE_DIR", None)
    cost_refs = []
    real_cost_line = None
    try:
        (home / ".halo").mkdir(parents=True, exist_ok=True)
        (home / ".halo" / "models.json").write_text(json.dumps({
            "or:vendor/a": {"price_in_per_m": 1.0, "price_out_per_m": 2.0},
            "or:vendor/b": {"price_in_per_m": 0.5, "price_out_per_m": 1.0}}), encoding="utf-8")
        import halo_harness.smoke_run as sr
        real_cost_line = sr.smoke_cost_line

        def _fake_cost(ref, **kw):
            cost_refs.append(ref)
            return real_cost_line(ref, **kw)
        sr.smoke_cost_line = _fake_cost

        import halo_harness.agents_doctor as ad
        def _fake_acceptance(*a, **kw):
            return [("bio-a", True, "ok"), ("bio-b", True, "ok")]
        ad.run_all_acceptance = _fake_acceptance
        import halo_harness.tui.dialogs.lineup_editor as le_mod
        le_mod.run_all_acceptance = _fake_acceptance

        template = {"name": "smoke-team", "description": "x", "version": 1, "agents": [
            {"agent": "bio-a", "role": "main", "as": "boss", "models": {"preference": "or:vendor/a"}},
            {"agent": "bio-b", "role": "subagent", "as": "worker", "models": {"preference": "or:vendor/b"}},
            {"agent": "bio-c", "role": "subagent", "as": "worker2", "models": {"preference": "or:vendor/a"}},
        ]}

        async def body():
            from textual.app import App
            app_cwd = Path(tempfile.mkdtemp(prefix="tryit-lucwd-"))
            holder = {}

            class _Host(App):
                def on_mount(self):
                    holder["screen"] = LineupEditor("smoke-team", template, [], cwd=app_cwd,
                                                    state_dir=home / ".halo")
                    self.push_screen(holder["screen"])
            app = _Host()
            async with app.run_test(size=(130, 50)) as pilot:
                await pilot.pause(0.15)
                editor = app.screen
                from textual.widgets import Button
                editor.query_one("#lineup-smoke", Button).press()
                for _ in range(20):
                    await pilot.pause(0.05)
                from textual.widgets import Static
                note = str(editor.query_one("#lineup-warnings", Static).render())
                ctx.check(f"one cost line per DISTINCT model (bio-c shares bio-a's), got {cost_refs}",
                          cost_refs == ["or:vendor/a", "or:vendor/b"])
                ctx.check(f"the note shows both costs, got {note[:150]!r}",
                          "or:vendor/a" in note and "or:vendor/b" in note)
                ctx.check(f"and then the results, got {note!r}",
                          "bio-a: ok" in note)
        asyncio.run(body())
    finally:
        import halo_harness.smoke_run as sr
        sr.smoke_cost_line = real_cost_line
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
