"""halo_harness.tui.scene_text -- the level band's pixels as Rich text
(Halo 3.0.2.0): the half-block renderer for truecolor terminals and the
plain-character form for the rest. See tui/scene.py.
"""

from __future__ import annotations

from rich.style import Style
from rich.text import Text

from halo_harness.tui.scene import ROWS, Scene, _mover_x


def _cell(top, bot, bg: str):
    if top is None and bot is None:
        return " ", Style(bgcolor=bg)
    if top == bot:
        return "█", Style(color=top, bgcolor=bg)
    if bot is None:
        return "▀", Style(color=top, bgcolor=bg)
    if top is None:
        return "▄", Style(color=bot, bgcolor=bg)
    return "▀", Style(color=top, bgcolor=bot)


def pixels_to_text(buf, bg: str) -> Text:
    """Two pixel rows per terminal row through ▀ ▄ █; runs of one style
    are appended together, so a wide band is a few hundred spans."""
    width = len(buf[0]) if buf else 0
    text = Text(no_wrap=True, overflow="crop")
    for row in range(ROWS):
        if row:
            text.append("\n")
        run, run_style = "", None
        for col in range(width):
            ch, style = _cell(buf[2 * row][col], buf[2 * row + 1][col], bg)
            if style == run_style:
                run += ch
            else:
                if run:
                    text.append(run, run_style)
                run, run_style = ch, style
        if run:
            text.append(run, run_style)
    return text


def render_ascii(scene: Scene, width: int, *, phase: str = "idle", frame: int = 0, scroll: int = 0) -> Text:
    """The no-truecolor form: ROWS rows of plain characters, the same
    positions, no colour."""
    rows = [[" "] * width for _ in range(ROWS)]

    def put(art, x, bottom_row=ROWS - 1):
        top = bottom_row - len(art) + 1
        for r, line in enumerate(art):
            for c, ch in enumerate(line):
                px, py = x + c, top + r
                if ch != " " and 0 <= px < width and 0 <= py < ROWS:
                    rows[py][px] = ch

    ground = scene.ascii.get("ground", ("=",))[0]
    rows[ROWS - 1] = list((ground * width)[:width])
    tile = scene.ascii.get("tile")
    if tile:
        spacing = max(len(tile[0]) + 10, 16)
        first = -(scroll % spacing) - spacing
        for x in range(first, width + spacing, spacing):
            put(tile, x, ROWS - 2)
    mover = scene.ascii.get("mover")
    if mover and scene.mover is not None and phase in scene.mover.phases:
        put(mover, _mover_x(scene.mover, frame, width), ROWS - 2)
    hero = scene.ascii.get("hero", ("o", "|", "^"))
    put(hero, scene.hero_x, ROWS - 2)
    text = Text(no_wrap=True, overflow="crop")
    for r, row in enumerate(rows):
        if r:
            text.append("\n")
        text.append("".join(row)[:width])
    return text
