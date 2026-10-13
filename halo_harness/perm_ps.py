"""halo_harness.perm_ps -- PowerShell candidate expansion for deny/ask rules
(2.0.10 review, finding 12: "PowerShell's equivalents").

A PowerShell deny or ask rule (`PowerShell(Remove-Item:*)`) must hold when
the same cmdlet is reached through a script block (`if ($x) { rm y }`,
`ls | % { rm $_ }`), the call operator (`& rm x`, `& 'Remove-Item' x`), or
a nested interpreter (`powershell -Command "rm x"`, `cmd /c "del x"`).
Leaf module: only adds candidate strings, no allow-side effect, no
judgement about which commands are dangerous.
"""
from __future__ import annotations

import re

_TOKEN_RE = re.compile(r'"[^"]*"|\'[^\']*\'|\S+')
_NESTED = {"powershell", "powershell.exe", "pwsh", "pwsh.exe"}
_CMD = {"cmd", "cmd.exe"}
_OPAQUE_HEADS = {"invoke-expression", "iex"}
_OPAQUE_FLAGS = {"-encodedcommand", "-enc", "-ec", "-e"}
_COMMAND_FLAGS = {"-command", "-c", "-cmd"}


def _tokens(segment: str) -> list:
    return _TOKEN_RE.findall(segment.strip())


def _unquote(tok: str) -> str:
    if len(tok) >= 2 and tok[0] == tok[-1] and tok[0] in "'\"":
        return tok[1:-1]
    return tok


def bodies(command: str) -> list:
    """Inner text of every `{ ... }` script block, `( ... )` group and
    `$( ... )` subexpression, outermost first, nested ones included."""
    out: list = []
    pairs = {"{": "}", "(": ")"}
    stack: list = []
    in_single = in_double = False
    i, n = 0, len(command)
    while i < n:
        c = command[i]
        if in_single:
            in_single = c != "'"
        elif in_double:
            if c == "`":
                i += 1
            elif c == '"':
                in_double = False
        elif herestring_end(command, i) is not None:
            i = herestring_end(command, i)
            continue
        elif c == "'":
            in_single = True
        elif c == '"':
            in_double = True
        elif c == "`":
            i += 1
        elif c in pairs:
            stack.append((pairs[c], i + 1))
        elif stack and c == stack[-1][0]:
            _close, start = stack.pop()
            out.append(command[start:i])
        i += 1
    while stack:  # unterminated group: its tail is still a candidate
        _close, start = stack.pop()
        out.append(command[start:])
    return [b for b in out if b.strip()]


def clean_head(segment: str) -> str:
    """Drop leading call operators / block openers and trailing closers,
    and unquote a quoted command name: `& 'Remove-Item' x }` -> `Remove-Item x`."""
    seg = segment.strip().lstrip("&.{(").strip().rstrip("})").strip()
    m = re.match(r'^("[^"]*"|\'[^\']*\')(.*)$', seg, re.DOTALL)
    if m:
        seg = _unquote(m.group(1)) + m.group(2)
    return seg


def payloads(segment: str) -> list:
    """Command text a nested interpreter receives as a string."""
    toks = _tokens(clean_head(segment))
    if not toks:
        return []
    head = _unquote(toks[0]).replace("\\", "/").rsplit("/", 1)[-1].lower()
    out: list = []
    if head in _NESTED:
        for i, t in enumerate(toks[1:], start=1):
            if t.lower() in _COMMAND_FLAGS:
                out.append(_unquote(" ".join(toks[i + 1:])))
                break
    elif head in _CMD:
        for i, t in enumerate(toks[1:], start=1):
            if t.lower() in ("/c", "/k", "/r"):
                body = _unquote(" ".join(toks[i + 1:]))
                out.append(body)
                pieces = cmd_split(body)
                if len(pieces) > 1:
                    out.extend(pieces)
                break
    return out


def cmd_split(payload: str) -> list:
    """cmd.exe's own command separators in a `cmd /c` payload: unquoted
    `&`, `&&`, `||`, `|` (`^` escapes the next character)."""
    parts, buf = [], []
    in_q = False
    i, n = 0, len(payload)
    while i < n:
        c = payload[i]
        if c == '"':
            in_q = not in_q
        elif not in_q and c == "^" and i + 1 < n:
            buf.append(payload[i:i + 2])
            i += 2
            continue
        elif not in_q and c in "&|":
            parts.append("".join(buf))
            buf = []
            i += 2 if payload[i + 1:i + 2] == c else 1
            continue
        buf.append(c)
        i += 1
    parts.append("".join(buf))
    return [p.strip() for p in parts if p.strip()]


_HERESTRING_CLOSE = {'"': re.compile(r'\n[ \t]*"@'), "'": re.compile(r"\n[ \t]*'@")}


def herestring_end(command: str, i: int):
    """When `command[i:]` opens a here-string (`@"` or `@'` then a line
    break), the index just past its closing `"@`/`'@` (end of text when it
    is never closed); otherwise None."""
    if command[i:i + 1] != "@" or command[i + 1:i + 2] not in ('"', "'"):
        return None
    if command[i + 2:i + 3] not in ("\n", "\r"):
        return None
    m = _HERESTRING_CLOSE[command[i + 1]].search(command, i + 2)
    return m.end() if m else len(command)


_START_HEADS = {"start-process", "saps", "start"}
_START_SWITCHES = {"-nonewwindow", "-wait", "-passthru", "-usenewenvironment", "-loaduserprofile"}


def start_process_targets(segment: str) -> list:
    """`Start-Process rm -ArgumentList x` (also `saps`/`start`, `-FilePath`)
    -> [`rm x`]: the command Start-Process launches, with its arguments."""
    toks = _tokens(clean_head(segment))
    if not toks or _unquote(toks[0]).lower() not in _START_HEADS:
        return []
    cmd, args = None, []
    i = 1
    while i < len(toks):
        low = toks[i].lower()
        nxt = toks[i + 1] if i + 1 < len(toks) else None
        if low in ("-filepath", "-path", "-pspath") and nxt is not None:
            cmd, i = _unquote(nxt), i + 2
        elif low in ("-argumentlist", "-args") and nxt is not None:
            args += [_unquote(a.strip()) for a in nxt.split(",") if a.strip()]
            i += 2
        elif low in _START_SWITCHES:
            i += 1
        elif low.startswith("-"):
            i += 2
        elif cmd is None:
            cmd, i = _unquote(toks[i]), i + 1
        else:
            args += [_unquote(a.strip()) for a in toks[i].split(",") if a.strip()]
            i += 1
    return [" ".join([cmd] + args)] if cmd else []


def is_opaque(segment: str) -> bool:
    """`iex`/`Invoke-Expression`, `powershell -EncodedCommand ...`: the
    payload is a string (or base64) the matcher cannot scan."""
    toks = _tokens(clean_head(segment))
    if not toks:
        return False
    head = _unquote(toks[0]).replace("\\", "/").rsplit("/", 1)[-1].lower()
    if head in _OPAQUE_HEADS:
        return True
    if head in _NESTED:
        return any(t.lower() in _OPAQUE_FLAGS for t in toks[1:])
    return False
