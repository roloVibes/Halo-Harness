"""tests.helpers.studio_session_links -- the links into the Session dashboard
(Halo 3.1.4.0 R2), the `links` step of tests/helpers/studio_session.py: a live Orchestra run's pages (the Map's line
"A goal run is going", Open) have Watch in Session for the run's session (a run folder whose lead is this harness's
session, marked live the way studio/orchestra_live.py marks the one it drives). 3.6.0.0 R5: Live's inspector and node
menu and Roles' Live tab, the other three ways in, went with those views."""
from __future__ import annotations

import threading

from tests.helpers.studio_session import COST, TAB, url

# P8: a 120-character goal -- the top line shows it whole, wrapped beside Open (never cut, never a slice at 80)
GOAL = ("Ship the basket discount fix for every customer who has a coupon and a loyalty card together, "
        "then make the tests pass")
# the goal's words whole (no overflow, no ellipsis or nowrap on it or its row) and Open's rect inside the top line's box
WHOLE = """(() => { const g = document.querySelector('[data-part=map] [data-testid=map-lit-run-goal]');
  const o = document.querySelector('[data-part=map] [data-testid=map-lit-run-open]'), t = document.querySelector('[data-part=map] [data-testid=map-topline]');
  if (!g || !o || !t) return null; const cut = (e) => { const s = getComputedStyle(e); return s.textOverflow === 'ellipsis' || s.whiteSpace === 'nowrap' || s.webkitLineClamp !== 'none'; };
  const O = o.getBoundingClientRect(), T = t.getBoundingClientRect();
  return { text: g.textContent, fits: g.scrollWidth <= g.clientWidth + 1 && g.scrollHeight <= g.clientHeight + 1,
    cut: [g, g.parentElement, g.parentElement.parentElement].some(cut), open_inside: O.width > 0 && O.left >= T.left - 0.5 && O.right <= T.right + 0.5
      && O.top >= T.top - 0.5 && O.bottom <= T.bottom + 0.5 }; })()"""


def live_run(rig):
    """A run of the rig's repo led by this harness's session, live as Studio's own run is."""
    from halo_harness.orchestra.goal import Goal, new_run
    from halo_harness.studio import orchestra_live as L
    goal = Goal(what=GOAL, done_when="the tests pass", stop_when="two returns", workers=2,
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
    'waited 30s'): the two things the button needs, each from the server and from the page. It prints the seconds
    each step took, yes/no and counts, the run read's HTTP status, what the Map's drawer shows (a run's id of the
    rig's made-up run), the top line's state, and the first 160 characters of the page's run inspector. Never a
    session id, a path or a token."""
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
            "open_button: !!document.querySelector('[data-testid=\"map-lit-run-open\"]'), "
            "drawer: document.querySelector('[data-testid=\"map-feed\"]')?.dataset.filter ?? null, "
            "settled: !!document.querySelector('[data-testid=\"map\"][data-settled]'), "
            "top_line: document.querySelector('[data-testid=\"map-topline\"]')?.dataset.lit ?? null, "
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
    # 3.6.0.1 (one Linux CI leg, red three times, its retry too): the button was on the page 0.3 s after the load, the
    # click right after it had no effect, and nothing came for 30 s, while the server answered. WHY IS NOT PROVEN.
    # The likely cause: in a page's first moments the top line is drawn again when the session listing lands. So the
    # driver waits for the Map to say it has settled before it presses and, on a failure, reports what the page held
    # (_why). P4 batch 9: Open lives in ONE parent whatever the top line says, so it is the same node once the Map
    # settled; it is pressed once, never a second time.
    c.js(f"window.__open1 = {opener}; 1")
    try:
        c.wait("!!document.querySelector('[data-testid=\"map\"][data-settled]')", 30)
        out["settled"] = True
    except TimeoutError:
        out["settled"] = False  # the press below still says what happened
    out["open_same_node"] = c.js(f"window.__open1 === {opener}")
    out["whole"] = c.js(WHOLE)
    # the presses that reach Open are COUNTED by the page (P4 batch 12: a constant here could never fail)
    c.js(f"window.__opens = 0; {opener}.addEventListener('click', () => window.__opens++, true); 1")
    t1 = time.monotonic()
    try:
        c.click_on(opener)
        out["open_clicks"] = c.js("window.__opens")
        out["watch_orchestra"] = c.wait("document.querySelector('[data-testid=\"orchestra-watch-session\"]')?.textContent", 30)
    except TimeoutError as e:
        took = {"to the Open button": round(t1 - t0, 1), "after its press": round(time.monotonic() - t1, 1),
                "settled first": out["settled"]}
        raise TimeoutError(f"{e}; WHY: {_why(c, rig, run_dir, sid, took)}") from None
    c.click_on("document.querySelector('[data-testid=\"orchestra-watch-session\"]')")
    out["orchestra_tab"] = c.wait(f"{TAB}.startsWith('Session') && {TAB}", 10)
    out["orchestra_session"] = c.wait(f"{COST}?.dataset.session === '{sid}' && {COST}.dataset.session", 15)
    out["sid"] = sid
    return out
