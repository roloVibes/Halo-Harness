"""tests.helpers.studio_session_truth -- the truth block, the status line and the Start view of Session's Live drawer
(Halo 3.6.0.2 R4 R20 R22 R23), in headless Chrome at 1280 x 800 over tests/helpers/studio_session_rig.py (this
harness's real session A) and a second local session B; every fact reaches the page through GET live's rows
(tests/helpers/studio_session_map_down.py `Rows`) and the feed's frames. No model is called.

    truth   A on `shop`: T1 -> T2 (new sessions on review-flow) -> T5 (its map changed) -> T7 (a step of the workflow W,
            a box on review-flow, runs): each step's lines, the block's height, the drawing's top, the block's colour
    long    A on `shop`, T1, then new sessions switched to a map of a 48-character name and a workflow of a 48-character
            name runs: the block holds only the names it has and is measured again when one really changes (P4 batch 11)
    wide    A on a map of a 48-character name of wide letters (m, w): the block's height at each animation frame from
            its first draw (P4 batch 11)
    flow40  A ran a workflow of a 40-character name and is done, then runs it again waiting for a model reply: the
            status line's room holds the long sentence from the first draw, the zoom row and the drawing hold still
    status  the status line: no rows yet, a workflow's step 3 of 6 at work waiting on its model, then all done
    start   A builds review-flow and ends: T8 while B is open; with no session the Start view's two sentences and its
            [New session]; the map switched on the same page (config crew.map) shows at once; a fresh page with no
            build seen: the first sentence only; the drawer's Empty on a fresh page names the server's {B}, then a switch

    python -m tests.helpers.studio_session_truth [step ...]
The last stdout line is a JSON object of what it saw.
"""
from __future__ import annotations

import json
import sys
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.studio_session_map_down import MapDownDriver, Rows, _seed_shop  # noqa: E402

TRUTH = "document.querySelector('[data-testid=\"session-truth\"]')"
STATUS = "document.querySelector('[data-testid=\"session-status\"]')"
START = "document.querySelector('[data-testid=\"session-start\"]')"
SAID = "document.querySelector('[data-testid=\"session-truth\"] [data-testid=\"session-lit-line\"]')"  # the shown lines, not the twin
FLOW = {"format": "map/1", "name": "review-flow", "boxes": [{"id": "check", "workflow": "W"}],
        "lines": [{"from": "main", "to": "check", "when": "always"}]}
STEPS6 = ["plan", "code", "test", "review", "fix", "ship"]
# what the page shows: the truth lines (each line's own words, a button's label apart), the block, the drawing's top
READ = f"""(() => {{ const t = {TRUTH}, s = {STATUS}, sc = document.querySelector('[data-testid=session-lit-map] .mp-mini-scroll');
  const said = t && t.querySelector('[data-testid=session-lit-line]');
  const probe = document.createElement('span'); probe.style.color = 'var(--warn)'; document.body.appendChild(probe);
  const warn = getComputedStyle(probe).color; probe.remove();
  const r = (el) => el ? Math.round(el.getBoundingClientRect().height * 2) / 2 : null;
  return {{ state: t?.dataset.state || '', lines: said ? [...said.querySelectorAll('.mp-truth-line')].map((p) => p.firstChild?.nodeValue || '') : [],
    buttons: said ? [...said.querySelectorAll('button')].map((b) => b.textContent) : [], text: t?.textContent || '',
    h: r(t?.querySelector('.mp-truth-lines')), top: sc ? Math.round(sc.getBoundingClientRect().top * 2) / 2 : null,
    color: said ? getComputedStyle(said).color : '', lineColor: said?.querySelector('.mp-truth-line') ? getComputedStyle(said.querySelector('.mp-truth-line')).color : '',
    warn, status: s?.textContent || '', sh: s ? s.getBoundingClientRect().height : null, slh: s ? parseFloat(getComputedStyle(s).lineHeight) : null,
    amber: !!t?.querySelector('.mp-amber, [data-tone=warn]'), itext: t?.innerText || '',
    inside: !!t?.querySelector('[data-testid=session-status]'),
    stop: s ? Math.round(s.getBoundingClientRect().top * 2) / 2 : null,
    th: r(t?.querySelector('.mp-truth-twin')), ttext: t?.querySelector('.mp-truth-twin')?.textContent || '',
    ztop: (() => {{ const z = document.querySelector('.mp-down-tools'); return z ? Math.round(z.getBoundingClientRect().top * 2) / 2 : null; }})(),
    below: t && s ? s.getBoundingClientRect().top >= t.getBoundingClientRect().bottom - 0.5 : null }}; }})()"""


def _size(c, w: int, h: int) -> None:
    c.call("Emulation.setDeviceMetricsOverride", width=w, height=h, deviceScaleFactor=1, mobile=False)


def _seed(rig) -> None:
    from halo_harness.crew import store
    _seed_shop(rig)
    store.write_text(store.path_for("map", "review-flow", state_dir=rig.state), json.dumps(FLOW))


def _main(rows: Rows, sid: str, **over) -> dict:
    base = next((r for r in rows.orig() if r.get("session_id") == sid), {})
    head = next((a for a in base.get("agents") or [] if a.get("agent_id") == "main"), {"agent_id": "main", "name": "main", "kind": "main"})
    return {**head, "parent": None, "crew": None, "square": None, "cost_usd": 0, **over}


def _kid(aid: str, name: str, state: str, current: str = "", cost: float = 0.0, crew=None) -> dict:
    return {"agent_id": aid, "name": name, "role": name, "parent": "main", "kind": "member", "state": state, "current": current,
            "cost_usd": cost, "crew": crew, "square": None, "task": f"{name}'s task", "since": time.time()}


def _open(c, rig, query: str) -> None:
    from tests.helpers.studio_session import boot_go, url
    _size(c, 1280, 800)
    boot_go(c, url(rig, query))
    c.wait("document.readyState !== 'loading'", 30)
    c.mouse("mouseMoved", 1279, 799)  # the pointer out of the drawer (it is on the left)


def _settle(c, cond: str, tries: int = 10) -> dict:
    try:
        c.wait(cond, 15)
    except TimeoutError:
        pass  # the read says what was there
    last = c.js(READ) or {}
    for _ in range(tries):
        time.sleep(0.3)
        now = c.js(READ) or {}
        if now == last:
            return now
        last = now
    return last


def truth(c, rig, rows: Rows, a: str, b: str) -> dict:
    t0 = time.time() - 600
    facts = {"map": "shop", "map_plain": False, "map_since": t0, "map_next": "shop", "map_next_since": t0 - 3600, "map_hash": "h1"}
    rows.reset()
    rows.idle(b)
    rows.set(a, busy=False, status="idle", agents=[_main(rows, a, state="done")], **facts)
    _open(c, rig, f"mode=session&session={a}&open=session-map")
    snaps = [_settle(c, f"!!{TRUTH} && {TRUTH}.dataset.state === 'T1' && !!document.querySelector('.mp-mini-scroll')")]
    steps = [("T2", dict(map_next="review-flow", map_next_since=t0 + 60), f"{TRUTH}?.dataset.state === 'T2'"),
             ("T5", dict(map_hash="h2"), f"{SAID}?.textContent.includes('shop changed at')"),
             ("T7", dict(agents=[_main(rows, a, state="running", current="Workflow: W"),
                                 _kid("w1", "tester", "running", "thinking", crew={"workflow": "W", "step": 1, "agent": "tester", "saved": True})]),
              f"{SAID}?.textContent.includes('running the workflow W')")]
    for _, fields, cond in steps:
        rows.set(a, **fields)
        snaps.append(_settle(c, cond))
    return {"truth": snaps, "truth_facts": {"t0": t0, "t2": t0 + 60}}


LONG48 = "code-review-and-tests-for-every-change-made-here"  # 48 characters: the longest name the store allows (crew/formats.py NAME)


def long(c, rig, rows: Rows, a: str, b: str) -> dict:
    from halo_harness.crew import store
    flow = {**FLOW, "name": LONG48, "boxes": [{"id": "check", "workflow": LONG48[:-1] + "w"}]}
    store.write_text(store.path_for("map", LONG48, state_dir=rig.state), json.dumps(flow))
    t0 = time.time() - 600
    facts = {"map": "shop", "map_plain": False, "map_since": t0, "map_next": "shop", "map_next_since": t0 - 3600, "map_hash": "h1"}
    rows.reset()
    rows.idle(b)
    rows.set(a, busy=False, status="idle", agents=[_main(rows, a, state="done")], **facts)
    _open(c, rig, f"mode=session&session={a}&open=session-map")
    snaps = [_settle(c, f"!!{TRUTH} && {TRUTH}.dataset.state === 'T1' && !!document.querySelector('.mp-mini-scroll')")]
    rows.set(a, map_next=LONG48, map_next_since=t0 + 60)
    snaps.append(_settle(c, f"{TRUTH}?.dataset.state === 'T2' && {SAID}?.textContent.includes('{LONG48}')"))
    rows.set(a, agents=[_main(rows, a, state="running", current=f"Workflow: {flow['boxes'][0]['workflow']}"),
                        _kid("w1", "tester", "running", "thinking", crew={"workflow": flow["boxes"][0]["workflow"], "step": 1,
                                                                         "agent": "tester", "saved": True})])
    snaps.append(_settle(c, f"{SAID}?.textContent.includes('running the workflow {flow['boxes'][0]['workflow']}')"))
    return {"long": snaps}


WIDE48 = "mw" * 24  # 48 characters of the widest letters
# every animation frame from the page's start: the truth block's lines' height once it is there (P4 batch 11)
FRAMES_JS = """window.__tb = []; (function loop() { const el = document.querySelector('[data-testid=session-truth] .mp-truth-lines');
  if (el) window.__tb.push(Math.round(el.getBoundingClientRect().height * 2) / 2); if (window.__tb.length < 400) requestAnimationFrame(loop); })();"""


def wide(c, rig, rows: Rows, a: str, b: str) -> dict:
    from halo_harness.crew import store
    store.write_text(store.path_for("map", WIDE48, state_dir=rig.state), json.dumps({**FLOW, "name": WIDE48}))
    t0 = time.time() - 600
    rows.reset()
    rows.idle(b)
    rows.set(a, busy=False, status="idle", agents=[_main(rows, a, state="done")], map=WIDE48, map_plain=False, map_since=t0,
             map_next=WIDE48, map_next_since=t0 - 3600, map_hash="h1",
             map_flows=["W"])  # 3.6.0.9 V batch 2 repair: the row names its map's workflow (crew/map_facts.py row): held from frame one
    c.call("Page.enable")  # the recorder runs before any page script
    sid = c.call("Page.addScriptToEvaluateOnNewDocument", source=FRAMES_JS) or {}
    sid = sid.get("identifier") if isinstance(sid, dict) else None
    try:
        _open(c, rig, f"mode=session&session={a}&open=session-map")
        snap = _settle(c, f"!!{TRUTH} && {TRUTH}.dataset.state === 'T1' && !!document.querySelector('.mp-mini-scroll')")
        frames = c.js("window.__tb || []") or []
    finally:
        if sid:
            c.call("Page.removeScriptToEvaluateOnNewDocument", identifier=sid)
    return {"wide": {"snap": snap, "frames": frames}}


W40 = "code-review-and-tests-for-every-change-m"  # 40 characters


def flow40(c, rig, rows: Rows, a: str, b: str) -> dict:
    t0 = time.time() - 600
    crew = lambda i, who: {"workflow": W40, "step": i, "agent": who, "saved": True}  # noqa: E731
    done = [_kid("w1", "planner", "done", cost=0.5, crew=crew(1, "planner")), _kid("w2", "tester", "done", cost=0.3, crew=crew(2, "tester"))]
    rows.reset()
    rows.idle(b)
    rows.set(a, busy=False, status="idle", agents=[_main(rows, a, state="done", cost_usd=0.1), *done], map="shop", map_plain=False,
             map_since=t0, map_next="shop", map_next_since=t0 - 3600, map_hash="h1")
    _open(c, rig, f"mode=session&session={a}&open=session-map")
    first = _settle(c, f"!!{STATUS} && {STATUS}.textContent.startsWith('Done') && !!document.querySelector('.mp-mini-scroll')")
    rows.set(a, busy=True, status="busy", agents=[_main(rows, a, state="running", current=f"Workflow: {W40}", cost_usd=0.1), done[0],
                                                  {**done[1], "state": "running", "current": "thinking"}])
    run = _settle(c, f"{STATUS}?.textContent.startsWith('tester working')")
    return {"flow40": [first, run]}


def status(c, rig, rows: Rows, a: str, b: str) -> dict:
    from halo_harness.peers.identity import harness
    rows.reset()
    rows.idle(b)
    rows.set(a, map="shop", map_next="shop", busy=False, status="idle", agents=[])
    _open(c, rig, f"mode=session&session={a}&open=session-map")
    first = _settle(c, f"!!{STATUS} && {STATUS}.textContent.startsWith('Waiting for you')")
    flow = lambda i: {"workflow": "W", "step": i, "agent": f"s{i}", "saved": True}  # noqa: E731
    kids = [_kid("w1", "planner", "done", cost=0.5, crew=flow(1)), _kid("w2", "coder", "done", cost=0.42, crew=flow(2)),
            _kid("w3", "tester", "running", "", cost=0.3, crew=flow(3)), _kid("w4", "reviewer", "queued", cost=0.2, crew=flow(4))]
    now = time.time()
    rig.server.events.publish({"session_id": a, "harness": harness()["id"], "event": "map_step", "agent_id": "main", "turn": 1,
                               "data": {"map": "shop", "box": "workflow:W", "workflow": "W", "kind": "start", "steps": STEPS6, "t": now},
                               "ts": now})
    rows.set(a, busy=True, status="busy", agents=[_main(rows, a, state="running", current="Workflow: W", cost_usd=1.0), *kids])
    busy = _settle(c, f"{STATUS}?.textContent.startsWith('tester working')")
    rows.set(a, busy=False, status="idle", agents=[_main(rows, a, state="done", cost_usd=1.0), *[{**k, "state": "done"} for k in kids]])
    done = _settle(c, f"{STATUS}?.textContent.startsWith('Done')")
    return {"status": [first, busy, done]}


def start(c, rig, rows: Rows, a: str, b: str) -> dict:
    from halo_harness.peers.identity import harness
    from halo_harness.theme import set_config_value
    out: dict = {}
    rows.reset()
    rows.idle(b, map_next="review-flow")
    rows.idle(a, map="auto", map_plain=True, map_next=None, map_next_since=None)
    _open(c, rig, f"mode=session&session={a}&open=session-map")
    c.wait(f"!!{TRUTH} && !!document.querySelector('.mp-mini-scroll')", 30)
    now = time.time()
    set_config_value("crew.map", "review-flow")
    rig.server.events.publish({"session_id": a, "harness": harness()["id"], "event": "builder_done", "agent_id": "main", "turn": 1,
                               "data": {"id": "card-t-1", "outcome": "applied", "undo": "u-t-1", "next": "review-flow",
                                        "this_session": "auto", "maps": {}, "t": now,
                                        "wrote": [{"kind": "map", "name": "review-flow", "added": True}]}, "ts": now})
    rows.set(a, map_next="review-flow", map_next_since=now)
    time.sleep(1.0)  # the frame and the row read (no wait condition shows a frame that changes nothing on screen)
    rows.hide(a)
    out["start_ended"] = _settle(c, f"{TRUTH}?.dataset.state === 'T8'")
    rows.hide(b)
    said = "[data-testid=session-start-map]"
    try:
        c.wait(f"!!{START} && !!document.querySelector('{said}')", 30)
    except TimeoutError:
        pass
    out["start_view"] = c.js(f"""(() => ({{ map: document.querySelector('{said}')?.firstChild?.nodeValue || '',
      built: document.querySelector('[data-testid=session-start-built]')?.firstChild?.nodeValue || null,
      button: document.querySelector('[data-testid=session-start-new]')?.textContent || '' }}))()""") or {}
    # R4: {B} is the server's now: the map new sessions use switched on the same page (Agents -> Map, a terminal) shows
    out["start_switched"] = _said_after(c, said, "shop", lambda: set_config_value("crew.map", "shop"))
    _said_after(c, said, "review-flow", lambda: set_config_value("crew.map", "review-flow"))
    c.js("document.querySelector('[data-testid=session-start-new]')?.click(); 1")
    time.sleep(0.3)
    out["start_focus"] = c.js("document.activeElement?.closest('[data-testid=session-new]') ? document.activeElement.dataset.testid : ''")
    _open(c, rig, "mode=session")
    try:
        c.wait(f"!!document.querySelector('{said}')?.textContent", 30)
    except TimeoutError:
        pass
    out["start_fresh"] = c.js(f"""(() => ({{ map: document.querySelector('{said}')?.firstChild?.nodeValue || '',
      built: !!document.querySelector('[data-testid=session-start-built]'),
      button: document.querySelector('[data-testid=session-start-new]')?.textContent || '' }}))()""") or {}
    # R4: the drawer's Empty on a fresh page ("Open the workspace anyway") reads {B} from the server too, and again on a switch
    _open(c, rig, "mode=session&open=session-map")
    empty = f"{TRUTH}?.dataset.state === 'Empty' ? {SAID}.querySelector('.mp-truth-line')?.firstChild?.nodeValue || '' : ''"
    try:
        c.wait("!!document.querySelector('[data-testid=session-open-workspace]')", 30)
        c.js("document.querySelector('[data-testid=session-open-workspace]').click(); 1")
        c.wait(f"({empty}).includes('review-flow')", 15)
    except TimeoutError:
        pass
    out["empty_fresh"] = c.js(empty)
    set_config_value("crew.map", "shop")
    try:
        c.wait(f"({empty}).includes('on shop.')", 15)
    except TimeoutError:
        pass
    out["empty_switched"] = c.js(empty)
    return out


def _said_after(c, said: str, name: str, act) -> str:
    """The Start view's first sentence once it names `name` after `act` (else what it says 15 s later)."""
    act()
    try:
        c.wait(f"(document.querySelector('{said}')?.firstChild?.nodeValue || '').includes('on {name}.')", 15)
    except TimeoutError:
        pass
    return c.js(f"document.querySelector('{said}')?.firstChild?.nodeValue || ''") or ""


class TruthDriver(MapDownDriver):
    width, height = 1280, 800

    @contextmanager
    def session(self, c):
        from tests.helpers.studio_session import FAKE_SID, collect_page_errors, second_session
        from tests.helpers.studio_session_rig import StudioSessionRig
        with StudioSessionRig() as rig:
            _seed(rig)
            second_session(rig)
            rows = Rows(rig)
            collect_page_errors(c)
            args = (c, rig, rows, rig.act.session_id, FAKE_SID)
            steps = [s for s in (truth, long, wide, flow40, status, start) if not self.argv or s.__name__ in self.argv]
            yield tuple((fn, args) for fn in steps)


if __name__ == "__main__":
    sys.exit(TruthDriver(sys.argv[1:]).main())
