"""tests.test_wizard_team_switch_sync -- the wizard's "Roles and lineup" step keeps its switch and its lineup list as one
choice through deferred messages. A `Switch.Changed` the step's own sync caused can arrive AFTER the list moved on; before
the fix (Windows shard 1, run 41600166305) that stale message re-highlighted the active lineup, and the two messages it
spawned settled on the wrong row for good. Hermetic: no network, no model; a scratch home per `plans/WORKER-RULES.md`.
"""
from __future__ import annotations

TIER = "full"  # a TUI pilot (Textual run_test)

import asyncio
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

REPO_DIR = Path(__file__).resolve().parent.parent
test, TESTS = new_registry()


class _Env:
    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
        d = Path(tempfile.mkdtemp(prefix="wiz-switch-"))
        os.environ["BRIDGE_TEST_HOME"] = str(d)
        os.environ["BRIDGE_STATE_DIR"] = str(d / ".halo")
        return self

    def __exit__(self, *exc):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _text(widget) -> str:
    return str(widget.renderable) if hasattr(widget, "renderable") else str(widget.render())


async def _settled(pilot, ready, timeout: float = 30.0) -> None:
    import time as _t
    end = _t.monotonic() + timeout
    while not ready() and _t.monotonic() < end:
        await pilot.pause(0.1)


@test
def test_a_stale_changed_from_the_steps_own_sync_never_moves_the_list(ctx: Ctx):
    from textual.widgets import OptionList, Switch

    from halo_harness.tui.dialogs.init_wizard import InitWizardApp, WizardState

    async def body():
        with _Env():
            state = WizardState(cwd=REPO_DIR, step_keys=("roles",), no_live=True)
            app = InitWizardApp(state)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause(0.15)
                step = app.screen
                preview = step.query_one("#wiz-team-preview")
                lst = step.query_one("#wiz-team-lineups-list", OptionList)
                switch = step.query_one("#wiz-roles-switch", Switch)
                lst.highlighted = 1
                await _settled(pilot, lambda: " -> " in _text(preview) and switch.value)
                lst.highlighted = 0
                await _settled(pilot, lambda: "Halo uses" in _text(preview) and not switch.value and not step._mine)
                ctx.check(f"the first row: the sentence, the switch off, the sync queue drained, got {_text(preview)[:40]!r} "
                          f"{switch.value} {step._mine}", "Halo uses" in _text(preview) and not switch.value and not step._mine)
                # the race: the Changed(True) the sync posted when the list stood on row 1 is delivered only now
                step._mine.append(True)
                step.on_switch_changed(Switch.Changed(switch, True))
                await pilot.pause(0.3)
                ctx.check(f"a stale Changed from the step's own sync leaves row 0 highlighted, got {lst.highlighted} "
                          f"{_text(preview)[:40]!r}", lst.highlighted == 0 and "Halo uses" in _text(preview))
                ctx.check("and is consumed", not step._mine)
                # the user's own flip (nothing of ours pending) still moves the list to a lineup
                step.on_switch_changed(Switch.Changed(switch, True))
                await _settled(pilot, lambda: " -> " in _text(preview))
                ctx.check(f"the user's flip highlights a lineup, got {lst.highlighted} {_text(preview)[:40]!r}",
                          lst.highlighted not in (None, 0) and " -> " in _text(preview))
    asyncio.run(body())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
