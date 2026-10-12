"""halo_harness.tui.widgets.input_sanitize -- strip terminal mouse reports
that reach the prompt as text (Halo 3.0.2.0). The Windows driver fix in
tui/win32_input.py removes the cause; this is the belt for any terminal
that still lets a report through: an SGR mouse report is `ESC [ < b ; x ;
y M` (or `m` on release), and what lands in a text box when the ESC is
lost is `[<35;72;18M`, or a tail of it such as `8;17M`.
"""

from __future__ import annotations

import re

# A whole report with its lead lost, or a tail cut inside the parameters:
# optional "[<", one to three numbers, a final M/m. A person typing
# "3;4M" on purpose is rare enough to accept.
_REPORT = re.compile(r"\[?<?\d{1,3}(?:;\d{1,3}){1,2}[Mm]")


def looks_like_mouse_report(text: str) -> bool:
    return bool(_REPORT.search(text))


def strip_mouse_reports(text: str) -> str:
    """`text` without any mouse-report fragments."""
    return _REPORT.sub("", text) if text else text
