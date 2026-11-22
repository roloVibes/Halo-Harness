"""tests.helpers.studio_live_now_steps -- "Live you can read" as a person sees it (Halo 3.6.0.13 LV, rule L7 with R10 and
R4), in headless Chrome over tests/helpers/studio_session_rig.py (this harness's real session A, its rows set through GET
live as tests/helpers/studio_auto_groups_draw.py sets them, the feed frames a real session sends published on Studio's own
bridge). Agents -> Live at 1440 x 900 and Session's drawer (its default width; its narrowest for `height` and `s5held`).
No model is called. Every name and figure is invented.

The page's interval timers (its one-second clock among them) are wrapped before the page loads: while `window.__held` is
set they skip, and `window.__step()` runs each once (a step of the clock, never a wait in milliseconds).

    s2now    S2: each NOW kind on the members ("Grep · {s}", "waiting for a model reply · {s}", "queued · {s}",
             "writing · {s}", "thinking · {s}", "waiting for you · {s}", "done in {span}", "stopped after {span}"), the
             heads, main's NOW and TURN -- in Session's drawer, then in Agents -> Live
    rest     the pointer rests on the drawing while the clock steps 30 times and a helper joins: every box's rect, then
             the pointer leaves and the helper is drawn (Session's drawer, then Agents -> Live)
    reduced  S6: reduced motion: a member turns done and one asks: data-ring, data-rang, the running animations; then no
             preference: a member turns done and rings
    s3slot   S3: twelve helpers in seven groups, Tester-1 of "run the tests" asks out of view: the slot (Session, Agents ->
             Live), scrolled past it, and its press
    s3rings  S3's second: the rings with the pointer resting on main, after it leaves; a member under the pointer; six in
             view ending at once
    fold     R4: a slot press with the step-in card open, and the "under the open box" form
    height   one member queued -> running -> a tool -> waiting -> done: its height in Agents -> Live and in Session's
             drawer at its narrowest (last but one: it narrows the drawer)
    s5held   S5: the drawer at its narrowest, a 39-character tool while the pointer is on the drawing, then off, then done

    python -m tests.helpers.studio_live_now_steps [step ...]
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

from tests.helpers.studio_auto_groups_draw import LMORE, LSCROLL, LW, MORE, P, PROBE, RECT, member  # noqa: E402
from tests.helpers.studio_session_map_down import MapDownDriver, Rows  # noqa: E402
from tests.helpers.studio_session_run import M, _main, _seed  # noqa: E402

CLOCK = """(() => { const si = window.setInterval, ci = window.clearInterval, fns = new Map(); window.__held = false; window.__ticks = 0;
  window.setInterval = (fn, ms, ...a) => { const id = si((...b) => { if (!window.__held && typeof fn === 'function') fn(...b); }, ms, ...a);
    if (typeof fn === 'function') fns.set(id, () => fn(...a)); return id; };
  window.clearInterval = (id) => { fns.delete(id); return ci(id); };
  window.__step = () => { window.__ticks += 1; for (const f of [...fns.values()]) { try { f(); } catch (e) { /* a timer's own fault */ } } return window.__ticks; };
})();"""
MSCROLL = f"{M}?.querySelector('.mp-mini-scroll')"
VIEWS = {"session": (M, MSCROLL, MORE), "live": (LW, LSCROLL, LMORE)}
CARD = "document.querySelector('[data-testid=map-step-in]')"
LCARD = f"document.querySelector('{P} [data-testid=map-step-in]')"
GROUPS = ":is([data-testid=session-map-group], [data-testid=live-group])"
# everything a test reads off one drawing: members, groups, main, the rings, what lies wholly in the scroll box's view
READ = f"""((root, sc) => {{ if (!root) return null; const R = {RECT}, v = sc ? sc.getBoundingClientRect() : null;
  const inView = (e) => {{ const r = e.getBoundingClientRect(); return !!v && r.height > 0 && r.top >= v.top - 0.5 && r.bottom <= v.top + sc.clientHeight + 0.5
    && r.left >= v.left - 0.5 && r.right <= v.left + sc.clientWidth + 0.5; }};
  const now = (m) => m.querySelector(':scope > [data-testid=map-member-now]');
  const main = root.querySelector('[data-box=main]');
  return {{ members: Object.fromEntries([...root.querySelectorAll('[data-member]')].map((m) => [m.dataset.member, {{raw: m.dataset.raw || '',
      now: now(m)?.textContent || '', kind: now(m)?.dataset.now || '', state: m.querySelector('[data-testid=map-member-state]')?.textContent || '',
      edge: getComputedStyle(m).borderLeftColor, rect: R(m), seen: inView(m), rang: m.dataset.rang || '', ring: m.dataset.ring || '',
      group: m.closest('[data-box]')?.dataset.box || ''}}])),
    groups: Object.fromEntries([...root.querySelectorAll('{GROUPS}')].map((g) => [g.dataset.box, {{name: g.querySelector('[data-testid=map-group-name]')?.textContent || '',
      counts: g.querySelector('[data-testid=map-group-counts]')?.textContent || '', warn: g.querySelector('[data-testid=map-group-counts] .mp-warn')?.textContent || '',
      rect: R(g), seen: inView(g), rang: g.dataset.rang || '', members: g.querySelectorAll('[data-member]').length}}])),
    main: main ? {{rect: R(main), now: main.querySelector('[data-testid=map-main-now]')?.textContent || '',
      turn: main.querySelector('[data-testid=map-main-turn]')?.textContent || '', rang: main.dataset.rang || ''}} : null,
    rang: [...root.querySelectorAll('[data-rang]')].map((e) => e.dataset.member || e.dataset.box),
    view: v ? [v.left, v.top, sc.clientWidth, sc.clientHeight] : null, top: sc ? sc.scrollTop : null }}; }})"""
SLOT_READ = """((b) => b ? {text: b.textContent, wait: b.dataset.wait ?? null, arrow: b.dataset.arrow ?? null, group: b.dataset.group ?? null} : null)"""
WARN = f"({PROBE})(document.body, '--warn')"


def read(c, view: str) -> dict:
    root, sc, slot = VIEWS[view]
    got = c.js(f"({READ})({root}, {sc})") or {}
    got["slot"] = c.js(f"({SLOT_READ})({slot})")
    return got


def mk(aid: str, who: str, desc: str, task: str, n: int, state: str = "running", model: str = "kimi-k3", since: float = 0.0) -> dict:
    return {**member(aid, who, desc, task, n, state=state, model=model), "since": since or time.time()}


def feed(rig, sid: str, aid: str, event: str, data: dict) -> None:
    from halo_harness.peers.identity import harness
    now = time.time()
    rig.server.events.publish({"session_id": sid, "harness": harness()["id"], "event": event, "agent_id": aid, "turn": 1, "data": data, "ts": now})


def ask(rig, sid: str, aid: str, n: int = 1) -> None:
    feed(rig, sid, aid, "permission_request", {"id": f"perm-{aid}-{n}", "name": "Bash", "input": {"command": "pytest -q tests/unit"}})


def put(rows: Rows, a: str, agents: list, **kw) -> None:
    rows.set(a, map="auto", map_plain=True, busy=True, status="busy", agents=agents, **kw)


def go(c, rig, rows: Rows, a: str, b: str, agents: list, w: int = 1440, h: int = 900) -> None:
    """Session's drawer on A (Auto) with `agents`, the clock running, the pointer off the drawing."""
    from tests.helpers.studio_session import boot_go, url
    rows.reset()
    rows.idle(b)
    put(rows, a, agents)
    c.call("Emulation.setDeviceMetricsOverride", width=w, height=h, deviceScaleFactor=1, mobile=False)
    boot_go(c, url(rig, f"mode=session&session={a}&open=session-map"))
    c.wait(f"!!{M} && {M}.dataset.map === 'auto' && !!{M}.querySelector('[data-box=main]')", 40)
    c.mouse("mouseMoved", w - 1, h - 1)


def to_live(c, groups: int) -> None:
    """Agents -> Live from Session's drawer, the pointer on the rail (off the frame)."""
    c.click_on("document.querySelector('[data-testid=session-lit-open]')")
    c.mouse("mouseMoved", 2, 400)
    c.wait(f"{LW}?.dataset.map === 'auto' && {LW}.querySelectorAll('[data-testid=live-group]').length === {groups}", 30)


def frames(c, n: int = 3) -> None:
    """`n` animation frames of the page (a layout effect and a scroll event have run)."""
    c.js(f"(async () => {{ for (let i = 0; i < {n}; i++) await new Promise((r) => requestAnimationFrame(() => r())); return 1; }})()")


def wait_or(c, expr: str, timeout: float = 15):
    try:
        return c.wait(expr, timeout)
    except TimeoutError:
        return None  # the reading says what it showed


def rest_on(c, expr: str) -> None:
    x, y, w, h = c.rect(expr)
    for dx in (0, 2, 4):
        c.mouse("mouseMoved", x + w / 2 + dx, y + h / 2)


def now_is(root: str, aid: str, start: str) -> str:
    return f"({root}?.querySelector('[data-member={aid}] > [data-testid=map-member-now]')?.textContent || '').startsWith({json.dumps(start)})"


# ---- S2 ---------------------------------------------------------------------------------------------------------------
S2_TASKS = ["write the changelog", "survey the TODOs", "fix the login bug", "review the money module", "plan the migration",
            "read the spec pdf"]


def s2_rows(rows: Rows, a: str, t0: float, end: bool) -> list:
    main = _main(rows, a, state="running", current="Agent: survey the TODOs", since=t0, started=t0,
                 turn={"n": 1, "helpers": 5, "tools": 4, "ended": False})
    T = S2_TASKS
    return [main, mk("w1", "writer", "note the release", T[0], 1, "done" if end else "running", since=t0),
            mk("r1", "researcher", "grep the TODOs", T[1], 2, since=t0), mk("r2", "researcher", "count them", T[1], 2, since=t0),
            mk("r3", "researcher", "sort them", T[1], 2, "queued", since=t0),
            mk("k1", "coder", "fix the login form", T[2], 3, model="glm-5", since=t0),
            mk("v1", "reviewer", "check pay.py", T[3], 4, "waiting" if end else "running", since=t0),
            mk("p1", "planner", "outline the steps", T[4], 5, since=t0),
            mk("x1", "reader", "read the spec", T[5], 6, "stopped" if end else "running", since=t0)]


S2_WANT = {"r1": "Grep · ", "r2": "waiting for a model reply · ", "r3": "queued · ", "k1": "writing · ", "p1": "thinking · ",
           "v1": "waiting for you · ", "w1": "done in ", "x1": "stopped after "}


def s2now(c, rig, rows: Rows, a: str, b: str) -> dict:
    out: dict = {}
    t0 = time.time() - 30
    go(c, rig, rows, a, b, s2_rows(rows, a, t0, False))
    c.wait(f"{M}.querySelectorAll('[data-member]').length === 8", 20)
    c.js("window.__held = true; 1")  # the clock held: "writing" stays (its 4 s are counted on the page's clock)
    try:
        feed(rig, a, "r1", "tool_use_start", {"id": "t-r1", "name": "Grep"})
        feed(rig, a, "main", "tool_use_start", {"id": "t-main", "name": "Agent"})
        feed(rig, a, "p1", "thinking_chunk", {"id": "th-p1", "text": "the steps first, then the order"})
        feed(rig, a, "k1", "text_chunk", {"text": "The form now checks the field."})
        ask(rig, a, "v1")
        put(rows, a, s2_rows(rows, a, t0, True))  # each ends while the page is open: the page saw the end
        every = " && ".join(now_is(M, k, v) for k, v in S2_WANT.items())
        wait_or(c, every, 20)
        out["session"] = read(c, "session")
        out["warn"] = c.js(WARN)
        c.js("window.__held = false; 1")
        to_live(c, 6)
        c.js("window.__held = true; 1")
        feed(rig, a, "k1", "text_chunk", {"text": " And the tests pass."})  # writing again, on this drawing's clock
        wait_or(c, " && ".join(now_is(LW, k, v) for k, v in S2_WANT.items()), 20)
        out["live"] = read(c, "live")
    finally:
        c.js("window.__held = false; 1")
    return {"s2now": out}


# ---- the pointer resting ----------------------------------------------------------------------------------------------
def _rects(c, view: str) -> dict:
    root = VIEWS[view][0]
    return c.js(f"""(() => {{ const R = {RECT}; return Object.fromEntries([...{root}.querySelectorAll('[data-member], [data-box]')]
      .map((e) => [e.dataset.member ? 'm:' + e.dataset.member : 'b:' + e.dataset.box, R(e)])); }})()""") or {}


def _rest_one(c, rig, rows: Rows, a: str, b: str, view: str) -> dict:
    t0 = time.time() - 5
    main = _main(rows, a, state="running", current="Agent: survey the TODOs", since=t0, started=t0)
    kids = [mk(f"q{i}", "researcher", f"read part {i}", "survey the TODOs", 1, since=t0) for i in (1, 2)]
    kids += [mk("q3", "coder", "fix the form", "fix the login bug", 2, model="glm-5", since=t0)]
    go(c, rig, rows, a, b, [main, *kids])
    c.wait(f"{M}.querySelectorAll('[data-member]').length === 3", 20)
    if view == "live":
        to_live(c, 2)
    root = VIEWS[view][0]
    frames(c, 6)
    c.js("window.__held = true; 1")
    out: dict = {}
    try:
        rest_on(c, f"{root}.querySelector('[data-box=main]')")
        out["held"] = (c.js(f"document.querySelector('{P} [data-testid=live-frame]')?.dataset.held || ''") if view == "live"
                       else "1" if c.js(f"!!{M}?.querySelector('[data-box=main]')?.matches(':hover')") else "")  # the pointer on the drawing
        first = _rects(c, view)
        changed: list = []
        c.js("performance.clearResourceTimings(); 1")
        put(rows, a, [main, *kids, mk("q4", "researcher", "read part 4", "survey the TODOs", 1, since=t0)])
        out["fetched"] = bool(wait_or(c, "performance.getEntriesByType('resource').some((e) => e.name.includes('/api/'))", 15))
        for _ in range(30):
            c.js("window.__step()")
            got = _rects(c, view)
            if got != first:
                changed.append({k: [first.get(k), got.get(k)] for k in set(first) | set(got) if first.get(k) != got.get(k)})
                first = got
        out["ticks"] = c.js("window.__ticks")
        out["changed"] = changed[:4]
        out["drawn_held"] = c.js(f"!!{root}.querySelector('[data-member=q4]')")
        c.mouse("mouseMoved", 2 if view == "live" else 1439, 899 if view != "live" else 400)
        c.js("window.__step(); 1")
        out["drawn_after"] = bool(wait_or(c, f"!!{root}.querySelector('[data-member=q4]')", 15))
    finally:
        c.js("window.__held = false; 1")
    return out


def rest(c, rig, rows: Rows, a: str, b: str) -> dict:
    return {"rest": {v: _rest_one(c, rig, rows, a, b, v) for v in ("session", "live")}}


# ---- S6: reduced motion -----------------------------------------------------------------------------------------------
ANIMS = "document.getAnimations().filter((x) => x.effect?.target?.closest?.('[data-member]')).map((x) => x.animationName || x.id || 'an animation')"


def reduced(c, rig, rows: Rows, a: str, b: str) -> dict:
    from tests.helpers.chrome_driver import emulate_motion
    out: dict = {}
    t0 = time.time() - 20
    main = _main(rows, a, state="running", current="Agent: survey the TODOs", since=t0, started=t0)
    kids = lambda s1, s2, s3: [mk("m1", "researcher", "read part 1", "survey the TODOs", 1, s1, since=t0),  # noqa: E731
                               mk("m2", "researcher", "read part 2", "survey the TODOs", 1, s2, since=t0),
                               mk("m3", "researcher", "read part 3", "survey the TODOs", 1, s3, since=t0)]
    try:
        for motion in ("reduce", "no-preference"):
            emulate_motion(c, motion)
            go(c, rig, rows, a, b, [main, *kids("running", "running", "running")])
            to_live(c, 1)
            frames(c, 6)
            got: dict = {"media": c.js("matchMedia('(prefers-reduced-motion: reduce)').matches")}
            ask(rig, a, "m2")
            put(rows, a, [main, *kids("done", "waiting", "running")])
            wait_or(c, f"{LW}.querySelector('[data-member=m1]')?.dataset.raw === 'done' && {LW}.querySelector('[data-member=m2]')?.dataset.raw === 'waiting'", 15)
            if motion == "no-preference":
                wait_or(c, f"!!{LW}.querySelector('[data-member=m1][data-rang]')", 10)
            frames(c, 2)
            got["ring"] = c.js(f"[...{LW}.querySelectorAll('[data-ring]')].map((e) => e.dataset.member || e.dataset.box)")
            got["rang"] = c.js(f"[...{LW}.querySelectorAll('[data-rang]')].map((e) => e.dataset.member || e.dataset.box)")
            got["anims"] = c.js(ANIMS)
            got["raw"] = c.js(f"[...{LW}.querySelectorAll('[data-member]')].map((e) => e.dataset.raw)")
            out[motion] = got
    finally:
        emulate_motion(c, "no-preference")
    return {"reduced": out}


# ---- S3 ---------------------------------------------------------------------------------------------------------------
S3_TASKS = ["survey the TODOs", "fix the login bug", "review the money module", "write the changelog", "run the tests",
            "read the spec pdf", "plan the migration"]


def s3_rows(rows: Rows, a: str, t0: float, **st) -> list:
    """S3: twelve helpers in seven groups; `st` sets a member's state by its id, `extra` adds members to group 1."""
    T = S3_TASKS
    spec = [("r1", "researcher", "read the old notes", 1, "running"), ("r2", "researcher", "read the issues", 1, "running"),
            ("r3", "researcher", "read the wiki", 1, "queued"), ("k1", "coder", "fix the login form", 2, "running"),
            ("v1", "reviewer", "check pay.py", 3, "queued"), ("v2", "reviewer", "check tax.py", 3, "queued"),
            ("w1", "writer", "note the release", 4, "done"), ("t1", "Tester", "run the unit tests", 5, "running"),
            ("t2", "Tester", "run the slow tests", 5, "queued"), ("d1", "general-purpose", "read the spec", 6, "queued"),
            ("n1", "planner", "plan the tables", 7, "queued"), ("n2", "planner", "plan the moves", 7, "queued")]
    extra = st.pop("extra", 0)
    spec += [(f"r{4 + i}", "researcher", f"read part {4 + i}", 1, "queued") for i in range(extra)]
    main = _main(rows, a, state="running", current="Agent: run the tests", since=t0, started=t0)
    return [main, *[mk(aid, who, desc, T[n - 1], n, st.get(aid, s), since=t0) for aid, who, desc, n, s in spec]]


def _go_s3(c, rig, rows: Rows, a: str, b: str, t0: float, live: bool = True, **st) -> None:
    go(c, rig, rows, a, b, s3_rows(rows, a, t0, **st))
    c.wait(f"{M}.querySelectorAll('{GROUPS}').length === 7", 20)
    if live:
        to_live(c, 7)
        frames(c, 6)


def _below_js(view: str, n: str) -> str:
    """The groups other than `n` wholly below the view of `view`'s scroll box (read from the page)."""
    root, sc, _ = VIEWS[view]
    return f"""(() => {{ const s = {sc}, v = s.getBoundingClientRect(), foot = v.top + s.clientHeight;
      return [...{root}.querySelectorAll('{GROUPS}')].filter((g) => g.dataset.box !== {json.dumps(n)} && g.getBoundingClientRect().top >= foot - 0.5).length; }})()"""


def s3slot(c, rig, rows: Rows, a: str, b: str) -> dict:
    out: dict = {}
    t0 = time.time() - 40
    _go_s3(c, rig, rows, a, b, t0, live=False)
    ask(rig, a, "t1")
    put(rows, a, s3_rows(rows, a, t0, t1="waiting"))
    for view in ("session", "live"):
        if view == "live":
            to_live(c, 7)
            frames(c, 6)
        slot = VIEWS[view][2]
        wait_or(c, f"({slot})?.textContent.startsWith('↓ run the tests · waits on you')", 15)
        frames(c, 2)
        out[view] = {"slot": c.js(f"({SLOT_READ})({slot})"), "below": c.js(_below_js(view, "group:5")),
                     "g5": (read(c, view).get("groups") or {}).get("group:5")}
    # the press (Agents -> Live): the asking member comes into view
    tester = f"{LW}.querySelector('[data-member=t1]')"
    seen = f"""(() => {{ const s = {LSCROLL}, v = s.getBoundingClientRect(), r = {tester}.getBoundingClientRect();
      return r.top >= v.top - 0.5 && r.bottom <= v.top + s.clientHeight + 0.5; }})()"""
    out["seen_before"] = c.js(seen)
    c.click_on(LMORE)
    out["press"] = bool(wait_or(c, seen, 10))
    c.mouse("mouseMoved", 2, 400)
    # scrolled past it: group 5 above the view (a shorter window when the drawing below it is shorter than the view)
    past = f"(() => {{ const s = {LSCROLL}; s.scrollTop = s.scrollHeight; const g = s.querySelector('[data-box=\"group:5\"]').getBoundingClientRect(); return g.bottom <= s.getBoundingClientRect().top + 0.5; }})()"
    out["up_height"] = None
    for hh in (900, 700, 560, 460):
        c.call("Emulation.setDeviceMetricsOverride", width=1440, height=hh, deviceScaleFactor=1, mobile=False)
        frames(c, 4)
        if c.js(past):
            out["up_height"] = hh
            break
    wait_or(c, f"({LMORE})?.textContent.startsWith('↑ run the tests · waits on you')", 15)
    out["up"] = c.js(f"({SLOT_READ})({LMORE})")
    if out["up"]:
        c.click_on(LMORE)
        out["up_press"] = bool(wait_or(c, seen, 10))
    c.call("Emulation.setDeviceMetricsOverride", width=1440, height=900, deviceScaleFactor=1, mobile=False)
    return {"s3slot": out}


def s3rings(c, rig, rows: Rows, a: str, b: str) -> dict:
    out: dict = {}
    t0 = time.time() - 40
    _go_s3(c, rig, rows, a, b, t0)
    out["first"] = read(c, "live")
    # S3's second, the pointer resting on main: Tester-1 asks (out of view), the coder ends, researcher-3 and reviewer-1
    # start, researcher-2 fails, main adds a fourth researcher to group 1
    rest_on(c, f"{LW}.querySelector('[data-box=main]')")
    ask(rig, a, "t1")
    put(rows, a, s3_rows(rows, a, t0, t1="waiting", k1="done", r3="running", r2="failed", v1="running", extra=1))
    wait_or(c, f"!!{LW}.querySelector('[data-member=k1][data-rang]') && !!{LW}.querySelector('[data-member=r2][data-rang]')", 15)
    frames(c, 2)
    out["held"] = read(c, "live")
    c.mouse("mouseMoved", 2, 400)
    wait_or(c, f"!!{LW}.querySelector('[data-member=r4]') && !!{LW}.querySelector('[data-box=\"group:1\"][data-rang]')", 15)
    frames(c, 2)
    out["left"] = read(c, "live")
    # a member under the pointer ends: no ring, then or after the pointer leaves
    rest_on(c, f"{LW}.querySelector('[data-member=r1]')")
    put(rows, a, s3_rows(rows, a, t0, t1="waiting", k1="done", r3="running", r2="failed", v1="running", extra=1, r1="done"))
    wait_or(c, f"{LW}.querySelector('[data-member=r1]')?.dataset.raw === 'done'", 15)
    frames(c, 2)
    c.mouse("mouseMoved", 2, 400)
    c.js("window.__step(); 1")
    frames(c, 4)
    out["pointer"] = read(c, "live")
    # six in view end at once (a window tall enough to hold them, read from the page): at most four ring, the top-most
    t1 = time.time() - 40
    six = [mk(f"s{i}", "researcher", f"read part {i}", "survey the TODOs", 1, since=t1) for i in range(1, 7)]
    main = _main(rows, a, state="running", current="Agent: survey the TODOs", since=t1, started=t1)
    go(c, rig, rows, a, b, [main, *six], h=1500)
    to_live(c, 1)
    frames(c, 6)
    out["six_before"] = read(c, "live")
    put(rows, a, [main, *[{**k, "state": "done"} for k in six]])
    wait_or(c, f"[...{LW}.querySelectorAll('[data-member]')].every((m) => m.dataset.raw === 'done') && !!{LW}.querySelector('[data-rang]')", 15)
    frames(c, 4)
    out["six"] = read(c, "live")
    c.call("Emulation.setDeviceMetricsOverride", width=1440, height=900, deviceScaleFactor=1, mobile=False)
    # the first hand-out of a session: main is drawn alone (nothing rings), then its first group is drawn: it rings HAND
    go(c, rig, rows, a, b, [main])
    to_live(c, 0)
    frames(c, 6)
    out["alone"] = read(c, "live")
    put(rows, a, [main, mk("f1", "researcher", "read part 1", "survey the TODOs", 1, since=time.time())])
    wait_or(c, f"!!{LW}.querySelector('[data-box=\"group:1\"][data-rang]')", 15)
    frames(c, 2)
    out["handed"] = read(c, "live")
    return {"s3rings": out}


# ---- R4: the slot press with the card open ----------------------------------------------------------------------------
LISTEN = f"""(() => {{ const s = {LSCROLL}; window.__scrolls = []; window.__top0 = s.scrollTop;
  s.addEventListener('scroll', () => window.__scrolls.push(!!{LCARD})); return 1; }})()"""
UNDER = f"""(() => {{ const c = {LCARD}.getBoundingClientRect(), s = {LSCROLL}, v = s.getBoundingClientRect();
  return [...{LW}.querySelectorAll('[data-member]')].filter((m) => {{ const r = m.getBoundingClientRect();
    return r.top >= v.top && r.bottom <= v.top + s.clientHeight && r.bottom > c.top && r.top < c.bottom && r.right > c.left && r.left < c.right; }})
    .map((m) => [m.dataset.member, m.closest('[data-box]')?.dataset.box || '']); }})()"""


def fold(c, rig, rows: Rows, a: str, b: str) -> dict:
    out: dict = {}
    t0 = time.time() - 40
    # a group waiting below, the card open on group 1: the press folds the card before any scroll
    _go_s3(c, rig, rows, a, b, t0, t1="waiting")
    ask(rig, a, "t1")
    c.click_on(f"{LW}.querySelector('[data-box=\"group:1\"] [data-testid=map-group-name]')")
    c.wait(f"!!{LCARD}", 10)
    wait_or(c, f"({LMORE})?.textContent.startsWith('↓ run the tests · waits on you')", 15)
    out["slot"] = c.js(f"({SLOT_READ})({LMORE})")
    c.js(LISTEN)
    c.click_on(LMORE)
    wait_or(c, f"!{LCARD} && window.__scrolls.length > 0", 10)
    frames(c, 4)
    out["press"] = c.js(f"({{scrolls: window.__scrolls, card: !!{LCARD}, moved: {LSCROLL}.scrollTop !== window.__top0}})")
    # the "under the open box" form: a member under the card asks; the press only folds the card
    c.mouse("mouseMoved", 2, 400)
    _go_s3(c, rig, rows, a, b, t0)
    c.click_on(f"{LW}.querySelector('[data-box=\"group:1\"] [data-testid=map-group-name]')")
    c.wait(f"!!{LCARD}", 10)
    c.mouse("mouseMoved", 2, 400)  # the pointer off the drawing: the open card alone holds it and covers the member
    frames(c, 2)
    under = c.js(UNDER) or []
    out["under_members"] = under
    if under:
        aid, box = under[0]
        out["under"] = {"aid": aid, "group": box}
        ask(rig, a, aid)
        put(rows, a, s3_rows(rows, a, t0, **{aid: "waiting"}))
        wait_or(c, f"({LMORE})?.dataset.arrow === 'under'", 15)
        frames(c, 2)
        out["under_slot"] = c.js(f"({SLOT_READ})({LMORE})")
        out["under_name"] = c.js(f"{LW}.querySelector('[data-box=\"{box}\"] [data-testid=map-group-name]')?.textContent || ''")
        out["under_rang"] = c.js(f"{LW}.querySelector('[data-member={aid}]')?.dataset.rang || ''")
        c.js(LISTEN)
        c.click_on(LMORE)
        wait_or(c, f"!{LCARD}", 10)
        frames(c, 4)
        out["under_press"] = c.js(f"({{scrolls: window.__scrolls, card: !!{LCARD}, moved: {LSCROLL}.scrollTop !== window.__top0}})")
    return {"fold": out}


# ---- the drawer at its narrowest --------------------------------------------------------------------------------------
def narrow(c) -> list:
    """Session's drawer dragged to its least width (as tests/helpers/studio_auto_groups_draw.py `longest` drags it)."""
    from tests.helpers.studio_run_parts import settled
    drawer = f"{M}?.closest('[data-testid=stage-drawer]')"
    for _ in range(3):
        sp = c.js(f"""(() => {{ const d = {drawer};
          const s = d?.querySelector(':scope > [data-testid=stage-splitter]'); if (!s) return null; const r = s.getBoundingClientRect();
          return [r.left + r.width / 2, r.top + r.height / 2, d.dataset.side, +s.getAttribute('aria-valuemin'), Math.round(d.getBoundingClientRect().width)]; }})()""")
        if not sp or sp[4] <= sp[3]:
            break
        c.drag(sp[0], sp[1], sp[0] + (-600 if sp[2] == "left" else 600), sp[1])
        c.mouse("mouseMoved", 1439, 899)
        settled(c, f"Math.round({drawer}?.getBoundingClientRect().width || 0)")
    return c.js(f"[Math.round({drawer}?.getBoundingClientRect().width || 0), +({drawer}?.querySelector(':scope > [data-testid=stage-splitter]')?.getAttribute('aria-valuemin') || 0)]")


MODEL = "mock-model-nine"  # invented: "{model} · waiting on you" is 32 characters, two rows at the drawer's narrowest
HEIGHT_STEPS = [("queued", "queued · "), ("running", "waiting for a model reply · "), ("tool", "Read · "),
                ("waiting", "waiting for you · "), ("done", "done in ")]


def _height_run(c, rig, rows: Rows, a: str, view: str, t0: float, main: dict) -> list:
    root = VIEWS[view][0]
    m = f"{root}.querySelector('[data-member=h1]')"
    seen: list = []
    for name, want in HEIGHT_STEPS:
        st = {"tool": "running"}.get(name, name)
        if name == "tool":
            feed(rig, a, "h1", "tool_use_start", {"id": f"t-h1-{view}", "name": "Read"})
        if name == "waiting":
            feed(rig, a, "h1", "tool_result", {"id": f"t-h1-{view}", "name": "Read", "content": "ok", "is_error": False})
            ask(rig, a, "h1", 2 if view == "session" else 1)
        put(rows, a, [main, mk("h1", "checker", "check the invoices", "check the invoices", 1, st, model=MODEL, since=t0)])
        wait_or(c, f"{m}?.dataset.raw === {json.dumps(st)} && {now_is(root, 'h1', want)}", 15)
        frames(c, 2)
        seen.append(c.js(f"(() => {{ const e = {m}; return e ? [{json.dumps(name)}, e.getBoundingClientRect().height, e.querySelector(':scope > [data-testid=map-member-now]')?.textContent || '', e.querySelector('[data-testid=map-member-state]')?.textContent || ''] : null; }})()"))
    return seen


def height(c, rig, rows: Rows, a: str, b: str) -> dict:
    out: dict = {}
    t0 = time.time() - 10
    main = _main(rows, a, state="running", current="Agent: check the invoices", since=t0, started=t0)
    first = [main, mk("h1", "checker", "check the invoices", "check the invoices", 1, "queued", model=MODEL, since=t0)]
    go(c, rig, rows, a, b, first)
    to_live(c, 1)
    frames(c, 4)
    out["live"] = _height_run(c, rig, rows, a, "live", t0, main)
    go(c, rig, rows, a, b, first)
    out["drawer"] = narrow(c)
    frames(c, 4)
    out["session"] = _height_run(c, rig, rows, a, "session", t0, main)
    out["width"] = c.js(f"{M}.querySelector('[data-member=h1]')?.getBoundingClientRect().width || 0")
    return {"height": out}


TOOL = "mcp__deckcraft__insert_chart_from_range"  # 39 characters


def s5held(c, rig, rows: Rows, a: str, b: str) -> dict:
    out: dict = {}
    t0 = time.time() - 10
    main = _main(rows, a, state="running", current="Agent: review the money module", since=t0, started=t0)
    kids = lambda st: [mk("e1", "reviewer", "check pay.py", "review the money module", 1, st, since=t0),  # noqa: E731
                       mk("e2", "coder", "fix the form", "fix the login bug", 2, model="glm-5", since=t0),
                       mk("e3", "planner", "plan the tables", "plan the migration", 3, since=t0)]
    go(c, rig, rows, a, b, [main, *kids("running")])
    out["drawer"] = narrow(c)
    frames(c, 4)
    m = f"{M}.querySelector('[data-member=e1]')"
    h = lambda: c.js(f"{m}?.getBoundingClientRect().height || 0")  # noqa: E731
    out["first"] = h()
    rest_on(c, f"{M}.querySelector('[data-box=main]')")
    feed(rig, a, "e1", "tool_use_start", {"id": "t-e1", "name": TOOL})
    wait_or(c, now_is(M, "e1", "a tool · "), 15)
    frames(c, 2)
    out["held"] = [h(), c.js(f"{m}.querySelector(':scope > [data-testid=map-member-now]')?.textContent || ''")]
    c.mouse("mouseMoved", 1439, 899)
    wait_or(c, now_is(M, "e1", TOOL + " · "), 15)
    frames(c, 2)
    out["left"] = [h(), c.js(f"{m}.querySelector(':scope > [data-testid=map-member-now]')?.textContent || ''")]
    feed(rig, a, "e1", "tool_result", {"id": "t-e1", "name": TOOL, "content": "ok", "is_error": False})
    put(rows, a, [main, *kids("done")])
    wait_or(c, f"{m}?.dataset.raw === 'done' && {now_is(M, 'e1', 'done in ')}", 15)
    frames(c, 2)
    out["done"] = [h(), c.js(f"{m}.querySelector(':scope > [data-testid=map-member-now]')?.textContent || ''")]
    return {"s5held": out}


STEPS = (s2now, rest, reduced, s3slot, s3rings, fold, height, s5held)


class LiveNowDriver(MapDownDriver):
    width, height = 1440, 900

    @contextmanager
    def session(self, c):
        from tests.helpers.chrome_driver import emulate_motion
        from tests.helpers.studio_session import FAKE_SID, collect_page_errors, second_session
        from tests.helpers.studio_session_rig import StudioSessionRig
        with StudioSessionRig() as rig:
            _seed(rig)
            second_session(rig)
            rows = Rows(rig)
            collect_page_errors(c)
            c.call("Page.addScriptToEvaluateOnNewDocument", source=CLOCK)
            emulate_motion(c, "no-preference")  # the hosted runners reduce motion; `reduced` sets each itself
            args = (c, rig, rows, rig.act.session_id, FAKE_SID)
            yield tuple((fn, args) for fn in STEPS if not self.argv or fn.__name__ in self.argv)


if __name__ == "__main__":
    sys.exit(LiveNowDriver(sys.argv[1:]).main())
