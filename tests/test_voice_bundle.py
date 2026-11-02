"""tests.test_voice_bundle -- Halo 3.3.9.0 R2: the voice-local bundle (templates/bundles/voice-local/pack.yaml) and the
speech servers the loop starts (halo_harness/voice/ensure.py), on the fixture 24 GB card (tests/helpers/bundle_rig):

1. voice-local validates and is the brief's: a small resident chat model (lfm3:1.7b, qwen3.8:4b, gemma4:4b) at 8 k,
   keep_alive -1, priority high; stt on cpu-or-gpu; tts on the CPU; latency_budget_ms 1500; meta-glasses names its
   reservation's window;
2. `halo pack verdict voice-local`: ready -- the chat model resident, stt on the GPU or the CPU, tts on the CPU;
3. `halo pack on voice-local` claims the reservation and says what it reserved; no process starts (a claim is a claim);
   the loop's picks are the bundle's, its budget the bundle's;
4. `/voice on` with no `stt` / `tts` entry says what it starts and the seconds first, starts R1's servers (the fake
   speech server through huggingface.voice_server_cmd) and `/voice off` stops what it started; a model not on disk is
   the download line, nothing left running.
Run: python -m tests.test_voice_bundle
"""
from __future__ import annotations

import queue
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.bundle_rig import LFM, BundleHome  # noqa: E402
from tests.helpers.hf_local_env import FAKE_VOICE  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


class _Ctl:
    """What voice/session.py reads of a Controller: events, state_dir, the taps, session.busy / model_ref."""

    def __init__(self, state) -> None:
        self.events, self.state_dir = queue.Queue(), state
        self.session = SimpleNamespace(busy=False, model_ref=SimpleNamespace(raw="ol:qwen3-coder:30b@pc"))
        self.taps: list = []

    def add_event_tap(self, fn) -> None:
        self.taps.append(fn)

    def remove_event_tap(self, fn) -> None:
        self.taps.remove(fn)

    def submit(self, text) -> None:
        pass


def _registry(state) -> list:
    from halo_harness.providers.local_runtime import load_registry
    return [r for r in load_registry(state) if r.get("id") in ("stt", "tts")]


@test
def test_voice_local_is_the_briefs(ctx: Ctx):
    from halo_harness.packs.bundles import shipped_dir
    from halo_harness.packs.discover import read_pack
    from halo_harness.packs.manifest_bundle import block
    pack = read_pack(shipped_dir() / "voice-local", "source", folder_is_id=True)
    ctx.check(f"validates clean, got {pack.problems}", pack.problems == [] and pack.id == "voice-local")
    b = block(pack)
    ctx.check(f"the chat need, got {b['needs']['chat']}", b["needs"]["chat"]["any_of"] == [LFM, "qwen3.8:4b", "gemma4:4b"]
              and b["needs"]["chat"]["window"] == 8192 and b["needs"]["chat"]["runtime"] == "ollama")
    ctx.check("stt on cpu-or-gpu, tts on the CPU", b["needs"]["stt"]["device"] == "cpu-or-gpu"
              and b["needs"]["tts"] == {"any_of": ["kokoro-82m"], "window": None, "device": "cpu", "vision": False,
                                        "tools": False, "runtime": "voice"})
    r = b["reservation"]
    ctx.check(f"the reservation holds the chat role resident, got {r}", r["model"] == "chat" and r["role"] == "chat"
              and r["keep_alive"] == -1 and r["priority"] == "high" and r["window"] == 8192)
    ctx.check("the budget and the routing", b["latency_budget_ms"] == 1500 and b["routing"]["task_work"] == "coder-or-cloud")
    g = block(read_pack(shipped_dir() / "meta-glasses", "source"))
    ctx.check("meta-glasses names its reservation's window", g["reservation"]["window"] == 8192
              and g["latency_budget_ms"] == 1500)


@test
def test_the_verdict_on_the_fixture_card(ctx: Ctx):
    from halo_harness.local_sched.bundle_fit import verdict
    from halo_harness.packs.bundles import find
    with BundleHome() as h:
        v = verdict(find("voice-local", cwd=h.repo)["block"], h.host, state_dir=h.state)
        ctx.check(f"ready, got {v['state']}: {v['says']}", v["state"] == "ready" and v["says"].startswith("fits today"))
        ctx.check(f"the chat model is the reservation, got {v['reserved']}", (v["reserved"] or {}).get("model") == LFM)
        stt = next(n for n in v["needs"] if n["role"] == "stt")
        tts = next(n for n in v["needs"] if n["role"] == "tts")
        ctx.check(f"stt on the GPU or the CPU, tts on the CPU, got {stt['placed']} / {tts['placed']}",
                  stt["placed"] in ("gpu", "cpu") and tts["placed"] == "cpu" and tts["gb"] == 0.0)
        code, out, _e = h.pack("verdict", "voice-local")
        ctx.check(f"halo pack verdict says it, got {code} {out!r}", code == 0 and "voice-local on pc: ready" in out)
        ctx.check("nothing pulled", h.mock.pulled == [])


@test
def test_pack_on_claims_and_starts_nothing(ctx: Ctx):
    from halo_harness.local_sched.claims_file import local_file, read
    from halo_harness.voice.ensure import picks
    with BundleHome() as h:
        code, out, err = h.pack("on", "voice-local")
        ctx.check(f"on: what it reserved, got {code} {out!r} {err!r}", code == 0 and f"reserved {LFM} on pc for "
                  "voice-local" in out)
        rows = read(local_file(h.state))
        ctx.check(f"the claim, got {rows}", any(r["bundle"] == "voice-local" and r["model"] == LFM for r in rows))
        ctx.check("no speech server started by the claim", _registry(h.state) == [])
        pk = picks(h.state)
        ctx.check(f"the loop's picks are the bundle's, got {pk}", pk["bundle"] == "voice-local" and pk["stt"] ==
                  ("faster-whisper:small.en", "auto") and pk["tts"] == ("kokoro-82m", "cpu") and pk["budget_ms"] == 1500
                  and pk["reserved"] == f"ol:{LFM}@pc")
        h.pack("off", "voice-local")
        ctx.check("off: the settings' picks again", picks(h.state)["bundle"] is None)


@test
def test_voice_on_starts_the_servers_with_the_cost_line_first(ctx: Ctx):
    import os
    from halo_harness.voice import session
    from halo_harness.voice.audio_fake import FakeAudio
    with BundleHome() as h:
        h.config(**{"huggingface.voice_server_cmd": [sys.executable, str(FAKE_VOICE)]})
        h.pack("on", "voice-local")
        said: list = []
        c = _Ctl(h.state)
        os.environ["HALO_VOICE_FAKE_DEVICES"] = "cpu"
        try:
            ok, lines = session.on(c, audio=FakeAudio(), say=said.append, mic=False)
            ctx.check(f"on, got {ok} {lines}", ok is True and lines[-1].startswith("voice on (hands-free"))
            ctx.check(f"the cost line came first, with the seconds, got {said}", len(said) == 2 and said[0].startswith(
                "starting stt: faster-whisper:small.en on the CPU: 0.9 GB RAM") and " -- ~5 s to load (halo local serve "
                "--stt faster-whisper:small.en --device cpu)" in said[0] and said[1].startswith("starting tts: kokoro-82m"))
            ctx.check(f"the reserved model is named, got {lines}", any(f"keeps ol:{LFM}@pc resident" in ln for ln in lines))
            ctx.check(f"both servers run, got {_registry(h.state)}", sorted(r["id"] for r in _registry(h.state)) ==
                      ["stt", "tts"])
            ctx.check("status says them", "  stt: faster-whisper:small.en on http://127.0.0.1:" in
                      session.slash(c, "status"))
            out = session.off(c)
            ctx.check(f"off stops what it started, got {out}", out[0] == "voice off" and len(out) == 3
                      and _registry(h.state) == [])
        finally:
            os.environ.pop("HALO_VOICE_FAKE_DEVICES", None)
            session.off(c)


@test
def test_a_model_not_on_disk_is_the_download_line(ctx: Ctx):
    from halo_harness.voice import session
    from halo_harness.voice.audio_fake import FakeAudio
    with BundleHome(voice=("kokoro-82m",)) as h:
        h.config(**{"huggingface.voice_server_cmd": [sys.executable, str(FAKE_VOICE)]})
        c = _Ctl(h.state)
        ok, lines = session.on(c, audio=FakeAudio(), say=lambda _l: None, mic=False)
        ctx.check(f"the download line, got {ok} {lines}", ok is False and lines[-1] ==
                  "faster-whisper:small.en is not present -- halo voice download faster-whisper:small.en (0.5 GB)")
        ctx.check("nothing left running", _registry(h.state) == [] and session.get(c) is None)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
