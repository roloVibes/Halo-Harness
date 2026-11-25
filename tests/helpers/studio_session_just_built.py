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
    follow  3.6.0.9 V (the owner's point 34): a workflow box's steps follow the workflow's file (a plain write, a
            Builder card that wrote only the workflow: "new" on the new steps) and a step's agent file (its model); a
            card's map body and the watcher's frame for that same write read the map zero times, a different write once
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
# fw (3.6.0.9 V batch 2): `{kind}:{name}` of each workflow or agent file the page heard, pushed 1 s after the frame: the
# page's own handler (lib/filesLive.ts, a 300 ms debounce set as the same frame arrives) has run by then, by timer order
HOOKS = r"""(() => { if (window.__jb) return; const jb = window.__jb = { open: 0, reqs: [], held: [], hold: false, fc: [], fw: [] };
  const ES = window.EventSource; if (ES) { const W = function (u, o) { const es = new ES(u, o);
    es.addEventListener('open', () => { jb.open += 1; });
    es.addEventListener('files_changed', (e) => { try { const d = JSON.parse(e.data).data || {};
      if (d.kind === 'maps') jb.fc.push([...(d.names || []), ...(d.removed || [])]);
      if (d.kind === 'workflows' || d.kind === 'agents') setTimeout(() => jb.fw.push(...(d.names || []).map((n) => d.kind + ':' + n)), 1000); } catch (x) { jb.fc.push(['?']); } });
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


def _told(rig, name: str, write, timeout: float = 15, kind: str = "maps") -> None:
    """`write()` a map's file, then wait until Studio's watcher has published a `files_changed` naming `name`. The watcher
    reports a write up to ~1.8 s later (POLL_S 1.5 + DEBOUNCE_S 0.3): a page opened inside that window hears it as a new
    version and rightly reads the map again (mapFiles.ts), so a step that counts reads opens its page only after this."""
    import threading
    from halo_harness.studio.events import bridge_for
    seen = threading.Event()

    def tap(f: dict) -> None:
        d = f.get("data") or {}
        if f.get("event") == "files_changed" and d.get("kind") == kind and name in [*(d.get("names") or []), *(d.get("removed") or [])]:
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
           next_: "str | None" = None, sigs: "dict | None" = None, **more) -> dict:
    """`builder_done` as P2b sends it; `sigs` (3.6.0.9 V) each body's file hash, as crew/map_events.py adds it."""
    from halo_harness.peers.identity import harness
    now = time.time()
    data = {"id": f"card-{undo}", "outcome": outcome, "wrote": wrote, "undo": undo, "next": next_, "this_session": this,
            "maps": maps, "t": now, **({"sigs": sigs} if sigs is not None else {}), **more}
    rig.server.events.publish({"session_id": sid, "harness": harness()["id"], "event": "builder_done", "agent_id": "main",
                               "turn": 1, "data": data, "ts": now})
    return data


def _sigs(rig, *names: str) -> dict:
    """3.6.0.9 V: the hash of each map's file, as the Builder's frame carries it (studio/files_live.py file_sig)."""
    from halo_harness.crew import store
    from halo_harness.studio.files_live import file_sig
    return {n: file_sig(store.path_for("map", n, state_dir=rig.state)) for n in names}


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
    # 3.6.0.21 T5: the moment extra1's box is first in the page (a MutationObserver: synchronous with the commit); only the
    # map reads the page STARTED before it count -- the file is written too, and a read Studio's watcher asks for after the
    # redraw is not the fault this guards (a redraw that waited on a read)
    c.js(f"""(() => {{ const t0 = window.__sameT0 = performance.now(); window.__sameAt = null;
      const seen = () => !!{Q}('[data-testid=session-lit-map] [data-box=extra1]');
      const mo = new MutationObserver(() => {{ if (seen()) {{ window.__sameAt = performance.now(); mo.disconnect(); }} }});
      mo.observe(document.body, {{childList: true, subtree: true, attributes: true}}); return t0; }})()""")
    _frame(rig, a, [{"kind": "map", "name": "shop", "added": False}], {"shop": _body(rig, "shop", one)}, undo="u1", this="shop",
           sigs=_sigs(rig, "shop"))
    a_ok = _wait(c, f"!!{Q}('[data-testid=session-lit-map] [data-box=extra1]')", 5)
    a_reqs = c.js(f"window.__sameAt == null ? -1 : {MAPREQS}.filter((r) => r.t >= window.__sameT0 && r.t < window.__sameAt).length")
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


STEPROWS = "[...document.querySelectorAll('[data-testid=session-lit-map] [data-testid=session-map-step]')]"
# review-flow with an agent box for coder too: a step's model is drawn from the facts of the map's agent box (litView.ts)
FOLLOW_FLOW = REVIEW_FLOW.replace("lines:", "- {id: coder, agent: coder}\nlines:") + "- {from: main, to: coder, when: always}\n"


def follow(c, rig, rows: Rows, a: str, b: str) -> dict:
    from halo_harness.crew import store
    fpath = store.path_for("workflow", "review", state_dir=rig.state)

    def flow(n: int) -> None:
        store.write_text(fpath, store.dump({**FLOW_REVIEW, "steps": [{"name": f"s{i}", "agents": ["coder"]} for i in range(n)]}))
    flow(2)
    _told(rig, "review-flow", lambda: _body(rig, "review-flow", FOLLOW_FLOW))
    rows.reset()
    rows.idle(b)
    rows.idle(a, map="review-flow", map_plain=False, map_scope="yours", map_path=str(store.path_for("map", "review-flow", state_dir=rig.state)))
    _open(c, rig, f"mode=session&session={a}&open=session-map")
    out: dict = {"first": _wait(c, f"{STEPROWS}.length === 2", 30)}
    n = f"{STEPROWS}.length"
    flow(3)  # (1) a plain write of the workflow
    out["plain"] = [_wait(c, f"{n} === 3", 12), c.js(n)]
    flow(4)  # (2) a Builder card that wrote only the workflow: its file, then its frame
    _frame(rig, a, [{"kind": "workflow", "name": "review", "added": False}], {}, undo="v2", this="review-flow")
    out["built"] = [_wait(c, f"{n} === 4 && {STEPROWS}[3].hasAttribute('data-new')", 12), c.js(n),
                    c.js(f"{STEPROWS}.map((r) => r.hasAttribute('data-new'))")]
    starter = store.find("agent", "coder", state_dir=rig.state)
    coder = dict(store.read(starter[0]) or {}) if starter else {}
    store.write_text(store.path_for("agent", "coder", state_dir=rig.state), store.dump({**coder, "name": "coder", "model": "gpu-model-b"}))  # (3)
    out["model"] = [_wait(c, f"{STEPROWS}.length === 4 && {STEPROWS}.every((r) => r.textContent.includes('gpu-model-b'))", 12),
                    c.js(f"{STEPROWS}[0]?.textContent || ''")]
    # (4) the read count: a card's body, then the watcher's frame for that same write: no read; a different write: one
    m0, f0 = c.js(f"{MAPREQS}.length"), c.js("window.__jb.fc.length")
    one = FOLLOW_FLOW.replace("lines:\n", "- {id: extra1, agent: writer}\nlines:\n") + "- {from: main, to: extra1, when: always}\n"
    _frame(rig, a, [{"kind": "map", "name": "review-flow", "added": False}], {"review-flow": _body(rig, "review-flow", one)},
           undo="v4", this="review-flow", sigs=_sigs(rig, "review-flow"))
    drawn1 = _wait(c, f"!!{Q}('[data-testid=session-lit-map] [data-box=extra1]')", 10)
    told = _wait(c, f"window.__jb.fc.slice({f0}).some((x) => x.includes('review-flow'))", 15)  # the watcher's frame, heard
    two = one.replace("lines:\n", "- {id: extra2, agent: writer}\nlines:\n") + "- {from: main, to: extra2, when: always}\n"
    _body(rig, "review-flow", two)
    drawn2 = _wait(c, f"!!{Q}('[data-testid=session-lit-map] [data-box=extra2]')", 12)
    out["reads"] = {"drawn": [drawn1, told, drawn2], "urls": c.js(f"{MAPREQS}.slice({m0}).map((r) => r.url)")}
    return {"follow": out}


# 3.6.0.9 V batch 2 (the owner's point 34; reader V1, WHAT HE MEETS TODAY 5): what was built is said again after F5
KEPT = "JSON.parse(sessionStorage.getItem('halo.studio.built') || '{}')"
REFUSE_JS = ("if (window.name === 'refuse-storage') { const set = Storage.prototype.setItem; Storage.prototype.setItem = function (k, v) {"
             " if (this === window.sessionStorage) throw new DOMException('refused', 'QuotaExceededError'); return set.call(this, k, v); }; }")
SAID = f"""(() => {{ const hd = {HEAD};
  return {{ head: hd?.querySelector('[data-testid=session-built-text]')?.textContent || '',
    lines: [...document.querySelectorAll('[data-testid=session-ready-text]')].map((e) => e.textContent),
    tags: [...document.querySelectorAll('[data-testid=session-lit-map] [data-box][data-new]')].map((x) =>
      x.dataset.box + ' ' + (x.querySelector('[data-testid=session-map-new]')?.textContent || '')) }}; }})()"""
WROTE_AUTO = [{"kind": "agent", "name": "checker", "added": True}, {"kind": "workflow", "name": "review", "added": True}]


def _js_str(v: str) -> str:
    import json
    return json.dumps(v)


def _f5(c, rig=None, query: str = "", go: bool = False) -> None:
    """F5 (a reload keeps the tab's sessionStorage); with `query`, the address is that session's page first (as he would
    have it after picking it, then pressing F5); `go`: that address opened in this tab instead (no reload)."""
    from tests.helpers.studio_session import url
    to = f"history.replaceState(null, '', {_js_str(url(rig, query))}); " if query and not go else ""
    then = f"location.assign({_js_str(url(rig, query))})" if go else "location.reload()"
    c.js(f"(() => {{ window.__old = 1; {to}setTimeout(() => {then}, 0); return 1; }})()")
    c.wait("!window.__old && document.readyState !== 'loading' && !!window.__jb && window.__jb.open > 0", 30)
    c.mouse("mouseMoved", 1279, 799)


def kept(c, rig, rows: Rows, a: str, b: str) -> dict:
    try:
        return _kept(c, rig, rows, a, b)
    finally:  # batch 2 repair: a failure midway never leaves storage refusing (or kept) for the later steps
        try:
            c.js("window.name = ''; 1")
        except Exception:
            pass


def _kept(c, rig, rows: Rows, a: str, b: str) -> dict:
    from tests.helpers.studio_map_live import MAP
    from tests.helpers.studio_session import page_errors
    c.call("Page.addScriptToEvaluateOnNewDocument", source=REFUSE_JS)  # active only while window.name says so
    out: dict = {}
    _told(rig, "shop", lambda: _body(rig, "shop", MAP))
    _on_shop(rig, rows, a, b)
    rows.idle(b, map="auto", map_plain=True)
    qa, qb = f"mode=session&session={a}&open=session-map", f"mode=session&session={b}&open=session-map"
    ready_lines = "document.querySelectorAll('[data-testid=session-ready-line]').length"
    # (1) b, on Auto: an applied card's head and ready lines
    _open(c, rig, qb)
    c.wait("!!document.querySelector('[data-testid=session-truth]')", 30)
    _frame(rig, b, WROTE_AUTO, {}, undo="k1", this="auto", next_="auto", ready=["review"],
           later=[{"kind": "agent", "name": "checker", "why": "AG1", "step": "review"}])
    _wait(c, f"{ready_lines} >= 1 && !!{HEAD}", 10)
    out["b_before"] = c.js(SAID)
    # (2) a's page (its address, then F5): none of b's; then a box added to a's running map: its head and its tag
    _f5(c, rig, qa)
    c.wait(f"!!{DRAWN} && {BOXES}.length > 1", 30)
    out["a_none"] = c.js(SAID)
    plus = MAP.replace("lines:\n", "- {id: tester, agent: tester}\nlines:\n") + "- {from: main, to: tester, when: always}\n"
    _frame(rig, a, [{"kind": "map", "name": "shop", "added": False}], {"shop": _body(rig, "shop", plus)}, undo="k2", this="shop")
    _wait(c, f"!!{Q}('[data-box=tester][data-new]') && !!{HEAD}", 10)
    out["a_before"] = c.js(SAID)
    # (3) F5: the same head and tag; b's page after F5: its head and lines
    _f5(c)
    _wait(c, f"!!{Q}('[data-box=tester][data-new]') && !!{HEAD}", 15)
    out["a_after"] = c.js(SAID)
    c.js("window.name = 'keep-tab'; 1")  # batch 2 repair: the rig's fresh-tab clear stands aside (studio_session.py)
    _f5(c, rig, qa + "&again=1", go=True)  # its address opened again in this tab, not a reload: the tab's storage keeps it
    _wait(c, f"!!{Q}('[data-box=tester][data-new]') && !!{HEAD}", 15)
    out["a_again"] = c.js(SAID)
    c.js("window.name = ''; 1")
    _f5(c, rig, qb)
    _wait(c, f"{ready_lines} >= 1 && !!{HEAD}", 15)
    out["b_after"] = c.js(SAID)
    # (4) a's row gone (keepOpen drops it with the page's memory) and back: after F5 nothing of it is said
    rows.hide(a)
    out["dropped"] = _wait(c, f"!({_js_str(a)} in {KEPT}) && ({_js_str(b)} in {KEPT})", 15)
    rows.hidden.discard(a)
    rows.refresh()
    _f5(c, rig, qa)
    c.wait(f"!!{DRAWN} && {BOXES}.length > 1", 30)
    time.sleep(0.5)
    out["a_dropped"] = c.js(SAID)
    # (5) a storage that refuses every write: the page works as today (head and tag drawn, no error), nothing is kept
    c.js("window.name = 'refuse-storage'; 1")
    _f5(c)
    c.wait(f"!!{DRAWN} && {BOXES}.length > 1", 30)
    stored = c.js("sessionStorage.getItem('halo.studio.built') || ''") or ""
    plus2 = plus.replace("lines:\n", "- {id: tester2, agent: tester}\nlines:\n") + "- {from: main, to: tester2, when: always}\n"
    _frame(rig, a, [{"kind": "map", "name": "shop", "added": False}], {"shop": _body(rig, "shop", plus2)}, undo="k3", this="shop")
    _wait(c, f"!!{Q}('[data-box=tester2][data-new]') && !!{HEAD}", 10)
    out["refused"] = {**(c.js(SAID) or {}), "errors": page_errors(c),
                      "refusing": c.js("(() => { try { sessionStorage.setItem('x', '1'); return false; } catch (e) { return true; } })()"),
                      "same": c.js(f"(sessionStorage.getItem('halo.studio.built') || '') === {_js_str(stored)}")}
    _f5(c)
    c.wait(f"!!{DRAWN} && {BOXES}.length > 2", 30)
    time.sleep(0.5)
    out["refused_after"] = {**(c.js(SAID) or {}), "errors": page_errors(c)}
    return {"kept": out}


LINES = "[...document.querySelectorAll('[data-testid=session-lit-line] .mp-truth-line')].map((e) => e.textContent)"
CHANGED = f"{LINES}.filter((t) => t.startsWith('The workflow'))"  # one workflow or several: both forms
# batch 2 repair: where the drawing's top box, the truth block and the Open button stand (the line's room is held)
GEOM = f"""(() => {{ const r = (e) => (e ? Math.round(e.getBoundingClientRect().top * 2) / 2 : null);
  const tops = [...document.querySelectorAll('[data-testid=session-lit-map] [data-box]')].map(r), t = {Q}('[data-testid=session-truth]');
  return {{ box: tops.length ? Math.min(...tops) : null, truth: t ? Math.round(t.getBoundingClientRect().height * 2) / 2 : null,
           open: r({Q}('[data-testid=session-lit-open]')) }}; }})()"""


def plain(c, rig, rows: Rows, a: str, b: str) -> dict:
    """3.6.0.9 V batch 2: a workflow on a box of the session's drawing, written by a plain write, is said in the truth
    block's lines; a Builder card's own write is said by its head alone; no line for an agent file; kept over F5."""
    from halo_harness.crew import store
    from halo_harness.studio.files_live import file_sig
    fpath = store.path_for("workflow", "review", state_dir=rig.state)

    def flow(n: int) -> None:
        store.write_text(fpath, store.dump({**FLOW_REVIEW, "steps": [{"name": f"s{i}", "agents": ["coder"]} for i in range(n)]}))
    _told(rig, "review", lambda: flow(2), kind="workflows")
    _told(rig, "review-flow", lambda: _body(rig, "review-flow", FOLLOW_FLOW))
    rows.reset()
    rows.idle(b)
    rows.idle(a, map="review-flow", map_plain=False, map_scope="yours", map_path=str(store.path_for("map", "review-flow", state_dir=rig.state)),
              map_flows=["review"])  # as crew/map_facts.py row names the workflows on its map's boxes (batch 2 repair)
    _open(c, rig, f"mode=session&session={a}&open=session-map")
    out: dict = {"first": [_wait(c, f"{STEPROWS}.length === 2", 30), c.js(CHANGED)]}
    heard = "window.__jb.fw.filter((x) => x === 'workflows:review').length"
    g0 = c.js(GEOM)
    flow(3)  # (1) a plain write of the workflow
    out["plain"] = [_wait(c, f"{CHANGED}.length === 1 && {STEPROWS}.length === 3", 15), c.js(CHANGED)]
    out["still"] = [g0, c.js(GEOM)]  # nothing moved when the line came: its room was held from the first draw
    flow(4)  # (2) another one: still one line for it
    out["again"] = [_wait(c, f"{heard} >= 2 && {STEPROWS}.length === 4", 15), c.js(CHANGED)]
    # (3) a Builder card that wrote it (its file, then its frame with the file's hash): its head and not the line as well,
    # also once the watcher's frame for that very write has been heard and handled
    flow(5)
    _frame(rig, a, [{"kind": "workflow", "name": "review", "added": False}], {}, undo="p3", this="review-flow",
           sigs={"workflow:review": file_sig(fpath)})
    out["card"] = [_wait(c, f"{heard} >= 3 && {STEPROWS}.length === 5 && !!{HEAD}", 15),
                   c.js(f"{HEAD}?.querySelector('[data-testid=session-built-text]')?.textContent || ''"), c.js(CHANGED)]
    flow(6)  # (4) a different plain write right after: said again
    out["after"] = [_wait(c, f"{CHANGED}.length === 1 && {STEPROWS}.length === 6", 15), c.js(CHANGED)]
    # (5) an agent file: its model shows, no line
    before = c.js(LINES)
    starter = store.find("agent", "coder", state_dir=rig.state)
    coder = dict(store.read(starter[0]) or {}) if starter else {}
    store.write_text(store.path_for("agent", "coder", state_dir=rig.state), store.dump({**coder, "name": "coder", "model": "gpu-model-c"}))
    out["agent"] = [_wait(c, "window.__jb.fw.includes('agents:coder')", 15), before, c.js(LINES)]
    # (6) F5: the line is still there
    _f5(c)
    out["reload"] = [_wait(c, f"{CHANGED}.length === 1 && {STEPROWS}.length === 6", 15), c.js(CHANGED)]
    # (7) batch 2 repair: on Auto, a workflow this session ran (its row says so) is said too, its room held from the first draw
    ran = _room_rows(rows, a)
    rows.reset()
    rows.idle(b)
    rows.idle(a, map="auto", map_plain=True, agents=[ran[0], {**ran[1], "crew": {"workflow": "review"}}])
    _open(c, rig, f"mode=session&session={a}&open=session-map")
    c.wait(f"!!{DRAWN} && {BOXES}.length > 1", 30)
    time.sleep(0.5)
    a0 = [c.js(CHANGED), c.js(GEOM)]
    flow(7)
    out["auto"] = [_wait(c, f"{CHANGED}.length === 1", 15), *a0, c.js(CHANGED), c.js(GEOM)]
    return {"plain": out}


class JustBuiltDriver(MapDownDriver):
    width, height = 1280, 800

    @contextmanager
    def session(self, c):
        from halo_harness.crew import store
        from tests.helpers.studio_session import FAKE_SID, collect_page_errors, second_session
        from tests.helpers.studio_session_rig import StudioSessionRig
        with StudioSessionRig() as rig:
            _seed_shop(rig)
            store.write_text(store.path_for("workflow", "review", state_dir=rig.state), store.dump(FLOW_REVIEW))
            second_session(rig)
            rows = Rows(rig)
            collect_page_errors(c)  # with the Page domain on: the hooks run before any page script
            c.call("Page.addScriptToEvaluateOnNewDocument", source=HOOKS)
            args = (c, rig, rows, rig.act.session_id, FAKE_SID)
            steps = [s for s in (word, same, once, heads, fetch, room, follow, kept, plain) if not self.argv or s.__name__ in self.argv]
            yield tuple((fn, args) for fn in steps)


if __name__ == "__main__":
    sys.exit(JustBuiltDriver(sys.argv[1:]).main())
