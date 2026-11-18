"""tests.helpers.studio_map_takeover_more -- the R4b driver's later steps (tests/helpers/studio_map_takeover.py): keys,
hover, ask, two, goal, replay. Each waits for the value it reads; no fixed sleep is a pass condition. 3.6.0.2 R57: the
Feed is 4 · Live's drawer; the Map's own drawer holds Run a goal and History (tests/helpers/studio_live_feed.py)."""
from __future__ import annotations

import json

from tests.helpers.session_rig import wait_for
from tests.helpers.studio_map_live_more import press
from tests.helpers.studio_map_live_steps import q, t
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
    """R57: Run a goal opens in the Map's own right drawer (no feed to go back to: a page's × closes it; 3.6.0.3 B: History
    left)."""
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
    return out


def ended(c, rig, lv, sent) -> dict:
    """3.6.0.3 B (R-B8): the session's turn ends for real (its helpers finish, main says its last words): with nothing
    running the Map is the plan -- no "Replay the last session", no Replay slot, nothing lit, no replay line."""
    for gate in ("a", "b"):
        rig.release(gate)
    for name in ("general-purpose", "reviewer", "stray", "file-counter"):
        lv.state(name, state="done")
    lv.refresh()
    line = t("map-topline")
    out = {"ended": c.wait(f"!!{line} && 'ended'", 60)}
    out["replay_parts"] = c.js(f"[!!{t('map-lit-replay-last')}, !!{line}.querySelector('.mp-slot'), {line}.hasAttribute('data-lit'),"
                               f" !!{t('map-replay-close')}, !!{q('[data-testid=map-world]')}?.dataset.lit]")
    return out
