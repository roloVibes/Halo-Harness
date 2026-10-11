"""tests.test_remote_chip -- Halo 2.0.9 round 4: the `remote` status chip and
the one protocol addition behind it. The bridge sends `note remote.attached`
over the control socket on attach / detach; the session counts attached
phones (and forgets a connection's phones when it closes), queues a
`remote_attached` event for the TUI, and the status bar shows `⇄ remote N`
(ASCII `<> remote N`) in the default layout and as a ticker slot in all
three game skins."""
from __future__ import annotations

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
from tests.helpers.signal_rig import ACI_A, mk_bridge, wait_for

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


class _Recorder:
    def __init__(self, endpoint, token=None):
        self.calls = []

    def call(self, cmd, **kw):
        self.calls.append((cmd, kw))
        return {"ok": True, "result": {}}

    def next_event(self, timeout=0.4):
        import time
        time.sleep(min(timeout, 0.05))
        return None

    def close(self):
        pass


@test
def test_bridge_attach_and_detach_send_the_note(ctx: Ctx):
    from halo_harness.remote import bridge_session as sess
    with Rig(serve=False):
        b, tr, clock = mk_bridge()
        b.client_factory = _Recorder
        rt = b.rt(ACI_A)
        ctx.check("attach succeeds", sess.attach(b, rt, {"endpoint": "unix:/nowhere", "session_id": "s"}) is None)
        client = rt.client
        sess.detach(b, rt)
        notes = [kw for cmd, kw in client.calls if cmd == "note"]
        ctx.check("attach then detach send note remote.attached true / false",
                  [n["attached"] for n in notes] == [True, False] and all(n["name"] == "remote.attached" for n in notes))
        ctx.check("the peer is the ACI prefix, never the whole id", notes[0]["peer"] == ACI_A[:8])


@test
def test_bridge_to_session_end_to_end(ctx: Ctx):
    from halo_harness.remote import bridge_session as sess
    with Rig() as rig:
        b, tr, clock = mk_bridge()
        entry = {"endpoint": rig.server.endpoint, "token": rig.server.token, "session_id": rig.handle.session_id}
        rt = b.rt(ACI_A)
        ctx.check("attach to the live socket", sess.attach(b, rt, entry) is None)
        ctx.check("the session counts the phone", wait_for(lambda: rig.handle.status()["remote_attached"] == 1))
        sess.detach(b, rt)
        ctx.check("and forgets it on detach", wait_for(lambda: rig.handle.status()["remote_attached"] == 0))


@test
def test_chip_text_and_hud_slot_declarations(ctx: Ctx):
    from halo_harness.tui.hud import SLOTS, skin_for
    from halo_harness.tui.hud_fields import remote_chip
    ctx.check("unicode chip", remote_chip(2) == f"{ARROWS} remote 2")
    ctx.check("ascii chip", remote_chip(1, True) == "<> remote 1")
    ctx.check("remote is in the slot vocabulary", "remote" in SLOTS)
    for name in ("doom", "metroid", "mario"):
        skin = skin_for(name)
        ctx.check(f"{name} ticker carries the remote slot", "remote" in [s.slot for s in skin.strip])
        ctx.check(f"{name} may drop it last-ish, never first", "remote" in skin.drop_order
                  and skin.drop_order.index("remote") > skin.drop_order.index("effort"))


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


@test
def test_game_skins_show_the_chip_in_the_ticker(ctx: Ctx):
    async def body():
        for theme in ("doom", "metroid", "mario"):
            with _scoped():
                app = _app(theme)
                async with app.run_test(size=(180, 30)) as pilot:
                    await pilot.pause(0.1)
                    bar = app.status_bar
                    bar.hud_ascii = False
                    bar.set_remote_attached(2)
                    await pilot.pause(0.05)
                    ctx.check(f"{theme}: ticker shows the chip", f"{ARROWS} remote 2" in str(bar.render()))
                    bar.hud_ascii = True
                    bar._refresh_display()
                    ctx.check(f"{theme}: ASCII ticker", "<> remote 2" in str(bar.render()))
                    bar.set_remote_attached(0)
                    ctx.check(f"{theme}: gone at zero", "remote" not in str(bar.render()))
    asyncio.run(body())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
