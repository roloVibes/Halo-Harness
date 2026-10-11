"""tests.test_review2_round9e -- pins for the vibes/review.md fix pass, round 9,
the Textual-pilot TUI findings, second half:

  * f70  ctrl+s in the roles editor with the effort prompt open dropped the
        model just picked
  * f71  a card arriving while the next one was being handed to the dock was
        shown over, and orphaned by, the hand-off
  * f74  invalid YAML in a lineup-editor section was silently kept as-was
  * f75  the auto-title first-turn counter was not reset by /clear

The first half (68, 72, 73) is tests/test_review2_round9b.py.
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

REPO_DIR = Path(__file__).resolve().parent.parent
test, TESTS = new_registry()

MODELS = [{"ref": "or:vendor/strong-model", "provider": "openrouter", "group": "OpenRouter (or:)",
           "context_tokens": 128000, "price_in_per_m": 1.0, "price_out_per_m": 2.0}]


class _Env:
    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
        d = tempfile.mkdtemp(prefix="r9b-")
        os.environ["BRIDGE_TEST_HOME"] = d
        os.environ["BRIDGE_STATE_DIR"] = str(Path(d) / ".halo")
        self.dir = Path(d)
        return self

    def __exit__(self, *exc):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        return False


def _app():
    from halo_harness.testing.fake_controller import FakeController
    from halo_harness.tui.app import BridgeApp
    fake = FakeController()
    return fake, BridgeApp(fake, cwd=str(REPO_DIR))


def _static_text(widget) -> str:
    return str(widget.renderable) if hasattr(widget, "renderable") else str(widget.render())


async def _submit(app, text: str) -> None:
    from halo_harness.tui.widgets.input import PromptInput
    await app.on_prompt_input_submitted(PromptInput.Submitted(text, app.prompt_input.pasted))


# ---- f71 ------------------------------------------------------------------------------

class _Marker:
    def set_text(self, _text):
        pass


def _card(app, rid):
    from halo_harness.tui.widgets.cards import PermissionCard
    return PermissionCard(request_id=rid, summary=f"Bash({rid})", reason="", suggested_rule=None,
                          on_decide=lambda reply: None, input_data={"command": rid})


@test
def test_f71_a_card_arriving_during_the_hand_off_is_queued_not_shown_over(ctx: Ctx):
    async def body():
        with _Env():
            fake, app = _app()
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause(0.2)

                async def _quick_note(*a, **k):  # no suspension: the arrival lands inside the hand-off window
                    return _Marker()

                app.transcript.add_note = _quick_note
                a, b, c = _card(app, "a"), _card(app, "b"), _card(app, "c")
                await app.enqueue_pending_card(a, marker_text="a")
                await app.enqueue_pending_card(b, marker_text="b")
                ctx.check("a is active, b waits", app.pending_card is a and app._pending_queue == [b])
                app.clear_pending_card()          # schedules b's activation
                await app.enqueue_pending_card(c, marker_text="c")   # arrives before it runs
                await pilot.pause(0.3)
                ctx.check(f"b (first in line) is the active card, got {app.pending_card!r}", app.pending_card is b)
                ctx.check("c is still waiting, not lost", app._pending_queue == [c])
                ctx.check("the dock shows exactly b", app.pending_dock.card is b and len(app.pending_dock.children) == 1)
                app.clear_pending_card()
                await pilot.pause(0.3)
                ctx.check("c becomes active after b", app.pending_card is c and app.pending_dock.card is c)
    asyncio.run(body())


@test
def test_f71_a_late_dock_clear_never_hides_a_live_card(ctx: Ctx):
    async def body():
        with _Env():
            fake, app = _app()
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause(0.2)

                async def _quick_note(*a, **k):
                    return _Marker()

                app.transcript.add_note = _quick_note
                a, d = _card(app, "a"), _card(app, "d")
                await app.enqueue_pending_card(a, marker_text="a")
                app.clear_pending_card()          # schedules the dock clear (nothing queued)
                await app.enqueue_pending_card(d, marker_text="d")   # a new ask lands before it runs
                await pilot.pause(0.3)
                ctx.check("d is the active card", app.pending_card is d)
                ctx.check("the dock is still visible and holds d", app.pending_dock.display and app.pending_dock.card is d)
                await app._clear_dock_if_idle()   # the late clear itself: a live card keeps the dock
                ctx.check("a late clear while d is live leaves it up", app.pending_dock.display and app.pending_dock.card is d)
    asyncio.run(body())


# ---- f70 ------------------------------------------------------------------------------

def _host(screen):
    from textual.app import App

    class _Host(App):
        def on_mount(self):
            self.push_screen(screen)
    return _Host()


@test
def test_f70_ctrl_s_with_the_effort_prompt_open_commits_the_pick(ctx: Ctx):
    from textual.widgets import Input

    from halo_harness.tui.dialogs.roles_editor import RolesEditor

    async def body():
        with _Env():
            editor = RolesEditor("r9-demo", {}, MODELS)
            app = _host(editor)
            async with app.run_test(size=(120, 45)) as pilot:
                await pilot.pause(0.2)
                editor._model_picked("orchestrator", "or:vendor/strong-model")
                editor.query_one("#roles-effort-input", Input).value = "bogus"
                editor.action_save()
                ctx.check("an unrecognized effort is refused, nothing committed",
                          editor.roles.get("orchestrator") is None and editor._pending_role == "orchestrator")
                editor.query_one("#roles-effort-input", Input).value = "high"
                editor.action_save()
                await pilot.pause(0.1)
                ctx.check(f"the picked model and effort are in the saved roles, got {editor.roles.get('orchestrator')}",
                          editor.roles.get("orchestrator") == {"model": "or:vendor/strong-model", "effort": "high"})
    asyncio.run(body())


# ---- f74 ------------------------------------------------------------------------------

@test
def test_f74_invalid_yaml_in_a_section_blocks_save_and_names_the_section(ctx: Ctx):
    from textual.widgets import Static, TextArea

    from halo_harness.tui.dialogs.lineup_editor import LineupEditor

    async def body():
        with _Env():
            editor = LineupEditor("r9-lineup", {"agents": []}, MODELS, is_new=True)
            app = _host(editor)
            async with app.run_test(size=(140, 55)) as pilot:
                await pilot.pause(0.2)
                area = editor.query_one("#lineup-section-budget", TextArea)
                for bad, needle in (("max_budget_usd: [20\n", "invalid YAML"), ("- a\n- b\n", "mapping")):
                    area.text = bad
                    await pilot.pause(0.05)
                    editor.action_save()
                    await pilot.pause(0.05)
                    hint = _static_text(editor.query_one("#lineup-hint", Static))
                    ctx.check(f"{bad!r}: not saved, hint names budget and {needle!r}, got {hint!r}",
                              hint.startswith("Not saved") and "budget" in hint and needle in hint)
                    ctx.check("the editor stays open", app.screen is editor)
    asyncio.run(body())


# ---- f75 ------------------------------------------------------------------------------

@test
def test_f75_clear_resets_the_auto_title_first_turn_counter(ctx: Ctx):
    async def body():
        with _Env():
            fake, app = _app()
            fake.clear_session = lambda: None
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause(0.2)
                app._turn_done_count = 3
                await _submit(app, "/clear")
                await pilot.pause(0.2)
                ctx.check(f"the counter starts over, got {app._turn_done_count}", app._turn_done_count == 0)
    asyncio.run(body())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
