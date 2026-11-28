"""tests.helpers.studio_session_plan -- 3.6.0.23 PV, the plan view of Session's Feed, in the live scene of
tests/helpers/studio_session_live.py (headless Chrome, the Linux VM). After the first CI run (the coordinator's
ruling): the objective and the plan chip sit in the Feed panel's TITLE BAR from the first draw; the Feed's head and
the Timeline's top (`.slv-strip`) do not move with no objective, a long one (an ellipsis in the bar, its hover whole)
or a plan arriving (the list closed); a click on the chip opens the list (the one move, the objective whole at its
top), a change of states keeps its height, the fold survives a reload, a click closes it."""
from __future__ import annotations

import time
from types import SimpleNamespace as NS

FEED = "document.querySelector('[data-testid=\"session-live\"]')"
BAR = f"{FEED}?.querySelector('.panel-bar')"
OBJ = f"{BAR}?.querySelector('[data-testid=\"session-feed-objective\"]')"
LINE = f"{OBJ}?.querySelector('.slv-objective-line')"
CHIP = f"{BAR}?.querySelector('[data-testid=\"session-plan-chip\"]')"
LIST = "document.querySelector('[data-testid=\"session-plan-list\"]')"
OPEN_OBJ = "(document.querySelector('[data-testid=\"session-plan-objective-words\"]')?.textContent || '')"
WORDS = f"({OBJ}?.querySelector('[data-testid=\"session-objective-words\"]')?.textContent || '')"
TOP = "Math.round(document.querySelector('.slv-strip').getBoundingClientRect().top * 10) / 10"
HEAD = "Math.round(document.querySelector('.slv-head').getBoundingClientRect().height * 10) / 10"
BAR_H = f"Math.round(({BAR}?.getBoundingClientRect().height || 0) * 10) / 10"
STEPS = ["Read basket.py", "Fix the discount order", "Run the basket suite"]
# The last step's activeForm wraps where its content does not, so its turn from "to do" to "doing" keeps the list's
# height only through the twin (PlanList.tsx).
LONG_NOW = ("Running the basket suite with the discount order fixed, then reading every failure it prints and writing down "
            "what each one says about the basket")
LONG_OBJ = "Ship the basket discount fix today: reorder the discounts in basket.py, add a test for each coupon and update the notes."
FORM = {0: "Doing: Read basket.py", 1: "Fixing the discount order", 2: LONG_NOW}


def _todos(states: list) -> list:
    return [{"content": s, "status": st, "activeForm": FORM[i]} for i, (s, st) in enumerate(zip(STEPS, states))]


def write_plan(rig, call: str, states: list) -> None:
    """A successful TodoWrite of the rig's real main, as its loop reports it to the tree (tool_use_ready, tool_result)."""
    tree = rig.session._agent_tree
    tree.observe("main", NS(kind="tool_use_ready", data={"id": call, "name": "TodoWrite", "input": {"todos": _todos(states)}}))
    tree.observe("main", NS(kind="tool_result", data={"id": call, "ok": True, "summary": "Todos updated"}))


def _h(c) -> float:
    return c.js(f"Math.round(({LIST}?.getBoundingClientRect().height || 0) * 10) / 10")


def _place(c) -> list:
    """Where the Feed's lines start: the Timeline's top, the head's height, the title bar's height."""
    return [c.js(TOP), c.js(HEAD), c.js(BAR_H)]


def first(c) -> dict:
    """At the page's first draw: the objective and the chip (no plan yet) in the Feed's title bar, no list."""
    return {"plan_first": {"bar": c.js(f"!!{OBJ}"), "chip": c.js(f"{CHIP}?.textContent || ''"), "list": c.js(f"!!{LIST}"),
                           "words": c.js(WORDS), "in_head": c.js("!!document.querySelector('.slv-head [data-testid=\"session-feed-objective\"]')"),
                           "chip_h": c.js(f"Math.round({CHIP}?.getBoundingClientRect().height || 0)")}}


def _reload(c, rig, expanded: str) -> dict:
    c.go(rig.url("session"))
    try:
        c.wait(f"{CHIP}?.textContent === 'Plan 2 of 3' && {CHIP}.getAttribute('aria-expanded') === {expanded!r}", 40)
    except TimeoutError:
        pass
    time.sleep(0.5)
    return {"chip": c.js(f"{CHIP}?.textContent || ''"), "expanded": c.js(f"{CHIP}?.getAttribute('aria-expanded')"), "list": c.js(f"!!{LIST}")}


def plan_view(c, rig, lv) -> dict:
    out: dict = {}
    places = [_place(c)]
    lv.state("main", objective="")
    c.wait(f"!!{OBJ}?.querySelector('[data-testid=\"session-objective-none\"]')", 10)
    places.append(_place(c))
    lv.state("main", objective=LONG_OBJ)
    c.wait(f"{WORDS} === {LONG_OBJ!r}", 10)
    places.append(_place(c))
    out["plan_long_objective"] = c.js(f"(() => {{ const l = {LINE}; return {{ellipsis: l.scrollWidth > l.clientWidth, "
                                      "hover: l.title, ends: getComputedStyle(l).textOverflow}; })()")
    write_plan(rig, "pv-1", ["completed", "in_progress", "pending"])
    c.wait(f"{CHIP}?.textContent === 'Plan 1 of 3'", 15)
    time.sleep(0.3)
    places.append(_place(c))
    out["plan_arrived"] = {"list": c.js(f"!!{LIST}"), "expanded": c.js(f"{CHIP}.getAttribute('aria-expanded')"),
                           "gap": c.js(f"(() => {{ const r = {CHIP}.getBoundingClientRect(), n = {OBJ}.nextElementSibling?.getBoundingClientRect(), "
                                       f"p = {LINE}.getBoundingClientRect(); return Math.min(r.left - p.right, n ? n.left - r.right : 99); }})()")}
    out["plan_hover"] = c.js(f"{CHIP}.title")
    c.click_on(CHIP)
    c.wait(f"{LIST}?.querySelectorAll('li').length === 3", 10)
    time.sleep(0.3)
    opened = [c.js(TOP)]
    heights = [_h(c)]
    write_plan(rig, "pv-2", ["completed", "completed", "in_progress"])
    c.wait(f"{CHIP}?.textContent === 'Plan 2 of 3'", 15)
    time.sleep(0.3)
    opened.append(c.js(TOP))
    heights.append(_h(c))
    out["plan_now_wraps"] = c.js(f"(() => {{ const w = [...{LIST}.querySelectorAll('.mpf-plan-words')].map((e) => "
                                 "e.getBoundingClientRect().height); return w[2] > w[0]; })()")
    out["plan_rows"] = c.js(f"[...{LIST}.querySelectorAll('li')].map((l) => [l.dataset.status, "
                            "l.querySelector('.mpf-plan-state').textContent, l.querySelector('.mpf-plan-words').textContent])")
    # the plan through the real tree brings main's row back with the rig's own objective: a long one again, now open
    lv.state("main", objective=LONG_OBJ)
    try:
        c.wait(f"{OPEN_OBJ} === {LONG_OBJ!r}", 10)
    except TimeoutError:
        pass
    out["plan_open_objective"] = {"words": c.js(OPEN_OBJ), "wraps": c.js(
        "document.querySelector('[data-testid=\"session-plan-objective-words\"]')?.getClientRects().length > 1")}
    out["plan_reload_open"] = _reload(c, rig, "true")
    c.click_on(CHIP)
    try:
        c.wait(f"!{LIST} && {CHIP}.getAttribute('aria-expanded') === 'false'", 10)
    except TimeoutError:
        pass
    time.sleep(0.3)
    out["plan_closed"] = {"list": c.js(f"!!{LIST}"), "place": _place(c)}
    out["plan_reload_closed"] = _reload(c, rig, "false")
    out["plan_places"], out["plan_opened"], out["plan_heights"] = places, opened, heights
    return out
