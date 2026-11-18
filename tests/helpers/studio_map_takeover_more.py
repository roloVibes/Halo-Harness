"""tests.helpers.studio_map_takeover_more -- the R4b driver's later steps (tests/helpers/studio_map_takeover.py): keys,
hover, ask, two, goal, replay. Each waits for the value it reads; no fixed sleep is a pass condition. 3.6.0.2 R57: the
Feed is 4 · Live's drawer; the Map's own drawer holds Run a goal and History (tests/helpers/studio_live_feed.py)."""
from __future__ import annotations

import json

from tests.helpers.session_rig import wait_for
from tests.helpers.studio_map_live_more import press
from tests.helpers.studio_map_live_steps import box, click_box, q, t
from tests.helpers.studio_map_takeover_steps import FD, back_to_map, to_feed
from tests.helpers.studio_live_feed import MD, MD_SHOWN

CARD = "document.getElementById('halo-hover-card')"


def letter(c, ch: str) -> None:
    for kind in ("keyDown", "keyUp"):
        c.call("Input.dispatchKeyEvent", type=kind, key=ch, code=f"Key{ch.upper()}", windowsVirtualKeyCode=ord(ch.upper()),
               **({"text": ch} if kind == "keyDown" else {}))


def keys(c, rig, lv, sent) -> dict:
    """R55 (rewritten): J / K stepped between the Map's working boxes; the Map draws no run, so none is working there."""
    c.js(f"{q('[data-testid=map-scroll]')}.focus(); 1")
    return {"working": c.js("[...document.querySelectorAll('[data-part=map] .mp-world [data-map-box][data-state=working], "
                            "[data-part=map] .mp-world [data-map-box][data-state=waiting]')].map((b) => b.dataset.mapBox)")}


def hover(c, rig, lv, sent) -> dict:
    """R55 + R43 (rewritten): the summary card of a box at work is 4 · Live's (the Map's boxes carry no run)."""
    from tests.helpers.studio_live_feed import live_box
    c.js("document.activeElement?.blur(); 1")
    from tests.helpers.studio_agents import key as press_key
    press_key(c, "4")
    out = {"by_itself": c.js(f"!!{CARD} && getComputedStyle({CARD}).display !== 'none'")}
    b = live_box("research")
    c.wait(f"!!{b}", 20)
    c.js(f"{b}.scrollIntoView({{block: 'center', inline: 'center'}}); 1")
    x, y, w, h = c.rect(b)
    c.mouse("mouseMoved", x + w * 0.4, y + h * 0.3)
    c.mouse("mouseMoved", x + w * 0.45, y + h * 0.35)
    try:
        out["card"] = c.wait(f"{CARD}?.textContent.includes('research') && "
                             f"[{CARD}.querySelector('[data-testid=hover-card-title]')?.textContent || {CARD}.textContent.slice(0, 80), "
                             f"[...{CARD}.querySelectorAll('[data-testid=hover-card-row]')].map((r) => r.dataset.row)]", 10)
    except TimeoutError:
        raise TimeoutError(f"no card on Live's research box: {c.js(f'[{x}, {y}, {w}, {h}, !!{CARD}, {CARD}?.textContent.slice(0, 120), document.elementFromPoint({x + w * 0.45}, {y + h * 0.35})?.outerHTML.slice(0, 160)]')}")
    out["covers"] = c.js(f"(() => {{ const k = {CARD}.getBoundingClientRect(); return [...{b}.querySelectorAll('button')].filter((x) => {{"
                         " const r = x.getBoundingClientRect(); return r.width && !(r.right <= k.left || r.left >= k.right || r.bottom <= k.top || r.top >= k.bottom); }).length; })()")
    c.mouse("mouseMoved", 4, 4)
    out["gone"] = c.wait(f"(!{CARD} || getComputedStyle({CARD}).display === 'none' || !{CARD}.textContent) && 'gone'", 10)
    back_to_map(c)
    return out


def ask(c, rig, lv, sent) -> dict:
    """A real pending ask: the session row lists it (`pending`, so Studio makes its Attention row) and its frame names
    the reviewer; the drawer's key answers it through the Attention row and the session's socket receives it."""
    rig.controller.register_pending_permission("perm-r4b", "Bash", {"command": "git push origin feature/basket"})  # a real waiter
    lv.state("reviewer", state="waiting")
    lv.ask("reviewer", "permission_request", {"id": "perm-r4b", "name": "Bash", "input": {"command": "git push origin feature/basket"}})
    lv.refresh(pending={"permission": ["perm-r4b"]})
    to_feed(c, lv, "check")  # R57: the Feed is 4 · Live's
    key = f"{FD}?.querySelector('[data-testid=session-live-ask]:last-of-type [data-testid=session-live-key][data-key=a]')"
    out = {"row": c.wait(f"{FD}?.dataset.filter === 'check' && {key}?.title.includes('Attention row') && {key}.title", 30)}
    before = len(sent)
    press(c, key)
    got = wait_for(lambda: [d for d in sent[before:] if "perm-r4b" in json.dumps(d["fields"])], 20) or [{}]
    out["sent"] = [got[0].get("cmd"), got[0].get("fields", {}).get("request_id"), got[0].get("fields", {}).get("action"), got[0].get("status"),
                   str(got[0].get("result"))[:160]]
    lv.fields.pop("pending", None)
    lv.state("reviewer", state="running")
    lv.refresh()
    back_to_map(c)
    return out


def two(c, rig, lv, sent) -> dict:
    """3.6.0.2 R55 + R34 (rewritten): the session picker is 4 · Live's ("Which session"), no longer the Map's."""
    from tests.helpers.studio_map_takeover import TWO_SID
    from tests.helpers.studio_live_feed import choose
    lv.fields["two"] = True
    lv.refresh()
    c.js("document.activeElement?.blur(); 1")
    from tests.helpers.studio_agents import key as press_key
    press_key(c, "4")
    sel = "[data-part=live] [data-testid=live-pick]"
    pk = f"document.querySelector('{sel}')"
    head = "document.querySelector('[data-part=live] [data-testid=agents-live]')"
    out = {"options": c.wait(f"{pk}?.options.length >= 2 && [...{pk}.options].map((o) => o.value)", 20)}
    choose(c, sel, TWO_SID)
    out["second"] = c.wait(f"{head}?.dataset.sid === {json.dumps(TWO_SID)} && {head}.dataset.sid", 10)
    choose(c, sel, rig.act.session_id)
    out["first"] = c.wait(f"{head}?.dataset.sid === {json.dumps(rig.act.session_id)} && {head}.dataset.sid", 10)
    out["first_is_rig"] = out["first"] == rig.act.session_id
    lv.fields["two"] = False
    lv.refresh()
    c.wait(f"!{pk}", 20)
    out["map_picker"] = c.js(f"!!{t('map-lit-pick')}")
    back_to_map(c)
    return out


def goal(c, rig, lv, sent) -> dict:
    """R57: Run a goal and History open in the Map's own right drawer (no feed to go back to: a page's × closes it)."""
    press(c, t("map-run-goal"))
    out = {"form": c.wait(f"{MD}?.querySelector('[data-testid=map-drawer]')?.dataset.page === 'goal' && !!{MD}.querySelector('[data-testid=run-goal-drawer]') && 'goal'", 15)}
    close = f"{MD}.querySelector('[data-testid=run-goal-close]')"
    c.js(f"{close}.scrollIntoView({{block: 'center'}}); 1")
    x, y, w, h = c.rect(close)
    out["under_back"] = c.js(f"(() => {{ const e = document.elementFromPoint({x + w / 2}, {y + h / 2}); return e ? (e.dataset.testid || e.className || e.tagName) : ''; }})()")
    press(c, close)
    try:
        out["back"] = c.wait(f"!({MD_SHOWN}) && 'back'", 10)
    except TimeoutError:
        raise TimeoutError(f"the goal's x: the drawer still {c.js(MD_SHOWN)}, under the button {out.get('under_back')!r}")
    press(c, t("map-history-all"))  # History's whole list in the drawer: goal runs and saved files beside sessions
    out["history"] = c.wait(f"{MD}?.querySelector('[data-testid=map-drawer]')?.dataset.page === 'history' && !!{MD}.querySelector('[data-testid=live-history-drawer]') && "
                            f"[...{MD}.querySelectorAll('[data-testid=live-history-drawer] .lh-rows > *')].length", 15)
    press(c, f"{MD}.querySelector('[data-testid=live-history-close]')")
    c.wait(f"!({MD_SHOWN})", 10)
    return out


# what the top line, the Replay-last button and the toasts say (a failed replay says why in a toast: "No replay: ...",
# "Nothing to replay: ..."), for the message of a press that started nothing
SEEN = """JSON.stringify((() => { const b = document.querySelector('[data-part="map"] [data-testid="map-lit-replay-last"]');
  const r = b && b.getBoundingClientRect(), at = r && document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
  return { button: b ? [b.title.slice(7, 60), [r.left, r.top, r.width, r.height].map(Math.round), b.disabled, at ? (at.closest('[data-testid]')?.dataset.testid || at.tagName) : null] : null,
    toasts: [...document.querySelectorAll('.toast-text')].map((e) => e.textContent.trim().slice(0, 80)),
    drawer: document.querySelector('[data-part="map"] [data-testid="map-drawer"]')?.dataset.page || null,
    top: document.querySelector('[data-part="map"] [data-testid="map-topline"]')?.textContent.slice(0, 80) }; })())"""


def replay(c, rig, lv, sent) -> dict:
    """Nothing running: the top line offers "Replay the last session"; the replay's rows fill the drawer."""
    for gate in ("a", "b"):  # the session's turn ends for real: its helpers finish, main says its last words
        rig.release(gate)
    for name in ("general-purpose", "reviewer", "stray", "file-counter"):
        lv.state(name, state="done")
    lv.refresh()
    last = t("map-lit-replay-last")
    try:
        out = {"offer": c.wait(f"{last}?.textContent", 60)}
    except TimeoutError:
        raise TimeoutError(f"no Replay the last session: the top line says {c.js(t('map-topline') + '?.textContent')!r}")
    press(c, last)
    try:
        out["replaying"] = c.wait(f"{t('map-topline')}?.dataset.lit === 'replay' && 'replay'", 30)
    except TimeoutError:  # P9 batch 4 (macOS CI, not reproduced on the Linux VM): what the page shows, in the message
        raise TimeoutError("no replay 30 s after the press: " + str(c.js(SEEN))[:600]) from None
    # P7 (the coordinator's ruling): Replay is his press, so the Map's drawer opens on History's page with that replay's
    # rows, at once (no click on the drawer's button first)
    shown = ("[data-part=map] [data-testid=map-drawer][data-page=history] [data-testid=map-drawer-replay]")
    try:
        out["opened"] = c.wait(f"!!document.querySelector('{shown}')?.offsetParent && 'history'", 10)
    except TimeoutError:
        out["opened"] = c.js("document.querySelector('[data-part=map] [data-testid=map-drawer]')?.dataset.page || null")
    click_box(c, "main")  # R57: the Map has no feed, so a replay's click opens no drawer of words; its scrubber moves it
    scrub = q("[data-testid=replay-scrub]")
    c.wait(f"!!{scrub}", 15)
    c.js(f"(() => {{ const s = {scrub}; const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;"
         " set.call(s, s.max); s.dispatchEvent(new Event('input', {bubbles: true})); s.dispatchEvent(new Event('change', {bubbles: true})); })(); 1")
    out["drawer"] = c.js("document.querySelectorAll('[data-part=map] [data-testid=map-feed], [data-part=map] [data-testid=map-feed-panel]').length")
    out["rows"] = c.wait(f"{t('map-topline')}?.dataset.lit === 'replay' && {scrub}.value === {scrub}.max && 'end'", 15)
    # P4 batch 12 (the coordinator's ruling): the replay's rows, up to the scrubber, in the Map's OWN drawer on History's page
    rows = "[data-part=map] [data-testid=map-drawer][data-page=history] [data-testid=map-drawer-replay] [data-testid=map-feed-replay-row]"
    from tests.helpers.studio_live_feed import MD_BTN  # the Map drawer's own button: History's page
    if c.js(f"{MD_BTN}?.getAttribute('aria-pressed')") != "true":
        c.click_on(MD_BTN)
    try:
        out["drawer_rows"] = c.wait(f"(() => {{ const r = [...document.querySelectorAll('{rows}')].filter((e) => e.offsetParent);"
                                    f" const cut = (x) => {{ const s = getComputedStyle(x); return s.textOverflow === 'ellipsis' || s.whiteSpace === 'nowrap'; }};"
                                    f" return r.length ? r.map((e) => [e.dataset.kind, e.scrollWidth <= e.clientWidth + 1 && e.scrollHeight <= e.clientHeight + 1"
                                    f" && ![e, ...e.querySelectorAll('*')].some(cut)]) : null; }})()", 15)
    except TimeoutError:
        out["drawer_rows"] = f"none: drawer {c.js('document.querySelector(`[data-part=map] [data-testid=map-drawer]`)?.dataset.page || null')}"
    out.update(replay_rows_follow(c, rows, scrub))
    return out


def replay_rows_follow(c, rows: str, scrub: str) -> dict:
    """P7: the rows follow the scrubber (fewer at its start than at its end), the newest is at the foot and in sight, and
    History's "Back to now" is in sight and pressable (nothing covers it) at 1500 x 900 and at 1280 x 800."""
    import time
    count = f"document.querySelectorAll('{rows}').length"

    def to(v: str) -> int:
        c.js(f"(() => {{ const s = {scrub}; const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;"
             f" set.call(s, {v}); s.dispatchEvent(new Event('input', {{bubbles: true}})); s.dispatchEvent(new Event('change', {{bubbles: true}})); }})(); 1")
        last = c.js(count)
        for _ in range(10):  # settled: two reads 200 ms apart alike
            time.sleep(0.2)
            now = c.js(count)
            if now == last:
                break
            last = now
        return last
    out = {"scrub": [to("s.min"), to("(+s.min + +s.max) / 2"), to("s.max")]}
    out["foot"] = c.js(f"""(() => {{ const r = [...document.querySelectorAll('{rows}')]; if (!r.length) return null;
      const box = r[0].parentElement, B = box.getBoundingClientRect(), L = r[r.length - 1].getBoundingClientRect();
      const secs = r.map((e) => e.querySelector('.mono')?.textContent.trim().split(':').reduce((a, x) => a * 60 + (+x), 0));
      return [secs.every((s, i) => i === 0 || s >= secs[i - 1]), L.bottom <= B.bottom + 1 && L.top >= B.top - 1]; }})()""")
    hit = ("(() => { const b = document.querySelector('[data-part=map] [data-testid=map-history-now]'); if (!b) return 'none';"
           " const r = b.getBoundingClientRect(); const x = r.left + r.width / 2, y = r.top + r.height / 2;"
           " const at = document.elementFromPoint(x, y); return y > 0 && y < innerHeight && x > 0 && x < innerWidth && !!at && b.contains(at); })()")
    out["now"] = {"1500": c.js(hit)}
    c.call("Emulation.setDeviceMetricsOverride", width=1280, height=800, deviceScaleFactor=1, mobile=False)
    try:
        time.sleep(0.5)
        out["now"]["1280"] = c.js(hit)
    finally:
        c.call("Emulation.setDeviceMetricsOverride", width=1500, height=900, deviceScaleFactor=1, mobile=False)
    return out
