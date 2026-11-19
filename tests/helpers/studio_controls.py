"""tests.helpers.studio_controls -- every control of Session's Live drawer and of Agents' four views, pressed (Halo
3.6.0.2 R42: "Every control in Session's Live drawer and Agents' four views changes the page at once (MutationObserver
> 0; awaited after a fetch) or is removed"), in headless Chrome as a first-time user over tests/helpers/studio_session_rig.py
(this harness's real session), tests/helpers/studio_live_rig.py (its agent rows, the row's `map`, the frames a session on
a map sends) and tests/helpers/studio_session_map_down.py `Rows` (GET live's rows set per session). The map `shop` and a
past session that ran on it are seeded as tests/helpers/studio_map_live.py does; the maps of Session's drawer as
tests/helpers/studio_session_run.py and studio_session_map_down_draw.py do. No model is called: every agent command
Studio forwards to a session lands in `LOG` (a stand-in for the session's socket that answers as a session would: a
pause leaves the agent paused, a resume running), so nothing is sent anywhere.

`presses(c, controls)`: for each `(name, selector, setup, how)` it (1) runs `setup` (a callable, or None), (2) finds the
control (a visible element: `found`), brings it into view, rests the pointer away, arms a MutationObserver on
`document.body` (subtree, childList, attributes, characterData) (a `window.fetch` wrapper installed before the page's
scripts counts the requests in flight), and lets the page run NOISE_S seconds: what changes by itself in that time (a clock's seconds) is marked as the
page's own noise and not counted after, (3) presses it (`how`: None = a click at its centre with real mouse events;
("choose", value) = a select set as a pick reaches React; ("key", name) = a key on the focused control; a callable),
(4) waits, bounded 10 s, until something changed, then until no request is in flight and two animation frames passed,
(5) records `muts` (the changes counted; a scroll the press made counts as one: the page moved). The hover summary card
is never counted (a pointer's rest, not the press). A press whose setup failed records `error`.

    python -m tests.helpers.studio_controls [group ...]     groups: session map live agents workflows
The last stdout line is a JSON object: per group a list of {name, found, muts | error}, plus what each group read.
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

NOISE_S = 1.2  # how long the page is watched before a press for what changes by itself (a ticking clock is caught)
LOG: list = []  # the agent commands that reached "the session" (the forward's stand-in)

VISIBLE = """((e) => { if (!e || !e.isConnected) return false; const r = e.getBoundingClientRect(), s = getComputedStyle(e);
  return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && !e.closest('[hidden], [inert]')
    && (!e.closest('[aria-hidden=true]') || e instanceof SVGElement); })"""  # a twin kept for its room is aria-hidden; a drawing's svg is too
# Is `e` what a press at its centre reaches? `e` or a child of it is; an ANCESTOR is not (`e` is clipped out of its
# scroller's view or covered, e.g. History below the Map panel's visible bottom: the press lands on the stage), unless `e`
# takes no pointer itself (an svg shape, `pointer-events: none`), where the press is the ancestor's by design.
REACHED = """((e, at) => !!at && (e === at || e.contains(at) || (at.contains(e)
  && (e instanceof SVGElement || getComputedStyle(e).pointerEvents === 'none'))))"""
INTO_VIEW = f"""((e) => {{ const r = e.getBoundingClientRect(); const x = r.left + r.width / 2, y = r.top + r.height / 2;
  const at = x >= 0 && y >= 0 && x <= innerWidth && y <= innerHeight ? document.elementFromPoint(x, y) : null;
  if (r.width && !{REACHED}(e, at)) {{ e.scrollIntoView({{block: 'center', inline: 'center'}}); return 1; }} return 0; }})"""
HIT = f"""((e) => {{ const r = e.getBoundingClientRect(), at = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
  return {REACHED}(e, at) ? '' : (at ? (at.dataset.testid || at.className || at.tagName) + '' : 'nothing'); }})"""
ARM = """(() => { const C = window.__ctl || (window.__ctl = {});
  if (C.mo) C.mo.disconnect();
  C.muts = 0; C.scrolls = 0; C.phase = 'noise'; C.noise = new WeakSet(); C.raf = 0;
  const hover = (n) => n && n.nodeType === 1 && (n.id === 'halo-hover-card' || !!n.closest?.('#halo-hover-card'));
  C.mo = new MutationObserver((list) => { for (const r of list) {
    const t = r.type === 'characterData' ? r.target.parentElement : r.target;
    if (!t || hover(t) || [...r.addedNodes, ...r.removedNodes].some(hover)) continue;
    if (C.phase === 'noise') { if (t !== document.body) C.noise.add(t); } else if (!C.noise.has(t)) C.muts++; } });
  C.mo.observe(document.body, {subtree: true, childList: true, attributes: true, characterData: true});
  if (!window.__ctlScroll) { window.__ctlScroll = 1;
    addEventListener('scroll', () => { if (window.__ctl?.phase === 'press') window.__ctl.scrolls++; }, true); }
  return 1; })()"""
# installed before the page's own scripts (lib/api.ts binds `fetch` as it loads): the requests in flight, for "awaited after a fetch"
FETCH_JS = ("window.__ctlIn = 0; (() => { const f = window.fetch.bind(window); window.fetch = (...a) => { window.__ctlIn++;"
            " return f(...a).finally(() => { window.__ctlIn--; }); }; })();")
SETTLE = "(() => { const C = window.__ctl; C.raf = 0; requestAnimationFrame(() => requestAnimationFrame(() => { C.raf = 1; })); return 1; })()"


def choose(c, sel: str, value: str) -> None:
    """A select set the way a person's pick reaches React: the value setter, then `change`."""
    c.js(f"(() => {{ const s = {sel}; const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;"
         f" set.call(s, {value!r}); s.dispatchEvent(new Event('change', {{bubbles: true}})); }})(); 1")


def away(c) -> None:
    """The pointer rests in the window's bottom-right corner, over nothing a hover opens."""
    w, h = c.js("[innerWidth, innerHeight]")
    c.mouse("mouseMoved", w - 1, h - 1)


def press_one(c, sel: str, how=None) -> dict:
    scrolled = c.js(f"{INTO_VIEW}({sel})") == 1  # P4 batch 12: reachable only by scrolling its panel -- REPORTED
    away(c)
    c.js(ARM)
    time.sleep(NOISE_S)
    rec = {"hit": c.js(f"{HIT}({sel})"), "scrolled": scrolled}
    c.js("window.__ctl.phase = 'press'; 1")
    if how is None:
        x, y, w, h = c.rect(sel)
        c.mouse("mouseMoved", x + w / 2, y + h / 2)
        rec["under"] = c.js(f"{HIT}({sel})")  # what the pointer is over as it presses (a hover may have opened something)
        c.mouse("mousePressed", x + w / 2, y + h / 2)
        c.mouse("mouseReleased", x + w / 2, y + h / 2)
        away(c)  # the pointer does not rest on it: its hover card is not the press's change
    elif isinstance(how, tuple) and how[0] == "choose":
        choose(c, sel, how[1])
    elif isinstance(how, tuple) and how[0] == "key":
        c.js(f"({sel}).focus(); 1")
        c.key(how[1])
    else:
        how()
    try:
        c.wait("window.__ctl.muts + window.__ctl.scrolls > 0", 10)
    except TimeoutError:
        pass
    c.js(SETTLE)
    try:
        c.wait("!window.__ctlIn && window.__ctl.raf === 1", 10)
    except TimeoutError:
        rec["inflight"] = c.js("window.__ctlIn")
    rec["muts"] = c.js("(window.__ctl.mo.disconnect(), window.__ctl.phase = 'off', window.__ctl.muts + window.__ctl.scrolls)")
    return rec


def presses(c, controls) -> list:
    """Each control pressed as the module's docstring says; one record per control, in order."""
    out = []
    for ctl in controls:
        name, sel = ctl[0], ctl[1]
        setup = ctl[2] if len(ctl) > 2 else None
        how = ctl[3] if len(ctl) > 3 else None
        rec: dict = {"name": name}
        try:
            if setup is not None:
                setup()
            rec["found"] = bool(c.js(f"{VISIBLE}({sel})"))
            if rec["found"]:
                rec.update(press_one(c, sel, how))
        except Exception as e:  # the record says what failed; the next control is still pressed
            rec["error"] = f"{type(e).__name__}: {e}"[:300]
        out.append(rec)
    return out


def scrolled(recs: list) -> list:
    """The controls a press could reach only after scrolling their panel (out of sight at rest): a list for the output."""
    return [r["name"] for r in recs or [] if r.get("scrolled")]


def failures(recs: list) -> list:
    """`name: not found` / `name: nothing changed` / `name: <error>` for every record that is not a change."""
    bad = []
    for r in recs or []:
        if r.get("error"):
            bad.append(f"{r['name']}: {r['error']}")
        elif not r.get("found"):
            bad.append(f"{r['name']}: not found")
        elif not r.get("muts"):
            bad.append(f"{r['name']}: nothing changed" + (f" (the press landed on {r['hit']})" if r.get("hit") else ""))
    return bad


def stand_in(rig, rows) -> None:
    """Agent commands land in LOG instead of the session's socket, answered as a session would: a pause leaves the agent
    paused and a resume running (GET live's rows, `rows.states`), so the page sees what a real session would show."""
    from halo_harness.studio import live_agents_api as la
    orig = la.forward

    def fwd(sid, cmd, fields):
        if cmd not in la.AGENT_COMMANDS.values():
            return orig(sid, cmd, fields)
        LOG.append({"sid": sid, "cmd": cmd, **{k: fields.get(k) for k in ("agent_id", "text", "reason") if k in fields}})
        if cmd in ("pause", "resume") and fields.get("agent_id"):
            rows.set(sid, states={**rows.states.get(sid, {}), fields["agent_id"]: "paused" if cmd == "pause" else "running"})
        return 200, {"ok": True}
    la.forward = fwd
    rig.closers.append(lambda: setattr(la, "forward", orig))


class ControlsDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}
    width, height = 1500, 900

    @contextmanager
    def session(self, c):
        from tests.helpers.studio_live_rig import Live
        from tests.helpers.studio_session import collect_page_errors
        from tests.helpers.studio_session_map_down import Rows
        from tests.helpers.studio_session_rig import StudioSessionRig
        from tests.helpers.studio_map_live import EXTRA, seed
        from tests.helpers import studio_controls_steps as S
        from tests.helpers import studio_controls_more as V
        with StudioSessionRig() as rig:
            seed(rig)
            S.seed(rig)
            lv = Live(rig, extra=EXTRA)
            lv.rows["r3v1e2w0"]["square"] = {"name": "review", "engine": "steps"}
            lv.refresh(map="shop", map_next="shop")
            rows = Rows(rig)
            stand_in(rig, rows)
            collect_page_errors(c)
            c.call("Page.addScriptToEvaluateOnNewDocument", source=FETCH_JS)
            groups = (S.session, S.map_view, V.live, V.agents, V.workflows)
            names = {"session": S.session, "map": S.map_view, "live": V.live, "agents": V.agents, "workflows": V.workflows}
            steps = [names[a] for a in self.argv if a in names] or list(groups)
            try:
                yield tuple((fn, (c, rig, lv, rows)) for fn in steps)
            finally:
                lv.close()


if __name__ == "__main__":
    sys.exit(ControlsDriver(sys.argv[1:]).main())
