"""tests.helpers.studio_agents_live_draw -- the drawing steps of Agents -> 4 · Live's driver (tests/helpers/studio_agents_live.py,
Halo 3.6.0.2 R3 R34 R12), over the same rig: the session's row on `shop` (the map seeded from tests/helpers/studio_map_live.py),
`code` (the implementer) and `check` (the reviewer, the workflow review's step) working. Each waits for the value it reads.

    follows   3 · Map shows starter; 4 · Live draws the session's own map shop left to right, lit (code working), with no
              connect dot, no label that is a button, no When card from a label's click, nothing amber; 3 · Map's picker
              changed afterwards leaves Live on shop
    holds     R12: the pointer on check's box; a made-up child under main, a second child under code and a hand-off
              main -> code arrive: every box holds still (0.5 px) and the scroll stays; the pointer leaves: code's box grows
    t9        R3: an `away` harness (another machine, `gpu-box`) with an open session `nightly` on `tiers` joins GET live; the
              picker lists "{title} · {map}" for both machines, none disabled; picking nightly says T9 and fetches nothing
"""
from __future__ import annotations

import time

P = "[data-part=live]"
F = f"{P} [data-testid=live-frame]"
LIVE = f"document.querySelector('{P} [data-testid=agents-live]')"
VIEW = "document.querySelector('[data-testid=agents]')?.dataset.view"
BOXES = f"[...document.querySelectorAll('{F} [data-map-box]')]"
RECTS = f"Object.fromEntries({BOXES}.map((b) => {{ const r = b.getBoundingClientRect(); return [b.dataset.mapBox, [r.left, r.top, r.width, r.height]]; }}))"
SCROLL = f"document.querySelector('{F} [data-testid=live-scroll]')"
AWAY = {"id": "h-away", "name": "gpu-box", "local": False,
        "sessions": [{"session_id": "away-1", "title": "nightly", "map": "tiers", "turns": 3, "busy": False, "agents": []}]}
T9 = "nightly runs on tiers on gpu-box. Its drawing is in that machine's Studio."


def box(bid: str) -> str:
    return f"document.querySelector('{F} [data-map-box=\"{bid}\"]')"


def choose(c, sel: str, value: str) -> None:
    """A select set the way a person's pick reaches React: the value setter, then `change`."""
    c.js(f"(() => {{ const s = document.querySelector('{sel}'); const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;"
         f" set.call(s, '{value}'); s.dispatchEvent(new Event('change', {{bubbles: true}})); }})(); 1")


def follows(c, rig, lv, rows) -> dict:
    out: dict = {}
    rows.reset()
    lv.refresh(map="shop", map_next="shop")
    c.go("about:blank")
    c.wait("location.href === 'about:blank'", 10)
    c.go(rig.url("agents", "&view=map"))
    c.wait(f"{VIEW} === 'map'", 40)
    sw = "[data-part=map] [data-testid=map-switcher]"
    c.wait(f"[...(document.querySelector('{sw}')?.options || [])].some((o) => o.value === 'starter')", 30)
    choose(c, sw, "starter")
    out["map_shows"] = c.wait(f"document.querySelector('{sw}').value === 'starter' && 'starter'", 15)
    c.click_on("document.querySelector('[data-part=map] [data-testid=agents-view-live]')")
    try:
        out["drawn"] = c.wait(f"{LIVE}?.dataset.map === 'shop' && {LIVE}.dataset.sid === '{lv.sid}' && {BOXES}.length >= 6"
                              f" && [{LIVE}.dataset.map, {BOXES}.length]", 30)
    except TimeoutError:
        raise TimeoutError(f"Live drew: {c.js(f'[{LIVE}?.dataset.map, {LIVE}?.dataset.sid, {BOXES}.length, {LIVE}?.innerText.slice(0, 300)]')}")
    out["lefts"] = c.js(f"(() => {{ const r = {RECTS}; return [r.main?.[0], [...new Set(Object.values(r).map((x) => Math.round(x[0])))].sort((a, b) => a - b)]; }})()")
    out["dots"] = c.js(f"document.querySelectorAll('{P} .mp-dot').length")
    out["label_buttons"] = c.js(f"[...document.querySelectorAll('{P} button[data-testid=map-label], {P} button[data-testid=live-label]')].filter((b) => !b.disabled).length")
    label = f"document.querySelector('{F} [data-testid=live-label][data-from=main][data-to=code]')"
    c.wait(f"!!{label}", 10)
    out["label"] = c.js(f"{label}.tagName + ':' + {label}.textContent")
    c.click_on(label)
    out["card"] = c.wait(f"document.querySelector('{F} [data-testid=map-step-in]')?.dataset.target || ''", 10)
    out["when_cards"] = c.js("document.querySelectorAll('[data-testid=when-card]').length")
    c.click_on(f"document.querySelector('{F} [data-testid=map-step-in-close]')")
    c.wait(f"!document.querySelector('{F} [data-testid=map-step-in]')", 10)
    out["amber"] = c.js(f"document.querySelectorAll('{P} .mp-amber, {P} [data-lit=other], {P} [data-testid=map-show-running]').length")
    out["truth_color"] = c.js(f"""(() => {{ const t = document.querySelector('{P} [data-testid=live-truth]'); const p = document.createElement('span');
      p.style.color = 'var(--warn)'; t.appendChild(p); const warn = getComputedStyle(p).color; p.remove();
      return [getComputedStyle(t).color, warn]; }})()""")
    out["code"] = c.wait(f"{box('code')}?.dataset.state === 'working' && [{box('code')}.dataset.lit, {box('code')}.dataset.state]", 20)
    choose(c, sw, "shop")
    choose(c, sw, "starter")
    time.sleep(0.5)  # a pick of the Map that would move Live would land within this; the value is read, not timed
    out["after_map_pick"] = c.js(f"{LIVE}?.dataset.map")
    return out


def holds(c, rig, lv, rows) -> dict:
    out: dict = {}
    c.wait(f"!!{box('check')} && !!{SCROLL}", 20)
    c.js(f"{box('check')}.scrollIntoView({{block: 'nearest', inline: 'nearest'}}); 1")
    time.sleep(0.3)
    x, y, w, h = c.js(f"(() => {{ const r = {box('check')}.getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; }})()")
    c.mouse("mouseMoved", x + w / 2, y + h / 2)
    c.wait(f"document.querySelector('{F}')?.dataset.held === '1'", 10)
    before, top = c.js(RECTS), c.js(f"{SCROLL}.scrollTop")
    lv.spawn("m4d3up01", "general-purpose", "general-purpose", "or:mock/glm-5-coder", "Count the tests in the basket suite")
    lv.rows["m4d3up01"]["crew"] = {"map": "shop", "box": "main", "made_up": True}
    lv.spawn("c0d3k1d1", "checker", "checker", "or:mock/glm-5-coder", "Check the discount rule", parent="implementer")
    lv.rows["c0d3k1d1"]["crew"] = {"map": "shop", "box": "code", "line": "main -> code", "agent": "checker", "saved": True}
    lv.refresh()
    lv.frame("main", "map_hop", {"map": "shop", "line": "main -> code", "from": "main", "to": "code", "state": "start", "t": time.time(),
                                 "task": "apply the discount before tax", "why": "always"})
    out["rows_in"] = c.wait(f"!!document.querySelector('{F} [data-row=c0d3k1d1]') && !!document.querySelector('{F} [data-row=m4d3up01]')", 20)
    out["lit"] = c.wait(f"document.querySelector('{F} .mp-line[data-from=main][data-to=code]')?.dataset.lit || ''", 10)
    samples = []
    for _ in range(6):
        samples.append(c.js(RECTS))
        time.sleep(0.2)
    moved = [k for s in samples for k, r in s.items() if k in before and max(abs(a - b) for a, b in zip(r, before[k])) > 0.5]
    out["moved"] = sorted(set(moved))
    out["scroll"] = [top, c.js(f"{SCROLL}.scrollTop")]
    c.mouse("mouseMoved", 4, 4)
    out["released"] = c.wait(f"document.querySelector('{F}')?.dataset.held !== '1' && (() => {{ const b = {box('code')}; const r = b.getBoundingClientRect();"
                             f" return r.height > {before['code'][3]} + 1 && b.querySelector('.mp-inner').offsetHeight + 20 <= b.clientHeight + 2 && r.height; }})()", 15)
    return out


def t9(c, rig, lv, rows) -> dict:
    from halo_harness.studio import live_api
    out: dict = {}
    orig = live_api.view_for

    def view_for(server, state_dir):
        v = orig(server, state_dir)
        return {**v, "harnesses": list(v.get("harnesses") or []) + [AWAY]}
    live_api.view_for = view_for
    try:
        rows.reset()
        c.go("about:blank")
        c.wait("location.href === 'about:blank'", 10)
        c.go(rig.url("agents", "&view=live"))
        pick = f"document.querySelector('{P} [data-testid=live-pick]')"
        opts = f"[...({pick}?.options || [])]"
        try:
            out["options"] = c.wait(f"{opts}.some((o) => o.value === 'away-1') && {opts}.map((o) => [o.value, o.textContent, o.disabled])", 40)
        except TimeoutError:
            raise TimeoutError(f"the picker: {c.js(f'{opts}.map((o) => o.textContent)')}; Live says {c.js(f'{LIVE}?.innerText.slice(0, 300)')!r}")
        out["pick_label"] = c.js(f"{pick}.getAttribute('aria-label')")
        c.js("""(() => { window.__mapGets = []; const f = window.fetch;
          window.fetch = function (u, ...a) { const s = String(u && u.url || u); if (s.includes('crew/map/')) window.__mapGets.push(s); return f.call(this, u, ...a); };
          return 1; })()""")
        choose(c, f"{P} [data-testid=live-pick]", "away-1")
        truth = f"document.querySelector('{P} [data-testid=live-truth]')"
        out["t9"] = c.wait(f"{truth}?.textContent === {T9!r} && [{truth}.dataset.state, {truth}.textContent]", 30)
        out["boxes"] = c.js(f"{BOXES}.length")
        try:
            c.wait("window.__mapGets.length > 0", 2)
        except TimeoutError:
            pass
        out["gets"] = c.js("window.__mapGets")
    finally:
        live_api.view_for = orig
        rows.refresh()
    return out
