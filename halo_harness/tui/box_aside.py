"""halo_harness.tui.box_aside -- 3.6.0.2 P5 batch 5: his draft is set aside for a borrow and comes back.

A card that needs a line of words (a deny reason, Other, plan feedback, an edit) borrows the box. The borrow used to
empty it, so a draft he was writing -- its pastes and image chips too -- was lost. Now every borrow, whatever the card,
sets the box's text, pastes and chips aside when the box holds text; the line above the box says so
(cardkeys-design.md K9, the decisions' J1 M4/M5). The text comes back exactly as it was: as the LAST step of the
borrow's Enter or Esc when the card has closed (after the clear, J2 M3); while the card stays open (more questions)
only when it closes or the box gets the focus with no borrow running; always before the next card's focus decision.
The borrow numbers its pastes and chips after the ones set aside (J3 M4). When the borrow's answer lost its claim
(answered elsewhere), the box holds the draft, a new line, then his words, and the kept guard holds all of it (K10).
"""

from __future__ import annotations


def _line(app):
    return getattr(app, "card_wait_line", None)


def _show(app) -> None:
    line = _line(app)
    if line is not None:
        line.set_aside(getattr(app, "_set_aside", None) is not None)


def set_aside(app) -> None:
    """Called by `borrow_input` in place of its plain clear: the box empties for the borrow's words."""
    box = app.prompt_input
    if getattr(app, "_set_aside", None) is not None and box.text:
        bring_back(app)  # never two drafts: one set aside earlier and words left in the box join first
    if getattr(app, "_set_aside", None) is None and box.text:
        app._set_aside = {"text": box.text, "pasted": dict(box.pasted), "images": list(box.images),
                          "counter": max([box._paste_counter, *box.pasted]), "cursor": box.cursor_location}
    aside = getattr(app, "_set_aside", None)
    if aside is not None:
        box.paste_floor = aside["counter"]
        box.image_seq_floor = max((int(i.get("seq", 0)) for i in aside["images"]), default=0)
    box.clear_submitted()
    _show(app)


def bring_back(app) -> "str | None":
    """The set-aside text back into the box, exactly as it was; words still in the box follow it after a new line
    (K10). Returns the box's text, or None when nothing was set aside."""
    aside = getattr(app, "_set_aside", None)
    if aside is None:
        return None
    app._set_aside = None
    box = app.prompt_input
    words = box.text
    box.pasted = {**aside["pasted"], **box.pasted}
    box._paste_counter = max(aside["counter"], box._paste_counter)
    box.images = list(aside["images"]) + [img for img in box.images if img not in aside["images"]]
    box.paste_floor = 0
    box.image_seq_floor = 0
    box.text = aside["text"] + ("\n" + words if words else "")
    if words:
        last = box.document.line_count - 1
        box.move_cursor((last, len(box.document.get_line(last))))
    else:
        box.move_cursor(aside["cursor"])
    box._auto_grow()
    _show(app)
    return box.text


def card_closed_after_borrow(app, card) -> None:
    """The last step of a borrow's Enter or Esc: the draft comes back once the card has closed."""
    if app.pending_card is not card or getattr(card, "done", False):
        bring_back(app)


def box_focused(app, new) -> None:
    """The base screen's focus moved: the box got it with no borrow running -- the draft comes back (K9)."""
    if (new is not None and new is getattr(app, "prompt_input", None) and app._borrowing_card is None
            and not getattr(app, "_answering_borrow", False)):
        bring_back(app)


def say_kept(app) -> None:
    """K11: the kept line for 10 s, in the slot above the box."""
    line = _line(app)
    if line is not None:
        line.show_kept()
