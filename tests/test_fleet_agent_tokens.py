"""tests.test_fleet_agent_tokens -- each agent row's own tokens (Halo 3.1.5.0
R3, fleet/agent_tokens.py, for Session's Cost panel): the sum of the usage
lines on the agent's own transcript, counted as the session meter counts
them; a sub-agent's rolled-up total on its parent's log is skipped; the read
is incremental (only new lines; a half-written last line waits for its end;
a file that shrank is read again); `session_row` (fleet/local_view.py) puts
the figures on every agent row that has a transcript and none of its own (3.1.8.0 R6: a None
figure is none; a row carrying its meter's numbers from message_end is kept).

Run: python -m tests.test_fleet_agent_tokens
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once  # noqa: E402

ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _usage(tin: int, tout: int, **extra) -> str:
    return json.dumps({"type": "usage", "usage": {"input_tokens": tin, "output_tokens": tout, "cache_read_input_tokens": 999}, "cost_usd": 0.001, **extra}) + "\n"


class _Dir:
    def __enter__(self) -> Path:
        from halo_harness.fleet import agent_tokens
        agent_tokens.forget()
        self.root = Path(tempfile.mkdtemp(prefix="agent-tokens-"))
        return self.root

    def __exit__(self, *exc) -> bool:
        shutil.rmtree(self.root, ignore_errors=True)
        return False


@test
def test_the_usage_lines_sum_and_a_child_rollup_is_skipped(ctx: Ctx):
    from halo_harness.fleet.agent_tokens import totals
    with _Dir() as d:
        log = d / "main.jsonl"
        log.write_text(json.dumps({"type": "message", "role": "user", "content": "hi"}) + "\n" + _usage(1200, 80) + _usage(300, 20)
                       + _usage(5000, 900, agent_id="kid-1", model="or:mock/kid") + "not json\n", encoding="utf-8")
        ctx.check(f"its own two calls, not the child's rollup, got {totals(log)}", totals(log) == (1500, 100))
        ctx.check("no transcript: None", totals(None) is None and totals(d / "missing.jsonl") is None)


@test
def test_the_read_is_incremental_and_a_half_line_waits(ctx: Ctx):
    from halo_harness.fleet.agent_tokens import totals
    with _Dir() as d:
        log = d / "agent-x.jsonl"
        log.write_text(_usage(100, 10), encoding="utf-8")
        ctx.check(f"first read, got {totals(log)}", totals(log) == (100, 10))
        line = _usage(40, 4)
        with log.open("a", encoding="utf-8") as f:
            f.write(line[:20])
        ctx.check(f"a half-written line counts nothing yet, got {totals(log)}", totals(log) == (100, 10))
        with log.open("a", encoding="utf-8") as f:
            f.write(line[20:] + _usage(1, 1))
        ctx.check(f"its end lands: both new lines count once, got {totals(log)}", totals(log) == (141, 15))
        ctx.check(f"a read with nothing new keeps the figures, got {totals(log)}", totals(log) == (141, 15))
        log.write_text(_usage(7, 3), encoding="utf-8")
        ctx.check(f"a file that shrank is read again from the start, got {totals(log)}", totals(log) == (7, 3))


@test
def test_session_row_puts_them_on_the_agent_rows(ctx: Ctx):
    from halo_harness.fleet.local_view import session_row
    with _Dir() as d:
        (d / "main.jsonl").write_text(_usage(2000, 150), encoding="utf-8")
        (d / "kid.jsonl").write_text(_usage(600, 40) + _usage(400, 10), encoding="utf-8")
        agents = [{"agent_id": "main", "transcript": str(d / "main.jsonl")}, {"agent_id": "kid", "parent": "main", "transcript": str(d / "kid.jsonl")},
                  {"agent_id": "job-1", "kind": "job"}, {"agent_id": "own", "transcript": str(d / "kid.jsonl"), "tokens_in": 5, "tokens_out": 6}]
        row = session_row({"session_id": "s1"}, {"turn": 1}, agents)
        got = {a["agent_id"]: (a.get("tokens_in"), a.get("tokens_out")) for a in row["agents"]}
        ctx.check(f"each agent's own, a job without a transcript none, a row's own figures kept, got {got}",
                  got == {"main": (2000, 150), "kid": (1000, 50), "job-1": (None, None), "own": (5, 6)})
        # 3.1.8.0 R6: a live registry row has the keys from the start (None before its first model call)
        fresh = [{"agent_id": "early", "transcript": str(d / "kid.jsonl"), "tokens_in": None, "tokens_out": None},
                 {"agent_id": "live", "transcript": str(d / "kid.jsonl"), "tokens_in": 0, "tokens_out": 0}]
        row = session_row({"session_id": "s2"}, {"turn": 1}, fresh)
        got = {a["agent_id"]: (a.get("tokens_in"), a.get("tokens_out")) for a in row["agents"]}
        ctx.check(f"None is no figure (the transcript is read); a row carrying its meter's numbers is kept, got {got}",
                  got == {"early": (1000, 50), "live": (0, 0)})


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
