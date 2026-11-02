"""tests.test_voice_findings -- Halo 3.3.9.0 R2: the steward's `voice-slow` (halo_harness/ollama_steward/
rules_voice_loop.py), read from the voice loop's cards in <state>/voice/turns.jsonl:

1. a stage over its share of the budget three turns running is one finding, keyed `voice|<stage>`, warn, with the
   stage, the three figures and the stated fix (text on the CPU -> --device cuda; token -> the bundle's reservation;
   audio -> tts-slow; heard -> silero-vad), never applied;
2. two slow turns, or three with a fast one between, are no finding; a budget of the bundle's own size is the one read;
3. `halo ollama steward findings` prints it and the Steward page (GET ollama/hosts: the host served here) carries it;
   `halo ollama explain voice-slow` answers from the knowledge row.
No model is called, nothing leaves the scratch home.
Run: python -m tests.test_voice_findings
"""
from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
_VARS = ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "OLLAMA_HOST", "BRIDGE_TEST_NO_BACKGROUND_NET")


@contextlib.contextmanager
def _home():
    from halo_harness.studio import ollama_hosts_view as V
    saved = {k: os.environ.get(k) for k in _VARS}
    root = Path(tempfile.mkdtemp(prefix="vl_find-")).resolve()
    state = root / ".halo"
    state.mkdir()
    os.environ.update(BRIDGE_TEST_HOME=str(root), BRIDGE_STATE_DIR=str(state), OLLAMA_HOST="http://127.0.0.1:9",
                      BRIDGE_TEST_NO_BACKGROUND_NET="1")
    old = dict(V.READERS)
    V.READERS.update({"card": lambda host: {}, "catalog": lambda host: {"models": []}})
    V.reset_cache()
    try:
        yield state
    finally:
        V.READERS.clear()
        V.READERS.update(old)
        V.reset_cache()
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _turns(state, *stage_rows, budget=1500):
    from halo_harness.voice.latency import Card, record
    for heard, text, token, audio in stage_rows:
        c = Card(budget_ms=budget)
        t = 0.0
        for stamp, ms in (("spoke", 0), ("heard", heard), ("text", text), ("token", token), ("audio", audio), ("last", 900)):
            t += ms / 1000.0
            c.mark(stamp, at=t)
        record(state, c)


def _found(state) -> list:
    from halo_harness.ollama_steward.rules import findings
    return [f for f in findings(state, cards={}, catalogs={}) if f["rule"] == "voice-slow"]


@test
def test_three_slow_turns_are_one_finding_with_the_fix(ctx: Ctx):
    with _home() as state:
        _turns(state, (200, 600, 300, 100), (210, 700, 310, 90), (190, 800, 290, 110))
        got = _found(state)
        ctx.check(f"one finding: the text stage, got {[f['key'] for f in got]}", [f["key"] for f in got] == ["voice|text"])
        f = got[0]
        ctx.check(f"warn, never applied, the figures, got {f['finding']!r}", f["severity"] == "warn" and f["applied"] is False
                  and "the voice loop's text stage ran over its 375 ms share of the 1,500 ms budget 3 turns running "
                      "(600, 700, 800 ms)" in f["finding"] and f["evidence"]["numbers"]["turns_ms"] == [600, 700, 800])
        ctx.check(f"stt on the CPU -> --device cuda, got {f['server_hint']}", f["server_hint"]["line"] ==
                  "halo local stop stt && halo local serve --stt faster-whisper:small.en --device cuda"
                  and "faster-whisper:small.en" in f["server_hint"]["cost"])
        _turns(state, (200, 300, 900, 100), (200, 300, 950, 100), (200, 300, 1000, 100))
        got = {f["stage"]: f for f in _found(state)}
        ctx.check(f"token: the bundle's reservation, got {sorted(got)}", sorted(got) == ["token"] and got["token"][
            "server_hint"]["line"] == "halo pack on voice-local" and "chat model is loading" in got["token"]["finding"])
        _turns(state, (400, 300, 300, 300), (400, 300, 300, 300), (400, 300, 300, 300))
        got = {f["stage"]: f["server_hint"]["line"] for f in _found(state)}
        ctx.check(f"heard and audio, got {got}", got == {"heard": "halo voice download silero-vad",
                                                         "audio": "halo ollama steward findings"})


@test
def test_no_finding_without_a_streak(ctx: Ctx):
    with _home() as state:
        _turns(state, (200, 900, 300, 100), (200, 900, 300, 100))
        ctx.check("two slow turns: none", _found(state) == [])
        _turns(state, (200, 100, 300, 100), (200, 900, 300, 100))
        ctx.check("a fast one inside the newest three: none", _found(state) == [])
        _turns(state, (200, 900, 300, 100), (200, 900, 300, 100), (200, 900, 300, 100), budget=4000)
        ctx.check("within a 4,000 ms budget's share (1,000 ms): none", _found(state) == [])


@test
def test_the_cli_the_steward_page_and_explain(ctx: Ctx):
    with _home() as state:
        _turns(state, (200, 600, 300, 100), (210, 700, 310, 90), (190, 800, 290, 110))
        from halo_harness.ollama_steward.cli_steward import cmd_ollama_steward
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cmd_ollama_steward(["findings"])
        ctx.check(f"halo ollama steward findings prints it, got {code} {out.getvalue()!r}", code == 0
                  and "voice-slow" in out.getvalue() and "voice loop" in out.getvalue())
        from halo_harness.studio.ollama_hosts_view import hosts_view
        view = hosts_view(state)
        rows = [f for h in view["hosts"] + view["local_servers"] for f in h.get("findings") or []
                if f["rule"] == "voice-slow"]
        ctx.check(f"the Steward page carries it once, on the host served here, got {[(f['host'], f['key']) for f in rows]}",
                  len(rows) == 1 and rows[0]["key"] == "voice|text" and rows[0]["host"] == view["hosts"][0]["name"])
        from halo_harness.ollama_steward.explain import cmd_ollama_explain
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cmd_ollama_explain(["voice-slow"])
        ctx.check(f"explain answers it, got {out.getvalue()[:200]!r}", code == 0 and "three turns running" in out.getvalue()
                  and "halo pack on voice-local" in out.getvalue())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
