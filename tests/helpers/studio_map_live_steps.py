"""tests.helpers.studio_map_live_steps -- the first steps of the lit Map's driver (tests/helpers/studio_map_live.py):
lit, hop, steps, helper, feed. Each waits for the value it reads; no fixed sleep is a pass condition."""
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


STATES = f"Object.fromEntries({qa('[data-testid=map-world] [data-map-box]')}.map((b) => [b.dataset.mapBox, b.dataset.state || '']))"
CUT = f"{qa('[data-testid=map-world] [data-map-box]')}.filter((b) => b.querySelector('.mp-inner').scrollHeight > b.clientHeight + 1).length"


def lit(c, rig, lv, sent) -> dict:
    emulate_motion(c, "no-preference")
    lv.state("reviewer", cost_usd=0.0123)
    c.go(rig.url("agents", "&view=map&map=shop"))
    c.wait(f"{VIEW} === 'map'", 40)
    out = {"head": c.wait(f"{t('map-lit-head')}?.textContent.startsWith('A session is running on this map') && {t('map-lit-head')}.textContent", 40)}
    out["sentence"] = c.wait(f"{t('map-lit-sentence')}?.textContent", 20)
    out["when"] = c.js(f"{t('map-lit-when')}?.textContent")
    tab = "document.querySelector('[data-part=map] [data-testid=agents-view-live]')"  # 3.6.0.2 R52: the dot is Live's
    mtab = "document.querySelector('[data-part=map] [data-testid=agents-view-map]')"
    out["dot"] = c.js(f"[{tab}?.dataset.running, {tab}?.innerText, {mtab}?.dataset.running || '']")
    out["states"] = c.wait(f"(() => {{ const s = {STATES}; return s.code === 'working' && s.check === 'working' && s.notes === 'idle' && s; }})()", 30)
    out["check_rows"] = c.js(f"[...{box('check')}.querySelectorAll('.mp-lit-row')].map((r) => r.textContent)")
    out["notes_rows"] = c.js(f"[...{box('notes')}.querySelectorAll('.mp-lit-row')].map((r) => r.textContent)")
    out["cut"] = c.js(CUT)
    out["stranger"] = c.wait(f"{qa('[data-testid=map-stranger]')}.map((s) => [s.dataset.agent, s.querySelector('.mp-tag').textContent])", 10)
    return out


def hop_step(c, rig, lv, sent) -> dict:
    label = q('[data-testid="map-label"][data-from="main"][data-to="code"]')
    hop(c, lv, "main -> code", "apply the discount before tax")
    out = {"pulse": c.wait(f"{label}?.dataset.pulse === '1' && {label}.textContent", 10)}
    out["travel"] = c.js(f"[!!{q('[data-testid=map-pulse]')}, {q('[data-testid=map-line][data-from=main][data-to=code]')}?.dataset.pulse]")
    shot(c, "studio-map-lit.png")
    out["back"] = c.wait(f"!{label}.dataset.pulse && {label}.textContent", 12)
    chain = q('[data-testid="map-label"][data-from="code"][data-to="check"]')
    hop(c, lv, "code -> check", "check the basket diff", chain=True)
    out["chain"] = c.wait(f"{chain}?.dataset.pulse === '1' && {chain}.textContent", 10)
    emulate_motion(c, "reduce")
    hop(c, lv, "main -> research", "read the pricing notes")
    line = q('[data-testid=map-line][data-from=main][data-to=research]')
    out["reduced"] = c.wait(f"{line}?.dataset.pulse === '1' && [...document.querySelectorAll('[data-testid=map-pulse]')].every((d) => getComputedStyle(d).display === 'none')", 10)
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
    click_box(c, "check")
    got = f"{qa('[data-map-box=check] [data-testid=map-lit-step]')}"
    out = {"steps": c.wait(f"{got}.length === 2 && {got}[1].textContent.includes('2 checks') && {got}.map((s) => s.textContent)", 10)}
    out["open_drawer"] = c.wait("document.querySelector('[data-testid=map-feed]')?.dataset.filter", 10)
    return out


def helper(c, rig, lv, sent) -> dict:
    h = q('[data-testid="map-world"] [data-helper="h3lp3r01"]')
    c.wait(f"!!{h}", 15)
    out = {"helper": c.js(f"[{h}.querySelector('[data-testid=map-made-up]')?.textContent, getComputedStyle({h}).borderTopStyle,"
                          f" {h}.getBoundingClientRect().left > {box('main')}.getBoundingClientRect().right]")}
    c.js(f"{h}.scrollIntoView({{block: 'center', inline: 'nearest'}}); 1")  # the picture shows it
    shot(c, "studio-map-helper.png")
    btn = f"{h}.querySelector('[data-testid=map-save-agent]')"
    c.js(f"{btn}.scrollIntoView({{block: 'nearest'}}); 1")
    c.click_on(btn)
    out["view"] = c.wait(f"{VIEW} === 'crew' && {VIEW}", 15)
    name = "document.querySelector('[data-testid=crew-name]')"
    out["form"] = c.wait(f"{name}?.value && [{name}.value, document.body.innerText.includes('the helper a session made up, not saved yet')]", 10)
    folder = Path(rig.state) / "crew" / "agents"
    out["written"] = sorted(p.name for p in folder.glob("*.yaml")) if folder.is_dir() else []
    c.js("document.activeElement?.blur(); 1")
    key(c, "3")
    c.wait(f"{VIEW} === 'map' && !!{t('map-lit-head')}", 20)
    return out


def feed(c, rig, lv, sent) -> dict:
    out: dict = {}
    click_box(c, "code")
    fd = "document.querySelector('[data-testid=map-feed]')"
    out["filter"] = c.wait(f"{fd}?.dataset.filter === 'code' && {fd}.dataset.filter", 10)
    lv.think("implementer", "tM1", "The discount has to come before tax.", end=True, ms=600)
    lv.say("implementer", "Applying the discount before tax now.")
    lv.talk("main", "implementer", "Apply the discount before tax in basket.py.", "task", mid="tk-m1")
    rows = f"[...{fd}.querySelectorAll('[data-testid=live-row]')].map((r) => r.dataset.kind)"
    try:
        out["kinds"] = c.wait(f"(() => {{ const k = {rows}; return ['think', 'text', 'talk'].every((x) => k.includes(x)) && k; }})()", 15)
    except TimeoutError:
        raise TimeoutError(f"the drawer's rows: {c.js(rows)}; it says: {c.js(f'{fd}.innerText.slice(0, 300)')!r}")
    lv.state("reviewer", state="waiting")
    lv.ask("reviewer", "permission_request", {"id": "perm-9", "name": "Bash", "input": {"command": "git push origin feature/basket"}})
    out["waits"] = c.wait(f"{box('check')}.dataset.state === 'waiting' && {box('check')}.querySelector('[data-testid=map-lit-state]').textContent", 15)
    click_box(c, "check")
    c.wait(f"{fd}?.dataset.filter === 'check'", 10)
    out["ask_keys"] = c.wait(f"{fd}.querySelectorAll('[data-testid=session-live-ask] [data-testid=session-live-key]').length", 10)
    shot(c, "studio-map-feed.png")
    lv.state("reviewer", state="running")
    c.js(f"{box('research')}.focus(); 1")  # the keyboard: Enter on a box opens its words
    c.key("Enter")
    out["keyboard"] = c.wait(f"{fd}?.dataset.filter === 'research' && 'research'", 10)
    area = f"{fd}.querySelector('[data-testid=map-feed-steer-text]')"
    c.js(f"{area}.focus(); 1")
    c.type_text(STEER)
    c.click_on(f"{fd}.querySelector('[data-testid=map-feed-steer]')")
    got = wait_for(lambda: [d for d in sent if d["cmd"] == "agent_steer" and STEER in str(d["fields"].get("text"))], 20) or [{}]
    out["steer"] = [got[0].get("cmd"), got[0].get("status")]
    c.click_on(f"{fd}.querySelector('[data-testid=map-feed-stop]')")
    c.wait(f"!!{fd}.querySelector('[data-testid=map-feed-stop-yes]')", 5)
    c.click_on(f"{fd}.querySelector('[data-testid=map-feed-stop-yes]')")
    got = wait_for(lambda: [d for d in sent if "stop" in d["cmd"]], 20) or [{}]
    out["stop"] = [got[0].get("cmd"), got[0].get("status")]
    return out


hop_step.__name__ = "hop"
