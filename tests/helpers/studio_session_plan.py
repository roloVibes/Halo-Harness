"""tests.helpers.studio_session_plan -- 3.6.0.23 PV, the plan view in Session's Feed head, in the live scene of
tests/helpers/studio_session_live.py (headless Chrome, the Linux VM): the objective's row is there at the first draw
and holds still while an objective goes and comes; a plan written through the real tree (agent/agent_observe.py, the
TodoWrite events the loop sends) opens the checklist once, the one move; a change of states keeps its height; a click
on the chip folds it, the fold survives a reload. Measured by the Timeline's top (`.slv-strip`)."""
from __future__ import annotations

import time
from types import SimpleNamespace as NS

OBJ = "document.querySelector('[data-testid=\"session-feed-objective\"]')"
CHIP = "document.querySelector('[data-testid=\"session-plan-chip\"]')"
LIST = "document.querySelector('[data-testid=\"session-plan-list\"]')"
WORDS = f"({OBJ}?.querySelector('[data-testid=\"session-objective-words\"]')?.textContent || '')"
TOP = "Math.round(document.querySelector('.slv-strip').getBoundingClientRect().top * 10) / 10"
STEPS = ["Read basket.py", "Fix the discount order", "Run the basket suite"]


def _todos(states: list) -> list:
    return [{"content": s, "status": st, "activeForm": f"{'Fixing the discount order' if i == 1 else 'Doing: ' + s}"}
            for i, (s, st) in enumerate(zip(STEPS, states))]


def write_plan(rig, call: str, states: list) -> None:
    """A successful TodoWrite of the rig's real main, as its loop reports it to the tree (tool_use_ready, tool_result)."""
    tree = rig.session._agent_tree
    tree.observe("main", NS(kind="tool_use_ready", data={"id": call, "name": "TodoWrite", "input": {"todos": _todos(states)}}))
    tree.observe("main", NS(kind="tool_result", data={"id": call, "ok": True, "summary": "Todos updated"}))


def _h(c) -> float:
    return c.js(f"Math.round(({LIST}?.getBoundingClientRect().height || 0) * 10) / 10")


def first(c) -> dict:
    """At the page's first draw: the row, its chip (no plan yet), no list, and its top and height."""
    return {"plan_first": {"row": c.js(f"!!{OBJ}"), "chip": c.js(f"{CHIP}?.textContent || ''"), "list": c.js(f"!!{LIST}"),
                           "words": c.js(WORDS), "h": c.js(f"Math.round({OBJ}?.getBoundingClientRect().height || 0)")}}


def plan_view(c, rig, lv) -> dict:
    out: dict = {}
    tops = [c.js(TOP)]
    lv.state("main", objective="")
    c.wait(f"!!{OBJ}?.querySelector('[data-testid=\"session-objective-none\"]')", 10)
    tops.append(c.js(TOP))
    lv.state("main", objective="Fix the discount order in basket.py")
    c.wait(f"{WORDS} === 'Fix the discount order in basket.py'", 10)
    tops.append(c.js(TOP))
    write_plan(rig, "pv-1", ["completed", "in_progress", "pending"])
    c.wait(f"{CHIP}?.textContent === 'Plan 1 of 3' && {LIST}?.querySelectorAll('li').length === 3", 15)
    time.sleep(0.3)
    tops.append(c.js(TOP))
    heights = [_h(c)]
    out["plan_hover"] = c.js(f"{CHIP}.title")
    write_plan(rig, "pv-2", ["completed", "completed", "in_progress"])
    c.wait(f"{CHIP}?.textContent === 'Plan 2 of 3'", 15)
    time.sleep(0.3)
    tops.append(c.js(TOP))
    heights.append(_h(c))
    out["plan_rows"] = c.js(f"[...{LIST}.querySelectorAll('li')].map((l) => [l.dataset.status, "
                            "l.querySelector('.mpf-plan-state').textContent, l.querySelector('.mpf-plan-words').textContent])")
    c.click_on(CHIP)
    c.wait(f"!{LIST} && {CHIP}.getAttribute('aria-expanded') === 'false'", 10)
    tops.append(c.js(TOP))
    c.go(rig.url("session"))
    try:
        c.wait(f"{CHIP}?.textContent === 'Plan 2 of 3'", 40)
    except TimeoutError:
        pass
    time.sleep(0.5)
    out["plan_reload"] = {"chip": c.js(f"{CHIP}?.textContent || ''"), "expanded": c.js(f"{CHIP}?.getAttribute('aria-expanded')"),
                          "list": c.js(f"!!{LIST}"), "words": c.js(WORDS)}
    c.click_on(CHIP)
    try:
        c.wait(f"!!{LIST}", 10)
    except TimeoutError:
        pass
    out["plan_unfold"] = c.js(f"!!{LIST} && {CHIP}.getAttribute('aria-expanded') === 'true'")
    out["plan_tops"], out["plan_heights"] = tops, heights
    return out
