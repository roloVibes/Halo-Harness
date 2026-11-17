"""tests.helpers.studio_session_just_built -- what was just built, shown at once (Halo 3.6.0.2 R26-R32), in headless
Chrome at 1280 x 800 over tests/helpers/studio_session_rig.py (this harness's real session A, a second session B). Every
fact reaches the page through GET live's rows (`Rows`) and the feed's frames (`builder_done` published as P2b sends it,
`files_changed` from Studio's own watcher). No model is called.

    word    the drawer closed: the view-bar word slot is there and empty, an applied build writes 'new' in it and nothing
            else moves, opens or pops up; opening the drawer empties it
    same    a same-name edit by a Builder card redraws from the frame's body; a plain file write redraws the open drawing
            with no 'new'; closed and opened again it is the newest version
    once    the pair: one map as plain text, two maps 'Running: {A} | Just built: {B}'; Just built chosen once, only while
            the pointer is outside and the pair was never pressed
    heads   the three Just built heads, the 'new {t}' tags, [Open in Workflows], tags kept over turns, gone when it ends
    fetch   nothing waits on the network: the head painted while every crew/map answer is held, one soft read for the
            running map, none for a body the frame brought, one for a body left out, none for left / failed / T8 / Empty,
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
# the page's event feed opened (a frame sent before it is lost); every /api request with its answer's status
HOOKS = r"""(() => { if (window.__jb) return; const jb = window.__jb = { open: 0, reqs: [], held: [], hold: false };
  const ES = window.EventSource; if (ES) { const W = function (u, o) { const es = new ES(u, o);
    es.addEventListener('open', () => { jb.open += 1; }); return es; }; W.prototype = ES.prototype; window.EventSource = W; }
  const f = window.fetch.bind(window);
  window.fetch = (u, o) => { const s = String(u && u.url || u); if (!/\/api\//.test(s)) return f(u, o);
    const r = { url: s.replace(/^.*?\/api\//, ''), status: 0, t: performance.now() }; jb.reqs.push(r);
    const go = () => f(u, o).then((x) => { r.status = x.status; return x; });
    if (jb.hold && /^crew\/map\//.test(r.url)) return new Promise((ok) => jb.held.push(ok)).then(go);
    return go(); }; })();"""
MAPREQS = "window.__jb.reqs.filter((r) => /^crew\\/map\\//.test(r.url))"
RECTS = "[...document.querySelectorAll('[data-testid=viewbar-btn]')].map((b) => { const r = b.getBoundingClientRect(); return [b.dataset.panel, r.left, r.top, r.width, r.height]; })"
BOXES = "[...document.querySelectorAll('[data-testid=session-lit-map] [data-box]')]"


def _size(c) -> None:
    c.call("Emulation.setDeviceMetricsOverride", width=1280, height=800, deviceScaleFactor=1, mobile=False)


def _open(c, rig, query: str) -> None:
    from tests.helpers.studio_session import boot_go, url
    _size(c)
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


def _parse(rig, text: str) -> dict:
    """A map's body as the frame carries it, without writing it where maps live (no files_changed follows)."""
    from halo_harness.crew import store
    p = Path(rig.state) / "parse-only.yaml"
    store.write_text(p, text)
    return store.read(p) or {}


def _frame(rig, sid: str, wrote: list, maps: dict, outcome: str = "applied", undo: str = "u", this: str = "starter") -> dict:
    from halo_harness.peers.identity import harness
    now = time.time()
    data = {"id": f"card-{undo}", "outcome": outcome, "wrote": wrote, "undo": undo, "next": None, "this_session": this,
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
    return c.js(f"""(() => {{ const p = {PAIR}, d = {DRAWN}, h = {HEAD};
      const btn = (w) => {{ const b = p?.querySelector(`[data-which=${{w}}]`); return b ? {{ pressed: b.getAttribute('aria-pressed'), marked: b.hasAttribute('data-new'), text: b.textContent }} : null; }};
      return {{ text: p?.textContent || '', h: p ? Math.round(p.getBoundingClientRect().height * 2) / 2 : null, buttons: p ? p.querySelectorAll('button').length : 0,
               running: btn('running'), built: btn('built'), map: d?.dataset.map || '', lit: d ? d.querySelectorAll('[data-lit]').length : -1,
               working: d ? d.querySelectorAll('[data-state=working]').length : -1, head: h?.firstChild?.nodeValue || '',
               headButton: h?.querySelector('button')?.textContent || '' }}; }})()""") or {}


def _press(c, which: str) -> None:
    c.js(f"{PAIR}?.querySelector('[data-which={which}]')?.click(); 1")


def word(c, rig, rows: Rows, a: str, b: str) -> dict:
    rows.reset()
    rows.idle(b)
    rows.idle(a, map="starter", map_plain=True)
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
    rows.reset()
    rows.idle(b)
    rows.idle(a, map="starter", map_plain=True)
    _open(c, rig, f"mode=session&session={a}&open=session-map")
    c.wait(f"!!{DRAWN} && !!{PAIR}", 30)
    out["plain"] = _pair(c)
    _frame(rig, a, built, {"review-flow": body}, undo="o1")
    _wait(c, f"{PAIR}?.textContent.includes('Just built: review-flow') && {DRAWN}?.dataset.map === 'review-flow'", 10)
    out["first"] = _pair(c)
    _press(c, "running")
    _wait(c, f"{DRAWN}?.dataset.map === 'starter'", 10)
    out["back"] = _pair(c)
    _frame(rig, a, built, {"review-flow": body}, undo="o2")
    _wait(c, f"{PAIR}?.querySelector('[data-which=built]')?.hasAttribute('data-new')", 10)
    time.sleep(0.5)
    out["second"] = _pair(c)
    # (b) a new page, the pointer on the drawing when the frame lands: only the tab is marked, never a jump later
    _open(c, rig, f"mode=session&session={a}&open=session-map")
    c.wait(f"!!{DRAWN} && !!{PAIR}", 30)
    r = c.js(f"(() => {{ const r = {DRAWN}.querySelector('.mp-mini-scroll').getBoundingClientRect(); return [r.left + r.width / 2, r.top + 20]; }})()")
    c.mouse("mouseMoved", r[0], r[1])
    time.sleep(0.3)
    _frame(rig, a, built, {"review-flow": body}, undo="o3")
    _wait(c, f"{PAIR}?.querySelector('[data-which=built]')?.hasAttribute('data-new')", 10)
    out["held"] = _pair(c)
    c.mouse("mouseMoved", 1279, 799)
    time.sleep(1.0)
    out["held_out"] = _pair(c)
    # (c) the pair pressed once: a later build only marks its tab
    _press(c, "running")
    _frame(rig, a, [{"kind": "map", "name": "third", "added": True}], {"third": _body(rig, "third", THIRD)}, undo="o4")
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
    _frame(rig, a, [{"kind": "workflow", "name": "solo", "added": True}], {}, undo="h1", this="shop")
    _wait(c, f"{HEAD}?.textContent.includes('solo')", 10)
    out["workflow"] = _pair(c)
    out["workflow_section"] = c.js(f"{Q}('.section-view:not([hidden])')?.dataset.section || ''")
    c.js(f"{HEAD}?.querySelector('button')?.click(); 1")
    _wait(c, f"{Q}('[data-testid=agents]')?.dataset.view === 'workflows' && {Q}('[data-testid=flow-form]')?.dataset.name === 'solo'", 10)
    out["opened"] = c.js(f"""(() => ({{ section: {Q}('.section-view:not([hidden])')?.dataset.section || '',
      view: {Q}('[data-testid=agents]')?.dataset.view || '', text: {Q}('[data-testid=flow-form]')?.dataset.name === 'solo' }}))()""")
    # (b) a box added to the running map: the same drawing, tagged, and its head
    _open(c, rig, f"mode=session&session={a}&open=session-map")
    c.wait(f"!!{DRAWN} && {BOXES}.length > 1", 30)
    plus = MAP.replace("lines:\n", "- {id: tester, agent: tester}\nlines:\n") + "- {from: main, to: tester, when: always}\n"
    _frame(rig, a, [{"kind": "map", "name": "shop", "added": False}], {"shop": _body(rig, "shop", plus)}, undo="h2", this="shop")
    _wait(c, f"!!{Q}('[data-box=tester][data-new]')", 10)
    out["running"] = {**_pair(c), **(c.js(f"""(() => ({{ tag: {Q}('[data-box=tester] [data-testid=session-map-new]')?.textContent || '',
      others: [...document.querySelectorAll('[data-testid=session-lit-map] [data-box][data-new]')].map((x) => x.dataset.box) }}))()""") or {})}
    # (c) any other map
    _frame(rig, a, [{"kind": "map", "name": "third", "added": True}], {"third": _body(rig, "third", THIRD)}, undo="h3", this="shop")
    _wait(c, f"{HEAD}?.textContent.includes('does not run on it')", 10)
    out["other"] = _pair(c)
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
    _body(rig, "shop", MAP)
    _on_shop(rig, rows, a, b)
    hold = c.call("Page.addScriptToEvaluateOnNewDocument", source="window.__jb && (window.__jb.hold = true);")["identifier"]
    try:
        _open(c, rig, f"mode=session&session={a}&open=session-map")
    finally:
        c.call("Page.removeScriptToEvaluateOnNewDocument", identifier=hold)
    _wait(c, f"{Q}('[data-testid=session-lit-line] .mp-truth-line') && !!{Q}('[data-testid=session-status]') && !!{PAIR}", 20)
    time.sleep(0.5)
    out["painted"] = c.js(f"""(() => ({{ truth: {Q}('[data-testid=session-lit-line] .mp-truth-line')?.firstChild?.nodeValue || '',
      status: {Q}('[data-testid=session-status]')?.textContent || '', pair: {PAIR}?.textContent || '',
      done: {MAPREQS}.filter((r) => r.status).length, asked: {MAPREQS}.map((r) => r.url), held: window.__jb.held.length }}))()""")
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
    m3 = mark()
    rows.hide(a)
    _wait(c, f"{Q}('[data-testid=session-truth]')?.dataset.state === 'T8'", 10)
    rows.hide(b)
    _wait(c, f"{Q}('[data-testid=session-truth]')?.dataset.state === 'Empty'", 15)
    time.sleep(1.0)
    out["t8_empty"] = c.js(f"{MAPREQS}.slice({m3}).map((r) => r.url)")
    out["failed"] = c.js("window.__jb.reqs.filter((r) => r.status >= 400).map((r) => `${r.status} ${r.url}`)")
    _body(rig, "shop", MAP)
    return {"fetch": out}


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
            steps = [s for s in (word, same, once, heads, fetch) if not self.argv or s.__name__ in self.argv]
            yield tuple((fn, args) for fn in steps)


if __name__ == "__main__":
    sys.exit(JustBuiltDriver(sys.argv[1:]).main())
