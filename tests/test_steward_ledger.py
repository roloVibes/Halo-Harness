"""tests.test_steward_ledger -- Halo 3.3.4.0 R2: every call to a local model
server leaves one line in `<state>/ollama/traffic.jsonl`
(halo_harness/ollama_steward/ledger.py, ledger_call.py).

1. a fake Ollama answer through a real `halo -p` Session (tests/helpers/
   ollama_turns.py, the mock on 127.0.0.1:0) -> one turn line with every field;
2. Ollama's 500 "no user query found in messages" -> status 500, the error,
   trimmed, and the re-send that follows is retry 1;
3. an `ollama.hosts` entry with `dialect: openai` -> the line from `usage`
   and `finish_reason`.
tests/test_steward_ledger_writes.py has the in-process half (the observer's
statuses, rotation, the calibration line, the off switch).
Never a real server, never the real ~/.halo.
Run: python -m tests.test_steward_ledger
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials
ensure_default_provider_credentials()

from tests.helpers.fake_home import build_fake_home  # noqa: E402
from tests.helpers.mock_ollama import _finish_chat, send_json  # noqa: E402
from tests.helpers.ollama_turns import _mock_with, _run, _Script  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _lines(fh, kind=None) -> list:
    path = Path(fh["home"]) / ".halo" / "ollama" / "traffic.jsonl"
    if not path.exists():
        return []
    rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    return [r for r in rows if kind is None or r.get("kind") == kind]


def _answer(handler, body):
    _finish_chat(handler, [
        {"message": {"role": "assistant", "content": "the answer"}, "done": False},
        {"message": {"role": "assistant", "content": ""}, "done": True, "done_reason": "stop",
         "total_duration": 2_500_000_000, "load_duration": 1_200_000_000, "prompt_eval_count": 4000,
         "prompt_eval_duration": 800_000_000, "eval_count": 40, "eval_duration": 500_000_000}])


@test
def test_a_fake_ollama_answer_leaves_one_line_with_every_field(ctx: Ctx):
    from halo_harness.ollama_steward.ledger import FIELDS
    fh = build_fake_home()
    mock = _mock_with("l2-model", None)
    mock.start()
    try:
        mock.scenarios["l2-model"] = _answer
        result = _run(fh, mock, "hi", "l2-model")
        ctx.check(f"exit 0, got {result.returncode} {result.stderr[-400:]!r}", result.returncode == 0)
        turns = _lines(fh, "turn")
        ctx.check(f"one turn line, got {len(turns)} of {len(_lines(fh))}", len(turns) == 1)
        line = turns[0] if turns else {}
        ctx.check(f"every field is present, missing {[k for k in FIELDS if k not in line]}",
                  all(k in line for k in FIELDS))
        ctx.check(f"host = the entry's name and url, got {line.get('host')}",
                  line.get("host") == {"name": "default", "url": mock.base_url.rstrip("/")})
        ctx.check("model, ref, dialect, kind", line.get("model") == "l2-model" and line.get("ref") == "ol:l2-model"
                  and line.get("dialect") == "ollama" and line.get("kind") == "turn")
        ctx.check(f"the window sent and its source, got {line.get('num_ctx_sent')} {line.get('window_source')!r}",
                  isinstance(line.get("num_ctx_sent"), int) and line.get("num_ctx_sent") >= 2048
                  and isinstance(line.get("window_source"), str) and line["window_source"] != "trim resend")
        ctx.check(f"the estimate, got {line.get('estimate_tokens')}", isinstance(line.get("estimate_tokens"), int)
                  and line["estimate_tokens"] > 1024)
        ctx.check(f"the counts and done_reason, got {line.get('prompt_eval_count')}",
                  isinstance(line.get("prompt_eval_count"), int) and line["prompt_eval_count"] > 1000
                  and line.get("eval_count") == 40
                  and line.get("done_reason") == "stop")
        ctx.check(f"the durations in ms and the rate, got {line}", line.get("total_ms") == 2500.0
                  and line.get("load_ms") == 1200.0 and line.get("prompt_eval_ms") == 800.0
                  and line.get("eval_ms") == 500.0 and line.get("eval_tok_s") == 80.0)
        ctx.check("status 200, no error, not trimmed, retry 0", line.get("status") == 200 and line.get("error") is None
                  and line.get("trimmed") is False and line.get("retry") == 0)
        ctx.check("the session, the turn, the tools and images counts, from outside a fleet",
                  isinstance(line.get("session"), str) and line.get("turn") == 1
                  and isinstance(line.get("tools_count"), int) and line["tools_count"] > 0
                  and line.get("images") == 0 and line.get("from") is None)
    finally:
        mock.stop()


def _trimmed_500(handler, body):
    send_json(handler, 500, {"error": "no user query found in messages"})


@test
def test_a_500_no_user_query_is_status_500_with_the_error_and_the_resend_is_retry_1(ctx: Ctx):
    fh = build_fake_home()
    mock = _mock_with("l2-trim", None)
    mock.start()
    try:
        mock.scenarios["l2-trim"] = _Script([_trimmed_500, _answer])
        result = _run(fh, mock, "hi", "l2-trim")
        ctx.check(f"exit 0, got {result.returncode}", result.returncode == 0)
        turns = _lines(fh, "turn")
        ctx.check(f"two turn lines (the 500, the re-send), got {[t.get('status') for t in turns]}",
                  [t.get("status") for t in turns] == [500, 200])
        if len(turns) == 2:
            first, second = turns
            ctx.check(f"the 500 carries the server's line, got {first.get('error')!r}",
                      "no user query found in messages" in str(first.get("error")))
            ctx.check("the 500 is a trim", first.get("trimmed") is True and first.get("retry") == 0)
            ctx.check(f"the re-send is retry 1 with a larger window, got {second.get('retry')}",
                      second.get("retry") == 1 and second.get("num_ctx_sent") > first.get("num_ctx_sent"))
            ctx.check(f"the re-send's window source says so, got {second.get('window_source')!r}",
                      second.get("window_source") == "trim resend")
    finally:
        mock.stop()


@test
def test_the_openai_dialect_line_comes_from_usage_and_finish_reason(ctx: Ctx):
    from tests.helpers.mock_openai import MockUpstream as MockOpenAI
    from tests.test_ollama_openai_host import _run_cli, _write_hosts
    fh = build_fake_home()
    gateway = MockOpenAI(path_prefix="/v1").start()
    try:
        gateway.models_response = {"object": "list", "data": [{"id": "mock/usage-after-finish"}]}
        _write_hosts(fh, [{"name": "gw", "url": f"http://127.0.0.1:{gateway.port}", "dialect": "openai",
                           "default": True}])
        result = _run_cli(fh, "hi", model="ol:mock/usage-after-finish@gw")
        ctx.check(f"exit 0, got {result.returncode} {result.stderr[-300:]!r}", result.returncode == 0)
        turns = _lines(fh, "turn")
        line = turns[0] if turns else {}
        ctx.check(f"one turn line, got {len(turns)}", len(turns) == 1)
        ctx.check(f"dialect openai on host gw, got {line.get('dialect')} {line.get('host')}",
                  line.get("dialect") == "openai" and (line.get("host") or {}).get("name") == "gw")
        ctx.check(f"usage -> the counts, got {line.get('prompt_eval_count')} {line.get('eval_count')}",
                  line.get("prompt_eval_count") == 123 and line.get("eval_count") == 7)
        ctx.check(f"finish_reason -> done_reason, got {line.get('done_reason')!r}", line.get("done_reason") == "stop")
        ctx.check("status 200 and a wall time", line.get("status") == 200 and isinstance(line.get("total_ms"), float))
    finally:
        gateway.stop()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
