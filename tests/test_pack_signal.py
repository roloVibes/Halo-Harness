"""tests.test_pack_signal -- the shipped signal pack, installed and enabled in a scratch home, driving a whole
conversation over real control sockets (Halo 3.3.13.0 R3; tests/helpers/remote_rig.Rig: a real Controller over the
scripted FakeSession, its ControlServer) through the stub transport (tests/helpers/signal_rig.py):

1. it installs from the shipped templates, enables with every grant it asks for (services) and its manifest, its
   requirement and its service read clean;
2. pair in one message; a text with no session starts one (the start seam answers with a Rig) and the answer comes
   back paragraph by paragraph; a permission card answered with `1`; a question with `b`; a voice note with a stub
   transcriber; `/notify` and a supervisor note through the core's seam (remote/notify.py);
3. the service under the supervisor (supervise/services.py) against the fake signal-cli: its health file says
   connected, the supervisor's way out stops it.
No signal-cli, no Java, no Signal message. Run: python -m tests.test_pack_signal"""
from __future__ import annotations


import os
import shutil
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import SHIPPED, PacksHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.signal_rig import ACI_A, SAFETY_A, StubTransport, envelope, now_ms, untrusted, wait_for  # noqa: E402

test, TESTS = new_registry()


class RigSessions:
    """session.Sessions' surface over real control sockets: each started session is a Rig."""

    def __init__(self, home: str) -> None:
        self.home, self.rigs, self.started = home, [], []

    def _row(self, rig) -> dict:
        return {"session_id": rig.session.log.session_id, "title": "Phone session", "cwd": str(rig.cwd),
                "started": 1000.0 + len(self.rigs), "kind": "headless", "model": "mock/fake", "pid": os.getpid()}

    def live(self) -> list:
        return [self._row(r) for r in self.rigs]

    def connect(self, sid: str):
        from halo_harness.remote.client import ControlClient
        rig = next((r for r in self.rigs if r.session.log.session_id == sid), None)
        return ControlClient(rig.server.endpoint, rig.server.token, timeout=10.0) if rig else None

    def start(self, cwd: str, model: str, by: str):
        from tests.helpers.remote_rig import Rig
        rig = Rig(session_id=f"phonesession{len(self.rigs) + 1:021d}")
        os.environ["BRIDGE_TEST_HOME"] = self.home  # the Rig took the variable for its own home: give it back
        self.rigs.append(rig)
        self.started.append({"cwd": cwd, "model": model, "by": by})
        return self._row(rig), ""

    def close(self) -> None:
        for r in self.rigs:
            r.server.close()
            r.controller.quit()


def _install(h) -> Path:
    src = h.sources / "signal"
    shutil.copytree(SHIPPED / "signal", src, ignore=shutil.ignore_patterns("__pycache__"))
    h.install(src, enable=True, grants=["services"])
    root = h.home / ".halo" / "packs" / "signal"
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root


@test
def test_the_pack_installs_and_reads_clean(ctx: Ctx):
    with PacksHome() as h:
        root = _install(h)
        from halo_harness.packs.discover import find
        from halo_harness.packs.manifest import validate_manifest
        pack = find("signal", cwd=h.repo)
        ctx.check("installed and enabled with the services grant", pack is not None and root.is_dir())
        ctx.check("its manifest reads clean", validate_manifest(pack.manifest, root=root) == [])
        from halo_harness.packs.manifest_requires import tools_of
        ctx.check("signal-cli is its requirement, never installed by Halo", [t["name"] for t in tools_of(pack.manifest)] == ["signal-cli"])
        from halo_harness.supervise.services_rows import declared
        ctx.check("its bridge is a service the supervisor runs", [(p.id, e["name"], g) for p, e, g in declared(h.home / ".halo", h.repo)]
                  == [("signal", "bridge", True)])


@test
def test_a_whole_conversation(ctx: Ctx):
    with PacksHome() as h:
        _install(h)
        from halo_signal.bridge import Bridge
        tr, sessions = StubTransport(), RigSessions(os.environ["BRIDGE_TEST_HOME"])
        heard = []
        b = Bridge({"rate_per_minute": 100}, tr, sessions=sessions,
                   transcribe=lambda path: (heard.append(path) or "make it blue", ""))
        stop = threading.Event()
        th = threading.Thread(target=b.run, args=(stop, 0.02), daemon=True)
        th.start()
        joined = lambda: "\n".join(tr.texts(ACI_A))  # noqa: E731
        try:
            phrase = b.pairing.invite()["phrase"]
            tr.identities[ACI_A] = SAFETY_A
            tr.deliver(untrusted(ACI_A, "+15550100", now_ms()))
            wait_for(lambda: tr.trusts, 3.0)
            tr.deliver(envelope(ACI_A, phrase, now_ms(), "+15550100"))
            ctx.check("paired in one message", wait_for(lambda: "Paired." in joined(), 5.0))
            tr.deliver(envelope(ACI_A, "paragraphs please", now_ms(), "+15550100"))
            ctx.check("a text with no session starts one", wait_for(lambda: sessions.started, 5.0)
                      and "Starting a session in " in joined())
            ctx.check("the answer arrives paragraph by paragraph", wait_for(lambda: "The end." in joined(), 10.0))
            texts = tr.texts(ACI_A)
            i = texts.index("First paragraph here.")
            ctx.check(f"in order, a code block whole, got {texts[i:i + 4]}", texts[i + 1] == "Second one."
                      and texts[i + 2] == "x = 1" and texts[i + 3] == "The end.")
            rig = sessions.rigs[0]
            ctx.check("the session logged the text the phone sent", any(
                n.get("type") == "user" and n["content"][0]["text"] == "paragraphs please" for n in rig.session.log.nodes()))
            tr.deliver(envelope(ACI_A, "please ask first", now_ms(), "+15550100"))
            ctx.check("the permission card arrives", wait_for(lambda: "echo hi" in joined(), 8.0))
            tr.deliver(envelope(ACI_A, "1", now_ms(), "+15550100"))
            ctx.check("1 allows once", wait_for(lambda: rig.session.permission_decisions.get("perm_1") is not None, 8.0))
            tr.deliver(envelope(ACI_A, "ask-question now", now_ms(), "+15550100"))
            ctx.check("the question card arrives", wait_for(lambda: "which?" in joined(), 8.0))
            tr.deliver(envelope(ACI_A, "b", now_ms(), "+15550100"))
            ctx.check("b answers it", wait_for(lambda: (rig.session.answers.get("q_1") or {}).get("answer") == "blue", 8.0))
            tr.files["v1"] = (b"\x00\x01", "audio/aac")
            tr.deliver(envelope(ACI_A, None, now_ms(), "+15550100",
                                attachments=[{"id": "v1", "contentType": "audio/aac", "filename": "n.m4a"}]))
            ctx.check("a voice note goes in as the prompt", wait_for(lambda: any(
                n.get("type") == "user" and n["content"][0]["text"] == "(voice note) make it blue"
                for n in rig.session.log.nodes()), 8.0) and heard)
            tr.deliver(envelope(ACI_A, "/notify on steward", now_ms(), "+15550100"))
            ctx.check("/notify answers", wait_for(lambda: "steward on" in joined(), 5.0))
            from halo_harness.remote.notify import listening, notify
            ctx.check("the bridge listens on the core's seam", wait_for(lambda: listening() == ["signal"], 5.0))
            notify("supervisor", "Goal g-7 done: the docs, $0.05")
            ctx.check("a supervisor note reaches the phone", wait_for(lambda: "Goal g-7 done" in joined(), 8.0))
        finally:
            stop.set()
            th.join(10)
            sessions.close()


@test
def test_the_service_under_the_supervisor(ctx: Ctx):
    with PacksHome() as h:
        root = _install(h)
        from halo_signal import settings
        from tests.helpers.signal_rig import wait_for as wf
        fake = root / "tests" / "fake_signal_cli.py"
        work = h.home / "fake-signal"
        work.mkdir()
        (work / "ctl.jsonl").write_text("", encoding="utf-8")
        settings.save_signal(binary=[sys.executable, str(fake)], account="+15550199",
                             extra_args=["--fake-ctl", str(work / "ctl.jsonl"), "--fake-log", str(work / "log.jsonl")])
        from halo_harness.supervise import pulse
        from halo_harness.supervise.services import Services
        state = h.home / ".halo"
        pulse.Pulse(state).write("running")
        svc = Services(state, cwd=h.repo)
        health = state / "packs" / ".data" / "signal" / "health.json"
        try:
            svc.tick()
            ctx.check("the supervisor started the bridge", svc.rec.get("signal/bridge", {}).get("state") == "running")
            ok = wf(lambda: health.exists() and '"connected"' in health.read_text(encoding="utf-8"), 30.0)
            log = state / "packs" / ".data" / "signal" / "service.log"
            ctx.check(f"its health file says connected (log: {log.read_text(encoding='utf-8', errors='replace')[-300:] if log.exists() else ''})", ok)
            svc.tick()
            ctx.check(f"the row carries the health, got {svc.rec['signal/bridge']}",
                      svc.rec["signal/bridge"].get("health") == "ok" and "connected" in str(svc.rec["signal/bridge"].get("line")))
        finally:
            svc.stop_all()
        ctx.check("the supervisor's way out stops it, and it says so", svc.rec["signal/bridge"]["state"] == "stopped"
                  and wf(lambda: '"stopped"' in health.read_text(encoding="utf-8"), 10.0))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
