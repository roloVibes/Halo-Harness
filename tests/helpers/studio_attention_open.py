"""tests.helpers.studio_attention_open -- "open" on an ask that waits on you (Halo 3.6.0.1), in headless Chrome on the
driver base, over tests/helpers/glance_rig.py (a scratch home, every pack off, one fake session behind its real control
socket) plus a second, idle session of this harness. The owner's report from live use of 3.6.0.0: "when I get an
attention alert and chose 'open' nothing happens". tests/test_studio_attention_open.py reads it:

    python -m tests.helpers.studio_attention_open

A stub stands in for the browser's Notification before any page script runs (this browser allows it; `studio.alerts`
is `browser` in the scratch config) and records each notification; it can also make Studio's answer to the next `o`
name another target (`window.__openAs`), to check that the other kinds of row keep their homes.

Every case records what the page shows once it settles (or after the budget): the section and Agents' view, the
Live column's agent pick (`<harness>|<session>|<agent>`: the session Session shows and the agent its Feed is pointed
at), whether Session's Live drawer and Attention drawer are open, the box selected on the drawing (Session's Live
drawer, or Agents -> 4 · Live) and how many of the ask's choices its card shows, whether the Feed shows the ask's keys, the Attention row selected and its
answers, and the toasts. Since 3.6.0.2 (P4 batch 9) the door lands on the run's drawing: from Agents on 4 · Live, from
anywhere else on Session's Live drawer. The ask is the fake session's
permission card on its main agent; the other session is idle.

`row_b`: Session on the asking session, only the Feed: the ask arrives, the Live ask card's O (then the rig answers the
card and the queue empties, so the next ask is news to the next page).
`alerts`: a new ask's alert; its click from Session showing only the Feed of the OTHER session (b), from Local (e) and
from Agents -> Map showing a map the session does not run on (d).
`row_a`: Session on the other session, the Agent drawer opened and then Attention (one drawer per side at this width:
Attention is the one open); the row's O. `row_c` / `row_d`: Agents -> Map on the session's map / another map, Agents'
Attention open; the row's O.
`home_steward`: a steward's row still opens Local; `home_ended`: a row whose session ended (the stub rewrites the
queue's row to name an ended session) says so in one toast line and stays put.
The last stdout line is a JSON object of what it saw (exit 2: no Chrome). No model is called.
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

from tests.helpers.chrome_driver import Driver  # noqa: E402

Q = "document.querySelector"
SID2 = "attnopenother000000000000000002"
BUDGET = 12  # seconds a case may take to settle (Windows runners are slow); a case that never settles is recorded as is
STUB = """(() => {
  const notes = [], reads = [];
  class FakeNote { constructor(title, opts) { this.title = title; this.tag = (opts || {}).tag || ""; this.onclick = null;
    this.closed = false; notes.push(this); } close() { this.closed = true; } }
  FakeNote.permission = "granted";
  FakeNote.requestPermission = () => Promise.resolve("granted");
  Object.defineProperty(window, "Notification", { value: FakeNote, configurable: true, writable: true });
  const f = window.fetch.bind(window);
  window.fetch = (u, init) => { const s = String(u && u.href || u);
    if (s.includes("/api/live/attention/answer") && window.__openAs) {
      const open = window.__openAs; window.__openAs = null;
      return Promise.resolve(new Response(JSON.stringify({ ok: true, answer: "open", open }), { status: 200, headers: { "Content-Type": "application/json" } }));
    }
    const p = f(u, init);
    if (!s.includes("/api/live/attention") || s.includes("answer")) return p;
    p.then(() => reads.push(Date.now()), () => undefined);
    if (!window.__endRow) return p;
    // the ended case: the queue's row of `__endRow` names a session that has ended (`__endSid`)
    return p.then((r) => r.clone().json().then((j) => { (j.rows || []).forEach((x) => { if (x.id === window.__endRow) x.session_id = window.__endSid; });
      return new Response(JSON.stringify(j), { status: r.status, headers: { "Content-Type": "application/json" } }); })); };
  window.__notes = notes; window.__reads = reads;
})()"""
SV = ".section-view[data-section=\\\"session\\\"]"
PROBE = f"""(() => {{
  const sec = {Q}('.section-view:not([hidden])')?.dataset.section || '';
  const pick = {Q}("{SV} [data-testid=session-live-agent]");
  const btn = {Q}("{SV} [data-testid=viewbar-btn][data-panel=session-attention]");
  const row = {Q}("{SV} .ws-cell[data-panel=session-attention] [data-testid=fleet-attn-row][aria-selected=true]");
  const sessions = pick ? [...new Set([...pick.options].map((o) => o.value.split('|')[1]).filter(Boolean))] : [];
  const live = {Q}("{SV} [data-testid=viewbar-btn][data-panel=session-map]");
  const box = sec === 'agents' ? {Q}('[data-part=live] [data-box][data-selected]') : {Q}("{SV} [data-testid=session-lit-box][data-selected]");
  const card = sec === 'agents' ? {Q}('[data-part=live] [data-testid=map-step-in]') : box?.closest('.mp-down')?.querySelector('[data-testid=map-step-in]');
  return {{ section: sec, view: {Q}('[data-testid=agents]')?.dataset.view || '', live_open: live ? live.getAttribute('aria-pressed') === 'true' : null,
           box: box ? box.dataset.box : '', feed_ask: !![...document.querySelectorAll('[data-testid=session-live-ask] [data-testid=session-live-key]')].find((e) => e.offsetParent), ask_keys: card ? card.querySelectorAll('[data-testid=map-step-in-ask] [data-testid=map-step-in-ask-key]').length : 0,
           pin: pick ? pick.value : null, sessions, attn_open: btn ? btn.getAttribute('aria-pressed') === 'true' : null,
           row: row ? row.dataset.id : '', keys: row ? [...row.querySelectorAll('[data-testid=fleet-attn-key]')].map((k) => k.dataset.key) : [],
           truth: {Q}('[data-part=live] [data-testid=live-truth]')?.dataset.state || '',
           toasts: [...document.querySelectorAll('.toast:not([data-leaving]) .toast-text')].map((t) => t.textContent) }};
}})()"""


def _settle(c, cond: str) -> dict:
    """What the page shows once `cond` holds (a JS expression over `p`, the probe), or after BUDGET seconds."""
    try:
        c.wait(f"(() => {{ const p = {PROBE}; return {cond}; }})()", BUDGET)
    except Exception:
        pass
    return c.js(PROBE)


def _landed(key: str, where: str = "session") -> str:
    """The one door's end state (3.6.0.2 P4 batch 9: the run's drawing). From Agents: Agents -> 4 · Live, the asking
    agent's box selected, its card open with the ask's choices. Elsewhere: Session on the row's session, the asking agent
    in the Live column's pick (3.6.0.1), Session's Live drawer open, the box selected and its card on the ask (Attention: _attention)."""
    _h, sid, aid = key.split("|")
    if where == "agents":  # P8: this rig's session runs with no map; 4 · Live draws main's box under its T4 line
        return f"p.section === 'agents' && p.view === 'live' && p.box === {json.dumps(aid)} && p.ask_keys > 0"
    return (f"p.section === 'session' && p.pin === {json.dumps(key)} && p.sessions.join() === {json.dumps(sid)} && p.live_open === true"
            f" && p.box === {json.dumps(aid)} && p.ask_keys > 0")


def _attention(c, row: str) -> dict:
    """P8 (3.6.0.1's Session landing, restored): Attention on the asked row with its answers. At this rig's 1500 px
    the door opens Attention and then the Live drawer, and the room rule (lib/workspace/rules.ts R9: the oldest drawer
    closes when the room runs out) closes Attention again; so what is on screen is read, and when Attention is closed
    ONE press of its view-bar button shows it: the row the door selected, with its answers."""
    p = c.js(PROBE)
    out = {"want": row, "open_at_landing": p.get("attn_open") is True}
    btn = f"{Q}(\"{SV} [data-testid=viewbar-btn][data-panel=session-attention]\")"
    if p.get("attn_open") is not True:
        c.click_on(btn)
        p = _settle(c, "p.attn_open === true && !!p.row")
    out.update(open=p.get("attn_open") is True, row=p.get("row") or "", keys=p.get("keys") or [])
    if not out["open_at_landing"] and out["open"]:
        c.click_on(btn)  # closed again: the saved layout the next case boots with is the door's own
        _settle(c, "p.attn_open === false")
    return out


def _boot(c, rig, query: str, ready: str) -> None:
    c.go("about:blank")
    c.wait("location.href === 'about:blank'", 10)
    c.go(rig.url(query))
    c.wait(ready, 40)


def _tab(c, section: str) -> None:
    c.click_on(f"{Q}('[data-testid=\"section-tab\"][data-tab-id=\"{section}\"]')")
    c.wait(f"{Q}('.section-view:not([hidden])')?.dataset.section === '{section}'", 20)


def _pick_map(c, name: str) -> str:
    sw = f"{Q}('[data-testid=\"map-switcher\"]')"
    c.wait(f"!!{sw} && [...{sw}.options].some((o) => o.value === '{name}')", 30)
    c.js(f"(() => {{ const s = {sw}; Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set.call(s, '{name}');"
         " s.dispatchEvent(new Event('change', { bubbles: true })); return 1; })()")
    try:
        c.wait(f"{sw}.value === '{name}'", 20)
    except Exception:
        pass
    return c.js(f"{sw}.value")


def _unpin(c) -> None:
    """Between two alert cases: the Feed back to every agent, Attention and the Live drawer closed (Session, then back
    where it was), so the next landing is news."""
    pick = f"{Q}('{SV.replace(chr(92), '')} [data-testid=\"session-live-agent\"]')"
    c.js(f"(() => {{ const s = {pick}; if (!s) return 0; Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set.call(s, '');"
         " s.dispatchEvent(new Event('change', { bubbles: true })); return 1; })()")
    btn = f"{Q}('{SV.replace(chr(92), '')} [data-testid=\"viewbar-btn\"][data-panel=\"session-attention\"]')"
    for panel in ("session-attention", "session-map"):
        b = btn.replace("session-attention", panel)
        if c.js(f"{b}?.getAttribute('aria-pressed') === 'true'"):
            c.click_on(b)
            c.wait(f"{b}.getAttribute('aria-pressed') === 'false'", 10)


def _click_o(c, scope: str, row_id: str) -> None:
    key = f"{Q}('{scope} [data-testid=\"fleet-attn-row\"][data-id=\"{row_id}\"] [data-testid=\"fleet-attn-key\"][data-key=\"o\"]')"
    c.wait(f"!!{key}", 30)
    c.click_on(key)


class Ctx:
    def __init__(self, rig) -> None:
        from halo_harness.peers.identity import harness
        self.rig = rig
        self.hid = harness()["id"]
        self.key = f"{self.hid}|{rig.sid}|main"
        self.row = ""


SHOWS = "[...({q}('{sv} [data-testid=\"session-live-agent\"]')?.options || [])].some((o) => o.value.includes('{sid}'))"


def _shows(sid: str) -> str:
    """Session shows the session `sid` (the Live column's agent pick lists its agents)."""
    return SHOWS.format(q=Q, sv=SV.replace(chr(92), ""), sid=sid)


def row_b(c, x: Ctx) -> dict:
    """(b) Session on the asking session, only the Feed: the ask arrives while the page is open (the Live column shows an ask
    card for the frames it saw), and the card's O. Then the card is answered by the rig and the queue empties."""
    rig = x.rig
    _boot(c, rig, f"mode=session&session={rig.sid}", f"{_shows(rig.sid)} && window.__reads.length >= 1")
    time.sleep(1.0)  # the page's first read of the queue is stored
    rig.ask("ask")  # the fake session parks on permission card perm_1
    o = f"{Q}('[data-testid=\"session-live-ask\"] [data-testid=\"session-live-key\"][data-key=\"o\"]')"
    c.wait(f"!!{o} && !{o}.disabled && {o}.title.includes('Attention row')", 40)
    out = {"row_b_before": c.js(PROBE)}
    x.row = _queue(rig)[0]  # the card says its row is read: the one row that waits
    c.click_on(o)
    out["row_b"] = _settle(c, _landed(x.key))
    out["row_b"]["attn"] = _attention(c, x.row)
    _answer(rig)
    return out


def alerts(c, x: Ctx) -> dict:
    """The alert's click from (b) Session showing only the OTHER session's Feed, (e) Local, (d) Agents -> Map on a map the
    session does not run on: one notification, its onclick called from each."""
    rig = x.rig
    _boot(c, rig, f"mode=session&session={SID2}", f"{_shows(SID2)} && window.__reads.length >= 1")
    out: dict = {"alert_b_before": c.js(PROBE)}
    time.sleep(1.0)  # the page's first read of the queue is stored: what waited on load is not news, the ask below is
    rig.ask("ask")
    c.wait("window.__notes.length >= 1", 40)
    x.row = c.js("window.__notes[0].tag").replace("halo-ask-", "", 1)
    out["row"], out["key"] = x.row, x.key
    c.js("window.__notes[0].onclick(); 1")
    out["alert_b"] = _settle(c, _landed(x.key))
    out["alert_b"]["attn"] = _attention(c, x.row)
    _unpin(c)
    _tab(c, "local")
    c.js("window.__notes[0].onclick(); 1")
    out["alert_e"] = _settle(c, _landed(x.key))
    out["alert_e"]["attn"] = _attention(c, x.row)
    _unpin(c)
    _tab(c, "agents")
    c.wait(f"!!{Q}('[data-testid=\"agents-view-map\"]')", 20)
    c.click_on(f"{Q}('[data-testid=\"agents-view-map\"]')")
    out["alert_d_map"] = _pick_map(c, "ship-it")
    c.js("window.__notes[0].onclick(); 1")
    out["alert_d"] = _settle(c, _landed(x.key, "agents"))
    return out


def row_a(c, x: Ctx) -> dict:
    """(a) Session on the OTHER session, the Agent and Attention drawers open; the row's O."""
    from tests.helpers.studio_session import open_strip
    _boot(c, x.rig, f"mode=session&session={SID2}", _shows(SID2))
    open_strip(c, "session-agent")
    open_strip(c, "session-attention")
    pressed = f"{Q}('{SV.replace(chr(92), '')} [data-testid=\"viewbar-btn\"][data-panel=\"{{}}\"]')?.getAttribute('aria-pressed')"
    out = {"row_a_before": {"agent": c.js(pressed.format("session-agent")), **c.js(PROBE)}}
    _click_o(c, f"{SV.replace(chr(92), '')} .ws-cell[data-panel=\"session-attention\"]", x.row)
    out["row_a"] = _settle(c, _landed(x.key))
    out["row_a"]["attn"] = _attention(c, x.row)
    return out


def _row_on_map(c, x: Ctx, case: str, name: str) -> dict:
    """(c) / (d): Agents -> Map on `name`, Agents' Attention open; the row's O."""
    _boot(c, x.rig, f"mode=agents&view=map&map={name}", f"!!{Q}('[data-testid=\"map-switcher\"]') && !!{Q}('[data-testid=\"agents-attention\"]')")
    out = {f"row_{case}_map": _pick_map(c, name)}
    c.click_on(f"{Q}('[data-testid=\"agents-attention\"]')")
    _click_o(c, "[data-testid=\"fleet-attention\"]", x.row)
    out[f"row_{case}"] = _settle(c, _landed(x.key, "agents"))
    return out


def row_c(c, x: Ctx) -> dict:
    return _row_on_map(c, x, "c", "starter")


def row_d(c, x: Ctx) -> dict:
    return _row_on_map(c, x, "d", "ship-it")


def _home(c, x: Ctx, target: dict, cond: str) -> dict:
    """Studio's answer to the next `o` names `target`; the row's O from Agents' Attention."""
    _boot(c, x.rig, "mode=agents&view=map", f"!!{Q}('[data-testid=\"agents-attention\"]')")
    c.click_on(f"{Q}('[data-testid=\"agents-attention\"]')")
    c.js(f"window.__openAs = {json.dumps(target)}; 1")
    _click_o(c, "[data-testid=\"fleet-attention\"]", x.row)
    return _settle(c, cond)


def home_steward(c, x: Ctx) -> dict:
    return {"home_steward": _home(c, x, {"section": "live", "panel": "ollama", "host": "gpu-box"}, "p.section === 'local'")}


def home_ended(c, x: Ctx) -> dict:
    """A row whose session has ended (the queue's row names an ended session: the door reads the row, 3.6.0.2): Studio
    reads the sessions once, then one line says so and nothing moves."""
    ended = "endedsession00000000000000000009"
    gone = {"section": "live", "panel": "fleet-agent", "harness": x.hid, "session_id": ended, "agent_id": "main"}
    mark = c.call("Page.addScriptToEvaluateOnNewDocument", source=f"window.__endRow = {json.dumps(x.row)}; window.__endSid = '{ended}';")
    try:
        return {"home_ended": _home(c, x, gone, "p.toasts.some((t) => t.includes('ended'))")}
    finally:
        try:
            c.call("Page.removeScriptToEvaluateOnNewDocument", identifier=(mark or {}).get("identifier", ""))
        except Exception:  # noqa: BLE001 -- the last case: nothing after it reads the queue
            pass


def _api(rig, path: str) -> dict:
    from halo_harness.studio.owner_proof import HEADER, header_for
    from tests.helpers.kept_http import request
    _s, data, _h = request(rig.server.server_address[1], "GET", "/api/" + path, None,
                           {"Authorization": "Bearer " + rig.server.token, HEADER: header_for(rig.server)},
                           timeout=30, who=rig.server.token)
    return json.loads(data.decode("utf-8") or "{}")


def _queue(rig) -> list:
    """The ids of the rows that wait now."""
    return [r.get("id") for r in _api(rig, "live/attention").get("rows") or []]


def _answer(rig) -> None:
    """Allow the waiting card from the rig's side, and wait until the queue is empty (the next ask is news again)."""
    end = time.monotonic() + 30
    while time.monotonic() < end:
        slot = rig.session._permission_waiters.get("perm_1")
        if slot:
            slot["decision"] = "allow"
            slot["event"].set()
            break
        time.sleep(0.1)
    while time.monotonic() < end and _queue(rig):
        time.sleep(0.2)
    if _queue(rig):
        raise RuntimeError("the answered card stayed in the queue")


def _second_session(rig) -> None:
    """A second session of this harness (idle, its main agent only), registered the way the TUI registers."""
    from halo_harness.controller import Controller
    from halo_harness.remote import runtime
    from tests.helpers.fake_remote_session import FakeRegistry, FakeSession
    ctl = Controller(session=FakeSession(SID2), cwd=rig.cwd, registry=FakeRegistry()).start()
    rig.closers.append(lambda: (runtime.stop_for(ctl), ctl.quit()))
    runtime.start_for_controller(ctl)
    end = time.monotonic() + 30
    while time.monotonic() < end:
        got = _api(rig, "live")
        sids = {s.get("session_id") for h in got.get("harnesses", []) if h.get("local") for s in h.get("sessions") or []}
        if {SID2, rig.sid} <= sids:
            return
        time.sleep(0.2)
    raise RuntimeError("the two sessions did not both show in GET live")


class AttentionOpenDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from tests.helpers import glance_rig
        from tests.helpers.glance_rig import GlanceRig
        glance_rig.WAIT_S = 900.0  # the one card stays waiting through every case
        c.call("Page.enable")
        c.call("Page.addScriptToEvaluateOnNewDocument", source=STUB)
        rig = GlanceRig()
        try:
            from halo_harness.theme import set_config_value
            set_config_value("studio.alerts", "browser")
            _second_session(rig)
            x = Ctx(rig)
            yield tuple((fn, (c, x)) for fn in (row_b, alerts, row_a, row_c, row_d, home_steward, home_ended))
        finally:
            rig.close()


if __name__ == "__main__":
    sys.exit(AttentionOpenDriver(sys.argv[1:]).main())
