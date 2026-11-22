"""tests.helpers.studio_run_parts -- what the 3.6.0.0 lit Map showed of a run, back on BOTH run drawings (Halo 3.6.0.2, P4
batch 13: Session's Live drawer and Agents -> 4 · Live, one set of parts, routes/crew/map/runParts.tsx), in headless
Chrome over tests/helpers/studio_session_rig.py and tests/helpers/studio_live_rig.py: the session runs on `shop`
(tests/helpers/studio_map_live.py), five helpers made up under main. No model is called. For each drawing (`session`,
`live`) every step is recorded on its own (`{where}.{step}.error` when it raised), so one missing part never hides another:

    clock    a helper in a Bash call: its row says the tool and its seconds, which grow (waited for, up to 15 s) while
             every box of the drawing keeps its rect (0.5 px)
    talk     main talks to the implementer (box code): the line main -> code pulses (`data-talk`), and no other line
    jk       the focus in the drawing: J picks the first box in drawing order, J the next, K back; with the card's Steer
             field focused, J is typed and the selection stays
    timers   every `setInterval` of the page is recorded from its boot: the intervals born while the drawing was shown
             (at least one: its clock) are all cleared once it is hidden (Session: Agents opened; Live: 3 · Map)
    under    main's box draws three of its rows and says "+{n} under it" for the rest; a press opens 4 · Live's Feed on
             main's `under:` page
    wait     (batch 13's repair) main hands work to the implementer, which is in a Bash call: the box holding it (code)
             carries the 3.6.0.0 outline (`data-waited`), the drawing's wait link says "waiting on: ... -> Bash ..." and
             a press picks that box (selected, its card open)
    waited   a drawn helper asks and waits on him: its row says "waiting for you · {n} s", the seconds grow, no box moves
    below    (P7, Session only) at 1280 x 800, before and while the wait link shows: "↓ n more below" keeps its rect and
             one line, the wait link sits inside the slot with its words whole; a link that fits the room kept leaves
             the slot's height, a longer one grows it once, in the frame it shows in (P9 batch 4: measured, any font)

    python -m tests.helpers.studio_run_parts
"""
from __future__ import annotations

import json
import sys
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.helpers.chrome_driver import Driver  # noqa: E402
from tests.helpers.studio_agents import key  # noqa: E402

ROOT = {"session": "[data-testid=session-lit-map]", "live": "[data-part=live] [data-testid=live-frame]"}
WORLD = {"session": ".mp-mini-world", "live": "[data-testid=live-world]"}
SCROLL = {"session": ".mp-mini-scroll", "live": "[data-testid=live-scroll]"}
VIEW = "document.querySelector('[data-testid=agents]')?.dataset.view"
HELPERS = [(f"h3lp3r0{i}", f"helper-{i}", f"Count the tests of suite {i}") for i in range(1, 6)]
IV = """(() => { const live = new Map(); window.__iv = live; const si = window.setInterval, ci = window.clearInterval;
  window.setInterval = function (fn, ms, ...r) { const id = si.call(window, fn, ms, ...r); live.set(id, [Number(ms) || 0, performance.now()]); return id; };
  window.clearInterval = function (id) { live.delete(id); return ci.call(window, id); }; })();"""


def q(where: str, sel: str = "") -> str:
    return f"document.querySelector('{ROOT[where]} {WORLD[where]}{(' ' + sel) if sel else ''}')"


def boxes(where: str) -> str:
    return f"[...document.querySelectorAll('{ROOT[where]} {WORLD[where]} > [data-box]')]"


def rects(where: str) -> str:
    return f"Object.fromEntries({boxes(where)}.map((b) => {{ const r = b.getBoundingClientRect(); return [b.dataset.box, [r.left, r.top, r.width, r.height]]; }}))"


def served(rig, sid: str) -> dict:
    """What Studio's server answers on GET live for the rig's session: its agents (main among them), busy, map."""
    try:
        status, v = rig.api("GET", "live")
    except Exception as e:  # the answer itself is the fact a red run needs
        return {"error": f"{type(e).__name__}: {e}"[:160]}
    rows = [s for h in v.get("harnesses") or [] for s in h.get("sessions") or [] if s.get("session_id") == sid]
    agents = [a.get("agent_id") for a in (rows[0].get("agents") or [])] if rows else []
    return {"status": status, "listed": bool(rows), "agents": len(agents), "main": "main" in agents,
            "busy": rows[0].get("busy") if rows else None, "map": rows[0].get("map") if rows else None}


def registry_facts(sid: str) -> dict:
    """3.6.0.4 S4, for a timeout message only (never in a polling loop: a probe is a connect to the session): the ids of
    the rows in sessions.json, the session's row's `unreachable_since`, and one timed connect probe of its endpoint.
    "not in file_rows" = the row left the registry; "in file_rows, probe False" = its accept queue is still full."""
    try:
        from halo_harness.remote import client, registry, runtime
        rows = registry._load(registry.registry_path())
        row = next((r for r in rows if r.get("session_id") == sid), {})
        endpoint = row.get("endpoint") or next((a.endpoint for a in runtime.actives() if a.session_id == sid), "")
        t0 = time.monotonic()
        ok = client.probe(endpoint) if endpoint else None
        return {"file_rows": [r.get("session_id") for r in rows], "unreachable_since": row.get("unreachable_since"),
                "probe": ok, "probe_ms": round((time.monotonic() - t0) * 1000)}
    except Exception as e:  # the message must still be raised
        return {"error": f"{type(e).__name__}: {e}"[:160]}


# 3.6.0.3 S: what the page held when a drawing did not draw (a macOS runner waited 40 s for five boxes on both drawings,
# from Session's `below` step on, and got none; not reproduced on the Linux VM under CPU throttling 20, two copies at
# once, a late feed and a slow session socket): shown, focused, its size, the drawing's frame and world, its boxes
PAGE = """(() => { const f = document.querySelector('$ROOT'), w = f && f.querySelector('$WORLD');
  const r = (e) => { if (!e) return null; const b = e.getBoundingClientRect(); return [b.left, b.top, b.width, b.height].map(Math.round); };
  return { visibility: document.visibilityState, focus: document.hasFocus(), size: [innerWidth, innerHeight],
    section: document.querySelector('[data-testid=section-tab][aria-selected=true]')?.textContent || null, frame: r(f), world: r(w),
    boxes: w ? [...w.querySelectorAll(':scope > [data-box]')].map((b) => b.dataset.box) : null,
    main_rows: w ? w.querySelectorAll('[data-box=main] [data-row]').length : null }; })()"""


def open_where(c, rig, lv, where: str) -> None:
    """The drawing opened, waited for on its facts in order within one 40 s budget, each named in its timeout: the
    server lists the session's agents, the page shows the drawing's frame, the drawing draws its boxes."""
    from tests.helpers.studio_session import boot_go, page_errors, url
    lv.refresh(map="shop", map_next="shop", busy=True)
    end = time.monotonic() + 40
    got = served(rig, lv.sid)
    while not (got.get("main") and got.get("agents", 0) >= 5) and time.monotonic() < end:
        time.sleep(0.25)
        got = served(rig, lv.sid)
    if not (got.get("main") and got.get("agents", 0) >= 5):
        raise TimeoutError(f"waited 40s for the server to list the session's agents (main and five more) on GET live, it answers "
                           f"{got}; the registry {registry_facts(lv.sid)}")
    boot_go(c, url(rig, f"mode=session&session={lv.sid}&open=session-map") if where == "session" else rig.url("agents", "&view=live"))
    page = PAGE.replace("$ROOT", ROOT[where]).replace("$WORLD", WORLD[where])
    for what, expr in ((f"the page to show the {where} drawing's frame", f"!!document.querySelector('{ROOT[where]}')"),
                       (f"the {where} drawing to draw five boxes and main's rows",
                        f"{boxes(where)}.length >= 5 && !!{q(where, '[data-box=main] [data-row]')}")):
        try:
            c.wait(expr, max(1.0, end - time.monotonic()))
        except TimeoutError:
            raise TimeoutError(f"waited 40s for {what}: the page {c.js(page)}, its errors {page_errors(c)[-3:]}; the server {served(rig, lv.sid)}; "
                               f"the registry {registry_facts(lv.sid)}") from None
    c.mouse("mouseMoved", 2, 890)  # the pointer off the drawing (R12 holds it still under the pointer)


def clock(c, lv, where: str, n: int) -> dict:
    mine = [h[0] for h in HELPERS]
    shown = c.js(f"[...{q(where, '[data-box=main]')}.querySelectorAll('[data-row]:not([hidden])')].map((r) => r.dataset.row)")
    aid = next(a for a in shown if a in mine)
    lv.tool(lv.rows[aid]["name"], "Bash", f"call-{where}-{n}")
    row = f"{q(where, f'[data-row={aid}]')}"
    c.wait(f"{row}?.querySelector('[data-testid=run-clock-secs]')?.textContent", 10)
    last = c.js(rects(where))
    for _ in range(12):  # the drawing settled after its first draw (two reads 500 ms apart alike); the tick is what is read
        time.sleep(0.5)
        now = c.js(rects(where))
        if now == last:
            break
        last = now
    s0, s1, moved = ticks(c, where, row)
    return {"tool": c.js(f"{row}.querySelector('[data-testid=run-clock]').dataset.tool"), "reads": [s0, s1], "moved": moved}


def until(c, expr: str, want, timeout: float = 10):
    """`expr`'s value once it equals `want` (waited for, so a slow runner only waits longer), else its last value."""
    import json
    try:
        c.wait(f"JSON.stringify({expr}) === {json.dumps(json.dumps(want, separators=(',', ':')))}", timeout)
    except Exception:
        pass
    return c.js(expr)


def ticks(c, where: str, row: str) -> tuple:
    """The row's clock read, then read again once its seconds have grown (waited for, up to 15 s: no wall-clock margin),
    and the boxes of the drawing whose rect moved between the two reads (0.5 px)."""
    text = f"{row}.querySelector('[data-testid=run-clock]').textContent"
    secs = f"(+(({text}).match(/· (\\d+) s$/) || [0, -1])[1])"
    r0, s0 = c.js(rects(where)), c.js(text)
    n0 = c.js(secs)
    try:
        c.wait(f"{secs} > {n0}", 15)
    except Exception:
        pass
    r1, s1 = c.js(rects(where)), c.js(text)
    return s0, s1, sorted(k for k in r0 if k in r1 and max(abs(a - b) for a, b in zip(r0[k], r1[k])) > 0.5)


def wait_link(c, lv, where: str) -> dict:
    """main hands work to the implementer (an `Agent` call) which is in a Bash call: the session waits on the implementer,
    so the box holding it (code) is outlined, and the drawing's wait link names it; a press picks that box."""
    outlined = f"{boxes(where)}.filter((b) => b.hasAttribute('data-waited')).map((b) => b.dataset.box)"
    link = f"document.querySelector('{ROOT[where]} [data-testid=run-wait]')"
    row = f"Math.round(document.querySelector('{ROOT[where]} [data-testid=run-wait-row]')?.getBoundingClientRect().height ?? -1)"
    out: dict = {"helper": lv.aid("implementer"), "row_before": c.js(row)}
    try:
        lv.tool("main", "Agent", f"call-{where}-agent")
        # P8: a long tool line -- the link shows its words whole on its reserved row, which keeps its height
        lv.tool("implementer", "Bash", f"call-{where}-bash", current="pytest -q tests/test_a_rather_long_module_name_for_the_slot.py")
        out["outlined"] = until(c, outlined, ["code"])
        c.wait(f"{link}?.textContent", 10)
        out.update({"link": c.js(f"{link}.textContent"), "leaf": c.js(f"{link}.dataset.leaf"), "row_after": c.js(row),
                    "whole": c.js(WHOLE.replace("$LINK", link))})
        c.js(f"{link}.click(); 1")
        out["picked"] = until(c, f"[({q(where, '> [data-selected]')}?.dataset.box || ''), !!document.querySelector('{ROOT[where]} [data-testid=map-step-in]')]", ["code", True])
    finally:
        lv.result("main", f"call-{where}-agent", "done", tool="Agent")
        lv.result("implementer", f"call-{where}-bash", "ok")
        lv.state("implementer", current="thinking")
    return out


# P8 batch 3: a tool's words of 90 wide letters -- the link shows them whole, and the row's height at the link's first
# draw (a frame watcher in the page) equals its height five frames later
WIDE = ("MWMWMWMWM " * 9).strip() + "W"
FRAMES = """(() => { const w = window.__wide = {first: null, later: null}; let n = -1;
  const tick = () => { const r = document.querySelector('$ROOT [data-testid=run-wait-row]'), l = document.querySelector('$ROOT [data-testid=run-wait]');
    if (n < 0 && l && (l.textContent || '').includes('MWMWMWMWM MWM')) { n = 0; w.first = Math.round(r.getBoundingClientRect().height); }
    else if (n >= 0 && ++n === 5) { w.later = Math.round(r.getBoundingClientRect().height); return; }
    requestAnimationFrame(tick); }; requestAnimationFrame(tick); return 1; })()"""


def wide_wait(c, lv, where: str) -> dict:
    """A helper waits on a tool whose words are 90 wide letters: the link's words whole (no '…' they do not have), its
    row's height at the link's first draw equal to its height five frames later."""
    link = f"document.querySelector('{ROOT[where]} [data-testid=run-wait]')"
    out: dict = {}
    c.js(FRAMES.replace("$ROOT", ROOT[where]))
    try:
        lv.tool("main", "Agent", f"call-{where}-wide-agent")
        lv.tool("implementer", "Bash", f"call-{where}-wide", current=WIDE)
        c.wait("window.__wide && window.__wide.later !== null", 15)
        out.update({"link": c.js(f"{link}?.textContent || null"), "rows": [c.js("window.__wide.first"), c.js("window.__wide.later")],
                    "whole": c.js(WHOLE.replace("$LINK", link))})
    finally:
        lv.result("main", f"call-{where}-wide-agent", "done", tool="Agent")
        lv.result("implementer", f"call-{where}-wide", "ok")
        lv.state("implementer", current="thinking")
    return out


# P8: an element's words whole: nothing overflows it and no ellipsis, nowrap or line clamp is on it or its row
WHOLE = """(() => { const e = $LINK; if (!e) return null; const cut = (x) => { const s = getComputedStyle(x);
  return s.textOverflow === 'ellipsis' || s.whiteSpace === 'nowrap' || s.webkitLineClamp !== 'none'; };
  return e.scrollWidth <= e.clientWidth + 1 && e.scrollHeight <= e.clientHeight + 1 && ![e, ...e.querySelectorAll('*'), e.parentElement].some(cut); })()"""


# P7: Session's bottom slot -- "↓ n more below" (its rect, how many lines its words take), the slot's height and width, and
# whether the wait link (when shown) lies inside the slot with its words whole
BELOW = """(() => { const s = document.querySelector('[data-testid=session-map-below]'); if (!s) return null;
  const m = s.querySelector('[data-testid=map-more-below]'), w = s.querySelector('[data-testid=run-wait]'), S = s.getBoundingClientRect();
  const lines = (el) => { const g = document.createRange(); g.selectNodeContents(el); return new Set([...g.getClientRects()].filter((x) => x.width > 0).map((x) => Math.round(x.top))).size; };
  const r = m && m.getBoundingClientRect(), W = w && w.getBoundingClientRect(), t = w && (w.querySelector('.mp-wait-words') || w);
  let nat = 0; if (m) { const k = m.cloneNode(true); k.style.cssText = 'position:absolute;visibility:hidden;white-space:nowrap;'; s.appendChild(k); nat = k.getBoundingClientRect().width; k.remove(); }
  return { more: r ? [r.left, r.top, r.width, r.height].map(Math.round) : null, lines: m ? lines(m) : 0, natural: !!r && Math.abs(r.width - nat) < 0.5,
    slot: [Math.round(S.width), Math.round(S.height)], wait: !!w,
    inside: !W || (W.top >= S.top - 0.5 && W.bottom <= S.bottom + 0.5 && W.left >= S.left - 0.5 && W.right <= S.right + 0.5),
    whole: !w || (w.scrollWidth <= w.clientWidth + 1 && w.scrollHeight <= w.clientHeight + 1
      && ![w, t].some((x) => { const c = getComputedStyle(x); return c.textOverflow === 'ellipsis' || c.whiteSpace === 'nowrap' || c.webkitLineClamp !== 'none'; })) }; })()"""


def settled(c, expr: str, tries: int = 12):
    """`expr`'s value once two reads 300 ms apart are alike (the drawing re-fitted after a resize), else its last value."""
    last = c.js(expr)
    for _ in range(tries):
        time.sleep(0.3)
        now = c.js(expr)
        if now == last:
            return now
        last = now
    return last


def below(c, lv, where: str) -> dict:
    """At 1280 x 800, before and while a wait link shows: "↓ n more below" keeps its rect, its own (natural) width and one
    line; the wait link lies inside the slot, its words whole. `fit`: a link whose words fit the room kept from the first
    draw (measured at this font) leaves the slot's height as it was; `grow`: a link one line longer grows the slot once, in
    the frame the link first shows in, to the link's own lines (P9 batch 4)."""
    out: dict = {}
    c.call("Emulation.setDeviceMetricsOverride", width=1280, height=800, deviceScaleFactor=1, mobile=False)
    try:
        # the drawer at its least width: its splitter dragged as far in as it goes (the drawer stops at its least width)
        # P9 batch 3 (CI, Windows and macOS: "got 455"): the step before left the page at 1500 px. On a slow runner the
        # splitter was read while the stage still had its 1500 px layout (the drawer 536 px, 0.37 of a 1448 px stage), so
        # the press missed the splitter once the drawer took its 1280 px width (455 px, 0.37 of 1228) and nothing was
        # dragged. Now the page has laid out 1280 px before the splitter is read, and the splitter is read again before
        # each drag until the drawer is at the least width the page itself states (aria-valuemin), three drags at most.
        drawer = "document.querySelector('[data-testid=session-map-below]')?.closest('[data-testid=stage-drawer]')"
        try:
            c.wait(f"innerWidth === 1280 && document.querySelector('[data-testid=stage]')?.clientWidth < 1280", 15)
        except TimeoutError:
            out["error"] = "the page did not take 1280 px"
        settled(c, f"(() => {{ const d = {drawer}, s = d?.querySelector(':scope > [data-testid=stage-splitter]');"
                   f" return [document.querySelector('[data-testid=stage]')?.clientWidth, d?.getBoundingClientRect().width, d?.dataset.max,"
                   f" s?.getBoundingClientRect().left, s?.getAttribute('aria-valuenow')]; }})()")
        for _ in range(3):
            sp = c.js(f"""(() => {{ const d = {drawer};
              const s = d?.querySelector(':scope > [data-testid=stage-splitter]'); if (!s) return null; const r = s.getBoundingClientRect();
              return [r.left + r.width / 2, r.top + r.height / 2, d.dataset.side, +s.getAttribute('aria-valuemin'), Math.round(d.getBoundingClientRect().width)]; }})()""")
            if not sp or sp[4] <= sp[3]:
                break
            c.drag(sp[0], sp[1], sp[0] + (-600 if sp[2] == "left" else 600), sp[1])
            c.mouse("mouseMoved", 2, 790)
            settled(c, f"Math.round({drawer}?.getBoundingClientRect().width || 0)")
        out["drawer"] = settled(c, "Math.round(document.querySelector('[data-testid=session-map-below]')?.closest('[data-testid=stage-drawer]')?.getBoundingClientRect().width || 0)")
        out["before"] = settled(c, BELOW)
        # P9 batch 4 (CI, macOS: the slot 42 -> 56 px with a long link): the room kept from the first draw is a number of
        # lines (the twins of a usual link); a link of longer words takes its room when it appears (the coordinator's
        # ruling of P8 batch 3). So the driver measures, at this page's own font, a tool line whose link fits the room
        # kept and the shortest one whose link needs more, and shows both, one after the other.
        m = out["measure"] = c.js(MEASURE.replace("$TEXTS", json.dumps([FIT, GROW]))) or {}
        if not m.get("fit") or not m.get("grow"):
            raise RuntimeError(f"no tool line measured to fit and to need one more line: {m}")
        link = "document.querySelector('[data-testid=session-map-below] [data-testid=run-wait]')?.textContent"
        for case, words, mark in (("fit", m["fit"][0], "test_fits_"), ("grow", m["grow"][0], "test_grows_")):
            c.js(GROWS.replace("$MARK", mark))
            lv.tool("main", "Agent", f"call-below-{case}-agent")
            lv.tool("implementer", "Bash", f"call-below-{case}", current=words)
            try:
                try:
                    c.wait(f"{link}?.includes({json.dumps(mark)})", 15)
                    c.wait("window.__grows && window.__grows.later !== null", 15)
                except TimeoutError:
                    out[f"{case}_link"] = c.js(f"{link} || null")
                out[case] = {"frames": c.js("window.__grows"), "settled": settled(c, BELOW)}
            finally:
                lv.result("main", f"call-below-{case}-agent", "done", tool="Agent")
                lv.result("implementer", f"call-below-{case}", "ok")
            c.wait(f"!({link} || '').includes({json.dumps(mark)})", 15)  # that wait is over (another may show)
    finally:
        lv.state("implementer", current="thinking")
        c.call("Emulation.setDeviceMetricsOverride", width=1500, height=900, deviceScaleFactor=1, mobile=False)
    return out


# P9 batch 4: tool lines of growing length (`n` of them, by letter), each a link "waiting on: implementer -> Bash {words}"
# measured in a hidden copy of the slot's own twin (its class, its width), out of the row's flow: the longest whose link
# fits the row kept from the first draw, and the shortest whose link needs more
FILL = "a_rather_long_module_name_for_the_slot_" * 8
FIT, GROW = "pytest -q tests/test_fits_", "pytest -q tests/test_grows_"
MEASURE = """(() => { const s = document.querySelector('[data-testid=session-map-below]'), row = s?.querySelector('[data-testid=run-wait-row]');
  const tw = row?.querySelector('.mp-wait-twin'); if (!tw) return null; const room = row.getBoundingClientRect().height;
  const k = tw.cloneNode(false); k.style.cssText = `position:absolute;left:0;top:0;width:${row.clientWidth}px`; row.appendChild(k);
  const words = (head, n) => head + '""" + FILL + """'.slice(0, n) + '.py', h = (t) => { k.textContent = 'waiting on: implementer -> Bash ' + t; return k.getBoundingClientRect().height; };
  const [fh, gh] = $TEXTS; let fit = null, grow = null;
  for (let n = 1; n < """ + str(len(FILL)) + """; n++) { const f = words(fh, n), hf = h(f); if (hf <= room + 0.5) fit = [f, Math.round(hf)]; else break; }
  for (let n = 1; n < """ + str(len(FILL)) + """; n++) { const g = words(gh, n), hg = h(g); if (hg > room + 0.5) { grow = [g, Math.round(hg)]; break; } }
  k.remove(); return { room: Math.round(room), fit, grow }; })()"""
# the frame the link with `$MARK` first shows in, and five frames later: the slot's height, "more below"'s rect, the link's
GROWS = """(() => { const w = window.__grows = {first: null, later: null}; let n = -1;
  const read = () => { const s = document.querySelector('[data-testid=session-map-below]'), m = s?.querySelector('[data-testid=map-more-below]');
    const l = s?.querySelector('[data-testid=run-wait]'), r = (e) => { const b = e.getBoundingClientRect(); return [b.left, b.top, b.width, b.height].map(Math.round); };
    return { slot: s ? Math.round(s.getBoundingClientRect().height) : 0, more: m ? r(m) : null, link: l ? Math.round(l.getBoundingClientRect().height) : 0 }; };
  const tick = () => { const l = document.querySelector('[data-testid=session-map-below] [data-testid=run-wait]');
    if (n < 0 && l && (l.textContent || '').includes('$MARK')) { n = 0; w.first = read(); }
    else if (n >= 0 && ++n === 5) { w.later = read(); return; }
    requestAnimationFrame(tick); }; requestAnimationFrame(tick); return 1; })()"""


def waited(c, lv, where: str) -> dict:
    """A drawn helper asks and waits on him: its row says what it waits for and for how long, and the seconds grow while
    no box moves."""
    mine = [h[0] for h in HELPERS]
    shown = c.js(f"[...{q(where, '[data-box=main]')}.querySelectorAll('[data-row]:not([hidden])')].map((r) => r.dataset.row)")
    aid = next(a for a in shown if a in mine)
    name = lv.rows[aid]["name"]
    row = q(where, f"[data-row={aid}]")
    try:
        lv.state(name, state="waiting")
        lv.ask(name)
        c.wait(f"{row}?.querySelector('[data-testid=run-clock-secs]')?.textContent", 10)
        s0, s1, moved = ticks(c, where, row)
        return {"reads": [s0, s1], "moved": moved, "kind": c.js(f"{row}.querySelector('[data-testid=run-clock]').dataset.wait || ''")}
    finally:
        lv.state(name, state="running")


def talk(c, lv, where: str) -> dict:
    lit = f"[...document.querySelectorAll('{ROOT[where]} {WORLD[where]} .mp-line[data-talk]')].map((p) => [p.dataset.from, p.dataset.to])"
    before = c.js(lit)
    lv.talk("main", "implementer", "Use the new discount table before tax")
    return {"before": before, "lit": c.wait(f"{lit}.length && {lit}", 8)}


def jk(c, where: str) -> dict:
    sel = f"({q(where, '> [data-selected]')}?.dataset.box || '')"
    order = c.js(f"{boxes(where)}.map((b) => [b.dataset.box, b.getBoundingClientRect()]).sort((a, b) => "
                 + ("a[1].left - b[1].left || a[1].top - b[1].top" if where == "live" else "a[1].top - b[1].top || a[1].left - b[1].left")
                 + ").map((x) => x[0])")
    c.js(f"document.querySelector('{ROOT[where]} {SCROLL[where]}').focus(); 1")
    got = []
    for ch, want in zip(("j", "j", "k"), (order[0], order[1], order[0])):
        key(c, ch)
        got.append(until(c, sel, want, 10))  # waited for: a slow runner only waits longer
    field = f"document.querySelector('{ROOT[where]} [data-testid=map-step-in] textarea, {ROOT[where]} [data-testid=map-step-in] input')"
    try:  # 3.6.0.14 O1-5: the selected box's sheet is usable (`map-step-in`) once placed: up to 1 s while it reads what its agent last said
        c.wait(f"!!{field}", 10)
    except TimeoutError:
        pass  # `field` below says it never came
    has = c.js(f"!!{field}")
    if has:
        c.js(f"{field}.focus(); 1")
        key(c, "j")
        try:
            c.wait(f"{field}.value.includes('j')", 10)  # the key landed in the field; the selection is read after it
        except Exception:
            pass
        time.sleep(1.0)
    return {"order": order[:3], "got": got, "field": has, "after_field": c.js(sel), "typed": c.js(f"{field}?.value || ''") if has else ""}


def timers(c, where: str) -> dict:
    from tests.helpers.studio_agents_live import alt
    if where == "session":
        c.js("document.querySelector('.ws-cell[data-panel=\"session-map\"] [data-testid=panel-collapse]').click(); 1")
        c.wait(f"!document.querySelector('{ROOT[where]}')", 10)
        t0 = c.js("performance.now()")
        c.js("document.querySelector('.section-view:not([hidden]) [data-testid=\"viewbar-btn\"][data-panel=\"session-map\"]').click(); 1")
    else:
        c.js("document.activeElement?.blur(); 1")
        key(c, "3")
        c.wait(f"{VIEW} === 'map'", 10)
        t0 = c.js("performance.now()")
        key(c, "4")
    c.wait(f"{VIEW if where == 'live' else 'true'} && !!{q(where, '[data-testid=run-clock-secs]')}", 20)
    time.sleep(1.5)  # the clock ticks while shown
    t1 = c.js("performance.now()")
    alive = f"[...window.__iv.values()].filter((v) => v[1] >= {t0} && v[1] <= {t1}).map((v) => v[0])"
    shown = c.js(alive)  # the intervals the drawing's showing started, alive while it is shown
    c.js("document.activeElement?.blur(); 1")
    if where == "session":
        alt(c, 2)
        c.wait("document.querySelector('[data-testid=\"section-tab\"][aria-selected=\"true\"]')?.textContent.startsWith('Agents')", 10)
    else:
        key(c, "3")
        c.wait(f"{VIEW} === 'map'", 10)
    time.sleep(1.5)
    return {"shown": shown, "left": c.js(alive)}


def under(c, where: str) -> dict:
    more = q(where, "[data-box=main] [data-testid=session-map-rows-more]")
    out = {"text": c.js(f"{more}?.textContent || ''"), "tag": c.js(f"{more}?.tagName || ''"),
           "hidden": c.js(f"{q(where, '[data-box=main]')}.querySelectorAll('[data-row][hidden]').length"), "of": c.js(f"{more}?.dataset.under || ''")}
    c.js(f"{more}.click(); 1")
    page = "document.querySelector('[data-part=live] [data-testid=map-feed-under]')"
    out["feed"] = c.wait(f"{VIEW} === 'live' && {page}?.dataset.of && [{VIEW}, {page}.dataset.of, "
                         "document.querySelector('[data-part=live] [data-testid=map-feed-filter]')?.value]", 15)
    return out


def drawing(c, rig, lv, where: str) -> dict:
    out: dict = {}
    for name, fn in (("clock", lambda: clock(c, lv, where, 1)), ("talk", lambda: talk(c, lv, where)), ("jk", lambda: jk(c, where)),
                     ("timers", lambda: (open_where(c, rig, lv, where), clock(c, lv, where, 2), timers(c, where))[2]),
                     ("under", lambda: (open_where(c, rig, lv, where), under(c, where))[1]),
                     ("wait", lambda: (open_where(c, rig, lv, where), wait_link(c, lv, where))[1]),
                     ("wide", lambda: (open_where(c, rig, lv, where), wide_wait(c, lv, where))[1]),
                     ("below", lambda: (open_where(c, rig, lv, where), below(c, lv, where))[1]),
                     ("waited", lambda: (open_where(c, rig, lv, where), waited(c, lv, where))[1])):
        if name == "below" and where != "session":
            continue  # the bottom slot is Session's drawer's
        try:
            if name == "clock":
                open_where(c, rig, lv, where)
            out.update({f"{where}.{name}.{k}": v for k, v in fn().items()})
        except Exception as e:  # each part on its own: one missing never hides another
            out[f"{where}.{name}.error"] = f"{type(e).__name__}: {e}"[:300]
    return out


class RunPartsDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}
    width, height = 1500, 900

    @contextmanager
    def session(self, c):
        from tests.helpers.studio_live_rig import Live
        from tests.helpers.studio_session import collect_page_errors
        from tests.helpers.studio_session_rig import StudioSessionRig
        from tests.helpers.studio_map_live import MAP
        with StudioSessionRig() as rig:
            from halo_harness.crew import store
            store.write_text(store.path_for("map", "shop", state_dir=rig.state), MAP)
            lv = Live(rig)
            for aid, name, task in HELPERS:
                lv.spawn(aid, name, "general-purpose", "or:mock/glm-5-coder", task)
                lv.rows[aid]["crew"] = {"map": "shop", "box": "main", "made_up": True}
            collect_page_errors(c)  # the page's errors, for open_where's message (the Page domain on)
            c.call("Page.addScriptToEvaluateOnNewDocument", source=IV)
            try:
                yield tuple((drawing, (c, rig, lv, w)) for w in ("session", "live") if not self.argv or w in self.argv)
            finally:
                lv.close()


if __name__ == "__main__":
    sys.exit(RunPartsDriver(sys.argv[1:]).main())
