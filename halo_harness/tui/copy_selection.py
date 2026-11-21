"""What a mouse drag over the transcript copies, and the copy when the drag is let go (3.6.0.6 package C; the
owner, 2026-11-20: "Copying from the session barely works!").

Textual records a drag in `screen.selections` against the LEAF widgets under the pointer: inside a reply those are
the reply's Markdown blocks, which have no `copy_text()`. So the selection is grouped by the transcript widget each
leaf belongs to and ordered as it stands on screen (the transcript's order, then top to bottom). A group whose
selection covers its whole widget (every leaf that draws text, all of it: rows AND columns) copies the widget's
stored source; any other group copies Textual's own drawn text for the dragged range, cleaned (`clean_copy_text`
also drops a drawn "❯ "/"⏺ " at the start)."""
from __future__ import annotations

from typing import Optional

SELECTION_LABEL = "the selection"  # perform_copy says "Copied the selection (N characters)"
COPIED_LAST_REPLY = "Copied the last reply ({n} characters)"


def _drawn(widget, selection) -> "Optional[tuple[str, str]]":
    """Textual's own `(text, ending)` for `selection` in `widget`, or None when the widget draws no text."""
    try:
        return widget.get_selection(selection)
    except Exception:
        return None


def _leaves(owner) -> list:
    """The widgets of `owner` that draw its text: itself when it has no children, else its shown descendants that
    have none."""
    kids = [w for w in owner.walk_children() if w.display and not w.displayed_children]
    return kids or [owner]


def _covers_whole(owner, pieces: dict) -> bool:
    from textual.selection import SELECT_ALL
    own = pieces.get(owner)
    if own is not None and _leaves(owner) != [owner]:
        # the transcript widget ITSELF is selected (a selection set on the widget: select all, a selection made by
        # code): it draws no text of its own to cut a range from. It is the whole of it, its source, as before
        # 3.6.0.7 (the release gate: a reply selected this way was left out of the copy), when it is selected as a
        # whole or when none of its leaves is selected with it; with a leaf's range beside it, the leaves decide below
        if (own.start is None and own.end is None) or all(w is owner for w in pieces):
            return True
    for leaf in _leaves(owner):
        full = _drawn(leaf, SELECT_ALL)
        if not full or not full[0].strip():
            continue
        sel = pieces.get(leaf)
        got = _drawn(leaf, sel) if sel is not None else None
        if got is None or got[0] != full[0]:
            return False
    return True


def _owner(widget, tracked: dict):
    node = widget
    while node is not None:
        if node in tracked:
            return node
        node = node.parent
    return widget


def selected_text(selections: dict, transcript_order: list) -> "Optional[str]":
    """The text a drag selected, as one string ready for the clipboard, or None when nothing is selected."""
    from halo_harness.tui.clipboard import clean_copy_text, join_copied_texts
    if not selections:
        return None
    tracked = {w: i for i, w in enumerate(transcript_order)}
    groups: dict = {}
    for widget, sel in selections.items():
        if not widget.is_attached:
            continue
        groups.setdefault(_owner(widget, tracked), {})[widget] = sel
    ordered = sorted(groups, key=lambda o: (tracked.get(o, len(tracked)), o.region.y, o.region.x))
    parts = []
    for owner in ordered:
        pieces = groups[owner]
        get_source = getattr(owner, "copy_text", None)
        if callable(get_source) and _covers_whole(owner, pieces):
            parts.append(clean_copy_text(get_source()))
            continue
        drawn = []
        for leaf in sorted(pieces, key=lambda w: (w.region.y, w.region.x)):
            got = _drawn(leaf, pieces[leaf])
            if got is not None:
                drawn.extend(got)
        parts.append(clean_copy_text("".join(drawn).rstrip("\n")))
    return join_copied_texts(parts) or None


def observe(app, event) -> None:
    """Every mouse event passes here on its way to Textual: a move to another cell while the button is down (after a
    press, before its release) is a drag. Moves always come before the release, whichever of the release and Textual's
    own TextSelected reaches the app first."""
    from textual import events
    if isinstance(event, events.MouseDown):
        app._press_at, app._dragged = event.screen_offset, False
    elif isinstance(event, events.MouseMove):
        press = getattr(app, "_press_at", None)
        if press is not None and event.screen_offset != press:
            app._dragged = True
    elif isinstance(event, events.MouseUp):
        app._press_at = None


def copy_on_release(app) -> None:
    """A drag over the transcript that ends with a selection copies it at once -- every drag, the same words again
    included. A release where the press was (a click, a scrollbar's) copies nothing, and neither does the same
    selection reported again without a drag."""
    dragged, app._dragged = getattr(app, "_dragged", False), False
    screen = app.screen
    if not dragged or screen is not getattr(app.transcript, "screen", None) or not screen.selections:
        return
    app.perform_copy(selected_text(screen.selections, app.transcript.widgets_in_order()), label=SELECTION_LABEL)
