"""tests.helpers.studio_session_just_built -- what was just built, shown at once (Halo 3.6.0.2 R26-R32), in headless
Chrome at 1280 x 800 over tests/helpers/studio_session_rig.py (this harness's real session A, a second session B). Every
fact reaches the page through GET live's rows (`Rows`) and the feed's frames (`builder_done` published as P2b sends it,
`files_changed` from Studio's own watcher). No model is called.

    word    the drawer closed: the view-bar word slot is there and empty, an applied build writes 'new' in it and nothing
            else moves, opens or pops up; opening the drawer empties it
    same    a same-name edit by a Builder card redraws from the frame's body; a plain file write redraws the open drawing
            with no 'new'; closed and opened again it is the newest version
    once    the pair: with one map no row at all, two maps 'Running: {A} | Just built: {B}'; Just built chosen once, only
            while the pointer is outside and the pair was never pressed
    heads   the three Just built heads (+ R36's sentence, S13 once in the drawer), the 'new {t}' tags, [Open in Workflows]
            on its own row, tags kept over turns, gone when it ends; no control moves when a head lands (the drawing moves
            down once, inside its own box), a long head's words whole at 1280 and in a 412 px drawer, and a frame that
            changes nothing in its words moves nothing (P3 batch 8)
    room    one map, nothing built, at 1280 x 800, 1440 x 900 and 1920 x 1080: the drawing's box (no pair row, no head
            room) and the '↓ n more below' words against the boxes wholly below (P3 batch 8)
    fetch   nothing waits on the network: the head painted while every crew/map answer is held, one soft read for the
            running map, none for a body the frame brought, one for a body left out, none for left / failed / T4 / T10 / T8 / Empty,
            a removed map says so with no failed /api

    python -m tests.helpers.studio_session_just_built [step ...]
The last stdout line is a JSON object of what it saw.
"""
from __future__ import annotations

import sys
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.scratch_seven import NAME as SEVEN, write_seven  # noqa: E402
from tests.helpers.studio_session_map_down import FLEET_READS, MapDownDriver, Rows, _reload, _seed_shop  # noqa: E402

Q = "document.querySelector"
BTN = f"{Q}('[data-testid=viewbar-btn][data-panel=session-map]')"
WORD = f"{BTN}?.querySelector('[data-testid=viewbar-word]')"
PAIR = f"{Q}('[data-testid=session-map-pair]')"
HEAD = f"{Q}('[data-testid=session-built-head]')"
DRAWN = f"{Q}('[data-testid=session-lit-map]')"
FLOW_SOLO = {"format": "workflow/1", "name": "solo", "for": "solo", "steps": [{"name": "one", "agents": ["coder"]}]}
THIRD = """format: map/1
name: third
boxes:
- {id: helper, agent: writer}
lines:
- {from: main, to: helper, when: always}
"""
REVIEW_FLOW = """format: map/1
name: review-flow
boxes:
- {id: review, workflow: review}
lines:
- {from: main, to: review, when: always}
"""
FLOW_REVIEW = {"format": "workflow/1", "name": "review", "for": "review",
               "steps": [{"name": "code", "agents": ["coder"]}, {"name": "review", "agents": ["reviewer"]}]}
# the page's event feed opened (a frame sent before it is lost); the maps each `files_changed` frame named; every /api
# request with its answer's status
HOOKS = r"""(() => { if (window.__jb) return; const jb = window.__jb = { open: 0, reqs: [], held: [], hold: false, fc: [] };
  const ES = window.EventSource; if (ES) { const W = function (u, o) { const es = new ES(u, o);
    es.addEventListener('open', () => { jb.open += 1; });
    es.addEventListener('files_changed', (e) => { try { const d = JSON.parse(e.data).data || {};
      if (d.kind === 'maps') jb.fc.push([...(d.names || []), ...(d.removed || [])]); } catch (x) { jb.fc.push(['?']); } });
    return es; }; W.prototype = ES.prototype; window.EventSource = W; }
  const f = window.fetch.bind(window);
  window.fetch = (u, o) => { const s = String(u && u.url || u); if (!/\/api\//.test(s)) return f(u, o);
    const r = { url: s.replace(/^.*?\/api\//, ''), status: 0, t: performance.now() }; jb.reqs.push(r);
    const go = () => f(u, o).then((x) => { r.status = x.status; return x; });
    if (jb.hold && /^crew\/map\//.test(r.url)) return new Promise((ok) => jb.held.push(ok)).then(go);
    return go(); }; })();"""
MAPREQS = "window.__jb.reqs.filter((r) => /^crew\\/map\\//.test(r.url))"
RECTS = "[...document.querySelectorAll('[data-testid=viewbar-btn]')].map((b) => { const r = b.getBoundingClientRect(); return [b.dataset.panel, r.left, r.top, r.width, r.height]; })"
BOXES = "[...document.querySelectorAll('[data-testid=session-lit-map] [data-box]')]"
# the drawer's controls (none may move when a head lands), the head's parts and the drawing's top (whole rects, half-px)
CONTROLS = ["session-lit-open", "canvas-zoom-out", "canvas-zoom-level", "canvas-zoom-in", "canvas-fit", "session-map-below"]
CTRLS = """(() => { const r = (s) => { const e = document.querySelector(s); if (!e) return null; const b = e.getBoundingClientRect();
  return [b.left, b.top, b.width, b.height].map((x) => Math.round(x * 2) / 2); };
  const sc = document.querySelector('.mp-down .mp-mini-scroll')?.getBoundingClientRect();
  const out = Object.fromEntries(['session-lit-open', 'canvas-zoom-out', 'canvas-zoom-level', 'canvas-zoom-in', 'canvas-fit',
    'session-built-head', 'session-built-text', 'session-built-open', 'session-map-below'].map((t) => [t, r(`.mp-down [data-testid=${t}]`)]));
  out.scrollTop = sc ? Math.round(sc.top * 2) / 2 : null; return out; })()"""
# the head's words: whole (never clamped, the last word inside the box and the drawing's room), the button on its own row
WHOLE = """(() => { const t = document.querySelector('.mp-down [data-testid=session-built-text]'); if (!t) return null;
  const cs = getComputedStyle(t), box = t.getBoundingClientRect(), room = t.closest('.mp-down-room')?.getBoundingClientRect();
  const b = t.closest('[data-testid=session-built-head]')?.querySelector('[data-testid=session-built-open]')?.getBoundingClientRect();
  const node = [...t.childNodes].reverse().find((n) => n.nodeType === 3 && n.nodeValue.length); let last = null;
  if (node) { const g = document.createRange(); g.setStart(node, node.nodeValue.length - 1); g.setEnd(node, node.nodeValue.length);
    const q = g.getBoundingClientRect(); last = { inBox: q.bottom <= box.bottom + 0.5 && q.right <= box.right + 0.5,
      inRoom: !!room && q.bottom <= room.bottom + 0.5 && q.top >= room.top - 0.5 }; }
  return { scrollH: t.scrollHeight, clientH: t.clientHeight, clamp: cs.webkitLineClamp || 'none', display: cs.display,
    overflow: cs.overflow, text: t.textContent, last, width: Math.round(box.width), ownRow: b ? b.top >= box.bottom - 0.5 : null }; })()"""
LONG = "code-review-and-tests-for-every-change-made-now"  # 47 characters: the head's words need a third line at 1280


def _size(c, w: int = 1280, h: int = 800) -> None:
    c.call("Emulation.setDeviceMetricsOverride", width=w, height=h, deviceScaleFactor=1, mobile=False)


def _open(c, rig, query: str, w: int = 1280, h: int = 800) -> None:
    from tests.helpers.studio_session import boot_go, url
    _size(c, w, h)
    boot_go(c, url(rig, query))
    c.wait("document.readyState !== 'loading'", 30)
    try:
        c.wait("!!window.__jb && window.__jb.open > 0", 30)
    except TimeoutError:
        raise TimeoutError(f"the event feed never opened: {c.js('JSON.stringify([typeof window.__jb, window.__jb && window.__jb.open, window.__jb && window.__jb.reqs.length, String(window.EventSource).slice(0, 60)])')}")
    c.mouse("mouseMoved", 1279, 799)


def _wait(c, expr: str, timeout: float = 10) -> bool:
    try:
        c.wait(f"!!({expr})", timeout)
        return True
    except TimeoutError:
        return False


def _body(rig, name: str, text: str) -> dict:
    from halo_harness.crew import store
    p = store.path_for("map", name, state_dir=rig.state)
    store.write_text(p, text)
    return store.read(p) or {}


def _told(rig, name: str, write, timeout: float = 15) -> None:
    """`write()` a map's file, then wait until Studio's watcher has published a `files_changed` naming `name`. The watcher
    reports a write up to ~1.8 s later (POLL_S 1.5 + DEBOUNCE_S 0.3): a page opened inside that window hears it as a new
    version and rightly reads the map again (mapFiles.ts), so a step that counts reads opens its page only after this."""
    import threading
    from halo_harness.studio.events import bridge_for
    seen = threading.Event()

    def tap(f: dict) -> None:
        d = f.get("data") or {}
        if f.get("event") == "files_changed" and d.get("kind") == "maps" and name in [*(d.get("names") or []), *(d.get("removed") or [])]:
            seen.set()
    taps = bridge_for(rig.server).taps
    taps.append(tap)
    try:
        write()
        if not seen.wait(timeout):
            raise TimeoutError(f"Studio's watcher never told of {name}'s file in {timeout} s")
    finally:
        taps.remove(tap)


def _parse(rig, text: str) -> dict:
    """A map's body as the frame carries it, without writing it where maps live (no files_changed follows)."""
    from halo_harness.crew import store
    p = Path(rig.state) / "parse-only.yaml"
    store.write_text(p, text)
    return store.read(p) or {}


def _frame(rig, sid: str, wrote: list, maps: dict, outcome: str = "applied", undo: str = "u", this: str = "auto",
           next_: "str | None" = None) -> dict:
    from halo_harness.peers.identity import harness
    now = time.time()
    data = {"id": f"card-{undo}", "outcome": outcome, "wrote": wrote, "undo": undo, "next": next_, "this_session": this,
            "maps": maps, "t": now}
    rig.server.events.publish({"session_id": sid, "harness": harness()["id"], "event": "builder_done", "agent_id": "main",
                               "turn": 1, "data": data, "ts": now})
    return data


def _on_shop(rig, rows: Rows, a: str, b: str) -> None:
    from halo_harness.crew import store
    rows.reset()
    rows.idle(b)
    rows.idle(a, map="shop", map_plain=False, map_scope="yours", map_path=str(store.path_for("map", "shop", state_dir=rig.state)))


def _pair(c) -> dict:
    return c.js(f"""(() => {{ const p = {PAIR}, d = {DRAWN}, h = {HEAD}, bar = {Q}('[data-testid=session-built]');
      const btn = (w) => {{ const b = p?.querySelector(`[data-which=${{w}}]`); return b ? {{ pressed: b.getAttribute('aria-pressed'), marked: b.hasAttribute('data-new'), text: b.textContent,
        whole: b.scrollWidth <= b.clientWidth + 1 && b.scrollHeight <= b.clientHeight + 1 && getComputedStyle(b).textOverflow !== 'ellipsis' && getComputedStyle(b).whiteSpace !== 'nowrap' }} : null; }};
      return {{ bar: !!bar, barH: bar ? bar.getBoundingClientRect().height : 0,
               text: p?.textContent || '', h: p ? Math.round(p.getBoundingClientRect().height * 2) / 2 : null, buttons: p ? p.querySelectorAll('button').length : 0,
               running: btn('running'), built: btn('built'), map: d?.dataset.map || '', lit: d ? d.querySelectorAll('[data-lit]').length : -1,
               working: d ? d.querySelectorAll('[data-state=working]').length : -1, head: h?.querySelector('[data-testid=session-built-text]')?.textContent || '',
               headButton: h?.querySelector('button')?.textContent || '' }}; }})()""") or {}


def _off(v, w) -> bool:
    if (v is None) != (w is None):
        return True
    if isinstance(v, list):
        return any(abs(x - y) > 0.5 for x, y in zip(v, w))
    return isinstance(v, (int, float)) and abs(v - w) > 0.5


def _still(c, before: dict, keys=None) -> dict:
    """What of `keys` (the controls by default) moved against `before` (half a px allowed), how far the drawing's top went,
    and the head's words (WHOLE)."""
    now = c.js(CTRLS) or {}
    keys = CONTROLS if keys is None else keys
    moved = {k: [before.get(k), now.get(k)] for k in keys if _off(before.get(k), now.get(k))}
    top = (now.get("scrollTop") or 0) - (before.get("scrollTop") or 0)
    return {"moved": moved, "top": top, "h": (now.get("session-built-head") or [0, 0, 0, 0])[3], "whole": c.js(WHOLE), "now": now}


def _press(c, which: str) -> None:
    c.js(f"{PAIR}?.querySelector('[data-which={which}]')?.click(); 1")


def word(c, rig, rows: Rows, a: str, b: str) -> dict:
    rows.reset()
    rows.idle(b)
    rows.idle(a, map="auto", map_plain=True)
    _open(c, rig, f"mode=session&session={a}")
    c.wait(f"!!{BTN} && {FLEET_READS} >= 1", 30)
    if c.js(f"{BTN}.getAttribute('aria-pressed') === 'true'"):  # the drivers' arrangement opens every panel: closed first
        c.js(f"{BTN}.click(); 1")
        c.wait(f"{BTN}.getAttribute('aria-pressed') === 'false'", 10)
    read = f"""(() => {{ const w = {WORD}, cs = w ? getComputedStyle(w) : null;
      const cv = document.createElement('canvas').getContext('2d'); if (cs) cv.font = cs.font;
      return {{ there: !!w, text: w?.textContent ?? null, minW: cs ? parseFloat(cs.minWidth) || 0 : 0, zero: cs ? cv.measureText('0').width : 0,
               rect: w ? (() => {{ const r = w.getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; }})() : null,
               rects: {RECTS}, pressed: [...document.querySelectorAll('[data-testid=viewbar-btn]')].map((x) => x.getAttribute('aria-pressed')),
               section: {Q}('.section-view:not([hidden])')?.dataset.section || '', drawer: {BTN}?.getAttribute('aria-pressed') === 'true',
               words: [...document.querySelectorAll('[data-testid=viewbar-word]')].map((x) => x.closest('[data-testid=viewbar-btn]')?.dataset.panel || ''),
               pops: [...document.querySelectorAll('[role=dialog], .toast')].filter((e) => !!(e.offsetParent || e.getClientRects().length)).length }}; }})()"""
    before = c.js(read) or {}
    t0 = time.time()
    _frame(rig, a, [{"kind": "map", "name": "review-flow", "added": True}], {"review-flow": _body(rig, "review-flow", REVIEW_FLOW)}, undo="w1")
    came = _wait(c, f"{WORD}?.textContent === 'new'", 10)
    took = time.time() - t0
    after = c.js(read) or {}
    c.js(f"{BTN}.click(); 1")
    _wait(c, f"{BTN}.getAttribute('aria-pressed') === 'true' && !!{Q}('[data-testid=session-truth]')", 10)
    _wait(c, f"{WORD}?.textContent === ''", 5)
    opened = c.js(read) or {}
    return {"word": {"before": before, "after": after, "opened": opened, "came": came, "took": took}}


def same(c, rig, rows: Rows, a: str, b: str) -> dict:
    from tests.helpers.studio_map_live import MAP
    _body(rig, "shop", MAP)
    _on_shop(rig, rows, a, b)
    _open(c, rig, f"mode=session&session={a}&open=session-map")
    c.wait(f"!!{DRAWN} && {BOXES}.length > 1", 30)
    n = c.js(f"{BOXES}.length")
    one = MAP.replace("lines:\n", "- {id: extra1, agent: writer}\nlines:\n") + "- {from: main, to: extra1, when: always}\n"
    before = c.js(f"{MAPREQS}.length")
    _frame(rig, a, [{"kind": "map", "name": "shop", "added": False}], {"shop": _body(rig, "shop", one)}, undo="u1", this="shop")
    a_ok = _wait(c, f"!!{Q}('[data-testid=session-lit-map] [data-box=extra1]')", 5)
    a_reqs = c.js(f"{MAPREQS}.length") - before
    a_new = c.js(f"!!{Q}('[data-box=extra1][data-new]')")
    two = one.replace("lines:\n", "- {id: extra2, agent: writer}\nlines:\n") + "- {from: main, to: extra2, when: always}\n"
    _body(rig, "shop", two)  # a plain write, as the Write tool makes: Studio's watcher sends files_changed
    b_ok = _wait(c, f"!!{Q}('[data-testid=session-lit-map] [data-box=extra2]')", 10)
    b = c.js(f"""(() => ({{ n: {BOXES}.length, isNew: !!{Q}('[data-box=extra2][data-new]'),
      tag: !!{Q}('[data-box=extra2] [data-testid=session-map-new]'), word: {WORD}?.textContent ?? null }}))()""")
    c.js(f"{BTN}.click(); 1")
    _wait(c, f"{BTN}.getAttribute('aria-pressed') === 'false' && !{DRAWN}", 5)
    c.js(f"{BTN}.click(); 1")
    c_ok = _wait(c, f"!!{Q}('[data-testid=session-lit-map] [data-box=extra2]')", 10)
    return {"same": {"n": n, "a": {"ok": a_ok, "reqs": a_reqs, "isNew": a_new},
                     "b": {"ok": b_ok, **(b or {})}, "c": {"ok": c_ok, "n": c.js(f"{BOXES}.length")}}}


def once(c, rig, rows: Rows, a: str, b: str) -> dict:
    out: dict = {}
    body = _body(rig, "review-flow", REVIEW_FLOW)
    built = [{"kind": "workflow", "name": "review", "added": True}, {"kind": "map", "name": "review-flow", "added": True}]
    write_seven(rig.state)  # 3.6.0.5: R30/R31 on a map of his of seven boxes, where 3.6.0.2's heads stand
    rows.reset()
    rows.idle(b)
    rows.idle(a, map=SEVEN, map_plain=False)
    _open(c, rig, f"mode=session&session={a}&open=session-map")
    c.wait(f"!!{DRAWN} && {BOXES}.length > 1", 30)
    out["plain"] = _pair(c)
    _frame(rig, a, built, {"review-flow": body}, undo="o1", this=SEVEN)
    _wait(c, f"{PAIR}?.textContent.includes('Just built: review-flow') && {DRAWN}?.dataset.map === 'review-flow'", 10)
    out["first"] = _pair(c)
    _press(c, "running")
    _wait(c, f"{DRAWN}?.dataset.map === '{SEVEN}'", 10)
    out["back"] = _pair(c)
    _frame(rig, a, built, {"review-flow": body}, undo="o2", this=SEVEN)
    _wait(c, f"{PAIR}?.querySelector('[data-which=built]')?.hasAttribute('data-new')", 10)
    time.sleep(0.5)
    out["second"] = _pair(c)
    # (b) a new page, the pointer on the drawing when the frame lands: only the tab is marked, never a jump later
    _open(c, rig, f"mode=session&session={a}&open=session-map")
    c.wait(f"!!{DRAWN} && {BOXES}.length > 1", 30)
    r = c.js(f"(() => {{ const r = {DRAWN}.querySelector('.mp-mini-scroll').getBoundingClientRect(); return [r.left + r.width / 2, r.top + 20]; }})()")
    c.mouse("mouseMoved", r[0], r[1])
    time.sleep(0.3)
    _frame(rig, a, built, {"review-flow": body}, undo="o3", this=SEVEN)
    _wait(c, f"{PAIR}?.querySelector('[data-which=built]')?.hasAttribute('data-new')", 10)
    out["held"] = _pair(c)
    c.mouse("mouseMoved", 1279, 799)
    time.sleep(1.0)
    out["held_out"] = _pair(c)
    # (c) the pair pressed once: a later build only marks its tab
    _press(c, "running")
    _frame(rig, a, [{"kind": "map", "name": "third", "added": True}], {"third": _body(rig, "third", THIRD)}, undo="o4", this=SEVEN)
    _wait(c, f"{PAIR}?.textContent.includes('Just built: third')", 10)
    time.sleep(0.5)
    out["pressed"] = _pair(c)
    return {"once": out}


def heads(c, rig, rows: Rows, a: str, b: str) -> dict:
    from halo_harness.crew import store
    from tests.helpers.studio_map_live import MAP
    out: dict = {}
    store.write_text(store.path_for("workflow", "solo", state_dir=rig.state), store.dump(FLOW_SOLO))
    _body(rig, "shop", MAP)
    _on_shop(rig, rows, a, b)
    _open(c, rig, f"mode=session&session={a}&open=session-map")
    c.wait(f"!!{DRAWN} && {BOXES}.length > 1", 30)
    time.sleep(0.5)
    still = c.js(CTRLS) or {}
    _frame(rig, a, [{"kind": "workflow", "name": "solo", "added": True}], {}, undo="h1", this="shop")
    _wait(c, f"{HEAD}?.textContent.includes('solo')", 10)
    time.sleep(0.3)
    out["workflow"] = {**_pair(c), "still": _still(c, still)}
    out["workflow_section"] = c.js(f"{Q}('.section-view:not([hidden])')?.dataset.section || ''")
    c.js(f"{HEAD}?.querySelector('button')?.click(); 1")
    _wait(c, f"{Q}('[data-testid=agents]')?.dataset.view === 'workflows' && {Q}('[data-testid=flow-form]')?.dataset.name === 'solo'", 10)
    out["opened"] = c.js(f"""(() => ({{ section: {Q}('.section-view:not([hidden])')?.dataset.section || '',
      view: {Q}('[data-testid=agents]')?.dataset.view || '', text: {Q}('[data-testid=flow-form]')?.dataset.name === 'solo' }}))()""")
    # (b) a box added to the running map: the same drawing, tagged, and its head
    _open(c, rig, f"mode=session&session={a}&open=session-map")
    c.wait(f"!!{DRAWN} && {BOXES}.length > 1", 30)
    time.sleep(0.5)
    still = c.js(CTRLS) or {}
    plus = MAP.replace("lines:\n", "- {id: tester, agent: tester}\nlines:\n") + "- {from: main, to: tester, when: always}\n"
    _frame(rig, a, [{"kind": "map", "name": "shop", "added": False}], {"shop": _body(rig, "shop", plus)}, undo="h2", this="shop")
    _wait(c, f"!!{Q}('[data-box=tester][data-new]')", 10)
    out["running"] = {**_pair(c), **(c.js(f"""(() => ({{ tag: {Q}('[data-box=tester] [data-testid=session-map-new]')?.textContent || '',
      others: [...document.querySelectorAll('[data-testid=session-lit-map] [data-box][data-new]')].map((x) => x.dataset.box) }}))()""") or {}),
                      "still": _still(c, still)}
    # (c) any other map
    _frame(rig, a, [{"kind": "map", "name": "third", "added": True}], {"third": _body(rig, "third", THIRD)}, undo="h3", this="shop")
    _wait(c, f"{HEAD}?.textContent.includes('does not run on it') && {DRAWN}?.dataset.map === 'third'", 10)
    time.sleep(0.3)
    out["other"] = {**_pair(c), "still": _still(c, still)}
    # (c) another map the build also made the one new sessions run on (R36's use row was ticked and applied)
    rows.set(a, map_next="fourth", map_next_since=time.time())  # the row as P2 sends it once the use row was applied
    # P9 batch 3 (CI, Windows): the switch of {B} is a fact of its own, read from the row: the truth block names fourth and
    # measures its twin again, once (R20, P4 batch 11: nothing is held for a name it does not have; R12 lets the block grow
    # while the pointer is outside). With Windows' font that takes one more line than the default's did; on Linux it happened
    # to take the same. So the heads below are compared with the drawer once the switch has reached the block: a head
    # landing still moves no control. (Before, other_next was read before the row reached the block, on every system.)
    named = _wait(c, f"({Q}('[data-testid=session-truth]')?.textContent || '').includes('run on fourth')", 15)
    time.sleep(0.5)
    switched = c.js(CTRLS) or {}
    _frame(rig, a, [{"kind": "map", "name": "fourth", "added": True}],
           {"fourth": _body(rig, "fourth", THIRD.replace("name: third", "name: fourth"))}, undo="h4", this="shop", next_="fourth")
    _wait(c, f"{HEAD}?.textContent.includes('fourth') && {Q}('[data-testid=session-truth]')?.dataset.state === 'T2'", 10)
    time.sleep(0.3)
    out["other_next"] = {**_pair(c), "still": _still(c, switched), "truth": c.js(f"{Q}('[data-testid=session-truth]')?.dataset.state || ''"),
                         "s13": c.js("(document.querySelector('.mp-down')?.innerText.match(/keeps running on/g) || []).length"),
                         "named": named, "switch": _still(c, still)["moved"]}
    # (e) a workflow whose name needs a third line at this width: every word on screen, the button on its own row
    _frame(rig, a, [{"kind": "workflow", "name": LONG, "added": True}], {}, undo="h5", this="shop")
    _wait(c, f"{HEAD}?.textContent.includes('{LONG}') && {DRAWN}?.dataset.map === 'shop'", 10)
    time.sleep(0.3)
    out["long"] = {**_pair(c), "still": _still(c, switched)}
    c.js("(() => { const m = document.querySelector('.mp-down'); m.style.width = '412px'; m.style.flex = 'none'; return 1; })()")
    time.sleep(0.5)
    out["long412"] = c.js(WHOLE)
    c.js("(() => { const m = document.querySelector('.mp-down'); m.style.width = ''; m.style.flex = ''; return 1; })()")
    time.sleep(0.5)
    # a frame that changes nothing in the head's words: the head, its words, its button and the drawing hold still
    held = c.js(CTRLS) or {}
    n = c.js(FLEET_READS)
    rows.set(a, status="idle", busy=False)
    _wait(c, f"{FLEET_READS} > {n}", 10)
    time.sleep(0.5)
    out["same_frame"] = _still(c, held, CONTROLS + ["session-built-head", "session-built-text", "session-built-open", "scrollTop"])
    # (d) two more turns and a fleet read later the tags are still there; once the session ends they go
    _press(c, "running")
    rows.turn(a)
    rows.idle(a)
    _reload(c, rows, 2)
    _wait(c, f"!!{Q}('[data-box=tester]')", 10)
    out["kept"] = c.js(f"!!{Q}('[data-box=tester][data-new]')")
    rows.hide(a)
    _wait(c, f"{Q}('[data-testid=session-truth]')?.dataset.state === 'T8'", 10)
    rows.hidden.discard(a)
    rows.refresh()
    _wait(c, f"!!{Q}('[data-box=tester]')", 15)
    out["ended"] = c.js(f"!!{Q}('[data-box=tester]') && !{Q}('[data-box=tester][data-new]')")
    return {"heads": out}


def fetch(c, rig, rows: Rows, a: str, b: str) -> dict:
    from halo_harness.crew import store
    from tests.helpers.studio_map_live import MAP
    out: dict = {}
    _told(rig, "shop", lambda: _body(rig, "shop", MAP))  # with every earlier step's map writes (one watcher scan)
    _on_shop(rig, rows, a, b)
    hold =c.call("Page.addScriptToEvaluateOnNewDocument", source="window.__jb && (window.__jb.hold = true);")["identifier"]
    try:
        _open(c, rig, f"mode=session&session={a}&open=session-map")
    finally:
        c.call("Page.removeScriptToEvaluateOnNewDocument", identifier=hold)
    _wait(c, f"{Q}('[data-testid=session-lit-line] .mp-truth-line') && !!{Q}('[data-testid=session-status]')", 20)
    time.sleep(0.5)
    out["painted"] = c.js(f"""(() => ({{ truth: {Q}('[data-testid=session-lit-line] .mp-truth-line')?.firstChild?.nodeValue || '',
      status: {Q}('[data-testid=session-status]')?.textContent || '', pair: {PAIR}?.textContent || '',
      done: {MAPREQS}.filter((r) => r.status).length, asked: {MAPREQS}.map((r) => r.url), held: window.__jb.held.length,
      told: window.__jb.fc }}))()""")
    c.js("window.__jb.hold = false; window.__jb.held.splice(0).forEach((go) => go()); 1")
    _wait(c, f"!!{DRAWN} && {BOXES}.length > 1", 15)
    mark = lambda: c.js(f"{MAPREQS}.length")  # noqa: E731
    m0 = mark()
    _frame(rig, a, [{"kind": "map", "name": "third", "added": True}], {"third": _parse(rig, THIRD)}, undo="f1", this="shop")
    _wait(c, f"{DRAWN}?.dataset.map === 'third' && {BOXES}.length > 1", 10)
    out["body_drawn"] = c.js(f"{MAPREQS}.slice({m0}).map((r) => r.url)")
    time.sleep(1.0)
    out["body"] = c.js(f"{MAPREQS}.slice({m0}).map((r) => r.url)")
    _body(rig, "big", THIRD.replace("name: third", "name: big"))
    time.sleep(3.0)  # Studio's watcher has told the page of big's file before the frame (not drawn: nothing is read)
    m1 = mark()
    _frame(rig, a, [{"kind": "map", "name": "big", "added": True}], {}, undo="f2", this="shop")
    _wait(c, f"{PAIR}?.textContent.includes('Just built: big')", 10)
    _press(c, "built")
    _wait(c, f"{DRAWN}?.dataset.map === 'big' && {BOXES}.length > 1", 10)
    time.sleep(1.0)
    out["left_out"] = c.js(f"{MAPREQS}.slice({m1}).map((r) => r.url)")
    m2 = mark()
    _frame(rig, a, [{"kind": "map", "name": "x1", "added": True}], {}, outcome="left", undo="f3", this="shop")
    _frame(rig, a, [{"kind": "map", "name": "x2", "added": True}], {}, outcome="failed", undo="f4", this="shop")
    time.sleep(1.5)
    out["left_failed"] = c.js(f"{MAPREQS}.slice({m2}).map((r) => r.url)")
    # removed: the running map's file goes; the open drawing reads it again (files_changed) and says so
    _press(c, "running")
    _wait(c, f"{DRAWN}?.dataset.map === 'shop'", 10)
    store.path_for("map", "shop", state_dir=rig.state).unlink()
    _wait(c, f"!!{Q}('[data-testid=session-map-removed]')", 15)
    out["removed"] = c.js(f"{Q}('[data-testid=session-map-removed]')?.textContent || ''")
    _body(rig, "shop", MAP)
    time.sleep(3.0)  # the watcher's files_changed for shop's file is read by the open drawing before the states below
    m3 = mark()
    state = f"{Q}('[data-testid=session-truth]')?.dataset.state"
    seen = []
    rows.set(a, map="", map_plain=False, map_scope=None, map_path=None)  # T4: the session runs with no map
    seen.append("T4" if _wait(c, f"{state} === 'T4'", 10) else c.js(state))
    time.sleep(1.0)
    rows.set(a, parent="studio:4242", turns=0, asked=False, map_next="shop")  # T10: from Studio, no message yet
    seen.append("T10" if _wait(c, f"{state} === 'T10'", 10) else c.js(state))
    time.sleep(1.0)
    rows.hide(a)
    seen.append("T8" if _wait(c, f"{state} === 'T8'", 10) else c.js(state))
    reads = c.js(f"{MAPREQS}.slice({m3}).map((r) => r.url)")
    rows.hide(b)  # Empty: no session at all, on a page that picked none (a picked session that ended stays T8, R4)
    _open(c, rig, "mode=session&open=session-map")
    ws = f"{Q}('[data-testid=session-open-workspace]')"
    _wait(c, ws, 30)  # with no session Session shows its Start view; the workspace is opened by hand
    c.js(f"{ws}?.click(); 1")
    seen.append("Empty" if _wait(c, f"{state} === 'Empty'", 15) else c.js(state))
    time.sleep(1.0)
    out["quiet"] = {"seen": seen, "reads": reads + c.js(f"{MAPREQS}.map((r) => r.url)")}
    out["failed"] = c.js("window.__jb.reqs.filter((r) => r.status >= 400).map((r) => `${r.status} ${r.url}`)")
    return {"fetch": out}


ROOM = f"""(() => {{ const room = {Q}('.mp-down-room')?.getBoundingClientRect(), sc = {Q}('.mp-down .mp-mini-scroll')?.getBoundingClientRect();
  const tools = {Q}('.mp-down-tools')?.getBoundingClientRect(), more = {Q}('[data-testid=map-more-below]');
  const tb = {Q}('.mp-down .mp-truth-box')?.getBoundingClientRect();
  const below = sc ? {BOXES}.filter((b) => b.getBoundingClientRect().top >= sc.bottom - 0.5).length : -1;
  return {{ room: room ? Math.round(room.height) : null, scroll: sc ? Math.round(sc.height) : null, top: sc ? Math.round(sc.top) : null,
           gap: room && tools ? Math.round(room.top - tools.bottom) : null, truth: tb ? Math.round(tb.height) : null,
           over: room && tb ? Math.round(room.top - tb.bottom) : null, pair: !!{PAIR}, bar: !!{Q}('[data-testid=session-built]'),
           boxes: {BOXES}.length, below, text: more?.textContent || '' }}; }})()"""


def _room_rows(rows: Rows, a: str) -> list:
    """Main and one DONE helper of main in the group "check the room" (on Auto main alone is one box: the wait wants two)."""
    base = next((r for r in rows.orig() if r.get("session_id") == a), {})
    main = next((x for x in base.get("agents") or [] if x.get("agent_id") == "main"), {"agent_id": "main", "name": "main", "kind": "main"})
    r1 = {"agent_id": "r1", "name": "coder", "role": "coder", "parent": "main", "kind": "member", "state": "done", "cost_usd": 0.0,
          "crew": None, "square": None, "task": "check the room", "model": "", "since": time.time(),
          "spawn": {"step": "1", "description": "check the room", "task": "check the room",
                    "group": {"key": "task:check the room", "n": 1, "by": "task"}}}
    return [{**main, "parent": None}, r1]


def room(c, rig, rows: Rows, a: str, b: str) -> dict:
    out: dict = {}
    for w, h in ((1280, 800), (1440, 900), (1920, 1080)):
        rows.reset()
        rows.idle(b)
        rows.idle(a, map="auto", map_plain=True, agents=_room_rows(rows, a))  # 3.6.0.5: main and one group (Auto draws groups)
        _open(c, rig, f"mode=session&session={a}&open=session-map", w, h)
        c.wait(f"!!{DRAWN} && {BOXES}.length > 1", 30)
        time.sleep(1.0)  # past the drawing's settle (200 ms) and its measured boxes
        out[f"{w}x{h}"] = c.js(ROOM)
    _size(c)
    return {"room": out}


class JustBuiltDriver(MapDownDriver):
    width, height = 1280, 800

    @contextmanager
    def session(self, c):
        from halo_harness.crew import store
        from tests.helpers.studio_session import ERRS_JS, FAKE_SID, second_session
        from tests.helpers.studio_session_rig import StudioSessionRig
        with StudioSessionRig() as rig:
            _seed_shop(rig)
            store.write_text(store.path_for("workflow", "review", state_dir=rig.state), store.dump(FLOW_REVIEW))
            second_session(rig)
            rows = Rows(rig)
            c.call("Page.enable")  # the hooks run before any page script
            c.call("Page.addScriptToEvaluateOnNewDocument", source=ERRS_JS)
            c.call("Page.addScriptToEvaluateOnNewDocument", source=HOOKS)
            args = (c, rig, rows, rig.act.session_id, FAKE_SID)
            steps = [s for s in (word, same, once, heads, fetch, room) if not self.argv or s.__name__ in self.argv]
            yield tuple((fn, args) for fn in steps)


if __name__ == "__main__":
    sys.exit(JustBuiltDriver(sys.argv[1:]).main())
