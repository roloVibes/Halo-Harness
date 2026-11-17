"""halo_harness.tui.card_focus -- 3.6.0.2 P5 batch 4: "a card never takes a key meant for the box".

A card that asks him something (a permission, a question, a plan, an approval, the size and image checks, the lane
offer, /effort, /rewind) used to take the keyboard the moment it showed, so a letter of the sentence he was typing
answered it. Now each shown card is either TAKEN (it gets the focus, as before) or WAITS (`app._held_card`: no focus,
the line above the box says it waits, Tab goes to it). The choice is made once, after the keys already queued
(`decide`, through `call_later`), from three facts: the box holds text; a key went into the box in the last
`keys.CARD_WAIT_S`; a dialog is open (cardkeys-design.md K1-K3, K19). A card answers a key only while it has the
focus (the decisions' F-C): any return to the box, by Tab or a click, makes it wait, and text and Enter in the box
never answer it. In its first `keys.CARD_FRESH_S` on screen a card answers no key: the key goes into the box and the
card waits (K17, F-A). Nothing here changes what is allowed -- only which widget gets a key.
"""

from __future__ import annotations

from halo_harness.tui import keys as tui_keys


def _base(app):
    return app.screen_stack[0] if app.screen_stack else None


def _in_card(card, widget) -> bool:
    if card is None or widget is None:
        return False
    if widget is card:
        return True
    try:
        return card in widget.ancestors
    except Exception:
        return False


def focus_target(card):
    """The widget a turn to `card` focuses: a question card's first unanswered list, else the card."""
    pick = getattr(card, "first_unanswered_list", None)
    target = pick() if callable(pick) else None
    return target if target is not None else card


def stamp_box_key(app, *, enter: bool = False) -> None:
    """K3/K19: a key (or paste) went into the box now."""
    box = getattr(app, "prompt_input", None)
    if box is None:
        return
    box.last_key_at = tui_keys.card_clock()
    box.last_key_was_enter = bool(enter)


def waits(app, card) -> bool:
    """The shown card waits: held, or its focus is not decided yet (J2 M1: it counts as waiting everywhere)."""
    if card is None or app._borrowing_card is card:
        return False  # a borrow he started on the card: the card is his to answer now
    return card is app._held_card or not getattr(card, "_focus_decided", True)


def _fresh(card) -> bool:
    _wait, fresh = tui_keys.card_times()
    shown = getattr(card, "shown_at", None)
    return fresh > 0 and shown is not None and tui_keys.card_clock() - shown < fresh


def _is_priority(app, key: str) -> bool:
    try:
        chain = app.screen._binding_chain
    except Exception:
        return False
    for _node, bindings in chain:
        if any(b.priority for b in bindings.key_to_bindings.get(key, ())):
            return True
    return False


# ---- a card is shown -------------------------------------------------------------------------------------------
def on_shown(app, card, *, own_act: bool) -> None:
    """Called by `set_pending_card` before the card becomes `pending_card`."""
    prev = app.pending_card
    if prev is not None and prev is not card:
        # J2 M5: his own command shows a card while another one waits: that one goes back to the FRONT of the queue
        # and comes forward again, waiting, when the new card closes.
        app._pending_queue.insert(0, prev)
        prev._comes_back_waiting = True
        dock = getattr(app, "pending_dock", None)
        if dock is not None and dock.card is prev:
            dock.display = False
        app.status_bar.set_pending_permission(False)
    app._held_card = None
    card.shown_at = tui_keys.card_clock()
    card.own_act = bool(own_act)
    card._focus_decided = False
    line = getattr(app, "card_wait_line", None)
    if line is not None:
        line.hide()


def _should_wait(app, card) -> bool:
    if getattr(card, "_comes_back_waiting", False):
        card._comes_back_waiting = False
        return True
    base = _base(app)
    if app.screen is not base:
        return True  # K2: a dialog is on top
    box = app.prompt_input
    last = box.last_key_at
    if getattr(card, "own_act", False):
        # J1 M3 / J2 M6: no key up to and including the one that ran his command counts, nor the chips it kept;
        # only a key typed after it shows (or text typed after it) makes the card wait.
        text = box.text
        for label in box._chip_labels():
            text = text.replace(label, "")
        return bool(text.strip()) or (last is not None and last > card.shown_at)
    if box.text:
        return True  # K1: words, pastes or chip labels in the box, wherever the focus is
    wait_s, _fresh_s = tui_keys.card_times()
    return base.focused is box and last is not None and tui_keys.card_clock() - last < wait_s


def decide(app, card) -> None:
    """K19: run through `call_later` after the card shows, so the keys already queued went first."""
    if app.pending_card is not card:
        return
    card._focus_decided = True
    base = _base(app)
    if _in_card(card, base.focused):
        refresh(app)  # he turned to it with Tab before this ran: it keeps the focus
        return
    if _should_wait(app, card):
        hold(app, card)
        return
    if card.is_mounted:
        app._focus_on_base(focus_target(card))  # K15: an empty, idle box -- the card takes the focus as before
    refresh(app)


def hold(app, card) -> None:
    """The card waits until it closes: no focus, its line above the box, the held placeholder (K5, K20)."""
    from halo_harness.tui.widgets.cards import held_placeholder
    app._held_card = card
    card._focus_decided = True
    if app._borrowing_card is None:
        box = app.prompt_input
        box.placeholder = held_placeholder(box.size.width or 80)
    refresh(app)


def placeholder(app) -> "str | None":
    """The box's placeholder a shown card asks for (K20), or None: the held one, picked from the box's width now, or a
    taken permission card's keys. A borrow sets its own, so None during one."""
    from halo_harness.tui.widgets.cards import PERMISSION_PLACEHOLDER, PermissionCard, held_placeholder
    card = getattr(app, "pending_card", None)
    if card is None or getattr(app, "_borrowing_card", None) is not None or getattr(card, "done", False):
        return None
    if card is app._held_card:
        return held_placeholder(app.prompt_input.size.width or 80)
    return PERMISSION_PLACEHOLDER if isinstance(card, PermissionCard) else None


def refresh(app) -> None:
    """The wait line and the permission tag follow where the focus is (K5, J1 M5)."""
    line = getattr(app, "card_wait_line", None)
    if line is None:
        return
    card = app.pending_card
    base = _base(app)
    waiting_now = (card is not None and card is app._held_card and app._borrowing_card is None
                   and not _in_card(card, base.focused if base is not None else None))
    if waiting_now:
        line.show_for(card, bool(app.prompt_input.text))
    else:
        line.hide()
    from halo_harness.tui.widgets.cards import PermissionCard
    if isinstance(card, PermissionCard) and not getattr(card, "done", False):
        app.status_bar.set_pending_permission(True, waiting=waiting_now)


def on_base_focus(app, new) -> None:
    """The base screen's focus moved. F-C: once the card's focus is decided, any move out of the card on the base
    screen (Tab, a click on the box or elsewhere) makes it wait -- but not a borrow the card itself started."""
    card = app.pending_card
    if (card is not None and new is not None and getattr(card, "_focus_decided", True)
            and app._borrowing_card is None and card is not app._held_card
            and not getattr(card, "done", False) and not _in_card(card, new)):
        hold(app, card)
        return
    refresh(app)


# ---- keys ------------------------------------------------------------------------------------------------------
def heal(app) -> None:
    """K13: nothing has the focus on the base screen: the card when it is taken, the box otherwise."""
    card = app.pending_card
    if card is not None and not waits(app, card) and card.is_mounted:
        app.set_focus(focus_target(card))
    else:
        app.set_focus(app.prompt_input)


def tab_from_box(app) -> None:
    """K7: Tab in the box (no completion list) with a card shown turns to the card; not during a borrow (J3 M3)."""
    card = app.pending_card
    if card is None or app._borrowing_card is not None or app.screen is not _base(app):
        return
    turn_to_card(app)


def turn_to_card(app) -> None:
    """Tab from the box, or a click on the wait line: the card gets the focus; its keys work as before (K7)."""
    card = app.pending_card
    if card is None or not card.is_mounted:
        return
    card._focus_decided = True
    app.set_focus(focus_target(card))
    refresh(app)


def tab_from_card(app) -> bool:
    """K8: Tab on the shown card goes back to the box, answers nothing, and the card waits from then on."""
    card = app.pending_card
    base = _base(app)
    if card is None or app.screen is not base or not _in_card(card, base.focused):
        return False
    hold(app, card)
    app.set_focus(app.prompt_input)
    return True


def before_key(app, event) -> bool:
    """Called from `BridgeApp.on_event` for a Key or Paste the app received (not yet routed). Decides which widget
    gets it and stamps the box's key time; returns True when the key was used up here."""
    from textual import events
    base = _base(app)
    if base is None or app.screen is not base or not hasattr(app, "prompt_input"):
        return False  # a dialog on top keeps every key it is typed
    box = app.prompt_input
    if isinstance(event, events.Paste):
        if base.focused is box:
            stamp_box_key(app)  # K3: a paste into the box counts
        return False
    key = event.key
    if _is_priority(app, key):
        return False
    if base.focused is None:
        heal(app)  # J1 M2 / J2 M4: the heal happens before the key is routed, so this key itself lands
    focused = base.focused
    card = app.pending_card
    if card is not None and _in_card(card, focused):
        if key == "tab":
            if _fresh(card):
                # J3 M2: Tab on a card in its first moments goes back to the box and stops there.
                hold(app, card)
                app.set_focus(box)
                event.stop()
                return True
            return False
        if getattr(card, "answered_line", None) and (event.is_printable or key == "enter"):
            # J1 M1: the card was already answered elsewhere: his key closes it and sends nothing; a letter goes
            # into the box (the whole sentence stays there), an Enter is used up (it never sends his draft).
            from halo_harness.tui.dispatch import _answered_elsewhere
            _answered_elsewhere(app, card)
            if app.screen.focused is not box:
                app.set_focus(box)
            if key == "enter":
                event.stop()
                return True
            stamp_box_key(app)
            return False
        if _fresh(card):
            # K17 / F-A: a card answers no key in its first moments on screen: it waits, and a letter goes into
            # the box (an Enter is used up: it never sends a draft he did not mean to send).
            hold(app, card)
            app.set_focus(box)
            stamp_box_key(app, enter=(key == "enter"))
            if key == "enter":
                event.stop()
                return True
            return False
        return False
    if focused is box:
        completion_open = bool(app.completion_popup.display and app._completion_items)
        if key == "tab" and card is not None and not completion_open:
            return False  # K7: the Tab that turns to a card leaves the box's key time as it was
        stamp_box_key(app, enter=(key == "enter"))
    return False
