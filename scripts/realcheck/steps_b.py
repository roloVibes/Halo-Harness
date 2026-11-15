"""scripts/realcheck/steps_b.py -- step 6: Studio, walked through the way a person clicks it, in headless Chrome
(tests/helpers/cdp.py, the suite's own driver), against a real `halo studio` started in a terminal.

Each section a person opens (Session; Agents with its Agents, Workflows and Map tabs; Local; Settings; Setup; Packs)
must draw within 5 s with no failed /api call and no console error; then each is opened again with every /api answer
held and let go one at a time (tests/helpers/hold_still.still: nothing a person would click moves), and two early
choices must survive their data landing (hold_still.survives). Last, one prompt from Session's Prompt panel in a new
session started from Studio, and its answer on the page. SKIP when the machine has no Chrome."""
from __future__ import annotations

import re
import time

from realcheck import fakes
from realcheck.core import URL, Fail, Skip, excerpt, split_url

WATCH = r"""(() => { if (window.__rc) return; const rc = window.__rc = {failed: [], errors: [], slow: []};
  const f = window.fetch.bind(window); const short = (s) => s.replace(/^.*?\/api\//, '').replace(/[?#].*$/, '');
  window.fetch = (u, o) => { const s = String(u && u.url || u); const p = f(u, o); const t0 = performance.now();
    if (/\/api\//.test(s)) p.then((r) => { const ms = Math.round(performance.now() - t0);
                                           if (ms > 1000) rc.slow.push(ms + ' ms ' + short(s));
                                           if (!r.ok) rc.failed.push(r.status + ' ' + short(s)); },
                                 (e) => { if (!/abort/i.test(String(e && e.name))) rc.failed.push('no answer ' + short(s)); });
    return p; };
  const ce = console.error.bind(console);
  console.error = (...a) => { rc.errors.push(a.map(String).join(' ').slice(0, 240)); ce(...a); };
  addEventListener('error', (e) => rc.errors.push('error: ' + (e.message || e.type)));
  addEventListener('unhandledrejection', (e) => rc.errors.push('unhandled: ' + String(e.reason).slice(0, 200))); })();"""

ANY = "!!document.querySelector('.section-view')"
SECTIONS = (  # what a person opens: (name, query, drawn when)
    ("Session", "mode=session", "!!document.querySelector('[data-testid=\"session-start\"], [data-testid=\"viewbar\"]')"),
    ("Agents: Agents", "mode=agents&view=crew", f"{ANY} && !!document.querySelector('[data-testid=\"viewbar\"]')"),
    ("Agents: Workflows", "mode=agents&view=workflows", "!!document.querySelector('[data-testid=\"agents\"]')"),
    ("Agents: Map", "mode=agents&view=map", "!!document.querySelector('[data-testid=\"map-bar\"]')"),
    ("Local", "mode=local", ANY),
    ("Settings", "mode=settings", "!!document.querySelector('[data-testid=\"settings-search\"]')"),
    ("Setup", "mode=setup", ANY),
    ("Packs", "mode=packs", ANY),
)
HOLD = ("session", "crew", "workflows", "map", "local", "setup", "settings")  # tests/helpers/studio_hold_still.VIEWS
CHOOSE = ("settings_search", "library_search")                              # ... and its CHOICES


def studio(ctx):
    from tests.helpers.chrome_driver import find_chrome, open_chrome
    if not find_chrome():
        raise Skip("no Chrome or Chromium on this machine (HALO_CHROME names one)")
    h = ctx.home("studio")
    t = ctx.terminal(h, "studio")
    got = t.wait_for(lambda s: re.search(URL, s), 30)
    if not got:
        ctx.end_leftovers(h)
        raise Fail("`halo studio` printed no address in 30 s: " + excerpt(t.plain(), 200))
    base, token = split_url(re.search(URL, t.plain()).group(0))

    def page(query: str) -> str:
        return f"{base}/?{query}&tour=off#t={token}"
    ev: dict = {"sections": {}, "hold_still": {}, "choices": {}}
    bad: list = []
    c = open_chrome()
    try:
        _sections(c, page, ev, bad)
        _hold(c, page, ev, bad)
        _prompt(c, page, ev, bad)
    finally:
        c.close()
        from realcheck.screen import quit_with_ctrl_c
        quit_with_ctrl_c(t)
        t.cleanup()
        ctx.end_leftovers(h)
    if bad:
        raise Fail("; ".join(bad[:6]) + (f" (+{len(bad) - 6} more)" if len(bad) > 6 else ""), ev)
    return f"{len(SECTIONS)} sections drew in 5 s, held still, a Studio prompt was answered", ev


def _sections(c, page, ev: dict, bad: list) -> None:
    c.call("Page.enable")
    ident = c.call("Page.addScriptToEvaluateOnNewDocument", source=WATCH)["identifier"]
    try:
        for name, query, ready in SECTIONS:
            c.go("about:blank")
            t0 = time.monotonic()
            c.go(page(query))
            try:
                c.wait(ready, 20)
                took = time.monotonic() - t0
            except TimeoutError:
                took = -1.0
            time.sleep(1.5)  # what lands right after the first paint counts too
            seen = c.js("window.__rc ? {failed: window.__rc.failed, errors: window.__rc.errors, slow: window.__rc.slow}"
                        " : null") or {}
            ev["sections"][name] = {"drawn_s": round(took, 2), **seen}
            if took < 0:
                bad.append(f"{name} did not draw in 20 s")
            elif took > 5.0:
                bad.append(f"{name} took {took:.1f}s to draw (budget 5 s)"
                           + (f", waiting on {', '.join(seen['slow'][:2])}" if seen.get("slow") else ""))
            if seen.get("failed"):
                bad.append(f"{name}: failed /api call(s) {seen['failed'][:3]}")
            if seen.get("errors"):
                bad.append(f"{name}: console error {seen['errors'][0][:160]!r}")
    finally:
        c.call("Page.removeScriptToEvaluateOnNewDocument", identifier=ident)


def _hold(c, page, ev: dict, bad: list) -> None:
    from tests.helpers.hold_still import clickables, still, survives
    from tests.helpers.studio_hold_still import CHOICES, VIEWS
    for name in HOLD:
        query, boxes, ready, before, then = VIEWS[name]
        try:
            got = still(c, page(query), clickables(*boxes), ready, before=before, then=then)
        except Exception as e:
            got = {"error": f"{type(e).__name__}: {e}"[:300]}
        ev["hold_still"][name] = {"moved": got.get("moved"), "measured": len(got.get("first") or {}),
                                  "error": got.get("error")}
        if got.get("error"):
            bad.append(f"hold still, {name}: {got['error'][:160]}")
        elif got.get("moved"):
            bad.append(f"hold still, {name}: {got['moved'][0]}")
    for name in CHOOSE:
        query, ready, choose, holds = CHOICES[name]
        try:
            got = survives(c, page(query), ready, choose, holds)
        except Exception as e:
            got = {"error": f"{type(e).__name__}: {e}"[:300]}
        ev["choices"][name] = {k: got.get(k) for k in ("made", "lost", "error")}
        if got.get("error") or not got.get("made") or got.get("lost"):
            bad.append(f"an early choice ({name}) did not survive: {got.get('error') or got.get('lost') or 'not made'}")


P = "document.querySelector('[data-testid=\"prompt-detail\"]')"
INPUT = "document.querySelector('[data-testid=\"prompt-input\"]')"
TEXTS = "[...document.querySelectorAll('[data-testid=\"prompt-text\"]')].map((x) => x.textContent).join(' ')"


def _prompt(c, page, ev: dict, bad: list) -> None:
    start = "document.querySelector('[data-testid=\"session-new-start\"]')"
    try:
        c.go("about:blank")
        c.go(page("mode=session"))
        c.wait(f"!!{start} && !{start}.disabled && 'form'", 30)
        c.click_on(start)
        sid = c.wait(f"{P}?.dataset.session", 60)
        t0 = time.monotonic()
        c.click_on(INPUT)
        c.type_text("RC-ASK from the Studio prompt")
        for kind in ("rawKeyDown", "keyUp"):
            c.call("Input.dispatchKeyEvent", type=kind, key="Enter", code="Enter", windowsVirtualKeyCode=13, modifiers=0)
        c.wait(f"{TEXTS}.includes({fakes.ANSWER!r}) && 'reply'", 60)
        ev["prompt"] = {"session": sid, "answer_s": round(time.monotonic() - t0, 2)}
        c.click_on("document.querySelector('[data-testid=\"prompt-end\"]')")
        c.click_on("document.querySelector('[data-testid=\"prompt-end-yes\"]')")
    except Exception as e:
        ev["prompt"] = {"error": f"{type(e).__name__}: {e}"[:300]}
        bad.append(f"a prompt from Studio's Prompt panel: {type(e).__name__}: {str(e)[:160]}")
