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


def _why(c, rig, run_dir, sid: str, took: dict) -> str:
    """What the server and the page say when the button never came (3.6.0.1: red twice on one CI runner with only
    'waited 30s'): the two things the button needs, each from the server and from the page. Yes/no and counts only."""
    said: list = [f"seconds {took}"]
    try:
        local = [h for h in rig.api("GET", "live")[1].get("harnesses", []) if h.get("local")]
        ids = [s.get("session_id") for h in local for s in h.get("sessions") or []]
        said.append(f"server: {len(local)} local harness(es), {len(ids)} session(s), the rig's among them: {sid in ids}")
    except Exception as e:  # noqa: BLE001 -- a diagnostic never hides the timeout it explains
        said.append(f"server live read failed: {type(e).__name__}")
    try:
        st, run = rig.api("GET", f"orchestra/{run_dir.name}")
        lead = str((run.get("run") or run).get("lead_holder") or "")
        said.append(f"server run: {st}, live {run.get('live')!r}, led by the rig's session: {lead.split('/')[0] == sid}")
    except Exception as e:  # noqa: BLE001
        said.append(f"server run read failed: {type(e).__name__}")
    try:
        said.append("page: " + str(c.js(
            "JSON.stringify({inspector: !!document.querySelector('[data-testid=\"run-inspector\"]'), "
            "gone: !!document.querySelector('[data-testid=\"run-gone\"]'), "
            "stop: !!document.querySelector('[data-testid=\"run-stop\"]'), "
            "steer: !!document.querySelector('[data-testid=\"run-steer\"]'), "
            "text: (document.querySelector('[data-testid=\"run-inspector\"]')?.innerText || '').slice(0, 160)})")))
    except Exception as e:  # noqa: BLE001
        said.append(f"page read failed: {type(e).__name__}")
    return "; ".join(said)


def links(c, rig) -> dict:
    import time
    out: dict = {}
    sid = rig.act.session_id
    t0 = time.monotonic()
    run_dir = live_run(rig)
    c.go(url(rig, "mode=agents&view=map&plan=off"))  # 3.6.0.0 R5: the Map's line names the run; Open shows its pages
    opener = "document.querySelector('[data-testid=\"map-lit-run-open\"]')"
    c.wait(f"!!{opener}", 30)
    t1 = time.monotonic()
    c.click_on(opener)
    watch = "document.querySelector('[data-testid=\"orchestra-watch-session\"]')?.textContent"
    try:
        out["watch_orchestra"] = c.wait(watch, 30)
    except TimeoutError as e:
        took = {"to the Open button": round(t1 - t0, 1), "after its click": round(time.monotonic() - t1, 1)}
        raise TimeoutError(f"{e}; WHY: {_why(c, rig, run_dir, sid, took)}") from None
    c.click_on("document.querySelector('[data-testid=\"orchestra-watch-session\"]')")
    out["orchestra_tab"] = c.wait(f"{TAB}.startsWith('Session') && {TAB}", 10)
    out["orchestra_session"] = c.wait(f"{COST}?.dataset.session === '{sid}' && {COST}.dataset.session", 15)
    out["sid"] = sid
    return out
