"""halo_harness.numbered -- 3.6.0.1: the one rule for a number a person typed.

`str.isdigit()` is True for '²', '２' and '٢': `int('²')` then raises (a traceback at a numbered pick) and `int('２')`
quietly reads row 2. A number a person types here is ASCII 0-9 only, after the surrounding blanks are stripped:
no sign (unless the caller asks for one), no dot, no superscripts, no other script's digits.
"""

from __future__ import annotations

from typing import Optional


def whole_number(text, *, signed: bool = False) -> Optional[int]:
    """The int the text is, or None. `signed=True` also takes one leading ASCII '-' ('-1' -> -1); never a '+'."""
    if not isinstance(text, str):
        return None
    t = text.strip()
    neg = signed and t.startswith("-")
    digits = t[1:] if neg else t
    if not (digits and digits.isascii() and digits.isdigit()):
        return None
    return -int(digits) if neg else int(digits)


def pick(text, count: int) -> Optional[int]:
    """A numbered pick: the row number when the text is a whole number from 1 to `count`, else None."""
    n = whole_number(text)
    return n if n is not None and 1 <= n <= count else None
