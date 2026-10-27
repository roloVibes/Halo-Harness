"""tests.helpers.studio_quiet -- "Quiet Studio" round R1 (Halo 3.3.2.0): nothing
opens on any tab, the icon rail, the inspector asks first, Focus. Real keys and
clicks in headless Chrome on the driver base; no provider request, no model call.

    python -m tests.helpers.studio_quiet seeded   capture_studio's seeded home (a lineup active)
    python -m tests.helpers.studio_quiet fresh    capture_start's fresh home (Start here is due)

seeded: each of the eight core sections loaded on its own (`?mode=<id>`, no
`tour=off`) and reached by Alt+1..8, with no section help, no dialog and no
Start here after 2 s; the rail's widths (icons <= 64 px, expanded <= 200 px since 3.3.2.0 R2)
through its chevron, remembered across a reload; rows without a printed key and
no tab strip in the header; the inspector closed on load, opened by a panel's
Settings, given back to the stage by its close button, remembered; Focus by F,
Shift+F (where F follows) and the header button, restoring the rail and the
inspector, remembered across a reload.
fresh: Start here on the first section only; "Set up this box" closes it for
this browser (not back on the next section or a reload); with the browser's key
cleared it is back once, "Just look around" closes it, then the eight sections
by Alt+1..8 and by load show nothing.
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
from tests.helpers.studio_packs_steps import CUR, alt, mod_key, q, qa  # noqa: E402

CORE = [("session", "Session"), ("team", "Team"), ("roles", "Roles"), ("fleet", "Fleet"), ("design", "Design"),
        ("orchestra", "Orchestra"), ("packs", "Packs"), ("setup", "Setup")]
OPEN = ("[document.querySelectorAll('[data-testid=section-help]').length, document.querySelectorAll('[role=dialog]').length, "
        "document.querySelectorAll('[data-testid=start-here]').length]")
APP = q(".app")
RAIL_W = f"Math.round({q('.rail')}.getBoundingClientRect().width)"
STAGE_W = f"Math.round({q('.stage')}.getBoundingClientRect().width)"
ATTRS = f"[{APP}.dataset.rail, {APP}.dataset.inspector, {APP}.dataset.focus]"
# 3.3.2.0 R2: the rail holds the section rows and its chevron, nothing else: no panel row, no layout block, no tree
RAIL_EXTRA = (f"[{qa('.rail > *')}.map((e) => e.dataset.testid).join(','), {qa('.rail .rail-item:not(.rail-section)')}.length, "
              f"{qa('.rail nav, .rail [data-testid^=layout-], .rail [data-testid^=fleet-], .rail [data-testid^=orchestra-]')}.length]")


def _url(ctx, query: str) -> str:
    return f"{ctx['base']}?{query}&feed=off#{ctx['frag']}"


def load(c, ctx, sid: str, title: str, extra: str = "") -> None:
    c.go("about:blank")  # the same address again would be a fragment hop, not a load
    c.go(_url(ctx, f"mode={sid}{extra}"))
    c.wait(f"{CUR}.startsWith('{title}') && !!{q('[data-testid=rail-toggle]')}", 40)


def blur(c) -> None:
    c.js("document.activeElement?.blur?.(); 1")


def each_section(c, ctx, tag: str, out: dict) -> None:
    """Every core section by a load of its own, then by Alt+1..8 from the last: nothing open after 2 s."""
    out[f"{tag}_loads"] = {}
    for sid, title in CORE:
        load(c, ctx, sid, title)
        time.sleep(2.0)
        out[f"{tag}_loads"][sid] = c.js(OPEN)
    out[f"{tag}_keys"] = {}
    for n, (sid, title) in enumerate(CORE, 1):
        blur(c)
        alt(c, n)
        c.wait(f"{CUR}.startsWith('{title}')", 15)
        time.sleep(2.0)
        out[f"{tag}_keys"][sid] = c.js(OPEN)


def sections(c, url, ctx) -> dict:
    out: dict = {}
    each_section(c, ctx, "seeded", out)
    return out


def rail(c, url, ctx) -> dict:
    load(c, ctx, "roles", "Roles", "&tour=off")
    out = {"rail_default": c.js(f"{APP}.dataset.rail"), "rail_icons_w": c.js(RAIL_W)}
    out["rail_items"] = c.js(f"{qa('.rail [data-testid=section-tab]')}.map((b) => [b.dataset.tabId, b.title, b.getAttribute('aria-label'), b.classList.contains('rail-item')])")
    out["rail_on"] = c.js(f"{qa('.rail [data-testid=section-tab].on')}.map((b) => b.dataset.tabId)")
    out["rail_labels_shown_icons"] = c.js(f"{qa('.rail .tab-label')}.filter((l) => l.checkVisibility()).length")
    out["rail_kbd"] = c.js(f"[{qa('.rail .kbd')}.length, /Alt\\+?\\d/.test({q('.rail')}.textContent)]")
    out["header_tabs"] = c.js(f"{qa('.topbar [role=tab]')}.length")
    out["header_title"] = c.js(f"{q('[data-testid=section-title]')}?.textContent || ''")
    out["panels_icons"] = c.js(RAIL_EXTRA)
    c.click_on(q("[data-testid=rail-toggle]"))
    out["rail_open"] = c.wait(f"{APP}.dataset.rail === 'open' && {APP}.dataset.rail", 5)
    time.sleep(0.4)
    out["rail_open_w"] = c.js(RAIL_W)
    out["rail_labels_shown_open"] = c.js(f"{qa('.rail .tab-label')}.filter((l) => l.checkVisibility()).length")
    out["rail_kbd_open"] = c.js(f"[{qa('.rail [data-testid=section-tab] .kbd')}.length, /Alt\\+?\\d/.test({qa('.rail [data-testid=section-tab]')}.map((b) => b.textContent).join(' '))]")
    out["panels_open"] = c.js(RAIL_EXTRA)
    load(c, ctx, "roles", "Roles", "&tour=off")
    out["rail_after_reload"] = [c.js(f"{APP}.dataset.rail"), c.js(RAIL_W)]
    c.click_on(q("[data-testid=rail-toggle]"))
    c.wait(f"{APP}.dataset.rail === 'icons'", 5)
    load(c, ctx, "roles", "Roles", "&tour=off")
    out["rail_back"] = [c.js(f"{APP}.dataset.rail"), c.js(RAIL_W), c.js("localStorage.getItem('halo.studio.rail')")]
    alt(c, 4)
    out["alt4"] = c.wait(f"{CUR}.startsWith('Fleet') && {q('.rail [data-testid=section-tab].on')}.dataset.tabId", 15)
    c.click_on(q(".rail [data-testid=section-tab][data-tab-id=team]"))
    out["click_team"] = c.wait(f"{CUR}.startsWith('Team') && 'team'", 15)
    return out


def _settings(c, panel: str) -> None:
    btn = q(f'[data-panel="{panel}"] [data-testid=panel-menu-btn]')
    c.wait(f"!!{btn}", 30)
    c.click_on(btn)
    c.wait(f"!!{q('[data-testid=panel-menu]')}", 5)
    c.click_on(q("[data-testid=panel-menu] [data-item=settings]"))


def inspector(c, url, ctx) -> dict:
    load(c, ctx, "roles", "Roles", "&tour=off")
    c.wait(f"{qa('[data-testid=roles-card]')}.length >= 3", 30)
    out = {"insp_load": c.js(f"{APP}.dataset.inspector"), "insp_aside": c.js(f"!!{q('[data-testid=inspector]')}"), "stage_w": c.js(STAGE_W)}
    c.click_on(qa("[data-testid=roles-card]") + "[1]")  # the card click the Roles drivers make: its Assignment, in Roles' own panel
    out["card_selected"] = c.wait(f"!!{q('[data-testid=roles-card][data-selected]')}", 10)
    time.sleep(0.5)
    out["insp_after_card"] = c.js(f"{APP}.dataset.inspector")
    _settings(c, "roles-graph")
    out["insp_open"] = c.wait(f"{APP}.dataset.inspector === 'open' && {q('.inspector-title')}?.textContent", 10)
    time.sleep(0.4)
    out["insp_w"] = c.js(f"Math.round({q('.inspector')}.getBoundingClientRect().width)")
    out["stage_w_open"] = c.js(STAGE_W)
    out["insp_saved"] = c.js("localStorage.getItem('halo.studio.inspector')")
    load(c, ctx, "roles", "Roles", "&tour=off")
    out["insp_reload_open"] = c.wait(f"{APP}.dataset.inspector === 'open' && {q('.inspector-title')}?.textContent", 20)
    c.click_on(q("[data-testid=inspector-close]"))
    out["insp_closed"] = c.wait(f"{APP}.dataset.inspector === 'closed' && !{q('[data-testid=inspector]')} && 'closed'", 10)
    time.sleep(0.4)
    out["stage_w_closed"] = c.js(STAGE_W)
    load(c, ctx, "roles", "Roles", "&tour=off")
    time.sleep(1.0)
    out["insp_reload_closed"] = [c.js(f"{APP}.dataset.inspector"), c.js("localStorage.getItem('halo.studio.inspector')")]
    _settings(c, "roles-lineups")
    out["insp_reopen"] = c.wait(f"{APP}.dataset.inspector === 'open' && {q('.inspector-title')}?.textContent", 10)
    return out


def focus(c, url, ctx) -> dict:
    c.click_on(q("[data-testid=rail-toggle]"))  # the widest case: the rail expanded and the inspector open (from the step before)
    out: dict = {"before": c.wait(f"{APP}.dataset.rail === 'open' && {ATTRS}", 5)}
    blur(c)
    c.key("f")
    out["f_on"] = c.wait(f"{APP}.dataset.focus === 'on' && {ATTRS}", 5)
    time.sleep(0.3)
    out["f_hidden"] = c.js(f"[{q('.rail')}.checkVisibility(), !!{q('.inspector')}?.checkVisibility(), {q('.hud-strip')}.checkVisibility()]")
    out["f_grid"] = c.js(f"getComputedStyle({APP}).gridTemplateColumns")
    out["f_rows"] = c.js(f"getComputedStyle({APP}).gridTemplateRows")
    out["f_saved"] = c.js("localStorage.getItem('halo.studio.focus')")
    load(c, ctx, "roles", "Roles", "&tour=off")
    out["f_reload"] = c.wait(f"{APP}.dataset.focus === 'on' && {APP}.dataset.inspector === 'open' && {ATTRS}", 20)
    blur(c)
    c.key("f")
    out["f_off"] = c.wait(f"{APP}.dataset.focus === 'off' && {ATTRS}", 5)
    out["f_back"] = c.js(f"[{q('.rail')}.checkVisibility(), {q('.hud-strip')}.checkVisibility()]")
    c.click_on(q("[data-testid=focus-toggle]"))
    out["btn_on"] = c.wait(f"{APP}.dataset.focus === 'on' && {q('[data-testid=focus-toggle]')}.getAttribute('aria-pressed')", 5)
    out["btn_title"] = c.js(f"{q('[data-testid=focus-toggle]')}.title")
    c.click_on(q("[data-testid=focus-toggle]"))
    out["btn_off"] = c.wait(f"{APP}.dataset.focus === 'off' && 'off'", 5)
    c.click_on(q(".rail [data-testid=section-tab][data-tab-id=session]"))
    c.wait(f"{CUR}.startsWith('Session')", 15)
    blur(c)
    mod_key(c, "KeyF", 70, 8, "F")  # Shift+F: Focus where F follows an agent
    out["shift_f"] = c.wait(f"{APP}.dataset.focus === 'on' && 'on'", 5)
    mod_key(c, "KeyF", 70, 8, "F")
    out["shift_f_off"] = c.wait(f"{APP}.dataset.focus === 'off' && 'off'", 5)
    c.click_on(q("[data-testid=rail-toggle]"))
    out["rail_after"] = c.wait(f"{APP}.dataset.rail === 'icons' && 'icons'", 5)
    return out


def fresh(c, url, ctx) -> dict:
    out: dict = {}
    load(c, ctx, "roles", "Roles")
    out["offer_first"] = c.wait(f"!!{q('[data-testid=start-here-setup]')}", 30)
    out["offer_open"] = c.js(OPEN)
    c.click_on(q("[data-testid=start-here-setup]"))
    out["setup_went"] = c.wait(f"{CUR}.startsWith('Setup') && !{q('[data-testid=start-here]')} && 'setup'", 15)
    out["start_key"] = c.js("localStorage.getItem('halo.studio.start')")
    time.sleep(2.0)
    out["after_setup"] = c.js(OPEN)
    blur(c)
    alt(c, 3)
    c.wait(f"{CUR}.startsWith('Roles')", 15)
    time.sleep(2.0)
    out["next_section"] = c.js(OPEN)
    load(c, ctx, "roles", "Roles")
    time.sleep(2.5)
    out["after_reload"] = c.js(OPEN)
    c.js("localStorage.removeItem('halo.studio.start'); 1")  # a new browser: the home still has no answer, the offer is back once
    load(c, ctx, "roles", "Roles")
    out["offer_again"] = c.wait(f"!!{q('[data-testid=start-here-dismiss]')}", 30)
    c.click_on(q("[data-testid=start-here-dismiss]"))
    out["dismissed"] = c.wait(f"!{q('[data-testid=start-here]')} && 'gone'", 10)
    each_section(c, ctx, "fresh", out)
    return out


class QuietDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_studio import seeded_home, serve
        which = (self.argv[:1] or ["seeded"])[0]
        if which == "fresh":
            from capture_start import fresh_home
            state = fresh_home()
        else:
            state = seeded_home()
        srv, url = serve(state, True)
        base, frag = url.split("?", 1)[0], url.split("#", 1)[1]
        ctx = {"state": state, "srv": srv, "base": base, "frag": frag}
        steps = (fresh,) if which == "fresh" else (sections, rail, inspector, focus)
        try:
            yield tuple((fn, (c, url, ctx)) for fn in steps)
        finally:
            srv.shutdown()
            srv.server_close()
            shutil.rmtree(state.parent, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(QuietDriver(sys.argv[1:]).main())
