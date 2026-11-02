"""tests.test_local_serve_voice -- Halo 3.3.9.0 R1: `halo local serve --stt | --tts <model>` (halo_harness/voice/
launch.py through local_hf_serve_cli.py) with the fake speech server (`huggingface.voice_server_cmd` =
tests/helpers/fake_voice_server.py, tests/helpers/hf_local_env.HfHome) on a free loopback port:

1. not on disk: "not present -- halo voice download <model> (N GB)", nothing starts;
2. served: the device line, the URL and the route; the registry row `stt` (voice-stt, its device and log) and the
   `huggingface.local_servers` entry `stt` (url, log, runtime, model, device, pid); a transcription answers;
3. `halo local servers` shows it with its runtime and device; `halo local log stt` reads its log;
4. a second `serve --stt` says the running one (another model: stop it first; the same: already serving);
5. `halo local stop stt` stops it and takes the entry out; `--tts kokoro-82m` speaks;
6. a declared model and a model of the other kind say so; without the seam a missing extra is the install line, exit 2;
7. --device: cpu said with the GPU kept for the chat model; auto -> cuda when the engines see it and it fits, else
   the CPU with why. No real engine, no model, nothing downloads.
Run: python -m tests.test_local_serve_voice
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.hf_local_env import HfHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.voice_files import put  # noqa: E402

test, TESTS = new_registry()
SMALL = "faster-whisper:small.en"


def _local(*argv) -> "tuple[int, str]":
    from halo_harness.local_cli import cmd_local
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = cmd_local(list(argv))
    return code, out.getvalue()


def _post(url: str, body: bytes, ctype: str) -> "tuple[int, bytes]":
    req = urllib.request.Request(url, data=body, headers={"Content-Type": ctype})
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status, r.read()


@test
def test_not_on_disk_starts_nothing(ctx: Ctx):
    with HfHome() as h:
        code, out = _local("serve", "--stt", SMALL)
        ctx.check(f"the download line, got {code} {out!r}", code == 1 and out.strip() ==
                  f"{SMALL} is not present -- halo voice download {SMALL} (0.5 GB)")
        ctx.check("no registry row", not (h.state / "run" / "local-servers.json").is_file()
                  or json.loads((h.state / "run" / "local-servers.json").read_text()) == [])


@test
def test_serve_stt_registers_the_server_and_the_entry(ctx: Ctx):
    from halo_harness.voice.engine_fake import TRANSCRIPT
    with HfHome() as h:
        put(h.models, SMALL)
        put(h.models, "faster-whisper:base.en")
        code, out = _local("serve", "--stt", SMALL, "--device", "cpu")
        ctx.check(f"serving, got {code} {out!r}", code == 0 and f"serving {SMALL} (stt) on http://127.0.0.1:" in out)
        ctx.check("the device line first", out.splitlines()[0].startswith(f"{SMALL} on the CPU: 0.9 GB RAM, the GPU keeps "
                                                                          "its ") and "(--device cpu)" in out.splitlines()[0])
        rows = json.loads((h.state / "run" / "local-servers.json").read_text(encoding="utf-8"))
        row = next((r for r in rows if r.get("id") == "stt"), {})
        ctx.check(f"the registry row, got {row}", row.get("kind") == "voice-stt" and row.get("device") == "cpu"
                  and row.get("ready") is True and str(row.get("log", "")).endswith("stt.log"))
        entry = next((e for e in h.config()["huggingface"].get("local_servers") or [] if e.get("name") == "stt"), {})
        ctx.check(f"the huggingface.local_servers entry, got {entry}", entry.get("runtime") == "voice-stt"
                  and entry.get("url") == row.get("base_url") and entry.get("model") == SMALL
                  and entry.get("device") == "cpu" and entry.get("pid") == row.get("pid") and entry.get("voice") is True)
        status, raw = _post(entry["url"] + "/audio/transcriptions", b"\x00\x00" * 16000, "audio/pcm;rate=16000")
        ctx.check(f"it transcribes, got {status} {raw[:80]!r}", status == 200 and json.loads(raw)["text"] == TRANSCRIPT)
        code, out = _local("servers")
        ctx.check(f"halo local servers, got {out!r}", code == 0 and "stt  voice-stt  http://127.0.0.1:" in out
                  and f"ready  {SMALL}  device cpu" in out)
        code, out = _local("log", "stt")
        ctx.check(f"halo local log stt, got {code} {out[:200]!r}", code == 0 and "voice load: stt " + SMALL in out
                  and "voice stt: audio 1.0 s" in out)
        code, out = _local("serve", "--stt", "faster-whisper:base.en")
        ctx.check(f"another model while it runs: the running one, got {code} {out!r}", code == 1
                  and out.startswith(f"stt is running: {SMALL} on http://127.0.0.1:") and "halo local stop stt first" in out)
        code, out = _local("serve", "--stt", SMALL)
        ctx.check(f"the same model: already serving, got {code} {out!r}", code == 0 and "already serving it" in out)
        code, out = _local("stop", "stt")
        ctx.check(f"stopped, got {code} {out!r}", code == 0 and out.startswith("stopped voice-stt stt"))
        ctx.check("the entry is out", not any(e.get("name") == "stt" for e in h.config()["huggingface"].get("local_servers")
                                              or []))


@test
def test_serve_tts_speaks(ctx: Ctx):
    with HfHome() as h:
        put(h.models, "kokoro-82m")
        code, out = _local("serve", "--tts", "kokoro-82m", "--device", "cpu")
        ctx.check(f"serving tts, got {code} {out!r}", code == 0 and "serving kokoro-82m (tts)" in out
                  and "/v1/audio/speech" in out)
        url = next(e["url"] for e in h.config()["huggingface"]["local_servers"] if e.get("name") == "tts")
        status, raw = _post(url + "/audio/speech", json.dumps({"input": "Hello.", "response_format": "pcm"}).encode(),
                            "application/json")
        ctx.check(f"PCM back, got {status} {len(raw)}", status == 200 and len(raw) == 2 * 12000)


@test
def test_declared_wrong_kind_and_a_missing_extra(ctx: Ctx):
    from halo_harness.voice import INSTALL_LINE
    with HfHome() as h:
        code, out = _local("serve", "--stt", "parakeet-tdt:0.6b")
        ctx.check(f"declared: its one line, exit 2, got {code} {out!r}", code == 2 and out.strip() ==
                  "no engine for parakeet-tdt in this build; faster-whisper:large-v3-turbo is the built STT")
        code, out = _local("serve", "--stt", "kokoro-82m")
        ctx.check(f"a TTS model as STT, got {code} {out!r}", code == 1 and "is not a STT model" in out)
        cfg = h.config()
        cfg["huggingface"].pop("voice_server_cmd")
        (h.state / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
        put(h.models, SMALL)
        real = sys.modules.get("faster_whisper", "absent")
        sys.modules["faster_whisper"] = None
        try:
            code, out = _local("serve", "--stt", SMALL)
        finally:
            sys.modules.pop("faster_whisper", None) if real == "absent" else sys.modules.__setitem__("faster_whisper", real)
        ctx.check(f"no extra: the install line, exit 2, got {code} {out!r}", code == 2 and INSTALL_LINE in out)


@test
def test_the_device_choice_is_said(ctx: Ctx):
    from halo_harness.voice.catalog import get
    from halo_harness.voice.device import choose, gpu_free_mib
    row = get(SMALL)
    with HfHome():
        free = gpu_free_mib()
        ctx.check(f"the box card's free MiB is read, got {free}", isinstance(free, int) and free > 0)
        got = choose(row, "auto", free_mib=22000, seen=["cpu", "cuda"])
        ctx.check(f"auto -> cuda when it fits, got {got}", got["device"] == "cuda" and got["line"] ==
                  f"{SMALL} on the GPU: 0.5 GB of its 22,000 MiB free (auto)")
        got = choose(row, "auto", free_mib=22000, seen=["cpu"])
        ctx.check(f"auto -> cpu with no CUDA, got {got['line']!r}", got["device"] == "cpu" and got["line"] ==
                  f"{SMALL} on the CPU: 0.9 GB RAM, the GPU keeps its 22,000 MiB for the chat model (auto: the engines "
                  "see no CUDA device)")
        got = choose(row, "auto", free_mib=300, seen=["cpu", "cuda"])
        ctx.check(f"auto -> cpu when it does not fit, got {got['line']!r}", got["device"] == "cpu"
                  and "the GPU has 300 MiB free, it needs 477 there" in got["line"])
        got = choose(row, "auto", free_mib=None, seen=["cpu", "cuda"])
        ctx.check("auto with no card: the CPU, said", got["device"] == "cpu" and "no GPU card read" in got["line"])
        got = choose(row, "cuda", free_mib=None, seen=["cpu"])
        ctx.check(f"asked cuda with none seen: honoured, said, got {got['line']!r}", got["device"] == "cuda"
                  and "its load may fail" in got["line"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
