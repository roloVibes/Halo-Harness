"""scripts/screenshots.py -- the reproducible TUI gallery (2.0.5 round 2d).

Drives the REAL TUI with Textual pilots over fixture data only -- a
scripted FakeController turn, fixture picker rows, fixture bios and the
shipped team templates, a fake MCP server list, a fixture permission ask,
fixture balances -- and saves one SVG per scene (120x36) under
docs/screenshots/: launch, turn, picker, team-step, mcp, permission,
balances, theme-doom, theme-metroid, theme-mario. Deterministic by construction: fixed seed, a frozen clock in
the widget modules (elapsed text is set through the same started_at /
_refresh seams the tests use, never a real timer read), no network, no
real keys, no real paths (the session cwd is the literal "~/project"),
and the real ~/.halo is never touched (BRIDGE_TEST_HOME points at a
fresh scratch dir before any halo_harness import). A rerun produces
byte-identical files; the committed SVGs are this script's output.

Usage: python scripts/screenshots.py [--out docs/screenshots]
"""

from __future__ import annotations

import argparse
import asyncio
import os
import random
import re
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

# Scoped state BEFORE the first halo_harness import (same rule as the
# suites): a fresh scratch home, background net off, Ollama parked.
os.environ["BRIDGE_TEST_HOME"] = tempfile.mkdtemp(prefix="halo-shots-home-")
os.environ["BRIDGE_TEST_NO_BACKGROUND_NET"] = "1"
os.environ.setdefault("OLLAMA_HOST", "http://127.0.0.1:1")
for _k in [k for k in os.environ if k.startswith(("HALO_", "ROLO_CLAUDE_"))]:
    del os.environ[_k]
random.seed(2026)

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402

ensure_default_provider_credentials()

from halo_harness import events as ev  # noqa: E402
from halo_harness.testing.fake_controller import FakeController  # noqa: E402
from halo_harness.tui.app import BridgeApp  # noqa: E402
from halo_harness.tui.dispatch import apply_event  # noqa: E402

# Frozen clock: the widget modules' own `time` handles return a constant,
# so every elapsed reading is whatever a seam set it to (never a real
# timer read) and the export cannot vary run to run.
_NOW = 1_000_000.0


class _FrozenTime:
    def monotonic(self) -> float:
        return _NOW

    def time(self) -> float:
        return 1_760_000_000.0

    def sleep(self, seconds: float) -> None:  # pragma: no cover - unused
        raise AssertionError("screenshots never sleep through widget time")


import halo_harness.tui.widgets.transcript as _tr  # noqa: E402
import halo_harness.tui.widgets.statusbar as _sb  # noqa: E402
import halo_harness.tui.widgets.cards as _cards  # noqa: E402

for _mod in (_tr, _sb, _cards):
    _mod.time = _FrozenTime()

# The intro is always the banner entry (pool line 0), never a random pick.
import halo_harness.tui.intro_lines as _il  # noqa: E402

_il.intro_text = lambda version, **kw: _il.INTRO_LINES[0].format(version=version)

# Every TipRotator gets the SAME seeded rng, so the mount-time tip draw
# (the prompt placeholder) is identical in every scene and every run.
# Seed 17 was chosen so that first draw equals the tip the committed
# docs/harness/tui-snapshots/*.svg renders already show -- test_tui.py
# regenerates those on every run, and a different tip would churn them
# (verified through the real pilot path, not the bare module pool).
import halo_harness.tui.tips as _tips  # noqa: E402

_OrigTipRotator = _tips.TipRotator


class _SeededTipRotator(_OrigTipRotator):
    def __init__(self, tips, **kw):
        kw["rng"] = random.Random(17)
        super().__init__(tips, **kw)


_tips.TipRotator = _SeededTipRotator

SIZE = (120, 36)
CWD = "~/project"  # fixture path, shown in the status bar -- never a real one
MODEL = "or:demo/atlas-pro"  # fixture ref, obviously not a real model id


def _write_svg(path: Path, svg: str) -> None:
    """LF line endings on every platform (newline= is 3.10+, the floor of
    requires-python) so a rerun is byte-identical to the committed file
    however the box's git handles autocrlf (pinned LF by .gitattributes)."""
    path.write_text(svg, encoding="utf-8", newline="\n")


def _stage_elapsed(widget, seconds: float, refresh_name: str = "_refresh") -> None:
    """Set a widget's elapsed reading through its own seams: started_at
    back-dated against the frozen clock, then its own re-render method,
    exactly the way a test drives the same widget."""
    widget.started_at = _NOW - seconds
    for name in (refresh_name, "_refresh_display"):
        fn = getattr(widget, name, None)
        if callable(fn):
            fn()
            return


async def _export(app, pilot, stage=None) -> str:
    """Flush one refresh pass, then export synchronously. `stage` (an
    optional callable run AFTER the flush and BEFORE the export) is where
    a scene sets elapsed readings through the widget seams -- running it
    here, with no `await` between it and the export, is what makes those
    readings stick: a drain tick between a staged write and the export
    would re-derive elapsed from `time.monotonic()` and clobber it (the
    frozen clock makes that a constant, but the clock's own RESTART on a
    phase-word event resets `_phase_started_at` to NOW, i.e. 0 s).
    Textual's random per-export CSS id is normalized so a rerun is
    byte-identical. The status bar's cwd segment is pinned to the
    fixture string verbatim: `BridgeApp.__init__` does `Path(cwd)`,
    which renders the fixture "~/project" as "~\\project" on Windows and
    "~/project" everywhere else (found by CI -- the Linux run failed the
    byte-parity check on exactly that slash flip)."""
    await pilot.pause(0)
    if stage is not None:
        stage()
    bar = getattr(app, "status_bar", None)
    if bar is not None:
        bar.spinner_index = 0
        if getattr(app, "cwd", None):
            bar.cwd = str(app.cwd).replace("\\", "/")
        bar._refresh_display()
    return re.sub(r"terminal-\d+-", "terminal-0-", app.export_screenshot())


async def _seed_bios() -> None:
    """Ship the bundled team templates into the scratch home so the Team
    step's Lineups pane renders real rows (the bios themselves are always
    reachable -- the shipped templates dir is already on the search path)."""
    from halo_harness.teams_yaml import ensure_builtin_team_templates
    ensure_builtin_team_templates()


async def scene_launch(out: Path) -> None:
    app = BridgeApp(FakeController(), cwd=CWD, show_intro=True)
    async with app.run_test(size=SIZE) as pilot:
        for _ in range(10):
            await app._drain()
            await pilot.pause(0.02)
        if app.intro_line is not None:
            app.intro_line.skip()
        _write_svg(out / "launch.svg", await _export(app, pilot))


async def scene_turn(out: Path) -> None:
    app = BridgeApp(FakeController(), cwd=CWD)
    async with app.run_test(size=SIZE) as pilot:
        for e in (
            ev.user_message("Add a rotate tool to the model picker", turn=1),
            ev.status(phase="thinking", model=MODEL, turn=1),
            ev.Event("message_start", {"model": MODEL}, turn=1),
            ev.thinking_delta("The picker rows come from format_picker_row; the sort keys live in the dialog.", turn=1),
            ev.text_delta("Let me check the current sort keys first.\n", turn=1),
            ev.Event("tool_use_start", {"id": "tu1", "name": "Grep"}, turn=1),
            ev.Event("tool_use_ready", {"id": "tu1", "name": "Grep",
                                        "input": {"pattern": "def _sort", "path": "halo_harness"}, "repaired": False}, turn=1),
        ):
            await apply_event(app, e)

        def stage():
            for block in app.transcript.children:
                if isinstance(block, _tr.ThinkingBlock):
                    _stage_elapsed(block, 18.0)
                if isinstance(block, _cards.ToolCard):
                    _stage_elapsed(block, 4.0)
            app.status_bar._phase_started_at = _NOW - 18.0

        _write_svg(out / "turn.svg", await _export(app, pilot, stage=stage))


async def scene_picker(out: Path) -> None:
    from halo_harness.tui.dialogs.model_picker import ModelPicker
    models = [
        {"ref": "or:demo/atlas-pro", "provider": "openrouter", "price_in_per_m": 0.65,
         "price_out_per_m": 3.25, "context_tokens": 1_000_000, "speed_ttft_s": 0.8, "speed_tokens_per_second": 65},
        {"ref": "or:demo/atlas-flash", "provider": "openrouter", "price_in_per_m": 0.07,
         "price_out_per_m": 0.28, "context_tokens": 262_144, "speed_ttft_s": 0.3, "speed_tokens_per_second": 120},
        {"ref": "dbx:demo-glm", "provider": "databricks", "context_tokens": 128_000,
         "dbu": "$0.015/1k", "detail": "glm · mlflow"},
        {"ref": "cc:demo-sonnet", "provider": "cc", "price_in_per_m": 3.0,
         "price_out_per_m": 15.0, "context_tokens": 1_000_000, "detail": "-> demo-sonnet"},
        {"ref": "ol:demo:32b", "provider": "ollama", "group": "Ollama (default)"},
        {"ref": "xp:demo-preview", "provider": "experiential", "price_in_per_m": 0,
         "price_out_per_m": 0, "context_tokens": 1_000_000, "speed_ttft_s": 0.9, "speed_tokens_per_second": 55},
    ]
    app = BridgeApp(FakeController(model=MODEL), cwd=CWD)
    async with app.run_test(size=SIZE) as pilot:
        app.push_screen(ModelPicker(models, current=MODEL))
        await pilot.pause(0.3)
        _write_svg(out / "picker.svg", await _export(app, pilot))


async def scene_team_step(out: Path) -> None:
    from textual.widgets import Switch
    from halo_harness.tui.dialogs.init_wizard import InitWizardApp, WizardState, _resolve_start_index, full_step_keys
    await _seed_bios()
    keys = full_step_keys()
    state = WizardState(cwd=os.environ["BRIDGE_TEST_HOME"], step_keys=keys,
                        index=_resolve_start_index("team", keys), no_live=True)
    app = InitWizardApp(state)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause(0.3)
        switch = app.screen.query_one("#wiz-team-switch", Switch)
        if not switch.value:
            await pilot.click("#wiz-team-switch")
            await pilot.pause(0.2)
        _write_svg(out / "team-step.svg", await _export(app, pilot))


async def scene_mcp(out: Path) -> None:
    from halo_harness.tui.dialogs.mcp_status import McpStatus

    def servers():
        return [
            {"name": "fixture-stdio", "type": "stdio", "command": "fixture-server", "args": [],
             "state": "connected", "error": None, "tool_count": 12, "scope": "user", "backoff_status": None},
            {"name": "broken-fixture", "type": "http", "command": "https://fixture.invalid/mcp", "args": [],
             "state": "failed", "error": "connection refused (fixture)", "tool_count": 0,
             "scope": "project", "backoff_status": None},
        ]

    app = BridgeApp(FakeController(), cwd=CWD)
    async with app.run_test(size=SIZE) as pilot:
        app.push_screen(McpStatus(servers(), test=lambda name, abort=None: [f"{name}: fixture"], refresh=servers))
        await pilot.pause(0.3)
        _write_svg(out / "mcp.svg", await _export(app, pilot))


async def scene_permission(out: Path) -> None:
    app = BridgeApp(FakeController(), cwd=CWD)
    async with app.run_test(size=SIZE) as pilot:
        for e in (
            ev.user_message("clean up the fixture build directory", turn=1),
            ev.Event("tool_use_ready", {"id": "tu1", "name": "Bash",
                                        "input": {"command": "rm -rf /tmp/fixture-build"}, "repaired": False}, turn=1),
            ev.Event("permission_request", {"id": "tu1", "name": "Bash",
                                            "input": {"command": "rm -rf /tmp/fixture-build"},
                                            "reason": "not covered by an existing rule",
                                            "suggested_rule": "Bash(rm -rf /tmp/fixture-build*)"}, turn=1),
        ):
            await apply_event(app, e)
        _write_svg(out / "permission.svg", await _export(app, pilot))


async def scene_balances(out: Path) -> None:
    from halo_harness.providers.balances import format_balances_table
    entries = {
        "openrouter": {"amount": 12.40, "kind": "limit_remaining"},
        "experiential": {"amount": 5.00, "kind": "credits"},
    }
    app = BridgeApp(FakeController(), cwd=CWD)
    async with app.run_test(size=SIZE) as pilot:
        app.status_bar.set_or_balance("OR $12.40 left")
        await apply_event(app, ev.user_message("/balances", turn=1))
        await apply_event(app, ev.system_note("\n".join(format_balances_table(entries))))
        await pilot.pause(0)
        _write_svg(out / "balances.svg", await _export(app, pilot))


async def _game_theme_scene(out: Path, theme: str, variant: "str | None" = None) -> None:
    """The main screen under a game theme (Halo 2.0.8): the HUD status bar
    mid-turn, with the face in its writing state. `variant` (a Metroid
    area, a Mario palette) is set on the app directly, never persisted."""
    app = BridgeApp(FakeController(model=MODEL), cwd=CWD, theme_name=theme)
    async with app.run_test(size=SIZE) as pilot:
        for e in (
            ev.user_message("Add a rotate tool to the model picker", turn=1),
            ev.status(phase="thinking", model=MODEL, turn=1),
            ev.Event("message_start", {"model": MODEL}, turn=1),
            ev.text_delta("The sort keys live in the picker dialog, so the new column goes there.\n", turn=1),
            ev.Event("tool_use_start", {"id": "tu1", "name": "Read"}, turn=1),
            ev.Event("tool_use_ready", {"id": "tu1", "name": "Read",
                                        "input": {"file_path": "halo_harness/tui/dialogs/model_picker.py"},
                                        "repaired": False}, turn=1),
            ev.text_delta("Next I will wire the column into the row format.", turn=1),
        ):
            await apply_event(app, e)
        bar = app.status_bar
        bar.hud_ascii = False
        if variant is not None:
            app.theme_variant = variant
            app.refresh_css(animate=False)
        app._sync_theme_chrome()
        bar.apply_status({"model": MODEL, "context_tokens": 312_000, "context_limit": 1_000_000,
                          "cost_usd": 0.0412, "permission_mode": "auto", "effort": "high",
                          "mcp": {"connected": 3, "total": 3, "tools": 41}})
        bar.set_provider_balance("openrouter", "OR $12.40 left")
        bar.set_cwd_branch(CWD, "main")
        bar.set_agents_running(2)
        bar.set_phase_word("writing")

        def stage():
            for block in app.transcript.children:
                if isinstance(block, _cards.ToolCard):
                    _stage_elapsed(block, 4.0)
            bar._phase_started_at = _NOW - 23.0
            bar._turn_started_at = _NOW - 23.0  # the HUD's TIME clock (Mario)

        _write_svg(out / f"theme-{theme}.svg", await _export(app, pilot, stage=stage))


async def scene_theme_doom(out: Path) -> None:
    await _game_theme_scene(out, "doom")


async def scene_theme_metroid(out: Path) -> None:
    """The Metroid HUD (Crateria): energy tanks, counters, the area panel,
    the visor face, the dashed map-grid border and the visor input frame."""
    await _game_theme_scene(out, "metroid", "crateria")


async def scene_theme_mario(out: Path) -> None:
    """The Mario HUD (bros): coins, timer, world, score, lives counters, the
    cap-and-moustache face, the brick border and the pipe input frame."""
    await _game_theme_scene(out, "mario", "bros")


SCENES = (scene_launch, scene_turn, scene_picker, scene_team_step, scene_mcp, scene_permission,
          scene_balances, scene_theme_doom, scene_theme_metroid, scene_theme_mario)


async def main(out: Path) -> int:
    out.mkdir(parents=True, exist_ok=True)
    for scene in SCENES:
        await scene(out)
        name = scene.__name__.replace("scene_", "").replace("_", "-")
        print(f"  wrote {out / (name + '.svg')}")
    print(f"{len(SCENES)} scenes -> {out}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Render the deterministic TUI screenshot gallery")
    parser.add_argument("--out", default=str(REPO / "docs" / "screenshots"), help="output directory")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(Path(args.out))))
