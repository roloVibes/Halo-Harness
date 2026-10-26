"""tests.test_ollama_trim_recovery -- Halo 3.2.3.0 R1: a real `halo -p`
Session (subprocess, `MockUpstream` standing in for the daemon -- never a
real Ollama, never a real model) against the two ways a request does not
fit the window Ollama uses:

- before the send: the request (this turn's tool output included) is
  larger than the largest window the call can get -> one line, compaction,
  then the smaller request (COMPACT path);
- after the send: a `prompt_eval_count` far under the estimate, a reply
  cut at the window's end (`done_reason: "length"`), or the 500
  "no user query found in messages" -> once per turn, raise the window and
  re-send (RAISE path) when there is room under the ceiling, else compact
  and re-send (COMPACT path); a second trim in the turn is one error line;
- any other Ollama 500 is sent three times at most, its raw text kept.
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


# ---- before the send: the COMPACT path ---------------------------------

@test
def test_tool_output_over_the_window_compacts_before_the_send(ctx: Ctx):
    base = _base_floor()
    trained = _pow2_above(base) + 4096
    fh = build_fake_home()
    big = fh["proj"] / "big.txt"
    big.write_text("".join(f"line {i:05d} BIGMARKER {'x' * 60}\n" for i in range(int(trained * 3.5 / 80) + 200)),
                   encoding="utf-8")
    mock = _mock_with("window-model", trained)
    mock.start()
    try:
        mock.scenarios["window-model"] = _Script([
            [{"message": {"role": "assistant", "content": "", "tool_calls": [
                {"function": {"name": "Read", "arguments": {"file_path": str(big)}}}]},
              "done": True, "done_reason": "stop", "prompt_eval_count": "real", "eval_count": 6}],
            _done("Done reading."),
        ])
        result = _run(fh, mock, "read big.txt", "window-model")
        out = result.stdout + result.stderr
        chats = _chats(mock)
        answering = [c for c in chats if not _is_compaction(c["body"])]
        ctx.check(f"exit 0, got {result.returncode} out={out[-600:]!r}", result.returncode == 0)
        ctx.check(f"the one line, got {out[-800:]!r}",
                  "is larger than window-model's window on default" in out and ": compacted" in out
                  and "of it tool output" in out)
        ctx.check(f"tool call, compaction, answer: got {_shape(chats)}", _shape(chats).startswith("ACA"))
        ctx.check("the request with the whole tool output was never sent to answer: compaction keeps the "
                  "turn in progress, so its tool output is cut on the wire to the window",
                  "characters of this tool output were cut" in json.dumps(answering[-1]["body"].get("messages"))
                  and "tokens of tool output cut to fit" in out)
        ctx.check(f"the answering request after compaction fits the window ({trained}), got "
                  f"{[_floor_of(c) for c in answering]}", _floor_of(answering[-1]) <= trained)
    finally:
        mock.stop()


# ---- after the send: a low prompt_eval_count --------------------------

@test
def test_trimmed_prompt_eval_count_resends_with_a_larger_window(ctx: Ctx):
    """RAISE path: room under the ceiling (the model is not in the
    catalog: the hard cap) -> the same request again with the window
    raised to the floor x 1.5, one line."""
    fh = build_fake_home()
    mock = _mock_with("trim-model", None)
    mock.real_prompt_counts = False
    mock.start()
    try:
        mock.scenarios["trim-model"] = _Script([_done("half an answer", 500), _done("the answer")])
        result = _run(fh, mock, "hi", "trim-model")
        out = result.stdout + result.stderr
        chats = _chats(mock)
        ctx.check(f"exit 0, got {result.returncode} out={out[-600:]!r}", result.returncode == 0)
        ctx.check(f"two sends, got {len(chats)}", len(chats) == 2)
        floor = _floor_of(chats[0])
        expected = max(_pow2_above(int(floor * 1.5 + 0.999)), 2 * _num_ctx(chats[0]))
        ctx.check(f"the window raised from {_num_ctx(chats[0])} to {expected}, got {_num_ctx(chats[1])}",
                  _num_ctx(chats[1]) == expected > _num_ctx(chats[0]))
        ctx.check(f"the line, got {out[-600:]!r}",
                  "default trimmed the request (500 of" in out and "re-sent with a" in out)
        ctx.check("the final answer printed", "the answer" in result.stdout)
    finally:
        mock.stop()


@test
def test_trimmed_with_no_room_compacts_and_resends(ctx: Ctx):
    """COMPACT path: the window is already at the trained context, so the
    trim is answered by compacting, then the request goes again."""
    trained = _no_room_trained()
    fh = build_fake_home()
    mock = _mock_with("tight-model", trained)
    mock.real_prompt_counts = False
    mock.start()
    try:
        mock.scenarios["tight-model"] = _Script([_done("half", 300), _done("the answer")])
        result = _run(fh, mock, "hi", "tight-model")
        out = result.stdout + result.stderr
        chats = _chats(mock)
        ctx.check(f"exit 0, got {result.returncode} out={out[-600:]!r}", result.returncode == 0)
        ctx.check(f"the window sent is the trained context, got {_num_ctx(chats[0])}", _num_ctx(chats[0]) == trained)
        ctx.check(f"the line, got {out[-600:]!r}", "default trimmed the request (300 of" in out
                  and "compacted and re-sent" in out)
        ctx.check(f"answer, compaction, answer: got {_shape(chats)}", _shape(chats).startswith("ACA"))
    finally:
        mock.stop()


# ---- after the send: a reply cut at the window's end -------------------

def _cut_at_window(handler, body):
    """`done_reason: "length"` with prompt + reply filling the window (not
    the request's own num_predict): Ollama answers 200 with a cut reply."""
    from tests.helpers.mock_ollama import _real_prompt_count
    num_ctx = ((body or {}).get("options") or {}).get("num_ctx") or 0
    seen = _real_prompt_count(body)
    start_ndjson(handler)
    write_ndjson_line(handler, {"message": {"role": "assistant", "content": "half a rep"}, "done": True,
                                "done_reason": "length", "prompt_eval_count": seen,
                                "eval_count": max(1, num_ctx - seen - 10)})
    end_ndjson(handler)


@test
def test_a_reply_cut_at_the_window_compacts_and_resends_once(ctx: Ctx):
    """COMPACT path: the window is already the trained context; the cut
    reply is never kept, the line says so, one re-send after compaction."""
    trained = _no_room_trained()
    fh = build_fake_home()
    mock = _mock_with("cut-model", trained)
    mock.start()
    try:
        mock.scenarios["cut-model"] = _Script([_cut_at_window, _done("the answer")])
        result = _run(fh, mock, "hi", "cut-model")
        out = result.stdout + result.stderr
        chats = _chats(mock)
        ctx.check(f"exit 0, got {result.returncode} out={out[-600:]!r}", result.returncode == 0)
        ctx.check(f"the line, got {out[-800:]!r}", "default cut the reply at the window (" in out
                  and "compacted and re-sent" in out)
        ctx.check(f"cut, compaction, answer: got {_shape(chats)}", _shape(chats).startswith("ACA"))
        ctx.check("the final answer printed", "the answer" in result.stdout)
    finally:
        mock.stop()


@test
def test_a_reply_cut_at_the_window_raises_the_window_when_there_is_room(ctx: Ctx):
    fh = build_fake_home()
    mock = _mock_with("cut-room", None)
    mock.start()
    try:
        mock.scenarios["cut-room"] = _Script([_cut_at_window, _done("the answer")])
        result = _run(fh, mock, "hi", "cut-room")
        out = result.stdout + result.stderr
        chats = _chats(mock)
        ctx.check(f"exit 0, got {result.returncode} out={out[-600:]!r}", result.returncode == 0)
        ctx.check(f"two sends, the second with twice the window, got {[_num_ctx(c) for c in chats]}",
                  len(chats) == 2 and _num_ctx(chats[1]) >= 2 * _num_ctx(chats[0]))
        ctx.check(f"the line, got {out[-800:]!r}", "cut the reply at the window (" in out and "re-sent with a" in out)
    finally:
        mock.stop()


@test
def test_the_reply_room_follows_num_predict(ctx: Ctx):
    """The floor holds prompt + the request's `num_predict`: the window
    sent is at least that sum."""
    fh = build_fake_home()
    mock = _mock_with("room-model", None)
    mock.start()
    try:
        mock.scenarios["room-model"] = _Script([_done("ok")])
        _run(fh, mock, "hi", "room-model")
        req = _chats(mock)[0]
        opts = req["body"]["options"]
        ctx.check(f"num_predict is sent, got {opts}", isinstance(opts.get("num_predict"), int) and opts["num_predict"] > 1024)
        ctx.check(f"num_ctx {opts['num_ctx']} >= prompt + num_predict ({_floor_of(req)})", opts["num_ctx"] >= _floor_of(req))
    finally:
        mock.stop()

if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
