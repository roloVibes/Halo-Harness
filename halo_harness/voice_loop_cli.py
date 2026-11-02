"""halo_harness.voice_loop_cli -- the voice loop's commands (Halo 3.3.9.0 R2; docs/COMMANDS-voice.md):

    halo voice [halo flags]                      `halo` with voice on (the TUI, then `/voice on`; voice.mode ptt: push-
                                                 to-talk); without the extra: the one install line, exit 2
    halo voice --input-file <wav> [--output-file <wav>] [halo flags]   one turn from a file, no microphone: the
                                                 transcript, the reply (spoken, or written to --output-file), its card
    halo voice on | off [--session ID]           voice on or off in a running session, through its control socket
    halo voice devices [--json]                  the microphones and speakers, the configured ones marked
    halo voice stats [--json] [-n 50]            median and worst per stage over the newest turns, the slow stage named
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import wave

TURN_WAIT_S = 600.0


def _missing_line(need_mic: bool = True):
    from halo_harness.voice import audio, engines
    from halo_harness.voice.launch import server_cmd
    from halo_harness.voice.remote import parse, setting  # 3.3.9.0 R3: both servers on another halo: no engines here
    far = all(parse(setting(k)) for k in ("stt", "tts"))
    gone = list(audio.missing()) + ([] if server_cmd()[1] or far else [m for m in engines.missing()])
    if gone:
        from halo_harness.voice import INSTALL_LINE
        return f"voice needs the voice extra ({', '.join(dict.fromkeys(gone))} missing): {INSTALL_LINE}"
    return None


def _devices(argv: list) -> int:
    from halo_harness.voice import audio
    p = argparse.ArgumentParser(prog="halo voice devices", description="The microphones and speakers the loop can open.")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    m = audio.devices()
    if a.json:
        print(json.dumps({**m, "input": audio.resolve("input", dev_map=m), "output": audio.resolve("output", dev_map=m)},
                         indent=2))
        return 0
    print("\n".join(audio.lines(m)))
    return 0 if not m.get("error") else 2


def _stats(argv: list) -> int:
    from halo_harness.config.paths import bridge_home
    from halo_harness.voice.latency import stats, stats_lines
    p = argparse.ArgumentParser(prog="halo voice stats", description="The voice turns' latency cards, summarized.")
    p.add_argument("--json", action="store_true")
    p.add_argument("-n", type=int, default=50, help="the newest N turns (default 50)")
    a = p.parse_args(argv)
    st = stats(bridge_home(), max(1, a.n))
    print(json.dumps(st, indent=2) if a.json else "\n".join(stats_lines(st)))
    return 0


def _toggle(word: str, argv: list) -> int:
    from halo_harness.remote.client import ControlClient, default_token_for
    from halo_harness.remote.registry import list_live
    p = argparse.ArgumentParser(prog=f"halo voice {word}", description=f"Voice {word} in a running session.")
    p.add_argument("--session", default="", help="a session id (or its start); default: the one running session")
    p.add_argument("mode", nargs="?", default="", help="on: hands-free | ptt")
    a = p.parse_args(argv)
    live = [r for r in list_live() if r.get("kind", "tui") == "tui"]
    rows = [r for r in live if str(r.get("session_id") or "").startswith(a.session)] if a.session else live
    if len(rows) != 1:
        if not rows:
            print("no running halo session here: halo voice opens one with voice on")
        else:
            print(f"{len(rows)} sessions run here; pick one with --session:")
            for r in rows:
                print(f"  {r.get('session_id')}  {r.get('cwd')}  {r.get('title') or ''}".rstrip())
        return 1
    e = rows[0]
    c = ControlClient(str(e.get("endpoint") or ""), default_token_for(e))
    try:
        r = c.call("slash", name="voice", args=" ".join(x for x in (word, a.mode) if x))
    finally:
        c.close()
    if not r.get("ok"):
        print(f"the session did not take it: {r.get('error')}")
        return 1
    print((r.get("result") or {}).get("output") or "")
    return 0


class FileOut:
    """--output-file: the reply's audio kept and written as one WAV when the turn ends (no speaker opened)."""

    def __init__(self, path: str) -> None:
        self.path, self.rate, self.pcm = path, 24000, []
        self.cut = threading.Event()

    def play(self, pcm: bytes, rate: int) -> bool:
        self.rate = rate
        self.pcm.append(pcm)
        return True

    def stop_output(self) -> None:
        self.cut.set()

    def resume_output(self) -> None:
        self.cut.clear()

    def frames(self):
        return iter(())

    def close(self) -> None:
        with wave.open(self.path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(self.rate)
            w.writeframes(b"".join(self.pcm))


def _printer(state: str, data: dict) -> None:
    from halo_harness.tui.voice_view import heard_line
    if state == "heard":
        print(heard_line(str(data.get("text") or ""), bool(data.get("steer"))))
    elif state in ("note", "card", "interrupted") and data.get("text"):
        print(data["text"])


def one_turn(rest: list, wav: str, out_wav: str = "") -> int:
    from halo_harness.cli import _build_parser
    from halo_harness.tui.bootstrap import build_controller
    from halo_harness.voice import audio as A, session
    from halo_harness.voice.audio import wav_frames
    try:
        frames = wav_frames(wav)
    except (OSError, ValueError) as e:
        print(f"{wav}: {e}")
        return 1
    if not out_wav and A.missing():
        print(A.missing_line() + " (or --output-file <wav> writes the reply instead)")
        return 2
    controller, _registry, _facade = build_controller(_build_parser().parse_args(rest))
    controller.start()
    try:
        out = FileOut(out_wav) if out_wav else A.Audio.open(input=False)
        ok, lines = session.on(controller, "hands-free", audio=out, say=print, mic=False)
        print("\n".join(lines))
        if not ok:
            return 1
        loop = session.get(controller)
        loop.sink = _printer
        loop.sink("note", {"text": f"{wav}: {len(frames) * A.FRAME_MS / 1000:.1f} s of audio"})
        loop.say_file(frames)
        loop.turns.wait(TURN_WAIT_S)
        reply = loop.cards[-1].text.strip() if loop.cards else ""
        if reply:
            print(f"reply: {reply}")
        session.off(controller)
        if out_wav:
            print(f"the reply's audio: {out_wav}")
        return 0 if loop.cards else 1
    finally:
        controller.quit()


def start(argv: list) -> int:
    p = argparse.ArgumentParser(prog="halo voice", add_help=False)
    p.add_argument("--input-file", default="")
    p.add_argument("--output-file", default="")
    a, rest = p.parse_known_args(argv)
    if a.input_file:
        return one_turn(rest, a.input_file, a.output_file)
    line = _missing_line()
    if line:
        print(line)
        return 2
    from halo_harness.cli import main
    from halo_harness.voice.session import _mode
    return main(rest + [f"/voice {'ptt' if _mode(None) == 'ptt' else 'on'}"])


LOOP_COMMANDS = {"devices": _devices, "stats": _stats, "on": lambda argv: _toggle("on", argv),
                 "off": lambda argv: _toggle("off", argv)}


if __name__ == "__main__":
    sys.exit(start(sys.argv[1:]))
