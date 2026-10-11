"""scripts/capture_scenes.py -- the front-page capture scenes (Halo 2.0.10 round 6).

Each scene is `async def scene(size, theme) -> list[str]`: one Textual-export
SVG string per frame (one frame for a still, 3-4 for an animated capture),
driven through the SAME pilot helpers `scripts/screenshots.py` uses (its
frozen clock, seeded tips, normalized export id, `_stage_elapsed` seam) over
fixture data only -- a scripted FakeController, mock rows, fake phones. The
list of captures (name, scene, size, theme, scale) is `tools/captures.json`;
`tools/capture_screens.py` renders them.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import screenshots as S  # noqa: E402  (sets the scoped env + frozen clock on import)

ev = S.ev
apply_event = S.apply_event
BridgeApp = S.BridgeApp
FakeController = S.FakeController
NOW = S._NOW
MODEL = S.MODEL
CWD = S.CWD

_THEME_NAME = "claude-dark"


def new_app(theme: str, **kw) -> "BridgeApp":
    return BridgeApp(FakeController(model=MODEL), cwd=CWD, theme_name=theme or _THEME_NAME, **kw)


def tool(turn: int, tid: str, name: str, args: dict) -> list:
    return [ev.Event("tool_use_start", {"id": tid, "name": name}, turn=turn),
            ev.Event("tool_use_ready", {"id": tid, "name": name, "input": args, "repaired": False}, turn=turn)]


def result(turn: int, tid: str, summary: str, content: str = "") -> "ev.Event":
    return ev.Event("tool_result", {"id": tid, "ok": True, "summary": summary, "content": content or summary}, turn=turn)


async def play(app, events) -> None:
    for e in events:
        await apply_event(app, e)


LIVE = 3  # the turn number of the live turn every scene plays out (two finished turns come before it)


async def history(app, first_turn: int = 1) -> None:
    """Two finished turns above the live one (turns first_turn, first_turn+1),
    so the page is a conversation and not a blank screen with one line."""
    t, u = first_turn, first_turn + 1
    await play(app, [
        ev.user_message("Which files define the picker's sort keys?", turn=t),
        ev.status(phase="thinking", model=MODEL, turn=t),
        ev.Event("message_start", {"model": MODEL}, turn=t),
        *tool(t, f"g{t}", "Grep", {"pattern": "SORT_KEYS", "path": "halo_harness"}),
        result(t, f"g{t}", "3 matches in 2 files"),
        ev.message_end(turn=t, stop_reason="tool_use", usage={"input_tokens": 1800, "output_tokens": 40}),
        ev.Event("message_start", {"model": MODEL}, turn=t),
        ev.text_delta("Two files: the dialog's key list and the row formatter.", turn=t),
        ev.message_end(turn=t, stop_reason="end_turn", usage={"input_tokens": 1900, "output_tokens": 60}, cost_usd=0.004),
        ev.turn_done(turn=t, reason="end_turn"),
        ev.user_message("Why does the picker show a blank price for the local models?", turn=u),
        ev.status(phase="thinking", model=MODEL, turn=u),
        ev.Event("message_start", {"model": MODEL}, turn=u),
        ev.text_delta("Let me look at how the row is formatted.\n", turn=u),
        *tool(u, f"h{u}", "Read", {"file_path": "halo_harness/model_display.py"}),
        result(u, f"h{u}", "Read 412 lines"),
        ev.message_end(turn=u, stop_reason="tool_use", usage={"input_tokens": 3100, "output_tokens": 90}),
        ev.Event("message_start", {"model": MODEL}, turn=u),
        ev.text_delta("A local route has no published price, so `format_picker_row` prints `?` for it on "
                      "purpose: a blank cell could be misread as a real zero. Nothing is broken.", turn=u),
        ev.message_end(turn=u, stop_reason="end_turn", usage={"input_tokens": 3500, "output_tokens": 140}, cost_usd=0.0112),
        ev.turn_done(turn=u, reason="end_turn"),
    ])
    app.status_bar.apply_status({"model": MODEL, "context_tokens": 38_000, "context_limit": 1_000_000,
                                 "cost_usd": 0.0112, "permission_mode": "auto", "effort": "high",
                                 "mcp": {"connected": 2, "total": 2, "tools": 24}})
    app.status_bar.set_cwd_branch(CWD, "main")


def _line(app, turn: int):
    return app.transcript._phase_lines.get((None, turn))


async def scene_turn_phase(size, theme) -> list:
    """The phase line counting (sending -> no tokens yet -> reasoning with a
    live token count) and then collapsing to its 'Thought for' summary."""
    frames = []
    app = new_app(theme)
    async with app.run_test(size=size) as pilot:
        await history(app)
        await play(app, [ev.user_message("Add a rotate tool to the model picker", turn=LIVE),
                         ev.status(phase="thinking", model=MODEL, turn=LIVE),
                         ev.phase(state="request_sent", turn=LIVE, model=MODEL)])

        def stage(seconds):
            def run():
                block = _line(app, LIVE)
                if block is not None:
                    S._stage_elapsed(block, seconds)
                app.status_bar._phase_started_at = NOW - seconds
            return run

        frames.append(await S._export(app, pilot, stage=stage(0.6)))
        await play(app, [ev.phase(state="headers", turn=LIVE, model=MODEL, ttfb_ms=4200)])
        frames.append(await S._export(app, pilot, stage=stage(5.0)))
        await play(app, [ev.Event("message_start", {"model": MODEL}, turn=LIVE),
                         ev.phase(state="first_token", turn=LIVE, model=MODEL, kind="reasoning"),
                         ev.thinking_delta("The picker rows come from format_picker_row. A rotate tool means a new sort "
                                           "key, so the key list in the dialog and the row format both change. "
                                           "Checking the tests that pin the column order first.", turn=LIVE)])
        frames.append(await S._export(app, pilot, stage=stage(11.0)))
        _line(app, LIVE).started_at = NOW - 18.0  # enter_done reads this: 'Thought for 18s'
        await play(app, [ev.text_delta("The new sort key goes in the dialog's key list and in the row format; the "
                                       "column-order tests are the only other place that needs to know.", turn=LIVE),
                         ev.message_end(turn=LIVE, stop_reason="end_turn", usage={"input_tokens": 4000, "output_tokens": 210},
                                        cost_usd=0.0238),
                         ev.turn_done(turn=LIVE, reason="end_turn")])
        app.status_bar.apply_status({"cost_usd": 0.0238, "context_tokens": 42_000, "context_limit": 1_000_000})
        frames.append(await S._export(app, pilot))
    return frames


async def scene_steer(size, theme) -> list:
    """A steer landing mid-turn: a long tool call is running, the user types,
    the words appear at once as a real message, then the turn takes them."""
    frames = []
    app = new_app(theme)
    async with app.run_test(size=size) as pilot:
        await history(app)
        await play(app, [ev.user_message("Rename the sort key and run the picker tests", turn=LIVE),
                         ev.status(phase="thinking", model=MODEL, turn=LIVE),
                         ev.phase(state="request_sent", turn=LIVE, model=MODEL),
                         ev.Event("message_start", {"model": MODEL}, turn=LIVE),
                         ev.text_delta("Renaming the key, then running the suite.\n", turn=LIVE),
                         *tool(LIVE, "s1", "Bash", {"command": "python -m tests.test_picker"})])

        def stage_tool(seconds):
            def run():
                for block in app.transcript.children:
                    if isinstance(block, S._cards.ToolCard) and block.status == "running":
                        S._stage_elapsed(block, seconds)
                app.status_bar._phase_started_at = NOW - seconds
            return run

        frames.append(await S._export(app, pilot, stage=stage_tool(41.0)))
        steer = "also keep the old key working as an alias"
        await play(app, [ev.Event("steer_queued", {"text": steer}, turn=LIVE)])
        frames.append(await S._export(app, pilot, stage=stage_tool(43.0)))
        await play(app, [result(LIVE, "s1", "212 passed"), ev.Event("steer_applied", {"text": steer}, turn=LIVE),
                         ev.message_end(turn=LIVE, stop_reason="tool_use", usage={"input_tokens": 4200, "output_tokens": 60}),
                         ev.phase(state="waiting_for_model", turn=LIVE)])
        frames.append(await S._export(app, pilot, stage=lambda: setattr(app.status_bar, "_phase_started_at", NOW - 1.0)))
        await play(app, [ev.phase(state="request_sent", turn=LIVE, model=MODEL),
                         ev.Event("message_start", {"model": MODEL}, turn=LIVE),
                         ev.phase(state="first_token", turn=LIVE, model=MODEL, kind="text"),
                         ev.text_delta("Done: the tests pass, and `price` still resolves to the new key as an alias, "
                                       "so existing configs keep working.", turn=LIVE)])
        frames.append(await S._export(app, pilot, stage=lambda: (
            S._stage_elapsed(_line(app, LIVE), 3.0), setattr(app.status_bar, "_phase_started_at", NOW - 3.0))))
    return frames


async def scene_pending_dock(size, theme) -> list:
    """Two asks queued at once: the dock holds the first above the prompt, the
    status bar counts both, the transcript keeps a marker for each."""
    app = new_app(theme)
    async with app.run_test(size=size) as pilot:
        await history(app)
        edit = {"file_path": "halo_harness/model_display.py", "old_string": "speed={speed}", "new_string": "speed={speed} rot={rot}"}
        await play(app, [
            ev.user_message("Wire the rotate column into the row format and run the suite", turn=LIVE),
            ev.Event("tool_use_ready", {"id": "p1", "name": "Edit", "input": edit, "repaired": False}, turn=LIVE),
            ev.Event("permission_request", {"id": "p1", "name": "Edit", "input": edit,
                                            "reason": "matches your ask rule Edit(halo_harness/*)",
                                            "suggested_rule": "Edit(halo_harness/model_display.py)"}, turn=LIVE),
            ev.Event("tool_use_ready", {"id": "p2", "name": "Bash", "input": {"command": "python -m tests.test_picker"},
                                        "repaired": False}, turn=LIVE),
            ev.Event("permission_request", {"id": "p2", "name": "Bash", "input": {"command": "python -m tests.test_picker"},
                                            "reason": "not covered by an existing rule",
                                            "suggested_rule": "Bash(python -m tests.*)"}, turn=LIVE)])
        app.transcript.scroll_end(animate=False)
        await pilot.pause(0.1)
        return [await S._export(app, pilot)]


async def scene_auto(size, theme) -> list:
    """Auto mode: a turn that edits, runs the tests and finishes with no ask
    anywhere (the status bar says `auto`; nothing waits for the user)."""
    app = new_app(theme)
    async with app.run_test(size=size) as pilot:
        await history(app)
        edit = {"file_path": "halo_harness/model_display.py", "old_string": "speed={speed}", "new_string": "speed={speed} rot={rot}"}
        await play(app, [
            ev.user_message("Wire the rotate column into the row format and run the suite", turn=LIVE),
            ev.status(phase="thinking", model=MODEL, turn=LIVE),
            ev.Event("message_start", {"model": MODEL}, turn=LIVE),
            ev.text_delta("Editing the row format, then running the picker tests.\n", turn=LIVE),
            *tool(LIVE, "a1", "Edit", edit), result(LIVE, "a1", "Edited model_display.py (+1 -1)"),
            *tool(LIVE, "a2", "Bash", {"command": "python -m tests.test_picker"}), result(LIVE, "a2", "212 passed in 3.1 s"),
            ev.message_end(turn=LIVE, stop_reason="tool_use", usage={"input_tokens": 4300, "output_tokens": 120}),
            ev.Event("message_start", {"model": MODEL}, turn=LIVE),
            ev.text_delta("Done: the column is in the row format and all 212 picker tests pass. Nothing needed your "
                          "approval -- no rule asked, so nothing stopped.", turn=LIVE),
            ev.message_end(turn=LIVE, stop_reason="end_turn", usage={"input_tokens": 4500, "output_tokens": 180}, cost_usd=0.0301),
            ev.turn_done(turn=LIVE, reason="end_turn")])
        app.status_bar.apply_status({"cost_usd": 0.0301, "context_tokens": 47_000, "context_limit": 1_000_000})
        return [await S._export(app, pilot)]
