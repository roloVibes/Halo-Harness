"""tests.helpers.studio_map_takeover_steps -- the first steps of the R4b driver (tests/helpers/studio_map_takeover.py):
facts, clocks, talk, depth, plan. Each waits for the value it reads, right after the action that causes it (a pulse
shows for a few seconds); no fixed sleep is a pass condition. 3.6.0.2 R57: the drawer these read is 4 · Live's Feed
(tests/helpers/studio_live_feed.py): a box is set in it by a click on Live's drawing, and the Map's links (the wait, a
helper's "+n under it", the plan) land there; each step comes back to 3 · Map after."""
from __future__ import annotations

import time

from tests.helpers.chrome_driver import emulate_motion
from tests.helpers.session_rig import wait_for
from tests.helpers.studio_map_live_more import press
from tests.helpers.studio_map_live_steps import VIEW, box, click_box, q, qa, t
from tests.helpers.studio_agents import key
from tests.helpers.studio_live_feed import choose, click_live_box, close_card, live_box, open_feed

FD = "document.querySelector('[data-testid=map-feed]')"  # 4 · Live's Feed: the Map has none (R57)
HEAD = f"{FD}?.querySelector('[data-testid=map-feed-head]')"
WHY = "Auto: the strongest reasoning model under the lineup's budget"


def fact(name: str) -> str:
    return f"({HEAD}?.querySelector('[data-testid={name}]')?.textContent || '')"


def facts(c, rig, lv, sent) -> dict:
    emulate_motion(c, "no-preference")
    lv.state("reviewer", model_reason=WHY, tokens_in=1234, tokens_out=56, cost_usd=0.0123, since=time.time() - 75)
    c.go(rig.url("agents", "&view=map&map=shop"))
    c.wait(f"{VIEW} === 'map'", 40)
    c.wait(f"!!{t('map-quiet')}", 40)  # 3.6.0.2 R55: the Map is the plan; its quiet line names the session
    to_feed(c, lv, "check")
    c.wait(f"{live_box('check')}?.dataset.state === 'working'", 30)
    try:
        c.wait(f"{FD}?.dataset.filter === 'check' && {HEAD}?.dataset.agent === 'r3v1e2w0'", 15)
    except TimeoutError:
        raise TimeoutError(f"the Feed on check: {c.js(f'[{FD}?.dataset.filter, {FD}?.dataset.sid, {HEAD}?.dataset.agent, {FD}?.innerText.slice(0, 200)]')}")
    out = {"head": c.wait(f"{fact('map-fact-why')} && [{fact('map-fact-who')}, {fact('map-fact-model')}, {fact('map-fact-why')}, {fact('map-fact-uses')}, "
                          f"{fact('map-fact-tokens')}, {fact('map-fact-cost')}, {fact('map-fact-ran')}]", 15)}
    pick_feed(c, "research")  # Pause / Resume on a real agent of the session (the researcher), so its socket answers
    c.wait(f"{FD}?.dataset.filter === 'research' && !!{FD}.querySelector('[data-testid=map-feed-pause]')", 15)
    press(c, f"{FD}.querySelector('[data-testid=map-feed-pause]')")
    got = wait_for(lambda: [d for d in sent if "pause" in str(d["cmd"]) or d["fields"].get("cmd") == "pause"], 20) or [{}]
    out["pause"] = [got[0].get("cmd"), got[0].get("fields", {}).get("cmd"), got[0].get("status")]
    lv.state("researcher", state="paused")
    out["resume_btn"] = c.wait(f"{FD}.querySelector('[data-testid=map-feed-pause][data-paused]')?.textContent", 15)
    press(c, f"{FD}.querySelector('[data-testid=map-feed-pause]')")
    got = wait_for(lambda: [d for d in sent if "resume" in str(d["cmd"]) or d["fields"].get("cmd") == "resume"], 20) or [{}]
    out["resume"] = [got[0].get("cmd"), got[0].get("fields", {}).get("cmd"), got[0].get("status")]
    lv.state("researcher", state="running")
    pick_feed(c, "check")
    c.wait(f"{FD}?.dataset.filter === 'check'", 10)
    lv.state("reviewer", state="failed")
    c.wait(f"!!{FD}.querySelector('[data-testid=map-feed-dismiss]')", 15)
    press(c, f"{FD}.querySelector('[data-testid=map-feed-dismiss]')")
    out["dismissed"] = c.wait(f"!{FD}.querySelector('[data-testid=map-feed-dismiss]') && {HEAD}?.dataset.state === 'failed' && 'gone'", 10)
    lv.state("reviewer", state="running")
    back_to_map(c)
    return out


def clocks(c, rig, lv, sent) -> dict:
    """3.6.0.2 R55 (rewritten to the truth): a tool's seconds on its box, the outline of the box the session waits on and
    the sentence's wait link were the Map's run overlay. The Map is the plan: the run is 4 · Live's -- its box says
    waiting, its Feed shows the ask -- and the Map draws none of them."""
    out: dict = {}
    lv.tool("implementer", "Bash", "call-clk", current="pytest -q")
    lv.state("reviewer", state="waiting")
    lv.ask("reviewer", "permission_request", {"id": "perm-clk", "name": "Bash", "input": {"command": "git push origin feature/basket"}})
    to_feed(c, lv, "check")
    out["live_waiting"] = c.wait(f"{live_box('check')}?.dataset.state === 'waiting' && 'waiting'", 20)
    out["feed_ask"] = c.wait(f"{FD}?.dataset.filter === 'check' && !!{FD}.querySelector('[data-testid=session-live-ask]') && 'ask'", 20)
    back_to_map(c)
    out["map_run"] = c.js(f"[{qa('[data-testid=map-lit-doing]')}.length, {qa('[data-testid=map-world] [data-map-box][data-waited]')}.length, "
                          f"{qa('[data-testid=map-lit-wait]')}.length]")
    lv.state("reviewer", state="running")
    lv.result("implementer", "call-clk", "3 passed")
    return out


def talk(c, rig, lv, sent) -> dict:
    """R55 (rewritten): one agent's words to another were a pulse on the Map's run overlay; they are a row of 4 · Live's
    Feed, and the Map draws no pulse and adds no line."""
    out: dict = {"lines_before": c.js(f"{qa('[data-testid=map-line]')}.length")}
    lv.talk("implementer", "reviewer", "Please look at the tax order in basket.py before you pass it", "task", mid="tk-r4b-1")
    to_feed(c, lv, "code")
    out["feed"] = c.wait(f"{FD}?.textContent.includes('Please look at the tax order') && 'said'", 20)
    back_to_map(c)
    out["pulse"] = c.js(f"{qa('[data-testid=map-talk]')}.length")
    out["lines"] = c.js(f"{qa('[data-testid=map-line]')}.length")
    return out


def depth(c, rig, lv, sent) -> dict:
    """R55 + R15 (rewritten): main's made-up helpers were boxes of the Map's run overlay ("+1 under it"); the Map draws
    none, and 4 · Live shows a made-up child as a row of the box that started it."""
    out: dict = {}
    lv.spawn("n3st3d01", "file-counter", "general-purpose", "or:mock/glm-5-coder", "Count the files the release notes name", parent="general-purpose")
    to_feed(c, lv, "code")
    out["live_row"] = c.wait(f"[...({live_box('main')}?.querySelectorAll('[data-testid=session-map-row-text]') || [])].map((r) => r.textContent)"
                             f".find((x) => x.startsWith('made up: List what the shop repo')) || ''", 20)
    back_to_map(c)
    out["map_helpers"] = c.js(f"{qa('[data-map-box^=\"made-up:\"]')}.length")
    return out


TODOS = [{"content": "Read basket.py", "status": "completed"},
         {"content": "Fix the discount order", "status": "in_progress", "activeForm": "Fixing the discount order"},
         {"content": "Run the basket suite", "status": "pending"}]


def plan(c, rig, lv, sent) -> dict:
    lv.state("main", plan=TODOS)  # 3.6.0.23 PV: the plan is main's row field (agent_observe.py); the `todos` frame is gone
    link = t("map-lit-plan")
    out = {"plan_line": c.wait(f"{link}?.textContent", 15)}
    press(c, link)
    rows = f"{FD}?.dataset.filter === 'plan' && [...{FD}.querySelectorAll('[data-testid=map-feed-plan-row]')].map((r) => [r.dataset.status, r.textContent])"
    try:
        out["plan_rows"] = c.wait(rows, 10)
    except TimeoutError:
        raise TimeoutError(f"the plan in the drawer: filter {c.js(f'{FD}?.dataset.filter')!r}, it says {c.js(f'{FD}?.innerText.slice(0, 200)')!r}")
    back_to_map(c)
    return out


def to_feed(c, lv, bid: str) -> None:
    """4 · Live's Feed set to the box `bid` by a click on Live's drawing (R57), the step-in card closed again."""
    c.js("document.activeElement?.blur(); 1")
    key(c, "4")
    open_feed(c, lv.sid)
    click_live_box(c, bid)
    close_card(c)


def pick_feed(c, bid: str) -> None:
    """The Feed's Show picker set to the box `bid` (the hover card a pointer leaves over Live's boxes covers no picker)."""
    sel = "[data-part=live] [data-testid=map-feed-filter]"
    c.wait(f"[...(document.querySelector('{sel}')?.options || [])].some((o) => o.value === '{bid}')", 15)
    choose(c, sel, bid)


def back_to_map(c) -> None:
    c.js("document.activeElement?.blur(); 1")
    key(c, "3")
    c.wait(f"{VIEW} === 'map' && !!{t('map-topline')}", 20)
