"""tools/hero_png.py -- the README's first image and the GitHub social preview
(3.1.6.0 R4): the HALO wordmark over Studio's Session dashboard.

The background is a crop of docs/media/studio-session.png (the Map on the
left, the Live column on the right, the whole width scaled to fit), darkened
at the top edge and behind the wordmark; the wordmark is halo_harness/banner.py's block
art drawn as cells with tools/hero_svg.py's `cell_rects` (never as text);
one line, hero_svg.TAGLINE, sits under it. Pillow only, the holo palette
(Studio's styles/tokens.css) and no fonts fetched: the line is set in
Pillow's own default face (Aileron), as tools/studio_modes_banner.py does.

    python tools/hero_png.py             # docs/media/hero.png (2560x720)
    python tools/hero_png.py --social    # docs/media/social-preview.png (1280x640)
    python tools/hero_png.py --check     # both against a fresh render; exit 1 when stale
Deterministic: a rerun writes byte-identical files. The social preview is a
hand upload: GitHub, the repo's Settings -> General -> Social preview.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

REPO = Path(__file__).resolve().parent.parent
MEDIA = REPO / "docs" / "media"
SOURCE = MEDIA / "studio-session.png"  # 3000x1800, tools/capture_session_anim.py
sys.path.insert(0, str(REPO / "tools"))

from hero_svg import TAGLINE, cell_rects  # noqa: E402  (hero_svg puts the repo on sys.path)
from halo_harness.banner import BANNER_ART_ROWS, RING_ROWS  # noqa: E402

# Studio's dark "holo" tokens; nothing else is drawn
BG = (7, 11, 20)            # --bg
ACCENT = (57, 215, 255)     # --accent, cyan: live
ACCENT_2 = (124, 140, 255)  # --accent-2
WARN = (255, 179, 71)       # --warn, amber: the ring
TEXT = (219, 231, 255)      # --text

# crop: the box of studio-session.png (x0, y0, x1, y1), scaled to `size`: the
# whole width, so the Live column keeps its right edge and the wordmark and its
# line sit over the session list and the Map. base: the dim over all of it;
# behind: the dim behind the wordmark and its line; at: the wordmark's left
# edge (None: centred); radius: rounded corners (the PNG then has alpha)
HERO = {"name": "hero.png", "size": (2560, 720), "crop": (0, 100, 3000, 944), "base": 0.22, "behind": 0.88,
        "cell": (22, 36), "at": 80, "font": 32, "radius": 32}
SOCIAL = {"name": "social-preview.png", "size": (1280, 640), "crop": (0, 60, 3000, 1560), "base": 0.62, "behind": 0.94,
          "cell": (20, 34), "at": None, "font": 26, "radius": 0}


def _smooth(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def _ramp(n: int, peak: float, start: float, end: float) -> "list[int]":
    """`peak` up to `start`, easing to 0 at `end` (positions 0..n-1)."""
    return [round(255 * peak * (1 - _smooth((i - start) / max(1.0, end - start)))) for i in range(n)]


def _strip(values: "list[int]", size: "tuple[int, int]", vertical: bool) -> Image.Image:
    line = Image.new("L", (1, len(values)) if vertical else (len(values), 1))
    line.putdata(values)
    return line.resize(size, Image.NEAREST)


def _backing(size: "tuple[int, int]", block: "tuple[int, int, int, int]", margin: int, peak: float) -> Image.Image:
    """`peak` over `block` grown by `margin`, its edges blurred away."""
    out = Image.new("L", size, 0)
    x0, y0, x1, y1 = block
    ImageDraw.Draw(out).rectangle((x0 - margin, y0 - margin, x1 + margin, y1 + margin), fill=round(255 * peak))
    return out.filter(ImageFilter.GaussianBlur(margin // 2))


def _scrim(spec: dict, block: "tuple[int, int, int, int]") -> Image.Image:
    """How much of the canvas colour covers the capture: a little everywhere,
    most at the top edge and behind the wordmark and its line."""
    w, h = spec["size"]
    alpha = Image.new("L", (w, h), round(255 * spec["base"]))
    alpha = ImageChops.lighter(alpha, _strip(_ramp(h, 0.88, 0, h * 0.4), (w, h), True))
    return ImageChops.lighter(alpha, _backing((w, h), block, spec["cell"][1] * 2, spec["behind"]))


def _letters_colour(i: int) -> "tuple[int, int, int]":
    if i < RING_ROWS:
        return WARN
    t = (i - RING_ROWS) / max(1, len(BANNER_ART_ROWS) - RING_ROWS - 1) * 0.7
    return tuple(round(a + (b - a) * t) for a, b in zip(ACCENT, ACCENT_2))


def _row_masks(size: "tuple[int, int]", x0: int, y0: int, cw: int, ch: int) -> "list[Image.Image]":
    """One coverage mask per art row, every cell a set of whole-pixel rects."""
    masks = []
    for i, row in enumerate(BANNER_ART_ROWS):
        mask = Image.new("L", size, 0)
        draw = ImageDraw.Draw(mask)
        for j, glyph in enumerate(row):
            if glyph == " ":
                continue
            for rx, ry, rw, rh, op in cell_rects(glyph, x0 + j * cw, y0 + i * ch, cw, ch):
                left, top, right, bottom = round(rx), round(ry), round(rx + rw), round(ry + rh)
                if right > left and bottom > top:
                    draw.rectangle((left, top, right - 1, bottom - 1), fill=round(255 * op))
        masks.append(mask)
    return masks


def _font(size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.load_default(size=size)  # Aileron, Pillow >= 10.1
    except TypeError as exc:
        raise SystemExit("tools/hero_png.py needs Pillow 10.1 or newer (ImageFont.load_default(size=))") from exc


def _glow(canvas: Image.Image, mask: Image.Image, colour: "tuple[int, int, int]", radius: int, strength: float) -> None:
    soft = mask.filter(ImageFilter.GaussianBlur(radius)).point(lambda v: round(v * strength))
    canvas.paste(colour, (0, 0, *canvas.size), soft)


def build(spec: dict) -> Image.Image:
    w, h = spec["size"]
    cw, ch = spec["cell"]
    font = _font(spec["font"])
    # the inked columns (the rows start with spaces): the ring is the widest
    ink_l = min(len(r) - len(r.lstrip()) for r in BANNER_ART_ROWS) * cw
    ink_r = max(len(r.rstrip()) for r in BANNER_ART_ROWS) * cw
    art_h = len(BANNER_ART_ROWS) * ch
    line_w = round(ImageDraw.Draw(Image.new("L", (1, 1))).textlength(TAGLINE, font=font))
    gap = round(spec["font"] * 1.05)
    y0 = round((h - art_h - gap - spec["font"]) * 0.46)
    if spec["at"]:  # at the left, the line under the H where the letters start
        x0 = spec["at"]
        line_x = x0 + 4 * cw
    else:  # centred on the ink
        x0, line_x = (w - (ink_r - ink_l)) // 2 - ink_l, (w - line_w) // 2
    line_y = y0 + art_h + gap
    block = (min(x0 + ink_l, line_x), y0, max(x0 + ink_r, line_x + line_w), line_y + spec["font"])
    if spec["at"]:  # at the left, the backing runs out to the left edge
        block = (0,) + block[1:]

    shot = Image.open(SOURCE).convert("RGB").crop(spec["crop"]).resize((w, h), Image.LANCZOS)
    canvas = Image.composite(Image.new("RGB", (w, h), BG), shot, _scrim(spec, block))

    masks = _row_masks((w, h), x0, y0, cw, ch)
    ring, letters = masks[0], masks[RING_ROWS]
    for m in masks[1:RING_ROWS]:
        ring = ImageChops.lighter(ring, m)
    for m in masks[RING_ROWS + 1:]:
        letters = ImageChops.lighter(letters, m)
    _glow(canvas, ring, WARN, cw, 0.18)
    _glow(canvas, letters, ACCENT, cw, 0.2)
    for i, mask in enumerate(masks):
        canvas.paste(_letters_colour(i), (0, 0, w, h), mask)

    text = Image.new("L", (w, h), 0)
    ImageDraw.Draw(text).text((line_x, line_y), TAGLINE, font=font, fill=255)
    _glow(canvas, text, BG, max(4, spec["font"] // 5), 0.9)  # a soft dark backing, so the line reads anywhere
    ImageDraw.Draw(canvas).text((line_x, line_y), TAGLINE, font=font, fill=TEXT)

    bar = Image.linear_gradient("L").rotate(90).resize((w, max(3, h // 180)), Image.BILINEAR)
    canvas.paste(Image.composite(Image.new("RGB", bar.size, ACCENT_2), Image.new("RGB", bar.size, ACCENT), bar), (0, 0))
    if not spec["radius"]:
        return canvas
    corners = Image.new("L", (w, h), 0)
    ImageDraw.Draw(corners).rounded_rectangle((0, 0, w - 1, h - 1), radius=spec["radius"], fill=255)
    canvas.putalpha(corners)
    return canvas


def _check(spec: dict) -> bool:
    path = MEDIA / spec["name"]
    if not path.is_file():
        print(f"{spec['name']}: missing, run tools/hero_png.py{' --social' if spec is SOCIAL else ''}")
        return False
    fresh, current = build(spec), Image.open(path)
    same = current.mode == fresh.mode and current.size == fresh.size and current.tobytes() == fresh.tobytes()
    print(f"{spec['name']}: " + ("up to date" if same else f"stale, re-run tools/hero_png.py{' --social' if spec is SOCIAL else ''}"))
    return same


def main(argv: "list[str]") -> int:
    if "--check" in argv:
        ok = all([_check(HERO), _check(SOCIAL)])
        print("hero check: " + ("ok" if ok else "STALE"))
        return 0 if ok else 1
    spec = SOCIAL if "--social" in argv else HERO
    out = MEDIA / spec["name"]
    im = build(spec)
    im.save(out, optimize=True)
    print(f"wrote {out.relative_to(REPO).as_posix()} ({im.width}x{im.height}, {out.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
