"""tests.test_ready_lines_tui -- Halo 3.6.0.5 C15, the terminal part: after a Builder card is applied in a session on
Auto, the Builder's card in the terminal shows, right under its header and so while it is folded, the lines that say
what is ready in this session now and what waits for the next session. The one source is the Builder tool result's
own lines (the terminal never receives `builder_done`): tui/dispatch.py READY_FIRST_WORDS, the first words
crew/ready_now.py writes. No other card ever shows them.

A real Auto session turn against the mock upstream (tests.test_ready_lines `_drive`); its own yielded events are fed to
a Textual pilot. Run: python -m tests.test_ready_lines_tui
"""

from __future__ import annotations

TIER = "full"  # a TUI pilot (Textual run_test): the full tier

import asyncio
import sys
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.test_ready_lines import CARD, P1_BOTH, P1_REVIEW, P2_STEP, _apply_all, _drive, _scoped  # noqa: E402

test, TESTS = new_registry()


def _app():
    from halo_harness.testing.fake_controller import FakeController
    from halo_harness.tui.app import BridgeApp
    return BridgeApp(FakeController(), cwd="~/project")


def _event(kind: str, data: dict):
    from halo_harness.events import Event
    return Event(kind, data)


@test
def test_terminal_builder_card_shows_p_lines_while_folded(ctx: Ctx):
    got: dict = {}

    def body(home):
        out = _drive(CARD, _apply_all, home=home)
        ctx.check(f"the turn ended without an error, got {out['error']!r}", out["ended"] and out["error"] is None)
        ready = next((e for e in out["events"] if e.kind == "tool_use_ready" and e.data.get("name") == "Builder"), None)
        result = next((e for e in out["events"] if e.kind == "tool_result" and ready is not None
                       and e.data.get("id") == ready.data.get("id")), None)
        got["ready"], got["result"] = ready, result
    _scoped(body)
    ready, result = got.get("ready"), got.get("result")
    ctx.check("the loop yielded the Builder's tool_use_ready and its tool_result", ready is not None and result is not None)
    if ready is None or result is None:
        return
    from halo_harness.tui.dispatch import apply_event

    async def run():
        app = _app()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.1)
            await apply_event(app, ready)
            await apply_event(app, result)
            await pilot.pause(0.1)
            card = app.transcript.tool_cards[ready.data["id"]]
            text = card._last_rendered or ""
            lines = text.split("\n")
            first = lines[0]
            ctx.check(f"the card is folded, got expanded={card.expanded}", card.expanded is False)
            ctx.check(f"right under the first header line: P1, then the card's status row, got {lines[:4]!r}",
                      lines[1:2] == ["  " + P1_BOTH] and len(lines) > 2
                      and not lines[2].lstrip().startswith(("Ready", "Saved", "Not run")))
            ctx.check(f"the first line is the Builder's own header, got {first!r}",
                      first.startswith("⏺") and not first.lstrip("⏺ ").startswith(("Ready", "Saved", "Not run")))
            # a Read card whose result holds the same lines: its header holds neither
            await apply_event(app, _event("tool_use_ready", {"id": "call_read", "name": "Read",
                                                             "input": {"file_path": "notes.txt"}}))
            await apply_event(app, _event("tool_result", {"id": "call_read", "ok": True, "summary": "2 lines",
                                                          "content": P1_REVIEW + "\n" + P2_STEP}))
            await pilot.pause(0.1)
            other = app.transcript.tool_cards["call_read"]
            ctx.check(f"another tool's card: no line in its header, got {other.header!r}",
                      P1_REVIEW not in other.header and P2_STEP not in other.header)
    asyncio.run(run())


@test
def test_terminal_first_words_are_ready_now_s(ctx: Ctx):
    from halo_harness.crew import ready_now
    from halo_harness.tui.dispatch import READY_FIRST_WORDS
    ctx.check("the terminal's three first words are ready_now.FIRST_WORDS", READY_FIRST_WORDS == ready_now.FIRST_WORDS)
    answer = {"ready": ["review"], "p3": ["tidy"],
              "later": [{"kind": "workflow", "name": "plan", "why": "WF"},
                        {"kind": "agent", "name": "checker", "why": "AG1", "step": "review"},
                        {"kind": "agent", "name": "coder", "why": "AG2"}]}
    lines = ready_now.p_lines(answer)
    ctx.check(f"every line p_lines writes starts with one of them, got {lines}",
              len(lines) == 5 and all(ln.startswith(READY_FIRST_WORDS) for ln in lines))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
