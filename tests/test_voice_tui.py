"""tests.test_voice_tui -- Halo 3.3.9.0 R2: voice in the TUI (tui/slash_voice.py, tui/voice_view.py, the status bar's
mic chip, the `voice` event in tui/dispatch.py), a Textual pilot with no audio and no model:

1. `/voice status` (and bare `/voice`) lands as one transcript note: voice off, the stt / tts picks, the budget;
2. the mic chip follows the loop's `voice` events (on, listening, speaking, idle, ptt, off);
3. a partial transcript shows in the status bar while the person speaks; `heard` echoes "you said: ..." in the transcript
   (a steer says it steers); "(interrupted while speaking)"; the latency card is the status bar's line after a turn;
4. Ctrl+Space is bound (push-to-talk); with voice off it says how to turn it on; /voice is in the slash catalog.
Run: python -m tests.test_voice_tui
"""
from __future__ import annotations

TIER = "full"  # a TUI pilot (Textual run_test): the full tier

import asyncio
import contextlib
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once  # noqa
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()
test, TESTS = new_registry()


@contextlib.contextmanager
def _scoped():
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
    tmp = Path(tempfile.mkdtemp(prefix="vl_tui-"))
    os.environ["BRIDGE_TEST_HOME"] = str(tmp)
    os.environ["BRIDGE_STATE_DIR"] = str(tmp / ".halo")
    try:
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _app():
    from halo_harness.testing.fake_controller import FakeController
    from halo_harness.tui.app import BridgeApp
    return BridgeApp(FakeController(), cwd="~/project")


async def _until(pilot, pred, n: int = 100) -> bool:
    for _ in range(n):
        if pred():
            return True
        await pilot.pause(0.05)
    return pred()


def _log(app) -> str:
    return "\n".join(str(x) for x in app.transcript.plain_log)


@test
def test_voice_status_is_one_note(ctx: Ctx):
    from halo_harness.tui.slash import handle_slash

    async def body():
        with _scoped():
            app = _app()
            async with app.run_test(size=(140, 30)) as pilot:
                await pilot.pause(0.1)
                await handle_slash(app, "voice", "status")
                ok = await _until(pilot, lambda: "voice is off" in _log(app))
                ctx.check(f"/voice status: off, the picks, the budget, got {_log(app)[-400:]!r}", ok
                          and "  stt: faster-whisper:small.en (not running: /voice on starts it" in _log(app)
                          and "  tts: kokoro-82m" in _log(app) and "budget 1,500 ms (target 750-900 ms)" in _log(app))
                await handle_slash(app, "voice", "")
                ok = await _until(pilot, lambda: _log(app).count("voice is off") == 2)
                ctx.check("bare /voice is the status too", ok)
                await handle_slash(app, "voice", "louder")
                ok = await _until(pilot, lambda: "Usage: /voice [on | off | ptt | status]" in _log(app))
                ctx.check("an unknown word: the usage line", ok)
    asyncio.run(body())


@test
def test_the_mic_chip_partial_echo_and_card(ctx: Ctx):
    from halo_harness.tui.dispatch import apply_event
    from halo_harness.voice.loop import event

    async def body():
        with _scoped():
            app = _app()
            async with app.run_test(size=(160, 30)) as pilot:
                await pilot.pause(0.1)
                bar = app.status_bar

                def shown() -> str:
                    return str(bar.render())
                ctx.check("no chip while voice is off", "mic" not in shown())
                await apply_event(app, event("on", mode="hands-free"))
                ctx.check(f"the chip: {shown()!r}", "mic" in shown() and "ptt" not in shown())
                await apply_event(app, event("listening"))
                ctx.check("listening", "mic: listening" in shown())
                await apply_event(app, event("partial", text="what is in the"))
                ctx.check(f"the partial transcript in the bar, got {bar.notice_shown()!r}",
                          bar.notice_shown() == "you: what is in the ...")
                await apply_event(app, event("heard", text="what is in the readme", steer=False))
                await apply_event(app, event("heard", text="no, the license", steer=True))
                ctx.check(f"the echo, got {_log(app)[-200:]!r}", "you said: what is in the readme" in _log(app)
                          and "you said: no, the license (steers the running turn)" in _log(app))
                await apply_event(app, event("speaking"))
                ctx.check("speaking", "mic: speaking" in shown())
                await apply_event(app, event("interrupted", text="(interrupted while speaking)"))
                ctx.check("the interruption in the transcript", "(interrupted while speaking)" in _log(app))
                line = "voice: 1.0 s of 1.5 s (heard 0.2 · text 0.3 · token 0.4 · audio 0.1)"
                await apply_event(app, event("card", text=line))
                ctx.check(f"the card is the bar's line after the turn, got {bar.notice_shown()!r}", bar.notice_shown() == line)
                await apply_event(app, event("idle"))
                await apply_event(app, event("on", mode="ptt"))
                ctx.check(f"push-to-talk chip, got {shown()!r}", "mic ptt" in shown())
                await apply_event(app, event("off"))
                ctx.check("the chip goes on off", "mic" not in shown())
    asyncio.run(body())


@test
def test_ctrl_space_is_push_to_talk(ctx: Ctx):
    from halo_harness.commands.builtins import _BUILTIN_SPECS
    from halo_harness.tui.app import BridgeApp
    from halo_harness.tui.keys import STATIC_APP_BINDINGS
    keys = {k for b in BridgeApp.BINDINGS for k in b.key.split(",") if b.action == "voice_ptt"}
    ctx.check(f"Ctrl+Space (and its NUL form) bound to voice_ptt, got {keys}", keys == {"ctrl+space", "ctrl+@"}
              and "ctrl+space" in STATIC_APP_BINDINGS)
    ctx.check("/voice is in the slash catalog", _BUILTIN_SPECS["voice"][2] == "[on|off|ptt|status]")

    async def body():
        with _scoped():
            app = _app()
            async with app.run_test(size=(140, 30)) as pilot:
                await pilot.pause(0.1)
                app.action_voice_ptt()
                ctx.check(f"voice off: how to turn it on, got {app.status_bar.notice_shown()!r}",
                          (app.status_bar.notice_shown() or "").startswith("voice is off: /voice ptt turns it on"))
    asyncio.run(body())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
