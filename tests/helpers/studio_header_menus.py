"""tests.helpers.studio_header_menus -- the section header's two menus for the Studio drivers (Halo 3.3.2.0 R2):
the "+" (`panels-add` opens `panels-menu`: one `panels-menu-item` per panel with `data-panel` and `data-word`)
and the "..." (`section-more` opens `section-more-menu`: `layout-arrange`, `layout-reset`, `layout-help`). They
replaced the expanded rail's PANELS list and LAYOUT block; the drivers click them the way a user does."""
from __future__ import annotations

import json

PLUS = "document.querySelector('[data-testid=panels-add]')"
PLUS_MENU = "document.querySelector('[data-testid=panels-menu]')"
MORE = "document.querySelector('[data-testid=section-more]')"
MORE_MENU = "document.querySelector('[data-testid=section-more-menu]')"
ROWS = ("[...document.querySelectorAll('[data-testid=panels-menu-item]')].map((b) => [b.dataset.panel, b.dataset.word, "
        "[...b.querySelectorAll('.badge')].map((x) => x.textContent), b.querySelector('.menu-label').textContent])")


def open_plus(c) -> None:
    """The "+" menu open (a click on its button when it is closed)."""
    if not c.js(f"!!{PLUS_MENU}"):
        c.wait(f"!!{PLUS}", 20)
        c.click_on(PLUS)
    c.wait(f"!!{PLUS_MENU}", 10)


def plus_rows(c) -> list:
    """[panel id, word, badges, title] per row of the "+" menu; the menu is left open."""
    open_plus(c)
    return c.js(ROWS)


def close_menus(c) -> None:
    """Esc closes an open header menu (the focus is on its rows)."""
    if c.js(f"!!{PLUS_MENU} || !!{MORE_MENU}"):
        c.key("Escape")
        c.wait(f"!{PLUS_MENU} && !{MORE_MENU}", 5)


def plus(c, panel: str) -> None:
    """Add, bring back or focus `panel` through the "+" menu."""
    open_plus(c)
    row = f"document.querySelector({json.dumps(f'[data-testid=panels-menu-item][data-panel={panel}]')})"
    c.wait(f"!!{row}", 10)
    c.click_on(row)
    c.wait(f"!{PLUS_MENU}", 5)


def more(c, item: str) -> bool:
    """Press the "..." menu's row `item` (layout-arrange, layout-reset, layout-help); False when it is disabled."""
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
