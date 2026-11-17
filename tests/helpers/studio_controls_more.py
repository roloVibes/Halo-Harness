"""tests.helpers.studio_controls_more -- the `live`, `agents` and `workflows` groups of tests/helpers/studio_controls.py
(Halo 3.6.0.2 R42).

    live       Agents -> 4 · Live with two open sessions: the session picker, a box (its step-in card), the card's Pause
               and x, the view bar's Feed, the Feed's filter, its Steer (typed, sent), its Stop (up to its question) and
               the question's No, the box head's Pause; `handles`: no editing handle in Live (R34: no dot, no When label
               that is a button)
    agents     1 · Agents and 2 · Workflows: the design names none of their controls, so every visible `button, select,
    workflows  [role=switch], [role=tab], a[href]` of the part at rest is enumerated and pressed, the page loaded at rest
               again whenever a press left it elsewhere. Not pressed, each with its reason (`<group>_skipped`): a control
               disabled at rest, a writer that saves or starts a run without a confirm (Save, Try it), a link to a new tab
"""
from __future__ import annotations

import re
import time

from tests.helpers.studio_controls import VISIBLE, choose, presses
from tests.helpers.studio_controls_steps import VIEW, vis

LP = "[data-part=live]"
FD = vis("[data-testid=map-feed]")
WRITERS = re.compile(r"^(Save|Try it|Try)\b")


def live(c, rig, lv, rows) -> dict:
    from tests.helpers.studio_live_feed import FEED_BTN, click_live_box
    from tests.helpers.studio_map_quiet import second_session
    out: dict = {}
    full, rig.full = rig.full, False  # a person's layout: the Feed opens by his hand
    t = lambda tid: vis(f"{LP} [data-testid={tid}]")  # noqa: E731
    live_root = vis(f"{LP} [data-testid=agents-live]")
    rows.reset()
    lv.refresh(map="shop", map_next="shop")
    recs: list = []
    try:
        with second_session(lv):
            def start():
                c.call("Emulation.setDeviceMetricsOverride", width=1500, height=900, deviceScaleFactor=1, mobile=False)
                c.go("about:blank")
                c.wait("location.href === 'about:blank'", 10)
                c.go(rig.url("agents", "&view=live"))
                c.wait(f"{VIEW} === 'live' && {live_root}?.dataset.sid === {lv.sid!r} && !!{t('live-pick')}", 40)

            def mine():
                choose(c, t("live-pick"), lv.sid)
                c.wait(f"{live_root}?.dataset.sid === {lv.sid!r} && !!{vis(LP + ' [data-testid=live-world] [data-map-box=code]')}", 20)

            def to_code():
                choose(c, f"{FD}?.querySelector('[data-testid=map-feed-filter]')", "code")
                c.wait(f"!!{FD}?.querySelector('[data-testid=map-feed-steer-text]')", 15)
                c.js(f"{FD}.querySelector('[data-testid=map-feed-steer-text]').focus(); 1")
                c.type_text("check the tax rule first")

            feed = lambda tid: f"{FD}?.querySelector('[data-testid={tid}]')"  # noqa: E731
            recs = presses(c, [
                ("Which session", t("live-pick"), start, ("choose", "two-0001")),
                ("a box", vis(f"{LP} [data-testid=live-world] [data-map-box=code]"), mine, lambda: click_live_box(c, "code")),
                ("the card: Pause", t("map-step-in-pause")),
                ("the card: x", t("map-step-in-close")),
                ("Feed", FEED_BTN),
                ("the Feed's filter", feed("map-feed-filter"), None, ("choose", "")),
                ("the Feed's Steer", feed("map-feed-steer"), to_code),
                ("the Feed's Stop", feed("map-feed-stop")),
                ("Stop's No", f"{feed('map-feed-stop-ask')}?.querySelector('button:last-of-type')"),
                ("the box head's Pause", feed("map-feed-pause")),
            ])
            out["handles"] = c.js(f"[document.querySelectorAll('{LP} .mp-dot').length,"
                                  f" [...document.querySelectorAll('{LP} [data-testid=map-label]')].filter((b) => b.tagName === 'BUTTON' && !b.disabled).length]")
    finally:
        rig.full = full
    out["live"] = recs
    return out


ENUM = f"""((part) => {{ const seen = {{}};
  return [...document.querySelectorAll(`[data-part=${{part}}] :is(button, select, [role=switch], [role=tab], a[href])`)]
    .filter((e) => {VISIBLE}(e)).map((e) => {{
      const tid = e.dataset.testid || '', text = (e.tagName === 'SELECT' ? (e.getAttribute('aria-label') || e.title || 'select')
        : (e.textContent || e.getAttribute('aria-label') || e.title || '')).trim().replace(/\\s+/g, ' ').slice(0, 40);
      const k = tid + '|' + text; seen[k] = (seen[k] || 0) + 1;
      return {{ key: k + '|' + seen[k], tid, text, tag: e.tagName, disabled: !!e.disabled || e.getAttribute('aria-disabled') === 'true',
               blank: e.tagName === 'A' && e.target === '_blank', shown: tid.startsWith('agents-view-') && e.getAttribute('aria-pressed') === 'true',
               other: e.tagName === 'SELECT' ? ([...e.options].find((o) => o.value !== e.value && !o.disabled)?.value ?? null) : null }}; }}); }})"""


def _find(part: str, key: str) -> str:
    """The control of `part` whose enumeration key is `key` (found again after a reload)."""
    return (f"(() => {{ const want = {key!r}, seen = {{}}; for (const e of document.querySelectorAll(`[data-part={part}] :is(button, select, [role=switch], [role=tab], a[href])`)) {{"
            f" if (!{VISIBLE}(e)) continue; const tid = e.dataset.testid || '', text = (e.tagName === 'SELECT' ? (e.getAttribute('aria-label') || e.title || 'select')"
            f" : (e.textContent || e.getAttribute('aria-label') || e.title || '')).trim().replace(/\\s+/g, ' ').slice(0, 40);"
            f" const k = tid + '|' + text; seen[k] = (seen[k] || 0) + 1; if (k + '|' + seen[k] === want) return e; }} return null; }})()")


def _enum_tab(c, rig, view: str) -> dict:
    full, rig.full = rig.full, False
    c.call("Emulation.setDeviceMetricsOverride", width=1500, height=900, deviceScaleFactor=1, mobile=False)

    def keys() -> list:
        return [x["key"] for x in c.js(f"{ENUM}({view!r})") or []]

    def load():
        """The tab at rest as a first-time user sees it: what an earlier press saved (a drawer opened, a panel alone) is
        forgotten first, then the page is loaded again."""
        for clear in (True, False):
            c.go("about:blank")
            c.wait("location.href === 'about:blank'", 10)
            c.go(rig.url("agents", f"&view={view}"))
            c.wait(f"{VIEW} === {view!r} && {vis('[data-part=' + view + ']')} !== null", 40)
            if clear:
                c.js("(() => { try { localStorage.clear(); sessionStorage.clear(); } catch (e) { /* none to clear */ } return 1; })()")
        last = None
        for _ in range(20):  # at rest: two reads 0.5 s apart list the same controls
            now = keys()
            if now and now == last:
                return
            last = now
            time.sleep(0.5)

    recs, skipped, at_rest = [], [], []
    try:
        load()
        rest = c.js(f"{ENUM}({view!r})") or []
        at_rest = [x["key"] for x in rest]
        for x in rest:
            why = ("disabled at rest (nothing to press)" if x["disabled"] else "opens a new tab" if x["blank"]
                   else "the tab shown now (pressing it keeps the page as it is)" if x["shown"]
                   else "writes or starts a run without a confirm" if WRITERS.match(x["text"]) and not x["tid"].startswith("agents-view") else
                   "a select with one choice" if x["tag"] == "SELECT" and x["other"] is None else "")
            if why:
                skipped.append([x["key"], why])
                continue
            if c.js(VIEW) != view or keys() != at_rest:
                load()
            how = ("choose", x["other"]) if x["tag"] == "SELECT" else None
            recs += presses(c, [(x["tid"] or x["text"] or x["key"], _find(view, x["key"]), None, how)])
    finally:
        rig.full = full
    return {"recs": recs, "skipped": skipped, "rest": at_rest}


def agents(c, rig, lv, rows) -> dict:
    got = _enum_tab(c, rig, "crew")
    return {"agents": got["recs"], "agents_skipped": got["skipped"], "agents_rest": got["rest"]}


def workflows(c, rig, lv, rows) -> dict:
    got = _enum_tab(c, rig, "workflows")
    return {"workflows": got["recs"], "workflows_skipped": got["skipped"], "workflows_rest": got["rest"]}
