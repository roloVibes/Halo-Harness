"""halo_harness.tui.widgets.input -- `PromptInput(TextArea)` (auto-growing
1-8 lines, paste placeholders, `\\`+Enter/Ctrl+J/Alt+Enter newline, history
Up/Down) and `CompletionPopup` (the `/`+`@` overlay list). Both are dumb
widgets: PromptInput posts `Submitted`/`CompletionQuery` messages and
exposes `.pasted`/history state; `app.py` owns the registry/filesystem
lookups and feeds results back via `show_completions`.
"""

from __future__ import annotations

from pathlib import Path

from textual import events
from textual.binding import Binding
from textual.message import Message
from textual.widgets import OptionList, TextArea

from halo_harness.tools.imageutil import IMAGE_EXTENSIONS
from halo_harness.tui.keys import PASTE_PLACEHOLDER_MIN_LINES, PROMPT_MAX_LINES, PROMPT_MIN_LINES


class CompletionPopup(OptionList):
    """Overlay list for `/` and `@` completion -- hidden (`display=False`)
    until `app.py` has candidates to show."""

    def __init__(self) -> None:
        super().__init__(id="completion-popup")
        self.display = False
        self.can_focus = False  # PromptInput keeps focus; app.py drives this list by index

    def show(self, items: "list[str]") -> None:
        self.clear_options()
        for item in items:
            self.add_option(item)
        self.display = bool(items)
        if items:
            self.highlighted = 0

    def hide(self) -> None:
        self.display = False
        self.clear_options()


class PromptInput(TextArea):
    """`tab_behavior="focus"` is overridden entirely -- Tab always means
    "accept completion" here, never focus-navigation (this app has nowhere
    else useful to Tab to while composing a prompt)."""

    class Submitted(Message):
        def __init__(self, text: str, pasted: dict) -> None:
            super().__init__()
            self.text = text
            self.pasted = dict(pasted)

    class CompletionQuery(Message):
        def __init__(self, kind: str, token: str) -> None:
            super().__init__()
            self.kind = kind
            self.token = token

    class CompletionDismissed(Message):
        pass

    class CompletionNav(Message):
        """1.0.1 hotfix 1: Up/Down while the completion popup is open move
        the highlighted entry instead of either moving the (single-line)
        cursor or triggering history nav -- `direction` is -1 (up) or +1
        (down); `app.py`'s own handler wraps the popup's `highlighted`
        index by the current candidate count."""
        def __init__(self, direction: int) -> None:
            super().__init__()
            self.direction = direction

    class HistoryNav(Message):
        def __init__(self, direction: int) -> None:
            super().__init__()
            self.direction = direction

    class PasteRequested(Message):
        """W2c item 3: Ctrl+V. Some Linux terminals never translate this
        into a bracketed-paste sequence at all (the terminal relies on its
        own separate shortcut instead, e.g. Ctrl+Shift+V) -- it reaches
        here as a bare control character, which `TextArea`'s own built-in
        `action_paste` (bound to this same key, overridden below) would
        otherwise insert FROM Textual's in-process `app.clipboard` register
        -- nothing in this app ever populates that from the real OS
        clipboard, so the built-in action silently "pastes" nothing useful.
        `app.py`'s own handler reads the REAL system clipboard off the UI
        thread instead and hands the text back via `paste_text` below."""
        pass

    BINDINGS = [
        Binding("tab", "accept_completion", "Complete", show=False),
        Binding("ctrl+j,alt+enter", "insert_newline", "Newline", show=False),
        # W2c item 2: TextArea's own inherited binding is "home,ctrl+a" ->
        # cursor-to-line-start; this REPLACES only the "ctrl+a" half (Ctrl+A
        # "selects all text in the input", D-TUI/Claude Code convention --
        # "home" alone still moves the cursor, completely unaffected,
        # verified: Textual's own per-class binding merge resolves each
        # keystroke independently, never as an all-or-nothing combo string).
        Binding("ctrl+a", "select_all", "Select all", show=False),
        # Halo 2.0.3.1: Shift+Insert is the other common "paste from the
        # real OS clipboard" shortcut (X11/Windows convention alongside
        # Ctrl+V) -- bound to the SAME "paste" action TextArea's own
        # built-in "ctrl+v" binding already resolves to `action_paste`
        # below (overridden, never the inherited in-process-register
        # paste), so both keys share one path with no new message type.
        Binding("shift+insert", "paste", "Paste", show=False),
        # 2.0.7 round 0d (rolo's live report, 2026-10-08): pasting a
        # freshly-taken SCREENSHOT did nothing at all. Root cause: on
        # Windows Terminal (and most modern terminals) Ctrl+V is
        # intercepted by the TERMINAL itself -- it runs its own paste,
        # finds no text on an image-only clipboard, and does nothing;
        # the keypress never reaches halo, so the 2.0.3.1 image-read
        # path below never runs. Ctrl+Alt+V is not a terminal default
        # anywhere (Windows Terminal, mintty, gnome-terminal, kitty all
        # pass it through) -- it always reaches the app, and
        # `action_paste`'s worker already reads text-first-then-image,
        # so this one key covers both payloads.
        Binding("ctrl+alt+v", "paste", "Paste", show=False),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(soft_wrap=True, show_line_numbers=False, tab_behavior="focus",
                          id="prompt-input", **kwargs)
        self.pasted: dict = {}
        self._paste_counter = 0
        # Halo 2.0.3.1: pending image attachments for the NEXT submit, in
        # chip order -- each `{"path": Path, "width": int|None,
        # "height": int|None, "media_type": str}`. `app.py` turns these
        # into real wire blocks at submit time (reading the file fresh);
        # this widget only ever tracks the chip metadata + its own visible
        # placeholder text, same split `self.pasted` already has for a
        # long text paste.
        self.images: list = []
        # 1.0.1 hotfix 1: mirrors `app.py`'s own completion_popup.display --
        # kept here too (rather than reaching into `self.app` on every
        # keypress) so `action_cursor_up`/`action_cursor_down`/`_on_key`'s
        # own Enter branch can decide, synchronously, whether Up/Down/Enter
        # mean "navigate/accept the popup" or their ordinary meaning.
        # `app.py`'s `set_completion_open` is the only writer.
        self._completion_open = False

    def set_completion_open(self, is_open: bool) -> None:
        self._completion_open = bool(is_open)

    # ---- submit / newline --------------------------------------------

    async def _on_key(self, event: events.Key) -> None:
        # 2.0.0 Launch intro: "any keypress ... completes it instantly" --
        # a plain PRINTABLE character is consumed by this widget's own
        # TextArea handling below and never reaches `BridgeApp._on_key`'s
        # OWN intro-skip check at all (confirmed by this file's sibling
        # test `test_on_key_debug_trace_never_logs_a_raw_printable_
        # keystroke`'s own docstring -- driving a printable key through a
        # real pilot never invokes the App's `_on_key` while this widget
        # has focus), so the skip ALSO has to happen right here, first,
        # before anything else below -- a side effect only, never
        # `event.stop()`, so the key still does whatever it would have
        # anyway (inserted into the text, or Enter's own branch below).
        intro_line = getattr(self.app, "intro_line", None)
        if intro_line is not None and not intro_line.done:
            intro_line.skip()
        if self.read_only:
            await super()._on_key(event)
            return
        if event.key == "enter":
            event.stop()
            event.prevent_default()
            if self._completion_open:
                # 1.0.1 hotfix 1: Enter accepts the highlighted completion
                # while the popup is open. Claude Code parity: for a `/`
                # command that one Enter also RUNS it (`/mo` + Enter opens
                # the model picker; typing `/models` and pressing Enter
                # once runs it -- a second Enter used to be required, which
                # read as "/models does nothing"). An `@` path completion
                # is only inserted (the message is still being composed);
                # Tab only ever inserts. app.py decides which, per kind.
                self.post_message(self.CompletionQuery("accept_submit", ""))
                self._auto_grow()
                return
            row, col = self.cursor_location
            line = self.document.get_line(row)
            if col > 0 and line[col - 1] == "\\":
                self.delete((row, col - 1), (row, col))
                self.insert("\n")
            else:
                text = self.text
                self.post_message(self.Submitted(text, self.pasted))
            self._auto_grow()
            return
        await super()._on_key(event)
        self._auto_grow()

    def action_insert_newline(self) -> None:
        self.insert("\n")
        self._auto_grow()

    def clear_submitted(self, keep_images: bool = False) -> None:
        """Empty the box after a submit. `keep_images=True` (a typed slash
        command, review finding 68) keeps the pending image chips: the
        records stay and their labels are put back as the box text, so the
        next real prompt still carries the attachments."""
        kept = list(self.images) if keep_images else []
        self.text = ""
        self.pasted = {}
        self._paste_counter = 0
        self.images = kept
        if kept:
            self.text = "".join(self._chip_labels())
            self.move_cursor((0, len(self.text)))
        self._auto_grow()

    # ---- auto-grow 1-8 lines -------------------------------------------

    def _auto_grow(self) -> None:
        # review/U5 must-do: count WRAPPED display rows, not logical
        # (newline-delimited) lines -- a single 300-character line at 80
        # columns is ~4 wrapped rows and used to report "1 of 5" (barely
        # taller than empty) because `document.line_count` only counts
        # `\n`s. `TextArea.wrapped_document.height` is Textual's own
        # wrap-aware row count, kept live as the document/width change;
        # `wrap_width` is 0 (nothing computed yet) for exactly one frame
        # around initial mount, before any resize has happened, so this
        # falls back to the logical count then rather than raising.
        try:
            row_count = self.wrapped_document.height
        except Exception:
            row_count = self.document.line_count
        lines = max(PROMPT_MIN_LINES, min(PROMPT_MAX_LINES, row_count))
        self.styles.height = lines

    def on_text_area_changed(self, _event: TextArea.Changed) -> None:
        self._drop_orphaned_images()
        self._auto_grow()
        self._maybe_query_completion()

    # ---- paste placeholder ------------------------------------------------

    async def _on_paste(self, event: events.Paste) -> None:
        if self.read_only:
            return
        # Textual dispatches a private `_on_<name>` handler at EVERY class
        # in the MRO that defines one, INDEPENDENTLY (message_pump.py's
        # `_get_dispatch_methods` walks `self.__class__.__mro__` and calls
        # each level's own definition -- it does NOT rely on `super()`
        # chaining). Calling `super()._on_paste(...)` from here would
        # therefore run `TextArea._on_paste` TWICE: once explicitly, right
        # now, and once more automatically and independently right after
        # this method returns (observed: the ORIGINAL, un-substituted text
        # got inserted a second time). The fix is to never call `super()`
        # here at all -- mutate `event.text` in place (Paste.text is a
        # plain mutable attribute) so the framework's OWN later, automatic
        # call to `TextArea._on_paste` performs the (correct, one-time)
        # insertion itself, using our substituted text.
        event.stop()  # never let it also bubble to the Screen/App
        event.text = self._text_or_image_chip_for(event.text)
        # `_auto_grow`/`_maybe_query_completion` run from `on_text_area_
        # changed` once the (still-pending) real insertion actually happens.

    def _placeholder_text_for(self, text: str) -> str:
        """The 4+-line-paste-becomes-a-placeholder rule (D-TUI) -- factored
        out so `_on_paste` (a real terminal paste) and `paste_text` below
        (a Ctrl+V-triggered system-clipboard paste, no real `events.Paste`
        object at all) apply the EXACT SAME rule through the EXACT SAME
        code, never a second, independently-drifting copy of it."""
        line_count = text.count("\n") + 1
        if line_count < PASTE_PLACEHOLDER_MIN_LINES:
            return text
        self._paste_counter += 1
        n = self._paste_counter
        self.pasted[n] = text
        return f"[Pasted text #{n} +{line_count} lines]"

    def _text_or_image_chip_for(self, text: str) -> str:
        """Halo 2.0.3.1: a pasted/dragged TEXT that IS the path of an
        existing image file (Explorer/Finder drag, with or without quotes)
        attaches that file as a chip instead of ever inserting the raw
        path -- checked BEFORE the long-text placeholder rule, which would
        otherwise only ever fire for a path long enough to wrap 4+ lines
        anyway. Falls through to `_placeholder_text_for` unchanged for
        anything that isn't an existing image path."""
        label = self._image_chip_label_for_path(text)
        return label if label is not None else self._placeholder_text_for(text)

    def _image_chip_label_for_path(self, raw: str) -> "str | None":
        candidate = (raw or "").strip()
        if not candidate or "\n" in candidate:
            return None
        if len(candidate) >= 2 and candidate[0] == candidate[-1] and candidate[0] in "\"'":
            candidate = candidate[1:-1]
        path = Path(candidate)
        default_media_type = IMAGE_EXTENSIONS.get(path.suffix.lower())
        if default_media_type is None or not path.is_file():
            return None
        width = height = None
        media_type = default_media_type
        try:
            from halo_harness.tools.imageutil import sniff_dimensions, sniff_media_type
            data = path.read_bytes()
            media_type = sniff_media_type(data) or media_type
            dims = sniff_dimensions(data)
            if dims:
                width, height = dims
        except OSError:
            pass
        return self._register_image_attachment(path, width, height, media_type)

    def _register_image_attachment(self, path: Path, width, height, media_type: str) -> str:
        # The label is fixed when the image is attached (finding 73): the
        # record is matched to its visible chip by this exact text, so a
        # chip removed by selecting-and-typing takes its record with it and
        # the surviving chips keep their numbers.
        seq = max((int(i.get("seq", 0)) for i in self.images), default=0) + 1
        label = f"[Image #{seq} {width}x{height}]" if (width and height) else f"[Image #{seq}]"
        self.images.append({"path": path, "width": width, "height": height, "media_type": media_type,
                            "seq": seq, "label": label})
        return label

    def _chip_labels(self) -> "list[str]":
        return [img.get("label") or f"[Image #{i}]" for i, img in enumerate(self.images, start=1)]

    def _drop_orphaned_images(self) -> None:
        """Finding 73: drop the pending image whose chip label is no longer
        in the box (selected over and typed on, cut, ...), so a removed chip
        never leaves its image attached to the next prompt."""
        if not self.images:
            return
        text = self.text
        kept = [img for img in self.images if (img.get("label") or "") in text]
        if len(kept) != len(self.images):
            self.images = kept

    def add_image_chip(self, *, path, width=None, height=None, media_type: str = "image/png") -> None:
        """Called by `app.py`/`tui/slash.py` once a REAL clipboard image
        read (performed off the UI thread -- a subprocess call can take
        real time) or `/paste <path>` comes back with something -- same
        insertion mechanics as `paste_text` below, just for a chip label
        instead of pasted text."""
        if self.read_only:
            return
        label = self._register_image_attachment(Path(path), width, height, media_type)
        if result := self._replace_via_keyboard(label, *self.selection):
            self.move_cursor(result.end_location)
        self._auto_grow()

    # ---- Ctrl+V: a real system-clipboard paste (W2c item 3) --------------

    def action_paste(self) -> None:
        """Overrides TextArea's own built-in `action_paste` (bound to this
        same "ctrl+v" key) -- see `PasteRequested`'s own docstring for why
        pasting Textual's in-process `app.clipboard` register directly,
        the built-in behavior, is never the right thing here."""
        if self.read_only:
            return
        self.post_message(self.PasteRequested())

    def paste_text(self, text: str) -> None:
        """Called by `app.py` once a Ctrl+V-triggered system-clipboard read
        (performed off the UI thread -- a subprocess call can take real
        time) actually comes back with something -- applies the same
        image-path-becomes-a-chip/paste-placeholder rule `_on_paste` uses
        for a real terminal paste, then inserts at the current selection/
        cursor, exactly like TextArea's own built-in paste."""
        if self.read_only or not text:
            return
        display_text = self._text_or_image_chip_for(text)
        if result := self._replace_via_keyboard(display_text, *self.selection):
            self.move_cursor(result.end_location)
        self._auto_grow()

    # ---- Backspace removes the last pending image chip (2.0.3.1) --------

    def action_delete_left(self) -> None:
        """A bare Backspace normally deletes one character left -- when the
        WHOLE input is nothing but already-inserted image chip labels (no
        other real text typed), it instead pops the last pending
        attachment and its own label, so an unwanted paste is one
        keystroke to undo, the same as `/images clear`
        (`tui/slash.py::_handle_images`) -- which reuses this exact
        "chip-only text" condition. Any other input (real text present, no
        pending images at all) is completely unaffected -- the ordinary
        TextArea behavior runs unchanged."""
        if self.images and self.text == "".join(self._chip_labels()):
            self.images.pop()
            self.text = "".join(self._chip_labels())
            self.move_cursor((0, len(self.text)))
            self._auto_grow()
            return
        super().action_delete_left()

    # ---- / and @ completion ------------------------------------------

    def _maybe_query_completion(self) -> None:
        from halo_harness.tui.completion import current_token

        row, col = self.cursor_location
        line = self.document.get_line(row)
        kind, _start, token = current_token(line, col)
        if kind and row == 0:
            self.post_message(self.CompletionQuery(kind, token))
        else:
            self.post_message(self.CompletionDismissed())

    def action_accept_completion(self) -> None:
        self.post_message(self.CompletionQuery("accept", ""))

    def replace_current_token(self, kind: str, replacement: str) -> None:
        """Replace the `/`- or `@`-prefixed token under the cursor (on the
        first line only, matching `_maybe_query_completion`) with
        `replacement` -- called by app.py after the user accepts a
        completion candidate. Halo 2.0.2 brief A.4: `kind == "arg"` (a
        `/role`/`/roles set` ARGUMENT -- role name, model ref, or effort
        level) carries no prefix character of its own, unlike "slash"
        (`/`) and "at" (`@`)."""
        from halo_harness.tui.completion import current_token

        row, col = self.cursor_location
        line = self.document.get_line(row)
        _kind, start, _token = current_token(line, col)
        prefix_char = "/" if kind == "slash" else ("@" if kind == "at" else "")
        self.replace(f"{prefix_char}{replacement}", (row, start), (row, col))
        self._auto_grow()

    # ---- completion popup Up/Down, else history Up/Down (only at the
    # first/last line -- see app.py) ----------------------------------------

    def action_cursor_up(self, select: bool = False) -> None:
        # 1.0.1 hotfix 1: checked BEFORE the history-nav row==0 check below
        # -- the popup only ever opens while typing on row 0 (`_maybe_
        # query_completion`'s own `row == 0` gate), so without this the
        # TextArea's normal "at the top line, Up means history" behavior
        # fired instead, and the popup's own highlight never moved.
        if self._completion_open and not select:
            self.post_message(self.CompletionNav(-1))
            return
        row, _col = self.cursor_location
        if row == 0 and not select:
            self.post_message(self.HistoryNav(-1))
            return
        super().action_cursor_up(select)

    def action_cursor_down(self, select: bool = False) -> None:
        if self._completion_open and not select:
            self.post_message(self.CompletionNav(1))
            return
        row, _col = self.cursor_location
        if row == self.document.line_count - 1 and not select:
            self.post_message(self.HistoryNav(1))
            return
        super().action_cursor_down(select)

    # ---- PgUp/PgDn scroll the transcript, never the (usually one-line)
    # prompt (D-TUI: "PgUp/PgDn ... scroll") -------------------------------

    def action_cursor_page_up(self) -> None:
        transcript = getattr(self.app, "transcript", None)
        if transcript is not None:
            transcript.scroll_page_up()
        else:
            super().action_cursor_page_up()

    def action_cursor_page_down(self) -> None:
        transcript = getattr(self.app, "transcript", None)
        if transcript is not None:
            transcript.scroll_page_down()
        else:
            super().action_cursor_page_down()
