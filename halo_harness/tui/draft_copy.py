"""halo_harness.tui.draft_copy -- copying the chat box's unsent draft, and the
one-time Shift-drag hint (3.1.6.0 R5, the owner on Kali 2026-10-20:
"Copying the words in a session chat text not yet sent does not work").

* `DraftKeeper` (one per `PromptInput`) remembers the last text the chat box
  held that was not a slash command -- so `/copy draft`, typed into that same
  box over the draft (or after Esc / Ctrl+U cleared it), still has the words.
  A sent message clears it: once sent it is no longer a draft.
* `copy_draft(app, source=...)` is the one path Ctrl+Shift+C and `/copy
  draft` share. The key copies what the box holds right now (else the
  remembered draft); the command copies the remembered draft (the box holds
  the command itself). `[Pasted text #n]` placeholders are expanded to the
  pasted text, then it goes through `app.perform_copy` like every copy.
* `ShiftDragHint` shows ONE status-line hint per session, the first time a
  mouse drag starts in the transcript or the chat box: the app has mouse
  tracking on, so the terminal's own selection needs Shift held.
"""
from __future__ import annotations

from textual import events

SHIFT_HINT = ("to select with the terminal's own selection hold Shift while dragging; "
              "Ctrl+C copies what is selected here")

# Ctrl+Shift+C as Textual names it: the kitty keyboard protocol reports
# "ctrl+shift+c" (or "ctrl+shift+C"), xterm's modifyOtherKeys "ctrl+C". A
# legacy terminal sends Ctrl+Shift+C as plain Ctrl+C (one byte, 0x03) or
# keeps it for its own copy -- `/copy draft` works everywhere.
COPY_DRAFT_KEYS = "ctrl+shift+c,ctrl+shift+C,ctrl+C"

NOTHING_TO_COPY = "Nothing in the chat box to copy yet."


def _is_command(text: str) -> bool:
    return text.lstrip().startswith("/")


class DraftKeeper:
    """The last non-command text the chat box held (and its pastes)."""

    def __init__(self) -> None:
        self.text = ""
        self.pasted: dict = {}

    def observe(self, text: str, pasted: "dict | None") -> None:
        if text.strip() and not _is_command(text):
            self.text = text
            self.pasted = dict(pasted or {})

    def sent(self) -> None:
        self.text = ""
        self.pasted = {}


def draft_for_copy(prompt, *, live_first: bool) -> str:
    """The draft's full text (pastes expanded). `live_first`: whatever the
    box holds now wins (the key); otherwise a slash command in the box is
    skipped for the remembered draft (the command)."""
    from halo_harness.tui.app import _expand_pasted
    live = prompt.text or ""
    if live.strip() and (live_first or not _is_command(live)):
        return _expand_pasted(live, prompt.pasted)
    keeper = getattr(prompt, "draft_keeper", None)
    if keeper is None:
        return ""
    return _expand_pasted(keeper.text, keeper.pasted)


def copy_draft(app, *, source: str) -> bool:
    """Copy the draft (`source` "key" or "command"); False when there is
    nothing to copy (and the status line says so)."""
    text = draft_for_copy(app.prompt_input, live_first=(source == "key"))
    if not text.strip():
        title = "/copy draft" if source == "command" else "Ctrl+Shift+C"
        app.notify(NOTHING_TO_COPY, severity="warning", title=title, timeout=3)
        return False
    return app.perform_copy(text, label="the draft")


def _in_copy_area(app, event) -> bool:
    """Whether the mouse is over the transcript or the chat box (on the
    screen that is showing -- a modal on top covers both)."""
    try:
        widget, _region = app.get_widget_at(event.x, event.y)
    except Exception:
        return False
    targets = [t for t in (getattr(app, "transcript", None), getattr(app, "prompt_input", None))
               if t is not None]
    node = widget
    while node is not None:
        if any(node is t for t in targets):
            return True
        node = node.parent
    return False


class ShiftDragHint:
    """MouseDown in the copy area, then a MouseMove with the button still
    held = a drag: the hint shows once and never again this session."""

    def __init__(self) -> None:
        self.shown = False
        self._armed = False

    def observe(self, app, event) -> None:
        if self.shown or not isinstance(event, events.MouseEvent):
            return
        if isinstance(event, events.MouseDown):
            self._armed = event.button == 1 and not event.shift and _in_copy_area(app, event)
            return
        if isinstance(event, events.MouseUp):
            self._armed = False
            return
        if isinstance(event, events.MouseMove) and self._armed and event.button:
            self.shown = True
            self._armed = False
            app.notify(SHIFT_HINT, title="Selecting text", timeout=10)
