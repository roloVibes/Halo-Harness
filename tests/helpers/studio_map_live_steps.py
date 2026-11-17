"""tests.helpers.studio_map_live_steps -- the first steps of the lit run's driver (tests/helpers/studio_map_live.py):
lit, hop, steps, helper on Agents -> 4 · Live (3.6.0.2 R34: the run is drawn there; the Map is the plan), feed on the
Map's drawer (P4 batch 4 moves the Feed to Live). Each waits for the value it reads; no fixed sleep is a pass condition."""
from __future__ import annotations

import base64
import time
from pathlib import Path

from tests.helpers.chrome_driver import emulate_motion
from tests.helpers.session_rig import wait_for
from tests.helpers.studio_agents import key

P = '[data-part="map"] '
VIEW = "document.querySelector('[data-testid=agents]')?.dataset.view"
SHOTS: list = []
STEER = "check the tax rule in the notes first"


def q(sel: str) -> str:
    return f"document.querySelector('{P}{sel}')"


def qa(sel: str) -> str:
    return f"[...document.querySelectorAll('{P}{sel}')]"


def t(name: str) -> str:
    return q(f'[data-testid="{name}"]')


def box(bid: str) -> str:
    return q(f'[data-testid="map-world"] [data-map-box="{bid}"]')


def shot(c, name: str) -> None:
    if SHOTS:
        (Path(SHOTS[0]) / name).write_bytes(base64.b64decode(c.call("Page.captureScreenshot", format="png")["data"]))


def click_box(c, bid: str) -> None:
    c.js(f"{box(bid)}.scrollIntoView({{block: 'nearest', inline: 'nearest'}}); 1")
    c.click_on(box(bid), 0.5, 0.25)


def hop(c, lv, line: str, task: str, **kw) -> None:
    a, b = line.split(" -> ")
    lv.frame("main", "map_hop", {"map": "shop", "line": line, "from": a, "to": b, "state": "start", "t": time.time(), "task": task,
                                 "why": "always", **kw})


LP = '[data-part="live"] '  # 3.6.0.2 R34: the run is drawn in Agents -> 4 · Live (the Map is the plan)
LWORLD = "[data-testid=live-world]"


def lq(sel: str) -> str:
    return f"document.querySelector('{LP}{sel}')"


def lqa(sel: str) -> str:
    return f"[...document.querySelectorAll('{LP}{sel}')]"


def lbox(bid: str) -> str:
    return lq(f'{LWORLD} [data-map-box="{bid}"]')


L_STATES = f"Object.fromEntries({lqa(LWORLD + ' [data-map-box]')}.map((b) => [b.dataset.mapBox, b.dataset.state || '']))"
L_CUT = f"{lqa(LWORLD + ' [data-map-box]')}.filter((b) => b.querySelector('.mp-inner').scrollHeight > b.clientHeight + 1).length"
FACE = ".mp-lit-row[data-state]"  # a box's own row (LitFace): "{kind} · {state}[ · what it does now]"


def lit(c, rig, lv, sent) -> dict:
    emulate_motion(c, "no-preference")
    lv.state("reviewer", cost_usd=0.0123)
    c.go(rig.url("agents", "&view=live"))
    c.wait(f"{VIEW} === 'live'", 40)
    tr = lq("[data-testid=live-truth]")
    out = {"head": c.wait(f"/^T[12]$/.test({tr}?.dataset.state || '') && [{tr}.dataset.state, {tr}.textContent]", 40)}
    out["sentence"] = c.wait(f"{lq('[data-testid=live-status]')}?.textContent.includes('working') && {lq('[data-testid=live-status]')}.textContent", 20)
    tab = "document.querySelector('[data-part=live] [data-testid=agents-view-live]')"  # 3.6.0.2 R52: the dot is Live's
    mtab = "document.querySelector('[data-part=live] [data-testid=agents-view-map]')"
    out["dot"] = c.js(f"[{tab}?.dataset.running, {tab}?.innerText, {mtab}?.dataset.running || '']")
    out["states"] = c.wait(f"(() => {{ const s = {L_STATES}; return s.code === 'working' && s.check === 'working' && s.notes === 'idle' && s; }})()", 30)
    out["code_face"] = c.js(f"{lbox('code')}.querySelector('{FACE}')?.textContent")
    out["notes_face"] = c.js(f"[...{lbox('notes')}.querySelectorAll('{FACE}')].map((r) => r.textContent)")
    out["cut"] = c.js(L_CUT)
    out["stranger"] = stray(c, lv)
    return out


def stray(c, lv) -> dict:
    """The stray agent (x0rph4n1, its parent `nobody`: no box of the map started it, so R17 has no box to draw it from):
    in Live it is no row of any box and no line, it is not a hand-off outside the map; the status line counts it among
    those working (it says one agent fewer once it is done, and again as many when it works)."""
    st = lq("[data-testid=live-status]")
    out = {"rows": c.js(f"document.querySelectorAll('{LP}[data-testid=live-frame] [data-row=x0rph4n1]').length"),
           "working": c.js(f"{st}?.textContent")}
    lv.state("stray", state="done")
    try:
        out["done"] = c.wait(f"{st}?.textContent !== {out['working']!r} && {st}.textContent", 15)
    finally:
        lv.state("stray", state="running")
    out["again"] = c.wait(f"{st}?.textContent === {out['working']!r} && {st}.textContent", 15)
    return out


def hop_step(c, rig, lv, sent) -> dict:
    label = lq('[data-testid="live-label"][data-from="main"][data-to="code"]')
    line = lq(f'{LWORLD} .mp-line[data-from=main][data-to=code]')
    hop(c, lv, "main -> code", "apply the discount before tax")
    out = {"pulse": c.wait(f"{label}?.dataset.pulse === '1' && {label}.textContent", 10)}
    out["travel"] = c.wait(f"!!{line}?.dataset.lit && [{line}.dataset.lit, {line}.dataset.hops]", 10)
    shot(c, "studio-live-lit.png")
    out["back"] = c.wait(f"!{label}.dataset.pulse && {label}.textContent", 12)
    chain = lq('[data-testid="live-label"][data-from="code"][data-to="check"]')
    hop(c, lv, "code -> check", "check the basket diff", chain=True)
    out["chain"] = c.wait(f"{chain}?.dataset.pulse === '1' && {chain}.textContent", 10)
    emulate_motion(c, "reduce")
    hop(c, lv, "main -> research", "read the pricing notes")
    rl = lq(f'{LWORLD} .mp-line[data-from=main][data-to=research]')
    out["reduced"] = c.wait(f"!!{rl}?.dataset.lit && !document.querySelector('{LP}[data-testid=map-pulse]')", 10)
    emulate_motion(c, "no-preference")
    return out


def steps(c, rig, lv, sent) -> dict:
    def st(kind, **kw):
        lv.frame("main", "map_step", {"map": "shop", "box": "check", "workflow": "review", "kind": kind, "t": time.time(), **kw})
    st("start", steps=[{"name": "Review"}, {"name": "Test"}])
    st("step", n=1, name="Review", state="done", rounds=1)
    st("agent", n=1, round=1, name="reviewer", state="done")
    st("agent", n=2, round=1, name="tester", state="done")
    st("check", n=2, round=1, yes=False)
    st("agent", n=2, round=2, name="tester", state="running")
    st("check", n=2, round=2, yes=False)
    got = f"{lbox('check')}.querySelectorAll('[data-testid=session-map-step]')"
    out = {"steps": c.wait(f"{got}.length === 2 && {got}[1].textContent.endsWith('working') && [{lbox('check')}.querySelector('[data-testid=session-map-block-head]')?.textContent,"
                           f" ...[...{got}].map((s) => s.textContent)]", 10)}
    head = f"{lbox('check')}.querySelector('[data-testid=session-map-block-head]')"
    c.js(f"{head}.scrollIntoView({{block: 'nearest', inline: 'nearest'}}); 1")
    c.click_on(head)  # R18: a block's head opens the step-in card for its running step
    out["open_drawer"] = c.wait(f"{lq('[data-testid=map-step-in]')}?.dataset.target", 10)
    c.click_on(lq("[data-testid=map-step-in-close]"))
    c.wait(f"!{lq('[data-testid=map-step-in]')}", 10)
    return out


def helper(c, rig, lv, sent) -> dict:
    row = lq(f'{LWORLD} [data-row="h3lp3r01"]')
    c.wait(f"!!{row}", 15)
    saved = f"{lqa(LWORLD + ' [data-testid=session-map-row]:not([data-helper])')}"
    out = {"helper": c.js(f"[{row}.querySelector('[data-testid=session-map-row-text]')?.textContent, !!{row}.querySelector('[data-testid=map-save-agent]'),"
                          f" {row}.closest('[data-map-box]')?.dataset.mapBox, {saved}.length > 0 && {saved}.every((r) => !r.querySelector('[data-testid=map-save-agent]'))]")}
    c.js(f"{row}.scrollIntoView({{block: 'center', inline: 'nearest'}}); 1")  # the picture shows it
    shot(c, "studio-live-helper.png")
    btn = f"{row}.querySelector('[data-testid=map-save-agent]')"
    c.js(f"{btn}.scrollIntoView({{block: 'nearest'}}); 1")
    c.click_on(btn)
    out["view"] = c.wait(f"{VIEW} === 'crew' && {VIEW}", 15)
    name = "document.querySelector('[data-testid=crew-name]')"
    out["form"] = c.wait(f"{name}?.value && [{name}.value, document.body.innerText.includes('the helper a session made up, not saved yet')]", 10)
    folder = Path(rig.state) / "crew" / "agents"
    out["written"] = sorted(p.name for p in folder.glob("*.yaml")) if folder.is_dir() else []
    c.js("document.activeElement?.blur(); 1")
    key(c, "4")  # 3.6.0.2 R57: the Feed is 4 · Live's drawer: the next step reads it there
    c.wait(f"{VIEW} === 'live'", 20)
    return out


def feed(c, rig, lv, sent) -> dict:
    """R57: the Feed is 4 · Live's right drawer (tests/helpers/studio_live_feed.py): opened from its button, a click on a box
    of Live's drawing sets it to that box (it was a click on the Map's box, opening the Map's drawer)."""
    from tests.helpers.studio_live_feed import FD, FEED_SHOWN, click_live_box, close_card, live_box, open_feed
    out: dict = {}
    open_feed(c, lv.sid)
    click_live_box(c, "code")
    out["filter"] = c.wait(f"{FD}?.dataset.filter === 'code' && {FD}.dataset.filter", 10)
    close_card(c)
    lv.think("implementer", "tM1", "The discount has to come before tax.", end=True, ms=600)
    lv.say("implementer", "Applying the discount before tax now.")
    lv.talk("main", "implementer", "Apply the discount before tax in basket.py.", "task", mid="tk-m1")
    rows = f"[...{FD}.querySelectorAll('[data-testid=live-row]')].map((r) => r.dataset.kind)"
    try:
        out["kinds"] = c.wait(f"(() => {{ const k = {rows}; return ['think', 'text', 'talk'].every((x) => k.includes(x)) && k; }})()", 15)
    except TimeoutError:
        raise TimeoutError(f"the Feed's rows: {c.js(rows)}; it says: {c.js(f'{FD}.innerText.slice(0, 300)')!r}")
    lv.state("reviewer", state="waiting")
    lv.ask("reviewer", "permission_request", {"id": "perm-9", "name": "Bash", "input": {"command": "git push origin feature/basket"}})
    chk = live_box("check")
    out["waits"] = c.wait(f"{chk}?.dataset.state === 'waiting' && {chk}.dataset.state", 15)  # check is the review workflow's block: its rows are its steps
    click_live_box(c, "check")
    c.wait(f"{FD}?.dataset.filter === 'check'", 10)
    close_card(c)
    out["ask_keys"] = c.wait(f"{FD}.querySelectorAll('[data-testid=session-live-ask] [data-testid=session-live-key]').length", 10)
    # the words he reads on Live that it waits on him: the Feed's ask row says what is asked (a block box's own state
    # line is the workflow's, R43)
    out["ask_what"] = c.js(f"{FD}.querySelector('[data-testid=session-live-ask] .slv-ask-what')?.textContent || ''")
    shot(c, "studio-map-feed.png")  # the name tools/capture_map_live.py collects
    lv.state("reviewer", state="running")
    c.js(f"{live_box('research')}.focus(); 1")  # the keyboard: Enter on a box of Live sets the Feed to it
    c.key("Enter")
    out["keyboard"] = c.wait(f"{FD}?.dataset.filter === 'research' && 'research'", 10)
    close_card(c)
    area = f"{FD}.querySelector('[data-testid=map-feed-steer-text]')"
    c.js(f"{area}.focus(); 1")
    c.type_text(STEER)
    c.click_on(f"{FD}.querySelector('[data-testid=map-feed-steer]')")
    got = wait_for(lambda: [d for d in sent if d["cmd"] == "agent_steer" and STEER in str(d["fields"].get("text"))], 20) or [{}]
    out["steer"] = [got[0].get("cmd"), got[0].get("status")]
    c.click_on(f"{FD}.querySelector('[data-testid=map-feed-stop]')")
    c.wait(f"!!{FD}.querySelector('[data-testid=map-feed-stop-yes]')", 5)
    c.click_on(f"{FD}.querySelector('[data-testid=map-feed-stop-yes]')")
    got = wait_for(lambda: [d for d in sent if "stop" in d["cmd"]], 20) or [{}]
    out["stop"] = [got[0].get("cmd"), got[0].get("status")]
    c.click_on("document.querySelector('[data-part=live] [data-testid=live-feed-panel] [data-testid=panel-collapse]')")  # closed again
    c.wait(f"!({FEED_SHOWN})", 10)
    c.js("document.activeElement?.blur(); 1")
    key(c, "3")  # the next steps start on 3 · Map, on shop, as they did when the Feed was the Map's
    sw = t("map-switcher")
    c.wait(f"{VIEW} === 'map' && [...({sw}?.options || [])].some((o) => o.value === 'shop')", 20)
    c.js(f"(() => {{ const s = {sw}; const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;"
         f" set.call(s, 'shop'); s.dispatchEvent(new Event('change', {{bubbles: true}})); }})(); 1")
    c.wait(f"{sw}.value === 'shop'", 20)
    return out


hop_step.__name__ = "hop"
