"""halo_harness.studio.theme_boot -- the served page's first paint in the saved palette (Halo 3.3.12.0 R1).

`theme_attr(page)` sets `data-theme` on index.html's <html> tag to `theme` in ~/.halo/config.json when it names a
palette of the registry (halo_harness/themes), else to "auto" (follow the system: holo on a dark system, paper on a
light one). lib/store.ts reads it as the page's first theme, so the page never paints in one palette and then
switches; the header's menu and Settings -> Themes write the key through `settings/set`.
"""

from __future__ import annotations

import html
import re

_ATTR = re.compile(rb'(<html\b[^>]*?)\sdata-theme="[^"]*"', re.I)


def saved_theme() -> str:
    """The palette name Studio draws in: the saved `theme`, or "auto" when it is unset or not a palette."""
    from halo_harness.theme import load_config
    from halo_harness.themes.registry import is_name
    saved = load_config().get("theme")
    return saved if is_name(saved) else "auto"


def theme_attr(page: bytes) -> bytes:
    value = html.escape(saved_theme(), quote=True).encode("utf-8")
    if b"<html" not in page:
        return page
    if _ATTR.search(page):
        return _ATTR.sub(lambda m: m.group(1) + b' data-theme="' + value + b'"', page, count=1)
    return page.replace(b"<html", b'<html data-theme="' + value + b'"', 1)
