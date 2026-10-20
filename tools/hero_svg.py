"""tools/hero_svg.py -- draw the vector hero and the vector social preview from
the wordmark in halo_harness/banner.py (2.0.11 round A2; 3.1.6.0 R4 the Studio
tagline and chips).

The block art is rendered as vector cells (one <rect> per block element,
thin bars for the box-drawing shadow glyphs), never as text: a text
rendering depends on the viewer's monospace font having gap-free block
glyphs, and GitHub's SVG viewer does not promise one. The art rows are
carried verbatim in the <desc> so tests can pin the hero to banner.py.
`cell_rects` is the one cell geometry: tools/hero_png.py draws the README's
first image (the wordmark over Studio's Session dashboard) from it too.

Usage: python tools/hero_svg.py            # docs/media/hero.svg (1280x330)
       python tools/hero_svg.py --social   # docs/media/social-preview.svg (1280x640)
Deterministic: a rerun writes byte-identical files.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from halo_harness.banner import BANNER_ART_ROWS, RING_ROWS  # noqa: E402

BG, SURFACE, TEXT, MUTED = "#1e1e2e", "#313244", "#cdd6f4", "#9399b2"
GOLD, ACCENT, USER = "#f9e2af", "#89b4fa", "#cba6f7"
CHIPS = (("Studio · every agent, live", ACCENT), ("any model", "#94e2d5"), ("your Claude Code setup, in place", GOLD))
TAGLINE = "The Claude Code-compatible harness for any model, with Studio: every agent, live."
SHADE = {"█": 1.0, "▓": 0.78, "▒": 0.5, "░": 0.25}
SHADOW = 0.45  # the opacity of the box-drawing shadow bars
FONT = "font-family=\"'Fira Code','DejaVu Sans Mono',Consolas,Menlo,monospace\""


def _hex(c: str) -> tuple[int, int, int]:
    return int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)


def _mix(a: str, b: str, t: float) -> str:
    x, y = _hex(a), _hex(b)
    return "#%02x%02x%02x" % tuple(round(x[i] + (y[i] - x[i]) * t) for i in range(3))


def _row_fill(i: int) -> str:
    if i < RING_ROWS:
        return GOLD
    letters = len(BANNER_ART_ROWS) - RING_ROWS
    return _mix(ACCENT, USER, (i - RING_ROWS) / max(1, letters - 1))


def cell_rects(ch: str, x: float, y: float, cw: float, ch_: float) -> "list[tuple[float, float, float, float, float]]":
    """The rectangles (x, y, width, height, opacity) that draw one art cell.
    Box-drawing glyphs are the figlet 'shadow': thin bars at 45% so they read
    as a drop shadow, not a wall."""
    if ch in SHADE:
        return [(x, y, cw, ch_, SHADE[ch])]
    if ch == "▀":
        return [(x, y, cw, ch_ / 2, 1.0)]
    if ch == "▄":
        return [(x, y + ch_ / 2, cw, ch_ / 2, 1.0)]
    bar_w, bar_h = cw * 0.34, ch_ * 0.2
    mx, my = x + (cw - bar_w) / 2, y + (ch_ - bar_h) / 2
    if ch == "═":
        return [(x, my, cw, bar_h, SHADOW)]
    if ch == "║":
        return [(mx, y, bar_w, ch_, SHADOW)]
    if ch == "╗":  # bar from the left to the centre, bar from the centre down
        return [(x, my, mx - x + bar_w, bar_h, SHADOW), (mx, my, bar_w, y + ch_ - my, SHADOW)]
    if ch == "╔":
        return [(mx, my, cw - mx + x, bar_h, SHADOW), (mx, my, bar_w, y + ch_ - my, SHADOW)]
    if ch == "╝":
        return [(x, my, mx - x + bar_w, bar_h, SHADOW), (mx, y, bar_w, my - y + bar_h, SHADOW)]
    if ch == "╚":
        return [(mx, my, cw - mx + x, bar_h, SHADOW), (mx, y, bar_w, my - y + bar_h, SHADOW)]
    return []


def _cell(ch: str, x: float, y: float, cw: float, ch_: float, fill: str) -> str:
    out = []
    for rx, ry, rw, rh, op in cell_rects(ch, x, y, cw, ch_):
        alpha = "" if op == 1.0 else f' opacity="{op}"'
        out.append(f'<rect x="{rx:g}" y="{ry:g}" width="{rw:g}" height="{rh:g}" fill="{fill}"{alpha}/>')
    return "".join(out)


def wordmark(x0: float, y0: float, cw: float, ch_: float) -> str:
    out = [f'<g id="wordmark" transform="translate({x0:g} {y0:g})">']
    for i, row in enumerate(BANNER_ART_ROWS):
        fill = _row_fill(i)
        for j, ch in enumerate(row):
            if ch != " ":
                out.append(_cell(ch, j * cw, i * ch_, cw, ch_, fill))
    out.append("</g>")
    return "\n".join(out)


def _head(w: int, h: int, title: str) -> str:
    rows = "\n".join(BANNER_ART_ROWS)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" '
            f'aria-labelledby="t d" {FONT}>\n<title id="t">{title}</title>\n'
            f"<desc id=\"d\">Halo Harness: the Claude Code-compatible harness for any model. The wordmark rows:\n{rows}\n</desc>\n"
            f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{ACCENT}"/>'
            f'<stop offset="1" stop-color="{USER}"/></linearGradient>'
            f'<radialGradient id="glow" cx="0.5" cy="0.5" r="0.5"><stop offset="0" stop-color="{GOLD}" stop-opacity="0.28"/>'
            f'<stop offset="1" stop-color="{GOLD}" stop-opacity="0"/></radialGradient></defs>\n'
            f'<rect width="{w}" height="{h}" rx="16" fill="{BG}"/>\n<rect x="0" y="0" width="{w}" height="6" fill="url(#g)"/>')


def _chip_width(name: str) -> int:
    # 14 px monospace is about 8.4 px a character; 32 px of padding, 130 at least
    return max(130, round(len(name) * 8.6 + 32))


def _chips(x: float, y: float) -> str:
    """Studio and any model on the first row, the setup chip on the second."""
    out, cx, cy = [], x, y
    for k, (name, color) in enumerate(CHIPS):
        if k == 2:
            cx, cy = x, y + 54
        w = _chip_width(name)
        out.append(f'<rect x="{cx:g}" y="{cy:g}" width="{w}" height="38" rx="19" fill="{SURFACE}" stroke="{color}" stroke-width="1.4"/>'
                   f'<text x="{cx + w / 2:g}" y="{cy + 25:g}" font-size="14" fill="{color}" text-anchor="middle" font-weight="700">{name}</text>')
        cx += w + 16
    return "\n".join(out)


def hero() -> str:
    cw, ch_ = 13.0, 22.0
    body = [_head(1280, 330, "Halo Harness"),
            f'<ellipse cx="{48 + 20 * cw:g}" cy="{44 + 1.5 * ch_:g}" rx="{22 * cw:g}" ry="{3 * ch_:g}" fill="url(#glow)"/>',
            wordmark(48, 44, cw, ch_),
            f'<text x="64" y="292" font-size="16" fill="{TEXT}" font-weight="400">{TAGLINE}</text>',
            _chips(760, 78),
            f'<text x="760" y="214" font-size="13" fill="{MUTED}" font-weight="400">same tools, same config, same habits</text>',
            "</svg>"]
    return "\n".join(body) + "\n"


def social() -> str:
    cw, ch_ = 20.0, 34.0
    x0 = (1280 - 40 * cw) / 2
    body = [_head(1280, 640, "Halo Harness"),
            f'<ellipse cx="640" cy="{120 + 1.5 * ch_:g}" rx="{24 * cw:g}" ry="{3.2 * ch_:g}" fill="url(#glow)"/>',
            wordmark(x0, 120, cw, ch_),
            f'<text x="640" y="492" font-size="22" fill="{TEXT}" text-anchor="middle" font-weight="400">{TAGLINE}</text>',
            f'<text x="640" y="530" font-size="17" fill="{MUTED}" text-anchor="middle">'
            "DeepSeek, GLM, Kimi, Qwen, Claude. Your ~/.claude setup, read in place.</text>",
            "</svg>"]
    return "\n".join(body) + "\n"


def main(argv: list[str]) -> int:
    out = REPO / "docs" / "media"
    if "--social" in argv:
        (out / "social-preview.svg").write_text(social(), encoding="utf-8", newline="\n")
        print(f"wrote {out / 'social-preview.svg'}")
    else:
        (out / "hero.svg").write_text(hero(), encoding="utf-8", newline="\n")
        print(f"wrote {out / 'hero.svg'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
