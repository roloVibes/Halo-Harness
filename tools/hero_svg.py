"""tools/hero_svg.py -- draw the README hero and the social preview from the
wordmark in halo_harness/banner.py (2.0.11 round A2).

The block art is rendered as vector cells (one <rect> per block element,
thin bars for the box-drawing shadow glyphs), never as text: a text
rendering depends on the viewer's monospace font having gap-free block
glyphs, and GitHub's SVG viewer does not promise one. The art rows are
carried verbatim in the <desc> so tests can pin the hero to banner.py.

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
CHIPS = (("DeepSeek", "#89b4fa"), ("GLM", "#94e2d5"), ("Kimi", "#a6e3a1"), ("Qwen", "#f9e2af"), ("Claude", "#fab387"))
TAGLINE = "The Claude Code-compatible harness for people who'd rather not be locked into one AI coding ecosystem."
SHADE = {"█": 1.0, "▓": 0.78, "▒": 0.5, "░": 0.25}
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


def _cell(ch: str, x: float, y: float, cw: float, ch_: float, fill: str) -> str:
    """The shapes for one art cell. Box-drawing glyphs are the figlet
    'shadow': thin bars at 45% so they read as a drop shadow, not a wall."""
    r = f'fill="{fill}"'
    if ch in SHADE:
        op = "" if SHADE[ch] == 1.0 else f' opacity="{SHADE[ch]}"'
        return f'<rect x="{x:g}" y="{y:g}" width="{cw:g}" height="{ch_:g}" {r}{op}/>'
    if ch == "▀":
        return f'<rect x="{x:g}" y="{y:g}" width="{cw:g}" height="{ch_ / 2:g}" {r}/>'
    if ch == "▄":
        return f'<rect x="{x:g}" y="{y + ch_ / 2:g}" width="{cw:g}" height="{ch_ / 2:g}" {r}/>'
    bar_w, bar_h = cw * 0.34, ch_ * 0.2
    mx, my = x + (cw - bar_w) / 2, y + (ch_ - bar_h) / 2
    h = f'<rect x="{x:g}" y="{my:g}" width="{cw:g}" height="{bar_h:g}" {r} opacity="0.45"/>'
    v = f'<rect x="{mx:g}" y="{y:g}" width="{bar_w:g}" height="{ch_:g}" {r} opacity="0.45"/>'
    if ch == "═":
        return h
    if ch == "║":
        return v
    half_h = f'width="{(cw - mx + x):g}"'
    if ch == "╗":  # bar from the left to the centre, bar from the centre down
        return (f'<rect x="{x:g}" y="{my:g}" width="{(mx - x + bar_w):g}" height="{bar_h:g}" {r} opacity="0.45"/>'
                f'<rect x="{mx:g}" y="{my:g}" width="{bar_w:g}" height="{(y + ch_ - my):g}" {r} opacity="0.45"/>')
    if ch == "╔":
        return (f'<rect x="{mx:g}" y="{my:g}" {half_h} height="{bar_h:g}" {r} opacity="0.45"/>'
                f'<rect x="{mx:g}" y="{my:g}" width="{bar_w:g}" height="{(y + ch_ - my):g}" {r} opacity="0.45"/>')
    if ch == "╝":
        return (f'<rect x="{x:g}" y="{my:g}" width="{(mx - x + bar_w):g}" height="{bar_h:g}" {r} opacity="0.45"/>'
                f'<rect x="{mx:g}" y="{y:g}" width="{bar_w:g}" height="{(my - y + bar_h):g}" {r} opacity="0.45"/>')
    if ch == "╚":
        return (f'<rect x="{mx:g}" y="{my:g}" {half_h} height="{bar_h:g}" {r} opacity="0.45"/>'
                f'<rect x="{mx:g}" y="{y:g}" width="{bar_w:g}" height="{(my - y + bar_h):g}" {r} opacity="0.45"/>')
    return ""


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


def _chips(x: float, y: float) -> str:
    out = []
    for k, (name, color) in enumerate(CHIPS):
        cx = x + (k % 3) * 150
        cy = y + (k // 3) * 54
        out.append(f'<rect x="{cx:g}" y="{cy:g}" width="130" height="38" rx="19" fill="{SURFACE}" stroke="{color}" stroke-width="1.4"/>'
                   f'<text x="{cx + 65:g}" y="{cy + 25:g}" font-size="14" fill="{color}" text-anchor="middle" font-weight="700">{name}</text>')
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
            f'<text x="640" y="492" font-size="24" fill="{TEXT}" text-anchor="middle" font-weight="400">'
            "The Claude Code-compatible harness for any model.</text>",
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
