"""tests.helpers.studio_live_plan_more -- parts 3 and 4 of tests/helpers/studio_live_plan.py (Halo 3.3.18.0 "The living
canvas"): what each agent waits on, the waiting path and Live's one sentence; a hand-off on a line; the three zoom levels,
the pointer anchor, and Fit with thirty agents. Every wait reads the VALUE it asserts; the pointer is the real one."""
from __future__ import annotations

import time

Q = "document.querySelector"
QA = "document.querySelectorAll"
WORLD = f"{Q}('[data-testid=\"roles-live-world\"]')"
NARR = f"{Q}('[data-testid=\"live-narration\"]')"


def node(aid: str) -> str:
    return f"{Q}('[data-testid=\"roles-live-node\"][data-agent$=\"{aid}\"]')"


def waits_of(aid: str) -> str:
    return f"{node(aid)}?.querySelector('[data-testid=\"roles-live-waits\"]')"


def waits(c, rig) -> dict:
    lv, out = rig.plan_live, {}
    impl = rig.agent("Implement").get("agent_id")
    out["main_waits"] = c.wait(f"{waits_of('main')}?.dataset.wait === 'agent' && {waits_of('main')}.textContent", 20)
    out["model_waits"] = c.wait(f"{waits_of(impl)}?.dataset.wait === 'model' && {waits_of(impl)}.textContent", 20)
    lv.tool("scribe", "Bash", "call_t1", current="pytest -q")
    out["tool_waits"] = c.wait(f"{waits_of('scr1')}?.dataset.wait === 'tool' && {waits_of('scr1')}.textContent", 20)
    out["tool_sentence"] = c.wait(f"{NARR}?.dataset.wait === 'tool' && {NARR}.dataset.text", 20)
    secs = f"{Q}('[data-testid=\"live-wait-secs\"]')?.textContent"
    out["secs_a"] = c.wait(secs, 10)
    time.sleep(2.6)
    out["secs_b"], out["tool_sentence_later"] = c.js(secs), c.js(f"{NARR}.dataset.text")
    out["path"] = c.js(f"[...{QA}('[data-testid=\"roles-live-node\"][data-path]')].map((n) => n.dataset.agent.split('|').pop()).sort()")
    lv.say("media", "Writing the summary of the clip now.")
    out["nothing_waits"] = c.wait(f"{waits_of('sqm1')}?.dataset.wait === 'nothing' && {waits_of('sqm1')}.textContent", 10)
    lv.state("listener", state="waiting")
    lv.ask("listener", data={"id": "perm-9", "name": "Bash", "input": {"command": "git push origin feature/basket"}})
    out["you_waits"] = c.wait(f"{waits_of('sqh1')}?.dataset.wait === 'you' && {waits_of('sqh1')}.textContent", 20)
    out["ask_sentence"] = c.wait(f"{NARR}?.dataset.wait === 'you' && {NARR}.dataset.text", 20)
    out["ask_leaf"] = c.js(f"{NARR}.dataset.leaf")
    out["ask_path"] = c.wait(f"(() => {{ const p = [...{QA}('[data-testid=\"roles-live-node\"][data-path]')].map((n) => n.dataset.agent.split('|').pop()).sort();"
                             " return p.includes('sqh1') && p; })()", 10)
    c.click_on(f"{Q}('[data-testid=\"live-level-near\"]')")  # a big drawing: the agent starts out of view
    c.wait(f"{WORLD}.dataset.level === 'near'", 10)
    c.js("(() => { const s = document.querySelector('.rlm-scroll'); s.scrollLeft = 0; s.scrollTop = 0; return 1; })()")
    seen = (f"(() => {{ const s = {Q}('.rlm-scroll').getBoundingClientRect(), n = {node('sqh1')}.getBoundingClientRect();"
            " return n.left >= s.left - 1 && n.right <= s.right + 1 && n.top >= s.top - 1 && n.bottom <= s.bottom + 1; })()")
    out["seen_before"] = c.js(seen)
    c.click_on(NARR, 0.2, 0.5)
    out["centred"] = c.wait(f"{seen} && 'in view'", 10)
    c.click_on(f"{Q}('[data-testid=\"live-level-mid\"]')")
    c.wait(f"{WORLD}.dataset.level === 'mid'", 10)
    return out


def handoff(c, rig) -> dict:
    lv = rig.plan_live
    when = f"{Q}('[data-testid=\"live-plan-when\"][data-to=\"tier:read\"]')"
    out = {"when_before": c.wait(f"{when}?.textContent", 10)}
    lv.talk("main", "researcher", "Check what the pricing notes say about tax", why="task")
    t0 = time.time()
    out["handoff"] = c.wait(f"{when}?.dataset.handoff === 'task' && {when}.textContent", 15)
    out["back_to_when"] = c.wait(f"!{when}.dataset.handoff && {when}.textContent", 20)
    out["handoff_s"] = round(time.time() - t0, 1)
    from tests.helpers.studio_hover_read import away, hover_card
    away(c)
    time.sleep(0.5)
    c.js(f"{when}.scrollIntoView({{block: 'center', inline: 'center'}}); 1")
    time.sleep(0.3)
    got = hover_card(c, when, "when", "plan-line:tier:read", 0.3, 0.5)
    out["hover_rows"] = len((got or {}).get("rows") or [])
    away(c)
    c.click_on(when, 0.3, 0.5)
    out["conv"] = c.wait(f"{Q}('[data-testid=\"section-tab\"][aria-selected=\"true\"]')?.dataset.tabId === 'session' && "
                         f"{Q}('[data-testid=\"conv-pair\"][data-on]')?.textContent", 20)
    c.go("about:blank")  # the same address with a #t= fragment is a fragment hop: a real load back to Agents
    c.go(rig.url("agents", "&view=live&scope=here"))
    c.wait(f"{Q}('[data-testid=\"section-tab\"][aria-selected=\"true\"]')?.dataset.tabId === 'agents' && {WORLD}?.dataset.plan === 'on' && "
           f"{QA}('[data-testid=\"roles-live-node\"]').length >= 6", 40)
    return out


def _wheel(c, x: float, y: float, dy: int) -> None:
    c.call("Input.dispatchMouseEvent", type="mouseWheel", x=x, y=y, deltaX=0, deltaY=dy, modifiers=2)


def levels(c, rig) -> dict:
    lv, out = rig.plan_live, {}
    c.wait(f"!!{NARR} && !!{Q}('[data-testid=\"live-level-far\"]') && {Q}('.feed-cell')?.dataset.status === 'open'", 20)  # the feed hears the thought
    lv.think("researcher", "th1", "Weighing whether the discount applies before tax.", end=True)
    time.sleep(1.0)  # the bar has its final width (the sentence came under it)
    for lvl in ("far", "near", "mid"):
        btn = f"{Q}('[data-testid=\"live-level-{lvl}\"]')"
        c.click_on(btn)
        try:
            c.wait(f"{WORLD}.dataset.level === '{lvl}'", 4)
        except TimeoutError:  # a click that landed while the bar was still settling: the element's own click
            c.js(f"{btn}.click(); 1")
        out[lvl] = c.wait(f"{WORLD}.dataset.level === '{lvl}' && [+{WORLD}.dataset.zoom, {QA}('[data-testid=\"roles-live-node\"]').length, "
                          f"{QA}('[data-testid=\"live-block\"]').length, {QA}('[data-testid=\"roles-live-near\"]').length]", 10)
        if lvl == "near":
            out["thought"] = c.wait(f"[...{QA}('[data-testid=\"roles-live-thought\"]')].map((t) => t.textContent).find((t) => t.includes('Weighing')) || ''", 10)
    x, y, w, h = c.rect(f"{Q}('[data-testid=\"agents\"] .rlm-scroll')")
    px, py = x + w * 0.5, y + h * 0.5
    under = (f"(() => {{ const e = document.elementFromPoint({px}, {py})?.closest('[data-testid=\"roles-live-node\"], [data-testid=\"live-block-bar\"]');"
             " return e ? (e.dataset.agent ? 'node:' + e.dataset.agent : 'block:' + e.dataset.block) : ''; })()")
    out["anchor_before"] = c.js(under)
    out["wheel_from"] = c.js(f"+{WORLD}.dataset.zoom")
    c.mouse("mouseMoved", px, py)
    for _ in range(4):
        _wheel(c, px, py, -120)
        time.sleep(0.25)
    out["wheel_zoom"] = c.js(f"+{WORLD}.dataset.zoom")
    try:
        out["wheel_level"] = c.wait(f"{WORLD}.dataset.level === 'near' && 'near'", 10)
    except TimeoutError:
        out["wheel_level"] = c.js(f"{WORLD}.dataset.level")
    time.sleep(0.4)
    out["anchor_after"] = c.js(under)
    c.click_on(f"{Q}('[data-testid=\"live-level-mid\"]')")
    c.wait(f"{WORLD}.dataset.level === 'mid'", 10)
    return out


def thirty(c, rig) -> dict:
    from tests.helpers.studio_live_plan import OVERLAP
    lv, now = rig.plan_live, time.time()
    for i in range(30):
        lv.rows[f"ck{i:02d}"] = {"agent_id": f"ck{i:02d}", "parent": "main", "name": f"checker-{i + 1}", "role": "checker", "bio": "checker",
                                 "lineup": "halo-dev-cycle", "model": "or:mock/cheap-fast", "kind": "member", "task": f"Check doc {i + 1}",
                                 "since": now - 5, "state": "running", "turns": 1, "cost_usd": 0.001, "current": "thinking", "last_text": "",
                                 "transcript": None, "spawn": {"step": "main#20", "description": f"Check doc {i + 1}", "lead": ""}}
    lv.refresh()
    c.wait(f"+{Q}('[data-testid=\"roles-live-map\"]').dataset.nodes >= 36", 30)
    c.click_on(f"{Q}('[data-testid=\"roles-live-fit\"]')")
    out = {"fit": c.wait(f"{WORLD}.dataset.level === 'far' && [+{WORLD}.dataset.zoom, {QA}('[data-testid=\"roles-live-node\"]').length]", 10)}
    time.sleep(0.4)
    out["readable"] = c.js(f"[...{QA}('[data-testid=\"live-block-bar\"] .pb-title, [data-testid=\"live-block-bar\"] .pb-counts')]"
                           f".map((e) => Math.round(parseFloat(getComputedStyle(e).fontSize) * +{WORLD}.dataset.zoom * 10) / 10)")
    out["inside"] = c.js("(() => { const s = document.querySelector('.rlm-scroll'); return s.scrollWidth <= s.clientWidth + 1 && s.scrollHeight <= s.clientHeight + 1; })()")
    out["far_overlap"] = c.js(OVERLAP)
    out["none_block"] = c.js(f"{Q}('[data-testid=\"live-block\"][data-block=\"none\"]')?.dataset.count")
    return out


MORE_STEPS = (waits, handoff, levels, thirty)
