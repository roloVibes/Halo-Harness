"""tests.test_voice_remote -- Halo 3.3.9.0 R3: the speech servers through the host (voice/remote.py; `voice.stt_server:
stt@pc`, `voice.tts_server: tts@pc`), on tests/helpers/voice_door_rig.DoorRig (host_act_rig.PeerRig with the fake speech
servers as the host's servers):

1. `stt@pc` resolves through the paired host (pc is the peer's Ollama host the halo host serves; `pc-host` its own
   name): a `halo-host:` url, the model from the served rows, the link's round trip, the line "stt on pc over the LAN
   (+N ms): <model>"; voice/ensure.ensure takes both, starts nothing, and hands the loop its `link`;
2. a voice loop on the peer hears with the host's stt server and speaks with its tts server (signed, one audit row
   each by op), and its latency card says "stt on pc over the LAN (+N ms)" with the `link` stage; `halo voice stats`
   counts it;
3. the one lines: no host of that name (the pair commands), no tts server there (the serve command, from `GET me`).
No model, no audio device, nothing leaves 127.0.0.1.
Run: python -m tests.test_voice_remote
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.turn_session import text_step  # noqa: E402
from tests.helpers.voice_door_rig import DoorRig  # noqa: E402

test, TESTS = new_registry()
REPLY = "It is on the host. The peer only listens."


def _far(stt: str = "stt@pc", tts: str = "tts@pc") -> None:
    from halo_harness import theme
    theme.set_config_value("voice.stt_server", stt)
    theme.set_config_value("voice.tts_server", tts)


@test
def test_stt_at_pc_resolves_through_the_host(ctx: Ctx):
    from halo_harness.voice import remote
    from halo_harness.voice.ensure import ensure
    with DoorRig([], session=False) as d:
        ctx.check(f"the default is local, got {remote.setting('stt')!r}", remote.setting("stt") == "local"
                  and remote.parse("local") is None and remote.parse("stt@pc") == "pc" and remote.parse("pc") == "pc")
        got = remote.resolve("stt", "stt@pc")
        ctx.check(f"stt@pc: a halo-host url, the model, the link, the line, got {got}", got.get("url") == "halo-host:pc#stt"
                  and got.get("model") == "faster-whisper:small.en" and isinstance(got.get("link_ms"), float)
                  and got["line"].startswith("stt on pc over the LAN (+") and got["line"].endswith(" ms): faster-whisper:small.en"))
        named = remote.resolve("tts", "tts@pc-host")
        ctx.check(f"the host's own name works too, got {named}", named.get("url") == "halo-host:pc-host#tts"
                  and named.get("model") == "kokoro-82m")
        _far()
        said: list = []
        urls, started, lines = ensure(d.rig.peer, say=said.append)
        ctx.check(f"ensure takes both from the host and starts nothing, got {urls} {started} {lines}", urls is not None
                  and urls["stt"] == "halo-host:pc#stt" and urls["tts"] == "halo-host:pc#tts" and started == [] and said == []
                  and [ln.split(" (+")[0] for ln in lines] == ["stt on pc over the LAN", "tts on pc over the LAN"])
        ctx.check(f"the loop's link: each kind's host and round trip, got {urls.get('link')}",
                  sorted(urls.get("link") or {}) == ["stt", "tts"] and urls["link"]["stt"]["host"] == "pc")


@test
def test_a_loop_on_the_peer_hears_and_speaks_through_the_host(ctx: Ctx):
    from halo_harness.voice.ensure import ensure
    from halo_harness.voice.latency import line, stats
    from tests.helpers.voice_rig import VoiceRig, talk
    with DoorRig([], transcripts=["where does it run"], session=False) as d:
        _far()
        urls, _started, _lines = ensure(d.rig.peer)
        with VoiceRig([text_step(REPLY)]) as v:
            loop = v.loop(stt_url=urls["stt"], tts_url=urls["tts"])
            loop.link = urls["link"]
            talk(v, loop)
            ok = v.wait(lambda: bool(loop.cards) and "last" in loop.cards[-1].t)
            heard = v.voice("heard")
            ctx.check(f"the host's stt heard it, the session got it, got {heard} {loop.errors}", ok and heard
                      and heard[0]["text"] == "where does it run" and not loop.errors)
            ctx.check(f"the host's tts spoke both sentences, played here, got {d.info['tts']['said']} {len(v.audio.captured)}",
                      d.info["tts"]["said"] == ["It is on the host.", "The peer only listens."] and len(v.audio.captured) == 2)
            card = loop.cards[-1]
            said = line(card)
            ctx.check(f"the card says the link, got {said!r}", "; stt on pc over the LAN (+" in said
                      and "tts on pc over the LAN (+" in said)
            row = card.row()
            ctx.check(f"the link stage beside the others, outside the total, got {row['stages']}",
                      isinstance(row["stages"].get("link"), int) and row["link"]["stt"]["host"] == "pc"
                      and row["total_ms"] == sum(row["stages"][k] for k in ("heard", "text", "token", "audio")))
            st = stats(v.state)
            ctx.check(f"halo voice stats counts the link stage, got {st['stages'].get('link')}",
                      st["turns"] == 1 and (st["stages"].get("link") or {}).get("n") == 1)
        stt_rows, tts_rows = d.rig.rig.audit_rows(1, op="voice_stt"), d.rig.rig.audit_rows(2, op="voice_tts")
        ctx.check(f"each request is one signed audit row by op, got {len(stt_rows)} {len(tts_rows)}",
                  len(stt_rows) == 1 and len(tts_rows) == 2 and all(r["ok"] for r in stt_rows + tts_rows))


@test
def test_the_one_lines(ctx: Ctx):
    from halo_harness.voice import remote
    from halo_harness.voice.ensure import ensure
    with DoorRig([], session=False, kinds=("stt",)) as d:
        got = remote.resolve("stt", "stt@mac")
        ctx.check(f"no host named mac: the pair commands, got {got}", got.get("error") == (
            "no paired halo host named mac: on mac, `halo host serve` and `halo host pair`; here, `halo host join <its "
            "address> <code>`"))
        got = remote.resolve("tts", "tts@pc")
        ctx.check(f"no tts server on pc: the serve command, got {got}", got.get("error") == (
            "pc lists no tts server: on pc, halo local serve --tts kokoro-82m (the halo host there shares it)"))
        _far()
        urls, started, lines = ensure(d.rig.peer)
        ctx.check(f"ensure says that line and starts nothing, got {urls} {started} {lines}", urls is None and started == []
                  and lines[-1].startswith("pc lists no tts server"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
