"""tests.test_voice_studio_api -- Halo 3.3.9.0 R3: Local -> Voice's routes without Chrome (studio/voice_api.py,
studio/voice_act_api.py) on tests/helpers/hf_local_env.HfHome (the mock Hugging Face hub on 127.0.0.1 with the speech
repos, the fake speech server as `huggingface.voice_server_cmd`), a scripted session (tests/helpers/
fake_remote_session.FakeSession) behind a real control socket in the home's registry:

1. GET local/voice: both servers stopped with their cost lines, the catalog with the present one, the session, its
   loop off (read only with loop=1), a seeded card with its line, Talk's confirm naming what it starts and its seconds;
2. POST server start tts (the cost line first, then serving) and stop; POST loop on (the session's own line: the
   extra's install line here); POST download: the size line without `yes`, the 3.3.5.0 job with it (the mock hub), a
   present model says so;
3. POST talk: one turn through the in-process speech servers -- the job's frames' view ends done with the transcript,
   the reply and the bytes; refusals are one line: not base64, past 30 s, no session.
No model, no audio device, nothing leaves 127.0.0.1.
Run: python -m tests.test_voice_studio_api
"""
from __future__ import annotations

import base64
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.hf_local_env import HfHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.voice_files import put  # noqa: E402

test, TESTS = new_registry()


class _Session:
    def __enter__(self):
        from halo_harness.controller import Controller
        from halo_harness.remote.control_socket import ControlServer
        from halo_harness.remote.handle import ControllerHandle
        from halo_harness.remote.registry import make_entry, register
        from tests.helpers.fake_remote_session import FakeRegistry, FakeSession
        self.controller = Controller(session=FakeSession(), cwd=Path.cwd(), registry=FakeRegistry())
        self.controller.start()
        self.handle = ControllerHandle(self.controller)
        self.handle.attach()
        self.server = ControlServer(self.handle).start()
        register(make_entry(session_id=self.handle.session_id, cwd=Path.cwd(), endpoint=self.server.endpoint,
                            token=self.server.token))
        return self

    def __exit__(self, *exc):
        for fn in (self.server.close, self.handle.detach, self.controller.quit):
            try:
                fn()
            except Exception:
                pass


def _card(state: Path) -> None:
    (state / "voice").mkdir(parents=True, exist_ok=True)
    row = {"at": time.time(), "total_ms": 900, "stages": {"heard": 0, "text": 200, "token": 600, "audio": 100, "last": 900},
           "budget_ms": 1500, "interrupted": False, "steered": False, "chars": 20, "via": "host"}
    (state / "voice" / "turns.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")


@test
def test_the_view(ctx: Ctx):
    with HfHome() as h, _Session() as s:
        put(h.models, "faster-whisper:small.en")
        _card(h.state)
        _c, quiet = h.api("GET", "local/voice", query={"session": s.handle.session_id})
        ctx.check(f"the 15 s refresh asks the session nothing, got {quiet['loop']}", quiet["loop"]["lines"] == [])
        code, v = h.api("GET", "local/voice", query={"session": s.handle.session_id, "loop": "1"})
        srv = {r["kind"]: r for r in v.get("servers") or []}
        ctx.check(f"both stopped with their cost lines, got {code} {[(k, r['running'], r['cost'][:40]) for k, r in srv.items()]}",
                  code == 200 and not srv["stt"]["running"] and srv["tts"]["cost"].startswith("starting tts: kokoro-82m on the CPU"))
        cat = {r["name"]: r for r in v["catalog"]}
        ctx.check("the catalog: seven, small.en present, kokoro's size line", len(cat) == 7 and cat["faster-whisper:small.en"]["present"]
                  and cat["kokoro-82m"]["size_line"] == "kokoro-82m: 0.34 GB from fastrtc/kokoro-onnx (repo unverified)")
        ctx.check(f"the session and its loop, got {v['sessions']} {v['loop']}", [x["session_id"] for x in v["sessions"]] ==
                  [s.handle.session_id] and v["loop"]["on"] is False and v["loop"]["lines"][0] == "voice is off")
        ctx.check(f"the seeded card with its line, got {v['turns']}", len(v["turns"]) == 1
                  and v["turns"][0]["line"].startswith("voice: 0.9 s of 1.5 s") and v["stats"]["turns"] == 1)
        ctx.check(f"Talk's confirm names both starts and its seconds, got {v['talk']['confirm']!r}", "It starts stt: "
                  "faster-whisper:small.en on the CPU" in v["talk"]["confirm"] and "tts: kokoro-82m" in v["talk"]["confirm"]
                  and "costs time, not dollars" in v["talk"]["confirm"])


@test
def test_the_buttons(ctx: Ctx):
    from halo_harness.voice import INSTALL_LINE
    with HfHome() as h, _Session() as s:
        put(h.models, "kokoro-82m")
        code, got = h.api("POST", "local/voice/server", {"kind": "tts", "op": "start"})
        ctx.check(f"start: the cost line first, then serving, got {code} {got.get('lines')}", code == 200
                  and got["lines"][0].startswith("starting tts: kokoro-82m") and any("serving kokoro-82m" in x for x in got["lines"]))
        code, got = h.api("POST", "local/voice/server", {"kind": "tts", "op": "stop"})
        ctx.check(f"stop, got {code} {got.get('lines')}", code == 200 and got["lines"][0].startswith("stopped voice-tts tts"))
        code, got = h.api("POST", "local/voice/loop", {"session": s.handle.session_id, "op": "on"})
        ctx.check(f"loop on: the session's own line, got {code} {got}", code == 200 and INSTALL_LINE in " ".join(got["lines"]))
        code, got = h.api("POST", "local/voice/download", {"model": "faster-whisper:small.en"})
        ctx.check(f"download: the size line first, got {code} {got.get('confirm')!r}", code == 200 and got["confirm"].startswith(
            "faster-whisper:small.en: 0.5 GB from Systran/faster-whisper-small.en (repo unverified) into "))
        code, got = h.api("POST", "local/voice/download", {"model": "faster-whisper:small.en", "yes": True})
        done = h.wait_job(got.get("job") or "")
        ctx.check(f"with yes: the download job, done on the mock hub, got {code} {done.get('say')!r}", code == 200
                  and done.get("ok") is True and "faster-whisper:small.en is on disk" in str(done.get("say")))
        code, got = h.api("POST", "local/voice/download", {"model": "faster-whisper:small.en"})
        ctx.check(f"present now, got {code} {got}", code == 200 and got.get("present"))


@test
def test_talk(ctx: Ctx):
    from halo_harness import theme
    from tests.helpers.voice_rig import speech_servers
    with HfHome() as h:
        stt, tts, info = speech_servers(["read me the plan"])
        theme.set_config_value("huggingface.local_servers", [{"name": "stt", "url": stt, "voice": True},
                                                             {"name": "tts", "url": tts, "voice": True}])
        pcm = base64.b64encode(b"\x10\x00" * 24000).decode("ascii")
        code, got = h.api("POST", "local/voice/talk", {"pcm_b64": pcm, "rate": 48000})
        ctx.check(f"no session: one line, got {code} {got}", code == 409 and got["error"].startswith("no running halo session"))
        with _Session():
            code, got = h.api("POST", "local/voice/talk", {"pcm_b64": "not base64!", "rate": 16000})
            ctx.check(f"not base64, got {code} {got}", code == 400 and "not base64" in got["error"])
            long = base64.b64encode(b"\x00\x00" * 16000 * 31).decode("ascii")
            code, got = h.api("POST", "local/voice/talk", {"pcm_b64": long, "rate": 16000})
            ctx.check(f"past 30 s, got {code} {got}", code == 413 and "up to 30 s" in got["error"])
            code, got = h.api("POST", "local/voice/talk", {"pcm_b64": pcm, "rate": 48000})
            ctx.check(f"a 0.5 s utterance at 48 kHz: 202 with its job, got {code} {got}", code == 202 and got["seconds"] == 0.5)
            end, view = time.monotonic() + 15, {}
            while time.monotonic() < end and not view.get("done"):
                view = h.api("GET", "local/voice/talk", query={"job": got["job"]})[1]
                time.sleep(0.05)
            ctx.check(f"done: the transcript, the reply, the audio bytes, got {view}", view.get("ok") is True
                      and view.get("transcript") == "read me the plan" and view.get("reply") and view.get("bytes", 0) > 0)
        for s in info["servers"]:
            s.shutdown()
        rows = (h.state / "voice" / "turns.jsonl").read_text(encoding="utf-8").splitlines()
        ctx.check(f"the card in turns.jsonl via studio, got {rows[-1:]}", json.loads(rows[-1]).get("via") == "studio")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
