"""tests.helpers.servers_seed_voice -- Halo 3.3.9.0 R1: the speech servers of tests/helpers/servers_seed.Home(voice=True):
`stt` (faster-whisper:large-v3-turbo on the CPU while the GPU had 22,000 MiB free, transcribing under 2x realtime, one
500) and `tts` (kokoro-82m: a failed CUDA load, then the CPU, its first audio past 400 ms), each a registry row Halo
started (a pid no process has) with its log, and the `huggingface.local_servers` entry the launcher writes. The lines
are voice/log_lines.py's own formats; nothing runs, nothing is sent.

    seed(home) -> None        writes the two logs, the two registry rows and the two entries into home's state
    STT_LOG / TTS_LOG / EXTRA_LINE   the fixture lines
"""
from __future__ import annotations

import json

PY = "/usr/bin/python3 -m halo_harness.voice.server"
STT_LOG = f"""--- halo starts: {PY} --kind stt --model faster-whisper:large-v3-turbo --path /models/turbo --device cpu --port 8091 --log stt.log --gpu-free-mib 22000
listening on 127.0.0.1:8091
voice server listening on http://127.0.0.1:8091 (stt faster-whisper:large-v3-turbo)
voice load: stt faster-whisper:large-v3-turbo on cpu (int8) in 6.20 s; the GPU had 22,000 MiB free
voice stt: audio 4.2 s -> text in 3.10 s (1.4x realtime) on cpu
voice stt: audio 2.0 s -> text in 1.60 s (1.2x realtime) on cpu
voice stt: audio 6.0 s -> text in 3.50 s (1.7x realtime) on cpu
voice request failed: POST /v1/audio/transcriptions 500: RuntimeError: the fixture engine's error
"""
TTS_LOG = f"""--- halo starts: {PY} --kind tts --model kokoro-82m --path /models/kokoro --device cuda --port 8092 --log tts.log
listening on 127.0.0.1:8092
voice load failed: tts kokoro-82m on cuda: RuntimeError: Library libcublas.so.12 is not found or cannot be loaded
--- halo starts: {PY} --kind tts --model kokoro-82m --path /models/kokoro --device cpu --port 8092 --log tts.log
listening on 127.0.0.1:8092
voice load: tts kokoro-82m on cpu (fp32) in 1.10 s
voice tts: text 84 chars -> audio 3.9 s, first audio 620 ms, in 1.40 s on cpu
voice tts: text 40 chars -> audio 2.0 s, first audio 540 ms, in 0.90 s on cpu
"""
EXTRA_LINE = ("voice load failed: stt faster-whisper:small.en on cpu: the speech engines are not installed "
              '(faster_whisper missing): uv tool install --reinstall "halo-harness[voice]"')


def seed(home) -> None:
    d = home.state / "local" / "servers"
    d.mkdir(parents=True, exist_ok=True)
    reg_path = home.state / "run" / "local-servers.json"
    reg_path.parent.mkdir(parents=True, exist_ok=True)
    rows = json.loads(reg_path.read_text(encoding="utf-8")) if reg_path.is_file() else []
    cfg = json.loads((home.state / "config.json").read_text(encoding="utf-8"))
    entries = cfg.setdefault("huggingface", {}).setdefault("local_servers", [])
    for kind, model, port, text, device in (("stt", "faster-whisper:large-v3-turbo", 8091, STT_LOG, "cpu"),
                                            ("tts", "kokoro-82m", 8092, TTS_LOG, "cpu")):
        log = d / f"{kind}.log"
        log.write_text(text, encoding="utf-8")
        setattr(home, f"{kind}_log", log)
        url = f"http://127.0.0.1:{port}"
        rows.append({"id": kind, "kind": f"voice-{kind}", "runtime": f"voice-{kind}", "model": model, "port": port,
                     "pid": home.pid, "base_url": f"{url}/v1", "log": str(log), "halo": True, "device": device,
                     "cmdline": PY.split() + ["--kind", kind, "--model", model, "--port", str(port)]})
        entries.append({"name": kind, "url": f"{url}/v1", "log": str(log), "runtime": f"voice-{kind}", "model": model,
                        "device": device, "pid": home.pid, "voice": True})
    reg_path.write_text(json.dumps(rows), encoding="utf-8")
    (home.state / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
