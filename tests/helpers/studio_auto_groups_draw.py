"""tests.helpers.studio_auto_groups_draw -- Auto's own groups as drawn (Halo 3.6.0.5 b/batch05 entries 2-4: B1 B7 B9-B13
B12a B30), in headless Chrome at 1280 x 800 over tests/helpers/studio_session_rig.py (this harness's real session A, its
rows set through GET live as tests/helpers/studio_session_run.py sets them: the row says `map: auto`, `map_plain: true`).
No model is called.

    scene   main alone (Session's drawer and Agents -> Live, both `data-map=auto`); then scene 2's two groups ("compare the
            three reports": three researchers; "fix the login bug": a coder) and a workflow run with no step frames (its
            member, not an empty block); group 1 does not move when group 2 comes; the same groups in Agents -> Live,
            column 1, no label on a line into a group
    lines   group 1's line live while a member works, then a trace weighing min(3, members); a map_hop frame lights nothing
    grow    a 60-character name, five count parts, a why line, a 60-character description, a child of a child's third
            line: nothing inside a group is cut, no ellipsis, no text under 12 px; the block on the drawer's full row
    five    five groups: group 5's colour is group 1's; the five names differ
    hover   hover a member: G4; a click: the card with the same "Why this model:" line; a click on a group's name: a row
            per live member with Pause and Stop; hover main: G5 from the row's map_agents
    slot    (batch 6, B26) a fifth group starts working wholly below the view: the slot names it in Session and in Agents
            -> Live, holds still, its press brings the head into view; his map hops: Agents -> Live has no slot
    focus   (batch 6, B27) group 4's card [Open in Agents -> Live] from Session and from Agents -> Live: its head at the
            top within 1 s, its border pulsing 2 s (timed in the page)
    scrolls (batch 7) Agents -> Live: React's commits while scrolling inside one group's span; a stored focus whose group
            is not placed is dropped; two presses of Open within the pulse
    heights (batch 8) Agents -> Live's slot at 1280x800, at 1280x1400 and back, with no scroll
    mainstill (k/batch02) main through done, a tool, the Agent tool, thinking, waiting on you, done: main's rect and
            group 1's rect in each state
    longest (batch 7-8, last: it narrows the drawer) Session's slot with the 60-character sample of ordinary letters,
            then a 25-character name, each with a two-digit count, at the default drawer width and at its narrowest

    python -m tests.helpers.studio_auto_groups_draw [step ...]
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

from tests.helpers.studio_session_map_down import MapDownDriver, Rows  # noqa: E402
from tests.helpers.studio_session_run import LINE, M, _hop, _kid, _main, _open, _seed  # noqa: E402

LONG = "compare the three quarterly reports and write the summary now"  # 60 characters
P = "[data-part=live]"
LW = f"document.querySelector('{P} [data-testid=live-world]')"
GROUP = f"(n) => {M}?.querySelector(`[data-testid=session-map-group][data-group=\"${{n}}\"]`)"
RECT = "(e) => { if (!e) return null; const r = e.getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; }"
PROBE = """(root, v) => { const s = document.createElement('span'); s.style.color = `var(${v})`; root.appendChild(s);
  const c = getComputedStyle(s).color; s.remove(); return c; }"""
HOVER = """(() => { const h = document.getElementById('halo-hover-card'); if (!h) return null;
  return [...h.querySelectorAll('[data-testid=session-map-hover-line]')].map((e) => e.textContent); })()"""


def member(aid: str, who: str, desc: str, task: str, n: int, *, state: str = "running", model: str = "kimi-k3", reason: str = "",
           parent: str = "main", by: str = "task", key: str = "", cost: float = 0.0) -> dict:
    k = _kid(aid, who, state, model=model, task=desc)
    k.update(parent=parent, cost_usd=cost, model_reason=reason or None,
             spawn={"step": "1", "description": desc, "task": task, "group": {"key": key or f"task:{task}", "n": n, "by": by}})
    return k


def scene2(t: float = 0.0) -> list:
    return [member(f"r{i}", "researcher", f"read report {x}", "compare the three reports", 1, reason="a pdf in the task")
            for i, x in enumerate("ABC", start=1)]


def _set(rows: Rows, a: str, agents: list, **kw) -> None:
    rows.set(a, map="auto", map_plain=True, busy=True, status="busy", agents=agents, **kw)


def _groups(c) -> list:
    return c.js(f"""[...{M}.querySelectorAll('[data-testid=session-map-group]')].map((g) => ({{n: g.dataset.group, colour: g.dataset.colour,
      rect: ({RECT})(g), border: getComputedStyle(g).borderTopColor, members: g.querySelectorAll('[data-member]').length,
      name: g.querySelector('[data-testid=map-group-name]')?.textContent || '', counts: g.querySelector('[data-testid=map-group-counts]')?.textContent || '',
      why: g.querySelector('[data-testid=map-group-why]')?.textContent || '',
      lines: [...g.querySelectorAll('[data-member]')].map((m) => [...m.querySelectorAll(':scope > span')].map((s) => s.textContent))}}))""")


def scene(c, rig, rows: Rows, a: str, b: str) -> dict:
    out: dict = {}
    main = _main(rows, a)
    _open(c, rig, rows, a, b, "auto", True, [main])
    out["alone"] = c.js(f"({{map: {M}.dataset.map, boxes: {M}.querySelectorAll('[data-box]').length, groups: {M}.querySelectorAll('[data-group]').length}})")
    _set(rows, a, [main, *scene2()])
    c.wait(f"({GROUP})(1)?.querySelectorAll('[data-member]').length === 3", 20)
    time.sleep(0.8)
    out["one"] = _groups(c)
    out["probe"] = c.js(f"Object.fromEntries(['--group-1', '--accent', '--warn', '--ok', '--bad'].map((v) => [v, ({PROBE})({M}, v)]))")
    coder = member("k1", "coder", "fix the login form", "fix the login bug", 2, model="glm-5")
    flow = member("q1", "reviewer", "review the change", "", 3, key="workflow:Q#tu3", by="workflow")
    # a square run (its step rows carry no crew tag, no map_step frame): its group shows its member, not an empty block
    _set(rows, a, [main, *scene2(), coder, flow])
    c.wait(f"!!({GROUP})(2) && !!({GROUP})(3)", 20)
    time.sleep(0.8)
    out["two"] = _groups(c)
    out["main"] = c.js(f"({RECT})({M}.querySelector('[data-box=main]'))")
    out["mainRows"] = c.js(f"{M}.querySelector('[data-box=main]').querySelectorAll('[data-testid=session-map-row]').length")
    c.click_on(f"document.querySelector('[data-testid=session-lit-open]')")
    c.wait(f"{LW}?.dataset.map === 'auto' && {LW}.querySelectorAll('[data-testid=live-group]').length === 3", 30)
    time.sleep(0.8)
    out["live"] = c.js(f"""(() => {{ const w = {LW}; return {{ map: w.dataset.map, main: ({RECT})(w.querySelector('[data-map-box=main]')),
      groups: [...w.querySelectorAll('[data-testid=live-group]')].map((g) => [g.dataset.group, ({RECT})(g)]),
      labels: [...w.querySelectorAll('[data-testid=live-label]')].map((l) => l.dataset.to) }}; }})()""")
    return {"scene": out}


def lines(c, rig, rows: Rows, a: str, b: str) -> dict:
    out: dict = {}
    main = _main(rows, a)
    coder = member("k1", "coder", "fix the login form", "fix the login bug", 2, state="done", model="glm-5")
    _open(c, rig, rows, a, b, "auto", True, [main, *scene2(), coder])
    c.wait(f"({LINE})('main', 'group:1')?.lit === 'live'", 20)
    out["live"] = c.js(f"({LINE})('main', 'group:1')")
    _hop(rig, a, "main", "group:2", "start")  # a map_hop frame on Auto: read by no drawing
    time.sleep(1.5)
    out["hop2"] = c.js(f"({LINE})('main', 'group:2')")
    _set(rows, a, [main, *[{**r, "state": "done"} for r in scene2()], coder])
    c.wait(f"({LINE})('main', 'group:1')?.lit === 'trace'", 20)
    out["trace"] = c.js(f"({LINE})('main', 'group:1')")
    return {"lines": out}


def grow(c, rig, rows: Rows, a: str, b: str) -> dict:
    main = _main(rows, a)
    kids = [member("g1", "researcher", LONG, LONG, 1, reason="a pdf in the task", cost=0.02),
            member("g2", "researcher", "read B", LONG, 1, state="waiting"), member("g3", "coder", "fix", LONG, 1, state="done", cost=0.01),
            member("g4", "coder", "fix two", LONG, 1, state="failed"),
            member("g5", "reviewer", "check a figure", LONG, 1, parent="g1")]
    _open(c, rig, rows, a, b, "auto", True, [main, *kids])
    c.wait(f"({GROUP})(1)?.querySelectorAll('[data-member]').length === 5", 20)
    time.sleep(1.0)
    return {"grow": c.js(f"""(() => {{ const g = ({GROUP})(1), all = [g, ...g.querySelectorAll('*')];
      const clip = all.filter((e) => e.scrollHeight > e.clientHeight + 1 && getComputedStyle(e).overflowY !== 'visible').map((e) => e.className || e.tagName);
      const cut = all.filter((e) => getComputedStyle(e).overflow === 'hidden' && e.scrollHeight > e.clientHeight + 1).map((e) => e.className || e.tagName);
      const ell = all.filter((e) => getComputedStyle(e).textOverflow === 'ellipsis').length;
      const small = all.filter((e) => [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim()) && parseFloat(getComputedStyle(e).fontSize) < 12).length;
      const inner = g.querySelector('.mp-inner'), box = g.getBoundingClientRect(), ib = inner.getBoundingClientRect();
      const world = {M}.querySelector('.mp-mini-world'), k = parseFloat(world.dataset.zoom) || 1;
      return {{ clip, cut, ell, small, w: box.width / k, h: box.height / k, inner: ib.height / k, left: (box.left - world.getBoundingClientRect().left) / k,
        world: world.getBoundingClientRect().width / k, members: [...g.querySelectorAll('[data-member]')].map((m) => [m.dataset.member, m.getBoundingClientRect().width / k, m.getBoundingClientRect().height / k]),
        name: g.querySelector('[data-testid=map-group-name]').textContent, counts: g.querySelector('[data-testid=map-group-counts]').textContent,
        bad: g.querySelector('[data-testid=map-group-counts] .mp-bad')?.textContent || '', why: g.querySelector('[data-testid=map-group-why]')?.textContent || '',
        third: g.querySelector('[data-member=g5] [data-testid=map-member-by]')?.textContent || '' }}; }})()""")}


def five(c, rig, rows: Rows, a: str, b: str) -> dict:
    main = _main(rows, a)
    kids = [member(f"f{i}", "coder", f"part {i}", f"task number {i}", i, model="glm-5") for i in range(1, 6)]
    _open(c, rig, rows, a, b, "auto", True, [main, *kids])
    c.wait(f"!!({GROUP})(5)", 20)
    time.sleep(0.6)
    return {"five": _groups(c)}


def hover(c, rig, rows: Rows, a: str, b: str) -> dict:
    from tests.helpers.studio_session_step_in import _rest_on
    out: dict = {}
    main = _main(rows, a, model="glm-5")
    kids = [member("h1", "researcher", "read report A", "compare", 1, reason="code work; tools; mid budget", cost=0.01),
            member("h2", "researcher", "read report B", "compare", 1), member("h3", "researcher", "read report C", "compare", 1, state="done")]
    _open(c, rig, rows, a, b, "auto", True, [main, *kids])
    rows.set(a, map_agents=["coder", "reviewer", "writer"])
    mem = f"{M}.querySelector('[data-member=h1]')"
    c.wait(f"!!{mem}", 20)
    time.sleep(1.0)
    _rest_on(c, f"{M}.querySelector('[data-box=main] .mp-name')")  # main first, at the drawer's top (on its name)
    c.wait("document.getElementById('halo-hover-card')?.dataset.for?.endsWith(':main')", 10)
    out["g5"] = c.js(HOVER)
    _rest_on(c, mem)  # then the member (the drawer brought down to it when it is below the edge)
    c.wait("document.getElementById('halo-hover-card')?.dataset.for?.endsWith(':h1')", 10)
    out["g4"] = c.js(HOVER)
    c.mouse("mouseMoved", 1279, 799)
    c.wait("!document.getElementById('halo-hover-card')", 5)
    c.click_on(mem)
    c.wait("!!document.querySelector('[data-testid=map-step-in-why]')", 10)
    out["card"] = c.js("""({title: document.querySelector('[data-testid=map-step-in-title]')?.textContent || '',
      why: document.querySelector('[data-testid=map-step-in-why]')?.textContent || '', sel: !!document.querySelector('[data-member=h1][data-selected]')})""")
    c.js("document.querySelector('[data-testid=map-step-in-close]')?.click(); 1")
    c.wait("!document.querySelector('[data-testid=map-step-in]')", 10)
    c.click_on(f"{M}.querySelector('[data-testid=map-group-name]')")
    c.wait("!!document.querySelector('[data-testid=map-step-in]')", 10)
    out["group"] = c.js("""({title: document.querySelector('[data-testid=map-step-in-title]')?.textContent || '',
      rows: [...document.querySelectorAll('[data-testid=map-step-in-row]')].map((r) => [r.dataset.key.split('|').pop(),
        !!r.querySelector('[data-testid=map-step-in-pause]'), !!r.querySelector('[data-testid=map-step-in-stop]')]),
      actions: ((a) => a ? [(a.dataset.key || '').split('|').pop(), a.querySelectorAll('[data-testid=map-step-in-pause]').length,
        a.querySelectorAll('[data-testid=map-step-in-stop]').length] : null)(document.querySelector('[data-testid=map-step-in-actions]')),
      sel: !!document.querySelector('[data-testid=session-map-group][data-selected]')})""")
    c.js("document.querySelector('[data-testid=map-step-in-close]')?.click(); 1")
    c.wait("!document.querySelector('[data-testid=map-step-in]')", 10)
    # 3.6.0.13 L3 (R8): once main was told what it can start, its hover says the session's counts and the kinds it was told
    c.mouse("mouseMoved", 1279, 799)
    c.wait("!document.getElementById('halo-hover-card')", 5)
    rows.set(a, agents=[{**main, "turn_total": {"helpers": 3, "tools": 4}}, *kids], kinds_told=["coder", "reviewer", "writer"],
             kinds_more=0)
    try:
        c.wait(f"!!{M}.querySelector('[data-box=main]')", 10)
        c.js(f"{M}.querySelector('.mp-mini-scroll').scrollTop = 0; 1")  # main at the drawer's top again (the member hover scrolled)
        time.sleep(1.0)
        _rest_on(c, f"{M}.querySelector('[data-box=main] .mp-name')")
        c.wait("(document.getElementById('halo-hover-card')?.textContent || '').includes('Told it can start')", 10)
    except TimeoutError:
        pass  # the reading says what it showed
    out["told"] = c.js(HOVER)
    return {"hover": out}


NAMES = [f"part {i} of the basket work" for i in range(1, 6)]
MORE = f"{M}?.querySelector('[data-testid=map-more-below]')"
SLOT = f"{M}?.querySelector('[data-testid=session-map-below]')"
LSLOT = f"document.querySelector('{P} [data-testid=live-below]')"
LMORE = f"document.querySelector('{P} [data-testid=live-more-below]')"
LGROUP = f"(n) => document.querySelector(`{P} [data-testid=live-group][data-group=\"${{n}}\"]`)"
# where group n's head stands against its scroll box's top (0 = at the top), and whether it lies inside the visible part
AT = """((g, s) => { if (!g || !s) return null; const a = g.getBoundingClientRect(), b = s.getBoundingClientRect();
  return {d: a.top - b.top - s.clientTop, inside: a.top >= b.top - 1 && a.top < b.top + s.clientHeight}; })"""


def _five(fifth: str) -> list:
    """Five groups of three coders; the first four done, the fifth `fifth`."""
    return [member(f"s{i}{j}", "coder", f"step {j} of part {i}", NAMES[i - 1], i, state="done" if i < 5 else fifth, model="glm-5")
            for i in range(1, 6) for j in range(1, 4)]


def slot(c, rig, rows: Rows, a: str, b: str) -> dict:
    """B26: a fifth group starts working wholly below the view: the slot names it (Session, then Agents -> Live), holds
    still, and its press brings the head into view; on a map of his Agents -> Live has no slot."""
    out: dict = {}
    main = _main(rows, a)
    _open(c, rig, rows, a, b, "auto", True, [main, *_five("done")])
    c.wait(f"!!({GROUP})(5)", 20)
    time.sleep(1.0)
    read = (f"({{rect: ({RECT})({SLOT}), text: {MORE}?.textContent || '', button: ({RECT})({MORE}), "
            f"cols: getComputedStyle({SLOT}).gridTemplateColumns}})")
    out["before"] = c.js(read)
    _set(rows, a, [main, *_five("running")])
    c.wait(f"({MORE})?.textContent.startsWith('↓ {NAMES[4]} · working')", 20)
    time.sleep(0.5)
    out["after"] = c.js(read)
    c.click_on(MORE)
    scroll = f"{M}.querySelector('.mp-mini-scroll')"
    try:
        out["press"] = c.wait(f"(() => {{ const r = ({AT})(({GROUP})(5), {scroll}); return r && Math.abs(r.d) <= 1 && r; }})()", 5)
    except TimeoutError:
        out["press"] = c.js(f"({AT})(({GROUP})(5), {scroll})")
    c.click_on("document.querySelector('[data-testid=session-lit-open]')")
    c.wait(f"{LW}?.dataset.map === 'auto' && {LW}.querySelectorAll('[data-testid=live-group]').length === 5", 30)
    c.wait(f"({LMORE})?.textContent.startsWith('↓ {NAMES[4]} · working')", 20)
    lread = f"({{rect: ({RECT})({LSLOT}), scroll: ({RECT})(document.querySelector('{P} [data-testid=live-scroll]')), text: {LMORE}?.textContent || ''}})"
    out["live"] = c.js(lread)
    _set(rows, a, [main, *_five("done")])
    c.wait(f"!{LMORE}", 20)
    out["live_empty"] = c.js(lread)
    _set(rows, a, [main, *_five("running")])
    c.wait(f"!!{LMORE}", 20)
    c.click_on(LMORE)
    lscroll = f"document.querySelector('{P} [data-testid=live-scroll]')"
    try:
        out["live_press"] = c.wait(f"(() => {{ const r = ({AT})(({LGROUP})(5), {lscroll}); return r && r.inside && r; }})()", 5)
    except TimeoutError:
        out["live_press"] = c.js(f"({AT})(({LGROUP})(5), {lscroll})")
    _open(c, rig, rows, a, b, "hops", False, [main])  # his map: Agents -> Live as before, no slot
    c.click_on("document.querySelector('[data-testid=session-lit-open]')")
    c.wait(f"{LW}?.dataset.map === 'hops'", 30)
    time.sleep(0.5)
    out["his"] = c.js(f"({{slot: !!{LSLOT}, frame: [...document.querySelector('{P} [data-testid=live-frame]').children].map((e) => e.dataset.testid || e.className)}})")
    return {"slot": out}


# B27: from the press, in the page: when group n's head first stands at its scroll box's top (or, when the drawing ends
# before that -- Auto's wide column of 3.6.0.15 L9a makes groups shorter -- the box scrolled to its end with the head in
# view: `end`), when data-pulse came, when it left
WATCH = """((n) => { const w = window.__focus = {t0: performance.now(), top: null, end: null, on: null, off: null};
  const tick = () => { const s = document.querySelector('[data-part=live] [data-testid=live-scroll]');
    const g = s && s.querySelector(`[data-testid=live-group][data-group="${n}"]`), t = performance.now() - w.t0;
    if (g && s.offsetParent) { const d = g.getBoundingClientRect().top - s.getBoundingClientRect().top - s.clientTop;
      const last = s.scrollTop > 0 && s.scrollTop >= s.scrollHeight - s.clientHeight - 1 && d >= -1 && d < s.clientHeight;
      if (w.top == null && (Math.abs(d) <= 1 || last)) (w.top = t), (w.end = Math.abs(d) > 1);
      if (g.hasAttribute('data-pulse')) { if (w.on == null) w.on = t; } else if (w.on != null && w.off == null) w.off = t; }
    if (w.off == null && t < 8000) requestAnimationFrame(tick); };
  requestAnimationFrame(tick); return 1; })"""
VIEW = "document.querySelector('[data-testid=agents]')?.dataset.view"


def focus(c, rig, rows: Rows, a: str, b: str) -> dict:
    """B27: group 4's card [Open in Agents -> Live], from Session and from Agents -> Live itself."""
    out: dict = {}
    main = _main(rows, a)
    _open(c, rig, rows, a, b, "auto", True, [main, *_five("running")])
    c.wait(f"!!({GROUP})(5)", 20)
    time.sleep(1.0)
    c.click_on(f"({GROUP})(4).querySelector('[data-testid=map-group-name]')")
    c.wait("document.querySelector('[data-testid=map-step-in]')?.dataset.target === 'group:4'", 10)
    c.js(f"{WATCH}(4)")
    c.click_on("document.querySelector('[data-testid=map-step-in-live]')")
    out["session"] = c.wait("window.__focus.off != null && window.__focus", 12)
    out["session_view"] = c.js(VIEW)
    c.js("document.querySelector('[data-part=live] [data-testid=live-scroll]').scrollTop = 0; 1")
    time.sleep(0.5)
    c.click_on(f"({LGROUP})(4).querySelector('[data-testid=map-group-name]')")
    c.wait(f"document.querySelector('{P} [data-testid=map-step-in]')?.dataset.target === 'group:4'", 10)
    c.js(f"{WATCH}(4)")
    c.click_on(f"document.querySelector('{P} [data-testid=map-step-in-live]')")
    out["live"] = c.wait("window.__focus.off != null && window.__focus", 12)
    out["live_view"] = c.js(VIEW)
    out["card"] = c.js(f"!!document.querySelector('{P} [data-testid=map-step-in]')")
    # the release gate of 3.6.0.5 (the hosted Windows and macOS runners reduce motion): with reduced motion the cue stays
    # its 2 s as a still outline; base.css ends every animation at once there, and the pulse's END takes data-pulse off
    c.call("Emulation.setEmulatedMedia", features=[{"name": "prefers-reduced-motion", "value": "reduce"}])
    try:
        out["reduced_media"] = c.js("matchMedia('(prefers-reduced-motion: reduce)').matches")
        c.js("document.querySelector('[data-part=live] [data-testid=live-scroll]').scrollTop = 0; 1")
        time.sleep(0.5)
        c.click_on(f"({LGROUP})(4).querySelector('[data-testid=map-group-name]')")
        c.wait(f"document.querySelector('{P} [data-testid=map-step-in]')?.dataset.target === 'group:4'", 10)
        c.js(f"{WATCH}(4)")
        c.click_on(f"document.querySelector('{P} [data-testid=map-step-in-live]')")
        out["reduced"] = c.wait("window.__focus.off != null && window.__focus", 12)
    finally:
        c.call("Emulation.setEmulatedMedia", features=[])
    return {"focus": out}


# b/batch07 entry 3: a counter of React's commits, added by this rig before the page loads (React calls a devtools hook
# when one is there; nothing of the product's) -- only for the step that counts
HOOK = """(() => { window.__commits = 0; window.__REACT_DEVTOOLS_GLOBAL_HOOK__ = { supportsFiber: true, isDisabled: false,
  renderers: new Map(), inject() { return 1; }, checkDCE() {}, onScheduleFiberRoot() {}, onCommitFiberUnmount() {},
  onPostCommitFiberRoot() {}, onCommitFiberRoot() { window.__commits += 1; } }; })();"""
LSCROLL = f"document.querySelector('{P} [data-testid=live-scroll]')"
# 40 small scroll steps (2 px a frame) inside group 3's span, against 40 idle frames just before
COUNT = f"""(async () => {{ const s = {LSCROLL}, g = s.querySelector('[data-testid=live-group][data-group="3"]');
  const fr = () => new Promise((r) => requestAnimationFrame(() => r()));
  const top = s.scrollTop + g.getBoundingClientRect().top - s.getBoundingClientRect().top;
  s.scrollTop = top + 4; for (let i = 0; i < 10; i++) await fr();
  const c0 = window.__commits; for (let i = 0; i < 40; i++) await fr(); const idle = window.__commits - c0;
  const c1 = window.__commits; for (let i = 0; i < 40; i++) {{ s.scrollTop += 2; await fr(); }} for (let i = 0; i < 3; i++) await fr();
  return {{hooked: window.__commits > 0, idle, scroll: window.__commits - c1, span: g.getBoundingClientRect().height,
    moved: Math.round(s.scrollTop - top - 4)}}; }})()"""
# for `ms` from now: did the scroll box move, did any group pulse
STILL = f"""((ms) => {{ const s = {LSCROLL}, w = window.__still = {{top: s.scrollTop, moved: false, pulsed: false, done: false}}, t0 = performance.now();
  const tick = () => {{ if (Math.abs(s.scrollTop - w.top) > 1) w.moved = true;
    if (s.querySelector('[data-testid=live-group][data-pulse]')) w.pulsed = true;
    if (performance.now() - t0 < ms) requestAnimationFrame(tick); else w.done = true; }};
  requestAnimationFrame(tick); return 1; }})"""
# group n's data-pulse as each batch of mutations leaves it, and every press of a card's Open in Agents -> Live
PULSES = f"""((n) => {{ const g = ({LGROUP})(n), w =window.__pulses = {{t0: performance.now(), presses: [], states: []}};
  document.addEventListener('click', (e) => {{ if (e.target.closest('[data-testid=map-step-in-live]')) w.presses.push(performance.now() - w.t0); }}, true);
  new MutationObserver(() => w.states.push([performance.now() - w.t0, g.hasAttribute('data-pulse')])).observe(g, {{attributes: true, attributeFilter: ['data-pulse']}});
  return 1; }})"""


def _twelve(gone: int = 0) -> list:
    return [member(f"t{i}{j}", "coder", f"step {j} of job {i}", f"job number {i}", i, state="done", model="glm-5")
            for i in range(1, 13) if i != gone for j in range(1, 4)]


def _live_open(c, n: int) -> None:
    """Group n's card in Agents -> Live, then its Open in Agents -> Live (clicks in the page: two presses well inside 2 s)."""
    c.js(f"({LGROUP})({n}).querySelector('[data-testid=map-group-name]').click(); 1")
    c.wait(f"document.querySelector('{P} [data-testid=map-step-in]')?.dataset.target === 'group:{n}'", 10)
    c.js(f"document.querySelector('{P} [data-testid=map-step-in-live]').click(); 1")


def scrolls(c, rig, rows: Rows, a: str, b: str) -> dict:
    """b/batch07 entry 3 (Auto only): scrolling Agents -> Live inside one group's span commits nothing new; a stored focus
    whose group is not placed at the drawing's first full draw is dropped (nothing jumps when it comes later); two presses
    of a group card's Open within the pulse leave one pulse, ending 2 s after the last press."""
    out: dict = {}
    # the Page domain is on for the whole run (collect_page_errors), so this script runs on the pages loaded below
    ident = (c.call("Page.addScriptToEvaluateOnNewDocument", source=HOOK) or {}).get("identifier")
    try:
        main = _main(rows, a)
        _open(c, rig, rows, a, b, "auto", True, [main, *_twelve()])
        c.wait(f"!!({GROUP})(12)", 20)
        time.sleep(1.0)
        # the stored focus: group 6's card in Session, group 6 gone from the rows, then its Open in Agents -> Live
        c.click_on(f"({GROUP})(6).querySelector('[data-testid=map-group-name]')")
        c.wait("document.querySelector('[data-testid=map-step-in]')?.dataset.target === 'group:6'", 10)
        _set(rows, a, [main, *_twelve(gone=6)])
        c.wait(f"!({GROUP})(6) && !!({GROUP})(12)", 20)
        c.click_on("document.querySelector('[data-testid=map-step-in-live]')")
        c.mouse("mouseMoved", 2, 400)  # the pointer off the frame (on the rail): a box that moves is drawn at once (R12)
        c.wait(f"{LW}?.dataset.map === 'auto' && {LW}.querySelectorAll('[data-testid=live-group]').length === 11", 30)
        time.sleep(1.5)  # its first full draw (placed and measured) has passed
        c.js(f"{STILL}(3000)")
        _set(rows, a, [main, *_twelve()])
        c.wait(f"!!({LGROUP})(6)", 20)
        out["stale"] = c.wait("window.__still.done && window.__still", 10)
        # the commits of 40 small scroll steps inside one group's span
        out["count"] = c.wait(COUNT, 20)
        # two presses of group 4's Open within its pulse
        c.js(f"{LSCROLL}.scrollTop = 0; 1")
        time.sleep(0.5)
        c.js(f"{PULSES}(4)")
        _live_open(c, 4)
        time.sleep(0.6)
        _live_open(c, 4)
        c.wait(f"window.__pulses.presses.length === 2 && performance.now() - window.__pulses.t0 > window.__pulses.presses[1] + 3500", 12)
        out["twice"] = c.js(f"({{...window.__pulses, end: ({LGROUP})(4).hasAttribute('data-pulse')}})")
    finally:
        if ident:
            c.call("Page.removeScriptToEvaluateOnNewDocument", identifier=ident)
    return {"scrolls": out}


def _twelfth(state: str) -> list:
    """Twelve groups, the twelfth `state`, the others done."""
    return [member(f"h{i}{j}", "coder", f"step {j} of job {i}", f"job number {i}", i, state=state if i == 12 else "done", model="glm-5")
            for i in range(1, 13) for j in range(1, 4)]


# b/batch08 entry 2: the page's interval timers (the drawing's one-second clock among them) skip their calls while
# window.__frozen is set, so nothing but the view's own size can give the slot a new answer -- only for the step that
# measures it (added before the page loads, removed after)
FREEZE = """(() => { const si = window.setInterval; window.__frozen = false;
  window.setInterval = (fn, ms, ...a) => si((...b) => { if (!window.__frozen && typeof fn === 'function') fn(...b); }, ms, ...a); })();"""


def heights(c, rig, rows: Rows, a: str, b: str) -> dict:
    """b/batch08 entry 2 (B26, Auto): Agents -> Live's slot says what is out of sight right after the window's height
    changes, with no scroll and the page's clock held: 1280x800, then 1280x1400, then back."""
    out: dict = {}
    ident = (c.call("Page.addScriptToEvaluateOnNewDocument", source=FREEZE) or {}).get("identifier")
    try:
        main = _main(rows, a)
        _open(c, rig, rows, a, b, "auto", True, [main, *_twelfth("running")])
        c.wait(f"!!({GROUP})(12)", 20)
        c.click_on("document.querySelector('[data-testid=session-lit-open]')")
        c.mouse("mouseMoved", 2, 400)  # the pointer off the frame (R12)
        c.wait(f"{LW}?.dataset.map === 'auto' && {LW}.querySelectorAll('[data-testid=live-group]').length === 12", 30)
        c.wait(f"({LMORE})?.textContent.startsWith('↓ job number 12 · working')", 20)
        time.sleep(0.5)
        read = (f"({{text: {LMORE}?.textContent || '', top: {LSCROLL}.scrollTop, h: {LSCROLL}.clientHeight, "
                f"vw: [innerWidth, innerHeight], hooked: String(window.setInterval).includes('__frozen')}})")
        vw = c.js("[innerWidth, innerHeight]")
        c.js("window.__frozen = true; 1")
        out["first"] = first = c.js(read)
        differs = f"(({LMORE})?.textContent || '') !== {json.dumps(first.get('text') or '')}"
        c.call("Emulation.setDeviceMetricsOverride", width=vw[0], height=1400, deviceScaleFactor=1, mobile=False)
        try:
            c.wait(differs, 5)
        except TimeoutError:
            pass  # the reading below says what stayed
        out["tall"] = c.js(read)
        c.call("Emulation.setDeviceMetricsOverride", width=vw[0], height=vw[1], deviceScaleFactor=1, mobile=False)
        try:
            c.wait(f"!({differs})", 5)
        except TimeoutError:
            pass
        out["back"] = c.js(read)
    finally:
        c.js("window.__frozen = false; 1")
        if ident:
            c.call("Page.removeScriptToEvaluateOnNewDocument", identifier=ident)
    return {"heights": out}


SAMPLE = "compare the three reports and write the summary for the team"  # 60 characters: groupWords.ts BELOW_SAMPLE
SHORT = "compare the three reports"  # 25 characters
SCROLLBOX = f"{M}?.querySelector('.mp-mini-scroll')"
TWIN = f"{SLOT}?.querySelector('.mp-below-twin')"


def _sixteen(fifth: str, name: str = SAMPLE) -> list:
    """Sixteen groups of three coders; the fifth named `name` and `fifth`, the others done."""
    return [member(f"x{i}{j}", "coder", f"step {j} of part {i}", name if i == 5 else f"part {i} of the long run", i,
                   state=fifth if i == 5 else "done", model="glm-5") for i in range(1, 17) for j in range(1, 4)]


def longest(c, rig, rows: Rows, a: str, b: str) -> dict:
    """b/batch08 entry 1 (B26): the slot's rect and the scroll box's rect are the same at the first draw and once the slot
    names the fifth of sixteen groups with a two-digit count -- the 60-character sample, then a 25-character name -- at
    the default drawer width and at its narrowest; the twin's rect is read beside them."""
    from tests.helpers.studio_run_parts import settled
    out: dict = {"len": len(SAMPLE), "short": len(SHORT)}
    main = _main(rows, a)
    read = (f"({{slot: ({RECT})({SLOT}), scroll: ({RECT})({SCROLLBOX}), twin: ({RECT})({TWIN}), "
            f"wait: ({RECT})({SLOT}?.querySelector(':scope > .mp-wait-row')), text: {MORE}?.textContent || '', "
            f"lh: parseFloat(getComputedStyle({TWIN}).lineHeight) || 0}})")
    named = lambda name: f"({MORE})?.textContent.startsWith('↓ {name} · working')"  # noqa: E731

    def pair(tag: str, name: str) -> None:
        _set(rows, a, [main, *_sixteen("done", name)])
        c.wait(f"!({named(name)}) && !!({GROUP})(16)", 20)
        out[f"{tag}first"] = settled(c, read)
        _set(rows, a, [main, *_sixteen("running", name)])
        c.wait(named(name), 20)
        time.sleep(0.5)
        out[f"{tag}named"] = c.js(read)

    _open(c, rig, rows, a, b, "auto", True, [main, *_sixteen("done")])
    c.wait(f"!!({GROUP})(16)", 20)
    time.sleep(1.0)
    pair("", SAMPLE)
    pair("short_", SHORT)
    # the drawer at its least width (as tests/helpers/studio_run_parts.py drags it)
    drawer = f"{SLOT}?.closest('[data-testid=stage-drawer]')"
    _set(rows, a, [main, *_sixteen("done")])
    c.wait(f"!({named(SAMPLE)}) && !({named(SHORT)})", 20)
    for _ in range(3):
        sp = c.js(f"""(() => {{ const d = {drawer};
          const s = d?.querySelector(':scope > [data-testid=stage-splitter]'); if (!s) return null; const r = s.getBoundingClientRect();
          return [r.left + r.width / 2, r.top + r.height / 2, d.dataset.side, +s.getAttribute('aria-valuemin'), Math.round(d.getBoundingClientRect().width)]; }})()""")
        if not sp or sp[4] <= sp[3]:
            break
        c.drag(sp[0], sp[1], sp[0] + (-600 if sp[2] == "left" else 600), sp[1])
        c.mouse("mouseMoved", 1279, 799)
        settled(c, f"Math.round({drawer}?.getBoundingClientRect().width || 0)")
    out["drawer"] = c.js(f"[Math.round({drawer}?.getBoundingClientRect().width || 0), +({drawer}?.querySelector(':scope > [data-testid=stage-splitter]')?.getAttribute('aria-valuemin') || 0)]")
    pair("narrow_", SAMPLE)
    pair("narrow_short_", SHORT)
    return {"longest": out}


# k/batch02 entry 1: main's states on Auto, each with what its box's rows then say (the fullest: a two-line row and the
# model wait's clock)
# 3.6.0.13 L3: the first state has no turn yet (the rig's own row has one), the last ends a turn with its counts
MAIN_STATES = [("done", {"state": "done", "current": "", "turn": None}), ("tool", {"state": "running", "current": "Bash: pytest -q"}),
               ("agent", {"state": "running", "current": "Agent: read report C"}), ("thinking", {"state": "running", "current": "thinking"}),
               ("waiting", {"state": "waiting", "current": ""}),
               # 3.6.0.13 L3: the turn ended with its counts: TURN under NOW, in the room held from the first draw
               ("done again", {"state": "done", "current": "", "turn": {"n": 1, "helpers": 12, "tools": 14, "ended": True}})]
MAIN_SAYS = {"done": "main · done", "tool": "main · working · Bash pytest -q", "agent": "main · working · Agent read report C",
             "thinking": "main · working · thinking", "waiting": "main · waiting on you", "done again": "main · done"}
MAIN_BOX = f"{M}?.querySelector('[data-box=main]')"


def mainstill(c, rig, rows: Rows, a: str, b: str) -> dict:
    """k/batch02 entry 1 (Auto): main's box driven through done, a tool, the Agent tool, thinking (waiting for a model
    reply), waiting on you and done: main's rect and group 1's rect, and what main's rows say, in every state."""
    from tests.helpers.studio_run_parts import settled
    out: dict = {"states": []}
    since = time.time() - 2
    main = _main(rows, a, since=since, started=since, **MAIN_STATES[0][1])
    _open(c, rig, rows, a, b, "auto", True, [main, *scene2()])
    c.wait(f"({GROUP})(1)?.querySelectorAll('[data-member]').length === 3", 20)
    read = (f"({{main: ({RECT})({MAIN_BOX}), one: ({RECT})(({GROUP})(1)), "
            f"row: {MAIN_BOX}?.querySelector('.mp-lit-row[data-state]')?.textContent || '', "
            f"clock: ({MAIN_BOX}?.querySelector('[data-testid=map-main-now]')?.textContent || '').trim(), "
            f"turn: {MAIN_BOX}?.querySelector('[data-testid=map-main-turn]')?.textContent ?? null}})")
    for name, over in MAIN_STATES:
        _set(rows, a, [_main(rows, a, since=since, started=since, **over), *scene2()])
        try:
            c.wait(f"({MAIN_BOX}?.querySelector('.mp-lit-row[data-state]')?.textContent || '') === {json.dumps(MAIN_SAYS[name])}", 15)
        except TimeoutError:
            pass  # the reading says what it showed
        if name == "thinking":
            try:
                c.wait(f"({MAIN_BOX}?.querySelector('[data-testid=map-main-now]')?.textContent || '').startsWith('waiting for a model reply')", 10)
            except TimeoutError:
                pass
        out["states"].append({"state": name, **settled(c, read)})
    return {"mainstill": out}


class AutoGroupsDriver(MapDownDriver):
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
            steps = [s for s in (scene, lines, grow, five, hover, slot, focus, scrolls, heights, mainstill, longest)
                     if not self.argv or s.__name__ in self.argv]
            yield tuple((fn, args) for fn in steps)


if __name__ == "__main__":
    sys.exit(AutoGroupsDriver(sys.argv[1:]).main())
