"""halo_harness.remote.qr_render -- terminal drawings of a QR matrix (Halo
2.0.9 round 4): half-block glyphs (two module rows per text row) and the
plain `##` form. Takes the rows of 0/1 that `qr.encode` returns."""

from __future__ import annotations

QUIET = 4


def render(matrix: list, quiet: int = QUIET) -> str:
    """Half-block text: light modules are filled so the code reads dark on
    light on a dark terminal. Two module rows per line."""
    n = len(matrix)

    def dark(r: int, c: int) -> bool:
        return 0 <= r < n and 0 <= c < n and bool(matrix[r][c])

    glyph = {(False, False): "█", (True, False): "▄", (False, True): "▀", (True, True): " "}
    lines = []
    for r in range(-quiet, n + quiet, 2):
        lines.append("".join(glyph[(dark(r, c), dark(r + 1, c))] for c in range(-quiet, n + quiet)))
    return "\n".join(lines)


def render_ascii(matrix: list, quiet: int = 2) -> str:
    n = len(matrix)
    rows = []
    for r in range(-quiet, n + quiet):
        rows.append("".join("##" if (0 <= r < n and 0 <= c < n and matrix[r][c]) else "  "
                            for c in range(-quiet, n + quiet)))
    return "\n".join(rows)
