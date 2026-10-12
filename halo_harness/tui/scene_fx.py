"""halo_harness.tui.scene_fx -- colour helpers and the lighting pass for the
level band (Halo 3.0.2.0). Pure functions over hex strings and the pixel
buffer `scene.render_pixels` builds; no Textual, no Rich.
"""

from __future__ import annotations

from functools import lru_cache

from halo_harness.tui.scene import HEIGHT


@lru_cache(maxsize=4096)
def _rgb(hex_: str) -> tuple:
    h = (hex_ or "#000000").lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        return 0, 0, 0


def _hex(r: float, g: float, b: float) -> str:
    return "#%02x%02x%02x" % (max(0, min(255, int(round(r)))), max(0, min(255, int(round(g)))),
                              max(0, min(255, int(round(b)))))


@lru_cache(maxsize=4096)
def shade(hex_: str, k: float) -> str:
    """`hex_` scaled by `k` (0.55 = the shadow of a colour, 1.3 = a highlight)."""
    r, g, b = _rgb(hex_)
    return _hex(r * k, g * k, b * k)


@lru_cache(maxsize=16384)
def mix(a: str, b: str, t: float) -> str:
    """`a` moved `t` (0..1) of the way to `b`."""
    ar, ag, ab = _rgb(a)
    br, bg_, bb = _rgb(b)
    return _hex(ar + (br - ar) * t, ag + (bg_ - ag) * t, ab + (bb - ab) * t)


def gradient(top: str, bottom: str, steps: int = HEIGHT) -> tuple:
    """`steps` colours from `top` to `bottom`, a sky in one line."""
    if steps <= 1:
        return (top,)
    return tuple(mix(top, bottom, i / (steps - 1)) for i in range(steps))


def apply_lights(buf, lights, sky, bg: str) -> None:
    """Each light is (cx, cy, (hex, radius)): pixels within `radius` move
    toward `hex` by a strength that falls off linearly, drawn pixels by
    up to 55 %, bare sky (None) by up to 45 % over the sky or `bg`
    colour. Deterministic, so captures stay byte-stable."""
    if not buf or not lights:
        return
    width = len(buf[0])
    for cx, cy, (color, radius) in lights:
        if radius <= 0:
            continue
        r2 = radius * radius
        for py in range(max(0, cy - radius), min(HEIGHT, cy + radius + 1)):
            dy = py - cy
            row = buf[py]
            for px in range(max(0, cx - radius), min(width, cx + radius + 1)):
                dx = px - cx
                d2 = dx * dx + dy * dy
                if d2 > r2:
                    continue
                strength = 1.0 - (d2 ** 0.5) / radius
                if row[px] is None:
                    base = sky[py] if sky else bg
                    row[px] = mix(base, color, 0.45 * strength)
                else:
                    row[px] = mix(row[px], color, 0.55 * strength)
