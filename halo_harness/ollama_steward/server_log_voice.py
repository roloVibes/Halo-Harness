"""halo_harness.ollama_steward.server_log_voice -- Halo 3.3.9.0 R1: a speech server's log lines as the steward's events
(server_rules_hf.classify hands a voice-stt / voice-tts server's lines here). The lines are voice/log_lines.py's: the
server writes them and this reads them with the same patterns.

    classify(line, at=None, runtime="voice-stt") -> event | None
        `voice load:`            load-result {model, device, compute, load_s, gpu_free_mib, voice: stt|tts}
        `voice stt:`             timing {voice: stt, audio_s, seconds, rtf, device}
        `voice tts:`             timing {voice: tts, chars, audio_s, first_ms, seconds, device}
        `voice load failed:`     load-failed {model, device, error, extra: the install line was the cause}
        `voice request failed:`  http-500 (a 500) | other-error
        a Python exception's last line (`RuntimeError: ...`) other-error; any other line None

The rules that read the events are ollama_steward/rules_voice.py (stt-slow, tts-slow, voice-cpu, voice-load-failed).
"""

from __future__ import annotations

import re
from typing import Optional

from halo_harness.ollama_steward.server_rules import event
from halo_harness.voice import INSTALL_LINE
from halo_harness.voice.log_lines import parse

SAYS = ("load-failed", "http-500", "other-error", "timing", "load-result")
_EXC = re.compile(r"^\w*(Error|Exception): ")


def classify(line: str, at=None, runtime: Optional[str] = None) -> Optional[dict]:
    rt = runtime or "voice-stt"
    text = str(line or "").rstrip("\r\n")
    got = parse(text)
    if got is None:
        if _EXC.match(text.strip()):
            return event("other-error", f"the speech server raised {text.strip()[:160]}", text, at=at, runtime=rt)
        return None
    w = got["what"]
    if w == "load":
        return event("load-result", f"{got['model']} loaded on the speech server ({got['kind']}) on {got['device']} "
                     f"({got['compute']}), {got['seconds']:.1f} s", text, at=at, model=got["model"], runtime=rt,
                     device=got["device"], compute=got["compute"], load_s=got["seconds"],
                     gpu_free_mib=got["gpu_free_mib"], voice=got["kind"])
    if w == "stt":
        return event("timing", f"audio {got['audio_s']:g} s -> text in {got['seconds']:.2f} s ({got['rtf']:g}x realtime) "
                     f"on {got['device']}", text, at=at, runtime=rt, voice="stt", audio_s=got["audio_s"],
                     seconds=got["seconds"], rtf=got["rtf"], device=got["device"])
    if w == "tts":
        return event("timing", f"text {got['chars']} chars -> audio {got['audio_s']:g} s, first audio {got['first_ms']} ms "
                     f"on {got['device']}", text, at=at, runtime=rt, voice="tts", chars=got["chars"],
                     audio_s=got["audio_s"], first_ms=got["first_ms"], seconds=got["seconds"], device=got["device"])
    if w == "load-failed":
        return event("load-failed", f"the speech server failed to load {got['model']} on {got['device']}: "
                     f"{got['error'][:160]}", text, at=at, model=got["model"], runtime=rt, device=got["device"],
                     error=got["error"], extra=INSTALL_LINE in got["error"] or None, voice=got["kind"])
    if w == "request-failed":
        kind = "http-500" if got["status"] == 500 else "other-error"
        return event(kind, f"a speech request failed ({got['method']} {got['path']} {got['status']}): {got['error'][:160]}",
                     text, at=at, runtime=rt, status=got["status"])
    return None
