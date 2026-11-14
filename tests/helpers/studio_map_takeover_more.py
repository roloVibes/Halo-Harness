"""tests.helpers.studio_map_takeover_more -- the R4b driver's later steps (tests/helpers/studio_map_takeover.py): keys,
hover, ask, two, goal, replay. Each waits for the value it reads; no fixed sleep is a pass condition."""
from __future__ import annotations

import json

from tests.helpers.session_rig import wait_for
from tests.helpers.studio_map_live_more import press
from tests.helpers.studio_map_live_steps import box, click_box, q, t
from tests.helpers.studio_map_takeover_steps import FD

CARD = "document.getElementById('halo-hover-card')"


def letter(c, ch: str) -> None:
    for kind in ("keyDown", "keyUp"):
        c.call("Input.dispatchKeyEvent", type=kind, key=ch, code=f"Key{ch.upper()}", windowsVirtualKeyCode=ord(ch.upper()),
               **({"text": ch} if kind == "keyDown" else {}))


def keys(c, rig, lv, sent) -> dict:
    c.js(f"{q('[data-testid=map-scroll]')}.focus(); 1")
    out = {"working": c.js("[...document.querySelectorAll('[data-part=map] .mp-world [data-map-box][data-state=working], "
                           "[data-part=map] .mp-world [data-map-box][data-state=waiting]')].map((b) => b.dataset.mapBox)")}
    seen = []
    for ch in ("j", "j", "k"):
        before = c.js("document.activeElement?.dataset?.mapBox || ''")
        letter(c, ch)
        seen.append(c.wait(f"(document.activeElement?.dataset?.mapBox || '') !== {json.dumps(before)} && document.activeElement.dataset.mapBox", 5))
    out["focus"] = seen
    return out


def hover(c, rig, lv, sent) -> dict:
    out = {"by_itself": c.js(f"!!{CARD} && getComputedStyle({CARD}).display !== 'none'")}
    b = box("research")
    c.js(f"{b}.scrollIntoView({{block: 'center', inline: 'center'}}); 1")
    x, y, w, h = c.rect(b)
    c.mouse("mouseMoved", x + w * 0.4, y + h * 0.3)
    c.mouse("mouseMoved", x + w * 0.45, y + h * 0.35)
    out["card"] = c.wait(f"{CARD}?.querySelector('[data-testid=hover-card-title]')?.textContent.includes('research') && "
                         f"[{CARD}.querySelector('[data-testid=hover-card-title]').textContent, "
                         f"[...{CARD}.querySelectorAll('[data-testid=hover-card-row]')].map((r) => r.dataset.row)]", 10)
    out["covers"] = c.js(f"(() => {{ const k = {CARD}.getBoundingClientRect(); return [...{b}.querySelectorAll('button')].filter((x) => {{"
                         " const r = x.getBoundingClientRect(); return r.width && !(r.right <= k.left || r.left >= k.right || r.bottom <= k.top || r.top >= k.bottom); }).length; })()")
    c.mouse("mouseMoved", 4, 4)
    out["gone"] = c.wait(f"(!{CARD} || getComputedStyle({CARD}).display === 'none' || !{CARD}.textContent) && 'gone'", 10)
    return out


def ask(c, rig, lv, sent) -> dict:
    """A real pending ask: the session row lists it (`pending`, so Studio makes its Attention row) and its frame names
    the reviewer; the drawer's key answers it through the Attention row and the session's socket receives it."""
    rig.controller.register_pending_permission("perm-r4b", "Bash", {"command": "git push origin feature/basket"})  # a real waiter
    lv.state("reviewer", state="waiting")
    lv.ask("reviewer", "permission_request", {"id": "perm-r4b", "name": "Bash", "input": {"command": "git push origin feature/basket"}})
    lv.refresh(pending={"permission": ["perm-r4b"]})
    click_box(c, "check")
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
    return out


def pick(c, sid: str) -> None:
    sel = t("map-lit-pick")
    c.js(f"(() => {{ const s = {sel}; const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;"
         f" set.call(s, {json.dumps(sid)}); s.dispatchEvent(new Event('change', {{bubbles: true}})); }})(); 1")


def two(c, rig, lv, sent) -> dict:
    from tests.helpers.studio_map_takeover import TWO_SID
    lv.fields["two"] = True
    lv.refresh()
    head = t("map-topline")
    out = {"options": c.wait(f"{t('map-lit-pick')}?.options.length >= 2 && [...{t('map-lit-pick')}.options].map((o) => o.value)", 20)}
    pick(c, TWO_SID)
    out["second"] = c.wait(f"{head}?.dataset.sid === {json.dumps(TWO_SID)} && {head}.dataset.sid", 10)
    pick(c, rig.act.session_id)
    out["first"] = c.wait(f"{head}?.dataset.sid === {json.dumps(rig.act.session_id)} && {head}.dataset.sid", 10)
    out["first_is_rig"] = out["first"] == rig.act.session_id
    lv.fields["two"] = False
    lv.refresh()
    c.wait(f"!{t('map-lit-pick')}", 20)
    return out


def goal(c, rig, lv, sent) -> dict:
    press(c, t("map-run-goal"))
    out = {"form": c.wait(f"{FD}?.dataset.filter === 'goal' && !!{FD}.querySelector('[data-testid=run-goal-drawer]') && 'goal'", 15)}
    back = f"{FD}.querySelector('[data-testid=map-feed-back]')"
    c.js(f"{back}.scrollIntoView({{block: 'center'}}); 1")
    x, y, w, h = c.rect(back)
    out["under_back"] = c.js(f"(() => {{ const e = document.elementFromPoint({x + w / 2}, {y + h / 2}); return e ? (e.dataset.testid || e.className || e.tagName) : ''; }})()")
    press(c, back)
    try:
        out["back"] = c.wait(f"{FD}?.dataset.filter === 'everyone' && 'back'", 10)
    except TimeoutError:
        raise TimeoutError(f"back: filter {c.js(f'{FD}?.dataset.filter')!r}, under the button {out.get('under_back')!r}, at {c.rect(back)}")
    press(c, t("map-history-all"))  # Live's whole History in the drawer: goal runs and saved files beside sessions
    out["history"] = c.wait(f"{FD}?.dataset.filter === 'history' && !!{FD}.querySelector('[data-testid=live-history-drawer]') && "
                            f"[...{FD}.querySelectorAll('[data-testid=live-history-drawer] .lh-rows > *')].length", 15)
    press(c, f"{FD}.querySelector('[data-testid=map-feed-back]')")
    c.wait(f"{FD}?.dataset.filter === 'everyone'", 10)
    return out


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
    out["replaying"] = c.wait(f"{t('map-topline')}?.dataset.lit === 'replay' && 'replay'", 30)
    click_box(c, "main")
    out["drawer"] = c.wait(f"{FD}?.dataset.replay === '1' && !!({FD}.querySelector('[data-testid=map-feed-replay]') || "
                           f"{FD}.querySelector('[data-testid=map-feed-replay-empty]')) && 'rows'", 15)
    scrub = q("[data-testid=replay-scrub]")
    c.js(f"(() => {{ const s = {scrub}; const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;"
         " set.call(s, s.max); s.dispatchEvent(new Event('input', {bubbles: true})); s.dispatchEvent(new Event('change', {bubbles: true})); })(); 1")
    out["rows"] = c.wait(f"[...({FD}?.querySelectorAll('[data-testid=map-feed-replay-row]') || [])].map((r) => r.dataset.kind)", 15)
    return out
