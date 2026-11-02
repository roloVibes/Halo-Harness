"""tests.test_bundle_fit_voice -- Halo 3.3.9.0 R1: a bundle's speech needs resolve through the speech catalog and what
is on disk (local_sched/bundle_voice.py; the verdict in local_sched/bundle_fit.py), on the bundle rig's fixture 24 GB
card (tests/helpers/bundle_rig.BundleHome; the speech files are tests/helpers/voice_files.put's few bytes):

1. present: the glasses verdict is ready and names each speech model with its footprint;
2. absent: "needs 2 downloads", each `halo voice download <model> (N GB)`, no Ollama button (a speech model is not a
   pull), and `halo pack verdict` prints the two commands;
3. a missing chat model and a missing speech model: the button names the Ollama tag only;
4. `cpu-or-gpu` goes on the GPU when it fits beside everything (no coder), its GPU figure;
5. `device: gpu` takes the first of any_of at its GPU figure (the brief's "1.5 GB on the GPU, 3.1 GB on the CPU");
6. a present model of the any_of is taken before an absent smaller one;
7. a name the catalog does not hold is said so, never sized; 8. "arrive with Voice" is gone from the tree.
Run: python -m tests.test_bundle_fit_voice
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.bundle_rig import LFM, BundleHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
SMALL_EN = "faster-whisper:small.en"


def _glasses(h):
    from halo_harness.local_sched.bundle_fit import verdict
    from halo_harness.packs.bundles import find
    return verdict(find("meta-glasses", cwd=h.repo)["block"], h.host, state_dir=h.state)


def _bundle(stt: list, device: str, task_work: str = "cloud") -> dict:
    return {"id": "talk", "name": "Talk", "needs": {"stt": {"any_of": stt, "window": None, "device": device,
                                                            "vision": False, "tools": False, "runtime": "voice"}},
            "reservation": None, "routing": {"task_work": task_work, "never_evict": "reserved", "escalation": "on"},
            "latency_budget_ms": None}


def _need(v: dict, role: str) -> dict:
    return next(n for n in v["needs"] if n["role"] == role)


@test
def test_present_speech_models_are_ready_with_their_footprint(ctx: Ctx):
    with BundleHome() as h:
        v = _glasses(h)
        ctx.check(f"ready, got {v['state']}: {v['says']}", v["state"] == "ready")
        ctx.check("stt present with both figures", "stt: faster-whisper:small.en present (0.5 GB on the GPU, 0.9 GB on the "
                  "CPU)" in v["says"])
        ctx.check("tts present", "tts: kokoro-82m present (0.3 GB on the GPU, 0.5 GB on the CPU)" in v["says"])
        stt = _need(v, "stt")
        ctx.check(f"on the CPU, no VRAM, installed, got {stt}", stt["placed"] == "cpu" and stt["gb"] == 0.0
                  and stt["installed"] is True and stt["command"] is None)


@test
def test_absent_speech_models_are_downloads_with_the_command(ctx: Ctx):
    with BundleHome(voice=False) as h:
        v = _glasses(h)
        ctx.check(f"needs 2 downloads, got {v['state']}: {v['says']}", v["state"] == "downloads"
                  and v["says"].startswith("needs 2 downloads (0.8 GB, ~"))
        ctx.check("each said with its command and GB", "stt: not present -- halo voice download faster-whisper:small.en "
                  "(0.5 GB)" in v["says"] and "tts: not present -- halo voice download kokoro-82m (0.34 GB)" in v["says"])
        ctx.check(f"no Ollama button for a speech model, got {v['button']}", v["button"] is None)
        ctx.check(f"the commands, got {v.get('voice_downloads')}", v.get("voice_downloads") == [
            "halo voice download faster-whisper:small.en", "halo voice download kokoro-82m"])
        code, out, _e = h.pack("verdict", "meta-glasses")
        ctx.check(f"halo pack verdict prints them, got {out!r}", code == 0 and "speech model: halo voice download "
                  "faster-whisper:small.en" in out and "meta-glasses on pc: downloads" in out)
        ctx.check("nothing downloaded or pulled", h.mock.pulled == [] and not list(h.models.iterdir()))


@test
def test_a_missing_chat_model_keeps_the_button_to_its_tag(ctx: Ctx):
    with BundleHome(lfm=False, voice=("kokoro-82m",)) as h:
        v = _glasses(h)
        ctx.check(f"two downloads, got {v['says']}", v["state"] == "downloads" and v["says"].startswith("needs 2 downloads"))
        ctx.check(f"the button pulls the chat model only, got {v['button']}", v["button"]["tags"] == [LFM])
        ctx.check("the speech command beside it", v["voice_downloads"] == ["halo voice download faster-whisper:small.en"])


@test
def test_cpu_or_gpu_goes_on_the_gpu_when_it_fits(ctx: Ctx):
    from halo_harness.local_sched.bundle_fit import verdict
    with BundleHome() as h:
        v = verdict(_bundle(["faster-whisper:small.en"], "cpu-or-gpu"), h.host, state_dir=h.state)
        stt = _need(v, "stt")
        ctx.check(f"on the GPU at its GPU figure, got {stt} / {v['says']}", stt["placed"] == "gpu" and stt["gb"] == 0.5
                  and v["state"] == "ready")
        ctx.check("no 'on the CPU' line", "on the CPU: no VRAM" not in v["says"])
        v = verdict(_bundle(["faster-whisper:large-v3-turbo", SMALL_EN], "cpu-or-gpu"), h.host, state_dir=h.state)
        stt = _need(v, "stt")
        ctx.check(f"the first is absent: the present one goes on the GPU, no download, got {stt}",
                  stt["placed"] == "gpu" and stt["tag"] == SMALL_EN and stt["gb"] == 0.5 and v["state"] == "ready")


@test
def test_a_gpu_need_takes_the_first_at_its_gpu_figure(ctx: Ctx):
    from halo_harness.local_sched.bundle_fit import verdict
    with BundleHome(voice=("faster-whisper:large-v3-turbo",)) as h:
        v = verdict(_bundle(["faster-whisper:large-v3-turbo", "faster-whisper:small.en"], "gpu"), h.host, state_dir=h.state)
        stt = _need(v, "stt")
        ctx.check(f"large-v3-turbo on the GPU, 1.5 GB, got {stt}", stt["tag"] == "faster-whisper:large-v3-turbo"
                  and stt["placed"] == "gpu" and stt["gb"] == 1.5)
        ctx.check(f"the brief's line, got {v['says']!r}", "stt: faster-whisper:large-v3-turbo present (1.5 GB on the GPU, "
                  "3.1 GB on the CPU)" in v["says"])


@test
def test_a_present_model_comes_before_an_absent_smaller_one(ctx: Ctx):
    with BundleHome(voice=("faster-whisper:large-v3-turbo", "kokoro-82m")) as h:
        v = _glasses(h)
        stt = _need(v, "stt")
        ctx.check(f"the present large-v3-turbo on the CPU, got {stt}", stt["tag"] == "faster-whisper:large-v3-turbo"
                  and stt["placed"] == "cpu" and stt["installed"] is True)
        ctx.check(f"ready: nothing to download, got {v['state']}", v["state"] == "ready")


@test
def test_a_name_outside_the_catalog_is_said_so(ctx: Ctx):
    from halo_harness.local_sched.bundle_fit import verdict
    with BundleHome() as h:
        v = verdict(_bundle(["whisper:tiny-made-up"], "cpu"), h.host, state_dir=h.state)
        stt = _need(v, "stt")
        ctx.check(f"not in the catalog, no size, no download, got {stt}", "not in the speech catalog" in stt["why"]
                  and stt["installed"] is None and not v["downloads"])


@test
def test_the_old_line_is_gone(ctx: Ctx):
    hits = []
    for root in ("halo_harness", "docs", "tests"):
        for p in (REPO / root).rglob("*"):
            if p.is_file() and p.suffix in (".py", ".md", ".yaml", ".tsx", ".ts") and p.name != Path(__file__).name:
                if "arrive with Voice" in p.read_text(encoding="utf-8", errors="replace"):
                    hits.append(str(p.relative_to(REPO)))
    ctx.check(f"'arrive with Voice' is nowhere in halo_harness/, docs/ or tests/, found {hits}", not hits)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
