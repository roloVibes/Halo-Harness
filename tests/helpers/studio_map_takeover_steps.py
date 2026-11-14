"""tests.helpers.studio_map_takeover_steps -- the first steps of the R4b driver (tests/helpers/studio_map_takeover.py):
facts, clocks, talk, depth, plan. Each waits for the value it reads, right after the action that causes it (a pulse
shows for a few seconds); no fixed sleep is a pass condition."""
from __future__ import annotations

import time

from tests.helpers.chrome_driver import emulate_motion
from tests.helpers.session_rig import wait_for
from tests.helpers.studio_map_live_more import press
from tests.helpers.studio_map_live_steps import VIEW, box, click_box, q, qa, t

FD = "document.querySelector('[data-testid=map-feed]')"
HEAD = f"{FD}?.querySelector('[data-testid=map-feed-head]')"
WHY = "Auto: the strongest reasoning model under the lineup's budget"


def fact(name: str) -> str:
    return f"({HEAD}?.querySelector('[data-testid={name}]')?.textContent || '')"


def facts(c, rig, lv, sent) -> dict:
    emulate_motion(c, "no-preference")
    lv.state("reviewer", model_reason=WHY, tokens_in=1234, tokens_out=56, cost_usd=0.0123, since=time.time() - 75)
    c.go(rig.url("agents", "&view=map&map=shop"))
    c.wait(f"{VIEW} === 'map'", 40)
    c.wait(f"{t('map-lit-head')}?.textContent.startsWith('A session is running on this map')", 40)
    c.wait(f"{box('check')}?.dataset.state === 'working'", 30)
    click_box(c, "check")
    c.wait(f"{FD}?.dataset.filter === 'check' && {HEAD}?.dataset.agent === 'r3v1e2w0'", 15)
    out = {"head": c.wait(f"{fact('map-fact-why')} && [{fact('map-fact-who')}, {fact('map-fact-model')}, {fact('map-fact-why')}, {fact('map-fact-uses')}, "
                          f"{fact('map-fact-tokens')}, {fact('map-fact-cost')}, {fact('map-fact-ran')}]", 15)}
    click_box(c, "research")  # Pause / Resume on a real agent of the session (the researcher), so its socket answers
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
    click_box(c, "check")
    c.wait(f"{FD}?.dataset.filter === 'check'", 10)
    lv.state("reviewer", state="failed")
    c.wait(f"!!{FD}.querySelector('[data-testid=map-feed-dismiss]')", 15)
    press(c, f"{FD}.querySelector('[data-testid=map-feed-dismiss]')")
    out["dismissed"] = c.wait(f"!{FD}.querySelector('[data-testid=map-feed-dismiss]') && {HEAD}?.dataset.state === 'failed' && 'gone'", 10)
    lv.state("reviewer", state="running")
    c.wait(f"{box('check')}?.dataset.state === 'working'", 15)
    return out


def clocks(c, rig, lv, sent) -> dict:
    out: dict = {}
    lv.tool("implementer", "Bash", "call-clk", current="pytest -q")
    doing = f"{box('code')}?.querySelector('[data-testid=map-lit-doing]')"
    out["tool"] = c.wait(f"{doing}?.dataset.clock && /Bash pytest -q · \\d+ s/.test({doing}.textContent) && {doing}.textContent", 20)
    lv.state("reviewer", state="waiting")
    lv.ask("reviewer", "permission_request", {"id": "perm-clk", "name": "Bash", "input": {"command": "git push origin feature/basket"}})
    wd = f"{box('check')}?.querySelector('[data-testid=map-lit-doing]')"
    out["waiting"] = c.wait(f"/waiting on you · \\d+ s/.test({wd}?.textContent || '') && {wd}.textContent", 20)
    out["outlined"] = c.wait(f"{qa('[data-testid=map-world] [data-map-box][data-waited]')}.map((b) => b.dataset.mapBox).join(',')", 15)
    link = t("map-lit-wait")
    out["link"] = c.wait(f"{link}?.textContent", 15)
    click_box(c, "code")  # the drawer on another box first: the link must move it
    c.wait(f"{FD}?.dataset.filter === 'code'", 10)
    c.js(f"{q('[data-testid=map-scroll]')}.scrollLeft = 0; {q('[data-testid=map-scroll]')}.scrollTop = 0; 1")
    press(c, link)
    out["opened"] = c.wait(f"{FD}?.dataset.filter === 'check' && document.activeElement === {box('check')} && 'check'", 10)
    out["in_view"] = c.js(f"(() => {{ const s = {q('[data-testid=map-scroll]')}.getBoundingClientRect(), b = {box('check')}.getBoundingClientRect();"
                          " return b.left >= s.left - 1 && b.right <= s.right + 1 && b.top >= s.top - 1 && b.bottom <= s.bottom + 1; })()")
    lv.state("reviewer", state="running")
    lv.result("implementer", "call-clk", "3 passed")
    return out


def talk(c, rig, lv, sent) -> dict:
    pulse = f"{q('[data-testid=map-talk][data-from=code][data-to=check]')}"
    out: dict = {"lines_before": c.js(f"{qa('[data-testid=map-line]')}.length")}
    lv.talk("implementer", "reviewer", "Please look at the tax order in basket.py before you pass it", "task", mid="tk-r4b-1")
    out["pulse"] = c.wait(f"!!{pulse} && [{pulse}.getAttribute('d').startsWith('M'), getComputedStyle({pulse}).display, "
                          f"{q('[data-testid=map-talk-label][data-from=code]')}?.textContent, {box('code')}.dataset.talk, {box('check')}.dataset.talk]", 10)
    out["lines"] = c.js(f"{qa('[data-testid=map-line]')}.length")
    out["gone"] = c.wait(f"!{pulse} && !{box('code')}.dataset.talk && 'gone'", 20)
    emulate_motion(c, "reduce")
    lv.talk("implementer", "reviewer", "And the rounding rule too", "task", mid="tk-r4b-2")
    out["reduced"] = c.wait(f"!!{pulse} && [getComputedStyle({pulse}).display, {box('code')}.dataset.talk, {box('check')}.dataset.talk]", 10)
    emulate_motion(c, "no-preference")
    return out


def depth(c, rig, lv, sent) -> dict:
    out: dict = {}
    lv.spawn("n3st3d01", "file-counter", "general-purpose", "or:mock/glm-5-coder", "Count the files the release notes name", parent="general-purpose")
    under = q('[data-map-box="made-up:h3lp3r01"] [data-testid=map-helper-under]')
    out["under"] = c.wait(f"{under}?.textContent", 20)
    nested = q('[data-map-box="made-up:n3st3d01"]')
    out["drawn"] = c.js(f"!!{nested}")
    c.js(f"{under}.scrollIntoView({{block: 'nearest', inline: 'nearest'}}); 1")
    press(c, under)
    row = f"{FD}?.querySelector('[data-testid=map-feed-under-row][data-aid=n3st3d01]')"
    out["listed"] = c.wait(f"{FD}?.dataset.filter === 'under:h3lp3r01' && {row}?.textContent", 10)
    press(c, row)
    out["filtered"] = c.wait(f"{FD}?.dataset.filter === 'agent:n3st3d01' && {FD}.dataset.filter", 10)
    return out


TODOS = [{"content": "Read basket.py", "status": "completed"},
         {"content": "Fix the discount order", "status": "in_progress", "activeForm": "Fixing the discount order"},
         {"content": "Run the basket suite", "status": "pending"}]


def plan(c, rig, lv, sent) -> dict:
    lv.frame("main", "todos", {"todos": TODOS})
    link = t("map-lit-plan")
    out = {"plan_line": c.wait(f"{link}?.textContent", 15)}
    press(c, link)
    rows = f"{FD}?.dataset.filter === 'plan' && [...{FD}.querySelectorAll('[data-testid=map-feed-plan-row]')].map((r) => [r.dataset.status, r.textContent])"
    try:
        out["plan_rows"] = c.wait(rows, 10)
    except TimeoutError:
        raise TimeoutError(f"the plan in the drawer: filter {c.js(f'{FD}?.dataset.filter')!r}, it says {c.js(f'{FD}?.innerText.slice(0, 200)')!r}")
    return out
