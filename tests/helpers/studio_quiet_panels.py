"""tests.helpers.studio_quiet_panels -- "Quiet Studio" round R3 (Halo 3.3.2.0): quieter panels, one thing per
section (its density setting went in 3.6.0.1); 3.6.0.0 R0a: the stage (one main thing, the other panels drawers opened from the view bar).
Real clicks and keys in headless Chrome at 1280 x 800 over capture_studio's seeded home; no provider request, no model
call.

    python -m tests.helpers.studio_quiet_panels [--shots DIR]

defaults: Session, Agents (Cast) and Packs on a fresh browser (localStorage cleared, `view=workspace`): the main
panel's box over the stage, the other panels' state (closed: a button in the view bar), the focused ornament (one
`.panel.focused`, one set of HUD brackets, one mono data line), no about line anywhere; with --shots a PNG each.
drawer: on Agents -> Live the inspector's button opens it as a drawer right of the tree (the tree gives up its width,
as tall as before, one gap between them), a click moves the ornament to it, its ? opens its help on the about line,
its close gives the width back.
saved: the inspector drawer opened is kept across a reload (no badge anywhere); the header's "..." Reset layout returns
to the default.
no_density (3.6.0.1, the three-lines button removed): the header has no density button and no hole where it was (the
palette door and the theme menu one header gap apart, the theme menu last, at 1280 and at 700 px wide); a browser that
saved `halo.studio.density = compact` under 3.6.0.0 opens with the fresh tokens and no `data-density` on <html>; the
palette offers no "Density" command.
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
from tests.helpers.studio_header_menus import button, more  # noqa: E402
from tests.helpers.studio_packs_steps import CUR, mod_key, q, qa  # noqa: E402

PRIMARY = [("session", "Session", "session-live"), ("roles", "Agents", "map-main"), ("packs", "Packs", "pm-installed")]
RECT = "((e) => { const r = e.getBoundingClientRect(); return [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)]; })"
COVER = ("((p) => { const a = RECT(document.querySelector('.section-view:not([hidden]) [data-panel=\"' + p + '\"] .panel')), "
         "s = RECT(document.querySelector('.stage')); return Math.round(1000 * a[2] * a[3] / (s[2] * s[3])) / 1000; })").replace("RECT", RECT)
STATE = ("[...document.querySelectorAll('.section-view:not([hidden]) [data-testid=viewbar-btn]')].filter((b) => !b.dataset.added)"
         ".map((b) => [b.dataset.panel, b.getAttribute('aria-pressed') === 'true' ? 'open' : 'closed'])"
         ".concat([...document.querySelectorAll('.section-view:not([hidden]) .stage-main > .ws-cell')].map((c) => [c.dataset.panel, 'open']))")
ORNAMENT = (f"[{qa('.section-view:not([hidden]) .panel.focused')}.map((p) => p.closest('.ws-cell').dataset.panel), {qa('.section-view:not([hidden]) .panel[data-focused]')}.length, "
            f"{qa('.section-view:not([hidden]) .hud-brackets')}.length, {qa('.section-view:not([hidden]) .panel-data')}.length, {qa('[data-testid=panel-about], .panel-about')}.length]")
MAP = q(".section-view:not([hidden]) [data-panel=map-main] .panel")
INSP = q(".section-view:not([hidden]) .stage-drawer [data-panel=map-drawer] .panel")


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


def steady(c, expr: str, timeout: float = 10):
    """`expr` once two reads 300 ms apart agree (the stage measures and lays out a moment after its first paint)."""
    last, end = None, time.time() + timeout
    while time.time() < end:
        got = c.js(expr)
        if got is not None and got == last:
            return got
        last = got
        time.sleep(0.3)
    return last


def defaults(c, url, ctx) -> dict:
    out: dict = {"cover": {}, "state": {}, "ornament": {}}
    for sid, title, prim in PRIMARY:
        fresh(c, ctx, sid, title, "&view=workspace")
        c.wait(f"!!{q(f'.section-view:not([hidden]) .stage-main [data-panel={prim}] .panel-body')}", 40)
        out["cover"][sid] = steady(c, f"{COVER}('{prim}')")
        out["state"][sid] = c.js(STATE)
        out["ornament"][sid] = c.js(ORNAMENT)
        if ctx.get("shots"):
            c.shot(Path(ctx["shots"]) / f"q3_{sid}.png", 1280, 800, 1)
    return out


def drawer(c, url, ctx) -> dict:
    fresh(c, ctx, "roles", "Agents")  # the old Roles door: the Map
    c.wait(f"!!{MAP}", 40)
    out = {"map_before": steady(c, f"{RECT}({MAP})")}
    c.click_on(button("map-drawer"))
    c.wait(f"!!{INSP}", 10)
    out["att_open"] = steady(c, f"{RECT}({INSP})")
    out["map_open"] = c.js(f"{RECT}({MAP})")
    c.click_on(q(".section-view:not([hidden]) [data-panel=map-drawer] .panel-title"))
    c.wait(f"{INSP}.classList.contains('focused')", 5)
    out["ornament_click"] = c.js(ORNAMENT)
    c.click_on(q(".section-view:not([hidden]) [data-panel=map-drawer] [data-testid=panel-help-btn]"))
    out["help_first"] = c.wait(f"{q('[data-testid=panel-help] .panel-help-about')}?.textContent", 10)
    out["about_title"] = c.js(f"{q('.section-view:not([hidden]) [data-panel=map-drawer] .panel-title')}.title")
    c.click_on(q(".section-view:not([hidden]) [data-panel=map-drawer] [data-testid=panel-help-btn]"))
    out["help_toggled"] = c.wait(f"!{q('[data-testid=panel-help]')} && 'closed'", 5)
    c.click_on(q(".section-view:not([hidden]) [data-panel=map-drawer] [data-testid=panel-collapse]"))
    c.wait(f"!{INSP}", 10)
    out["map_back"] = steady(c, f"{RECT}({MAP})")
    out["custom_after"] = c.js(f"!!{q('[data-testid=layout-badge]')}")
    return out


def saved(c, url, ctx) -> dict:
    fresh(c, ctx, "roles", "Agents")
    c.wait(f"!!{MAP}", 40)
    before = steady(c, f"{RECT}({MAP})")
    c.click_on(button("map-drawer"))
    c.wait(f"!!{INSP}", 10)
    out = {"map_mine": steady(c, f"{RECT}({MAP})"), "map_default": before, "key": c.js("!!localStorage.getItem('halo.studio.layout.agents-map')")}
    load(c, ctx, "roles", "Agents")
    c.wait(f"!!{MAP} && !!{INSP}", 40)
    out["map_reload"] = steady(c, f"{RECT}({MAP})")
    out["badge"] = c.js(f"!!{q('[data-testid=layout-badge]')}")
    out["reset"] = more(c, "layout-reset")
    c.wait(f"!{INSP}", 10)
    out["map_reset"] = steady(c, f"{RECT}({MAP})")
    out["cover_reset"] = c.js(f"{COVER}('map-main')")
    return out


def _tokens(c) -> list:
    return c.js("[document.documentElement.dataset.density || '', getComputedStyle(document.documentElement).getPropertyValue('--pad').trim(), "
                "getComputedStyle(document.querySelector('.section-view:not([hidden]) .stage-row')).columnGap, "
                "Math.round(document.querySelector('.section-view:not([hidden]) [data-panel=map-main] .panel-bar').getBoundingClientRect().height), "
                "getComputedStyle(document.body).fontSize]")


# 3.6.0.1: the header's last items. [density buttons (the old toggle: its testid, "Density: ..." label and title), the
# palette door's right edge -> the theme menu's left edge, the header's column gap, the theme menu's right edge + the
# header's right padding -> the header's right edge, the theme menu is the header's last child]
HEADER = ("(() => { const t = document.querySelector('.topbar'), p = t.querySelector(':scope > .palette-btn'), "
          "m = t.querySelector('[data-testid=theme-menu-btn]').parentElement, s = getComputedStyle(t), "
          "a = p.getBoundingClientRect(), b = m.getBoundingClientRect(), r = t.getBoundingClientRect(); "
          "return [t.querySelectorAll('[data-testid=density-toggle], [aria-label^=Density], [title^=Density]').length, Math.round(b.left - a.right), "
          "Math.round(parseFloat(s.columnGap)), Math.round(b.right + parseFloat(s.paddingRight) - r.right), t.lastElementChild === m]; })()")


def no_density(c, url, ctx) -> dict:
    """3.6.0.1: the three-lines density button is gone with its setting: no button, no hole where it was (at 1280 and at
    a narrow window), a browser that saved `halo.studio.density = compact` under 3.6.0.0 opens with the default
    tokens, and the palette offers no Density command."""
    fresh(c, ctx, "roles", "Agents")
    c.wait(f"!!{q('[data-panel=map-main] .panel-body')}", 40)
    out = {"fresh": steady(c, "1") and _tokens(c), "header": steady(c, HEADER)}
    try:
        c.call("Emulation.setDeviceMetricsOverride", width=700, height=800, deviceScaleFactor=1, mobile=False)
        out["header_narrow"] = steady(c, HEADER)
        if ctx.get("shots"):
            c.shot(Path(ctx["shots"]) / "q3_header_narrow.png", 700, 800, 1)
    finally:
        c.call("Emulation.setDeviceMetricsOverride", width=1280, height=800, deviceScaleFactor=1, mobile=False)
    c.js("localStorage.setItem('halo.studio.density', 'compact'); 1")  # what a 3.6.0.0 browser may still hold
    load(c, ctx, "roles", "Agents")
    c.wait(f"!!{q('[data-panel=map-main] .panel-body')}", 40)
    out["saved_compact"] = steady(c, "1") and _tokens(c)
    out["html_attr"] = c.js("document.documentElement.hasAttribute('data-density')")
    mod_key(c, "KeyK", 75, 2, "k")
    c.wait("document.activeElement?.classList.contains('palette-input')", 10)
    c.type_text("Density")
    c.wait("document.activeElement?.value === 'Density'", 5)
    out["palette"] = steady(c, f"{qa('[data-testid=palette] [role=option] .palette-label')}.map((e) => e.textContent).filter((t) => t.startsWith('Density'))")
    c.key("Escape")
    return out


class QuietPanelsDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}
    width, height = 1280, 800

    @contextmanager
    def session(self, c):
        from capture_studio import seeded_home, serve
        state = seeded_home()
        srv, url = serve(state, True)
        shots = self.argv[self.argv.index("--shots") + 1] if "--shots" in self.argv else ""
        ctx = {"state": state, "srv": srv, "base": url.split("?", 1)[0], "frag": url.split("#", 1)[1], "shots": shots}
        try:
            yield tuple((fn, (c, url, ctx)) for fn in (defaults, drawer, saved, no_density))
        finally:
            srv.shutdown()
            srv.server_close()
            shutil.rmtree(state.parent, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(QuietPanelsDriver(sys.argv[1:]).main())
