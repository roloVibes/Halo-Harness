"""tests.helpers.studio_instrument_shots -- the captures a round of the Instrument look (Halo 3.3.15.0 L1) compares
with docs/design/studio-instrument/mockups/png: over the Studio fleet rig plus three spawned agents, each core section
at 1440 x 900 and 1280 x 800, Roles Live at both, Session's + menu, Session in Focus and Session 390 wide.

    python -m tests.helpers.studio_instrument shots DIR      (the driver's `shots` mode runs this)

No model is called; the PNGs land in DIR only."""
from __future__ import annotations

import time
from pathlib import Path

from tests.helpers.studio_packs_steps import q


def shots(c, rig, folder: str) -> dict:
    from tests.helpers.studio_instrument import CORE, media, rig_load
    out_dir = Path(folder)
    out_dir.mkdir(parents=True, exist_ok=True)
    rig.full = False  # the quiet default layouts, not the drivers' open=all
    made = []
    media(c)

    def shot(name: str, w: int, h: int) -> None:
        made.append(f"{name}:{c.shot(out_dir / name, w, h, 1)}")

    for w, h in ((1440, 900), (1280, 800)):
        c.shot(out_dir / "blank.png", w, h, 1)
        for sid, title in CORE:
            rig_load(c, rig, sid, title)
            time.sleep(2.0)
            shot(f"{sid}@{w}.png", w, h)
        rig_load(c, rig, "roles", "Agents", "&view=live")
        time.sleep(2.0)
        shot(f"roles-live@{w}.png", w, h)
    rig_load(c, rig, "session", "Session")
    c.click_on(q(".section-view:not([hidden]) [data-testid=viewbar-btn][data-panel=session-cost]"))  # 3.6.0.0 R0a: a drawer from the view bar
    c.wait(f"!!{q('.stage-drawer[data-panel-in=session-cost] .panel-body')}", 10)
    shot("session-plus.png", 1440, 900)
    rig_load(c, rig, "session", "Session")
    c.click_on(q("[data-testid=focus-toggle]"))
    time.sleep(0.6)
    shot("session-focus.png", 1440, 900)
    c.click_on(q("[data-testid=focus-toggle]"))
    c.shot(out_dir / "blank.png", 390, 844, 1)
    rig_load(c, rig, "session", "Session")
    time.sleep(2.0)
    shot("session-phone.png", 390, 844)
    (out_dir / "blank.png").unlink(missing_ok=True)
    return {"shots": made}
