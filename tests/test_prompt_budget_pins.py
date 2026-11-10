"""tests.test_prompt_budget_pins -- Halo 3.3.16.1 "the local prompt diet": a budget that cannot be crossed
silently. The first turn Halo would send (agent/prompt_measure.first_turn: the system prompt and snapshots
of a fake home with a 250-line MEMORY.md and topic files, the built-in tools, a plain "hi"), measured for
five cases on Windows and on Linux, each pinned as an upper bound:

    an unknown remote model (the 32,768 default), a 16,384 window, 49,152, 65,536 (lean), a 200k cloud model

The unknown remote case must leave prompt + the reply's room at or under 26,000 of 32,768 and go out at
32,768 on both platforms (3.3.16.0 sent 16,970 + 16,384 and doubled the window to 65,536). Never a server,
never a model call. When one fails: a new tool or new prompt text pushed the first turn past its bound.
Run: python -m tests.test_prompt_budget_pins
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("BRIDGE_TEST_HOME", tempfile.mkdtemp(prefix="pb_pins-"))
os.environ.setdefault("BRIDGE_TEST_NO_BACKGROUND_NET", "1")

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()

# (label, model ref, window, prompt bound, tool block bound, sent window)
CASES = (("an unknown remote model", "ol:room-model", 32768, 9000, 4500, 32768),
         ("a 16,384 window", "ol:tiny:3b@lan", 16384, 7000, 2200, 16384),
         ("a 49,152 window", "ol:qwen3-coder:30b@lan", 49152, 9000, 4500, 49152),
         ("a 65,536 window (lean)", "ol:qwen3-coder:30b@lan", 65536, 9000, None, 65536),
         ("a 200k cloud model", "ant:claude-opus-5-5", 200000, 18000, None, 200000))
UNKNOWN_TOTAL = 26000
SYSTEM_LEAN = 4000
_HOME: dict = {}


def why(what: str, bound: int) -> str:
    return (f"a new tool or prompt text pushed {what} past {bound:,}: give it a lean description "
            f"(tools/lean_descriptions.py), defer it, or raise this bound on purpose and say why in the CHANGELOG")


def _measure(ref: str, window: int, platform: str) -> dict:
    from tests.helpers.fake_home import build_fake_home
    from halo_harness.agent.prompt_measure import first_turn
    if "fh" not in _HOME:
        _HOME["fh"] = build_fake_home()
        os.environ["BRIDGE_TEST_HOME"] = str(_HOME["fh"]["home"])
    return first_turn(ref, window=window, platform=platform, cwd=_HOME["fh"]["proj"])


def _pins(ctx: Ctx, platform: str) -> None:
    for label, ref, window, prompt_max, tools_max, sent in CASES:
        m = _measure(ref, window, platform)
        tools = sum(r["tokens"] for r in m["tools"] if r["offered"])
        ctx.check(f"{platform}, {label}: the first turn is {m['prompt']:,} tokens -- " + why("the first turn", prompt_max),
                  m["prompt"] <= prompt_max)
        if tools_max is not None:
            ctx.check(f"{platform}, {label}: the tool block is {tools:,} tokens -- " + why("the lean tool block", tools_max),
                      tools <= tools_max)
        ctx.check(f"{platform}, {label}: sent at {m['sent_window']} (want {sent:,}) -- the prompt plus the reply's room "
                  f"({m['total']:,}) no longer fits the window it starts from", m["sent_window"] == sent)
        if window < 65536:
            ctx.check(f"{platform}, {label}: lean, got {m['lean']}", m["lean"] is True)


@test
def test_the_five_cases_on_windows(ctx: Ctx):
    _pins(ctx, "win32")


@test
def test_the_five_cases_on_linux(ctx: Ctx):
    _pins(ctx, "linux")


@test
def test_an_unknown_remote_model_stays_well_inside_32768(ctx: Ctx):
    for platform in ("win32", "linux"):
        m = _measure("ol:room-model", 32768, platform)
        ctx.check(f"{platform}: prompt + the reply's room {m['total']:,} -- " + why("prompt + room", UNKNOWN_TOTAL),
                  m["total"] <= UNKNOWN_TOTAL)
        ctx.check(f"{platform}: the window sent is 32,768, got {m['sent_window']}", m["sent_window"] == 32768)
        ctx.check(f"{platform}: the reply's room is a quarter of it, got {m['reply_room']}", m["reply_room"] == 8192)
        ctx.check(f"{platform}: the system message (memory in it) is {m['system_message']:,} -- "
                  + why("the lean system message", SYSTEM_LEAN), m["system_message"] <= SYSTEM_LEAN)


@test
def test_the_cloud_case_is_not_lean_and_carries_every_tool(ctx: Ctx):
    m = _measure("ant:claude-opus-5-5", 200000, "linux")
    ctx.check(f"a 200k cloud model is not lean, got {m['lean']}", m["lean"] is False)
    ctx.check(f"every tool offered, got {[r['name'] for r in m['tools'] if not r['offered']]}",
              all(r["offered"] for r in m["tools"]))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
