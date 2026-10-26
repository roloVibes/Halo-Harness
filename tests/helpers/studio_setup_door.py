"""tests.helpers.studio_setup_door -- the doors' steps of the Setup driver
(tests/helpers/studio_setup.py, Halo 3.3.0.0 R4: `halo init` opens
`?mode=setup&first=1`, `halo setup team` `?mode=setup&block=team`), in headless
Chrome over the driver's scratch home; no network, no model call:

1. `?mode=setup&first=1` (no `tour=off`): Setup, and (3.3.1.0 R1) no help
   and no dialog after 2 s; the strip leads with "set up this box", the
   address bar loses `first=1` (the token stays), Start here's offer waits;
   a reload of the page opens no help and no first-run line;
2. `?mode=setup&block=team`: the Team page is open, focus in it, in view,
   and `block=` leaves the address bar;
3. a `focus` frame `{mode: "setup", block: "check"}` (what a second `halo
   setup` sends a Studio page already open): the Check page opens, focused.
"""
from __future__ import annotations

import time

from tests.helpers.studio_packs_steps import CUR, q

ACTIVE_PANEL = "(document.activeElement?.closest('[data-testid=setup-step-page]')?.dataset.step || '')"  # 3.3.1.0 R1: the page
HELP = q("[data-testid=section-help]")


def first_run(c, url, ctx) -> dict:
    c.go(url.replace("mode=roles&tour=off", "mode=setup&first=1"))
    c.wait(f"{CUR}.startsWith('Setup') && !!{q('[data-testid=setup-rail-step]')}", 40)
    c.wait(f"!!{q('[data-testid=setup-strip-first]')}", 20)
    time.sleep(2.0)
    out = {"first_section": c.js(CUR),
           "first_help": c.js(f"!!{HELP} || document.querySelectorAll('[role=dialog]').length > 0"),
           "first_strip": c.js(f"{q('[data-testid=setup-strip-first]')}.textContent"),
           "first_search": c.js("location.search"), "first_hash": c.js("location.hash.length > 3 || !!sessionStorage.getItem('halo-studio-token')"),
           "first_start_open": c.js(f"!!{q('[data-testid=start-here-setup]')}")}
    c.js("location.reload(); 1")
    time.sleep(0.5)
    c.wait(f"{CUR}.startsWith('Setup') && !!{q('[data-testid=setup-strip-cell]')}", 40)
    time.sleep(1.0)
    out["reload_help"] = c.js(f"!!{HELP}")
    out["reload_strip_first"] = c.js(f"!!{q('[data-testid=setup-strip-first]')}")
    return out


def block(c, url, ctx) -> dict:
    c.go(url.replace("mode=roles", "mode=setup&block=team"))
    c.wait(f"{CUR}.startsWith('Setup') && !!{q('[data-testid=setup-strip-cell]')}", 40)
    out = {"block_focus": c.wait(f"{ACTIVE_PANEL} === 'team' && {ACTIVE_PANEL}", 20),
           "block_search": c.js("location.search"),
           "block_visible": c.wait(f"(() => {{ const r = {q('[data-testid=setup-step-page][data-step=team]')}.getBoundingClientRect(); "
                                   "return r.top < innerHeight && r.bottom > 0 && r.top >= 0; })()", 10)}
    return out


def frame(c, url, ctx) -> dict:
    from halo_harness.studio.events import bridge_for
    from halo_harness.studio.setup_door import SetupTarget
    bridge_for(ctx["srv"]).publish_local({"session_id": "studio", "event": "focus", "ts": time.time(),
                                          "data": SetupTarget(block="check").focus()})
    return {"frame_focus": c.wait(f"{ACTIVE_PANEL} === 'check' && {ACTIVE_PANEL}", 20)}


STEPS = (first_run, block, frame)
