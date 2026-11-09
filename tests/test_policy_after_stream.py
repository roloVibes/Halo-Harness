"""tests.test_policy_after_stream -- an `after: true` policy covers the live output too (Halo 3.3.14.0 R2, REVIEW #11
PERMS-5; agent/policy_gate.progress, agent/loop.py's tool_progress). The `policy-fence` fixture's after copy (Write,
Edit, Read, Bash), its HALO_POLICY_TEST_REDACT / _DROP seams, a real Bash call that echoes a marker:

1. redact: no `tool_progress` frame carries the marker; the live output is the redacted text, the result the same;
2. drop: no `tool_progress` frame at all; the result is the pack's line;
3. with the policy not armed after the call, the live output is the command's own (the marker is there).
No model is called (a mock upstream answers the two steps).
Run: python -m tests.test_policy_after_stream"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.policy_session import Upstream, fenced_home, session_in  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.turn_session import text_step, tool_step  # noqa: E402

test, TESTS = new_registry()
WORD = "PINEAPPLE-7731"


def _turn(h, scenario: str) -> list:
    steps = [tool_step("Bash", {"command": f"echo the code is {WORD} && echo end"}), text_step("ok")]  # && runs solo
    with Upstream(scenario, steps) as up:
        s = session_in(h, up, mode="bypassPermissions")
        return list(s.turn("run it"))


def _progress(evs) -> list:
    return [str(e.data.get("text")) for e in evs if e.kind == "tool_progress"]


def _result(evs) -> str:
    return str(next((e.data.get("summary") or e.data.get("content") or e.data for e in evs if e.kind == "tool_result"), ""))


@test
def test_redact_reaches_the_live_output(ctx: Ctx):
    with fenced_home(after=True, HALO_POLICY_TEST_REDACT=WORD) as h:
        evs = _turn(h, "pas-redact")
    frames = _progress(evs)
    ctx.check(f"no live frame carries the marker, got {frames}", frames and not any(WORD in f for f in frames))
    ctx.check("the live output is the redacted text", any("[held]" in f for f in frames))


@test
def test_drop_sends_no_live_output(ctx: Ctx):
    with fenced_home(after=True, HALO_POLICY_TEST_DROP=1) as h:
        evs = _turn(h, "pas-drop")
    ctx.check(f"no live frame, got {_progress(evs)}", _progress(evs) == [])
    ctx.check(f"the result is the pack's line, got {_result(evs)!r}", "policy after: drop" in _result(evs)
              and WORD not in _result(evs))


@test
def test_without_an_after_policy_the_output_streams_as_it_is(ctx: Ctx):
    with fenced_home(after=False) as h:
        evs = _turn(h, "pas-plain")
    ctx.check(f"the command's own output, got {_progress(evs)}", any(WORD in f for f in _progress(evs)))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
