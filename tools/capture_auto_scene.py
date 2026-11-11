"""tools/capture_auto_scene.py -- the 3.3.17.1 scene tools/capture_steer.py shoots for the README's "Auto mode that never
interrupts" (scripted feed frames over tests/helpers/studio_live_rig.py; no model is called):

    auto(c, rig, lv, png)   docs/media/studio-auto.png: Session's Live column over one short turn in auto mode -- the
                            implementer edits a file, the tester runs the suite, the tester finishes -- and no ask card
                            anywhere in it; the map and the cost beside it. (Studio draws no mode word in Session: the
                            mode is Setup's Permissions page, `permission_mode` in config.json, so the picture shows what
                            auto does, not a label.)
"""
from __future__ import annotations

import time
from pathlib import Path


def auto(c, rig, lv, png: Path) -> int:
    from capture_identity import guard_page
    from capture_session_anim import open_session
    from halo_harness.theme import set_config_value
    set_config_value("permission_mode", "auto")
    open_session(c, rig)
    lv.refresh(cost_usd=0.012, context_tokens=31_000, context_limit=128_000, turns=3)
    lv.say("main", "Wiring the discount before the tax line, then running the basket suite. ")
    time.sleep(0.6)
    lv.tool("implementer", "Edit", "au-e1", "basket.py")
    time.sleep(0.6)
    lv.result("implementer", "au-e1", "basket.py: 3 lines changed", tool="Edit")
    lv.refresh(cost_usd=0.021, context_tokens=44_000, context_limit=128_000, turns=5)
    time.sleep(0.6)
    lv.tool("tester", "Bash", "au-t1", "pytest -q tests/test_basket.py")
    time.sleep(0.8)
    lv.result("tester", "au-t1", "4 passed in 0.31s")
    time.sleep(0.6)
    lv.state("tester", state="done", last_text="Done: the basket suite passes, 4 tests. Nothing asked for your approval.")
    lv.refresh(cost_usd=0.034, context_tokens=52_000, context_limit=128_000, turns=6)
    c.mouse("mouseMoved", 4, 4)
    time.sleep(1.5)
    guard_page(c, "studio-auto")
    return c.shot(png)
