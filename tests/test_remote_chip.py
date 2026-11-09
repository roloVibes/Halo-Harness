"""tests.test_remote_chip -- Halo 2.0.9 round 4: the `remote` status chip and
the one protocol addition behind it. A transport's bridge (the signal pack's since 3.3.13.0 R3, halo_signal/
session.py) sends `note remote.attached` over the control socket on attach / detach; the session counts attached
phones (and forgets a connection's phones when it closes), queues a `remote_attached` event for the TUI, and the
status bar shows `⇄ remote N` (ASCII `<> remote N`); 3.3.13.0 R3: with no phone attached, the chip names the
transport that listens or the pack service that should run and does not (remote/status.chip)."""
from __future__ import annotations

TIER = "full"  # a TUI pilot (Textual run_test): the full tier

import asyncio
import contextlib
import os
import queue
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once
from tests.helpers.remote_rig import Rig
from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.signal_rig import wait_for

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

test, TESTS = new_registry()
ARROWS = "⇄"


def _events(q) -> list:
    out = []
    while True:
        try:
            item = q.get_nowait()
        except queue.Empty:
            return out
        if item is not None and item.kind == "remote_attached":
            out.append(item.data)


@test
def test_note_counts_phones_and_queues_the_event(ctx: Ctx):
    with Rig() as rig:
        c = rig.client()
        r = c.call("note", name="remote.attached", peer="00000000", attached=True)
        ctx.check("note attached answers with the count", r["ok"] and r["result"] == {"attached": 1})
        ctx.check("status carries remote_attached", c.call("status")["result"]["remote_attached"] == 1)
        c.call("note", name="remote.attached", peer="00000000", attached=True)
        ctx.check("the same phone twice is still one", c.call("status")["result"]["remote_attached"] == 1)
        c.call("note", name="remote.attached", peer="11111111", attached=True)
        r = c.call("note", name="remote.attached", peer="00000000", attached=False)
        ctx.check("detach counts down", r["result"] == {"attached": 1})
        evs = _events(rig.controller.events)
        ctx.check("one remote_attached event per change (1, 2, 1)", [e["count"] for e in evs] == [1, 2, 1])
        ctx.check("the event names the phone and direction",
                  evs[0]["peer"] == "00000000" and evs[0]["attached"] is True and evs[2]["attached"] is False)
        bad = c.call("note", name="something.else", peer="x", attached=True)
        ctx.check("an unknown note name is an error", bad["ok"] is False and "unknown note" in bad["error"])
        ctx.check("a note without a peer is an error", c.call("note", name="remote.attached", attached=True)["ok"] is False)


@test
def test_a_closed_connection_takes_its_phones_with_it(ctx: Ctx):
    with Rig() as rig:
        a, b = rig.client(), rig.client()
        a.call("note", name="remote.attached", peer="aaaaaaaa", attached=True)
        ctx.check("one phone attached", b.call("status")["result"]["remote_attached"] == 1)
        a.close()  # the bridge crashed
        ok = wait_for(lambda: b.call("status")["result"]["remote_attached"] == 0, 5.0)
        ctx.check("the count falls back to zero when the bridge's connection closes", ok)
        ctx.check("and the TUI was told", [e["count"] for e in _events(rig.controller.events)] == [1, 0])


# The bridge's side (the note on attach and detach, a bridge to a session end to end) is the signal pack's
# (3.3.13.0 R3): tests/test_pack_signal.py drives it over a real control socket.


@test
def test_chip_text(ctx: Ctx):
    from halo_harness.tui.widgets.statusbar import remote_chip
    ctx.check("unicode chip", remote_chip(2) == f"{ARROWS} remote 2")
    ctx.check("ascii chip", remote_chip(1, True) == "<> remote 1")
    from halo_harness.tui.widgets.statusbar import StatusBar
    bar = StatusBar.__new__(StatusBar)
    bar.remote_attached, bar.hud_ascii, bar.transport_chip = 0, True, None
    bar._refresh_display = lambda: None
    bar.set_transport("signal")
    ctx.check("3.3.13.0 R3: with no phone attached the chip names the transport", bar._remote_str() == "<> signal")
    bar.set_transport("")
    ctx.check("and goes with it", bar._remote_str() == "")


@contextlib.contextmanager
def _scoped():
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
    tmp = Path(tempfile.mkdtemp(prefix="halo-chip-"))
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


def _app(theme=None):
    from halo_harness.testing.fake_controller import FakeController
    from halo_harness.tui.app import BridgeApp
    kw = {"theme_name": theme} if theme else {}
    return BridgeApp(FakeController(), cwd="~/project", **kw)


@test
def test_status_bar_shows_the_chip_in_the_default_layout(ctx: Ctx):
    from halo_harness import events
    from halo_harness.tui.dispatch import apply_event

    async def body():
        with _scoped():
            app = _app()
            async with app.run_test(size=(140, 30)) as pilot:
                await pilot.pause(0.1)
                bar = app.status_bar
                bar.hud_ascii = False
                bar._refresh_display()
                ctx.check("no chip before a phone attaches", "remote" not in str(bar.render()))
                await apply_event(app, events.remote_attached(1, ["aaaaaaaa"], peer="aaaaaaaa"))
                await pilot.pause(0.05)
                ctx.check(f"the chip appears: {str(bar.render())!r}", f"{ARROWS} remote 1" in str(bar.render()))
                bar.hud_ascii = True
                bar._refresh_display()
                ctx.check("ASCII form on a terminal without truecolor", "<> remote 1" in str(bar.render()))
                await apply_event(app, events.remote_attached(0, [], peer="aaaaaaaa", attached=False))
                await pilot.pause(0.05)
                ctx.check("the chip goes when the phone detaches", "remote" not in str(bar.render()))
    asyncio.run(body())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
