"""tests.helpers.studio_panels_menu -- "Quiet Studio" round R2 (Halo 3.3.2.0): panels and layout leave the
rail. Real clicks and keys in headless Chrome on the driver base, over capture_studio's seeded home (a lineup
active); no provider request, no model call.

    python -m tests.helpers.studio_panels_menu

`menu`: Roles' "+" lists its six panels, each "focus"; ArrowDown on the button opens it on the first row,
ArrowDown / End move, Escape closes it and gives the button the focus; a panel collapsed to a strip reads
"bring back" with the strip badge, Enter on its row opens it again, and the "custom layout" badge shows.
`arrange`: a fresh Roles layout, the palette's Reset layout disabled with its words; Alt+Left moves the
Inspector, the palette's Arrange panels puts every panel back in its default box (the toast says so).
`reset`: the "..." menu's Reset layout clears the saved key, the badge goes, its rows then disabled with words.
`moving`: "How panels move" opens the section help on its Moving panels part; the ? reaches it too.
`fleet`: the "+" adds the optional Tree panel ("add", then "focus"), the strips read "bring back"; Orchestra's
"+" has its RUNS group with New run; the rail holds the sections only in both widths; Setup has no "+",
no "..." and no badge.
The last stdout line is the JSON of what it saw (exit 2: no Chrome)."""
from __future__ import annotations

import shutil
import sys
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.chrome_driver import Driver  # noqa: E402
from tests.helpers.studio_header_menus import PLUS_MENU, close_menus, more, open_plus, plus, plus_rows  # noqa: E402
from tests.helpers.studio_packs_steps import CUR, mod_key, q, qa  # noqa: E402
from tests.helpers.studio_quiet import RAIL_EXTRA  # noqa: E402

WS = "document.querySelector('.workspace[data-section=\"roles\"]')"
CELLS = f"""Object.fromEntries([...{WS}.querySelectorAll('.ws-cell')].map((c) => {{ const r = c.getBoundingClientRect();
  return [c.dataset.panel, [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)]]; }}))"""
ACTIVE = "(document.activeElement?.dataset.panel || document.activeElement?.dataset.testid || '')"
BADGE = q("[data-testid=layout-badge]")
TOASTS = "(document.querySelector('.toasts')?.textContent || '')"
SAVED = "localStorage.getItem('halo.studio.layout.roles')"


def _url(ctx, query: str) -> str:
    return f"{ctx['base']}?{query}&feed=off&open=all#{ctx['frag']}"  # 3.3.2.0 R3: every panel open (tests/helpers/studio_full.py)


def load(c, ctx, query: str, title: str) -> None:
    c.go("about:blank")  # the same address again would be a fragment hop, not a load
    c.go(_url(ctx, query))
    c.wait(f"{CUR}.startsWith('{title}')", 40)


def arrow(c, key: str, vk: int) -> None:
    mod_key(c, key, vk, 0, key)


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
    """Ctrl+K, `text` typed: [label, hint, aria-disabled] of the selected entry; the palette stays open."""
    mod_key(c, "KeyK", 75, 2, "k")
    c.wait(f"!!{q('[data-testid=palette] input')} && document.activeElement === {q('[data-testid=palette] input')}", 10)
    c.type_text(text)
    time.sleep(0.3)
    return c.js(f"(() => {{ const o = {q('[data-testid=palette] [role=option][aria-selected=true]')}; return o && "
                f"[o.querySelector('.palette-label').textContent, o.querySelector('.palette-hint')?.textContent || '', o.getAttribute('aria-disabled')]; }})()")


def menu(c, url, ctx) -> dict:
    load(c, ctx, "mode=roles&tour=off&view=workspace", "Roles")
    c.wait(f"{WS} && {WS}.querySelectorAll('.ws-cell').length === 6", 40)
    out = {"default": settle(c, CELLS), "badge_fresh": c.js(f"!!{BADGE}")}
    out["rows"] = plus_rows(c)
    out["groups"] = c.js(f"{qa('[data-testid=panels-menu] .hdr-menu-name')}.map((e) => e.textContent)")
    close_menus(c)
    c.js(f"{q('[data-testid=panels-add]')}.focus(); 1")
    arrow(c, "ArrowDown", 40)
    out["kbd_open"] = c.wait(f"!!{PLUS_MENU} && {ACTIVE}", 5)
    arrow(c, "ArrowDown", 40)
    out["kbd_down"] = c.js(ACTIVE)
    arrow(c, "End", 35)
    out["kbd_end"] = c.js(ACTIVE)
    c.key("Escape")
    out["kbd_esc"] = c.wait(f"!{PLUS_MENU} && {ACTIVE}", 5)
    btn = q('[data-panel="roles-problems"] [data-testid=panel-menu-btn]')
    c.click_on(btn)
    c.wait(f"!!{q('[data-testid=panel-menu]')}", 5)
    c.click_on(q("[data-testid=panel-menu] [data-item=collapse]"))
    c.wait(f"{q('[data-panel=roles-problems] .panel')}.dataset.collapsed === 'true'", 5)
    out["badge_custom"] = c.wait(f"{BADGE}?.textContent", 5)
    out["rows_strip"] = plus_rows(c)
    c.js(f"{q('[data-testid=panels-menu-item][data-panel=roles-problems]')}.focus(); 1")
    enter(c)
    out["brought_back"] = c.wait(f"!{PLUS_MENU} && !{q('[data-panel=roles-problems] .panel')}.dataset.collapsed && 'open'", 5)
    return out


def arrange(c, url, ctx) -> dict:
    c.js("localStorage.removeItem('halo.studio.layout.roles'); 1")
    load(c, ctx, "mode=roles&tour=off&view=workspace&page=2", "Roles")
    c.wait(f"{WS} && {WS}.querySelectorAll('.ws-cell').length === 6", 40)
    out = {"default": settle(c, CELLS), "pal_reset_fresh": palette(c, "Reset layout")}
    c.key("Escape")
    c.js(f"{q('[data-panel=roles-inspector] .panel')}.focus(); 1")
    for _ in range(3):
        mod_key(c, "ArrowLeft", 37, 1, "ArrowLeft")
        time.sleep(0.1)
    out["moved"] = settle(c, CELLS)
    out["saved_moved"] = bool(c.js(SAVED))
    out["pal_arrange"] = palette(c, "Arrange panels")
    c.key("Enter")
    out["arrange_toast"] = c.wait(f"{TOASTS}.includes('Roles panels arranged') && 'arranged'", 10)
    out["arranged"] = settle(c, CELLS)
    return out


def reset(c, url, ctx) -> dict:
    out = {"badge_before": c.js(f"{BADGE}?.textContent || ''")}
    out["reset_ran"] = more(c, "layout-reset")
    out["reset_toast"] = c.wait(f"{TOASTS}.includes('Roles layout reset') && 'reset'", 10)
    out["after"] = [c.js(f"!!{BADGE}"), c.js(SAVED)]
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
    c.click_on(q(".rail [data-testid=section-tab][data-tab-id=fleet]"))
    c.wait(f"{CUR}.startsWith('Fleet')", 15)
    out["fleet_rows"] = plus_rows(c)
    close_menus(c)
    plus(c, "fleet-tree")
    out["tree"] = c.wait(f"!!{q('[data-testid=fleet-tree] [data-testid=fleet-tree-list]')}", 20)
    out["fleet_rows_after"] = settle(c, "1") and plus_rows(c)
    close_menus(c)
    out["rail_icons"] = c.js(RAIL_EXTRA)
    c.click_on(q("[data-testid=rail-toggle]"))
    c.wait(f"{q('.app')}.dataset.rail === 'open'", 5)
    out["rail_open"] = c.js(RAIL_EXTRA)
    out["rail_open_w"] = c.js(f"Math.round({q('.rail')}.getBoundingClientRect().width)")
    c.click_on(q("[data-testid=rail-toggle]"))
    c.click_on(q(".rail [data-testid=section-tab][data-tab-id=orchestra]"))
    c.wait(f"{CUR}.startsWith('Orchestra')", 15)
    open_plus(c)
    out["orch_groups"] = c.js(f"{qa('[data-testid=panels-menu] .hdr-menu-name')}.map((e) => e.textContent)")
    out["orch_new_run"] = c.js(f"!!{q('[data-testid=panels-menu] [data-testid=orchestra-new-run]')}")
    close_menus(c)
    load(c, ctx, "mode=setup&tour=off", "Setup")
    time.sleep(1.0)
    out["setup"] = c.js("['panels-add', 'section-more', 'layout-badge'].map((t) => !!document.querySelector(`[data-testid=${t}]`))")
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
