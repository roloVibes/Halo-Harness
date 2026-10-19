"""halo_harness.tui.widgets.inplace -- change a Static's text without a
screen layout when its size cannot change.

`Static.update` asks for a full layout by default, and Textual lays out the
whole screen: every transcript widget, thousands of them in a long session.
The status bar, the phase line and the tool / agent cards redraw once a
second (their elapsed counters), so each tick cost a full reflow -- 100 ms
at 50 turns, 400 ms at 150 -- and keys typed meanwhile waited behind it.
`update_in_place` repaints only, unless the new text would change the
widget's height (a wrap) or its width depends on its content. A widget
whose CSS fixes its height (the status bar's `height: 1`, the band's
`height: 8`) never needs the height check: a status line longer than the
terminal wraps in the content measure but the row stays one row, and
measuring it asked for a layout on every tick.
"""

from __future__ import annotations


def update_in_place(widget, content) -> None:
    """`widget.update(content)` with a layout only when the size can change."""
    if not _size_is_fixed(widget):
        widget.update(content)
        return
    if _height_is_fixed(widget):
        widget.update(content, layout=False)
        return
    old_height = widget.content_size.height
    widget.update(content, layout=False)
    try:
        container = widget.parent.size if widget.parent is not None else widget.app.size
        new_height = widget.get_content_height(container, widget.app.size, widget.content_size.width)
    except Exception:
        widget.refresh(layout=True)
        return
    if new_height != old_height:
        widget.refresh(layout=True)


def _size_is_fixed(widget) -> bool:
    """Mounted, laid out once, and not sized by its own width."""
    try:
        if not widget.is_mounted or widget.content_size.width <= 0:
            return False
        width = widget.styles.width
        return width is None or not width.is_auto
    except Exception:
        return False


def _height_is_fixed(widget) -> bool:
    """The CSS sets the height (cells or a fraction), so content cannot change it."""
    try:
        height = widget.styles.height
        return height is not None and not height.is_auto
    except Exception:
        return False
