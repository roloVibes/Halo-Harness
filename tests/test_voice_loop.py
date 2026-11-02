"""tests.test_voice_loop -- Halo 3.3.9.0 R2: the voice loop (halo_harness/voice/loop.py, speak.py, latency.py) on a
real Controller over a real Session whose model replies are scripted (tests/helpers/voice_rig.VoiceRig), R1's speech
routes in process with a fake engine, the fake audio seam and the fake VAD:

1. an utterance's transcript lands as the prompt (the session's log, the `heard` event), the reply is cut into
   sentences, each spoken through the TTS server and played, and the turn's card lands in voice/turns.jsonl with
   every stage filled;
2. a second utterance while the turn still runs steers it (steer_queued, the next request carries it; the echo says it
   steers);
3. a code fence is said once as "a code block", never read out;
4. barge-in: speech over a reply stops the playback within the fake clock's 250 ms, the rest is not spoken, the
   transcript gets "(interrupted while speaking)";
5. push-to-talk: press, the frames, press again -> one utterance; --input-file: a WAV is one turn;
6. `halo voice stats`: the median and the worst per stage over the newest turns, the slow stage named.
No audio device, no model, nothing leaves 127.0.0.1.
Run: python -m tests.test_voice_loop
"""
from __future__ import annotations

import json
import sys
import tempfile
import threading
import time
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.turn_session import text_step  # noqa: E402
from tests.helpers.voice_rig import VoiceRig, gated, talk, text_chunks  # noqa: E402

test, TESTS = new_registry()
ASK = "what is in the readme"


def _user_texts(session) -> list:
    return [b.get("text", "") for n in session.log.nodes() if n.get("type") == "user"
            for b in (n.get("content") or []) if isinstance(b, dict)]


@test
def test_the_transcript_is_the_prompt_and_the_reply_is_spoken(ctx: Ctx):
    from halo_harness.voice.latency import rows
    with VoiceRig([text_step("The readme has two parts. One is setup! The other: usage?")], transcripts=[ASK]) as r:
        loop = r.loop(clock=time.monotonic)
        talk(r, loop)
        ctx.check("the turn ended with its card", loop.turns.wait(10))
        ctx.check(f"the transcript is the prompt, got {_user_texts(r.session)}", ASK in _user_texts(r.session))
        heard = r.voice("heard")
        ctx.check(f"the heard event carries it, not a steer, got {heard}", heard and heard[0]["text"] == ASK
                  and heard[0]["steer"] is False)
        said = r.info["tts"]["said"]
        ctx.check(f"each sentence spoken in order, got {said}",
                  said == ["The readme has two parts.", "One is setup!", "The other: usage?"])
        ctx.check(f"played at the reply's rate, got {len(r.audio.captured)} chunks",
                  len(r.audio.captured) == 3 and all(rate == 24000 for rate, _ in r.audio.captured))
        got = rows(r.state)
        st = got[-1]["stages"] if got else {}
        ctx.check(f"the card is in turns.jsonl with every stage, got {got}", len(got) == 1 and all(
            isinstance(st.get(k), int) for k in ("heard", "text", "token", "audio", "last")) and got[0]["total_ms"] >= 0)
        card = r.voice("card")
        ctx.check(f"one card line after the turn, got {card}", len(card) == 1 and card[0]["text"].startswith("voice: "))


@test
def test_a_second_utterance_mid_turn_steers(ctx: Ctx):
    gate = threading.Event()
    calls = {"n": 0}

    def scn(h, body):
        calls["n"] += 1
        if calls["n"] == 1:
            return gated(text_chunks("Working on the first. ", stop=False), gate, text_chunks("Still working."))(h, body)
        from tests.helpers.mock_openai import _finish
        _finish(h, text_step("Doing the second thing instead."))
    with VoiceRig(scn, transcripts=[ASK, "actually do the second thing"]) as r:
        loop = r.loop()
        talk(r, loop)
        ctx.check("the turn runs, its first text streamed", r.wait(lambda: r.session.busy and "text_delta" in r.kinds()))
        talk(r, loop)
        ok = r.wait(lambda: "steer_queued" in r.kinds())
        gate.set()
        ctx.check("the second utterance is a steer (steer_queued)", ok)
        heard = r.voice("heard")
        ctx.check(f"the echo says it steers, got {heard}", len(heard) == 2 and heard[1]["steer"] is True)
        from halo_harness.tui.voice_view import heard_line
        ctx.check("the transcript line", heard_line(heard[1]["text"], True) ==
                  "you said: actually do the second thing (steers the running turn)")
        ctx.check("the turn finished once", r.wait(lambda: r.kinds().count("turn_done") == 1, 15))
        ctx.check(f"the next model call carried the steer, got {calls['n']} calls",
                  calls["n"] == 2 and "actually do the second thing" in " ".join(_user_texts(r.session)))
        ctx.check("the steered reply is spoken", r.wait(lambda: "Doing the second thing instead." in r.info["tts"]["said"]))
        ctx.check("the first card ended as steered", any(c.steered for c in loop.cards))


@test
def test_code_fences_are_said_once_never_read(ctx: Ctx):
    reply = "Here it is.\n```python\nprint('x')\nprint('y')\n```\nRun it twice. See [1] and [the docs](https://x)."
    with VoiceRig([text_step(reply)]) as r:
        loop = r.loop()
        talk(r, loop)
        ctx.check("the turn ended", loop.turns.wait(10))
        said = r.info["tts"]["said"]
        ctx.check(f"the fence is 'a code block', the markup out, got {said}",
                  said == ["Here it is.", "a code block", "Run it twice.", "See and the docs."])


@test
def test_barge_in_stops_the_reply_within_250_ms(ctx: Ctx):
    with VoiceRig([text_step("This is a long answer. It keeps going. And going on.")], hold=True) as r:
        loop = r.loop()
        talk(r, loop)
        ctx.check("the reply is playing (held)", r.audio.playing.wait(10))
        first = talk(r, loop, ms=200)
        ctx.check(f"the output stopped {r.audio.stopped_at and round((r.audio.stopped_at - first) * 1000)} ms after the "
                  "speech started (within 250)", r.audio.stopped_at is not None and 0 <= r.audio.stopped_at - first <= 0.25)
        ctx.check(f"the rest was not spoken, got {r.info['tts']['said']}",
                  r.info["tts"]["said"][:1] == ["This is a long answer."] and "And going on." not in r.info["tts"]["said"])
        ctx.check(f"the transcript says so, got {r.voice('interrupted')}",
                  [d["text"] for d in r.voice("interrupted")] == ["(interrupted while speaking)"])
        ctx.check("the interrupted card is marked", any(c.interrupted for c in loop.cards))
        ctx.check("the new utterance reached the session", r.wait(lambda: len(r.voice("heard")) == 2))


@test
def test_push_to_talk_and_an_input_file(ctx: Ctx):
    from halo_harness.voice.audio import split, tone, wav_frames
    with VoiceRig([text_step("Heard you.")]) as r:
        loop = r.loop(mode="ptt")
        loop.on_frame(split(tone(100))[0])
        ctx.check("ptt: nothing is heard before the press", r.info["stt"]["n"] == 0 and not r.voice("heard"))
        ctx.check("the press listens", "listening" in loop.ptt())
        for f in split(tone(300)):
            loop.on_frame(f)
        ctx.check("the second press sends it", loop.ptt().startswith("sent"))
        ctx.check("one utterance, one turn", loop.turns.wait(10) and r.info["stt"]["n"] == 1 and len(r.voice("heard")) == 1)
        path = Path(tempfile.mkdtemp(prefix="vl_wav-")) / "hello.wav"
        with wave.open(str(path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            w.writeframes(tone(400))
        loop.mode = "hands-free"
        loop.turns.clear()
        loop.say_file(wav_frames(path))
        ctx.check("--input-file: the WAV is one turn", loop.turns.wait(10) and len(r.voice("heard")) == 2)


@test
def test_stats_median_and_the_slow_stage(ctx: Ctx):
    from halo_harness.voice.latency import Card, line, record, stats, stats_lines
    state = Path(tempfile.mkdtemp(prefix="vl_stats-"))
    for heard, text, token, audio in ((200, 300, 400, 100), (250, 320, 900, 120), (240, 310, 1100, 90)):
        c = Card(budget_ms=1500)
        t = 0.0
        for stamp, ms in (("spoke", 0), ("heard", heard), ("text", text), ("token", token), ("audio", audio),
                          ("last", 2000)):
            t += ms / 1000.0
            c.mark(stamp, at=t)
        record(state, c)
    st = stats(state)
    ctx.check(f"three turns, medians per stage, got {st['stages']}", st["turns"] == 3 and st["stages"]["heard"]["median"]
              == 240 and st["stages"]["token"]["median"] == 900 and st["stages"]["token"]["worst"] == 1100)
    ctx.check(f"the slow stage is named, got {st['slow']}", st["slow"]["stage"] == "token" and st["slow"]["of_share"] == 1.5)
    out = "\n".join(stats_lines(st))
    ctx.check(f"the lines, got {out!r}", "token   median    900 ms  worst  1,100 ms" in out
              and "the slow stage: token (1.5x its share, over it)" in out)
    rows = [json.loads(x) for x in (state / "voice" / "turns.jsonl").read_text().splitlines()]
    ctx.check(f"the status-bar line of the slow one, got {line(rows[-1])!r}", line(rows[-1]) ==
              "voice: 1.7 s, over the 1.5 s budget (heard 0.2 · text 0.3 · token 1.1 · audio 0.1) -- slow: token")
    ctx.check(f"a fast one, got {line(rows[0])!r}", line(rows[0]) ==
              "voice: 1.0 s of 1.5 s (heard 0.2 · text 0.3 · token 0.4 · audio 0.1)")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
