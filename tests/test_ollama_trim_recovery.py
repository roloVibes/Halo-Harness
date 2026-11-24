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
    # a window one step above Halo's own prompt (3.3.16.0 R3: the pow2 rounding jumped to 69632 once the prompt passed
    # 32768 -- one more tool did it -- and then the Read's capped output no longer overflowed the window)
    trained = -(-(base + 4096) // 4096) * 4096
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
def test_trimmed_with_no_room_a_first_answer_stands_and_a_later_request_compacts(ctx: Ctx):
    """COMPACT path: the window is already at the trained context. 3.6.0.20 E8: a FIRST request has nothing to compact
    (`halo -p "hi"` is one): its answer stands, one line says so, one call. A request with an earlier answer is
    compacted and re-sent, as before: trim_recovery's own test below, and end to end tests/test_ollama_window_fixes.py
    `test_a_later_request_trimmed_cut_or_refused_after_the_send_is_still_compacted`."""
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
        ctx.check(f"one line, the answer stands, got {out[-600:]!r}",
                  "default read 300 of" in out and "tokens of the first request (its window is" in out
                  and "nothing earlier to compact, the answer stands" in out and "compacted" not in out)
        ctx.check(f"one call, got {_shape(chats)}", _shape(chats) == "A")
        ctx.check("its answer printed", "half" in result.stdout)
    finally:
        mock.stop()


@test
def test_trim_recovery_compacts_a_later_request_and_lets_a_first_one_stand(ctx: Ctx):
    """3.6.0.20 E8, the decision itself: at a window that cannot grow, a request with an earlier answer is compacted
    and re-sent (today's line); a first request's answer stands (one line); a first request with no answer (the 500)
    stops; a window that can grow is raised first either way."""
    from types import SimpleNamespace as NS
    from halo_harness.agent.ollama_window import trim_recovery
    from halo_harness.providers.ollama_prompt import WindowChoice

    def decide(first: bool, *, ceiling=8192, **kw):
        s = NS(_ollama_window_state={"factor": {}, "trim_turn": None, "cap": {}, "last": {
            "estimate": 6000, "reserve": 1024, "host_name": "gpu-box", "host_url": "http://gpu-box:11434",
            "model": "example-model:30b", "first": first, "choice": WindowChoice(8192, "x", 6000, ceiling, True)}})
        return trim_recovery(s, 1, 3000, overflow_handled=False, current_num_ctx=8192, **kw)
    kind, _n, line = decide(False)
    ctx.check(f"a later request: compact, got {kind} {line!r}", kind == "compact" and "compacted and re-sent" in line)
    kind, _n, line = decide(True)
    ctx.check(f"a first request: stands, got {kind} {line!r}", kind == "stands" and line ==
              "gpu-box read 3k of 5k tokens of the first request (its window is 8k): nothing earlier to compact, "
              "the answer stands")
    kind, _n, line = decide(True, cut_at=8192)
    ctx.check(f"a first request's cut reply: stands, got {kind} {line!r}", kind == "stands" and line ==
              "gpu-box cut the reply at the window (3k of 8k tokens): nothing earlier to compact, the reply stands as "
              "it is")
    kind, _n, _line = decide(True, answered=False)
    ctx.check(f"a first request with no answer (the 500): error, got {kind}", kind == "error")
    kind, n, _line = decide(True, ceiling=32768)
    ctx.check(f"a trimmed first request with room to grow: raised first, got {kind} {n}",
              kind == "resend" and n and n > 8192)
    kind, n, _line = decide(True, ceiling=32768, cut_at=8192)
    ctx.check(f"a first request's cut reply with room to grow: stands (never thrown away for a raise), got {kind} {n}",
              kind == "stands" and n is None)
    kind, n, _line = decide(False, ceiling=32768, cut_at=8192)
    ctx.check(f"a later request's cut reply with room to grow: raised, got {kind} {n}",
              kind == "resend" and n and n > 8192)


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
def test_a_reply_cut_at_the_window_stands_first_and_a_later_one_compacts_once(ctx: Ctx):
    """COMPACT path: the window is already the trained context. 3.6.0.20 E8: a FIRST request's cut reply stands
    (nothing earlier to compact), one line, one call; a later request's cut is compacted and re-sent once, as
    before (trim_recovery's own test above; end to end in tests/test_ollama_window_fixes.py)."""
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
        ctx.check(f"one line, the reply stands, got {out[-800:]!r}", "default cut the reply at the window (" in out
                  and "tokens): nothing earlier to compact, the reply stands as it is" in out
                  and "compacted" not in out)
        ctx.check(f"one call, got {_shape(chats)}", _shape(chats) == "A")
        ctx.check("the cut reply printed", "half a rep" in result.stdout)
    finally:
        mock.stop()


@test
def test_a_reply_cut_at_the_window_with_room_stands_first_and_raises_the_window_later(ctx: Ctx):
    """3.6.0.20 E8 after the check (rewritten to the truth): a FIRST request's reply cut at the window stands even
    when the window could grow (a re-send would throw the reply away; it was: re-sent at twice the window), one line,
    one call. A later request's cut is re-sent at a larger window, as before (trim_recovery's own test above)."""
    fh = build_fake_home()
    mock = _mock_with("cut-room", None)
    mock.start()
    try:
        mock.scenarios["cut-room"] = _Script([_cut_at_window, _done("the answer")])
        result = _run(fh, mock, "hi", "cut-room")
        out = result.stdout + result.stderr
        chats = _chats(mock)
        ctx.check(f"exit 0, got {result.returncode} out={out[-600:]!r}", result.returncode == 0)
        ctx.check(f"one send, got {[_num_ctx(c) for c in chats]}", len(chats) == 1)
        ctx.check(f"the line, got {out[-800:]!r}", "default cut the reply at the window (" in out
                  and "tokens): nothing earlier to compact, the reply stands as it is" in out and "re-sent" not in out)
        ctx.check("the cut reply printed", "half a rep" in result.stdout)
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
        floor = _floor_of(req)
        ctx.check(f"num_ctx {opts['num_ctx']} >= prompt + num_predict ({floor})", opts["num_ctx"] >= floor)
    finally:
        mock.stop()

if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
