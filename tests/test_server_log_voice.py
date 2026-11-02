"""tests.test_server_log_voice -- Halo 3.3.9.0 R1: the steward sees a speech server like a llama-server
(ollama_steward/servers_hf.py's runtimes, server_rules_hf.py -> server_log_voice.py, rules_voice.py), from the fixture
logs of tests/helpers/servers_seed_voice.py:

1. the roster names `stt` and `tts` with their runtimes (voice-stt / voice-tts), Halo's log and launch on each;
2. the log's lines are events under the server's name: the load (device, the GPU's free MiB), a timing per request,
   the 500; the model from the start line, not `-m halo_harness...`;
3. the findings, keyed `stt|<model>` / `tts|<model>`: stt-slow (1.4x realtime median -> --device cuda, the GPU had the
   room), voice-cpu (info), voice-load-failed (the CUDA library -> --device cpu), tts-slow (first audio 620 ms ->
   no smaller built TTS), each with server, runtime and applied false; `halo ollama steward findings` prints them;
4. the extra's failure line -> voice-load-failed whose fix is the install line;
5. the line formats round-trip (voice/log_lines.py writes what server_log_voice reads; the brief's 13.5x example).
Fixture logs only: no server runs, nothing is sent.
Run: python -m tests.test_server_log_voice
"""
from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
ensure_default_provider_credentials()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.servers_seed import Home  # noqa: E402

test, TESTS = new_registry()
TURBO = "faster-whisper:large-v3-turbo"


def _home():
    return Home(llama=False, lms=False, mlx=False, voice=True)


def _scan(h):
    from halo_harness.ollama_steward.server_log_hf import scan
    out = {}
    for name in ("stt", "tts"):
        out[name] = scan(h.state, h.server(name), from_start=True)[0]
    return out


def _findings(h):
    from halo_harness.ollama_steward.rules import findings
    return findings(h.state, cards={}, catalogs={}, hosts=[])


@test
def test_the_roster_names_the_speech_servers(ctx: Ctx):
    from halo_harness.ollama_steward.servers_hf import RUNTIMES, roster, runtime_word
    with _home() as h:
        rows = {s.name: s for s in roster(h.state)}
        ctx.check(f"stt and tts, got {sorted(rows)}", sorted(rows) == ["stt", "tts"])
        ctx.check("their runtimes", rows["stt"].runtime == "voice-stt" and rows["tts"].runtime == "voice-tts")
        ctx.check("Halo's log and launch on each", rows["stt"].log == str(h.stt_log) and "--kind stt" in (rows["stt"].launch or ""))
        ctx.check("the runtime words", "voice-stt" in RUNTIMES and runtime_word("voice_tts") == "voice-tts")


@test
def test_the_lines_are_events_under_the_servers_name(ctx: Ctx):
    with _home() as h:
        got = _scan(h)
        stt = [e for e in got["stt"] if e["kind"] != "other-error" or "exited" not in e["say"]]
        kinds = [e["kind"] for e in stt]
        ctx.check(f"a load, three timings, a 500, got {kinds}", kinds == ["load-result", "timing", "timing", "timing",
                                                                           "http-500"])
        load = stt[0]
        ctx.check(f"the load: the model from --model, cpu, the GPU's free MiB, got {load}", load["model"] == TURBO
                  and load["data"]["device"] == "cpu" and load["data"]["gpu_free_mib"] == 22000 and load["host"] == "stt")
        ctx.check("each timing has its realtime factor and the model", all(e["model"] == TURBO and e["data"]["voice"] == "stt"
                                                                           and e["data"]["rtf"] < 2 for e in stt[1:4]))
        tts = [e["kind"] for e in got["tts"] if "exited" not in e["say"]]
        ctx.check(f"tts: the failed load, the load, two timings, got {tts}", tts == ["load-failed", "load-result", "timing",
                                                                                    "timing"])


@test
def test_the_findings_and_their_fix_lines(ctx: Ctx):
    with _home() as h:
        _scan(h)
        found = {f["rule"]: f for f in _findings(h)}
        ctx.check(f"the four, got {sorted(found)}", {"stt-slow", "voice-cpu", "voice-load-failed", "tts-slow"} <= set(found))
        slow = found["stt-slow"]
        ctx.check(f"stt-slow: keyed by the server, warn, got {slow['key']} {slow['severity']}", slow["key"] == f"stt|{TURBO}"
                  and slow["severity"] == "warn" and slow["server"] == "stt" and slow["runtime"] == "voice-stt")
        ctx.check(f"stt-slow: 1.4x and --device cuda, got {slow['finding']!r}", "1.4x realtime" in slow["finding"]
                  and slow["server_hint"]["line"] == f"halo local stop stt && halo local serve --stt {TURBO} --device cuda")
        cpu = found["voice-cpu"]
        ctx.check(f"voice-cpu: info, the free MiB, never applied, got {cpu['finding']!r}", cpu["severity"] == "info"
                  and "22,000 MiB free" in cpu["finding"] and cpu["applied"] is False)
        bad = found["voice-load-failed"]
        ctx.check(f"voice-load-failed: tts, error, --device cpu, got {bad['key']} {bad['server_hint']}", bad["key"] ==
                  "tts|kokoro-82m" and bad["severity"] == "error" and "--device cpu" in bad["server_hint"]["line"])
        tslow = found["tts-slow"]
        ctx.check(f"tts-slow: 580 ms median, got {tslow['finding']!r}", "after 580 ms" in tslow["finding"]
                  and tslow["evidence"]["numbers"]["first_ms"] == 580)
        from halo_harness.ollama_steward.cli_steward import cmd_ollama_steward
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cmd_ollama_steward(["findings"])
        ctx.check(f"halo ollama steward findings prints them, got {code}", code == 0 and "stt-slow" in out.getvalue()
                  and f"stt {TURBO}" in out.getvalue())


@test
def test_the_extra_line_is_the_install_fix(ctx: Ctx):
    from halo_harness.ollama_steward.server_log_voice import classify
    from halo_harness.ollama_steward.rules_voice import load_failed
    from halo_harness.voice import INSTALL_LINE
    from tests.helpers.servers_seed_voice import EXTRA_LINE
    ev = classify(EXTRA_LINE, at=1.0, runtime="voice-stt")
    ctx.check(f"load-failed, extra, got {ev}", ev["kind"] == "load-failed" and ev["data"]["extra"] is True)
    g = {"host": "stt", "model": "faster-whisper:small.en", "key": "stt|faster-whisper:small.en", "events": [ev],
         "runtime": "voice-stt", "server": "stt"}
    f = load_failed(g, "stt")[0]
    ctx.check(f"the install line is the fix, got {f['server_hint']}", f["server_hint"]["line"] == INSTALL_LINE)
    ctx.check("a line that is not the server's is nothing", classify("some other text", runtime="voice-stt") is None)


@test
def test_the_formats_round_trip(ctx: Ctx):
    from halo_harness.voice import log_lines as L
    ctx.check("the brief's stt line", L.stt(4.2, 0.31, "cpu") == "voice stt: audio 4.2 s -> text in 0.31 s (13.5x realtime) on cpu")
    ctx.check("the brief's tts line", L.tts(84, 3.9, 92, 0.4, "cuda") == ("voice tts: text 84 chars -> audio 3.9 s, first "
                                                                         "audio 92 ms, in 0.40 s on cuda"))
    for line in (L.stt(4.2, 0.31, "cpu"), L.tts(84, 3.9, 92, 0.4, "cuda"), L.loaded("stt", "kokoro-82m", "cpu", "int8", 1.0, 500),
                 L.load_failed("tts", "kokoro-82m", "cuda", "x"), L.request_failed("POST", "/v1/audio/speech", 500, "y"),
                 L.listening("http://127.0.0.1:1", "stt", "faster-whisper:base.en")):
        ctx.check(f"parsed back: {line}", L.parse(line) is not None)
    ctx.check("rtf", L.parse(L.stt(4.2, 0.31, "cpu"))["rtf"] == 13.5)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
