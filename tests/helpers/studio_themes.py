"""tests.helpers.studio_themes -- one `theme` key for the terminal and Studio (Halo 3.3.12.0 R1), real clicks in
headless Chrome through the driver base over a fresh scratch home (no `theme` saved); no provider request, no model
call. Every theme write lands in the scratch config.json:

1. a fresh page follows the system (`data-theme="auto"`): holo's --bg on a dark system, paper's on a light one;
2. the header's theme menu: Follow the system and the ten palettes, each with a swatch row;
3. picking ember writes `theme: ember` to config.json and flips the page's `data-theme`; a reload keeps it (the
   server paints the first frame in it);
4. Settings -> Themes (`?mode=settings&page=themes`): eleven rows (follow + the ten), the swatch chips in the colours
   `GET settings/themes` sends, ember marked current; the pointer on paper previews it on the page, config.json
   untouched; Esc puts ember back; a click on dusk saves it and the current mark moves; Daltonized on writes
   dusk-daltonized and the page's --accent is the daltonized one;
5. the header's "Follow the system" removes the key and the page is `auto` again.
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
from tests.helpers.studio_packs_steps import CUR, q, qa  # noqa: E402

THEME = "document.documentElement.dataset.theme"
VAR = "getComputedStyle(document.documentElement).getPropertyValue('{}').trim()"
ITEM = "[data-testid=theme-item][data-theme-id={}]"
ROW = "[data-testid=theme-row][data-theme-id={}]"


def saved(ctx):
    p = ctx["state"] / "config.json"
    return (json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}).get("theme")


def until_saved(ctx, want, timeout: float = 15):
    end = time.time() + timeout
    while time.time() < end:
        if saved(ctx) == want:
            return want
        time.sleep(0.1)
    return saved(ctx)


def _load(c, ctx, query: str, section: str) -> None:
    c.go("about:blank")  # the same address again would be a fragment hop, not a load
    c.go(f"{ctx['base']}?{query}&feed=off&tour=off#{ctx['frag']}")
    c.wait(f"{CUR}.startsWith('{section}')", 40)


def scheme(c, value: str) -> None:
    c.call("Emulation.setEmulatedMedia", media="", features=[{"name": "prefers-color-scheme", "value": value},
                                                             {"name": "prefers-reduced-motion", "value": "reduce"}])


def press(c, expr: str, done: str) -> None:
    c.wait(f"!!({expr})", 15)
    c.js(f"({expr}).scrollIntoView({{block: 'center'}}); 1")
    time.sleep(0.15)
    c.click_on(expr)
    try:
        c.wait(done, 4)
    except TimeoutError:
        c.js(f"({expr})?.click(); 1")
        c.wait(done, 15)


def follow_first(c, url, ctx) -> dict:
    scheme(c, "dark")
    _load(c, ctx, "mode=roles", "Roles")
    out = {"fresh_theme": c.js(THEME), "fresh_bg_dark": c.js(VAR.format("--bg"))}
    scheme(c, "light")
    out["fresh_bg_light"] = c.wait(f"{VAR.format('--bg')} !== '{out['fresh_bg_dark']}' && {VAR.format('--bg')}", 10)
    scheme(c, "dark")
    return out


def header_menu(c, url, ctx) -> dict:
    btn = q("[data-testid=theme-menu-btn]")
    press(c, btn, f"!!{q('[data-testid=theme-menu]')}")
    c.wait(f"{qa('[data-testid=theme-menu] [data-testid=theme-item]')}.length === 11", 15)
    out = {"menu_ids": c.js(qa("[data-testid=theme-menu] [data-testid=theme-item]") + ".map((b) => b.dataset.themeId)"),
           "menu_swatches": c.js(f"{qa('[data-testid=theme-menu] [data-testid=theme-swatch]')}.length")}
    press(c, q(ITEM.format("ember")), f"{THEME} === 'ember'")
    out["pick_theme"] = c.js(THEME)
    out["pick_saved"] = until_saved(ctx, "ember")
    out["pick_bg"] = c.js(VAR.format("--bg"))
    _load(c, ctx, "mode=roles", "Roles")
    out["reload_theme"] = c.js(THEME)
    return out


def page(c, url, ctx) -> dict:
    from halo_harness.studio.api import Request, dispatch
    _status, api = dispatch(Request(method="GET", path="settings/themes", query={}, body={}, cwd=ctx["proj"], state_dir=ctx["state"]))
    _load(c, ctx, "mode=settings&page=themes", "Settings")
    c.wait(f"{qa('[data-testid=theme-row]')}.length === 11", 30)
    out = {"page_rows": c.js(qa("[data-testid=theme-row]") + ".map((r) => r.dataset.themeId)"), "page_search": c.js("location.search"),
           "page_current": c.js(qa("[data-testid=theme-row][data-current]") + ".map((r) => r.dataset.themeId)")}
    chips = c.js(qa("[data-testid=theme-list] [data-testid=theme-row]") + ".filter((r) => r.querySelector('[data-testid=theme-swatch]'))"
                 ".map((r) => [r.dataset.themeId, [...r.querySelectorAll('.th-chip')].map((i) => [i.dataset.token, getComputedStyle(i).backgroundColor])])")
    want = {p["id"]: p["tokens"] for p in api["palettes"]}
    off = []
    for pid, got in chips:
        for token, colour in got:
            h = want[pid][token].lstrip("#")
            rgb = f"rgb({int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)})"
            if colour != rgb:
                off.append([pid, token, colour, rgb])
    out["chips_checked"], out["chips_off"] = sum(len(g) for _p, g in chips), off
    x, y, w, h = c.rect(q(ROW.format("paper")))
    c.mouse("mouseMoved", x + w * 0.6, y + h / 2)
    out["hover_theme"] = c.wait(f"{THEME} === 'paper' && {THEME}", 10)
    out["hover_saved"] = saved(ctx)
    c.key("Escape")
    out["esc_theme"] = c.wait(f"{THEME} === 'ember' && {THEME}", 10)
    press(c, q(ROW.format("dusk")), f"!!{q(ROW.format('dusk') + '[data-current]')}")
    out["dusk_saved"] = until_saved(ctx, "dusk")
    out["dusk_current"] = c.js(qa("[data-testid=theme-row][data-current]") + ".map((r) => r.dataset.themeId)")
    out["dusk_theme"] = c.js(THEME)
    press(c, q("[data-testid=theme-mod][data-mod=daltonized]"), f"{THEME} === 'dusk-daltonized'")
    out["dal_saved"] = until_saved(ctx, "dusk-daltonized")
    out["dal_accent"] = c.wait(f"{VAR.format('--accent')} !== '' && {VAR.format('--accent')}", 10)
    out["dal_want"] = next(p["daltonized"]["accent"] for p in api["palettes"] if p["id"] == "dusk")
    return out


def follow(c, url, ctx) -> dict:
    btn = q("[data-testid=theme-menu-btn]")
    press(c, btn, f"!!{q('[data-testid=theme-menu]')}")
    press(c, q(ITEM.format("auto")), f"{THEME} === 'auto'")
    out = {"follow_theme": c.js(THEME), "follow_saved": until_saved(ctx, None)}
    cfg = ctx["state"] / "config.json"
    out["follow_key_gone"] = "theme" not in (json.loads(cfg.read_text(encoding="utf-8")) if cfg.is_file() else {})
    _load(c, ctx, "mode=roles", "Roles")
    out["follow_reload"] = c.js(THEME)
    return out


class ThemesDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_studio import seeded_home, serve
        state = seeded_home()
        srv, url = serve(state, True)
        base, frag = url.split("?", 1)[0], url.split("#", 1)[1]
        ctx = {"state": state, "srv": srv, "base": base, "frag": frag, "proj": state.parent / "project"}
        try:
            yield tuple((fn, (c, url, ctx)) for fn in (follow_first, header_menu, page, follow))
        finally:
            srv.shutdown()
            srv.server_close()
            shutil.rmtree(state.parent, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(ThemesDriver(sys.argv[1:]).main())
