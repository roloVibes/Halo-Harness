"""halo_harness.tui.win32_input -- keep terminal mouse reports out of the
prompt on Windows (Halo 3.0.2.0).

Textual's Windows input thread (`textual.drivers.win32.EventMonitor.run`)
reads console records and skips any KEY_EVENT whose virtual-key code is
zero while any bit of `dwControlKeyState` is set. ConPTY delivers the VT
mouse reports the terminal sends (`ESC [ < 35 ; 72 ; 18 M`, a mouse move)
as synthetic key records: the lead ESC has a zero virtual-key code, and
the control state carries the LOCK keys too (NumLock 0x20, ScrollLock
0x40, CapsLock 0x80). With NumLock on, the ESC of every report is dropped
and the rest of the report -- `[<35;72;18M` -- reaches the prompt as typed
text, dozens of times a second while the mouse moves. The owner saw
exactly that on 2026-10-11.

`keep_key_record` is the corrected rule: a record is skipped only when its
virtual-key code is zero AND an Alt or Ctrl modifier is actually held (the
case the original check meant: the noise around Alt+numpad entry). Lock
and shift bits never cause a drop.

That alone was not enough (the owner still saw `[<35;72;18M`, `8;17M`,
`;93;17M` on 2026-10-12, with the filter in place). A console probe showed
every record arriving clean, so the loss is in the hand-off, not the
filter: Textual's parser gives up on an escape sequence 100 ms after its
last character (`ESCDELAY`), and a report that straddles two reads of the
console while the main thread is busy (startup: the catalog, the MCP
servers, the intro) is fed as `ESC` and then, after the delay, its tail
as typed text. A console whose input mode flips mid-report (a child
process that inherits it) hands over the tail alone. `PendingInput` sits
between the console and the parser: a trailing incomplete sequence is
held until the rest arrives (or the console goes quiet, for a real Esc),
and a batch that is nothing but orphaned report tails is dropped before
the parser can type it. `install()` swaps Textual's monitor for a
subclass whose `run` applies both; everything else in the loop is
Textual's own code, kept line for line.

3.1.3.0 (fragments again on 2026-10-19): a quiet console used to release a
held PARTIAL report after 30 ms, and the parser types it -- on a loaded
machine the halves of a report can be that far apart. Now only a lone ESC
is released on quiet (a real Esc); a held report head (`ESC [ <` + digits)
waits up to `HEAD_PATIENCE_S` for its tail, then is dropped, never typed,
and a head left in a batch (its tail lost to a console-mode flip) goes the
same way. `SizeSettle` lets a window drag settle for `SETTLE_S` before one
Resize reaches Textual (a full screen layout per size record before).
`HALO_INPUT_TRACE=<file>` appends every raw batch and what the parser got.
"""

from __future__ import annotations

import os
import re
import sys
import time

ALT_OR_CTRL = 0x0001 | 0x0002 | 0x0004 | 0x0008   # RIGHT_ALT, LEFT_ALT, RIGHT_CTRL, LEFT_CTRL


def keep_key_record(char: str, vkey: int, control_state: int) -> bool:
    """Whether a key-down console record carries a character the parser
    should see. Pure, so it is unit-tested without a console."""
    if not char:
        return False
    if vkey == 0 and (control_state & ALT_OR_CTRL):
        return False
    return True


# a trailing ESC, `ESC [` + parameter bytes with no final byte, or `ESC O`
_INCOMPLETE_TAIL = re.compile(r"\x1b(?:\[[<?\d;:\-]*|O)?\Z")
_COMPLETE_REPORT = re.compile(r"\x1b\[<\d{1,3};\d{1,3};\d{1,3}[Mm]")
# what is left of a batch of mouse reports once the complete ones are
# taken out, when all of it is report tails: "[<35;72;18M", "8;17M", ";93;17M"
_ORPHAN_TAILS = re.compile(r"^(?:\[?<?[\d;]*;\d{1,3}[Mm])+$")
# a report head (`ESC [ <` + digits) that never got its tail: it ends the
# batch or runs straight into the next escape. Nobody types `ESC [ <`.
_STRAY_HEAD = re.compile(r"\x1b\[<[\d;]*(?=\x1b|\Z)")
_REPORT_HEAD = re.compile(r"\x1b\[<[\d;]*\Z")
HEAD_PATIENCE_S = 2.0   # how long a held report head waits for its tail
SETTLE_S = 0.06         # a window drag is over when no size record came for this long


def drop_orphan_tails(text: str) -> str:
    """A batch whose non-report remainder is nothing but report tails
    loses the tails; any batch carrying real typed text is untouched
    (typed characters arrive one per read, so a human never produces
    a whole `7;18M` in one batch). A report head without its tail
    (3.1.3.0) goes whatever else is in the batch."""
    if not text:
        return text
    text = _STRAY_HEAD.sub("", text)
    rest = _COMPLETE_REPORT.sub("", text)
    if rest and _ORPHAN_TAILS.match(rest):
        return "".join(_COMPLETE_REPORT.findall(text))
    return text


class PendingInput:
    """The stage between the console reads and Textual's parser (pure, so
    it is unit-tested with a replay through the real XTermParser)."""

    MAX_HELD = 64

    def __init__(self, clock=time.monotonic) -> None:
        self.held = ""
        self.held_since = 0.0
        self._clock = clock

    def push(self, text: str) -> str:
        """Prepend what was held, hold back an incomplete trailing
        sequence, return what the parser may see now."""
        text = self.held + text
        self.held = ""
        m = _INCOMPLETE_TAIL.search(text)
        if m is not None and len(text) - m.start() <= self.MAX_HELD:
            self.held = text[m.start():]
            self.held_since = self._clock()
            text = text[:m.start()]
        return drop_orphan_tails(text)

    def flush(self) -> str:
        """The console went quiet. A held lone ESC was a real Esc key and
        is released; a held report head keeps waiting for its tail (the
        other half of a split report can be tens of ms behind on a busy
        machine) and is dropped, never typed, once `HEAD_PATIENCE_S` is up;
        any other partial sequence is released as before."""
        if not self.held:
            return ""
        if _REPORT_HEAD.match(self.held):
            if self._clock() - self.held_since < HEAD_PATIENCE_S:
                return ""
            self.held = ""
            return ""
        held, self.held = self.held, ""
        return held


class SizeSettle:
    """The last window size seen, released once no new size has come for
    `SETTLE_S` (pure: the loop passes its own clock readings)."""

    def __init__(self) -> None:
        self.size = None
        self._deadline = 0.0

    def push(self, size, now: float) -> None:
        self.size = size
        self._deadline = now + SETTLE_S

    def due(self, now: float):
        """The settled size, once, or None while a drag is still moving."""
        if self.size is not None and now >= self._deadline:
            size, self.size = self.size, None
            return size
        return None


_INSTALLED = False


def _trace(path: str, raw: str, fed: str, held: str) -> None:
    """One line per console batch: what came in, what the parser got, what is held."""
    try:
        with open(os.path.expanduser(path), "a", encoding="utf-8") as fh:
            fh.write(f"{time.time():.3f} raw={raw!r} fed={fed!r} held={held!r}\n")
    except Exception:
        pass


def install() -> bool:
    """Patch Textual's Windows event monitor once; True when installed."""
    global _INSTALLED
    if _INSTALLED:
        return True
    if sys.platform != "win32":
        return False
    try:
        from textual.drivers import win32
    except Exception:
        return False
    base = getattr(win32, "EventMonitor", None)
    if base is None or getattr(base, "_halo_patched", False):
        return base is not None

    class HaloEventMonitor(base):  # type: ignore[misc, valid-type]
        _halo_patched = True

        def run(self) -> None:
            from ctypes import byref, wintypes
            from textual import constants
            from textual._xterm_parser import XTermParser
            exit_requested = self.exit_event.is_set
            parser = XTermParser(debug=constants.DEBUG)
            try:
                read_count = wintypes.DWORD(0)
                hIn = win32.GetStdHandle(win32.STD_INPUT_HANDLE)
                MAX_EVENTS = 1024
                KEY_EVENT = 0x0001
                WINDOW_BUFFER_SIZE_EVENT = 0x0004
                arrtype = win32.INPUT_RECORD * MAX_EVENTS
                input_records = arrtype()
                ReadConsoleInputW = win32.KERNEL32.ReadConsoleInputW
                keys: list = []
                append_key = keys.append
                pending = PendingInput()
                settle = SizeSettle()
                trace_path = os.environ.get("HALO_INPUT_TRACE", "")
                while not exit_requested():
                    for event in parser.tick():
                        self.process_event(event)
                    settled = settle.due(time.monotonic())
                    if settled is not None:
                        self.on_size_change(*settled)
                    if win32.wait_for_handles([hIn], 30 if (pending.held or settle.size) else 100) is None:
                        held = pending.flush()
                        if held:
                            for event in parser.feed(held):
                                self.process_event(event)
                        continue
                    ReadConsoleInputW(hIn, byref(input_records), MAX_EVENTS, byref(read_count))
                    read_input_records = input_records[: read_count.value]
                    del keys[:]
                    new_size = None
                    for input_record in read_input_records:
                        event_type = input_record.EventType
                        if event_type == KEY_EVENT:
                            key_event = input_record.Event.KeyEvent
                            if not key_event.bKeyDown:
                                continue
                            key = key_event.uChar.UnicodeChar
                            if keep_key_record(key, key_event.wVirtualKeyCode, key_event.dwControlKeyState):
                                append_key(key)
                        elif event_type == WINDOW_BUFFER_SIZE_EVENT:
                            size = input_record.Event.WindowBufferSizeEvent.dwSize
                            new_size = (size.X, size.Y)
                    if keys:
                        raw = "".join(keys).encode("utf-16", "surrogatepass").decode("utf-16")
                        text = pending.push(raw)
                        if trace_path:
                            _trace(trace_path, raw, text, pending.held)
                        if text:
                            for event in parser.feed(text):
                                self.process_event(event)
                    if new_size is not None:
                        settle.push(new_size, time.monotonic())
            except Exception as error:  # the same catch Textual's own loop has
                self.app.log.error("EVENT MONITOR ERROR", error)

    win32.EventMonitor = HaloEventMonitor
    _INSTALLED = True
    return True
