"""tests.helpers.studio_agents_fleet -- the Fleet fold in Agents (Halo 3.3.16.0 R2: a machine's agents in Agents) in
headless Chrome on the driver base, over a scratch home (this harness alone, no session) with one drafted fleet mission
seeded in its mission store (fleet/mission_store.py: no hub, no lead, no model call). tests/test_studio_agents.py runs it:

    python -m tests.helpers.studio_agents_fleet fleet   ?mode=fleet lands on Agents -> Live with the fleet scope on
                                                        (this machine's node and box) and Fleet's line once; the scope
                                                        switch and F on the canvas; the Attention chip on every view,
                                                        its panel closed on load, opened by the chip and closed by A;
                                                        Live's inspector at a glance with nothing picked, a machine's
                                                        summary when its node is clicked (Specs one page), Back; the
                                                        mission is a row of Runs' list ("+" menu) and opens Runs'
                                                        Mission panel on it

The last stdout line is a JSON object of what it saw (exit 2: no Chrome)."""
from __future__ import annotations

import sys
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.chrome_driver import Driver  # noqa: E402
from tests.helpers.studio_agents import key, open_page  # noqa: E402

VIEW = "document.querySelector('[data-testid=\"agents\"]')?.dataset.view"
MAP = "document.querySelector('[data-testid=\"roles-live-map\"]')"
NOTE = "document.querySelector('[data-testid=\"agents-team-note\"]')"
CHIP = "document.querySelector('[data-testid=\"agents-attention\"]')"
PANEL = "document.querySelector('[data-testid=\"fleet-attention\"]')"
GOAL = "Chart the basket prices across the fleet"


def press(c, expr: str, until: str, timeout: int = 15):
    """Click `expr` and wait for `until`; a click that landed while the panel was still laying out is retried from the
    page (the element's own click), once."""
    c.wait(f"!!{expr}", timeout)
    c.click_on(expr)
    try:
        return c.wait(until, 4)
    except TimeoutError:
        c.js(f"{expr}?.click(); 1")
        return c.wait(until, timeout)


def fleet_door(c, page) -> dict:
    open_page(c, page, "mode=fleet")
    out = {"fleet_door": c.wait(f"{VIEW} === 'live' && {MAP}?.dataset.scope === 'fleet' && [{VIEW}, {MAP}.dataset.scope, {NOTE}?.textContent || '']", 30)}
    out["machines_drawn"] = c.wait("(() => { const m = [...document.querySelectorAll('[data-testid=\"live-machine\"]')];"
                            " return m.length && m.map((x) => [x.dataset.local || '', !!document.querySelector("
                            "`[data-testid=\"fleet-box\"][data-key=\"h:${x.dataset.harness}\"]`)]); })()", 30)
    open_page(c, page, "mode=fleet")
    c.wait(f"{MAP}?.dataset.scope === 'fleet'", 30)
    time.sleep(0.4)
    out["again"] = c.js(f"!!{NOTE}")
    return out


def scope_switch(c, page) -> dict:
    open_page(c, page, "mode=agents&view=live")
    out = {"default": c.wait(f"{MAP}?.dataset.scope", 30)}
    c.click_on("document.querySelector('[data-testid=\"live-scope-fleet\"]')")
    out["clicked"] = c.wait(f"{MAP}.dataset.scope === 'fleet' && !!document.querySelector('[data-testid=\"live-machine\"]') && 'fleet'", 10)
    c.click_on("document.querySelector('.rlm-scroll')")
    c.call("Input.dispatchKeyEvent", type="keyDown", key="F", code="KeyF", windowsVirtualKeyCode=70, modifiers=8, text="F")
    c.call("Input.dispatchKeyEvent", type="keyUp", key="F", code="KeyF", windowsVirtualKeyCode=70, modifiers=8)
    out["f_key"] = c.wait(f"{MAP}.dataset.scope === 'here' && 'here'", 10)
    out["focus_off"] = c.js("document.querySelector('.app').dataset.focus || 'off'")
    return out


def chip(c, page) -> dict:
    out = {}
    for view in ("cast", "runs", "live"):
        open_page(c, page, f"mode=agents&view={view}")
        out[view] = c.wait(f"{VIEW} === '{view}' && !!{CHIP} && [{CHIP}.dataset.count, {CHIP}.dataset.tone || '', !!{PANEL}]", 30)
    c.click_on(CHIP)
    out["chip_opened"] = c.wait(f"!!{PANEL} && {PANEL}.dataset.panel", 10)
    out["rows_match"] = c.wait(f"(document.querySelector('[data-testid=\"fleet-attn-empty\"]') || document.querySelector("
                               f"'[data-testid=\"fleet-attention-list\"]')) && +{CHIP}.dataset.count === "
                               "document.querySelectorAll('[data-testid=\"fleet-attn-row\"]').length", 15)
    c.js("document.activeElement?.blur(); document.body.focus(); 1")
    key(c, "a")
    out["a_closes"] = c.wait(f"!{PANEL} && 'closed'", 10)
    key(c, "a")
    out["a_opens"] = c.wait(f"!!{PANEL} && 'open'", 10)
    return out


def glance(c, page) -> dict:
    from tests.helpers.studio_fleet_panels import open_strip
    open_page(c, page, "mode=agents&view=live&scope=fleet")
    open_strip(c, "roles-inspector")  # a strip on load (one thing open per section); its chevron opens it
    body = "document.querySelector('[data-testid=\"live-inspector\"]')"
    out = {"none": c.wait(f"{body}?.dataset.pick === 'none' && !!document.querySelector('[data-testid=\"live-glance\"]') && "
                          "[...document.querySelectorAll('[data-testid=\"live-glance-lines\"] dt')].map((d) => d.textContent)", 30)}
    out["machine"] = press(c, "document.querySelector('[data-testid=\"live-machine\"]')", f"{body}.dataset.pick === 'machine' && document.querySelector('[data-testid=\"machine-summary\"]') && "
                            "[!!document.querySelector('[data-testid=\"fleet-person\"]'), [...document.querySelectorAll('[data-testid^=\"machine-block-\"]')]"
                            ".map((b) => b.dataset.testid)]", 15)
    out["specs"] = press(c, "document.querySelector('[data-testid=\"machine-edit-specs\"]')", "!!document.querySelector('[data-testid=\"machine-page\"]') && !!document.querySelector('[data-testid=\"fleet-who-input\"]')"
                          " && !document.querySelector('[data-testid=\"machine-summary\"]') && 'page'", 15)
    out["back"] = press(c, "document.querySelector('[data-testid=\"machine-page-back\"]')", "!!document.querySelector('[data-testid=\"machine-summary\"]') && 'summary'", 10)
    out["cleared"] = press(c, "document.querySelector('[data-testid=\"live-inspector-back\"]')", f"{body}.dataset.pick === 'none' && 'none'", 10)
    return out


def mission_row(c, page, mid: str) -> dict:
    from tests.helpers.studio_header_menus import open_plus
    open_page(c, page, "mode=agents&view=runs")
    c.wait(f"{VIEW} === 'runs'", 30)
    row = f"document.querySelector('[data-testid=\"orchestra-menu-mission\"][data-mission=\"{mid}\"]')"
    open_plus(c)
    out = {"row": c.wait(f"!!{row} && {row}.title", 20)}
    c.click_on(row)
    det = "document.querySelector('[data-testid=\"fleet-mission-detail\"]')"
    out["opened"] = c.wait(f"{VIEW} === 'runs' && !!{det} && !!document.querySelector('[data-panel=\"fleet-mission\"]') && "
                           f"document.querySelector('.fmi-goal')?.textContent", 30)
    open_page(c, page, f"mode=fleet&mission={mid}")
    out["mission_door"] = c.wait(f"{VIEW} === 'runs' && document.querySelector('.fmi-goal')?.textContent", 30)
    return out


class AgentsFleetDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_studio import serve
        from halo_harness.config.paths import bridge_home
        from halo_harness.fleet import mission as M, mission_store as S
        from halo_harness.studio.server import url_for
        state = bridge_home()
        state.mkdir(parents=True, exist_ok=True)
        mid = M.new_id()
        S.create(state, M.new_doc(mid=mid, goal=GOAL, hub={"id": "here", "name": "you@studio"}, by="you@studio"))
        srv, _url = serve(state)
        base = url_for(srv)

        def page(query: str) -> str:
            return base.replace("/#t=", f"/?{query}&feed=off&tour=off#t=")
        self.out["mission"] = mid
        try:
            args = (c, page)
            yield ((fleet_door, args), (scope_switch, args), (chip, args), (glance, args), (mission_row, (c, page, mid)))
        finally:
            srv.shutdown()
            srv.server_close()


if __name__ == "__main__":
    sys.exit(AgentsFleetDriver(sys.argv[1:]).main())
