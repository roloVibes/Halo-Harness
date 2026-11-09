"""tests.helpers.studio_pack_themes -- the pack step of tests/helpers/studio_themes.py (Halo 3.3.12.0 R2): the fixture
pack `pack-theme` installed and enabled in the scratch home (in process, the Pack Manager's own route), then in
headless Chrome:

1. the header's menu lists Follow, the eleven, then the pack's two palettes in a group under "pack-theme";
2. picking `pack-theme/nightshade` writes the key and the page's computed --accent is the fixture's token;
3. Settings -> Themes shows the pack's rows under "pack-theme", nightshade marked current;
4. a reload with the page's scripts off: the server's inline rule alone paints it (data-theme the pack palette,
   --accent the fixture's token, the app not run) -- the first frame is never the default;
5. disabling the pack through the Pack Manager's route restores the theme saved before (midnight) on the open page
   (the `files_changed` frame for config.json), the pack's variables taken off <html>.
No provider request, no model call; every theme write lands in the scratch config.json.
"""
from __future__ import annotations

import time
from pathlib import Path

from tests.helpers.studio_packs_steps import CUR, q, qa

REPO = Path(__file__).resolve().parents[2]
THEME = "document.documentElement.dataset.theme"
VAR = "getComputedStyle(document.documentElement).getPropertyValue('{}').trim()"
NIGHT = "pack-theme/nightshade"
GROUP = "[data-testid=theme-menu] [data-testid=theme-group][data-pack=pack-theme]"


def _call(ctx, method: str, path: str, body=None):
    from halo_harness.studio.api import Request, dispatch
    return dispatch(Request(method=method, path=path, query={}, body=body or {}, cwd=ctx["proj"], state_dir=ctx["state"]))


def _go(c, ctx, query: str, section: str, *, feed: bool = False) -> None:
    c.go("about:blank")
    c.go(f"{ctx['base']}?{query}{'' if feed else '&feed=off'}&tour=off#{ctx['frag']}")
    c.wait(f"{CUR}.startsWith('{section}')", 40)


def _press(c, expr: str, done: str) -> None:
    c.wait(f"!!({expr})", 15)
    c.js(f"({expr}).scrollIntoView({{block: 'center'}}); 1")
    time.sleep(0.15)
    c.click_on(expr)
    try:
        c.wait(done, 4)
    except TimeoutError:
        c.js(f"({expr})?.click(); 1")
        c.wait(done, 15)


def _saved(ctx, want, timeout: float = 15):
    import json
    p = ctx["state"] / "config.json"
    end = time.time() + timeout
    got = None
    while time.time() < end:
        got = (json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}).get("theme")
        if got == want:
            return got
        time.sleep(0.1)
    return got


def _first_paint(c, ctx) -> dict:
    """The page with its scripts off: only the server's inline rule can colour it."""
    out = {}
    c.go("about:blank")
    c.call("Emulation.setScriptExecutionDisabled", value=True)
    try:
        c.go(f"{ctx['base']}?mode=roles&feed=off&tour=off#{ctx['frag']}")
        c.wait("document.readyState === 'complete' && !!document.getElementById('halo-pack-theme')", 20)
        out = {"first_theme": c.js(THEME), "first_accent": c.js(VAR.format("--accent")), "first_bg": c.js(VAR.format("--bg")),
               "first_app_ran": c.js("!!document.querySelector('[data-testid=section-tab]')"),
               "first_inline_vars": c.js("document.documentElement.style.length")}
    finally:
        c.call("Emulation.setScriptExecutionDisabled", value=False)
    return out


def pack_themes(c, url, ctx) -> dict:
    from halo_harness.packs.install import install
    ok, lines = install(str(REPO / "tests" / "fixtures" / "packs" / "pack-theme"), cwd=ctx["proj"], state_dir=ctx["state"])
    status, _ans = _call(ctx, "POST", "pack/pack-theme/enable")
    _call(ctx, "POST", "settings/set", {"key": "theme", "value": "midnight"})
    out = {"pack_installed": ok and status == 200}
    _go(c, ctx, "mode=roles", "Roles")
    _press(c, q("[data-testid=theme-menu-btn]"), f"!!{q('[data-testid=theme-menu]')}")
    c.wait(f"{qa('[data-testid=theme-menu] [data-testid=theme-item]')}.length === 14", 15)  # follow + eleven + the two pack palettes
    out["pack_menu_group"] = c.js(qa(GROUP + " [data-testid=theme-item]") + ".map((b) => b.dataset.themeId)")
    out["pack_menu_head"] = c.js(f"{q(GROUP + ' [data-testid=theme-group-name]')}?.textContent || ''")
    _press(c, q(f'[data-testid=theme-item][data-theme-id="{NIGHT}"]'), f"{THEME} === '{NIGHT}'")
    out["pack_saved"] = _saved(ctx, NIGHT)
    out["pack_accent"] = c.wait(f"{VAR.format('--accent')} === '#b48cff' && {VAR.format('--accent')}", 10)
    _go(c, ctx, "mode=settings&page=themes", "Settings")
    page_group = "[data-testid=theme-list] [data-testid=theme-group][data-pack=pack-theme]"
    c.wait(f"{qa(page_group + ' [data-testid=theme-row]')}.length === 2", 30)
    out["pack_page_rows"] = c.js(qa(page_group + " [data-testid=theme-row]") + ".map((r) => r.dataset.themeId)")
    out["pack_page_head"] = c.js(f"{q(page_group + ' [data-testid=theme-group-name]')}?.textContent || ''")
    out["pack_page_current"] = c.js(qa("[data-testid=theme-row][data-current]") + ".map((r) => r.dataset.themeId)")
    out.update(_first_paint(c, ctx))
    _go(c, ctx, "mode=settings&page=themes", "Settings", feed=True)
    c.wait(f"{VAR.format('--accent')} === '#b48cff'", 15)
    status, ans = _call(ctx, "POST", "pack/pack-theme/disable")
    out["off_lines"] = ans.get("lines") if isinstance(ans, dict) else None
    out["off_saved"] = _saved(ctx, "midnight")
    out["off_theme"] = c.wait(f"{THEME} === 'midnight' && {THEME}", 20)
    out["off_accent"] = c.wait(f"{VAR.format('--accent')} === '#5b9dff' && {VAR.format('--accent')}", 10)
    out["off_inline_accent"] = c.js("document.documentElement.style.getPropertyValue('--accent')")
    # the pack's rows leave after the registry re-read that pack_changed starts; a slow runner is still drawing them
    out["off_rows"] = c.wait(f"{qa('[data-testid=theme-row]')}.length === 12 && {qa('[data-testid=theme-row]')}.length", 20)
    return out
