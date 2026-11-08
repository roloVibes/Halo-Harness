"""halo_harness.studio.theme_boot -- the served page's first paint in the saved palette (Halo 3.3.12.0 R1).

`theme_attr(page)` sets `data-theme` on index.html's <html> tag to `theme` in ~/.halo/config.json when it names a
palette of the registry (halo_harness/themes), else to "auto" (follow the system: holo on a dark system, paper on a
light one). lib/store.ts reads it as the page's first theme, so the page never paints in one palette and then
switches; the header's menu and Settings -> Themes write the key through `settings/set`.

R2: a pack's palette has no block in the built tokens.css (it is not known at build time), so when the saved theme
is one, its variables (themes/studio_css.py, the same derivation as the ten) go into the page as one
`<style id="halo-pack-theme">` rule for `:root[data-theme="<pack-id>/<id>"]` at the end of <head>, and
`theme_csp` allows exactly that rule by its sha256 in the page's style-src: the first frame is the pack's palette,
never a flash of holo. After that lib/theme.ts keeps the variables on <html> from `GET settings/themes`.
"""

from __future__ import annotations

import base64
import hashlib
import html
import re

_ATTR = re.compile(rb'(<html\b[^>]*?)\sdata-theme="[^"]*"', re.I)
STYLE_ID = "halo-pack-theme"
_STYLE = re.compile(rb'<style id="' + STYLE_ID.encode() + rb'">(.*?)</style>', re.S)


def saved_theme() -> str:
    """The palette name Studio draws in: the saved `theme`, or "auto" when it is unset or not a palette."""
    from halo_harness.theme import load_config
    from halo_harness.themes.registry import is_name
    saved = load_config().get("theme")
    return saved if is_name(saved) else "auto"


def pack_rule(name: str) -> str:
    """The first-paint rule for a pack palette's name ("" for a core palette or "auto": tokens.css has those)."""
    from halo_harness.themes.registry import SEP
    from halo_harness.themes.studio_css import as_dict
    if SEP not in name:
        return ""
    decls = " ".join(f"{k}: {v};" for k, v in as_dict(name).items())
    if not decls or any(c in decls for c in "<>{}"):
        return ""
    sel = name.replace("\\", "").replace('"', "")
    return f':root[data-theme="{sel}"] {{ {decls} }}'


def theme_attr(page: bytes) -> bytes:
    name = saved_theme()
    value = html.escape(name, quote=True).encode("utf-8")
    if b"<html" not in page:
        return page
    if _ATTR.search(page):
        page = _ATTR.sub(lambda m: m.group(1) + b' data-theme="' + value + b'"', page, count=1)
    else:
        page = page.replace(b"<html", b'<html data-theme="' + value + b'"', 1)
    rule = pack_rule(name)
    if rule and b"</head>" in page:
        page = page.replace(b"</head>", f'<style id="{STYLE_ID}">{rule}</style></head>'.encode("utf-8"), 1)
    return page


def theme_csp(csp: str, page: bytes) -> str:
    """`csp` with the first-paint rule's sha256 in style-src when the page carries one; `csp` itself otherwise."""
    m = _STYLE.search(page)
    if not m:
        return csp
    digest = base64.b64encode(hashlib.sha256(m.group(1)).digest()).decode("ascii")
    return csp.replace("style-src 'self'", f"style-src 'self' 'sha256-{digest}'", 1)
