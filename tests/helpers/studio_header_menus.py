"""tests.helpers.studio_header_menus -- the panels' doors for the Studio drivers. Halo 3.3.2.0 R2 put a "+" menu in the
section header; 3.6.0.0 R0a replaced it with the view bar (lib/workspace/ViewBar.tsx: one `viewbar-btn` per drawer and
tab of the view, `data-panel`, `aria-pressed` while it is open, `data-added="no"` for an optional panel not in the view
yet). The "..." (`section-more` opens `section-more-menu`: `layout-reset`, `layout-help`; Session adds `session-glance`)
stays in the header. The drivers click them the way a user does."""
from __future__ import annotations

import json

BAR = "document.querySelector('.section-view:not([hidden]) [data-testid=viewbar]')"
MORE = "document.querySelector('[data-testid=section-more]')"
MORE_MENU = "document.querySelector('[data-testid=section-more-menu]')"
ROWS = ("[...document.querySelectorAll('.section-view:not([hidden]) [data-testid=viewbar-btn]')].map((b) => [b.dataset.panel, "
        "b.dataset.added === 'no' ? 'add' : b.getAttribute('aria-pressed') === 'true' ? 'open' : 'closed', b.dataset.role, "
        "b.querySelector('.viewbar-name').textContent])")


def button(panel: str) -> str:
    return f"document.querySelector({json.dumps(f'.section-view:not([hidden]) [data-testid=viewbar-btn][data-panel={panel}]')})"


def bar_rows(c) -> list:
    """[panel id, add | open | closed, role, name] per button of the view bar."""
    c.wait(f"!!{BAR}", 20)
    return c.js(ROWS)


def close_menus(c) -> None:
    """Esc closes an open header menu (the focus is on its rows)."""
    if c.js(f"!!{MORE_MENU}"):
        c.key("Escape")
        c.wait(f"!{MORE_MENU}", 5)


def plus(c, panel: str) -> None:
    """Add or open `panel` through its button in the view bar (a press on an open one would close it: left alone)."""
    btn = button(panel)
    c.wait(f"!!{btn}", 20)
    if c.js(f"{btn}.getAttribute('aria-pressed') !== 'true'"):
        c.click_on(btn)
    c.wait(f"{btn}.getAttribute('aria-pressed') === 'true'", 10)


def more(c, item: str) -> bool:
    """Press the "..." menu's row `item` (layout-reset, layout-help); False when it is disabled."""
    if not c.js(f"!!{MORE_MENU}"):
        c.wait(f"!!{MORE}", 20)
        c.click_on(MORE)
    c.wait(f"!!{MORE_MENU}", 10)
    row = f"document.querySelector('[data-testid={item}]')"
    if c.js(f"{row}.disabled"):
        close_menus(c)
        return False
    c.click_on(row)
    c.wait(f"!{MORE_MENU}", 5)
    return True
