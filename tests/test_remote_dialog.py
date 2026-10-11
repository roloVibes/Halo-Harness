"""tests.test_remote_dialog -- Halo 2.0.9 round 4: the TUI `/remote` dialog
(tui/dialogs/remote_status.py) and the `/remote status|pair|off` text forms.

Driven with Textual pilots over a FakeController. State is real files under
a scratch home (pending.json, peers.json, the bridge pulse); the bridge is
NEVER started: a guard makes any SignalTransport.start() fail the test.
"""
from __future__ import annotations

import asyncio
import contextlib
import os
import sys
import tempfile
import threading
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
def test_dialog_shows_state_requests_and_phones(ctx: Ctx):
    async def body():
        with _scoped():
            _seed()
            app = _app()
            async with app.run_test(size=(120, 40)) as pilot:
                await _open(pilot, app)
                state = _text(app, "#remote-state")
                ctx.check("bridge state is off with the control socket line and the run hint",
                          "Bridge: off" in state and "control socket:" in state and "halo remote signal run" in state)
                pend, peers = _options(app, "#remote-pending"), _options(app, "#remote-peers")
                ctx.check("the contact request shows the prefix, number and safety number",
                          len(pend) == 1 and "00000000" in pend[0] and "+15555550101" in pend[0] and "11111 22222" in pend[0])
                ctx.check("the paired phone shows signed", len(peers) == 1 and "+15555550102" in peers[0] and "signed" in peers[0])
                await pilot.press("escape")
                await pilot.pause(0.1)
                ctx.check("Esc closes the dialog", type(app.screen).__name__ != "RemoteStatus")
    asyncio.run(body())
    ctx.check("the bridge was never started in this process", STARTED == [])


@test
def test_approve_shows_the_code_then_the_secret_once(ctx: Ctx):
    from halo_harness.remote import dialog_model as dm, signing
    from halo_harness.remote.pairing import Pairing
    codes: list = []

    class Spy(Pairing):
        def approve(self, aci):
            ap = super().approve(aci)
            codes.append(ap.code)
            return ap

    async def body():
        saved, dm.Pairing = dm.Pairing, Spy
        try:
            await run_body()
        finally:
            dm.Pairing = saved

    async def run_body():
        with _scoped():
            _seed()
            app = _app()
            async with app.run_test(size=(120, 44)) as pilot:
                await _open(pilot, app)
                await pilot.press("a")
                ok = await until(pilot, lambda: "█" in _text(app, "#remote-code"))
                ctx.check("a approves: the code is shown large", ok and "send exactly this code" in _text(app, "#remote-code"))
                ctx.check("without a bridge the dialog says to run it", "halo remote signal run" in _text(app, "#remote-code"))
                req = [r for r in Pairing().pending() if r["aci"] == ACI_A][0]
                ctx.check("the request is approved in pending.json", req["state"] == "approved")
                big = _text(app, "#remote-code").splitlines()[:5]
                ctx.check("the large code is five lines of block glyphs", len(big) == 5 and all(set(x) <= {"█", " "} for x in big))
                # the bridge side: it runs the queued trust step, then the phone sends the code the dialog issued
                tr = StubTransport()
                p = Pairing(transport=tr)
                p.service(tr)
                ctx.check("the trust step ran with the safety number", tr.trusts == [(ACI_A, "".join(SAFETY_A.split()))])
                res = p.redeem(ACI_A, codes[-1], "+15555550101")
                ctx.check("the phone redeems the code", res.status == "paired")
                ok = await until(pilot, lambda: signing.secret_to_phrase(res.secret) in _text(app, "#remote-secret"))
                ctx.check("the dialog shows the 32-word phrase and the link once paired", ok and "halo-remote://pair?" in _text(app, "#remote-secret"))
                await pilot.press("escape")
                await pilot.pause(0.1)
                ctx.check("the first Esc keeps the dialog (the phrase is shown once)", type(app.screen).__name__ == "RemoteStatus")
                await pilot.press("w")
                await pilot.pause(0.1)
                ctx.check("w ('I wrote it down') clears the secret", _text(app, "#remote-secret").strip() == "")
                await until(pilot, lambda: len(_options(app, "#remote-peers")) == 2)
                ctx.check("both phones are listed", len(_options(app, "#remote-peers")) == 2)
    asyncio.run(body())


@test
def test_signed_toggle_unpair_reverify_and_kill_switch(ctx: Ctx):
    from halo_harness.remote import bridge_state as BS
    from halo_harness.remote.pairing import Pairing
    from halo_harness.theme import get_config_value, set_config_value

    async def body():
        with _scoped():
            _seed()
            set_config_value("remote.signal.enabled", True)
            Pairing().block(ACI_B, SAFETY_A)
            app = _app()
            async with app.run_test(size=(120, 40)) as pilot:
                await _open(pilot, app)
                await pilot.press("tab")  # pending list -> phones list
                await pilot.press("tab")
                app.screen.query_one("#remote-peers").focus()
                await pilot.pause(0.1)
                ctx.check("a blocked phone says so", "BLOCKED" in _options(app, "#remote-peers")[0])
                await pilot.press("s")
                ok = await until(pilot, lambda: Pairing().peer(ACI_B)["signed"] is False)
                ctx.check("s turns signing off for the highlighted phone", ok)
                await until(pilot, lambda: "unsigned" in _options(app, "#remote-peers")[0])
                ctx.check("and the row shows unsigned", "unsigned" in _options(app, "#remote-peers")[0])
                await pilot.press("v")
                await pilot.pause(0.4)
                import json
                from halo_harness.remote.signal_config import remote_dir
                ops = json.loads((remote_dir() / "pending.json").read_text(encoding="utf-8")).get("ops", [])
                ctx.check("v queues the trust step for the bridge", any(o["kind"] == "reverify" for o in ops))
                stop_seen = threading.Event()
                BS.BridgeState().write("connected")

                def bridge():  # a stand-in bridge: ends when the stop file appears
                    while not BS.stop_requested():
                        time.sleep(0.05)
                    stop_seen.set()
                    BS.BridgeState(pid=2 ** 22 + 99).write("stopped")
                threading.Thread(target=bridge, daemon=True).start()
                await pilot.press("o")
                ok = await until(pilot, lambda: stop_seen.is_set())
                ctx.check("o writes the stop file the bridge polls", ok)
                await until(pilot, lambda: get_config_value("remote.signal.enabled", True) is False)
                ctx.check("and sets remote.signal.enabled to false", get_config_value("remote.signal.enabled", True) is False)
                await until(pilot, lambda: "Bridge: stopped" in _text(app, "#remote-state"))
                ctx.check("the dialog then reads stopped", "Bridge: stopped" in _text(app, "#remote-state"))
                await pilot.press("u")
                ok = await until(pilot, lambda: not Pairing().is_paired(ACI_B))
                ctx.check("u unpairs the highlighted phone", ok)
    asyncio.run(body())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
