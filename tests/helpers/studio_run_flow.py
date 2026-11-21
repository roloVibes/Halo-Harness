"""tests.helpers.studio_run_flow -- Run it (Halo 3.6.0.6 P, the owner's point 31: "pack workflows should be launchable
from any studio view that can see them") in headless Chrome, over tests/helpers/crew_rig.py with the pack that ships with
Halo (doc-review) installed and enabled and a map of his whose box holds the pack's workflow. Every press is a real one
(the DevTools input domain). Each Run starts a real headless session from the rig's Studio (POST crew/run), which runs
the workflow by name on the mock upstream; the driver reads each session's record for the receipt, then ends them the
way Studio's own stop does (sessions_new_api.end_started). tests/test_studio_run_flow.py reads what it saw:

    flows     Agents -> 2 · Workflows, the pack's workflow open: Run it beside Try it; its form in place, the line, Run;
              the receipt; Watch it in Live -> Agents -> 4 · Live draws "workflow doc-review--review-docs"
    goal      the Map's Run a goal drawer: the head Workflows lists it with its tag; Run it there
    manager   Packs -> the pack's row: its crew workflow with Run it, under the pack
    section   its section (opened from the Pack Manager's link): the row drawn by Studio above the pack's page; Run it
    map       on the map of his, the workflow box's card: Run it
    palette   Ctrl+K, Run a workflow, Enter: the list; a pick opens the form docked in the view; Run
    viewonly  a tab a link opened: each view's Run -> 403 and the one toast with Make this tab yours (no second message);
              the toast's button pressed once: the same Run in Workflows answers 202
The last stdout line is a JSON object of what it saw (exit 2: no Chrome).

    python -m tests.helpers.studio_run_flow
"""
from __future__ import annotations

import sys
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.helpers.chrome_driver import Driver  # noqa: E402

FLOW = "doc-review--review-docs"
MAP = "run-flow-map"
Q = "document.querySelector"
SIDS: list = []


def q(sel: str) -> str:
    return f"{Q}({sel!r})"


def ctrl_k(c) -> None:
    for kind in ("keyDown", "keyUp"):
        c.call("Input.dispatchKeyEvent", type=kind, key="k", code="KeyK", windowsVirtualKeyCode=75, modifiers=2)


# Where Try it was at its FIRST draw, against its form's top (a scroll is not a move): taken the moment React puts it in
# the page, so a later move (an answer that lands after the form, a control added beside it) is seen whenever it comes.
FIRST = """(() => { window.__tryFirst = {}; new MutationObserver(() => {
  const s = document.querySelector('[data-testid=flow-try-send]'), f = s && s.closest('[data-testid=flow-form]');
  if (s && f && window.__tryFirst[f.dataset.name] == null) window.__tryFirst[f.dataset.name] = s.getBoundingClientRect().top - f.getBoundingClientRect().top;
}).observe(document, {childList: true, subtree: true}); })();"""

STATE = ("[...document.querySelectorAll('[data-testid=run-flow-form]')].map((f) => [f.dataset.name, f.querySelector('textarea').value, f.querySelector('[data-testid=run-flow-run]').disabled, f.getBoundingClientRect().top, document.activeElement?.outerHTML.slice(0, 80)])")


def type_task(c, form: str, task: str) -> None:
    """The task box has the keys once the form opens (RunFlow.tsx focuses it); pressed first only when it has not."""
    box = q(form + " [data-testid=run-flow-task]")
    for _ in range(2):
        if not c.js(f"document.activeElement === {box}"):
            c.click_on(box)
        c.call("Input.insertText", text=task)
        if c.js(f"{box}.value.trim().length > 0"):
            return
    raise TimeoutError(f"the task did not go in: {c.js(STATE)}")


TWO_FRAMES = "new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(() => r(1))))"
# null when the control's middle is the top-most thing at its place; else where to wheel (the middle of its nearest
# scroller) and by how much to bring it wholly inside that scroller
SIGHT = """((b) => { const r = b.getBoundingClientRect(), e = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
  if (e === b || b.contains(e)) return null;
  let s = b.parentElement;
  while (s && !(s.scrollHeight > s.clientHeight + 1 && /auto|scroll/.test(getComputedStyle(s).overflowY))) s = s.parentElement;
  if (!s) return [0, 0, 0];
  const q = s.getBoundingClientRect();
  return [q.left + q.width / 2, q.top + q.height / 2, r.bottom > q.bottom - 12 ? r.bottom - q.bottom + 12 : (r.top < q.top + 12 ? r.top - q.top - 12 : 0)]; })"""


def into_sight(c, sel: str) -> None:
    """As a person does before pressing a control that is out of sight: the wheel, over the scroller that holds it. On the
    Map an opened box with the Run it form can be taller than the drawing's room (on Windows, at 1280 x 800, the room was
    250 px and the box 508: the Run button's middle lay under the line below the drawing, 4 runs of 7). A scroll made by
    a script is not what a person does, and the Map did not keep it."""
    for _ in range(8):
        got = c.js(f"{SIGHT}({q(sel)})")
        if got is None or not got[2]:
            return
        c.call("Input.dispatchMouseEvent", type="mouseWheel", x=got[0], y=got[1], deltaX=0, deltaY=got[2])
        c.js(TWO_FRAMES)


def run_in(c, where: str, form: str, task: str = "Review notes.md") -> dict:
    """Press Run it in `where` (a selector holding the button), type the task in `form`, press Run: what it saw."""
    btn = f"{where} [data-testid=run-flow-open]"
    c.wait(f"!!{q(btn)} && !{q(btn)}.disabled", 40)
    c.js(f"{q(btn)}.scrollIntoView({{block: 'center'}}); 1")  # in sight first, as a person scrolls to it: then nothing may move
    top0 = c.js(f"{q(btn)}.getBoundingClientRect().top")
    n0 = c.js("(window.__w || []).filter((w) => w.startsWith('POST crew/run ')).length")
    c.click_on(q(btn))
    try:
        c.wait(f"!!{q(form + ' [data-testid=run-flow-task]')}", 20)
    except TimeoutError:
        hit = c.js(f"(() => {{ const r = {q(btn)}.getBoundingClientRect(); const e = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);"
                   " return [r.top, r.left, innerHeight, e ? e.outerHTML.slice(0, 160) : null, document.querySelectorAll('[data-testid=run-flow-form]').length]; })()")
        raise TimeoutError(f"no form after Run it in {where}: the button's rect, the window, what is under it, forms: {hit}")
    out = {"name": c.js(f"{q(form + ' [data-testid=run-flow-name]')}.textContent"),
           "line": c.js(f"{q(form + ' [data-testid=run-flow-line]')}.textContent"),
           "buttons": c.js(f"[...{q(form)}.querySelectorAll('button')].map((b) => b.textContent)"),
           "button_held": c.js(f"{q(btn)}.getBoundingClientRect().top") == top0,
           "rows": c.js(f"{q(form + ' [data-testid=run-flow-task]')}.rows || 0"),
           "task_height": c.js(f"{q(form + ' [data-testid=run-flow-task]')}.getBoundingClientRect().height")}
    type_task(c, form, task)
    h0 = c.js(f"{q(form)}.getBoundingClientRect().height")
    into_sight(c, form + " [data-testid=run-flow-run]")
    c.click_on(q(form + " [data-testid=run-flow-run]"))
    try:
        c.wait(f"(window.__w || []).filter((w) => w.startsWith('POST crew/run ')).length > {n0}", 30)
    except TimeoutError:
        run = q(form + " [data-testid=run-flow-run]")  # what the press met: the button's rect, the window, what lies on it
        hit = c.js(f"(() => {{ const b = {run}; if (!b) return null; const r = b.getBoundingClientRect();"
                   " const e = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);"
                   " return [Math.round(r.left), Math.round(r.top), Math.round(r.right), Math.round(r.bottom), innerWidth, innerHeight,"
                   " b.disabled, e === b || b.contains(e), e ? e.outerHTML.slice(0, 200) : null,"
                   " (window.__w || []).slice(-6), (() => { const sc = b.closest('.mp-scroll'); if (!sc) return 'no map scroller';"
                   " const q = sc.getBoundingClientRect(), w = sc.querySelector('.mp-world-size').getBoundingClientRect(), bx = b.closest('[data-map-box]').getBoundingClientRect();"
                   " return {scrollTop: sc.scrollTop, scrollHeight: sc.scrollHeight, clientHeight: sc.clientHeight, scrollerTop: Math.round(q.top), scrollerBottom: Math.round(q.bottom),"
                   " worldSizeBottom: Math.round(w.bottom), boxTop: Math.round(bx.top), boxBottom: Math.round(bx.bottom), overflowY: getComputedStyle(sc).overflowY}; })()]; })()")
        raise TimeoutError(f"no POST crew/run after Run: {c.js(STATE)}; the Run button [l, t, r, b, window w, h, disabled, "
                           f"on top, what is on it, the last requests]: {hit}") from None
    out["posted"] = c.js("(window.__w || []).filter((w) => w.startsWith('POST crew/run ')).pop()")
    if out["posted"].endswith(" 202"):
        c.wait(f"!!{q('[data-testid=run-flow-receipt]')}", 20)
        out["receipt"] = c.js(f"{q('[data-testid=run-flow-receipt]')}.textContent")
        out["room_held"] = c.js(f"{q('[data-testid=run-flow-started]')}.getBoundingClientRect().height") >= h0 - 0.5
        out["watch"] = c.js(f"{q('[data-testid=run-flow-watch]')}.textContent")
        SIDS.append(out["receipt"].replace("Started: session ", "").rstrip("."))
    else:
        time.sleep(1.0)
        out["toast"] = c.js(f"{q('[data-testid=owner-toast]')}?.querySelector('[data-testid=owner-tab-yours]')?.textContent || ''")
        out["toasts"] = c.js("document.querySelectorAll('[data-testid=owner-toast]').length")
        out["inline_error"] = c.js(f"!!{q('[data-testid=run-flow-error]')}")
        c.click_on(q(form + " [data-testid=run-flow-cancel]"))
    return out


def flows(c, rig, own=True) -> dict:
    if own:
        c.go(rig.url(f"&view=workflows&workflow={FLOW}"))
    form = '[data-testid=flow-form][data-name="' + FLOW + '"]'
    c.wait(f"!!{q(form)}", 40)
    send = q("[data-testid=flow-try-send]")
    beside = c.js(f"!!{q('[data-testid=run-flow-open]')} && {q('[data-testid=run-flow-open]')}.parentElement === {send}.parentElement")
    c.js(f"{q('[data-testid=run-flow-open]')}.scrollIntoView({{block: 'center'}}); 1")
    rel = f"({send}.getBoundingClientRect().top - {q(form)}.getBoundingClientRect().top)"  # in the form: a scroll of the page is not a move
    try0 = c.js(f"(window.__tryFirst || {{}})[{FLOW!r}] ?? null")  # its first draw (FIRST), not a moment after it
    got = run_in(c, "[data-testid=flow-try]", "[data-testid=flow-try] [data-testid=run-flow-form]")
    if own:  # its band read (the owner's page reads it; a view-only tab cannot): what came after the first draw is in
        c.wait(f"!!{q('[data-testid=flow-cost-line]')} && !{q('[data-testid=flow-cost-line]')}.textContent.includes('reading the prices')", 60)
    held = c.js(f"!!{send} && {rel} === {try0} && {send}.textContent === 'Try it'")
    got["try_first"], got["try_now"] = try0, c.js(rel)
    if own and got.get("receipt"):
        c.click_on(q("[data-testid=run-flow-watch]"))
        text = "(document.querySelector('[data-section=agents]:not([hidden])')?.innerText || '')"
        end = time.monotonic() + 90
        while time.monotonic() < end and not c.js(f"{text}.includes('workflow {FLOW}')"):
            time.sleep(0.5)
        got["live"] = c.js(f"{text}.includes('workflow {FLOW}')")
        got["live_view"] = c.js("new URLSearchParams(location.search).get('view') + ' ' + (document.querySelector('[data-section=agents]:not([hidden]) [data-agents-view], [data-testid=agents-view]')?.outerHTML || '').slice(0, 120)")
        got["live_text"] = c.js(f"{text}.slice(0, 900)")
        got["groups"] = c.js("[...document.querySelectorAll('[data-testid=map-group-name]')].map((x) => x.textContent)")
    return {"beside": beside, "try_held": held, **got}


def goal(c, rig, own=True) -> dict:
    if own:
        c.go(rig.url("&view=map"))
    button = "[...document.querySelectorAll('[data-testid=map-run-goal]')].find((e) => e.offsetParent)"
    c.wait(f"!!{button}", 40)
    c.click_on(button)
    c.wait(f"!!{q('[data-testid=goal-flows]')} && !!{q('[data-testid=orchestra-workflow-pick]')}", 60)  # both lists drawn: then nothing may move
    rows = c.js("[...document.querySelectorAll('[data-testid=goal-flow]')].map((r) => [r.dataset.name, r.querySelector('[data-testid=goal-flow-tag]')?.textContent || '', r.dataset.scope])")
    head = c.js(f"{q('[data-testid=goal-flows] .cw-label')}.textContent")
    sel = f"[data-testid=goal-flow][data-name={FLOW}]".replace(FLOW, f'"{FLOW}"')
    return {"listed": rows, "head": head, "pack_select": c.js(f"!!{q('[data-testid=orchestra-workflow-pick]')}"),
            **run_in(c, sel, sel + " [data-testid=run-flow-form]")}


def manager(c, rig, own=True) -> dict:
    from tests.helpers.studio_agents import key
    if own:
        c.go(rig.url().replace("mode=agents", "mode=packs"))
    else:
        key(c, "4", alt=True)
    row = "[data-testid=pm-installed-row][data-id=doc-review] .pm-row-main"
    c.wait(f"!!{q(row)}", 40)
    c.click_on(q(row))
    sel = f'[data-testid=pm-links] [data-testid=pack-flow][data-name="{FLOW}"]'
    c.wait(f"!!{q(sel)}", 30)
    return run_in(c, sel, sel + " [data-testid=run-flow-form]")


def section(c, rig, own=True) -> dict:
    c.click_on(q("[data-testid=pm-links] [data-testid=pm-open-section]"))
    sel = f'.section-view:not([hidden]) [data-testid=pack-flows] [data-testid=pack-flow][data-name="{FLOW}"]'
    c.wait(f"!!{q(sel)}", 30)
    drawn = c.js(f"!{q(sel)}.closest('.pk-view-host') && {q(sel)}.closest('[data-testid=pack-flows]').dataset.where.startsWith('section:')")
    return {"drawn_by_studio": drawn, **run_in(c, sel, sel + " [data-testid=run-flow-form]")}


def map_box(c, rig, own=True) -> dict:
    from tests.helpers.studio_agents import key
    if own:
        c.go(rig.url("&view=map"))
    else:  # in the Workflows tab of this tab: 3 is Agents -> 3 · Map
        c.js("document.activeElement?.blur(); 1")
        key(c, "3")
    c.wait(f"!!{q('[data-testid=map-switcher]')}", 40)
    c.js(f"(() => {{ const s = {q('[data-testid=map-switcher]')}; const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;"
         f" set.call(s, '{MAP}'); s.dispatchEvent(new Event('change', {{bubbles: true}})); }})(); 1")
    box = "[data-testid=map-world] [data-map-box=rev]"
    c.wait(f"!!{q(box)}", 30)
    c.click_on(q(box), 0.5, 0.25)
    sel = "[data-testid=map-run-flow][data-box=rev]"
    c.wait(f"!!{q(sel)}", 30)
    return run_in(c, sel, sel + " [data-testid=run-flow-form]")


def palette(c, rig, own=True) -> dict:
    c.js("document.activeElement?.blur(); 1")
    ctrl_k(c)
    c.wait(f"!!{q('[data-testid=palette] input')}", 20)
    c.call("Input.insertText", text="Run a workflow")
    c.wait("[...document.querySelectorAll('.palette-item .palette-label')].some((x) => x.textContent === 'Run a workflow')", 20)
    # pressed, not Enter: the pointer left over the palette by the last press may have moved its selection
    c.click_on("[...document.querySelectorAll('.palette-item')].find((x) => x.querySelector('.palette-label').textContent === 'Run a workflow')")
    item = f"[...document.querySelectorAll('.palette-item')].find((x) => x.querySelector('.palette-label').textContent === '{FLOW}')"
    c.wait(f"!!{item}", 20)
    listed = c.js(f"{item}.querySelector('.palette-hint')?.textContent || ''")
    c.click_on(item)
    return {"listed_tag": listed, **_dock(c)}


EARLY: dict = {}
LABELS = "[...document.querySelectorAll('.palette-item .palette-label')].map((x) => x.textContent)"


def early(c, rig) -> dict:
    """Run a workflow picked BEFORE the workflows are read (Ctrl+K at once on a slow first read: the release gate of
    3.6.0.6, the macOS runner): the list says it is reading, then lists them. Studio's answers are held 3 s for it."""
    rig.server.slow_ms = 3000
    try:
        c.go("about:blank")
        c.go(rig.url("&view=live"))  # a view that does not read the workflows by itself
        c.wait(f"!!{q('[data-testid=agents]')}", 60)
        c.js("document.activeElement?.blur(); 1")
        ctrl_k(c)
        c.wait(f"!!{q('[data-testid=palette] input')}", 20)
        c.call("Input.insertText", text="Run a workflow")
        c.wait(f"{LABELS}.includes('Run a workflow')", 20)
        c.click_on("[...document.querySelectorAll('.palette-item')].find((x) => x.querySelector('.palette-label').textContent === 'Run a workflow')")
        c.wait(f"{LABELS}.length > 0 && !{LABELS}.includes('Run a workflow')", 10)
        EARLY["first"] = c.js(LABELS)
        c.wait(f"{LABELS}.includes('{FLOW}')", 30)
        EARLY["then"] = c.js(LABELS)
    finally:
        rig.server.slow_ms = 0
        for _ in range(2):
            c.key("Escape")
    return {"early": EARLY}


def _dock(c) -> dict:
    form = "[data-testid=run-flow-dock] [data-testid=run-flow-form]"
    c.wait(f"!!{q(form)}", 20)
    out = {"line": c.js(f"{q(form + ' [data-testid=run-flow-line]')}.textContent"),
           "name": c.js(f"{q(form + ' [data-testid=run-flow-name]')}.textContent")}
    n0 = c.js("(window.__w || []).filter((w) => w.startsWith('POST crew/run ')).length")
    type_task(c, form, "Review notes.md")
    c.click_on(q(form + " [data-testid=run-flow-run]"))
    try:
        c.wait(f"(window.__w || []).filter((w) => w.startsWith('POST crew/run ')).length > {n0}", 30)
    except TimeoutError:
        raise TimeoutError(f"no POST crew/run after Run: {c.js(STATE)}") from None
    out["posted"] = c.js("(window.__w || []).filter((w) => w.startsWith('POST crew/run ')).pop()")
    if out["posted"].endswith(" 202"):
        out["receipt"] = c.wait(f"{q('[data-testid=run-flow-dock] [data-testid=run-flow-receipt]')}?.textContent", 20)
        SIDS.append(str(out["receipt"]).replace("Started: session ", "").rstrip("."))
    else:
        time.sleep(1.0)
        out["toast"] = c.js(f"{q('[data-testid=owner-toast]')}?.querySelector('[data-testid=owner-tab-yours]')?.textContent || ''")
        out["inline_error"] = c.js(f"!!{q('[data-testid=run-flow-error]')}")
        c.click_on(q(form + " [data-testid=run-flow-cancel]"))
    return out


OWN: dict = {}
VIEWONLY: dict = {}


def into(out: dict, key: str, fn, *args) -> None:
    """One view's pass, kept as soon as it returns (a later step that fails keeps what the earlier ones saw)."""
    out[key] = fn(*args)


def own(c, rig) -> dict:
    for key, fn in (("flows", flows), ("goal", goal), ("map", map_box), ("manager", manager), ("section", section), ("palette", palette)):
        into(OWN, key, fn, c, rig)
    return {"own": OWN}


def viewonly(c, rig) -> dict:
    """A tab a link opened: every view's Run is refused with the one toast; one press of its button, then Run works."""
    from tests.helpers.studio_owner_tab import by_link, landed
    by_link(c, rig)
    VIEWONLY["row"] = c.js(f"!!{q('[data-testid=owner-tab-row]')}")
    for key, fn in (("flows", flows), ("map", map_box), ("goal", goal), ("manager", manager), ("section", section), ("palette", palette)):
        into(VIEWONLY, key, fn, c, rig, False)
    c.js("window.__before = 1; 1")
    c.click_on(f"{q('[data-testid=owner-toast]')}.querySelector('[data-testid=owner-tab-yours]')")
    landed(c)
    into(VIEWONLY, "after_press", flows, c, rig, False)
    return {"viewonly": VIEWONLY}


def ended(rig) -> dict:
    """Each session's record holds the receipt; Studio's own stop ends them all (closing.py)."""
    from halo_harness.bg_run import pid_alive
    from halo_harness.studio import sessions_new_api as N
    from tests.helpers.session_rig import wait_for
    receipt = f"crew workflow {FLOW} · ran on the step runner · done"

    def log(sid):
        found = list((rig.state / "sessions").rglob(f"{sid}.jsonl"))
        return found[0].read_text("utf-8", "replace") if found else ""
    got = {sid: bool(wait_for(lambda s=sid: receipt in log(s) or None, 120, 0.5)) for sid in SIDS}
    pids = [r["pid"] for r in N.started(rig.state)]
    gone = N.end_started(wait_s=30.0)
    alive = [p for p in pids if wait_for(lambda p=p: (not pid_alive(p)) or None, 30, 0.2) is None]
    return {"sids": list(SIDS), "receipts": got, "ended": len(gone), "survivors": alive}


def errors(c) -> dict:
    from tests.helpers.studio_session import page_errors
    return {"page_errors": page_errors(c)}


class RunFlowDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}
    width, height = 1500, 900

    @contextmanager
    def session(self, c):
        from halo_harness.crew import store
        from tests.helpers.crew_rig import CrewRig
        from tests.helpers.studio_owner_tab import WATCH
        from tests.helpers.studio_session import collect_page_errors
        with CrewRig() as rig:
            rig.with_pack().studio()
            raw = {"format": "map/1", "name": MAP, "boxes": [{"id": "rev", "workflow": FLOW}],
                   "lines": [{"from": "main", "to": "rev", "when": {"says": ["review"]}}]}
            store.write_text(store.path_for("map", MAP, state_dir=rig.state), store.dump(raw))
            collect_page_errors(c)
            c.call("Page.addScriptToEvaluateOnNewDocument", source=WATCH)
            c.call("Page.addScriptToEvaluateOnNewDocument", source=FIRST)
            try:
                self.out.update(early=EARLY, own=OWN, viewonly=VIEWONLY)
                yield ((early, (c, rig)), (own, (c, rig)), (viewonly, (c, rig)), (errors, (c,)), (ended, (rig,)))
            finally:
                from halo_harness.studio import sessions_new_api as N
                N.end_started(wait_s=10.0)


if __name__ == "__main__":
    sys.exit(RunFlowDriver(sys.argv[1:]).main())
