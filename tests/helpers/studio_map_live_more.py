"""tests.helpers.studio_map_live_more -- the later steps of the lit Map's driver (tests/helpers/studio_map_live.py):
amber, nomap, history, zoom, room, panel. Each waits for the value it reads."""
from __future__ import annotations

import time

from tests.helpers.studio_map_live_steps import VIEW, box, hop, q, qa, shot, t

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
    line = t("map-topline")
    out = {"amber": c.wait(f"{line}?.dataset.lit === 'other' && [{line}.textContent.includes('another map, shop'), getComputedStyle({line}).color]", 15)}
    out["unlit"] = c.js(f"{qa('[data-testid=map-world] [data-map-box][data-lit]')}.length")
    press(c, t("map-show-running"))
    try:
        out["shown_running"] = c.wait(f"{sw}.value === 'shop' && {t('map-topline')}?.dataset.lit === 'live' && {sw}.value", 15)
    except TimeoutError:
        raise TimeoutError(f"after Show the running map: {c.js(f'[{sw}.value, {line}?.dataset.lit]')}")
    return out


def nomap(c, rig, lv, sent) -> dict:
    lv.refresh(map=None)
    show = t("map-lit-show-nomap")
    out = {"offer": c.wait(f"!!{show} && {t('map-topline')}.textContent.includes('not on a map')", 20)}
    press(c, show)
    head = t("map-lit-head")
    out["nomap_head"] = c.wait(f"{head}?.textContent.startsWith('This session did not start on a map') && {head}.textContent", 15)
    out["boxes"] = c.wait(f"(() => {{ const b = {qa('[data-testid=map-world] [data-map-box]')}; return b.length >= 4 && "
                          f"[b.filter((x) => x.dataset.helper).length, b.filter((x) => !x.dataset.helper).map((x) => x.dataset.mapBox)]; }})()", 15)
    out["labels"] = c.js(f"{qa('[data-testid=map-label]')}.length")
    press(c, t("map-lit-back"))
    lv.refresh(map="shop")
    out["again"] = c.wait(f"{t('map-topline')}?.dataset.lit === 'live' && {qa('[data-testid=map-label]')}.length", 20)
    return out


def history(c, rig, lv, sent) -> dict:
    from tests.helpers.studio_session_parts import PAST_SID
    pick = t("map-history-pick")
    out = {"rows": c.wait(f"{pick}?.options.length >= 1 && [...{pick}.options].map((o) => o.value)", 20)}
    c.js(f"(() => {{ const s = {pick}; const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;"
         f" set.call(s, '{PAST_SID}'); s.dispatchEvent(new Event('change', {{bubbles: true}})); }})(); 1")
    press(c, t("map-history-replay"))
    line = t("map-topline")
    out["replay"] = c.wait(f"{line}?.dataset.lit === 'replay' && {line}.textContent.includes('on this map') && 'replay'", 20)
    out["quiet"] = c.wait(f"{q('[data-testid=map-world]')}.dataset.lit === 'replay' && {box('review')}.dataset.state", 15)
    out["fired_end"] = c.js(f"{q('[data-testid=map-line][data-from=main][data-to=review]')}?.dataset.fired")
    out["removed"] = c.wait(f"{qa('[data-testid=map-removed]')}.map((x) => x.dataset.box)", 10)
    shot(c, "studio-map-replay.png")
    rng = "document.querySelector('[data-testid=replay-scrub]')"
    c.wait(f"!!{rng}", 10)
    c.js(f"(() => {{ const r = {rng}; const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;"
         f" set.call(r, '0'); r.dispatchEvent(new Event('input', {{bubbles: true}})); }})(); 1")
    out["at_start"] = c.wait(f"!{q('[data-testid=map-line][data-from=main][data-to=review]')}?.dataset.fired && {box('review')}.dataset.state", 10)
    press(c, t("map-history-card"))
    out["card"] = c.wait("document.querySelector('[data-testid=report-card]')?.dataset.ref", 15)
    press(c, t("map-history-now"))
    out["now"] = c.wait(f"{t('map-topline')}?.dataset.lit === 'live' && 'live'", 15)
    return out


def zoom(c, rig, lv, sent) -> dict:
    world = q('[data-testid="map-world"]')
    plus = q('[data-testid="map-canvas"] [data-testid="canvas-zoom-in"]')
    before = c.js(f"{world}.dataset.zoom")
    press(c, plus)
    hand = c.wait(f"{world}.dataset.zoom !== '{before}' && {world}.dataset.zoom", 10)
    lv.spawn("n3wh3lp1", "general-purpose", "general-purpose", "or:mock/glm-5-coder", "Count the tests")
    hop(c, lv, "main -> code", "a second hand-off while zoomed")
    c.wait(f"!!{q('[data-helper=n3wh3lp1]')} && {q('[data-testid=map-label][data-from=main][data-to=code]')}?.dataset.pulse === '1'", 15)
    return {"zoom": [hand, c.js(f"{world}.dataset.zoom")]}


ROOM = """(() => {
  const root = document.querySelector('[data-part="map"]');
  const scope = [...root.querySelectorAll('.mp-box[data-lit], .mp-box[data-helper], [data-testid=map-topline], [data-testid=map-feed]')];
  const small = scope.flatMap((el) => [el, ...el.querySelectorAll('*')]).filter((e) => e.offsetParent && e.childNodes.length
      && [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim()) && parseFloat(getComputedStyle(e).fontSize) < 12).length;
  const ctl = [...root.querySelectorAll('[data-testid=map-feed] button, [data-testid=map-feed] select, [data-testid=map-topline] button, [data-testid=map-history] button')]
      .filter((b) => b.offsetParent && b.getBoundingClientRect().height < 27.5).length;
  const side = [...root.querySelectorAll('.panel-body, .mpf-rows')].filter((p) => p.scrollWidth > p.clientWidth + 1).length;
  const cut = [...root.querySelectorAll('[data-testid=map-world] [data-map-box]')].filter((b) => b.querySelector('.mp-inner').scrollHeight > b.clientHeight + 1).length;
  return {small, ctl, side, cut, feed: !!document.querySelector('[data-testid=map-feed]')};
})()"""


def room(c, rig, lv, sent) -> dict:
    out: dict = {}
    for w, h in ((1280, 800), (1500, 900), (1920, 1000)):
        c.call("Emulation.setDeviceMetricsOverride", width=w, height=h, deviceScaleFactor=1, mobile=False)
        c.wait(f"!!{FD}", 10)
        time.sleep(0.4)  # the layout settles after the resize; the values below are measured, not timed
        out[f"room_{w}"] = c.js(ROOM)
    c.call("Emulation.setDeviceMetricsOverride", width=1500, height=900, deviceScaleFactor=1, mobile=False)
    return out


def panel(c, rig, lv, sent) -> dict:
    c.go("about:blank")
    c.go(rig.url("session"))
    mini = "document.querySelector('[data-testid=\"session-map\"] [data-testid=\"session-lit-map\"]')"
    out = {"panel": c.wait(f"!!{mini} && {mini}.querySelectorAll('[data-testid=session-lit-box]').length >= 6 && [{mini}.dataset.map,"
                           f" {mini}.querySelectorAll('[data-testid=session-lit-box][data-helper]').length > 0,"
                           f" {mini}.querySelectorAll('.mp-dot, [data-testid=map-label]').length]", 40)}
    press(c, f"{mini}.querySelector('[data-testid=session-lit-open]')")
    out["to_tab"] = c.wait(f"{VIEW} === 'map' && document.querySelector('[data-part=map] [data-testid=map-switcher]')?.value === 'shop' && 'shop'", 20)
    return out
