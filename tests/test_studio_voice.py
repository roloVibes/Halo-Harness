"""tests.test_studio_voice -- Halo 3.3.9.0 R3 deliverable 3: Local -> Voice in headless Chrome through
tests/helpers/studio_voice.py (skipped without one), with Chrome's FAKE media device (no real microphone), fake speech
engines, a scripted session behind its control socket; no model call, never a request beyond 127.0.0.1:

1. the servers' status: stt running (its url), tts stopped with its cost line (device, memory, seconds); the catalog's
   seven models with the two on disk marked present; a download's size line before anything moves; the glasses note
   (no phone app ships; the voice door is the contract); Talk's title says what it does and costs; nothing opens over
   the page;
2. one Talk turn end to end: the confirm text first (the microphone, the server it starts, the seconds, no dollars),
   the fake microphone records, Send; the transcript shows, the reply, the audio sink received the reply's bytes (two
   sentences of the fake engine's 500 ms at 24 kHz), the card's line, the turn in the list (via studio), tts started
   with its cost line said;
3. Stop on the tts row stops the server Talk started.
Run: python -m tests.test_studio_voice
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.driver_got import got as driver_got  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
_RUN: dict = {}


def _got(ctx: Ctx) -> dict:
    info = driver_got(ctx, "tests.helpers.studio_voice", why="the Voice page checks need headless Chrome", cache=_RUN,
                      timeout=300)
    ctx.check(f"nothing left 127.0.0.1, got {info.get('blocked')}", not info.get("blocked"))
    return info


@test
def test_the_servers_the_catalog_and_the_notes(ctx: Ctx):
    got = _got(ctx)
    s = {r[0]: r[1:] for r in got.get("servers") or []}
    ctx.check(f"stt running on its url, tts stopped with its cost line, got {s}", sorted(s) == ["stt", "tts"]
              and s["stt"][:2] == ["running", "faster-whisper:small.en"] and s["stt"][2].startswith("on http://127.0.0.1:")
              and s["tts"][:2] == ["stopped", "kokoro-82m"] and s["tts"][2].startswith("starting tts: kokoro-82m on the CPU")
              and "~3 s to load" in s["tts"][2])
    cat = dict(got.get("catalog") or [])
    ctx.check(f"the seven models, the two on disk present, got {cat}", len(cat) == 7
              and [k for k, v in cat.items() if v] == ["faster-whisper:small.en", "kokoro-82m"])
    ctx.check(f"a download says its size first, got {got.get('size')!r}", str(got.get("size")).startswith(
        "faster-whisper:base.en: 0.15 GB from Systran/faster-whisper-base.en (repo unverified) into "))
    ctx.check(f"the glasses note: no phone app ships, the door is the contract, got {got.get('note')!r}",
              "no phone app ships with Halo" in str(got.get("note")) and "POST /host/v1/voice/turn" in str(got.get("note")))
    title = str(got.get("talk_title"))
    ctx.check(f"Talk's title says what it does and costs, got {title!r}", title.startswith("Talk asks this browser for the "
              "microphone") and "It starts tts: kokoro-82m" in title and "costs time, not dollars" in title)
    ctx.check(f"one session to talk to, nothing opens over the page, got {got.get('sessions')} {got.get('dialogs')}",
              got.get("sessions") == 1 and got.get("dialogs") == 0)


@test
def test_one_talk_turn_end_to_end(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the confirm text first, got {got.get('confirm')!r}", got.get("confirm") == got.get("talk_title"))
    ctx.check(f"the fake microphone recorded, got {got.get('seconds')}", isinstance(got.get("seconds"), (int, float))
              and got["seconds"] >= 0.5)
    ctx.check(f"the transcript shows, got {got.get('transcript')!r}", got.get("transcript") == "you said: what is in the readme")
    ctx.check(f"the reply, got {got.get('reply')!r}", got.get("reply") == "The readme says hello. That is all.")
    ctx.check(f"the sink received both sentences' audio (2 x 500 ms at 24 kHz), got {got.get('sink')}",
              got.get("sink") == 2 * 24000)
    ctx.check(f"the card's line, got {got.get('line')!r}", str(got.get("line")).startswith("voice: ") and " of 1.5 s" in str(got.get("line")))
    ctx.check(f"the turn in the list, via studio, got {got.get('turns')}", [t[0] for t in got.get("turns") or []] == ["studio"])
    ctx.check(f"Talk started tts with its cost line said, got {got.get('tts')} {got.get('notes')}", got.get("tts") == "running"
              and any(str(n).startswith("starting tts: kokoro-82m") for n in got.get("notes") or []))
    ctx.check(f"one transcription, one model call, no error, got {got.get('stt_requests')} {got.get('session_turns')} "
              f"{got.get('error')!r}", got.get("stt_requests") == 1 and got.get("session_turns") == 1 and not got.get("error"))


@test
def test_stop_stops_the_server_talk_started(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"tts stopped, stt still running, got {got.get('after_stop')} {got.get('stop_said')!r}",
              got.get("after_stop") == ["running", "stopped"] and str(got.get("stop_said")).startswith("stopped voice-tts tts"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
