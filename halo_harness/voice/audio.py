"""halo_harness.voice.audio -- the microphone and the speaker (Halo 3.3.9.0 R2; docs/VOICE.md "The loop"):

    devices() -> {"inputs": [dev], "outputs": [dev], "error": str | None}   dev = {index, name, default, channels, rate}
    lines(dev_map=None) -> the `halo voice devices` lines, the configured ones marked (voice.input_device / output_device)
    missing() -> ["sounddevice"] | []       missing_line() -> the extra's one install line
    Audio.open(input=..., output=...) -> Audio | FakeAudio   frames() yields FRAME samples of 16 kHz mono PCM16 (32 ms),
        play(pcm, rate) -> False once stop_output() cut it, stop_output() (barge-in), resume_output(), close()
    wav_frames(path) -> [frame]             a WAV as the microphone would hear it, then 600 ms of silence (--input-file)
    tone(ms) / silence(ms) -> PCM16 at 16 kHz   the fake microphone's speech and its quiet

The real devices are sounddevice's (PortAudio), part of the `voice` extra; nothing imports it until a device opens.
HALO_VOICE_AUDIO=fake (tests only) is voice/audio_fake.FakeAudio: no device is opened.
"""

from __future__ import annotations

import array
import importlib.util
import math
import os
import queue
import struct
import threading
from typing import Optional

from halo_harness.voice import INSTALL_LINE

FAKE_ENV = "HALO_VOICE_AUDIO"
RATE = 16000
FRAME = 512
FRAME_MS = 32


def fake_on() -> bool:
    return os.environ.get(FAKE_ENV, "").strip().lower() == "fake"


def missing() -> list:
    if fake_on():
        return []
    try:
        return [] if importlib.util.find_spec("sounddevice") is not None else ["sounddevice"]
    except (ImportError, ValueError):
        return ["sounddevice"]


def missing_line() -> str:
    return f"the microphone and the speaker need sounddevice (the voice extra): {INSTALL_LINE}"


def _fake_devices() -> dict:
    def rows(var, default, kind):
        names = [n for n in os.environ.get(var, default).split(",") if n.strip()]
        return [{"index": i, "name": n.strip(), "default": i == 0, "channels": 1, "rate": RATE, "kind": kind}
                for i, n in enumerate(names)]
    return {"inputs": rows("HALO_VOICE_FAKE_INPUTS", "fake microphone", "input"),
            "outputs": rows("HALO_VOICE_FAKE_OUTPUTS", "fake speaker", "output"), "error": None}


def devices() -> dict:
    if fake_on():
        return _fake_devices()
    if missing():
        return {"inputs": [], "outputs": [], "error": missing_line()}
    try:
        import sounddevice as sd
        found = sd.query_devices()
        din, dout = (list(sd.default.device) + [None, None])[:2]
    except Exception as e:  # PortAudio itself missing (Linux: the apt line in docs/INSTALL.md)
        return {"inputs": [], "outputs": [], "error": f"the audio devices could not be read: {e}"}
    out: dict = {"inputs": [], "outputs": [], "error": None}
    for i, d in enumerate(found):
        base = {"index": i, "name": str(d.get("name")), "rate": int(d.get("default_samplerate") or RATE)}
        if int(d.get("max_input_channels") or 0) > 0:
            out["inputs"].append({**base, "default": i == din, "channels": int(d["max_input_channels"]), "kind": "input"})
        if int(d.get("max_output_channels") or 0) > 0:
            out["outputs"].append({**base, "default": i == dout, "channels": int(d["max_output_channels"]), "kind": "output"})
    return out


def _setting(key: str):
    from halo_harness.theme import get_config_value
    return get_config_value(key, default=None)


def resolve(kind: str, want=None, dev_map: Optional[dict] = None) -> Optional[dict]:
    """The device a loop opens: `want` (an index or part of a name), else voice.input_device / output_device, else the
    system default; None when there is none."""
    rows = (dev_map or devices())["inputs" if kind == "input" else "outputs"]
    want = want if want not in (None, "") else _setting(f"voice.{kind}_device")
    if want not in (None, ""):
        w = str(want).strip().lower()
        hit = next((d for d in rows if str(d["index"]) == w), None) or next((d for d in rows if w in d["name"].lower()), None)
        if hit is not None:
            return hit
    return next((d for d in rows if d["default"]), rows[0] if rows else None)


def lines(dev_map: Optional[dict] = None) -> list:
    m = dev_map or devices()
    if m.get("error"):
        return [m["error"]]
    out = []
    for kind, label in (("input", "inputs"), ("output", "outputs")):
        chosen = resolve(kind, dev_map=m)
        out.append(f"{label} (voice.{kind}_device):")
        for d in m[label]:
            mark = "*" if chosen is not None and d["index"] == chosen["index"] else " "
            out.append(f"  {mark} {d['index']:>3}  {d['name']}{'  (default)' if d['default'] else ''}")
        if not m[label]:
            out.append("  no microphone: halo voice --input-file <wav> drives one turn from a file" if kind == "input"
                       else "  no speaker: halo voice --input-file <wav> --output-file <wav> writes the reply instead")
    return out


def tone(ms: int, rate: int = RATE, hz: float = 220.0, amp: int = 8000) -> bytes:
    n = int(rate * ms / 1000)
    return b"".join(struct.pack("<h", int(amp * math.sin(2 * math.pi * hz * i / rate))) for i in range(n))


def silence(ms: int, rate: int = RATE) -> bytes:
    return b"\0\0" * int(rate * ms / 1000)


def split(pcm: bytes) -> list:
    step = FRAME * 2
    return [pcm[i:i + step].ljust(step, b"\0") for i in range(0, len(pcm), step)]


def wav_frames(path) -> list:
    from halo_harness.voice.server_routes import from_wav
    with open(path, "rb") as f:
        pcm, rate = from_wav(f.read())
    if rate != RATE and pcm:
        src = array.array("h", pcm)
        n = max(1, int(len(src) * RATE / rate))
        pcm = array.array("h", (src[min(len(src) - 1, int(i * rate / RATE))] for i in range(n))).tobytes()
    return split(pcm + silence(600))


class Audio:
    """sounddevice streams: the microphone at 16 kHz mono in FRAME blocks, the speaker opened at the reply's rate."""

    def __init__(self, inp: Optional[dict], out: Optional[dict]) -> None:
        import sounddevice as sd
        self.sd, self.inp, self.out = sd, inp, out
        self.q: "queue.Queue" = queue.Queue()
        self.cut, self.closed = threading.Event(), threading.Event()
        self._out, self._out_rate = None, None
        self._in = None
        if inp is not None:
            self._in = sd.RawInputStream(samplerate=RATE, channels=1, dtype="int16", blocksize=FRAME, device=inp["index"],
                                         callback=lambda data, _n, _t, _s: self.q.put(bytes(data)))
            self._in.start()

    @classmethod
    def open(cls, input=None, output=None):
        if fake_on():
            from halo_harness.voice.audio_fake import FakeAudio
            return FakeAudio()
        m = devices()
        return cls(resolve("input", input, m) if input is not False else None, resolve("output", output, m))

    def frames(self):
        while not self.closed.is_set():
            try:
                yield self.q.get(timeout=0.25)
            except queue.Empty:
                continue

    def play(self, pcm: bytes, rate: int) -> bool:
        if self.cut.is_set() or self.out is None:
            return False
        if self._out is None or self._out_rate != rate:
            self._out = self.sd.RawOutputStream(samplerate=rate, channels=1, dtype="int16", device=self.out["index"])
            self._out.start()
            self._out_rate = rate
        out, step = self._out, max(2, rate // 50 * 2)  # 20 ms writes: a cut lands within one of them
        try:
            for i in range(0, len(pcm), step):
                if self.cut.is_set():
                    return False
                out.write(pcm[i:i + step])
        except Exception:  # a barge-in aborted the stream mid-write
            return False
        return not self.cut.is_set()

    def stop_output(self) -> None:
        self.cut.set()
        s, self._out = self._out, None
        if s is not None:
            try:
                s.abort()
                s.close()
            except Exception:
                pass

    def resume_output(self) -> None:
        self.cut.clear()

    def close(self) -> None:
        self.closed.set()
        self.stop_output()
        if self._in is not None:
            try:
                self._in.stop()
                self._in.close()
            except Exception:
                pass
