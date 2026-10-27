"""tests.helpers.studio_quiet_panels -- "Quiet Studio" round R3 (Halo 3.3.2.0): quieter panels, one thing per
section, a density setting. Real clicks and keys in headless Chrome at 1280 x 800 over capture_studio's seeded
home (plus tools/design_demo's project so Design draws its panels); no provider request, no model call.

    python -m tests.helpers.studio_quiet_panels [--shots DIR]

defaults: each of the seven panel sections (Session, Team, Roles, Fleet, Design, Orchestra, Packs) on a fresh
browser (localStorage cleared, `view=workspace`): the primary panel's box over the stage, the other panels'
state (strips at the foot), the focused ornament (one `.panel.focused`, one set of HUD brackets, one mono data
line), no about line anywhere; with --shots a PNG per section.
strip: in Fleet a strip opens in the column right of the map (the map gives up its columns, nothing overlaps), a
click moves the ornament to it, its ? opens its help on the about line, collapsing it gives the rows back.
saved: Alt+Shift+Up on the focused map saves a layout of its own; a reload keeps it (the badge); the header's
"..." Reset layout returns to the quiet default.
density: the header toggle switches `data-density` and the measured tokens (`--pad`, a panel's gutter, its
title line, the body text), remembered across a reload; the palette's "Density: comfortable" switches it back.
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
from tests.helpers.studio_header_menus import more  # noqa: E402
from tests.helpers.studio_packs_steps import CUR, mod_key, q, qa  # noqa: E402

PRIMARY = [("session", "Session", "session-live"), ("team", "Team", "team-board"), ("roles", "Roles", "roles-graph"),
           ("fleet", "Fleet", "fleet-map"), ("design", "Design", "design-artboards"), ("orchestra", "Orchestra", "graph"),
           ("packs", "Packs", "pm-installed")]
RECT = "((e) => { const r = e.getBoundingClientRect(); return [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)]; })"
COVER = ("((p) => { const a = RECT(document.querySelector('[data-panel=\"' + p + '\"] .panel')), s = RECT(document.querySelector('.stage'));"
         " return Math.round(1000 * a[2] * a[3] / (s[2] * s[3])) / 1000; })").replace("RECT", RECT)
STATE = ("[...document.querySelectorAll('.section-view:not([hidden]) .ws-cell, .workspace .ws-cell')].filter((c) => c.checkVisibility())"
         ".map((c) => [c.dataset.panel, c.querySelector('.panel').dataset.collapsed === 'true' ? 'strip' : c.dataset.floating ? 'float' : 'open'])")
ORNAMENT = (f"[{qa('.panel.focused')}.map((p) => p.closest('.ws-cell').dataset.panel), {qa('.panel[data-focused]')}.length, "
            f"{qa('.hud-brackets')}.length, {qa('.panel-data')}.length, {qa('[data-testid=panel-about], .panel-about')}.length]")


def _url(ctx, query: str) -> str:
    return f"{ctx['base']}?{query}&feed=off&tour=off#{ctx['frag']}"


def load(c, ctx, sid: str, title: str, extra: str = "") -> None:
    c.go("about:blank")  # the same address again would be a fragment hop, not a load
    c.go(_url(ctx, f"mode={sid}{extra}"))
    c.wait(f"{CUR}.startsWith('{title}')", 40)


def fresh(c, ctx, sid: str, title: str, extra: str = "") -> None:
    """A fresh browser: nothing remembered, then the section loaded on its own."""
    load(c, ctx, sid, title, extra)
    c.js("localStorage.clear(); 1")
    load(c, ctx, sid, title, extra)


def defaults(c, url, ctx) -> dict:
    out: dict = {"cover": {}, "state": {}, "ornament": {}}
    for sid, title, prim in PRIMARY:
        fresh(c, ctx, sid, title, "&view=workspace")
        c.wait(f"!!{q(f'[data-panel={prim}] .panel')}", 40)
        time.sleep(1.2)  # the workspace measured and laid out
        out["cover"][sid] = c.js(f"{COVER}('{prim}')")
        out["state"][sid] = c.js(STATE)
        out["ornament"][sid] = c.js(ORNAMENT)
        if ctx.get("shots"):
            c.shot(Path(ctx["shots"]) / f"q3_{sid}.png", 1280, 800, 1)
    out["stage"] = c.js(f"{RECT}({q('.stage')})")
    return out


def strip(c, url, ctx) -> dict:
    fresh(c, ctx, "fleet", "Fleet", "&view=workspace")
    mp = q("[data-panel=fleet-map] .panel")
    c.wait(f"!!{mp}", 40)
    time.sleep(1.0)
    out = {"map_before": c.js(f"{RECT}({mp})")}
    c.click_on(q("[data-panel=fleet-attention] [data-testid=panel-strip]"))
    att = q("[data-panel=fleet-attention] .panel")
    c.wait(f"{att}.dataset.collapsed !== 'true'", 10)
    time.sleep(0.6)
    out["att_open"] = c.js(f"{RECT}({att})")
    out["map_open"] = c.js(f"{RECT}({mp})")
    out["strips_below"] = c.js(f"{qa('.panel[data-collapsed]')}.every((p) => p.getBoundingClientRect().top >= {att}.getBoundingClientRect().bottom - 2)")
    c.click_on(q("[data-panel=fleet-attention] .panel-title"))
    time.sleep(0.4)
    out["ornament_click"] = c.js(ORNAMENT)
    c.click_on(q("[data-panel=fleet-attention] [data-testid=panel-help-btn]"))
    out["help_first"] = c.wait(f"{q('[data-testid=panel-help] .panel-help-about')}?.textContent", 10)
    out["about_title"] = c.js(f"{q('[data-panel=fleet-attention] .panel-title')}.title")
    c.click_on(q("[data-panel=fleet-attention] [data-testid=panel-help-btn]"))
    out["help_toggled"] = c.wait(f"!{q('[data-testid=panel-help]')} && 'closed'", 5)
    c.click_on(q("[data-panel=fleet-attention] [data-testid=panel-strip]"))
    c.wait(f"{att}.dataset.collapsed === 'true'", 10)
    time.sleep(0.6)
    out["map_back"] = c.js(f"{RECT}({mp})")
    out["custom_after_strip"] = c.js(f"!!{q('[data-testid=layout-badge]')}")
    return out


def saved(c, url, ctx) -> dict:
    fresh(c, ctx, "fleet", "Fleet", "&view=workspace")
    mp = q("[data-panel=fleet-map] .panel")
    c.wait(f"!!{mp}", 40)
    time.sleep(1.0)
    before = c.js(f"{RECT}({mp})")
    c.click_on(q("[data-panel=fleet-map] .panel-title"))
    mod_key(c, "ArrowUp", 38, 9, "ArrowUp")  # Alt+Shift+Up: four rows shorter, the user's own layout
    time.sleep(0.6)
    out = {"map_mine": c.js(f"{RECT}({mp})"), "map_default": before, "key": c.js("!!localStorage.getItem('halo.studio.layout.fleet')")}
    load(c, ctx, "fleet", "Fleet", "&view=workspace")
    c.wait(f"!!{mp}", 40)
    time.sleep(1.0)
    out["map_reload"] = c.js(f"{RECT}({mp})")
    out["badge"] = c.js(f"!!{q('[data-testid=layout-badge]')}")
    out["reset"] = more(c, "layout-reset")
    time.sleep(1.0)
    out["map_reset"] = c.js(f"{RECT}({mp})")
    out["cover_reset"] = c.js(f"{COVER}('fleet-map')")
    out["badge_reset"] = c.js(f"!!{q('[data-testid=layout-badge]')}")
    return out


def _tokens(c) -> list:
    return c.js("[document.documentElement.dataset.density || '', getComputedStyle(document.documentElement).getPropertyValue('--pad').trim(), "
                "getComputedStyle(document.querySelector('[data-panel=roles-graph]')).paddingTop, "
                "Math.round(document.querySelector('[data-panel=roles-graph] .panel-bar').getBoundingClientRect().height), "
                "getComputedStyle(document.body).fontSize]")


def density(c, url, ctx) -> dict:
    fresh(c, ctx, "roles", "Roles")
    c.wait(f"!!{q('[data-panel=roles-graph] .panel-body')}", 40)
    time.sleep(0.6)
    out = {"comfortable": _tokens(c), "toggle_title": c.js(f"{q('[data-testid=density-toggle]')}.title")}
    c.click_on(q("[data-testid=density-toggle]"))
    c.wait("document.documentElement.dataset.density === 'compact'", 5)
    time.sleep(0.4)
    out["compact"] = _tokens(c)
    out["saved"] = c.js("localStorage.getItem('halo.studio.density')")
    if ctx.get("shots"):
        c.shot(Path(ctx["shots"]) / "q3_roles_compact.png", 1280, 800, 1)
    load(c, ctx, "roles", "Roles")
    c.wait(f"!!{q('[data-panel=roles-graph] .panel-body')}", 40)
    out["reload"] = _tokens(c)
    mod_key(c, "KeyK", 75, 2, "k")
    c.wait("document.activeElement?.classList.contains('palette-input')", 10)
    c.type_text("Density: comfortable")
    time.sleep(0.4)
    c.key("Enter")
    c.wait("document.documentElement.dataset.density === 'comfortable'", 5)
    time.sleep(0.4)
    out["palette"] = _tokens(c)
    out["saved_after"] = c.js("localStorage.getItem('halo.studio.density')")
    return out


class QuietPanelsDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}
    width, height = 1280, 800

    @contextmanager
    def session(self, c):
        from capture_studio import seeded_home, serve
        from design_demo import seed
        state = seeded_home()
        seed(state)  # a Design project: the section draws its panels, not its Start view
        srv, url = serve(state, True)
        shots = self.argv[self.argv.index("--shots") + 1] if "--shots" in self.argv else ""
        ctx = {"state": state, "srv": srv, "base": url.split("?", 1)[0], "frag": url.split("#", 1)[1], "shots": shots}
        try:
            yield tuple((fn, (c, url, ctx)) for fn in (defaults, strip, saved, density))
        finally:
            srv.shutdown()
            srv.server_close()
            shutil.rmtree(state.parent, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(QuietPanelsDriver(sys.argv[1:]).main())
