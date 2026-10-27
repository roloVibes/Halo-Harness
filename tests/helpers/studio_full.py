"""tests.helpers.studio_full -- the full arrangement for the Studio drivers (Halo 3.3.2.0 R3).

Since 3.3.2.0 R3 each section opens on one thing: its primary panel fills the stage and every other panel is
a strip at the foot (ui/src/lib/workspace/quiet.ts). A driver that works inside a secondary panel (Session's
Cost, Fleet's Attention, the Roles Inspector, Design's Thread...) loads the page with `open=all`: every panel
in its own spec rectangle, the arrangement the drivers were written against. The quiet default itself is pinned
by tests/test_studio_quiet_panels.py; `open=all` is a URL switch a link or a capture may use too."""
from __future__ import annotations

OPEN_ALL = "&open=all"


def full(url: str) -> str:
    """`url` with `open=all` in its query (before the `#t=` token); unchanged when it already has an `open=`."""
    if "open=" in url.split("#", 1)[0]:
        return url
    head, sep, frag = url.partition("#")
    joiner = "&" if "?" in head else "?"
    return f"{head}{joiner}open=all{sep}{frag}"


def toggle_face(c, panel_sel: str, must: bool = True) -> bool:
    """Compact / Expand of the panel `panel_sel` (a CSS selector of its cell or its panel) through its ... menu
    (3.3.2.0 R3: the toggle left the title line for the menu's `face` row). A panel with one face has no such
    row: with `must` that raises, else the menu closes again and the answer is False."""
    import json
    import time
    btn = f"document.querySelector({json.dumps(panel_sel + ' [data-testid=panel-menu-btn]')})"
    c.wait(f"!!{btn}", 15)
    c.js(f"{btn}.scrollIntoView({{block: 'center'}}); 1")
    c.click_on(btn)
    menu = "document.querySelector('[data-testid=panel-menu]')"
    row = "document.querySelector('[data-testid=panel-menu] [data-item=face]')"
    c.wait(f"!!{menu}", 5)
    time.sleep(0.1)
    if not must and not c.js(f"!!{row}"):
        c.key("Escape")
        c.wait(f"!{menu}", 5)
        return False
    c.wait(f"!!{row}", 5)
    c.click_on(row)
    c.wait(f"!{menu}", 5)
    return True
