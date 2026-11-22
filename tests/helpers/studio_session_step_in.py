"""tests.helpers.studio_session_step_in -- stepping in from Session's Live drawer and its hover (Halo 3.6.0.2 R18 R43 R44),
in headless Chrome at 1280 x 800 over tests/helpers/studio_session_rig.py (session A, its rows set through GET live,
`Rows`) and the map frames the runtime sends. The agent commands Studio posts are taken by a stand-in for the forward to
the session's socket (`LOG`: what reached "the session"), so nothing runs and nothing is sent anywhere.

    card     the case-2 rig: tester's step row opens the card -- the sheet -- by its own box in the drawer (3.6.0.14
             O1-3: 6 px under it, else over it, else today's place; `geo` of READ), main's by main's box, named tester, Pause / Stop / the steer field aimed at tester; Pause reaches the session and reads
             Resume once the row is paused; 20 frames of Pause <-> Resume move no button; a steer reaches the session
    recheck  `hops`: a box with two live children (a row each, no buttons in a row: ONE Pause and Stop in the action row,
             aimed at the chosen row; a click on c2's row words moves them and the steer field to c2); a line's card is the child carrying that
             line; Stop confirmed after the child ended sends nothing and says "ended at {t}"; confirmed while it runs
             sends one agent stop and no session command; [Open in Agents -> Live] goes to Agents, the session kept;
             an off-map line's card offers "Open the map at main"
    done     a done and a next step row and a calm line: the state only, no Stop, Pause or steer field
    hover    the hover card on a box (name, agent, model, state, "Starts when: ... (from main)", its child) and on a
             workflow's block; no When label on Session's lines; a click opens the card, not the hover
    doors    Stop asked at each of the other four doors (Agents' row, the Feed, the command palette, the k key in the
             Agent panel), the agent ended before Yes: the confirm goes, nothing is sent, and one line says
             "{name} ended at {t}" / "ended at {t}" where Stop was pressed (P3 batch 8)

    python -m tests.helpers.studio_session_step_in [step ...]
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

from tests.helpers.studio_session_map_down import Rows  # noqa: E402
from tests.helpers.studio_session_run import M, RunDriver, _hop, _frame, _kid, _main, _open, _seed, case2  # noqa: E402

LOG: list = []  # the agent commands that reached "the session" (the forward's stand-in)
CARD = "document.querySelector('[data-testid=\"map-step-in\"]')"
TAB = "(document.querySelector('[data-testid=\"section-tab\"][aria-selected=\"true\"]')?.textContent || '')"
PANELS = "document.querySelectorAll('.section-view:not([hidden]) .panel-body:not([hidden])').length"
SESSION_CMDS = "performance.getEntriesByType('resource').filter((e) => /\\/api\\/live\\/[^/]+\\/[^/]+\\/command(\\?|$)/.test(e.name)).length"
# 3.6.0.14 O1-3: where the drawer's sheet `k` stands against its box: its `data-side`, its height at open (`data-words`), its
# target's anchor (as sheetPlace.ts anchorSel), the frame's padding box (`down`) and the drawing's scroll box (`view`)
SHEET_GEO = """((k) => { const R = (e) => { if (!e) return null; const r = e.getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; };
  const f = k.offsetParent, id = k.dataset.target || '', e = CSS.escape, cut = id.lastIndexOf(':'), fr = f && f.getBoundingClientRect();
  const sel = id.startsWith('member:') ? `[data-member="${e(id.slice(7))}"]` : id.startsWith('box:') ? `[data-box="${e(id.slice(4))}"]`
    : id.startsWith('group:') ? `[data-box="${e(id)}"]` : id.startsWith('head:') ? `[data-box][data-workflow="${e(id.slice(5))}"]`
    : id.startsWith('step:') && cut > 5 ? `[data-box][data-workflow="${e(id.slice(5, cut))}"]` : null;
  return { side: k.dataset.side || '', words: Number(k.dataset.words) || 0, anchor: sel && f ? R(f.querySelector(sel)) : null,
    down: f ? [fr.left + f.clientLeft, fr.top + f.clientTop, f.clientWidth, f.clientHeight] : null, view: R(f && f.querySelector('[data-pan]')) }; })"""


def sheet_rule(rect, geo) -> tuple:
    """O1-3, every figure read from the page: the drawer's sheet is the frame less 16 wide at 8 from its left; "below": 6
    under its box (its top kept 8 inside the view) and its foot 8 inside the view; "above": its foot 6 over its box;
    "fixed": its foot 40 over the frame's (at most the frame less 56); its height the smaller of its words at open and the room its side gives."""
    g = geo or {}
    a, d, v, side, words = g.get("anchor"), g.get("down"), g.get("view"), g.get("side"), g.get("words") or 0
    if not (rect and d and v and words):
        return False, f"nothing to read: {rect} {g}"
    near = lambda x, y: abs(x - y) <= 1.0  # noqa: E731
    left, top, width, h = rect
    vt, vb = v[1], v[1] + v[3]
    if not (near(left, d[0] + 8) and near(width, d[2] - 16)):
        return False, f"left {left} / width {width} against the frame {d}"
    if side == "below" and a:
        room, at = vb - 8 - top, near(top, max(a[1] + a[3] + 6, vt + 8)) and top + h <= vb - 8 + 1
    elif side == "above" and a:
        foot = min(a[1] - 6, vb - 8)
        room, at = foot - (vt + 8), near(top + h, foot)
    elif side == "fixed":
        room, at = d[3] - 56, near(top + h, d[1] + d[3] - 40)
    else:
        return False, f"side {side!r} with anchor {a}"
    return bool(at and near(h, min(words, room))), f"side {side}, rect {rect}, anchor {a}, view {v}, words {words}, room {room}"


READ = f"""(() => {{ const k = {CARD}; if (!k) return null;
  const R = (e) => {{ if (!e) return null; const r = e.getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; }};
  const q = (t) => k.querySelector(`[data-testid=${{t}}]`), n = (t) => k.querySelectorAll(`[data-testid=${{t}}]`).length;
  return {{ rect: R(k), inDrawer: !!{M}?.contains(k), geo: {SHEET_GEO}(k), title: q('map-step-in-title')?.textContent || '', state: q('map-step-in-state')?.textContent || '',
    rows: [...k.querySelectorAll('[data-testid=map-step-in-row]')].map((r) => ({{ key: r.dataset.key || '',
      text: r.querySelector('[data-testid=map-step-in-row-text]')?.textContent || '', pause: !!r.querySelector('[data-testid=map-step-in-pause]'),
      stop: !!r.querySelector('[data-testid=map-step-in-stop]'), ended: r.querySelector('[data-testid=map-step-in-ended]')?.textContent || '' }})),
    actions: (() => {{ const a = q('map-step-in-actions'); return a ? {{ key: a.dataset.key || '', pause: a.querySelectorAll('[data-testid=map-step-in-pause]').length,
      stop: a.querySelectorAll('[data-testid=map-step-in-stop]').length }} : null; }})(),
    pause: R(q('map-step-in-pause')), pauseText: q('map-step-in-pause')?.textContent || '', stop: R(q('map-step-in-stop')),
    steer: R(q('fleet-steer')), steerKey: k.querySelector('[data-steer-key]')?.dataset.steerKey || '', live: R(q('map-step-in-live')),
    liveText: q('map-step-in-live')?.textContent || '', map: q('map-step-in-map')?.textContent || '',
    n: {{ pause: n('map-step-in-pause'), stop: n('map-step-in-stop'), steer: n('fleet-steer'), live: n('map-step-in-live') }} }}; }})()"""
HOVER = """(() => { const h = document.getElementById('halo-hover-card'); if (!h) return null;
  return { kind: h.dataset.kind || '', lines: [...h.querySelectorAll('[data-testid=session-map-hover-line]')].map((e) => e.textContent) }; })()"""


def _patch(rig) -> None:
    """Agent commands land in LOG instead of the session's socket (the other reads still go through)."""
    from halo_harness.studio import live_agents_api as la
    orig = la.forward

    def fwd(sid, cmd, fields):
        if cmd in la.AGENT_COMMANDS.values():
            LOG.append({"sid": sid, "cmd": cmd, **{k: fields.get(k) for k in ("agent_id", "text", "reason") if k in fields}})
            return 200, {"ok": True}
        return orig(sid, cmd, fields)
    la.forward = fwd
    rig.closers.append(lambda: setattr(la, "forward", orig))


def _logged(cmd: str, aid: str, n: int = 1, s: float = 15) -> list:
    end = time.time() + s
    while time.time() < end:
        got = [x for x in LOG if x["cmd"] == cmd and x.get("agent_id") == aid]
        if len(got) >= n:
            return got
        time.sleep(0.1)
    return [x for x in LOG if x["cmd"] == cmd and x.get("agent_id") == aid]


def _key(a: str, aid: str) -> str:
    from halo_harness.peers.identity import harness
    return f"{harness()['id']}|{a}|{aid}"


def _close(c) -> None:
    c.click_on(f"{CARD}.querySelector('[data-testid=map-step-in-close]')")
    c.wait(f"!{CARD}", 5)


def _press(c, testid: str) -> None:
    c.click_on(f"{CARD}.querySelector('[data-testid={testid}]')")


def _line(c, f: str, t: str) -> None:
    """A real click at the middle of the line `f` -> `t` (on its hit path)."""
    pt = c.js(f"""(() => {{ const p = {M}?.querySelector('path[data-hit="{f}>{t}"]'); if (!p) return null; const L = p.getTotalLength(),
      q = p.getPointAtLength(L / 2), m = p.getScreenCTM(); return [m.a * q.x + m.c * q.y + m.e, m.b * q.x + m.d * q.y + m.f]; }})()""")
    if not pt:
        raise AssertionError(f"no hit path for the line {f} -> {t}")
    c.click(pt[0], pt[1])


def _hit_width(c, f: str, t: str):
    return c.js(f"(() => {{ const p = {M}?.querySelector('path[data-hit=\"{f}>{t}\"]'); return p ? parseFloat(getComputedStyle(p).strokeWidth) : null; }})()")


def card(c, rig, rows: Rows, a: str, b: str) -> dict:
    out: dict = {"key": _key(a, "w3")}
    LOG.clear()
    blk = case2(c, rig, rows, a, b)
    step3 = f"{blk}.querySelector('[data-testid=session-map-step][data-n=\"3\"]')"
    out["before"] = {"tab": c.js(TAB), "panels": c.js(PANELS)}
    c.click_on(step3)
    c.wait(f"!!{CARD}", 10)
    out["tester"] = c.js(READ)
    _close(c)
    c.click_on(f"{M}.querySelector('[data-box=main] .mp-name')")
    c.wait(f"!!{CARD}", 10)
    out["main"] = c.js(READ)
    _close(c)
    c.click_on(step3)
    c.wait(f"!!{CARD}", 10)
    _press(c, "map-step-in-pause")
    out["paused"] = _logged("pause", "w3")
    rows.set(a, states={"w3": "paused"})
    c.wait(f"{CARD}?.querySelector('[data-testid=map-step-in-pause]')?.textContent === 'Resume'", 15)
    out["resume"] = c.js(READ)
    frames = []
    for i in range(20):  # R12: the card's buttons hold still through the word change and the rows read again
        st = "running" if i % 2 == 0 else "paused"
        rows.set(a, states={"w3": st})
        c.wait(f"{CARD}?.querySelector('[data-testid=map-step-in-pause]')?.textContent === '{'Pause' if st == 'running' else 'Resume'}'", 15)
        frames.append(c.js(READ))
    out["frames"] = frames
    c.click_on(f"{CARD}.querySelector('[data-testid=fleet-steer]')")
    c.type_text("use the fast suite")
    c.key("Enter")
    out["steered"] = _logged("agent_steer", "w3")
    out["after"] = {"tab": c.js(TAB), "panels": c.js(PANELS), "card": c.js(f"!!{CARD}")}
    out["log"] = list(LOG)
    return {"card": out}


def recheck(c, rig, rows: Rows, a: str, b: str) -> dict:
    from tests.helpers.studio_session import alt
    out: dict = {"keys": {x: _key(a, x) for x in ("c1", "c2", "w1")}}
    LOG.clear()
    on = {"map": "hops", "box": "code", "line": "main -> code", "agent": "coder", "saved": True}
    _open(c, rig, rows, a, b, "hops", False, [_main(rows, a), _kid("c1", "coder", "running", crew=on), _kid("c2", "coder", "running", crew=on)])
    c.wait(f"{M}.querySelectorAll('[data-box=code] [data-testid=session-map-row]').length === 2", 20)
    c.click_on(f"{M}.querySelector('[data-box=code] .mp-name')")
    c.wait(f"!!{CARD}", 10)
    out["two"] = c.js(READ)
    c.click_on(f"{CARD}.querySelector('[data-testid=map-step-in-row][data-key=\"{out['keys']['c2']}\"] [data-testid=map-step-in-row-text]')")
    c.wait(f"{CARD}?.querySelector('[data-testid=map-step-in-actions]')?.dataset.key === '{out['keys']['c2']}'", 10)
    out["twoC2"] = c.js(READ)
    # (b) a line's card is the live child carrying it; confirmed after it ended: nothing is sent
    _open(c, rig, rows, a, b, "hops", False, [_main(rows, a), _kid("c1", "coder", "running", crew=on)])
    c.wait(f"!!{M}.querySelector('path[data-hit=\"main>code\"]')", 20)
    out["hitWidth"] = _hit_width(c, "main", "code")
    _line(c, "main", "code")
    c.wait(f"!!{CARD}", 10)
    out["line"] = c.js(READ)
    _press(c, "map-step-in-stop")
    c.wait("!!document.querySelector('[data-testid=fleet-confirm-yes]')", 10)
    rows.set(a, states={"c1": "done"})
    c.wait(f"!!{CARD}?.querySelector('[data-testid=map-step-in-ended]')", 15)
    c.click_on("document.querySelector('[data-testid=fleet-confirm-yes]')")
    time.sleep(1.5)
    out["endedLog"] = [x for x in LOG if x["cmd"] == "agent_stop"]
    out["ended"] = c.js(READ)
    # (c) confirmed while it runs: one agent stop for c1, no session command
    rows.set(a, states={})
    c.wait(f"!!{CARD}?.querySelector('[data-testid=map-step-in-stop]')", 15)
    _press(c, "map-step-in-stop")
    c.wait("!!document.querySelector('[data-testid=fleet-confirm-yes]')", 10)
    c.click_on("document.querySelector('[data-testid=fleet-confirm-yes]')")
    _logged("agent_stop", "c1")
    time.sleep(1.0)
    out["stops"] = [x for x in LOG if x["cmd"] == "agent_stop"]
    out["sessionCmds"] = c.js(SESSION_CMDS)
    # (e) [Open in Agents -> Live]: Agents, and Session keeps this session
    _press(c, "map-step-in-live")
    c.wait(f"{TAB}.includes('Agents')", 10)
    out["liveTab"] = c.js(TAB)
    alt(c, 1)
    c.wait(f"!!{M}", 15)
    out["back"] = {"tab": c.js(TAB), "sid": c.js(f"{M}.dataset.sid")}
    # (d) an off-map line: W on no box of `hops`, its step 1 running
    w1 = _kid("w1", "coder", "running", crew={"map": "hops", "workflow": "W", "step": 1, "agent": "coder", "saved": True})
    _open(c, rig, rows, a, b, "hops", False, [_main(rows, a, current="Workflow: W"), w1])
    _hop(rig, a, "main", "workflow:W", "start", workflow="W", off=True)
    _frame(rig, a, "map_step", {"map": "hops", "box": "workflow:W", "workflow": "W", "kind": "start", "steps": ["one", "two"]})
    c.wait(f"!!{M}.querySelector('path[data-hit=\"main>workflow:W\"]')", 20)
    _line(c, "main", "workflow:W")
    c.wait(f"!!{CARD}", 10)
    out["off"] = c.js(READ)
    _press(c, "map-step-in-map")
    c.wait(f"{TAB}.includes('Agents')", 10)
    c.wait("document.querySelectorAll('[data-testid=map-box][data-map-box=docs]').length > 0", 15)
    out["offTab"] = c.js(TAB)
    return {"recheck": out}


def done(c, rig, rows: Rows, a: str, b: str) -> dict:
    out: dict = {}
    blk = case2(c, rig, rows, a, b)
    for n in (1, 4):
        c.click_on(f"{blk}.querySelector('[data-testid=session-map-step][data-n=\"{n}\"]')")
        c.wait(f"!!{CARD}", 10)
        out[f"step{n}"] = c.js(READ)
        _close(c)
    on = {"map": "hops", "box": "code", "line": "main -> code", "agent": "coder", "saved": True}
    _open(c, rig, rows, a, b, "hops", False, [_main(rows, a), _kid("c1", "coder", "running", crew=on)])
    c.wait(f"!!{M}.querySelector('path[data-hit=\"main>docs\"]')", 20)
    _line(c, "main", "docs")
    c.wait(f"!!{CARD}", 10)
    out["calm"] = c.js(READ)
    return {"done": out}


def _rest_on(c, expr: str) -> None:
    # 3.6.0.2 R30 R31 (P3 batch 6): the pair and the Just built head take room over the drawing: a box under the scroll
    # box's edge is brought up first as a person would, by "↓ n more below" (one row a press; R11)
    seen = f"""(() => {{ const e = {expr}, sc = e?.closest('.mp-mini-scroll'); if (!e || !sc) return true;
      const r = e.getBoundingClientRect(), s = sc.getBoundingClientRect(); return r.bottom <= s.bottom + 0.5 && r.top >= s.top - 0.5; }})()"""
    for _ in range(4):
        if c.js(seen):
            break
        c.js("document.querySelector('[data-testid=map-more-below]')?.click(); 1")
        time.sleep(0.6)
    x, y, w, h = c.rect(expr)
    for dx in (0, 2, 4):  # a real move onto it (the hover starts on the first move, then rests)
        c.mouse("mouseMoved", x + w / 2 + dx, y + h / 2)
        time.sleep(0.05)


def hover(c, rig, rows: Rows, a: str, b: str) -> dict:
    out: dict = {}
    on = {"map": "hops", "box": "code", "line": "main -> code", "agent": "coder", "saved": True}
    w1 = _kid("w1", "coder", "running", crew={"map": "hops", "workflow": "W", "step": 1, "agent": "coder", "saved": True})
    _open(c, rig, rows, a, b, "hops", False, [_main(rows, a), _kid("c1", "coder", "running", crew=on, model="or:v/coder"), w1])
    _hop(rig, a, "main", "workflow:W", "start", workflow="W", off=True)
    c.wait(f"!!{M}.querySelector('[data-testid=session-map-block][data-workflow=W]') && {M}.querySelector('[data-box=code]')?.dataset.state === 'working'", 20)
    _rest_on(c, f"{M}.querySelector('[data-box=code] .mp-name')")
    c.wait("document.getElementById('halo-hover-card')?.dataset.kind === 'map' && !!document.querySelector('[data-testid=session-map-hover-line]')", 10)
    out["code"] = c.js(HOVER)
    c.mouse("mouseMoved", 1279, 799)
    c.wait("!document.getElementById('halo-hover-card')", 5)
    _rest_on(c, f"{M}.querySelector('[data-testid=session-map-block][data-workflow=W] [data-testid=session-map-block-head]')")
    c.wait("!!document.querySelector('[data-testid=session-map-hover-line]')", 10)
    out["block"] = c.js(HOVER)
    out["labels"] = c.js(f"{M}.querySelectorAll('[data-testid=map-label]').length")
    out["dots"] = c.js(f"{M}.querySelectorAll('.mp-dot').length")
    c.click_on(f"{M}.querySelector('[data-box=code] .mp-name')")
    c.wait(f"!!{CARD}", 10)
    time.sleep(0.5)
    out["click"] = {"card": c.js(f"!!{CARD}"), "hover": c.js("!!document.getElementById('halo-hover-card')")}
    return {"hover": out}


YES = "document.querySelector('[data-testid=fleet-confirm-yes]')"
TOASTS = "[...document.querySelectorAll('.toast:not([data-leaving]) .toast-text')].map((t) => t.textContent)"
FEED_STOP = "document.querySelector('[data-testid=session-live-stop]')"
AGENT_STOP = "document.querySelector('[data-panel=session-agent] [data-testid=fleet-stop]')"


def _ask(c, door: str) -> None:
    if door == "agents":
        c.click_on(AGENT_STOP)
    elif door == "feed":
        c.click_on(FEED_STOP)
    elif door == "palette":
        c.click_on("document.querySelector('.palette-btn')")
        c.wait("!!document.getElementById('cmd-fleet-stop')", 10)
        c.click_on("document.getElementById('cmd-fleet-stop')")
    else:  # the k key, in the Agent panel (outside any field)
        c.js("document.querySelector('[data-panel=session-agent] [data-testid=fleet-stream]')"
             ".dispatchEvent(new KeyboardEvent('keydown', {key: 'k', bubbles: true})); 1")


def doors(c, rig, rows: Rows, a: str, b: str) -> dict:
    from tests.helpers.studio_session import boot_go, url
    on = {"map": "hops", "box": "code", "line": "main -> code", "agent": "coder", "saved": True}
    rows.reset()
    rows.idle(b)
    rows.set(a, map="hops", map_plain=False, busy=True, status="busy", agents=[_main(rows, a), _kid("c1", "coder", "running", crew=on)])
    c.call("Emulation.setDeviceMetricsOverride", width=1280, height=800, deviceScaleFactor=1, mobile=False)
    boot_go(c, url(rig, f"mode=session&session={a}&open=session-agent"))  # the Agent drawer (one drawer at a time at 1280)
    steer = "document.querySelector('[data-testid=session-live-steer-open]')"  # 3.6.0.11: the Feed's Stop is in its Steer box, off until asked for
    try:
        c.wait(f"!!{steer} && !{steer}.disabled", 30)
        c.click_on(steer)
        c.wait(f"!!{AGENT_STOP} && !!{FEED_STOP}", 30)
    except TimeoutError:
        return {"doors": {"missing": c.js(f"""({{ agent: !!{AGENT_STOP}, feed: !!{FEED_STOP}, stops: [...document.querySelectorAll('[data-testid=fleet-stop]')].length,
          panels: [...document.querySelectorAll('[data-panel]')].map((e) => e.dataset.panel + (e.hidden ? ':hidden' : '')) }})""")}}
    line = {"agents": "document.querySelector('[data-testid=fleet-stop-ended]')?.textContent || ''",
            "feed": "document.querySelector('[data-testid=session-live-stop-ended]')?.textContent || ''"}
    out: dict = {}
    for door in ("agents", "feed", "palette", "key"):
        LOG.clear()
        rows.set(a, states={})  # every agent running
        try:
            c.wait(f"!{FEED_STOP}?.disabled && !{AGENT_STOP}?.disabled && !{YES}", 15)
            toasts = c.js(TOASTS) or []
            _ask(c, door)
            c.wait(f"!!{YES}", 10)
            rows.set(a, states={"*": "done"})  # it ends between the ask and the Yes
            c.wait(f"!!{FEED_STOP}?.disabled", 15)
            c.click_on(YES)
            got = line.get(door) or f"({TOASTS}).slice({len(toasts)}).find((t) => t.includes('ended at')) || ''"
            try:
                c.wait(f"!!({got})", 5)
            except TimeoutError:
                pass  # the read says what was there
            time.sleep(0.5)
            out[door] = {"line": c.js(got), "confirm": c.js(f"!!{YES}"), "stops": [x for x in LOG if x["cmd"] == "agent_stop"]}
        except (TimeoutError, AssertionError) as e:
            out[door] = {"error": str(e)[:300], "confirm": c.js(f"!!{YES}")}
            if c.js(f"!!{YES}"):
                c.key("Escape")
    return {"doors": out}


class StepInDriver(RunDriver):
    @contextmanager
    def session(self, c):
        from tests.helpers.studio_session import FAKE_SID, collect_page_errors, second_session
        from tests.helpers.studio_session_rig import StudioSessionRig
        with StudioSessionRig() as rig:
            _seed(rig)
            second_session(rig)
            _patch(rig)
            rows = Rows(rig)
            collect_page_errors(c)
            args = (c, rig, rows, rig.act.session_id, FAKE_SID)
            steps = [s for s in (card, recheck, done, hover, doors) if not self.argv or s.__name__ in self.argv]
            yield tuple((fn, args) for fn in steps)


if __name__ == "__main__":
    sys.exit(StepInDriver(sys.argv[1:]).main())
