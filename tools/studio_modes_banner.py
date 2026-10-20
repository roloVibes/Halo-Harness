"""tools/studio_modes_banner.py -- the Studio five-tile banner for the README.

Composes studio-orchestra.png, studio-roles.png, studio-design.png,
studio-fleet.png, studio-team.png and studio-session.png (the headless-Chrome captures from
tools/capture_studio.py) into one wide banner, docs/media/studio-modes.png:
five frames in a row on the Studio background with a section label over
each and the key that switches to it (Alt+1 .. Alt+6). Pure Pillow, no fonts fetched: the label uses the default
bitmap font scaled up, so the file is identical on every machine with the
same inputs.

    python tools/studio_modes_banner.py            # writes docs/media/studio-modes.png
    python tools/studio_modes_banner.py --check    # exits 1 when the file is stale
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parent.parent
MEDIA = REPO / "docs" / "media"
OUT = MEDIA / "studio-modes.png"

FRAMES = (
    ("studio-orchestra.png", "Orchestra", "Alt 1", "agents writing the same files"),
    ("studio-roles.png", "Roles", "Alt 2", "lineups and bios as a graph"),
    ("studio-design.png", "Design", "Alt 3", "artboards on your own apps"),
    ("studio-fleet.png", "Fleet", "Alt 4", "every harness, every agent"),
    ("studio-team.png", "Team", "Alt 5", "people, blocks and stages"),
    ("studio-session.png", "Session", "Alt 6", "this session, live"),
)
FRAME_W = 640           # each capture is scaled to this width
GAP = 28
PAD = 36
LABEL_H = 92
BG = (17, 17, 27)       # Studio's canvas (claude-dark $bridge-bg)
PANEL = (30, 30, 46)
ACCENT = (137, 180, 250)
INK = (205, 214, 244)
MUTED = (147, 153, 178)
RADIUS = 14


def _font(size: int) -> ImageFont.ImageFont:
    # ImageFont.load_default(size=) is Pillow >= 10.1; fall back to the bitmap
    # default so the script still runs (the label is then smaller).
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _rounded(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=255)
    return mask


def build() -> Image.Image:
    frames = []
    for name, *_ in FRAMES:
        im = Image.open(MEDIA / name).convert("RGB")
        h = round(im.height * FRAME_W / im.width)
        frames.append(im.resize((FRAME_W, h), Image.LANCZOS))
    frame_h = max(f.height for f in frames)
    width = PAD * 2 + FRAME_W * len(FRAMES) + GAP * (len(FRAMES) - 1)
    height = PAD + LABEL_H + frame_h + PAD
    canvas = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(canvas)
    title_font, key_font, sub_font = _font(30), _font(19), _font(18)
    x = PAD
    for (name, label, key, blurb), frame in zip(FRAMES, frames):
        # the label block: a key chip, the mode name, a one-line blurb
        title_w = draw.textlength(label, font=title_font)
        draw.text((x, PAD + 6), label, font=title_font, fill=INK)
        kw = draw.textlength(key, font=key_font)
        chip = (x + title_w + 14, PAD + 8, x + title_w + 14 + kw + 20, PAD + 8 + 34)
        draw.rounded_rectangle(chip, radius=8, fill=PANEL, outline=ACCENT, width=2)
        draw.text((chip[0] + 10, PAD + 8 + 6), key, font=key_font, fill=ACCENT)
        draw.text((x, PAD + 50), blurb, font=sub_font, fill=MUTED)
        # the frame, rounded, with a hairline border
        y = PAD + LABEL_H
        card = Image.new("RGB", (FRAME_W, frame_h), PANEL)
        card.paste(frame, (0, 0))
        canvas.paste(card, (x, y), _rounded(card.size, RADIUS))
        draw.rounded_rectangle((x, y, x + FRAME_W - 1, y + frame_h - 1), radius=RADIUS, outline=(49, 50, 68), width=2)
        x += FRAME_W + GAP
    return canvas


def main(argv: list[str]) -> int:
    im = build()
    if "--check" in argv:
        if not OUT.exists():
            print(f"missing: {OUT}")
            return 1
        current = Image.open(OUT).convert("RGB")
        same = current.size == im.size and current.tobytes() == im.tobytes()
        print("up to date" if same else "stale: re-run tools/studio_modes_banner.py")
        return 0 if same else 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    im.save(OUT, optimize=True)
    print(f"wrote {OUT.relative_to(REPO)} ({im.width}x{im.height}, {OUT.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
