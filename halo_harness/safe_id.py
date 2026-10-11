"""halo_harness.safe_id -- identifiers that become file names (2.0.10 review,
finding 25).

Two kinds of id reach a path join:

  * a CLI / caller supplied SESSION id (`--resume <id>`, `SessionLog(cwd,
    session_id=...)`): validated, and a bad one is rejected with a clear
    error (`validate_session_id`);
  * a provider supplied `tool_use_id` (any string the upstream chose, such
    as `functions.Read:0`): turned into a safe file stem
    (`safe_file_stem`), because refusing the id would drop a legitimate
    tool call.

Neither ever lets a separator, a drive colon or a leading dot reach
`Path / name`.
"""
from __future__ import annotations

import re

_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_UNSAFE_RE = re.compile(r"[^A-Za-z0-9._-]")


def is_safe_session_id(value) -> bool:
    return isinstance(value, str) and bool(_SESSION_ID_RE.match(value))


def validate_session_id(value) -> str:
    """Return `value` when it is a safe session id, else raise ValueError
    with a message that says what is accepted."""
    if not is_safe_session_id(value):
        raise ValueError(
            f"invalid session id {value!r}: use 1-128 letters, digits, '.', '_' or '-' "
            "(starting with a letter or digit); path separators are not allowed")
    return value


def safe_file_stem(value, default: str = "unnamed") -> str:
    """A file-name stem derived from an arbitrary id: every character outside
    `A-Za-z0-9._-` becomes `_`, a leading dot becomes `_`, the length is
    capped at 128, and an empty id becomes `default`."""
    text = _UNSAFE_RE.sub("_", str(value or ""))
    if text.startswith("."):
        text = "_" + text[1:]
    return text[:128] or default
