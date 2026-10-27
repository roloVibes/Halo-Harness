"""tests.test_ollama_window_steward -- Halo 3.3.4.0 R3: the two parked
3.2.3.0 bugs the steward's rules found, pinned through the loop rig (a real
`halo -p` Session in a subprocess against `tests/helpers/mock_ollama`,
never a real Ollama or model; tests/helpers/ollama_turns.py), and a
profile read before every call:

1. the compaction trigger per model, before the call: a tool result that
   takes the request past 80 % of the window compacts BEFORE the request
   goes out (it used to go out with the reply's room squeezed, and only the
   reply after it triggered compaction);
2. a reply that used up the room the window left it (`done_reason:
   "length"`, Ollama reading fewer tokens than Halo's estimate) is a cut:
   compacted and re-sent, the cut text never kept nor sent again;
3. a profile (`ollama.profiles["default|<model>"]`) sets the window sent,
   the reply's least room and keep_alive on the wire.
Run: python -m tests.test_ollama_window_steward
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
ensure_default_provider_credentials()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.fake_home import build_fake_home  # noqa: E402
from tests.helpers.mock_ollama import end_ndjson, start_ndjson, write_ndjson_line, _real_prompt_count  # noqa: E402
from tests.helpers.ollama_turns import (  # noqa: E402
    _base_floor, _chats, _done, _floor_of, _is_compaction, _mock_with, _no_room_trained, _num_ctx, _run, _Script,
    _shape,
)

test, TESTS = new_registry()


def _profile(fh, model: str, **fields) -> None:
    cfg = Path(fh["home"]) / ".halo" / "config.json"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    data = json.loads(cfg.read_text(encoding="utf-8")) if cfg.exists() else {}
    data.setdefault("ollama", {}).setdefault("profiles", {})[f"default|{model}"] = {**fields, "by": "user"}
    cfg.write_text(json.dumps(data), encoding="utf-8")


@test
def test_a_request_past_80_percent_compacts_before_it_is_sent(ctx: Ctx):
    base = _base_floor() - 16384  # Halo's own prompt part (the floor less its num_predict)
    trained = 32768
    tool_tokens = int(0.8 * trained) - base + 2500  # past 80 % of the window, still under it
    fh = build_fake_home()
    big = fh["proj"] / "big.txt"
    big.write_text("".join(f"row {i:05d} {'z' * 60}\n" for i in range(int(tool_tokens * 3.5 / 71))), encoding="utf-8")
    mock = _mock_with("gate-model", trained)
    mock.start()
    try:
        mock.scenarios["gate-model"] = _Script([
            [{"message": {"role": "assistant", "content": "", "tool_calls": [
                {"function": {"name": "Read", "arguments": {"file_path": str(big)}}}]},
              "done": True, "done_reason": "stop", "prompt_eval_count": "real", "eval_count": 6}],
            _done("read it."),
        ])
        result = _run(fh, mock, "read big.txt", "gate-model")
        out = result.stdout + result.stderr
        chats = _chats(mock)
        ctx.check(f"exit 0, got {result.returncode} {out[-500:]!r}", result.returncode == 0)
        ctx.check(f"the line, got {out[-900:]!r}", "% of gate-model's window on default" in out
                  and "compacted before the call" in out)
        ctx.check(f"tool call, compaction, answer: got {_shape(chats)}", _shape(chats).startswith("ACA"))
        answering = [c for c in chats if not _is_compaction(c["body"])]
        before = answering[1]["body"].get("messages") if len(answering) > 1 else []
        ctx.check("the answering request after the tool call went out after the compaction",
                  chats.index(answering[1]) > next(i for i, c in enumerate(chats) if _is_compaction(c["body"]))
                  and before)
    finally:
        mock.stop()


def _squeezed_cut(handler, body):
    """The reply used all the room the window left (`num_predict`), and the
    server read fewer tokens than Halo's chars / 3.5 (85 %): under the 97 %
    that `is_window_cut` asks for."""
    opts = (body or {}).get("options") or {}
    start_ndjson(handler)
    write_ndjson_line(handler, {"message": {"role": "assistant", "content": "CUTMARK half a reply"}, "done": True,
                                "done_reason": "length", "prompt_eval_count": int(_real_prompt_count(body) * 0.85),
                                "eval_count": int(opts.get("num_predict") or 1024)})
    end_ndjson(handler)


@test
def test_a_reply_cut_at_the_squeezed_room_is_never_kept_or_resent(ctx: Ctx):
    trained = _no_room_trained()
    fh = build_fake_home()
    mock = _mock_with("squeeze-model", trained)
    mock.real_prompt_counts = False
    mock.start()
    try:
        mock.scenarios["squeeze-model"] = _Script([_squeezed_cut, _done("the whole answer")])
        result = _run(fh, mock, "hi", "squeeze-model")
        out = result.stdout + result.stderr
        chats = _chats(mock)
        first = (chats[0]["body"].get("options") or {}) if chats else {}
        ctx.check(f"the window is the trained context and the reply's room was squeezed, got {first}",
                  first.get("num_ctx") == trained and first.get("num_predict", 10 ** 9) < 16384)
        ctx.check(f"the cut line, got {out[-800:]!r}", "cut the reply at the window" in out)
        ctx.check(f"cut, compaction, answer: got {_shape(chats)}", _shape(chats).startswith("ACA"))
        ctx.check("the cut text is in no later request", all("CUTMARK" not in json.dumps(c["body"].get("messages"))
                                                              for c in chats[1:]))
        ctx.check("the final answer printed, not the cut one", "the whole answer" in result.stdout
                  and "CUTMARK" not in result.stdout.split("the whole answer")[-1])
    finally:
        mock.stop()


@test
def test_a_profile_sets_the_window_the_reply_room_and_keep_alive(ctx: Ctx):
    fh = build_fake_home()
    _profile(fh, "prof-model", num_ctx=49152, num_predict=6000, keep_alive="10m")
    mock = _mock_with("prof-model", 131072)
    mock.start()
    try:
        mock.scenarios["prof-model"] = _Script([_done("ok")])
        result = _run(fh, mock, "hi", "prof-model")
        req = _chats(mock)[0]
        opts = req["body"].get("options") or {}
        ctx.check(f"exit 0, got {result.returncode}", result.returncode == 0)
        ctx.check(f"the profile's window is sent, got {opts.get('num_ctx')}", opts.get("num_ctx") == 49152)
        ctx.check(f"keep_alive from the profile, got {req['body'].get('keep_alive')}", req["body"].get("keep_alive") == "10m")
        ctx.check(f"the reply keeps at least 6,000, got {opts.get('num_predict')}", (opts.get("num_predict") or 0) >= 6000)
        ctx.check("the request fits the window", _floor_of(req) <= 49152)
    finally:
        mock.stop()
    fh = build_fake_home()
    _profile(fh, "small-model", num_ctx=65536)
    mock = _mock_with("small-model", 16384)
    mock.start()
    try:
        mock.scenarios["small-model"] = _Script([_done("ok")])
        _run(fh, mock, "hi", "small-model")
        got = _num_ctx(_chats(mock)[0])
        ctx.check(f"a profile window is held under the trained context (16,384), got {got}", got == 16384)
    finally:
        mock.stop()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
