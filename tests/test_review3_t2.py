"""tests.test_review3_t2 -- pins for the 3.0.2.0 review fix pass, round T-tui
(dialogs and the wizard):

  * item 76  a corrupt studio.json port reads as "no Studio", never a crash
  * item 77  Back from a step the Summary jumped to returns the index too
  * item 79  the Studio URL stays on screen; a newer hint is never cleared early
  * item 146 re-picking a role's model keeps its escalation override
  (item 147, Org mode's switch, went with Org in 3.1.4.0)

Item 78 (picker speed) and item 162 (game status bar) are in _t3; 148/149 in _t4.

Run: python -m tests.test_review3_t2
"""
from __future__ import annotations

TIER = "full"  # a TUI pilot (Textual run_test): the full tier

import asyncio
import json
import sys
import time
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _text(widget) -> str:
    return str(widget.renderable) if hasattr(widget, "renderable") else str(widget.render())


def _host():
    from textual.app import App
    return App()


@test
def test_item146_new_model_keeps_the_escalation_override(ctx: Ctx):
    from textual.widgets import Input
    from halo_harness.tui.dialogs.roles_editor import RolesEditor

    async def body():
        app = _host()
        async with app.run_test(size=(110, 40)) as pilot:
            ed = RolesEditor("t", {"reviewer": {"model": "or:a/b", "effort": "high", "escalation": False}}, [])
            app.push_screen(ed)
            await pilot.pause(0.2)
            ed._pending_role, ed._pending_model, ed._pending_agent = "reviewer", "or:c/d", None
            ok = ed._commit_pending("high", ed.query_one("#roles-effort-input", Input))
            ctx.check(f"committed, got {ed.roles['reviewer']}", ok and ed.roles["reviewer"] ==
                      {"model": "or:c/d", "escalation": False, "effort": "high"})
            ed.roles["plain"] = "or:x/y"
            ed._pending_role, ed._pending_model, ed._pending_agent = "plain", "or:z/w", None
            ed._commit_pending("", ed.query_one("#roles-effort-input", Input))
            ctx.check(f"a role with nothing extra stays a bare string, got {ed.roles['plain']!r}",
                      ed.roles["plain"] == "or:z/w")
    asyncio.run(body())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
