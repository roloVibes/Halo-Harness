"""tests.helpers.studio_session_links -- the links into the Session dashboard
(Halo 3.1.4.0 R2), the `links` step of tests/helpers/studio_session.py: a live Orchestra run's pages (the Map's line
"A goal run is going", Open) have Watch in Session for the run's session (a run folder whose lead is this harness's
session, marked live the way studio/orchestra_live.py marks the one it drives). 3.6.0.0 R5: Live's inspector and node
menu and Roles' Live tab, the other three ways in, went with those views."""
from __future__ import annotations

import threading

from tests.helpers.studio_session import COST, TAB, url

def live_run(rig):
    """A run of the rig's repo led by this harness's session, live as Studio's own run is."""
    from halo_harness.orchestra.goal import Goal, new_run
    from halo_harness.studio import orchestra_live as L
    goal = Goal(what="Ship the basket discount fix", done_when="the tests pass", stop_when="two returns", workers=2,
                return_cap=1, test="python -c pass", files=["basket.py"], test_timeout_s=30)
    run_dir = new_run(rig.proj, goal, lead_holder=f"{rig.act.session_id}/main")
    stop = threading.Event()
    keeper = threading.Thread(target=stop.wait, daemon=True, name="rig-live-run")
    keeper.start()
    with L._lock:
        L._live.update(thread=keeper, run_id=run_dir.name)
    rig.closers.append(stop.set)
    return run_dir


def links(c, rig) -> dict:
    out: dict = {}
    sid = rig.act.session_id
    live_run(rig)
    c.go(url(rig, "mode=agents&view=map&plan=off"))  # 3.6.0.0 R5: the Map's line names the run; Open shows its pages
    opener = "document.querySelector('[data-testid=\"map-lit-run-open\"]')"
    c.wait(f"!!{opener}", 30)
    c.click_on(opener)
    out["watch_orchestra"] = c.wait("document.querySelector('[data-testid=\"orchestra-watch-session\"]')?.textContent", 30)
    c.click_on("document.querySelector('[data-testid=\"orchestra-watch-session\"]')")
    out["orchestra_tab"] = c.wait(f"{TAB}.startsWith('Session') && {TAB}", 10)
    out["orchestra_session"] = c.wait(f"{COST}?.dataset.session === '{sid}' && {COST}.dataset.session", 15)
    out["sid"] = sid
    return out
