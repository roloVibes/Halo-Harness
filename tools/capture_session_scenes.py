"""tools/capture_session_scenes.py -- the scripted activity
tools/capture_session_anim.py films (Halo 3.1.5.0 R3): what each agent of
the fleet rig (tests/helpers/studio_session_rig.py, plus the extra agents of
tests/helpers/studio_live_rig.py) says, runs and hands back, second by
second, as the feed frames a live session sends. A scene is a list of
(seconds, step) pairs; `play` runs it on a thread against the clock so the
capture loop can take its frames meanwhile. No model is called.
"""
from __future__ import annotations

import threading
import time


def session_scene(lv) -> list:
    """Session: six agents at work, a thought, a spawn and its task, an ask, two finishing (one hands back), the spend
    and the context rising."""
    def cost(usd: float, ctx: int):
        return lambda: lv.refresh(cost_usd=usd, context_tokens=ctx, context_limit=128_000, turns=3 + int(usd * 100))
    return [
        (0.0, cost(0.012, 38_000)),
        (0.02, lambda: lv.think("implementer", "s-th1", "The coupon is taxed because the discount runs after the tax line; ")),  # 3.3.16.2: a THINK row
        (0.06, lambda: lv.think("implementer", "s-th1", "moving it above the tax should fix the missing cent.", end=True, ms=1800, tokens=96)),
        (0.1, lambda: lv.say("implementer", "Reading basket.py: the discount runs after the tax line, so a coupon is taxed. ")),
        (0.5, lambda: lv.tool("researcher", "Read", "s-r1", "notes.md")),
        (0.9, lambda: lv.say("tester", "Waiting on the change, then the basket suite.")),
        (1.3, lambda: lv.result("researcher", "s-r1", "# pricing: discount before tax", tool="Read")),
        (1.6, lambda: lv.say("researcher", "The pricing notes agree: discount first, then tax.")),
        (1.9, lambda: lv.tool("implementer", "Edit", "s-i1", "basket.py")),
        (2.2, lambda: (lv.state("tester", cost_usd=0.004), lv.say("docs", "Drafting the CHANGES.md line for the discount order."))),
        (2.5, cost(0.021, 52_000)),
        (2.7, lambda: lv.result("implementer", "s-i1", "basket.py: 3 lines changed", tool="Edit")),
        (3.0, lambda: lv.tool("tester", "Bash", "s-t1", "pytest -q tests/test_basket.py")),
        (3.4, lambda: lv.spawn("v3r1f1e9", "verifier", "verifier", "or:mock/qwen3-coder", "Verify: the basket suite on the change")),
        (3.5, lambda: lv.talk("main", "verifier", "Verify: run the basket suite on the change and tell me what fails.", "task", mid="s-k1")),
        (3.8, lambda: lv.say("verifier", "Running the suite against the new discount order.")),
        (4.2, lambda: lv.ask("reviewer", "permission_request")),
        (4.5, cost(0.034, 79_000)),
        (4.7, lambda: lv.result("tester", "s-t1", "4 passed in 0.31s")),
        (5.0, lambda: (lv.state("docs", cost_usd=0.003), lv.state("docs", state="done", last_text="CHANGES.md: the discount now applies before tax."))),
        (5.1, lambda: lv.talk("docs", "main", "CHANGES.md: the discount now applies before tax.", "hand-back", mid="s-k2")),
        (5.4, lambda: lv.say("implementer", "Done: the discount applies before tax; the suite passes.")),
        (5.8, lambda: lv.tool("verifier", "Bash", "s-v1", "pytest -q")),
        (6.2, cost(0.046, 104_000)),
        (6.6, lambda: lv.state("tester", state="done", last_text="the basket suite passes: 4 tests")),
        (7.0, cost(0.058, 109_000)),
    ]


def play(steps: list) -> threading.Thread:
    """Run `steps` against the clock on a thread (each at its second from now); the thread is returned started."""
    def run() -> None:
        t0 = time.monotonic()
        for at, fn in steps:
            time.sleep(max(0.0, at - (time.monotonic() - t0)))
            try:
                fn()
            except Exception:
                pass
    th = threading.Thread(target=run, daemon=True, name="capture-scene")
    th.start()
    return th
