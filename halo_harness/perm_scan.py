"""halo_harness.perm_scan -- quote-aware Bash text scanners for the DENY/ASK
side of the permission engine (3.0.2.0 review fix pass, round A).

Leaf module (no import of permissions.py). Everything here only finds the
text a shell would really run or read: heredoc openers and bodies, the
inner text of `$( )` / backtick / `( )` / `{ ...; }` / `<( )` spans that are
NOT inside a quoted string or a `#` comment (word-level helpers live in
perm_words.py). Nothing here judges a command.
"""
from __future__ import annotations

_COMMENT_AFTER = " \t\n;&|()"


# ---- heredocs --------------------------------------------------------------

def heredoc_opener(command: str, start: int):
    """`command[start:]` begins with `<<[-]DELIM` (DELIM optionally quoted):
    return (index just past the delimiter word, DELIM, strip_tabs), or None
    when this is not a heredoc opener (a `<<<` here-string, no delimiter)."""
    n = len(command)
    if command[start:start + 3] == "<<<":
        return None
    j = start + 2
    strip_tabs = j < n and command[j] == "-"
    if strip_tabs:
        j += 1
    while j < n and command[j] in " \t":
        j += 1
    if j >= n:
        return None
    if command[j] in ("'", '"'):
        quote = command[j]
        end_quote = command.find(quote, j + 1)
        if end_quote == -1:
            return None
        delim = command[j + 1:end_quote]
        j = end_quote + 1
    else:
        k = j
        while j < n and not command[j].isspace() and command[j] not in "&|;":
            j += 1
        delim = command[k:j].lstrip("\\")
    if not delim:
        return None
    return j, delim, strip_tabs


def heredoc_body_end(command: str, body_start: int, delim: str, strip_tabs: bool) -> int:
    """Index just past the body's closing delimiter LINE (EOF when the
    heredoc is never closed)."""
    n = len(command)
    k = body_start
    while k <= n:
        line_end = command.find("\n", k)
        line = command[k:line_end if line_end != -1 else n]
        probe = line.lstrip("\t") if strip_tabs else line
        if probe == delim:
            return (line_end + 1) if line_end != -1 else n
        if line_end == -1:
            return n
        k = line_end + 1
    return n


# ---- quote- and comment-aware span bodies ----------------------------------

def _comment_starts(cmd: str, i: int) -> bool:
    return cmd[i] == "#" and (i == 0 or cmd[i - 1] in _COMMENT_AFTER)


def _skip_backtick(cmd: str, i: int) -> int:
    k = cmd.find("`", i + 1)
    return k + 1 if k != -1 else len(cmd)


def close_paren(cmd: str, j: int) -> int:
    """Index of the `)` closing a `(`/`$(` whose body starts at `j` (a fresh
    quoting context), or len(cmd) when it is never closed."""
    depth, i, n = 1, j, len(cmd)
    in_s = in_d = False
    while i < n:
        c = cmd[i]
        if in_s:
            in_s = c != "'"
            i += 1
            continue
        if c == "\\":
            i += 2
            continue
        if in_d:
            if c == '"':
                in_d = False
            elif cmd.startswith("$(", i):
                i = close_paren(cmd, i + 2) + 1
                continue
            elif c == "`":
                i = _skip_backtick(cmd, i)
                continue
            i += 1
            continue
        if c == "'":
            in_s = True
        elif c == '"':
            in_d = True
        elif c == "`":
            i = _skip_backtick(cmd, i)
            continue
        elif _comment_starts(cmd, i):
            nl = cmd.find("\n", i)
            i = nl if nl != -1 else n
            continue
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return n


def _close_brace(cmd: str, j: int) -> int:
    """Index of the `}` closing a `{ ` group whose body starts at `j`, or -1."""
    depth, i, n = 1, j, len(cmd)
    in_s = in_d = False
    while i < n:
        c = cmd[i]
        if in_s:
            in_s = c != "'"
        elif c == "\\":
            i += 2
            continue
        elif in_d:
            in_d = c != '"'
        elif c == "'":
            in_s = True
        elif c == '"':
            in_d = True
        elif c == "(" or cmd.startswith("$(", i):
            i = close_paren(cmd, i + (2 if c == "$" else 1)) + 1
            continue
        elif c == "`":
            i = _skip_backtick(cmd, i)
            continue
        elif _comment_starts(cmd, i):
            nl = cmd.find("\n", i)
            i = nl if nl != -1 else n
            continue
        elif c == "{" and cmd[i + 1:i + 2] in (" ", "\t", "\n", ";"):
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def span_bodies(command: str, _depth: int = 0, *, nested: bool = True) -> "tuple[list, list]":
    """(substitution bodies, group bodies) of `command`, nested ones
    included unless `nested=False`: `$( )` and backtick spans (also inside
    double quotes), and `( )`, `<( )`, `>( )`, `{ ...; }` groups (never
    inside quotes). Single-quoted text and `#` comments contribute nothing."""
    subs: list = []
    groups: list = []
    i, n = 0, len(command)
    in_s = in_d = False

    def _take(body: str, into: list) -> None:
        into.append(body)
        if nested and _depth < 6:
            inner_subs, inner_groups = span_bodies(body, _depth + 1)
            subs.extend(inner_subs)
            groups.extend(inner_groups)

    while i < n:
        c = command[i]
        if in_s:
            in_s = c != "'"
            i += 1
            continue
        if c == "\\":
            i += 2
            continue
        if command.startswith("$(", i):
            end = close_paren(command, i + 2)
            _take(command[i + 2:end], subs)
            i = end + 1
            continue
        if c == "`":
            k = command.find("`", i + 1)
            if k == -1:
                break
            _take(command[i + 1:k], subs)
            i = k + 1
            continue
        if in_d:
            in_d = c != '"'
            i += 1
            continue
        if c == "'":
            in_s = True
        elif c == '"':
            in_d = True
        elif _comment_starts(command, i):
            nl = command.find("\n", i)
            i = nl if nl != -1 else n
            continue
        elif c == "(" or (c in "<>" and command[i + 1:i + 2] == "("):
            start = i + (1 if c == "(" else 2)
            end = close_paren(command, start)
            _take(command[start:end], groups)
            i = end + 1
            continue
        elif c == "{" and command[i + 1:i + 2] in (" ", "\t", "\n", ";"):
            end = _close_brace(command, i + 1)
            if end != -1:
                _take(command[i + 1:end], groups)
                i = end + 1
                continue
        i += 1
    return [b for b in subs if b.strip()], [b for b in groups if b.strip()]
