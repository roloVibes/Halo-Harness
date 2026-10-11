"""scripts/svgsize.py -- give a Textual SVG export an explicit size (Halo
2.0.11 round A1). Pure: no imports with side effects, so a test can import
it in-process (scripts/screenshots.py freezes the clock and seeds the RNG
on import and must only ever run in its own process)."""

from __future__ import annotations

import re

_VIEWBOX = re.compile(r'(<svg\b[^>]*?)\s+viewBox="0 0 ([\d.]+) ([\d.]+)"')


def sized_svg(svg: str) -> str:
    """Add `width`/`height` matching the viewBox to the root tag. Textual
    writes a viewBox only; an SVG with no intrinsic size is laid out at the
    replaced-element default of about 300x150 px wherever it sits in an
    <img> -- GitHub's file view, the page a README click opens, showed
    every capture as a thumbnail. Idempotent: a root tag that already
    carries a width is returned unchanged."""
    m = _VIEWBOX.search(svg)
    if not m or re.search(r'<svg\b[^>]*\bwidth=', svg[:m.end()]):
        return svg
    w, h = float(m.group(2)), float(m.group(3))
    head = f'{m.group(1)} width="{w:g}" height="{h:g}" viewBox="0 0 {m.group(2)} {m.group(3)}"'
    return svg[:m.start()] + head + svg[m.end():]
