"""tests.test_studio_steward_chat -- Halo 3.3.7.0 R5, Local -> Steward's chat box in headless Chrome through
tests/helpers/studio_steward_chat.py (skipped without one), over tests/helpers/chat_rig.ChatHome: a fake model on
127.0.0.1:0 answering fixed JSON (a card read, then an answer); no provider request, no real model:

1. the chat names the steward's model; one question typed and asked;
2. the question, the tool line and the answer show, the answer with its cost chip ("local, N s");
3. the model picker lists the roster's candidates (the host's catalog), the smallest first.
Run: python -m tests.test_studio_steward_chat
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.driver_got import got as driver_got  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
_RUN: dict = {}


def _got(ctx: Ctx) -> dict:
    info = driver_got(ctx, "tests.helpers.studio_steward_chat", why="the chat checks need headless Chrome",
                      cache=_RUN, timeout=480)
    return info


@test
def test_one_question_one_answer(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the steward's model is named, got {got.get('model')!r}", "ol:steward-mock:1b@loop" in str(got.get("model")))
    ctx.check(f"the question shows, got {got.get('q')}", got.get("q") == ["what holds the card on loop?"])
    ctx.check(f"the tool line, got {got.get('tools')}", any(str(t).startswith("[card]") for t in got.get("tools") or []))
    ctx.check(f"the answer, got {got.get('answer')!r}", str(got.get("answer")).startswith("The card on loop is 24 GB"))
    ctx.check(f"two calls to the fake, got {got.get('calls')}", got.get("calls") == 2)


@test
def test_the_cost_chip_and_the_picker(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the cost chip, got {got.get('cost')!r}", str(got.get("cost")).startswith("local, ")
              and str(got.get("cost")).endswith(" s"))
    ctx.check(f"the picker lists the roster's candidates, the small one first, got {got.get('candidates')}",
              (got.get("candidates") or [None])[0] == "ol:qwen3.5:9b@loop")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
