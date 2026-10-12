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
and shift bits never cause a drop. `install()` swaps Textual's monitor
for a subclass whose `run` applies the rule; everything else in the loop
is Textual's own code, kept line for line.
"""

from __future__ import annotations

import sys

ALT_OR_CTRL = 0x0001 | 0x0002 | 0x0004 | 0x0008   # RIGHT_ALT, LEFT_ALT, RIGHT_CTRL, LEFT_CTRL


def keep_key_record(char: str, vkey: int, control_state: int) -> bool:
    """Whether a key-down console record carries a character the parser
    should see. Pure, so it is unit-tested without a console."""
    if not char:
        return False
    if vkey == 0 and (control_state & ALT_OR_CTRL):
        return False
    return True


_INSTALLED = False


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
                while not exit_requested():
                    for event in parser.tick():
                        self.process_event(event)
                    if win32.wait_for_handles([hIn], 100) is None:
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
                        for event in parser.feed("".join(keys).encode("utf-16", "surrogatepass").decode("utf-16")):
                            self.process_event(event)
                    if new_size is not None:
                        self.on_size_change(*new_size)
            except Exception as error:  # the same catch Textual's own loop has
                self.app.log.error("EVENT MONITOR ERROR", error)

    win32.EventMonitor = HaloEventMonitor
    _INSTALLED = True
    return True
