"""tests.helpers.studio_flows -- Agents -> 2 · Workflows (Halo 3.6.0.0 R2) in headless Chrome, as a first-time user, over
tests/helpers/crew_rig.py (a scratch home, a git repo, the mock upstream for Try it, the builder's scripted model).
tests/test_studio_flows.py reads what it saw:

    first    from 1 · Agents, the 2 key: the Workflows tab, its list drawer open, the five starters, the switch's five
             names, no conversation; the empty form says how to start
    copy     a starter's click: its copy, its steps drawn; a repeat added (a loop mark drawn); a step moved up and
             back; Save: in the list tagged `not on the map`, the one line that nothing is on a map yet
    drawn    R8: the list drawer closed -> the drawing fits its wider box; a zoom by hand survives a drawer; Fit
    make     the builder: "make a review workflow ..." on a new form -> one preview: the proposal card, the agent's
             widening lines unticked, ghost steps in the form and in the drawing, a ghost row; "make it" -> the agent
             form filled in; Save there -> back here, its lines out of the preview; Apply -> the workflow file; Undo
    write    Write it for me on a saved workflow: the box filled and focused; its step line a ghost step; Discard
    try      the band said first; a test request; each step's state, the agents that ran, the checks; seen
    delete   Delete asks on the page; Keep it.     board    the old board as Board, then back

    python -m tests.helpers.studio_flows [DIR]     DIR: also save studio-workflows-tab.png and studio-workflows-try.png
No model is called beyond the mock upstream and the scripted builder."""
from __future__ import annotations

import base64
import json
import sys
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.helpers.chrome_driver import Driver  # noqa: E402
from tests.helpers.studio_agents import key  # noqa: E402
from tests.helpers.studio_crew import said, until  # noqa: E402

VIEW = "document.querySelector('[data-testid=\"agents\"]')?.dataset.view"
P = "[data-part=\"flows\"] "
SHOTS: list = []


def q(sel: str, part: str = P) -> str:
    return f"document.querySelector('{part}{sel}')"


def qa(sel: str, part: str = P) -> str:
    return f"[...document.querySelectorAll('{part}{sel}')]"


def t(name: str, part: str = P) -> str:
    return q(f'[data-testid="{name}"]', part)


def click(c, name: str, part: str = P) -> None:
    c.wait(f"!!{t(name, part)} && !{t(name, part)}.disabled", 20)
    c.js(f"{t(name, part)}.click(); 1")


def type_in(c, name: str, text: str, part: str = P) -> None:
    c.wait(f"!!{t(name, part)}", 20)
    c.js(f"{t(name, part)}.focus(); {t(name, part)}.select && {t(name, part)}.select(); 1")
    c.call("Input.insertText", text=text)


def shot(c, name: str) -> None:
    if SHOTS:
        (Path(SHOTS[0]) / name).write_bytes(base64.b64decode(c.call("Page.captureScreenshot", format="png")["data"]))


def first(c, rig) -> dict:
    c.go(rig.url("&view=crew"))
    c.wait(f"{VIEW} === 'crew' && !!document.querySelector('[data-testid=\"crew-starter\"]')", 40)
    c.js("document.activeElement?.blur(); 1")
    key(c, "2")
    out = {"view": c.wait(f"{VIEW} === 'flows' && {VIEW}", 20), "slow_ms": rig.server.slow_ms}
    c.wait(f"{qa('[data-testid=flow-starter]')}.length >= 5 && !!{t('builder-meta')}", 30)
    out["first"] = c.js(f"({{list: !!{q('.stage-drawer[data-panel-in=flow-list]')}, conversation: !!{t('builder-conversation')},"
                        f" starters: {qa('[data-testid=flow-starter]')}.map((b) => b.dataset.name), empty: {t('flow-empty')}?.innerText.split('\\n')[0],"
                        f" switch: {qa('[data-testid=agents-views] button')}.map((b) => b.innerText), dialogs: document.querySelectorAll('[role=dialog]').length}})")
    return out


def steps(c) -> list:
    return c.js(f"{qa('[data-testid=flow-step]')}.map((s) => s.dataset.name)")


def copy(c, rig) -> dict:
    c.js(f"{q('[data-testid=flow-starter][data-name=review]')}.click(); 1")
    c.wait(f"{t('flow-name')}?.value === 'my-review' && {qa('[data-testid=flow-drawn-step]')}.length === 2", 20)
    out = {"copied": [steps(c), c.js(f"{t('flow-note')}.innerText")]}
    c.js(f"{qa('[data-testid=flow-repeat-add]')}[1].click(); 1")
    out["loop"] = c.wait(f"{qa('[data-testid=flow-drawn-loop]')}.length === 1 && {q('[data-testid=flow-drawn-loop]')}.innerText", 10)
    c.js(f"{qa('[data-testid=flow-step-up]')}[1].click(); 1")
    out["moved"] = c.wait(f"{qa('[data-testid=flow-step]')}[0]?.dataset.name === 'Test' && {qa('[data-testid=flow-step]')}.map((s) => s.dataset.name)", 10)
    c.js(f"{qa('[data-testid=flow-step-down]')}[0].click(); 1")
    c.wait(f"{qa('[data-testid=flow-step]')}[0]?.dataset.name === 'Review'", 10)
    click(c, "flow-save")
    said(c, f"!!{q('[data-testid=flow-item][data-name=my-review]')} && {t('flow-note')}.innerText.startsWith('Saved my-review')", f"{t('flow-note')}?.innerText", 30)
    out["row"] = c.js(f"[{q('[data-testid=flow-item][data-name=my-review] [data-testid=flow-item-map]')}.innerText, !!{t('flow-no-map')}]")
    got = rig.api("GET", "crew/workflow/my-review")[1].get("workflow") or {}
    out["file"] = [s.get("name") for s in got.get("steps") or []] + [got.get("steps", [{}, {}])[1].get("repeat")]
    out["cost"] = c.wait(f"{t('flow-cost-line')}?.innerText.includes('a run') || {t('flow-cost-line')}?.innerText.includes('unknown') ? {t('flow-cost-line')}.innerText : ''", 20)
    shot(c, "studio-workflows-tab.png")
    return out


ZOOM = q("[data-testid=flow-drawn-scroll] [data-zoom]")
INSIDE = (f"(() => {{ const S = {t('flow-drawn-scroll')}.getBoundingClientRect(); return {qa('[data-testid=flow-drawn-step]')}.every((b) => {{"
          " const r = b.getBoundingClientRect(); return r.left >= S.left - 1 && r.right <= S.right + 1 && r.top >= S.top - 1; }); })()")


def drawn(c, rig) -> dict:
    btn = "document.querySelector('.section-view:not([hidden]) [data-testid=viewbar-btn][data-panel=\"flow-list\"]')"
    out = {"before": [c.js(f"{ZOOM}.dataset.zoom"), c.js(INSIDE)]}
    w0 = c.js(f"{t('flow-drawn-scroll')}.clientWidth")
    c.js(f"{btn}.click(); 1")
    c.wait(f"!{q('.stage-drawer[data-panel-in=flow-list]')} && {t('flow-drawn-scroll')}.clientWidth !== {w0}", 10)
    out["closed"] = until(lambda: [c.js(f"{ZOOM}.dataset.zoom"), c.js(INSIDE)], lambda v: v[1] is True, 10)
    c.js(f"{t('flow-drawn-scroll')}.dispatchEvent(new WheelEvent('wheel', {{deltaY: -120, deltaMode: 0, ctrlKey: true, bubbles: true, cancelable: true}})); 1")
    hand = c.wait(f"{ZOOM}.dataset.zoom !== {json.dumps(out['closed'][0])} && {ZOOM}.dataset.zoom", 10)
    c.js(f"{btn}.click(); 1")
    c.wait(f"!!{q('.stage-drawer[data-panel-in=flow-list] .panel-body')}", 10)
    out["hand"] = [hand, until(lambda: c.js(f"{ZOOM}.dataset.zoom"), lambda z: z == hand, 3)]
    c.js(f"{q('[data-testid=flow-drawn] [data-testid=canvas-fit]')}.click(); 1")
    out["fit"] = until(lambda: [c.js(f"{ZOOM}.dataset.zoom"), c.js(INSIDE)], lambda v: v[1] is True and v[0] != hand, 10)
    return out


def make(c, rig) -> dict:
    click(c, "flow-new")
    c.wait(f"{t('flow-name')}?.value.startsWith('new-workflow')", 10)
    type_in(c, "flow-name", "review-loop")
    from tests.test_builder_workflows import ASK
    type_in(c, "builder-input", ASK)
    click(c, "builder-send")
    c.wait(f"!!{t('builder-preview')} && {qa('[data-testid=flow-ghost-step]')}.length === 2", 30)
    out = {"ticks": c.js(f"{qa('[data-testid=builder-tick]')}.map((x) => [x.closest('[data-target]').dataset.target, x.dataset.widen, x.checked])"),
           "card": c.js(f"{q('[data-testid=builder-card]')}?.dataset.name"),
           "ghosts": [c.js(f"{qa('[data-testid=flow-ghost]')}.map((g) => g.innerText.split('\\n')[0])"), c.js(f"{qa('[data-testid=flow-drawn-step][data-ghost]')}.length")]}
    click(c, "builder-make-it")
    crew = '[data-part="crew"] '
    out["made"] = c.wait(f"{VIEW} === 'crew' && {t('crew-name', crew)}?.value === 'my-reviewer' && [{t('crew-note', crew)}.innerText, {t('crew-use-bash', crew)}.getAttribute('aria-checked')]", 20)
    click(c, "crew-save", crew)
    c.wait(f"{VIEW} === 'flows'", 20)
    lines = qa('[data-testid=builder-line][data-target="agent:my-reviewer"] input')
    out["unticked"] = c.js(f"{lines}.map((x) => x.checked)")
    click(c, "builder-apply")
    c.wait(f"!!{t('builder-receipt')} && !!{q('[data-testid=flow-item][data-name=review-loop]')} && {qa('[data-testid=flow-step]')}.length === 2", 20)
    got = rig.api("GET", "crew/workflow/review-loop")[1]
    out["applied"] = [[s["name"] for s in got["workflow"]["steps"]], got["missing"], rig.api("GET", "crew/agent/my-reviewer")[1]["agent"]["uses"]]
    click(c, "builder-undo")
    c.wait(f"!{t('builder-receipt')} && !{q('[data-testid=flow-item][data-name=review-loop]')}", 20)
    out["undone"] = rig.api("GET", "crew/workflow/review-loop")[0]
    return out


def write(c, rig) -> dict:
    c.js(f"{q('[data-testid=flow-item][data-name=my-review]')}.click(); 1")
    c.wait(f"{t('flow-name')}?.value === 'my-review'", 20)
    click(c, "flow-write")
    out = {"prefill": c.wait(f"document.activeElement === {t('builder-input')} && {t('builder-input')}.value", 10)}
    click(c, "builder-send")
    out["ghost"] = c.wait(f"{qa('[data-testid=flow-ghost-step]')}.length === 1 && {qa('[data-testid=flow-drawn-step][data-ghost]')}.length === 1 && {q('[data-testid=flow-ghost-step] b')}.innerText", 30)
    click(c, "builder-discard")
    out["gone"] = c.wait(f"!{t('flow-ghost-step')} && !{q('[data-testid=flow-drawn-step][data-ghost]')}", 10)
    if c.js(f"{t('builder-toggle')}?.getAttribute('aria-expanded') === 'true'"):
        click(c, "builder-toggle")
    return out


def try_it(c, rig) -> dict:
    out = {"estimate": c.wait(f"{t('flow-try-estimate')}?.innerText.includes('It costs one run: ') && !{t('flow-try-estimate')}.innerText.includes('reading') && {t('flow-try-estimate')}.innerText", 20)}
    type_in(c, "flow-try-text", "Review the basket")
    click(c, "flow-try-send")
    c.wait(f"{t('flow-try-state')}?.textContent === 'done' || {t('flow-try-state')}?.textContent === 'failed'", 180)
    out["state"] = c.js(f"{t('flow-try-state')}.textContent")
    out["steps"] = c.js(f"{qa('[data-testid=flow-try-step]')}.map((s) => [s.dataset.n, s.dataset.state, [...s.querySelectorAll('[data-testid=flow-try-agent]')].map((a) => a.dataset.name)])")
    out["checks"] = c.js(f"{qa('[data-testid=flow-try-check]')}.length")
    out["why"] = c.js(f"{t('flow-try-stop-why')}?.innerText")
    out["total"] = c.js(f"{t('flow-try-total')}?.innerText")
    from halo_harness.crew import trial
    out["seen"] = until(lambda: [r.get("seen") for r in trial.recent(rig.state) if r.get("kind") == "workflow"], lambda v: bool(v) and all(v), 20)
    c.js(f"{t('flow-try-result')}.scrollIntoView({{block: 'center'}}); 1")
    shot(c, "studio-workflows-try.png")
    return out


def delete(c, rig) -> dict:
    click(c, "flow-delete")
    c.wait(f"!!{t('flow-delete-ask')}", 10)
    out = {"ask": c.js(f"{t('flow-delete-ask')}.innerText.split('\\n')[0]")}
    click(c, "flow-delete-no")
    out["kept"] = [c.wait(f"!!{t('flow-savebar')}", 10), rig.api("GET", "crew/workflow/my-review")[0]]
    c.js(f"{q('[data-testid=agents-view-workflows]')}.click(); 1")
    out["board"] = c.wait(f"{VIEW} === 'workflows' && !document.querySelector('[data-part=workflows]').hidden && 'board'", 20)
    c.js("document.querySelector('[data-part=\"workflows\"] [data-testid=agents-view-flows], [data-testid=agents-bar] [data-testid=agents-view-flows]').click(); 1")
    out["back"] = c.wait(f"{VIEW} === 'flows' && {t('flow-name')}?.value", 20)
    return out


class FlowsDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}
    width, height = 1500, 900

    @contextmanager
    def session(self, c):
        from tests.helpers.crew_rig import CrewRig
        SHOTS[:] = self.argv[:1]
        with CrewRig() as rig:
            rig.studio()
            yield tuple((fn, (c, rig)) for fn in (first, copy, drawn, make, write, try_it, delete))


if __name__ == "__main__":
    sys.exit(FlowsDriver(sys.argv[1:]).main())
