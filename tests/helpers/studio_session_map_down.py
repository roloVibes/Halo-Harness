"""tests.helpers.studio_session_map_down -- which session Session's Live drawer draws, and that it holds still (Halo
3.6.0.2 "Session map", R1 R2 R4 R5), in headless Chrome over tests/helpers/studio_session_rig.py (this harness's real
session A, three agents mid-work) and a second local session B (tests/helpers/studio_session.py `second_session`,
registered as started a minute before A). Each session's row in GET live is set per step through `Rows` (its map, busy,
started, parent, turns, its agents' states, or hidden as if it ended). No model is called.

    follows   B chosen in Session (`&session=`): the drawer and Cost speak of B, never "the first on a map" (R1)
    kept      the drawn session stays drawn while the other gets a turn and ends it (R1)
    turns     three turns of A: the map, its boxes, the head line and its top never change; main lit only in a turn (R2)
    noturn    a terminal session with no turn yet is drawn (R2)
    studio    an idle Studio-started session is never picked while another is open; once A ends A reads T8; alone the
              Studio one reads T10, draws no box and fetches no map (R4, R5)
    default   no pick: the Agent panel shows the newest working agent of the session shown (batch 7)
    stale     `&session=` of a session never listed: given up after two reads, Session as with no pick (batch 7)

    python -m tests.helpers.studio_session_map_down
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

from tests.helpers.chrome_driver import Driver  # noqa: E402

DRAWN = "document.querySelector('[data-testid=\"session-lit-map\"]')"
LINE = "document.querySelector('[data-testid=\"session-lit-line\"]')"
BOXES = "[...document.querySelectorAll('[data-testid=\"session-lit-box\"]')]"
COST = "document.querySelector('[data-testid=\"session-cost-detail\"]')"
# 3.6.0.2 R28 (P3 batch 6): the truth line is drawn from the row before the map is read; while it is read the drawing's
# root is `session-lit-map-wait`, so "drawn" is the drawing, or a line with no map to read (T8, T10)
WAIT = "document.querySelector('[data-testid=\"session-lit-map-wait\"]')"
FLEET_READS = "performance.getEntriesByType('resource').filter((e) => /\\/api\\/live(\\?|$)/.test(e.name)).length"
MAP_READS = "performance.getEntriesByType('resource').filter((e) => /\\/api\\/crew\\/map\\//.test(e.name)).length"
T10_SHOP = "New session from Studio, no message yet. It will run on shop."


class Rows:
    """GET live's rows of this harness with fields set per session (`set`), every agent's state set (`states`: an
    agent id, or "*" for the rest), or the session left out as if it ended (`hide`); restored on close."""

    def __init__(self, rig) -> None:
        from halo_harness.peers import local_view
        self.rig, self.lv, self.orig = rig, local_view, local_view.sessions
        self.fields: dict = {}
        self.states: dict = {}
        self.hidden: set = set()

        def sessions(list_live=None):
            out = []
            for r in self.orig(list_live):
                sid = r.get("session_id")
                if sid in self.hidden:
                    continue
                r = {**r, **self.fields.get(sid, {})}
                st = self.states.get(sid)
                if st:
                    r["agents"] = [{**a, "state": st.get(a.get("agent_id"), st.get("*", a.get("state")))} for a in r.get("agents") or []]
                out.append(r)
            return sorted(out, key=lambda r: (r.get("started") or 0, r.get("session_id") or ""))
        local_view.sessions = sessions
        local_view.forget()
        rig.closers.append(self.close)

    def set(self, sid: str, states: "dict | None" = None, **fields) -> None:
        self.fields.setdefault(sid, {}).update(fields)
        if states is not None:
            self.states[sid] = states
        self.refresh()

    def idle(self, sid: str, **fields) -> None:
        self.set(sid, {"*": "done"}, busy=False, status="idle", **fields)

    def turn(self, sid: str, **fields) -> None:
        self.set(sid, {"main": "running", "*": "done"}, busy=True, status="busy", **fields)

    def hide(self, sid: str) -> None:
        self.hidden.add(sid)
        self.refresh()

    def reset(self) -> None:
        self.fields.clear()
        self.states.clear()
        self.hidden.clear()
        self.refresh()

    def refresh(self) -> None:
        """Make the page read GET live again (a `sessions` frame), as Live.refresh does."""
        self.lv.forget()
        self.rig.server.events.publish({"session_id": None, "event": "sessions", "agent_id": None, "turn": None, "data": {}, "ts": time.time()})

    def close(self) -> None:
        self.lv.sessions = self.orig
        self.lv.forget()


def _page(c, rig, query: str) -> None:
    from tests.helpers.studio_session import boot_go, url
    boot_go(c, url(rig, query))
    c.wait("document.readyState !== 'loading'", 30)
    c.js("performance.setResourceTimingBufferSize(100000); 1")


def _reload(c, rows: Rows, n: int = 1) -> None:
    """Make the page read GET live `n` more times and wait for each answer (not a sleep)."""
    for _ in range(n):
        before = c.js(FLEET_READS) or 0
        rows.refresh()
        c.wait(f"{FLEET_READS} > {before}", 15)


def _read(c) -> dict:
    return c.js(f"""(() => {{ const m = {DRAWN}, l = {LINE};
      return {{ sid: m?.dataset.sid || l?.dataset.sid || '', map: m ? m.dataset.map : null,
               boxes: {BOXES}.map((b) => b.dataset.box).sort(), main: {BOXES}.find((b) => b.dataset.box === 'main')?.dataset.state || '',
               line: l?.textContent || '', state: l?.dataset.state || '', top: l ? Math.round(l.getBoundingClientRect().top * 2) / 2 : null,
               cost: {COST}?.dataset.session || '', text: (document.querySelector('[data-testid=\"session-map\"]')?.textContent || '').slice(0, 200) }}; }})()""") or {}


def _seed_shop(rig) -> None:
    from halo_harness.crew import store
    from tests.helpers.studio_map_live import MAP
    store.write_text(store.path_for("map", "shop", state_dir=rig.state), MAP)


def follows(c, rig, rows: Rows, a: str, b: str) -> dict:
    rows.reset()
    rows.set(a, map="shop")
    rows.turn(b, map="starter")
    _page(c, rig, f"mode=session&session={b}")
    c.wait(f"!!{DRAWN} && !!{COST}?.dataset.session", 30)
    return {"follows": _read(c)}


def kept(c, rig, rows: Rows, a: str, b: str) -> dict:
    rows.reset()
    rows.idle(a, map="shop")
    rows.idle(b, map="starter")
    _page(c, rig, "mode=session")
    c.wait(f"!!({DRAWN} || ({LINE} && !{WAIT})) && !!{COST}?.dataset.session", 30)
    seen = [_read(c)]
    x = seen[0].get("sid") or ""
    other = b if x == a else a
    rows.turn(other)
    _reload(c, rows, 2)
    seen.append(_read(c))
    rows.idle(other)
    _reload(c, rows, 2)
    seen.append(_read(c))
    return {"kept": seen}


def turns(c, rig, rows: Rows, a: str, b: str) -> dict:
    rows.reset()
    rows.idle(a, map="shop")
    rows.idle(b, map="starter")
    _page(c, rig, "mode=session")
    c.wait(f"!!{DRAWN} && {BOXES}.length >= 1 && !!{LINE}", 30)
    snaps, during = [_read(c)], []
    for _ in range(3):
        rows.turn(a)
        _reload(c, rows)
        c.wait(f"{BOXES}.find((b) => b.dataset.box === 'main')?.dataset.state === 'working'", 15)
        during.append(_read(c))
        rows.idle(a)
        _reload(c, rows)
        c.wait(f"{BOXES}.find((b) => b.dataset.box === 'main')?.dataset.state !== 'working'", 15)
        snaps.append(_read(c))
    return {"turns": snaps, "turns_during": during}


def noturn(c, rig, rows: Rows, a: str, b: str) -> dict:
    rows.reset()
    rows.idle(b, parent=None, turns=0, asked=False)
    _page(c, rig, f"mode=session&session={b}")
    try:
        c.wait(f"!!{DRAWN} && {BOXES}.length >= 1", 30)
    except TimeoutError:
        pass  # the read says what was there
    return {"noturn": _read(c)}


def studio(c, rig, rows: Rows, a: str, b: str) -> dict:
    out: dict = {}
    rows.reset()
    rows.idle(a)
    rows.idle(b, parent="studio:4242", turns=0, asked=False, started=time.time() + 60, map_next="shop")
    _page(c, rig, "mode=session")
    c.wait(f"!!({DRAWN} || ({LINE} && !{WAIT})) && !!{COST}?.dataset.session", 30)
    out["studio_first"] = _read(c)
    rows.hide(a)
    try:
        c.wait(f"{LINE}?.dataset.state === 'T8'", 15)
    except TimeoutError:
        pass
    out["studio_ended"] = _read(c)
    _page(c, rig, "mode=session")
    try:
        c.wait(f"{LINE}?.dataset.state === 'T10'", 30)
    except TimeoutError:
        pass
    _reload(c, rows)
    out["studio_alone"] = _read(c)
    out["studio_map_reads"] = c.js(MAP_READS)
    return out


AGENT = "document.querySelector('[data-testid=\"fleet-agent-detail\"]')"


def default(c, rig, rows: Rows, a: str, b: str) -> dict:
    """No pick: the Agent panel shows the newest working agent of the session Session shows (batch 7)."""
    rows.reset()  # A at work, as the rig runs it
    rows.idle(b)
    _page(c, rig, "mode=session&open=session-agent")
    try:
        c.wait(f"!!{AGENT}", 20)
    except TimeoutError:
        pass  # the read says what was there
    d = c.js(f"(() => ({{ key: {AGENT}?.dataset.key || '', state: {AGENT}?.dataset.state || '', cost: {COST}?.dataset.session || '',"
             f" empty: !!document.querySelector('[data-testid=\"fleet-agent-empty\"]') }}))()") or {}
    return {"default": d, "rig_sid": a}


def stale(c, rig, rows: Rows, a: str, b: str) -> dict:
    """A link to a session that ended before the page loaded: given up after two reads without it (batch 7)."""
    rows.reset()
    rows.set(a, map="shop")
    rows.idle(b)
    _page(c, rig, "mode=session&session=0e0e0e0e-ended-before-the-page")
    c.wait(f"{FLEET_READS} >= 1", 30)
    _reload(c, rows, 3)
    try:
        c.wait(f"{DRAWN}?.dataset.sid === '{a}' && {COST}?.dataset.session === '{a}'", 15)
    except TimeoutError:
        pass
    return {"stale": _read(c), "rig_sid": a}


class MapDownDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}
    width, height = 1440, 900

    def run(self, steps, emit: bool = True) -> dict:
        """Every step runs even after one before it failed (each resets the rows and loads its own page), so each test
        shows its own red, not the first failed step's; `failed` names every step that raised."""
        errs = []
        for step in steps:
            super().run([step], emit=False)
            if "failed" in self.out:
                errs.append(self.out.pop("failed"))
        if errs:
            self.out["failed"] = " | ".join(errs)[:1600]
        if emit:
            import json
            print(json.dumps(self.out))
        return self.out

    @contextmanager
    def session(self, c):
        from tests.helpers.studio_session import ERRS_JS, second_session
        from tests.helpers.studio_session_rig import StudioSessionRig
        with StudioSessionRig() as rig:
            _seed_shop(rig)
            second_session(rig)
            rows = Rows(rig)
            from tests.helpers.studio_session import FAKE_SID
            c.call("Page.addScriptToEvaluateOnNewDocument", source=ERRS_JS)
            args = (c, rig, rows, rig.act.session_id, FAKE_SID)
            yield tuple((fn, args) for fn in (follows, kept, turns, noturn, studio, default, stale))


if __name__ == "__main__":
    sys.exit(MapDownDriver(sys.argv[1:]).main())
