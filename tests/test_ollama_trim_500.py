"""tests.test_ollama_trim_500 -- Halo 3.2.3.0 R1: Ollama's 500 "no user
query found in messages" (kind `prompt_trimmed`: raise the window and
re-send, else compact and re-send, once per turn; a second one is one
error line) and any other Ollama 500 (three sends at most, its raw text
kept) -- a real `halo -p` Session against the mock (tests/helpers/
ollama_turns.py), never a real Ollama.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials
ensure_default_provider_credentials()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.fake_home import build_fake_home
from tests.helpers.mock_ollama import _finish_chat, send_json, start_ndjson, write_ndjson_line, end_ndjson
from tests.helpers.ollama_turns import (
    _base_floor, _chats, _no_room_trained, _done, _floor_of, _is_compaction, _mock_with, _num_ctx, _pow2_above, _run, _Script, _shape,
)

test, TESTS = new_registry()


# ---- the 500 "no user query found in messages" ----------------------

def _trimmed_500(handler, body):
    send_json(handler, 500, {"error": "no user query found in messages"})


@test
def test_ollama_500_no_user_query_raises_once_then_one_error_line(ctx: Ctx):
    """RAISE path, then a second trim in the same turn: one error line
    with the raw text -- two sends, never six."""
    fh = build_fake_home()
    mock = _mock_with("q-model", None)
    mock.start()
    try:
        mock.scenarios["q-model"] = _Script([_trimmed_500])
        result = _run(fh, mock, "hi", "q-model")
        out = result.stdout + result.stderr
        chats = _chats(mock)
        ctx.check(f"exit != 0, got {result.returncode}", result.returncode != 0)
        ctx.check(f"two sends (the raise is the retry), got {len(chats)}", len(chats) == 2)
        ctx.check("the second send has a larger window", _num_ctx(chats[1]) > _num_ctx(chats[0]))
        ctx.check(f"the raise line, got {out[-800:]!r}", "default trimmed the request (" in out
                  and "re-sent with a" in out)
        ctx.check(f"one error line with the raw text, got {out[-800:]!r}",
                  out.count("error: default trimmed the request again") == 1
                  and "(Ollama: no user query found in messages)" in out)
    finally:
        mock.stop()


@test
def test_ollama_500_no_user_query_compacts_when_the_window_cannot_grow(ctx: Ctx):
    trained = _no_room_trained()
    fh = build_fake_home()
    mock = _mock_with("q-tight", trained)
    mock.start()
    try:
        mock.scenarios["q-tight"] = _Script([_trimmed_500, _done("the answer")])
        result = _run(fh, mock, "hi", "q-tight")
        out = result.stdout + result.stderr
        chats = _chats(mock)
        ctx.check(f"exit 0, got {result.returncode} out={out[-600:]!r}", result.returncode == 0)
        ctx.check(f"500, compaction, answer: got {_shape(chats)}", _shape(chats).startswith("ACA"))
        ctx.check(f"the line, got {out[-600:]!r}", "compacted and re-sent" in out)
    finally:
        mock.stop()


@test
def test_other_ollama_500_is_sent_three_times_with_its_raw_text(ctx: Ctx):
    fh = build_fake_home()
    mock = _mock_with("crash-model", None)
    mock.start()
    try:
        mock.scenarios["crash-model"] = lambda h, b: send_json(h, 500, {"error": "llama runner process has terminated"})
        result = _run(fh, mock, "hi", "crash-model")
        out = result.stdout + result.stderr
        chats = _chats(mock)
        ctx.check(f"three sends, never six, got {len(chats)}", len(chats) == 3)
        ctx.check(f"the raw text is in the error line, got {out[-600:]!r}",
                  "llama runner process has terminated" in out and "Ollama had an internal error" in out)
    finally:
        mock.stop()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
