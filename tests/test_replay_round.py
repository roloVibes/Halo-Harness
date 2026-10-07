"""tests.test_replay_round -- Halo 2.0.6 round 4: session replay for
model swaps.

The v2.0.4 model review's item 3: replay a recorded session's turn
against a different model with the same tools and the same transcript
prefix, and compare the outcomes side by side. Pinned end-to-end against
the mock upstream: a real print-mode session is recorded (its log on
disk), then replayed against a second scripted scenario -- the ORIGINAL
file must stay byte-identical, the fork must carry the prefix, and the
report must name both outcomes and SAME/DIFFERENT honestly.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.mock_openai import MockUpstream, SCENARIOS, ScriptedTurns
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()

REPO_DIR = Path(__file__).resolve().parent.parent


def _cli_env(home: Path) -> dict:
    env = {k: v for k, v in os.environ.items()
           if k not in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "BRIDGE_ENV_FILE", "HALO_GOVERNOR")}
    env.update({"BRIDGE_TEST_HOME": str(home), "PYTHONPATH": str(REPO_DIR),
                "BRIDGE_TEST_NO_BACKGROUND_NET": "1"})
    return env


import contextlib


@contextlib.contextmanager
def _scoped_home(home: Path):
    """BRIDGE_TEST_HOME/BRIDGE_STATE_DIR scoped to the fake home for THIS
    process -- replay_session/fork/sessions_dir resolve state from the
    environment, and the test process (unlike the CLI child) starts
    unscoped."""
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
    os.environ["BRIDGE_TEST_HOME"] = str(home)
    os.environ.pop("BRIDGE_STATE_DIR", None)
    try:
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _record_session(mock, home: Path, cwd: Path) -> "tuple[str, Path]":
    """A real print-mode session with ONE real user turn, recorded on disk
    like any halo -p run. Returns (session_id, log_path)."""
    SCENARIOS["rep-src"] = ScriptedTurns([[
        {"choices": [{"index": 0, "delta": {"role": "assistant"}}]},
        {"choices": [{"index": 0, "delta": {"content": "the original answer, line one\nline two"}}]},
        {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
    ]])
    env = _cli_env(home)
    env.update({"BRIDGE_OPENROUTER_BASE_URL": mock.base_url, "OPENROUTER_API_KEY": "test-key"})
    r = subprocess.run([sys.executable, "-m", "halo_harness", "-p", "do the recorded task",
                        "--model", "or:mock/rep-src", "--cwd", str(cwd)],
                       env=env, cwd=str(REPO_DIR), capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-400:]
    # sessions live under the STATE dir (BRIDGE_TEST_HOME/.halo/sessions/
    # <project-slug>/), keyed by the project slug -- resolve the same way
    # the harness does, with the CHILD's home scoped in for the lookup
    from halo_harness.agent import sessions as agent_sessions
    with _scoped_home(home):
        sessions_dir = agent_sessions.sessions_dir(cwd)
    # sessions_dir already includes the project slug -- the logs are its
    # DIRECT children (<slug>/<id>.jsonl), not one level deeper
    logs = sorted(sessions_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime) \
        if sessions_dir.is_dir() else []
    assert logs, "no session log was recorded"
    return logs[-1].stem, logs[-1]


@test
def test_parse_turns_reads_the_real_log_shape(ctx: Ctx):
    from halo_harness.replay import parse_turns
    d = Path(tempfile.mkdtemp(prefix="replay-parse-"))
    log = d / "s.jsonl"
    nodes = [
        {"type": "meta", "model": "or:mock/x"},
        {"type": "user", "text": "first task"},
        {"type": "assistant", "content": [{"type": "text", "text": "answer one"}]},
        {"type": "usage", "usage": {"input_tokens": 10, "output_tokens": 4}, "cost_usd": 0.001},
        {"type": "user", "kind": "notice", "text": "a notice is not a turn"},
        {"type": "user", "text": "second task"},
        {"type": "assistant", "content": [{"type": "tool_use", "name": "Grep", "id": "t1", "input": {}}]},
        {"type": "assistant", "content": [{"type": "text", "text": "answer two"}]},
        {"type": "usage", "usage": {"input_tokens": 20, "output_tokens": 6}, "cost_usd": 0.002},
    ]
    log.write_text("\n".join(json.dumps(n) for n in nodes), encoding="utf-8")
    turns = parse_turns(log)
    ctx.check(f"two real turns (the notice is not one), got {[t.index for t in turns]}",
              [t.index for t in turns] == [1, 2])
    t1, t2 = turns
    ctx.check(f"turn 1 keeps its line offset, got {t1.node_line}", t1.node_line == 1)
    ctx.check(f"turn 1 aggregates usage, got {t1.tokens_in}/{t1.tokens_out} ${t1.cost_usd}",
              (t1.tokens_in, t1.tokens_out, t1.cost_usd) == (10, 4, 0.001))
    ctx.check(f"turn 2 collects tool names, got {t2.tool_names}", t2.tool_names == ["Grep"])
    ctx.check(f"turn 2 sums both usage nodes? no -- one node here, got ${t2.cost_usd}",
              t2.cost_usd == 0.002)


@test
def test_replay_swaps_the_model_and_diffs_the_outcome(ctx: Ctx):
    mock = MockUpstream().start()
    home = Path(tempfile.mkdtemp(prefix="replay-home-"))
    cwd = home / "project"
    cwd.mkdir(parents=True)
    try:
        session_id, log_path = _record_session(mock, home, cwd)
        original_bytes = log_path.read_bytes()

        # the replay target: a DIFFERENT model answering differently
        SCENARIOS["rep-dst"] = ScriptedTurns([[
            {"choices": [{"index": 0, "delta": {"role": "assistant"}}]},
            {"choices": [{"index": 0, "delta": {"content": "the swapped model's answer, entirely different"}}]},
            {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
        ]])
        from halo_harness.replay import replay_session
        with _scoped_home(home):
            report = replay_session(cwd, session_id, model="or:mock/rep-dst",
                                    extra_env={**_cli_env(home),
                                               "BRIDGE_OPENROUTER_BASE_URL": mock.base_url,
                                               "OPENROUTER_API_KEY": "test-key"})
        ctx.check(f"the replay ran to completion, got {report.get('error') or report.get('replay_exit')}",
                  report.get("ok") is True)
        ctx.check(f"turn 1 of 1 replayed, got {report.get('turn')}/{report.get('turns_total')}",
                  (report.get("turn"), report.get("turns_total")) == (1, 1))
        ctx.check("the DIFFERENT answer is reported as different",
                  report.get("same_answer") is False)
        ctx.check(f"the divergence line is named, got {report.get('first_divergence_line')}",
                  isinstance(report.get("first_divergence_line"), int))
        ctx.check(f"the original outcome is summarized, got {report['original']['assistant_chars']}",
                  report["original"]["assistant_chars"] > 0)
        ctx.check(f"the replay outcome is summarized, got {report['replay']['assistant_chars']}",
                  report["replay"]["assistant_chars"] > 0)
        ctx.check("the ORIGINAL session file is byte-identical after the replay",
                  log_path.read_bytes() == original_bytes)
        # the fork carries the prefix AND the replay's own answer
        fork_path = log_path.parent / f"{report['fork_id']}.jsonl"
        ctx.check("the fork exists beside the original", fork_path.is_file())
        if fork_path.is_file():
            from halo_harness.replay import parse_turns
            fork_turns = parse_turns(fork_path)
            ctx.check(f"the fork holds exactly the replay turn, got {[t.user_text[:20] for t in fork_turns]}",
                      len(fork_turns) == 1 and fork_turns[0].user_text == "do the recorded task")
            ctx.check("the fork's answer is the SWAPPED model's",
                      "swapped model" in fork_turns[0].assistant_text)
    finally:
        mock.stop()
        SCENARIOS.pop("rep-src", None)
        SCENARIOS.pop("rep-dst", None)


@test
def test_replay_same_model_same_script_reports_same(ctx: Ctx):
    mock = MockUpstream().start()
    home = Path(tempfile.mkdtemp(prefix="replay-same-"))
    cwd = home / "project"
    cwd.mkdir(parents=True)
    try:
        session_id, log_path = _record_session(mock, home, cwd)
        from halo_harness.replay import replay_session
        with _scoped_home(home):
            report = replay_session(cwd, session_id, model="or:mock/rep-src",
                                    extra_env={**_cli_env(home),
                                               "BRIDGE_OPENROUTER_BASE_URL": mock.base_url,
                                               "OPENROUTER_API_KEY": "test-key"})
        ctx.check(f"the replay ran, got {report.get('error')}", report.get("ok") is True)
        ctx.check(f"identical scripted answers report SAME, got same={report.get('same_answer')}",
                  report.get("same_answer") is True)
        ctx.check("no divergence line on SAME", report.get("first_divergence_line") is None)
    finally:
        mock.stop()
        SCENARIOS.pop("rep-src", None)


@test
def test_cli_json_output_and_bad_session(ctx: Ctx):
    from halo_harness.replay_cli import cmd_replay
    home = Path(tempfile.mkdtemp(prefix="replay-cli-"))
    cwd = home / "project"
    cwd.mkdir(parents=True)
    # no such session: a clean non-zero exit, never a traceback
    rc = cmd_replay(["no-such-session", "--model", "or:mock/x", "--cwd", str(cwd)])
    ctx.check(f"an unknown session exits 1, got {rc}", rc == 1)
    rc2 = cmd_replay(["no-such-session", "--model", "or:mock/x", "--cwd", str(cwd), "--json"])
    ctx.check(f"--json path exits 1 too, got {rc2}", rc2 == 1)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
