"""halo_harness.tui.widgets.input_sanitize -- text hygiene at the terminal's
edge, both directions.

In: terminal mouse reports that reach the prompt as text (Halo 3.0.2.0). The
Windows driver fix in tui/win32_input.py removes the cause; this is the belt
for any terminal that still lets a report through: an SGR mouse report is
`ESC [ < b ; x ; y M` (or `m` on release), and what lands in a text box when
the ESC is lost is `[<35;72;18M`. Only the report SHAPE is matched (a `<`
lead, or three numbers not following a `[`), so an SGR colour literal such as
`\\033[1;31m` or a `PS1` definition is ordinary text.

Out: `display_safe` turns control characters in text Halo did not write
(tool output, model text, file contents) into visible symbols, so an escape
sequence inside them is shown, never executed by the terminal.
`SafeStatic` is a `Static` that applies it to everything it renders.
"""

from __future__ import annotations

import re
from typing import Optional

from rich.text import Text
from textual.widgets import Static

_SHAPE = r"(?:\[?<\d{1,3}(?:;\d{1,3}){1,2}|(?<![\[\d;])\d{1,3};\d{1,3};\d{1,3})[Mm]"
_REPORT = re.compile(_SHAPE)
_REPORT_AT_END = re.compile(_SHAPE + r"$")


def looks_like_mouse_report(text: str) -> bool:
    return bool(_REPORT.search(text))


def strip_mouse_reports(text: str) -> str:
    """`text` without any mouse-report fragments."""
    return _REPORT.sub("", text) if text else text


def report_start_before(text: str) -> Optional[int]:
    """Where a mouse report that ends exactly at the end of `text` starts, or
    None. The prompt checks only the text left of the cursor when a final
    `M`/`m` is typed, so nothing elsewhere in the box is ever touched."""
    match = _REPORT_AT_END.search(text) if text else None
    return match.start() if match else None


# Every C0 control except TAB, LF and CR (Textual drops CR, BEL, BS, VT and FF
# itself), DEL, and the C1 range (0x9b is a one-byte CSI). Each maps to ONE
# visible character, so a Rich Text's style spans still line up afterwards.
_UNSAFE = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


def _visible(match: "re.Match[str]") -> str:
    code = ord(match.group())
    if code < 0x20:
        return chr(0x2400 + code)  # the Control Pictures block: ESC -> U+241B
    if code == 0x7F:
        return "␡"
    return "�"


def display_safe(text: str) -> str:
    """`text` with every control character a terminal would act on replaced
    by a visible symbol of the same length."""
    if not text or not _UNSAFE.search(text):
        return text
    return _UNSAFE.sub(_visible, text)


def display_safe_content(content):
    """`display_safe` for whatever a Static is handed: a str, a Rich Text
    (spans kept), anything else unchanged."""
    if isinstance(content, str):
        return display_safe(content)
    if isinstance(content, Text):
        plain = content.plain
        safe = display_safe(plain)
        if safe is not plain and safe != plain:
            content = content.copy()
            content.plain = safe
    return content


class SafeStatic(Static):
    """A Static whose content always goes through `display_safe_content`."""

    def __init__(self, content="", *args, **kwargs) -> None:
        super().__init__(display_safe_content(content), *args, **kwargs)

    def update(self, content="", *args, **kwargs) -> None:
        return super().update(display_safe_content(content), *args, **kwargs)
