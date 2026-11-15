"""tests.helpers.hold_still -- "the page holds still while its data lands" (3.6.0.0 R5c), for any Studio driver.

A person (or a driver) clicks what the page shows first, and on a slow machine the click is handled after more data has
landed. A control that moves, goes away or is covered when an answer lands takes that click somewhere else: Run a goal
moved 94 px when the map list landed, and "Goal runs, files, Compare" moved when the map and its past runs landed. Both
failed only on slow CI runners. This check makes the order of the answers deterministic:

    from tests.helpers.hold_still import still
    got = still(c, url, {"run-goal": "document.querySelector('[data-testid=map-run-goal]')", ...},
                ready="!!document.querySelector('[data-testid=map-bar]')")

1. every `fetch` to `/api/` waits at a gate (a script that runs before the page's own);
2. once `ready` holds (the fewest answers that draw it let go first, oldest first), each named control on the page is
   measured: its first paint. `before(c)` is a first click made then (open a drawer), and `then` what it must draw;
3. the held answers are let go one at a time, oldest first (the ones they lead to join the queue); after each lands and
   the page has drawn, each measured control is measured again and the element at its first centre is read;
4. `moved` lists every control that moved, went away or was covered, and after which answer. Empty: it held still.
   It ends once nothing has asked for `quiet` seconds (a poll that comes back later is not waited for).

A control that is not on the page at first paint is not measured: drawing a control only once it can work is fine.
`ready` and the controls are JS expressions. The gate is taken off afterwards; the page is left as it ended."""
from __future__ import annotations

import json
import time

GATE = """(() => { if (window.__hold) return; const f = window.fetch.bind(window); const q = [];
  const h = window.__hold = { queue: q, inflight: 0, seen: [], next() { const e = q.shift(); if (!e) return null; h.seen.push(e.path); e.go(); return e.path; } };
  window.fetch = (u, o) => { const s = String(u && u.url || u); if (!/\\/api\\//.test(s)) return f(u, o);
    const path = s.replace(/^.*?\\/api\\//, '').replace(/[?#].*$/, '');
    return new Promise((go) => q.push({ path, go })).then(() => { h.inflight++; return f(u, o).finally(() => setTimeout(() => h.inflight--, 0)); }); }; })();"""

# the answer's body read and the page drawn: a task, then two frames
DRAWN = "new Promise((r) => setTimeout(() => requestAnimationFrame(() => requestAnimationFrame(() => r(1))), 30))"


def _measure(c, controls: dict) -> dict:
    parts = ", ".join(f"{json.dumps(name)}: (() => {{ const e = {expr}; if (!e) return null; const r = e.getBoundingClientRect(); "
                      f"return r.width || r.height ? [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)] : null; }})()"
                      for name, expr in controls.items())
    return c.js(f"({{{parts}}})")


def _under(c, controls: dict, first: dict) -> dict:
    """Each measured control: is the element at its first-paint centre the control (or inside it)?"""
    out = {}
    for name, rect in first.items():
        x, y = rect[0] + rect[2] / 2, rect[1] + rect[3] / 2
        out[name] = c.js(f"""(() => {{ const e = {controls[name]}; const at = document.elementFromPoint({x}, {y});
          if (e && at && (e === at || e.contains(at))) return ''; return at ? (at.closest('[data-testid]')?.dataset.testid || at.tagName) : 'nothing'; }})()""")
    return out


def clickables(*containers: str):
    """`controls` for `still`: every button, select, input, link, switch and tab with a test id (its own or its nearest
    one's) inside the CSS `containers`, read at first paint; each named by a selector that finds exactly it."""
    def read(c) -> dict:
        sels = c.js(f"""(() => {{ const out = []; for (const box of {json.dumps(list(containers))}.flatMap((s) => [...document.querySelectorAll(s)]))
          for (const el of box.querySelectorAll('button, select, input, a[href], [role=switch], [role=tab]')) {{
            const t = el.closest('[data-testid]'); if (!t || !box.contains(t)) continue;
            let s = `[data-testid="${{t.dataset.testid}}"]`;
            for (const [k, a] of [['panel', 'panel'], ['view', 'view'], ['kind', 'kind'], ['id', 'id'], ['tabId', 'tab-id']]) if (t.dataset[k]) s += `[data-${{a}}="${{t.dataset[k]}}"]`;
            if (document.querySelectorAll(s).length === 1 && !out.includes(s)) out.push(s); }}
          return out; }})()""")
        return {s: f"document.querySelector({json.dumps(s)})" for s in sels or []}
    return read


def _release_until(c, expr: str, log: list, timeout: float = 40) -> None:
    """Let the held answers go one at a time, oldest first, until `expr` holds."""
    end = time.time() + timeout
    while not c.js(f"!!({expr})"):
        if time.time() > end:
            raise TimeoutError(f"hold_still: waited {timeout}s for: {expr}")
        path = c.js("window.__hold.next()")
        if path:
            log.append(path)
            c.wait("window.__hold.inflight === 0 && 'idle'", 20)
            c.js(DRAWN)
        else:
            time.sleep(0.1)


def still(c, url: str, controls, ready: str, *, before=None, then: "str | None" = None, limit: int = 120, quiet: float = 0.6) -> dict:
    """Open `url` with every /api/ answer held, measure `controls` ({name: JS expression}, or `clickables(...)`) at first
    paint, let the answers go one at a time and say what moved: {"first": {name: rect}, "released": [paths], "moved": [lines]}.
    `before(c)`: what a person does first while nothing has landed (open a drawer); the controls are measured after it,
    once `then` holds (the answers it needs let go first, the fewest that draw it)."""
    c.call("Page.enable")
    ident = c.call("Page.addScriptToEvaluateOnNewDocument", source=GATE)["identifier"]
    out: dict = {"first": {}, "released": [], "moved": []}
    try:
        c.go("about:blank")
        c.go(url)
        c.wait("!!window.__hold", 40)
        out["before_ready"] = []  # a page that draws nothing until an answer lands: the fewest answers that draw it
        _release_until(c, ready, out["before_ready"])
        c.js(DRAWN)
        if before is not None:
            before(c)
            c.js(DRAWN)
            if then:
                _release_until(c, then, out["before_ready"])
        if callable(controls):
            controls = controls(c)
        out["first"] = {k: v for k, v in _measure(c, controls).items() if v} if controls else {}
        # a control whose centre is out of sight or under something at first paint is not judged by what covers it
        # later (a click scrolls to it first); it is listed, and its moves still count
        hid = {k for k, v in _under(c, controls, out["first"]).items() if v}
        out["hidden_at_first"] = sorted(hid)
        bad: set = set()
        idle_since = None
        while len(out["released"]) < limit:
            path = c.js("window.__hold.next()")
            if path is None:  # nothing waits: done once nothing has asked for a while
                idle_since = idle_since or time.time()
                if time.time() - idle_since > quiet:
                    break
                time.sleep(0.1)
                continue
            idle_since = None
            out["released"].append(path)
            c.wait("window.__hold.inflight === 0 && 'idle'", 20)
            c.js(DRAWN)
            now = _measure(c, controls)
            under = _under(c, controls, out["first"])
            for name, rect in out["first"].items():
                if name in bad:
                    continue
                if not now.get(name):
                    out["moved"].append(f"{name} went away after {path}")
                elif any(abs(a - b) > 1 for a, b in zip(rect, now[name])):
                    out["moved"].append(f"{name} moved after {path}: {rect} -> {now[name]}")
                elif under[name] and name not in hid:
                    out["moved"].append(f"{name} covered by {under[name]} after {path}")
                else:
                    continue
                bad.add(name)
    finally:
        c.call("Page.removeScriptToEvaluateOnNewDocument", identifier=ident)
    return out
