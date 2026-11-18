"""tests.helpers.studio_map_live_more -- the later steps of the lit run's driver (tests/helpers/studio_map_live.py):
amber (3.6.0.2: another map open on 3 · Map, 4 · Live unchanged and never amber), nomap (T4 in Live), zoom and room
(in Live), panel (Session's Live drawer, its link to Agents -> Live). 3.6.0.3 B: History's replay on the Map left Studio.
Each waits for the value it reads."""
from __future__ import annotations

import time

from tests.helpers.studio_agents import key
from tests.helpers.studio_map_live_steps import LP, LWORLD, VIEW, hop, lq, lqa, t

FD = "document.querySelector('[data-testid=map-feed]')"


def press(c, expr: str) -> None:
    """A person scrolls to what they press (the main panel scrolls), then clicks it."""
    c.wait(f"!!({expr})", 15)
    c.js(f"({expr}).scrollIntoView({{block: 'center', inline: 'nearest'}}); 1")
    c.click_on(expr)


def amber(c, rig, lv, sent) -> dict:
    sw = t("map-switcher")
    c.js(f"(() => {{ const s = {sw}; const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;"
         f" set.call(s, 'starter'); s.dispatchEvent(new Event('change', {{bubbles: true}})); }})(); 1")
    c.wait(f"{sw}.value === 'starter'", 15)
    c.js("document.activeElement?.blur(); 1")
    key(c, "4")
    live = lq("[data-testid=agents-live]")
    out = {"amber": c.wait(f"{VIEW} === 'live' && {live}?.dataset.map === 'shop' && {lqa(LWORLD + ' [data-map-box]')}.length >= 6"
                           f" && [{live}.dataset.map, document.querySelectorAll('{LP}.mp-amber, {LP}[data-lit=other], {LP}[data-testid=map-show-running]').length]", 20)}
    out["unlit"] = c.js(f"{lqa(LWORLD + ' [data-map-box][data-lit]')}.length")
    return out


def nomap(c, rig, lv, sent) -> dict:
    lv.refresh(map=None)
    tr = lq("[data-testid=live-truth]")
    out = {"nomap_head": c.wait(f"{tr}?.dataset.state === 'T4' && {tr}.textContent", 20)}
    # P8: a session with no map is drawn as Session's Live drawer draws it: main's box, and what the run started (this
    # rig's session runs the workflow review: its block), under the T4 line
    try:
        c.wait(f"{lqa('[data-map-box]')}.length > 0", 20)
    except Exception:
        pass  # recorded as drawn (none), the test says so
    out["boxes"] = [c.js(f"{lqa('[data-map-box]')}.map((b) => b.dataset.mapBox)"), c.js(f"!!{lq('[data-testid=map-lit-show-nomap]')}")]
    lv.refresh(map="shop")
    out["again"] = c.wait(f"{lq('[data-testid=agents-live]')}?.dataset.map === 'shop' && {lqa('[data-testid=live-label]')}.length", 20)
    sw = t("map-switcher")  # the Map back on shop (R55: the Map is the plan)
    c.js(f"(() => {{ const s = {sw}; const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;"
         f" set.call(s, 'shop'); s.dispatchEvent(new Event('change', {{bubbles: true}})); }})(); 1")
    c.js("document.activeElement?.blur(); 1")
    key(c, "3")
    c.wait(f"{VIEW} === 'map' && {sw}.value === 'shop' && !!{t('map-topline')}", 20)  # R55: the Map is the plan, never lit by a run
    return out


def zoom(c, rig, lv, sent) -> dict:
    c.js("document.activeElement?.blur(); 1")
    key(c, "4")
    world = lq(LWORLD)
    plus = lq('[data-testid="live-frame"] [data-testid="canvas-zoom-in"]')
    c.wait(f"{VIEW} === 'live' && !!{world}", 15)
    before = c.js(f"{world}.dataset.zoom")
    press(c, plus)
    hand = c.wait(f"{world}.dataset.zoom !== '{before}' && {world}.dataset.zoom", 10)
    lv.spawn("n3wh3lp1", "general-purpose", "general-purpose", "or:mock/glm-5-coder", "Count the tests")
    c.wait(f"!!{lq('[data-row=n3wh3lp1]')}", 15)  # the row stays; the label's task is a few seconds: one wait each, in order
    hop(c, lv, "main -> code", "a second hand-off while zoomed")
    c.wait(f"{lq('[data-testid=live-label][data-from=main][data-to=code]')}?.dataset.pulse === '1'", 10)
    c.mouse("mouseMoved", 4, 4)  # the pointer leaves: the held change is drawn, the zoom still his
    c.wait(f"document.querySelector('{LP}[data-testid=live-frame]')?.dataset.held !== '1'", 10)
    return {"zoom": [hand, c.js(f"{world}.dataset.zoom")]}


ROOM = """(() => {
  const root = document.querySelector('[data-part="live"]');
  const scope = [...root.querySelectorAll('.mp-box[data-lit], [data-testid=live-truth], [data-testid=live-status], [data-testid=live-label]')];
  const small = scope.flatMap((el) => [el, ...el.querySelectorAll('*')]).filter((e) => e.offsetParent && e.childNodes.length
      && [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim()) && parseFloat(getComputedStyle(e).fontSize) < 12).length;
  const ctl = [...root.querySelectorAll('[data-testid=live-frame] button, [data-testid=live-pick], [data-testid=live-truth] button')]
      .filter((b) => b.offsetParent && b.getBoundingClientRect().height < 27.5).length;
  const side = [...root.querySelectorAll('.panel-body')].filter((p) => p.scrollWidth > p.clientWidth + 1).length;
  const cut = [...root.querySelectorAll('[data-testid=live-world] [data-map-box]')].filter((b) => b.querySelector('.mp-inner').scrollHeight > b.clientHeight + 1).length;
  return {small, ctl, side, cut};
})()"""


def room(c, rig, lv, sent) -> dict:
    out: dict = {}
    for w, h in ((1280, 800), (1500, 900), (1920, 1000)):
        c.call("Emulation.setDeviceMetricsOverride", width=w, height=h, deviceScaleFactor=1, mobile=False)
        c.wait(f"!!{lq(LWORLD)}", 10)
        time.sleep(0.4)  # the layout settles after the resize; the values below are measured, not timed
        out[f"room_{w}"] = c.js(ROOM)
    c.call("Emulation.setDeviceMetricsOverride", width=1500, height=900, deviceScaleFactor=1, mobile=False)
    return out


PANEL = """(() => { const m = MINI; if (!m || m.querySelectorAll('[data-testid=session-lit-box]').length < 6) return false;
  const R = (e) => e.getBoundingClientRect();
  const bx = [...m.querySelectorAll('[data-testid=session-lit-box]')], main = R(m.querySelector('[data-box=main]'));
  const rest = bx.filter((b) => b.dataset.box !== 'main'), tops = rest.map((b) => Math.round(R(b).top));
  const per = Math.max(...tops.map((t) => tops.filter((u) => Math.abs(u - t) <= 2).length));
  const named = [...m.querySelectorAll('[data-testid=session-map-row-text]')].map((r) => r.textContent);
  return [m.dataset.map, bx.length, rest.every((b) => R(b).top >= main.bottom - 0.5), per,
          m.querySelectorAll('.mp-dot, [data-testid=map-label]').length, named.some((x) => x.startsWith('implementer · '))]; })()"""


def panel(c, rig, lv, sent) -> dict:
    c.go("about:blank")
    c.go(rig.url("session"))
    mini = "document.querySelector('[data-testid=session-map] [data-testid=session-lit-map]')"
    # 3.6.0.2 R7 R15: drawn down (main alone on top, at most two a row), children as named rows inside their box
    out = {"panel": c.wait(PANEL.replace("MINI", mini), 40)}
    press(c, f"{mini}.querySelector('[data-testid=session-lit-open]')")
    live = "document.querySelector('[data-part=live] [data-testid=agents-live]')"
    out["to_tab"] = c.wait(f"{VIEW} === 'live' && {live}?.dataset.sid === '{lv.sid}' && {live}.dataset.map", 20)
    return out
