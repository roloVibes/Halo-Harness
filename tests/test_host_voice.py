"""tests.test_host_voice -- Halo 3.3.9.0 R3: the host's voice door, `POST /host/v1/voice/turn` (host/ops_voice.py,
voice/turn.py), over tests/helpers/voice_door_rig.DoorRig: a halo host whose speech servers are R1's routes with fake
engines and whose session is a real Controller with scripted replies behind its control socket, and a peer paired
with it in this process:

1. one utterance (a 16 kHz WAV) in: the transcript first (a J frame), the reply's audio as A frames (two sentences
   spoken), the trailer with the transcript, the reply, the latency card; the audit row by op with the seconds and the
   session; the host's voice/turns.jsonl keeps the card; the pair key in neither;
2. an 8 kHz utterance (the glasses' HFP capture) is resampled and heard;
3. each refusal is one line before any audio: no `control` grant (the grant command), no session there, the 30 s
   budget, no stt server (the serve command), an audio shape the door does not read;
4. `GET me` lists the door, its grant, the speech servers by model and the sessions it reaches (no endpoint, no token);
   the served rows give a speech server `kind: speech` and its model.
No model, no audio device, nothing leaves 127.0.0.1.
Run: python -m tests.test_host_voice
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.turn_session import text_step  # noqa: E402
from tests.helpers.voice_door_rig import DoorRig, wav  # noqa: E402

test, TESTS = new_registry()
REPLY = "The answer is short. That is all."


def _turn(r, body=None, ctype="audio/wav", **kw) -> "tuple[list, str]":
    from halo_harness.voice import remote
    from halo_harness.voice.client import VoiceError
    try:
        return list(remote.turn(r.client(), wav() if body is None else body, ctype, **kw)), ""
    except VoiceError as e:
        return [], str(e)


@test
def test_one_utterance_in_the_reply_out(ctx: Ctx):
    with DoorRig([text_step(REPLY)], transcripts=["what is the answer"]) as r:
        frames, err = _turn(r)
        kinds = [k for k, _p in frames]
        ctx.check(f"J heard first, J rate, then audio, the trailer last, got {kinds} {err!r}", not err and kinds[:3] == ["J", "J", "A"]
                  and frames[1][1] == {"rate": 24000} and kinds.count("J") == 3
                  and frames[0][1] == {"heard": "what is the answer"} and kinds[-1] == "J" and "A" in kinds)
        audio = sum(len(p) for k, p in frames if k == "A")
        t = frames[-1][1] if frames else {}
        ctx.check(f"the trailer: transcript, reply, rate, the bytes it streamed, got {t}", t.get("done") is True
                  and t.get("transcript") == "what is the answer" and t.get("reply") == REPLY and t.get("rate") == 24000
                  and t.get("audio_bytes") == audio == 2 * 1920)
        st = (t.get("card") or {}).get("stages") or {}
        ctx.check(f"the card: text, token and audio measured, its line, got {st} {t.get('line')!r}",
                  all(isinstance(st.get(k), int) for k in ("text", "token", "audio")) and str(t.get("line")).startswith("voice: "))
        ctx.check(f"the two sentences went to the tts server, got {r.info['tts']['said']}",
                  r.info["tts"]["said"] == ["The answer is short.", "That is all."])
        rows = r.rig.rig.audit_rows(1, op="voice_turn")
        ctx.check(f"one audit row by op: the seconds, the session, landed, got {rows}", len(rows) == 1 and rows[0]["ok"]
                  and rows[0]["params"]["seconds"] == 0.5 and str(r.handle.session_id).startswith(rows[0]["params"]["session"])
                  and rows[0].get("landed") is True)
        kept = (r.rig.home / "voice" / "turns.jsonl").read_text(encoding="utf-8").splitlines()
        ctx.check(f"the host keeps the card, via host, by the peer, got {kept[-1:]}", len(kept) == 1
                  and json.loads(kept[-1]).get("via") == "host" and json.loads(kept[-1]).get("peer") == "bob@peer")
        audit = (r.rig.home / "host" / "audit.jsonl").read_text(encoding="utf-8")
        ctx.check("the pair key is in neither the audit nor the card", r.rig.rig.key.hex() not in audit
                  and r.rig.rig.key.hex() not in "".join(kept))


@test
def test_an_8_khz_utterance_is_resampled(ctx: Ctx):
    with DoorRig([text_step("Yes.")], transcripts=["is it on"]) as r:
        frames, err = _turn(r, wav(500, 8000))
        ctx.check(f"an HFP-rate WAV is heard, got {frames[:1]} {err!r}", not err and frames[0][1] == {"heard": "is it on"})
        rows = r.rig.rig.audit_rows(1, op="voice_turn")
        ctx.check(f"its seconds are the utterance's, got {rows}", rows and rows[0]["params"]["seconds"] == 0.5)
        pcm = b"\x00\x01" * 8000
        frames, err = _turn(r, pcm, "audio/pcm;rate=8000")
        ctx.check(f"raw PCM at 8 kHz too, got {frames[:1]} {err!r}", not err and frames and "heard" in frames[0][1])


@test
def test_each_refusal_is_one_line(ctx: Ctx):
    with DoorRig([text_step("x")], grants=()) as r:
        _f, err = _turn(r)
        ctx.check(f"no control grant: the grant command, got {err!r}", "holds no `control` grant" in err
                  and "halo host grant bob@peer control" in err)
    with DoorRig([text_step("x")], session=False) as r:
        _f, err = _turn(r)
        ctx.check(f"no session there: start halo there, got {err!r}", err == "no running halo session on pc-host: start "
                  "`halo` there (GET me lists the sessions)")
    with DoorRig([text_step("x")]) as r:
        _f, err = _turn(r, b"\x00\x00" * 16000 * 31, "audio/pcm;rate=16000")
        ctx.check(f"the 30 s budget, got {err!r}", err == "the utterance is 31.0 s: the voice door takes up to 30 s "
                  "(16 kHz PCM)")
        _f, err = _turn(r, b"OggS....", "audio/ogg")
        ctx.check(f"an audio shape it does not read, got {err!r}", err.startswith("Content-Type audio/ogg: send audio/pcm"))
        _f, err = _turn(r, session="nosuch")
        ctx.check(f"an unknown session, got {err!r}", err == "no running session 'nosuch' on pc-host")
        r.servers[:] = [s for s in r.servers if s.runtime != "voice-stt"]
        _f, err = _turn(r)
        ctx.check(f"no stt server there: the serve command, got {err!r}", err == "no stt server runs on pc-host: there, "
                  "halo local serve --stt faster-whisper:small.en")
        rows = r.rig.rig.audit_rows(4, op="voice_turn")
        ctx.check(f"each refusal is an audit row that did not land, got {[x.get('ok') for x in rows]}", len(rows) == 4
                  and not any(x.get("ok") or x.get("landed") for x in rows))
        ctx.check("no audio was made for a refusal", r.info["tts"]["n"] == 0)


@test
def test_get_me_lists_the_door(ctx: Ctx):
    from halo_harness.host import state as S
    with DoorRig([text_step("x")]) as r:
        v = r.client().me(fresh=True).get("voice") or {}
        ctx.check(f"the door and its grant, got {v.get('door')} {v.get('grant')}", v.get("door") == "POST /host/v1/voice/turn"
                  and v.get("grant") == "control" and v.get("max_s") == 30.0)
        ctx.check(f"the speech servers by model, got {v.get('stt')} {v.get('tts')}",
                  v.get("stt") == {"name": "stt", "model": "faster-whisper:small.en"}
                  and v.get("tts") == {"name": "tts", "model": "kokoro-82m"})
        rows = v.get("sessions") or []
        ctx.check(f"the session it reaches, without its endpoint or token, got {rows}", len(rows) == 1
                  and rows[0]["session_id"] == r.handle.session_id and set(rows[0]) == {"session_id", "title", "cwd", "kind"})
        got = S.server_rows("192.0.2.10", r.servers)
        ctx.check(f"the served rows: kind speech and the model, got {got}", [(x["kind"], x["runtime"], x.get("model"))
                  for x in got] == [("speech", "voice-stt", "faster-whisper:small.en"), ("speech", "voice-tts", "kokoro-82m")])
        joined = [x for x in r.rig.entry.get("servers") or [] if x.get("kind") == "speech"]
        ctx.check(f"the join carried them to the peer, got {joined}", [x["name"] for x in joined] == ["stt", "tts"])


@test
def test_the_turn_reads_each_delta_as_it_streams(ctx: Ctx):
    from halo_harness.events import Event
    from halo_harness.remote.feed import EventHub
    from halo_harness.voice.turn import KINDS
    hub = EventHub(flush_s=60.0)
    voice, other = hub.subscribe(kinds=KINDS), hub.subscribe()
    for t in ("The first ", "sentence. "):
        hub.publish(Event("text_delta", {"text": t}))
    got = [voice.get(0.05) for _ in range(2)]
    ctx.check(f"the voice turn's subscriber gets each delta at once, got {got}", [f and f["event"] for f in got] ==
              ["text_delta", "text_delta"] and got[1]["data"]["text"] == "sentence. ")
    ctx.check("every other subscriber still waits for the coalesced chunk", other.get(0.05) is None)
    hub.flush_now()
    chunk = other.get(0.05)
    ctx.check(f"then one text_chunk for it, none for the voice subscriber, got {chunk}", chunk and chunk["event"] ==
              "text_chunk" and chunk["data"]["text"] == "The first sentence. " and voice.get(0.05) is None)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
