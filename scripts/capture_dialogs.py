"""scripts/capture_dialogs.py -- the dialog and HUD front-page capture scenes
(Halo 2.0.10 round 6), plus `SCENES`, the registry `tools/capture_screens.py`
reads. Same rules as `capture_scenes.py`: fixture data only, the shared pilot
helpers of `scripts/screenshots.py`, one SVG string per frame."""

from __future__ import annotations

import capture_scenes as C

S = C.S
ev = C.ev


async def scene_picker(size, theme) -> list:
    models = list(S.PICKER_MODELS) + [
        {"ref": "or:demo/atlas-lite", "provider": "openrouter", "price_in_per_m": 0.03, "price_out_per_m": 0.11,
         "context_tokens": 131_072, "speed_ttft_s": 0.2, "speed_tokens_per_second": 180},
        {"ref": "or:demo/forge-72b", "provider": "openrouter", "price_in_per_m": 0.40, "price_out_per_m": 1.20,
         "context_tokens": 128_000, "speed_ttft_s": 1.1, "speed_tokens_per_second": 48},
        {"ref": "or:demo/forge-72b:free", "provider": "openrouter", "price_in_per_m": 0, "price_out_per_m": 0,
         "context_tokens": 64_000, "speed_ttft_s": 2.4, "speed_tokens_per_second": 21},
        {"ref": "dbx:demo-kimi", "provider": "databricks", "context_tokens": 256_000, "dbu": "$0.011/1k",
         "detail": "kimi · mlflow"},
        {"ref": "ol:demo-coder:14b", "provider": "ollama", "group": "Ollama (default)"},
    ]
    return [await S.picker_svg(models, size)]


def _tasks_rows() -> list:
    def row(aid, title, model, status, tools, cost, elapsed, depth, parent=None):
        return {"agent_id": aid, "task_id": aid, "title": title, "model": model, "status": status, "is_error": False,
                "tool_count": tools, "cost_usd": cost, "elapsed_s": elapsed, "depth": depth,
                "parent_agent_id": parent, "log_path": ""}
    return [
        row("a1", "Lead", "or:demo/atlas-pro", "running", 7, 0.0412, 312.0, 0),
        row("a2", "Planner", "or:demo/atlas-pro", "completed", 5, 0.0120, 64.0, 1, "a1"),
        row("a3", "Implementer", "ol:demo-coder:14b", "running", 22, 0.0, 188.0, 1, "a1"),
        row("a4", "Tester", "or:demo/atlas-flash", "running", 9, 0.0031, 95.0, 2, "a3"),
        row("a5", "Reviewer", "or:demo/atlas-flash", "queued", 0, 0.0, 0.0, 1, "a1"),
        row("a6", "Docs", "or:demo/atlas-lite", "queued", 0, 0.0, 0.0, 1, "a1"),
    ]


async def scene_tasks(size, theme) -> list:
    from halo_harness.tui.dialogs.tasks import TasksPanel
    app = C.BridgeApp(C.FakeController(model=C.MODEL, agent_tasks=_tasks_rows()), cwd=C.CWD, theme_name=theme)
    async with app.run_test(size=size) as pilot:
        await C.history(app)
        await C.play(app, [ev.user_message("/tasks", turn=C.LIVE)])
        app.push_screen(TasksPanel(list_agent_tasks=app.controller.list_agent_tasks,
                                   read_task_board=app.controller.read_task_board))
        await pilot.pause(0.3)
        return [await S._export(app, pilot)]


def _mcp_servers() -> list:
    return [
        {"name": "fs-tools", "type": "stdio", "command": "fs-tools-server", "args": ["--root", "."], "state": "connected",
         "error": None, "tool_count": 12, "scope": "user", "backoff_status": None},
        {"name": "issue-tracker", "type": "http", "url": "https://tracker.example.invalid:8443/mcp", "command": None,
         "args": [], "state": "failed", "error": "connection refused", "tool_count": 0, "scope": "project",
         "backoff_status": "retry in 20 s"},
        {"name": "connector__claude-docs", "type": "connector", "state": "connected", "connector_name": "Claude Docs",
         "url": "https://connector.example.invalid/docs", "host": "connector.example.invalid", "tool_count": 9,
         "status_text": "connected"},
        {"name": "connector__team-calendar", "type": "connector", "state": "needs_auth", "connector_name": "Team Calendar",
         "url": "https://connector.example.invalid/calendar", "host": "connector.example.invalid", "tool_count": 0,
         "status_text": "needs authentication"},
    ]


async def scene_mcp(size, theme) -> list:
    return [await S.mcp_svg(_mcp_servers, size)]


async def scene_hud(size, theme, name: str) -> list:
    variant = {"doom": None, "metroid": "norfair", "mario": "bros"}[name]
    async def prelude(app):
        await C.history(app, first_turn=-1)  # turns -1 and 0: the HUD scene's own events are turn 1
    return [await S.game_theme_svg(name, variant, size, prelude=prelude)]


async def scene_review(size, theme) -> list:
    from halo_harness.tui.widgets.review_cards import ReviewCard, ReviewHeader
    findings = [
        {"file": "src/session/loop.py", "line": 142, "severity": "high", "verdict": "CONFIRMED", "category": "correctness",
         "short_summary": "A steer that arrives during a tool call is dropped when the call raises.",
         "summary": "The pending-steer list is cleared before the tool result is recorded, so a raised tool error "
                    "loses the user's words.",
         "failure_scenario": "Type a steer while a Bash call is running; the call times out; the steer never reaches the model.",
         "reason": "Reproduced by reading the clear() ordering at line 138-142."},
        {"file": "src/net/client.py", "line": 57, "severity": "medium", "verdict": "CONFIRMED", "category": "security",
         "short_summary": "The retry path logs the full request headers.",
         "failure_scenario": "A failed call writes the authorization header to the debug log."},
        {"file": "src/ui/picker.py", "line": 311, "severity": "medium", "verdict": "PLAUSIBLE", "category": "performance",
         "short_summary": "The picker re-sorts every row on each keypress.",
         "failure_scenario": "Roughly 400 rows with a held-down arrow key stutters."},
        {"file": "tests/test_picker.py", "line": 88, "severity": "low", "verdict": "PLAUSIBLE", "category": "tests",
         "short_summary": "The column-order test never covers the free variants."},
    ]
    app = C.new_app(theme)
    async with app.run_test(size=size) as pilot:
        await C.history(app)
        await C.play(app, [ev.user_message("/review", turn=C.LIVE)])
        await app.transcript.mount_widget(ReviewHeader(
            "Review of main..feature/steer-fix: 4 findings (2 confirmed, 2 plausible) from 5 reviewers in 94 s, $0.18"))
        for i, finding in enumerate(findings, 1):
            card = ReviewCard(finding, i)
            if i == 1:
                card.expanded = True
                card._render_card()
            await app.transcript.mount_widget(card)
        return [await S._export(app, pilot)]


async def scene_remote(size, theme) -> list:
    snap = S.remote_fixture_snap()
    snap["pending"] = [{"index": 1, "aci": "a1b2c3d4-0000-4000-8000-000000000001", "aci_prefix": "a1b2c3d4",
                        "number": "+15555550101", "state": "pending", "first_seen": 0,
                        "safety_number": "11111 22222 33333 44444 55555 66666 77777 88888 99999 00000 11111 22222"}]
    return [await S.remote_svg(snap, size, code=None)]


def _hud(name):
    async def scene(size, theme):
        return await scene_hud(size, theme, name)
    return scene


async def scene_level(size, theme, name: str) -> list:
    """2.0.11 round A3: the level band mid-turn, four frames of the hero
    running and the enemy crossing (the still is the last frame)."""
    variant = {"doom": None, "metroid": "norfair", "mario": "bros"}[name]

    async def prelude(app):
        await C.history(app, first_turn=-1)
    frames = tuple(range(40, 46)) if name != "doom" else tuple(range(12, 18))  # 3.0.2.0: six frames, a stride and a shot
    return await S.game_theme_svg(name, variant, size, prelude=prelude, band_frames=frames)


def _level(name):
    async def scene(size, theme):
        return await scene_level(size, theme, name)
    return scene


SCENES = {
    "turn-phase": C.scene_turn_phase, "auto": C.scene_auto, "steer": C.scene_steer, "pending-dock": C.scene_pending_dock,
    "picker": scene_picker, "tasks": scene_tasks, "mcp": scene_mcp, "review": scene_review, "remote": scene_remote,
    "hud-doom": _hud("doom"), "hud-metroid": _hud("metroid"), "hud-mario": _hud("mario"),
    "level-doom": _level("doom"), "level-metroid": _level("metroid"), "level-mario": _level("mario"),
}
