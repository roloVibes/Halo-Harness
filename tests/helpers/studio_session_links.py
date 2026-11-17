"""tests.helpers.studio_session_links -- the links into the Session dashboard
(Halo 3.1.4.0 R2), the `links` step of tests/helpers/studio_session.py: a live Orchestra run's pages (the Map's line
"A goal run is going", Open) have Watch in Session for the run's session (a run folder whose lead is this harness's
session, marked live the way studio/orchestra_live.py marks the one it drives). 3.6.0.0 R5: Live's inspector and node
menu and Roles' Live tab, the other three ways in, went with those views."""
from __future__ import annotations

import threading

from tests.helpers.hold_still import DRAWN, GATE, _measure
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
# P8 repair: what must hold still on the Map while the goal run's line lands (tests/helpers/hold_still.py `still`)
_PART = "document.querySelector('[data-part=map] [data-testid={}]')"
HELD = {"drawing": _PART.format("map-scroll"), "top line": _PART.format("map-topline"),
        "zoom": _PART.format("canvas-zoom"),
        "run open": _PART.format("map-lit-run-open")}
# the oldest held answer that is not a goal run's (None: none waits)
_NOT_RUN = ("(() => { const h = window.__hold, i = h.queue.findIndex((e) => !e.path.startsWith('orchestra'));"
            " if (i < 0) return null; const e = h.queue.splice(i, 1)[0]; h.seen.push(e.path); e.go(); return e.path; })()")


def _release(c, nxt: str, quiet: float = 0.6, each=None) -> list:
    """Let the held answers `nxt` picks go one at a time until none has waited for `quiet` s; `each(path)` after each."""
    import time
    out: list = []
    idle = None
    while len(out) < 120:
        path = c.js(nxt)
        if path is None:
            idle = idle or time.time()
            if time.time() - idle > quiet:
                return out
            time.sleep(0.1)
            continue
        idle = None
        out.append(path)
        c.wait("window.__hold.inflight === 0 && 'idle'", 20)
        c.js(DRAWN)
        if each:
            each(path)
    return out


def held_run(c, page: str) -> dict:
    """P8 repair: the Map opened with every /api/ answer held (tests/helpers/hold_still.py's gate). Every answer but the
    goal runs' let go until nothing more asks: what is drawn then (`drawn_before_runs`). Then the rest, oldest first,
    until the drawing is there: the first draw, measured (`first`); then every answer left, one at a time, the Map
    measured again after each (`moved`)."""
    import time
    c.call("Page.enable")
    ident = c.call("Page.addScriptToEvaluateOnNewDocument", source=GATE)["identifier"]
    out: dict = {"moved": []}
    try:
        c.go("about:blank")
        c.go(page)
        c.wait("!!window.__hold", 40)
        out["before"] = _release(c, _NOT_RUN, quiet=1.5)
        out["drawn_before_runs"] = sorted(k for k, v in _measure(c, HELD).items() if v)
        end = time.time() + 40
        while not c.js(f"!!{HELD['drawing']}") and time.time() < end:
            path = c.js("window.__hold.next()")
            if path:
                out["before"].append(path)
                c.wait("window.__hold.inflight === 0 && 'idle'", 20)
                c.js(DRAWN)
            else:
                time.sleep(0.1)
        out["first"] = first = {k: v for k, v in _measure(c, HELD).items() if v}

        def look(path):
            now = _measure(c, HELD)
            for k, v in first.items():  # each control said once, at its first move
                if not any(m.startswith(k + " moved") for m in out["moved"]) and (
                        not now.get(k) or any(abs(a - b) > 1 for a, b in zip(v, now[k]))):
                    out["moved"].append(f"{k} moved after {path}: {v} -> {now.get(k)}")
        out["released"] = _release(c, "window.__hold.next()", each=look)
    finally:
        c.call("Page.removeScriptToEvaluateOnNewDocument", identifier=ident)
    return out


def live_run(rig, what: str = GOAL):
    """A run of the rig's repo led by this harness's session, live as Studio's own run is."""
    from halo_harness.orchestra.goal import Goal, new_run
    from halo_harness.studio import orchestra_live as L
    goal = Goal(what=what, done_when="the tests pass", stop_when="two returns", workers=2,
                return_cap=1, test="python -c pass", files=["basket.py"], test_timeout_s=30)
    run_dir = new_run(rig.proj, goal, lead_holder=f"{rig.act.session_id}/main")
    stop = threading.Event()
    keeper = threading.Thread(target=stop.wait, daemon=True, name="rig-live-run")
    keeper.start()
    with L._lock:
        L._live.update(thread=keeper, run_id=run_dir.name)
    rig.closers.append(stop.set)
    return run_dir


# P8 batch 3: a goal of 40 characters (one line beside Open) and one of 200 (several lines, whole)
SHORT_GOAL = "Fix the basket discount for loyal people"
LONG_GOAL = ("Ship the basket discount fix for every customer who has a coupon and a loyalty card together, keep the "
             "receipts as they print today, write the change note for the shop staff, then make the tests pass")
STILL = {"drawing": _PART.format("map-scroll"), "top line": _PART.format("map-topline"), "zoom": _PART.format("canvas-zoom")}


def _tops(c) -> dict:
    """The tops of the drawing, the zoom row and the top line (and the top line's height)."""
    m = _measure(c, STILL)
    return {k: (v[1] if k != "top line" else [v[1], v[3]]) if v else None for k, v in m.items()}


def starts(c, rig) -> dict:
    """P8 batch 3 (the coordinator's ruling): the Map open with no goal run, settled; a goal run of 40 characters starts
    (its run folder, live, and the feed's `orchestra_state` frame, as a run Studio drives says it): the run's row was in
    the first draw, one line, empty, so nothing moves; then a run of 200 characters starts: its whole goal grows the row
    ONCE, and nothing moves after that. The run's room is the free width of the top line's row of controls beside Replay
    (LitLine.tsx RunRow): at 1920 x 1000 it holds a 40-character goal on one line; in this rig's Map at 1500 x 900
    it is 319 px (measured) and the same goal takes two lines (it grows the row once, a real change, never cut)."""
    import time
    out: dict = {}
    c.call("Emulation.setDeviceMetricsOverride", width=1920, height=1000, deviceScaleFactor=1, mobile=False)
    try:
        return _starts(c, rig, out)
    finally:
        c.call("Emulation.clearDeviceMetricsOverride")


def _starts(c, rig, out: dict) -> dict:
    import time
    run_row = "document.querySelector('[data-part=map] [data-testid=map-lit-run-row]')"
    goal = "document.querySelector('[data-part=map] [data-testid=map-lit-run-goal]')?.textContent || ''"

    def start(what: str) -> None:
        run_dir = live_run(rig, what)
        rig.server.events.publish_local({"session_id": f"orchestra:{run_dir.name}", "event": "orchestra_state",
                                         "data": {"run": run_dir.name, "kind": "state", "text": "running"}})
    c.go(url(rig, "mode=agents&view=map&plan=off"))
    c.wait("!!document.querySelector('[data-testid=\"map\"][data-settled]')", 30)
    time.sleep(1.0)
    out["no_run"] = _tops(c)
    out["empty_row"] = c.js(f"(() => {{ const r = {run_row}; if (!r) return null; const h = r.getBoundingClientRect().height;"
                            f" return [Math.round(h), r.getAttribute('aria-hidden'), (r.innerText || '').trim()]; }})()")
    start(SHORT_GOAL)
    c.wait(f"({goal}).includes({SHORT_GOAL!r}) && 'shown'", 30)
    time.sleep(0.5)
    out["short"] = _tops(c)
    out["short_parts"] = _measure(c, {k: _PART.format(v) for k, v in (("acts", "map-topline-acts"), ("plan", "map-lit-extras"),
                                                                       ("run", "map-lit-run-row"), ("goal", "map-lit-run-goal"))})
    start(LONG_GOAL)
    c.wait(f"({goal}).includes('the shop staff') && 'shown'", 30)
    time.sleep(0.5)
    out["long"] = _tops(c)
    out["long_whole"] = c.js(WHOLE)
    time.sleep(1.5)
    out["long_later"] = _tops(c)
    c.go("about:blank")  # the flow after it loads the same address afresh (a same-address go would keep this page)
    return out


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
    out["starts"] = starts(c, rig)  # P8 batch 3: before the flow below (its own runs are not live after it)
    run_dir = live_run(rig)
    opener = "document.querySelector('[data-testid=\"map-lit-run-open\"]')"
    c.go(url(rig, "mode=agents&view=map&plan=off"))  # 3.6.0.0 R5: the Map's line names the run; Open shows its pages
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
    # P8 repair (the owner's rule: nothing moves after the first draw): the Map opened with every answer held, then the
    # answers let go one at a time; the drawing waits for the goal runs' listing, so the run's line (its 120-character
    # goal) is in the first draw, and the drawing under the top line, the top line and the zoom never move
    # (done last: the links above are 3.6.0.1's flow, untouched)
    out["held"] = held_run(c, url(rig, "mode=agents&view=map&plan=off"))
    out["held"]["run_landed"] = c.wait(f"!!{opener} && 'landed'", 30)
    return out
