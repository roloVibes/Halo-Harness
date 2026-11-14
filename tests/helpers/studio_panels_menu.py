"""tests.helpers.studio_panels_menu -- "Quiet Studio" round R2 (Halo 3.3.2.0): panels and layout leave the rail;
3.6.0.0 R0a: the header's "+" became the view bar (one named button per drawer and tab, lib/workspace/ViewBar.tsx).
Real clicks and keys in headless Chrome on the driver base, over capture_studio's seeded home (a lineup active); no
provider request, no model call.

    python -m tests.helpers.studio_panels_menu

`menu`: Agents' view bar on Cast: the Canvas with its tabs (Activity and the plan review to add), then the drawers
(Lineups, Bios on the left; Inspector, Problems, Models on the right), every one closed; a focused button and Enter
open its drawer beside the canvas, the button pressed; the panel's close puts it away again; nothing says "custom
layout".
`arrange`: a fresh layout: the palette's Reset layout disabled with its words; the palette's "Show panel: Inspector"
opens its drawer; Alt+Left on it widens it by 40 px (kept in the saved v3 record); Reset layout enabled now.
`reset`: the "..." menu's Reset layout (the toast) closes the drawers and clears the saved key; its rows then say so.
`moving`: "How panels open" opens the section help on its Moving panels part; the ? reaches it too.
`fleet`: on Agents -> Live the bar adds the optional Activity tab ("add", then shown in the canvas's place); the rail
holds the sections only in both widths; Setup and Local (paged) have no view bar, no "..." and no badge.
The last stdout line is the JSON of what it saw (exit 2: no Chrome)."""
from __future__ import annotations

import json
import shutil
import sys
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.chrome_driver import Driver  # noqa: E402
from tests.helpers.studio_header_menus import bar_rows, button, close_menus, more, plus  # noqa: E402
from tests.helpers.studio_packs_steps import CUR, mod_key, q, qa  # noqa: E402
from tests.helpers.studio_quiet import RAIL_EXTRA  # noqa: E402

WS = q(".workspace[data-section=roles]")
DRAWERS = f"[...{WS}.querySelectorAll('.stage-drawer')].map((d) => [d.dataset.panelIn, d.dataset.side, Math.round(d.getBoundingClientRect().width)])"
ACTIVE = "(document.activeElement?.dataset.panel || document.activeElement?.dataset.testid || '')"
BADGE = q("[data-testid=layout-badge]")
TOASTS = "(document.querySelector('.toasts')?.textContent || '')"
SAVED = "JSON.parse(localStorage.getItem('halo.studio.layout.roles') || 'null')"
CANVAS = q(".workspace[data-section=roles] .stage-main [data-testid=roles-graph]")


def _url(ctx, query: str) -> str:
    return f"{ctx['base']}?{query}&feed=off#{ctx['frag']}"


def load(c, ctx, query: str, title: str) -> None:
    c.go("about:blank")  # the same address again would be a fragment hop, not a load
    c.go(_url(ctx, query))
    c.wait(f"{CUR}.startsWith('{title}')", 40)


def enter(c) -> None:
    """Enter as a keyboard types it (with its text), so a focused button activates."""
    c.call("Input.dispatchKeyEvent", type="keyDown", key="Enter", code="Enter", windowsVirtualKeyCode=13, text="\r")
    c.call("Input.dispatchKeyEvent", type="keyUp", key="Enter", code="Enter", windowsVirtualKeyCode=13)


def settle(c, expr: str, timeout: float = 8):
    last, end = None, time.time() + timeout
    while time.time() < end:
        got = c.js(expr)
        if got == last:
            return got
        last = got
        time.sleep(0.3)
    return last


def palette(c, text: str) -> list:
    """Ctrl+K, `text` typed: [label, hint, aria-disabled] of the selected entry once it is the one asked for."""
    mod_key(c, "KeyK", 75, 2, "k")
    c.wait(f"!!{q('[data-testid=palette] input')} && document.activeElement === {q('[data-testid=palette] input')}", 10)
    c.type_text(text)
    sel = q("[data-testid=palette] [role=option][aria-selected=true]")
    c.wait(f"({sel}?.querySelector('.palette-label')?.textContent || '').includes({json.dumps(text.split(': ')[-1])})", 10)
    return c.js(f"(() => {{ const o = {sel}; return o && "
                f"[o.querySelector('.palette-label').textContent, o.querySelector('.palette-hint')?.textContent || '', o.getAttribute('aria-disabled')]; }})()")


def menu(c, url, ctx) -> dict:
    load(c, ctx, "mode=roles&tour=off&view=workspace", "Agents")
    c.wait(f"!!{CANVAS}", 40)
    out = {"rows": bar_rows(c), "drawers_fresh": c.js(DRAWERS), "badge_fresh": c.js(f"!!{BADGE}")}
    c.js(f"{button('roles-problems')}.focus(); 1")
    out["focus"] = c.js(ACTIVE)
    enter(c)
    c.wait(f"!!{q('.stage-drawer[data-panel-in=roles-problems] .panel-body')}", 10)
    out["opened"] = [c.js(DRAWERS), c.js(f"{button('roles-problems')}.getAttribute('aria-pressed')"),
                     c.js(f"!!{BADGE} || document.querySelector('.hud-strip').innerText.includes('layout yours')")]
    c.click_on(q("[data-panel=roles-problems] [data-testid=panel-collapse]"))
    c.wait(f"!{q('.stage-drawer[data-panel-in=roles-problems]')}", 10)
    out["closed"] = [c.js(DRAWERS), c.js(f"{button('roles-problems')}.getAttribute('aria-pressed')")]
    return out


def arrange(c, url, ctx) -> dict:
    c.js("localStorage.removeItem('halo.studio.layout.roles'); 1")
    load(c, ctx, "mode=roles&tour=off&view=workspace&page=2", "Agents")
    c.wait(f"!!{CANVAS}", 40)
    out = {"pal_reset_fresh": palette(c, "Reset layout")}
    c.key("Escape")
    out["pal_show"] = palette(c, "Show panel: Inspector")
    c.key("Enter")
    c.wait(f"!!{q('.stage-drawer[data-panel-in=roles-inspector] .panel-body')}", 10)
    before = settle(c, DRAWERS)
    c.js(f"{q('[data-panel=roles-inspector] .panel')}.focus(); 1")
    mod_key(c, "ArrowLeft", 37, 1, "ArrowLeft")  # Alt+Left on a right drawer: wider
    c.wait(f"JSON.stringify({DRAWERS}) !== {json.dumps(json.dumps(before))}", 10)
    out["widened"] = [before, settle(c, DRAWERS), c.js(SAVED)]
    out["pal_reset_now"] = palette(c, "Reset layout")
    c.key("Escape")
    return out


def reset(c, url, ctx) -> dict:
    out = {"reset_ran": more(c, "layout-reset")}
    out["reset_toast"] = c.wait(f"{TOASTS}.includes('Agents layout reset') && 'reset'", 10)
    c.wait(f"!{q('.workspace[data-section=roles] .stage-drawer')}", 10)
    out["after"] = [c.js(DRAWERS), c.js(SAVED)]
    c.click_on(q("[data-testid=section-more]"))
    c.wait(f"!!{q('[data-testid=section-more-menu]')}", 5)
    out["more_rows"] = c.js(f"{qa('[data-testid=section-more-menu] [role=menuitem]')}.map((b) => [b.dataset.testid, b.disabled, b.querySelector('.menu-word')?.textContent || ''])")
    close_menus(c)
    return out


def moving(c, url, ctx) -> dict:
    out = {"help_ran": more(c, "layout-help")}
    part = q("[data-testid=section-help] [data-testid=help-moving]")
    out["moving"] = c.wait(f"{part} && [{part}.dataset.on || '', {part}.textContent]", 10)
    c.click_on(q("[data-testid=section-help-ok]"))
    c.wait(f"!{q('[data-testid=section-help]')}", 5)
    c.click_on(q("[data-testid=section-help-btn]"))
    c.wait(f"!!{q('[data-testid=section-help-item]')}", 5)
    c.click_on(q("[data-testid=section-help-item]"))
    out["moving_from_q"] = c.wait(f"!!{part} && ({part}.dataset.on || 'plain')", 10)
    c.click_on(q("[data-testid=section-help-ok]"))
    return out


def fleet(c, url, ctx) -> dict:
    out: dict = {}
    c.click_on(q(".rail [data-testid=section-tab][data-tab-id=agents]"))
    c.wait(f"{CUR}.startsWith('Agents')", 15)
    c.click_on(q("[data-testid=agents-view-live]"))
    c.wait("document.querySelector('[data-testid=agents]')?.dataset.view === 'live'", 10)
    out["fleet_rows"] = bar_rows(c)
    plus(c, "fleet-activity")
    out["tree"] = c.wait(f"!!{q('.stage-main [data-testid=fleet-activity] [data-testid=fleet-log]')}", 20)
    out["fleet_rows_after"] = bar_rows(c)
    out["rail_icons"] = c.js(RAIL_EXTRA)
    c.click_on(q("[data-testid=rail-toggle]"))
    c.wait(f"{q('.app')}.dataset.rail === 'open'", 5)
    out["rail_open"] = c.js(RAIL_EXTRA)
    out["rail_open_w"] = c.js(f"Math.round({q('.rail')}.getBoundingClientRect().width)")
    c.click_on(q("[data-testid=rail-toggle]"))
    c.wait(f"{q('.app')}.dataset.rail !== 'open'", 5)
    for name, title in (("setup", "Setup"), ("local", "Local")):
        load(c, ctx, f"mode={name}&tour=off", title)
        c.wait("!!document.querySelector('[data-testid=setup-rail], [data-testid=local-rail-page]')", 20)
        out[name] = c.js("['.section-view:not([hidden]) [data-testid=viewbar]', '[data-testid=section-more]', '[data-testid=layout-badge]']"
                         ".map((s) => !!document.querySelector(s))")
    return out


class PanelsMenuDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_studio import seeded_home, serve
        state = seeded_home()
        srv, url = serve(state, True)
        ctx = {"state": state, "base": url.split("?", 1)[0], "frag": url.split("#", 1)[1]}
        try:
            yield tuple((fn, (c, url, ctx)) for fn in (menu, arrange, reset, moving, fleet))
        finally:
            srv.shutdown()
            srv.server_close()
            shutil.rmtree(state.parent, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(PanelsMenuDriver(sys.argv[1:]).main())
