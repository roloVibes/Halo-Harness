"""tests.test_remote_dialog_text -- Halo 2.0.9 round 4: the `/remote` notices-to-notifications poll,
the `/remote status|pair|off` text forms, bare `/remote` opening the dialog, and the large-code font.
Same scratch-home pilot setup as tests/test_remote_dialog.py."""
from __future__ import annotations

TIER = "full"  # a TUI pilot (Textual run_test): the full tier

import asyncio
import contextlib
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials
from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.signal_rig import ACI_A, ACI_B, SAFETY_A, SAFETY_B, StubTransport, pair_peer

ensure_default_provider_credentials()
test, TESTS = new_registry()
STARTED: list = []


@contextlib.contextmanager
def _scoped():
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
    os.environ["BRIDGE_TEST_HOME"] = tempfile.mkdtemp(prefix="halo-remote-dlg-")
    os.environ.pop("BRIDGE_STATE_DIR", None)
    from halo_harness.remote import signal_transport
    orig = signal_transport.SignalTransport.start
    signal_transport.SignalTransport.start = lambda self: STARTED.append(1)
    try:
        yield
    finally:
        signal_transport.SignalTransport.start = orig
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


async def until(pilot, cond, timeout: float = 6.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        await pilot.pause(0.05)
    return bool(cond())


def _text(app, selector: str) -> str:
    return str(app.screen.query_one(selector).render())


def _options(app, selector: str) -> list:
    ol = app.screen.query_one(selector)
    return [str(ol.get_option_at_index(i).prompt) for i in range(ol.option_count)]


def _seed():
    from halo_harness.remote.pairing import Pairing
    p = Pairing(transport=StubTransport())
    pair_peer(p, ACI_B, "+15555550102", SAFETY_B)
    Pairing().note_contact(ACI_A, "+15555550101", SAFETY_A)


async def _open(pilot, app, poll: float = 0.3):
    from halo_harness.remote import dialog_model
    from halo_harness.tui.dialogs.remote_status import RemoteStatus
    app.push_screen(RemoteStatus(dialog_model.snapshot(), poll=poll))
    await pilot.pause(0.2)
    return app.screen


def _app():
    from halo_harness.testing.fake_controller import FakeController
    from halo_harness.tui.app import BridgeApp
    return BridgeApp(FakeController(), cwd="~/project")


@test
def test_notices_become_notifications_and_are_cleared(ctx: Ctx):
    from halo_harness.remote.pairing import Pairing
    from halo_harness.tui.slash_remote import poll_notices_once

    async def body():
        with _scoped():
            app = _app()
            async with app.run_test(size=(120, 40)) as pilot:
                seen: list = []
                app.notify = lambda msg, **kw: seen.append(str(msg))
                Pairing().add_notice("identity_changed", ACI_A, "the safety number changed; commands are refused until reverify")
                Pairing().add_notice("rate_limited", "", "Signal rate limit: sending paused for 60 s. Captcha token: tok")
                n = await asyncio.to_thread(poll_notices_once, app)
                await pilot.pause(0.1)
                ctx.check("both notices were shown as notifications", n == 2 and len(seen) == 2 and "safety number changed" in seen[0])
                ctx.check("and cleared", Pairing().notices() == [])
                await _open(pilot, app)
                Pairing().add_notice("code_expired", ACI_B, "pairing code expired; the contact request was dropped")
                await until(pilot, lambda: any("expired" in s for s in seen))
                ctx.check("the open dialog surfaces them too", any("expired" in s for s in seen) and Pairing().notices() == [])
    asyncio.run(body())


@test
def test_slash_forms_and_bare_remote_opens_the_dialog(ctx: Ctx):
    from halo_harness.commands.builtins import _cmd_remote
    from halo_harness.remote.pairing import Pairing
    from halo_harness.theme import get_config_value, set_config_value
    from halo_harness.tui.slash import handle_slash

    with _scoped():
        _seed()
        out = _cmd_remote("status", None)
        ctx.check("/remote status: bridge line, control socket line, the phone, the hint",
                  "bridge: off" in out and "control socket:" in out and "+15555550102" in out and "halo remote signal run" in out)
        ctx.check("bare /remote in print mode is the same text", "bridge:" in _cmd_remote("", None))
        out = _cmd_remote("pair", None)
        ctx.check("/remote pair lists the request with its safety number", "1  00000000" in out and "11111 22222" in out)
        out = _cmd_remote("pair 7", None)
        ctx.check("an unknown number is said plainly", "No contact request" in out)
        out = _cmd_remote("pair 1", None)
        code = [w for w in out.split() if w.isdigit() and len(w) == 6]
        ctx.check("/remote pair 1 approves and prints the one-time code", len(code) == 1
                  and [r["state"] for r in Pairing().pending() if r["aci"] == ACI_A] == ["approved"])
        set_config_value("remote.signal.enabled", True)
        out = _cmd_remote("off", None)
        ctx.check("/remote off is the kill switch", "remote.signal.enabled is false" in out
                  and get_config_value("remote.signal.enabled", True) is False)
        ctx.check("an unknown argument prints usage", "usage: /remote" in _cmd_remote("frob", None))

    async def body():
        with _scoped():
            app = _app()
            async with app.run_test(size=(120, 40)) as pilot:
                await handle_slash(app, "remote", "")
                ok = await until(pilot, lambda: type(app.screen).__name__ == "RemoteStatus")
                ctx.check("bare /remote opens the dialog", ok)
    asyncio.run(body())


@test
def test_big_digits_font_is_five_rows_and_distinct(ctx: Ctx):
    from halo_harness.tui.dialogs.remote_status import _FONT, big_digits
    rows = big_digits("0123456789").split("\n")
    ctx.check("five rows", len(rows) == 5)
    ctx.check("every digit has a different glyph", len({v for v in _FONT.values()}) == 10)
    ctx.check("a six-digit code is 6*3 + 5*2 = 28 cells wide", all(len(r) == 28 for r in big_digits("123456").split("\n")))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
