"""tests.helpers.hud_skin_checks -- the checks every HUD skin must pass (Halo
2.0.8 theme pack): the width sweep, the cascade's drop-order rule, the five
face states, the ASCII fallback. Skin-specific tests (tests/test_hud_metroid.py,
and round 3's Mario) call these with their own skin and add their own panels.

All check names are plain ASCII on purpose: a Windows cp1252 console crashes
`print_results` on HUD glyphs in a failing check name.
"""
from __future__ import annotations

from rich.cells import cell_len

from halo_harness.tui.hud import FACE_STATES, SLOTS, HudField, Segment
from halo_harness.tui.hud_render import cascade, render_hud


def sample_fields() -> dict:
    """A fully populated status bar, every slot a skin may name."""
    return {
        "model": HudField("or:demo/atlas-pro", "atlas-pro"),
        "tokens": HudField("812k left", "812k", "ok"),
        "context": HudField("62%", "62%", "ok", 0.62),
        "tools": HudField("41 tools", "41", "ok"),
        "mcp": HudField("MCP 3/3", "3/3", "ok"),
        "cost": HudField("$0.0123 · OR $12.40 left", "$0.0123"),
        "providers": HudField("or dbx", "or", "ok"),
        "cwd": HudField("~/project (main)", "project (main)", "dim"),
        "area": HudField("project · main", "project", "dim"),
        "turns": HudField("07"),
        "elapsed": HudField("0:23", "", "warn"),
        "mode": HudField("auto", "auto"),
        "effort": HudField("high"),
        "agents": HudField("agents 2"),
        "phase": HudField("⠋ writing 23 s · ↓1.2k", "⠋ writing", "warn"),
    }


def lines(skin, width: int, state: str = "idle", ascii_mode: bool = False, fields=None) -> list:
    text = render_hud(skin, fields if fields is not None else sample_fields(), width=width,
                      face_state=state, ascii_mode=ascii_mode)
    return text.plain.split("\n")


def check_declaration(ctx, skin) -> None:
    named = [s.slot for s in skin.segments] + [s.slot for s in skin.strip] + list(skin.compact) + list(skin.drop_order)
    unknown = sorted({n for n in named if n not in SLOTS})
    ctx.check(f"every slot the skin names is in the shared vocabulary, unknown: {unknown}", not unknown)
    ctx.check("the face slot is a panel", any(s.slot == "face" for s in skin.segments))
    keep = {"phase", "context", "cost", "face", "mode", "needs_you", "permission", "offline"}
    ctx.check("the narrow-cascade keepers are never in drop_order", not (keep & set(skin.drop_order)))
    ctx.check("every dropped slot is a panel or a strip item",
              set(skin.drop_order) <= {s.slot for s in skin.segments} | {s.slot for s in skin.strip})
    ctx.check("segments and strip are Segment declarations",
              all(isinstance(s, Segment) for s in skin.segments + skin.strip))


def check_width_sweep(ctx, skin, ascii_mode: bool = False, fields=None) -> None:
    """3 rows of exactly `width` cells from compact_below up to 220 columns;
    one compact row that fits below it."""
    bad = []
    for width in range(skin.compact_below, 221):
        rows = lines(skin, width, ascii_mode=ascii_mode, fields=fields)
        if len(rows) != skin.rows or any(cell_len(row) != width for row in rows):
            bad.append((width, [cell_len(row) for row in rows]))
    ctx.check(f"{skin.name}: {skin.rows} rows of exactly `width` cells for {skin.compact_below}..220 "
              f"(ascii={ascii_mode}), bad: {bad[:3]}", not bad)
    bad = [w for w in range(20, skin.compact_below)
           if len(lines(skin, w, ascii_mode=ascii_mode, fields=fields)) != 1
           or cell_len(lines(skin, w, ascii_mode=ascii_mode, fields=fields)[0]) > w]
    ctx.check(f"{skin.name}: 1 compact row that fits for 20..{skin.compact_below - 1} (ascii={ascii_mode}), bad: {bad[:3]}",
              not bad)


def check_cascade_follows_drop_order(ctx, skin, fields=None) -> None:
    """The dropped set at any width is a prefix of the declared drop order
    (among the slots on offer) and nothing dropped earlier comes back."""
    fields = fields if fields is not None else sample_fields()
    on_offer = {s.slot for s in skin.segments} | set(fields)
    order = [x for x in skin.drop_order if x in on_offer]
    previous: set = set()
    bad_prefix, bad_back = [], []
    for width in range(220, skin.compact_below - 1, -1):
        panels, strip, _forms = cascade(skin, fields, width, False)
        shown = {s.slot for s in panels} | {s.slot for s in strip}
        dropped = {s.slot for s in skin.segments + skin.strip if s.slot in on_offer} - shown
        if dropped != set(order[:len(dropped)]):
            bad_prefix.append(width)
        if not previous <= dropped:
            bad_back.append(width)
        previous = dropped
    ctx.check(f"{skin.name}: dropped slots are a prefix of the declared order, bad widths: {bad_prefix[:3]}", not bad_prefix)
    ctx.check(f"{skin.name}: nothing dropped earlier comes back as the terminal widens, bad: {bad_back[:3]}", not bad_back)


def check_faces(ctx, skin) -> None:
    ctx.check(f"{skin.name}: five states declared", set(skin.faces) == set(FACE_STATES))
    sets = set()
    for state, frames in skin.faces.items():
        ctx.check(f"{skin.name}/{state}: frames are non-empty ASCII", bool(frames) and all(f.isascii() and f.strip() for f in frames))
        sets.add(tuple(frames))
    ctx.check(f"{skin.name}: every state has its own frame set", len(sets) == 5)
    widths = {cell_len(f) for frames in skin.faces.values() for f in frames}
    ctx.check(f"{skin.name}: all frames the same width, got {widths}", len(widths) == 1)
    for state in FACE_STATES:
        mid = lines(skin, 100, state)[1]
        ctx.check(f"{skin.name}/{state}: its first frame is in the middle row", skin.faces[state][0] in mid)
        ctx.check(f"{skin.name}/{state}: has a face style", state in skin.face_styles)


def check_ascii_fallback(ctx, skin) -> None:
    def ascii_form(v: HudField) -> HudField:
        enc = lambda t: t.encode("ascii", "ignore").decode()
        return HudField(enc(v.long), enc(v.short), v.tone, v.frac)
    fields = {k: ascii_form(v) for k, v in sample_fields().items()}
    for width in (60, 80, 120):
        rows = lines(skin, width, "needs_you", ascii_mode=True, fields=fields)
        ctx.check(f"{skin.name}: {width} columns, every character is ASCII in ascii mode", "\n".join(rows).isascii())
        ctx.check(f"{skin.name}: {width} columns, ascii rows are full width", all(cell_len(r) == width for r in rows))
