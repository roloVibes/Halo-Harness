"""halo_harness.tui.hud_render -- turns a `HudSkin` + live `HudField`s into
the multi-row HUD `rich.text.Text` (Halo 2.0.8). See `tui/hud.py` for the
declaration shape; nothing here is specific to one game.
"""

from __future__ import annotations

from rich.cells import cell_len
from rich.text import Text

from halo_harness.tui.hud import HudField, HudSkin, Segment, ascii_only, clip, pad

METER_CELLS = 6


def _label_min(seg: Segment) -> int:
    return max(seg.width_min, len(seg.label) + 1 if seg.label else 0)


def _face_text(skin: HudSkin, state: str, frame: int, g) -> str:
    frames = skin.faces.get(state) or skin.faces.get("idle") or ("o_o",)
    return f"{g.face_l}{frames[frame % len(frames)]}{g.face_r}"


def _face_width(skin: HudSkin, g) -> int:
    widest = 0
    for frames in skin.faces.values():
        for fr in frames:
            widest = max(widest, cell_len(g.face_l + fr + g.face_r))
    return widest


def _glyph(seg: Segment, ascii_mode: bool) -> str:
    return ascii_only(seg.glyphs) if ascii_mode else seg.glyphs


def _meter(frac: float, g, cells: int = METER_CELLS) -> str:
    on = max(0, min(cells, round(frac * cells)))
    return f"{g.meter_l}{g.meter_on * on}{g.meter_off * (cells - on)}{g.meter_r}"


def _strip_text(seg: Segment, f: HudField, short: bool, ascii_mode: bool) -> str:
    body = (f.short if short and f.short else f.long)
    gl = _glyph(seg, ascii_mode)
    return f"{gl} {body}" if gl else body


def _strip_cells(items, forms, fields, ascii_mode) -> int:
    texts = [cell_len(_strip_text(s, fields[s.slot], forms[s.slot], ascii_mode)) for s in items]
    return 5 + sum(texts) + 3 * max(0, len(texts) - 1) if texts else 4


def _panel_min_total(panels) -> int:
    return sum(_label_min(s) + 2 for s in panels) + len(panels) + 1


def cascade(skin: HudSkin, fields: dict, width: int, ascii_mode: bool):
    """Drop slots in `skin.drop_order` until the panel row and the strip
    both fit at their smallest forms; then relax the strip back to long
    forms item by item while it still fits. Returns (panels, strip, forms)."""
    panels = list(skin.segments)
    strip = [s for s in skin.strip if fields.get(s.slot) and fields[s.slot].long]
    order = list(skin.drop_order)
    forms = {s.slot: True for s in strip}
    while order and (_panel_min_total(panels) > width or _strip_cells(strip, forms, fields, ascii_mode) > width):
        slot = order.pop(0)
        panels = [s for s in panels if s.slot != slot]
        strip = [s for s in strip if s.slot != slot]
    # relax: the most important strip items (last dropped) get long forms first
    ranking = list(reversed(skin.drop_order))
    rank = {slot: i for i, slot in enumerate(ranking)}
    for seg in sorted(strip, key=lambda s: rank.get(s.slot, -1)):
        forms[seg.slot] = False
        if _strip_cells(strip, forms, fields, ascii_mode) > width:
            forms[seg.slot] = True
    return panels, strip, forms


def _panel_candidates(seg, f, g, ascii_mode, cells: int = METER_CELLS):
    gl = _glyph(seg, ascii_mode)
    prefix = f"{gl} " if gl else ""
    meter = _meter(f.frac, g, cells) if f.frac is not None else ""
    out = []
    for body in (f.long, f.short):
        if not body:
            continue
        if meter:
            out.append((prefix, meter + " ", body))
        out.append((prefix, "", body))
    out.append(("", "", f.short or f.long))
    return out


def _panel_natural(seg, f, g, ascii_mode, *, short: bool = False, cells: int = METER_CELLS) -> int:
    """The width a panel wants: its long form (or, with `short`, the first
    candidate built from the short text)."""
    if f is None:
        return _label_min(seg)
    cands = _panel_candidates(seg, f, g, ascii_mode, cells)
    pick = cands[0]
    if short and f.short:
        pick = next((c for c in cands if c[2] == f.short), cands[0])
    return max(_label_min(seg), sum(cell_len(p) for p in pick))


def _distribute(panels, widths, naturals, width) -> None:
    """Grow panels left to right, first to their short natural width and then
    to their long one, while the row fits; hand any leftover columns out
    round-robin so the HUD always spans the whole terminal width."""
    def total():
        return sum(widths[s.slot] + 2 for s in panels) + len(panels) + 1
    for natural in naturals:
        for seg in panels:
            want = natural[seg.slot] - widths[seg.slot]
            room = width - total()
            if want > 0 and room > 0:
                widths[seg.slot] += min(want, room)
    i = 0
    while panels and total() < width:
        widths[panels[i % len(panels)].slot] += 1
        i += 1


def _panel_pieces(skin, seg, f, w, g, ascii_mode, face_text, face_style):
    st = skin.styles
    if seg.slot == "face":
        shown = clip(face_text, w)
        lead = (w - cell_len(shown)) // 2
        return [(" " * lead, ""), (shown, face_style), (" " * (w - lead - cell_len(shown)), "")]
    if f is None:
        return [(pad("-", w), st.get("dim", ""))]
    tone_style = st.get(f.tone or "value", st.get("value", ""))
    for prefix, meter, body in _panel_candidates(seg, f, g, ascii_mode, skin.meter_cells):
        if cell_len(prefix) + cell_len(meter) + cell_len(body) <= w:
            used = cell_len(prefix) + cell_len(meter) + cell_len(body)
            meter_pieces = [(meter, tone_style)]
            if meter and st.get("meter_off"):  # a skin may dim the empty cells (Metroid's empty tanks)
                full = g.meter_l + g.meter_on * meter.count(g.meter_on)
                meter_pieces = [(full, tone_style), (meter[len(full):], st["meter_off"])]
            return [(prefix, st.get("glyph", "")), *meter_pieces, (body, tone_style), (" " * (w - used), "")]
    return [(pad(clip(f.short or f.long, w), w), tone_style)]


def _render_panels(skin, panels, fields, widths, g, ascii_mode, face_text, face_style):
    st = skin.styles
    border = st.get("border", "")
    top, mid = Text(), Text()
    top.append(g.tl, border)
    mid.append(g.v, border)
    for i, seg in enumerate(panels):
        inner = widths[seg.slot] + 2
        label = clip(seg.label, inner - 3) if seg.label else ""
        if label:
            top.append(g.h + " ", border)
            top.append(label, st.get("label", ""))
            top.append(" " + g.h * (inner - cell_len(label) - 3), border)
        else:
            top.append(g.h * inner, border)
        mid.append(" ", "")
        for text, style in _panel_pieces(skin, seg, fields.get(seg.slot), widths[seg.slot], g, ascii_mode,
                                         face_text, face_style):
            mid.append(text, style)
        mid.append(" ", "")
        last = i == len(panels) - 1
        top.append(g.tr if last else g.tee_down, border)
        mid.append(g.v, border)
    return top, mid


def _render_strip(skin, strip, fields, forms, width, g, ascii_mode):
    st = skin.styles
    border = st.get("border", "")
    line = Text()
    line.append(g.bl + g.h, border)
    texts = [_strip_text(s, fields[s.slot], forms[s.slot], ascii_mode) for s in strip]
    budget = width - 5 - 3 * max(0, len(texts) - 1)
    over = sum(cell_len(t) for t in texts) - budget
    if over > 0 and texts:  # last resort: ellipsize the widest item
        widest = max(range(len(texts)), key=lambda k: cell_len(texts[k]))
        texts[widest] = clip(texts[widest], max(3, cell_len(texts[widest]) - over))
    for k, (seg, text) in enumerate(zip(strip, texts)):
        if k:
            line.append(" " + g.h + " ", border)
        else:
            line.append(" ", "")
        line.append(text, st.get(fields[seg.slot].tone or "value", st.get("value", "")))
    used = cell_len(line.plain)
    line.append(" " + g.h * max(0, width - used - 2) + g.br, border)
    return line


def render_compact(skin: HudSkin, fields: dict, face_text: str, face_style: str, width: int) -> Text:
    """The single-line form for very narrow terminals: face, phase, context
    percent, cost, cwd and mode (`skin.compact`), nothing else."""
    st = skin.styles
    parts = []
    for slot in skin.compact:
        if slot == "face":
            parts.append([face_text, face_style])
            continue
        f = fields.get(slot)
        body = (f.short or f.long) if f else ""
        if body:
            parts.append([body, st.get(f.tone or "value", st.get("value", ""))])
    over = sum(cell_len(p[0]) for p in parts) + max(0, len(parts) - 1) - width
    if over > 0:
        widest = max(range(len(parts)), key=lambda k: cell_len(parts[k][0]) if k else 0)
        parts[widest][0] = clip(parts[widest][0], max(3, cell_len(parts[widest][0]) - over))
    text = Text()
    for k, (body, style) in enumerate(parts):
        text.append(body if k == 0 else " " + body, style)
    text.truncate(width, overflow="ellipsis")
    return text


def render_hud(skin: HudSkin, fields: dict, *, width: int, face_state: str = "idle", frame: int = 0,
               ascii_mode: bool = False) -> Text:
    """The HUD for `width` columns: three rows (labelled panels, values,
    ticker) or the one-line compact form below `skin.compact_below`."""
    g = skin.glyphs_ascii if ascii_mode else skin.glyphs
    width = width or 100
    face_text = _face_text(skin, face_state, frame, g)
    face_style = skin.face_styles.get(face_state, skin.styles.get("value", ""))
    if width < skin.compact_below:
        return render_compact(skin, fields, face_text, face_style, width)
    panels, strip, forms = cascade(skin, fields, width, ascii_mode)
    widths = {s.slot: _label_min(s) for s in panels}
    face_w = _face_width(skin, g)
    naturals = [{s.slot: (face_w if s.slot == "face" else _panel_natural(s, fields.get(s.slot), g, ascii_mode,
                                                                          short=short, cells=skin.meter_cells))
                  for s in panels}
                for short in (True, False)]
    widths = {s.slot: max(widths[s.slot], face_w if s.slot == "face" else 0) for s in panels}
    _distribute(panels, widths, naturals, width)
    top, mid = _render_panels(skin, panels, fields, widths, g, ascii_mode, face_text, face_style)
    text = Text()
    text.append_text(top)
    text.append("\n")
    text.append_text(mid)
    text.append("\n")
    text.append_text(_render_strip(skin, strip, fields, forms, width, g, ascii_mode))
    return text
