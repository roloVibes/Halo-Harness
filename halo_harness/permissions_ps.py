r"""halo_harness.permissions_ps -- Read / Edit path rules gate the PowerShell tool's readers and writers (Halo 3.3.14.0
R2, REVIEW #13 PERMS-7; the Bash half is permissions.py `_bash_read_deny_hit` / `_bash_write_deny_hit`).

    read_hit(engine, command, action="deny") -> Rule | None    a reader (Get-Content / cat / gc / type, Select-String,
        Import-Csv, Copy-Item's source, Move-Item's source, [IO.File]::Read* / Open* / Copy) on a path a Read rule of
        `action` names; a recursive Copy-Item walks its folder (bounded)
    write_hit(engine, command) -> Rule | None   a writer (Set-Content, Add-Content, Out-File, Clear-Content, New-Item,
        Remove-Item, Copy-Item / Move-Item, `>` / `>>` redirections, [IO.File]::Write* / Append* / Delete / Move / ...) on
        a path an Edit / Write deny rule names

Each segment (`;`, `|`, `&&`, script blocks, `powershell -Command` / `cmd /c` payloads) is read with the cwd in effect
at its point (`cd` / `Set-Location` / `sl` / `pushd` move it; an unresolvable one leaves relative words unchecked, as
for Bash). `~`, `$HOME`, `$env:USERPROFILE`, `$PWD` expand; a word with any other `$` is taken to hit the first rule (it
cannot be checked). `\\?\` and `\\host\C$\` spellings are normalised by the engine's path matcher. Nothing runs when
no Read / Edit path rule exists.
"""

from __future__ import annotations

import glob as _glob
import os
import re
from pathlib import Path
from typing import Optional

from halo_harness import perm_ps as _pa

READERS = {"get-content", "select-string", "import-csv", "copy-item", "move-item",
           "format-hex", "fhx", "import-clixml", "import-powershelldatafile", "rename-item", "ren", "rni"}  # 3.4.1.2
WRITERS = {"set-content", "add-content", "out-file", "clear-content", "new-item", "remove-item", "copy-item",
           "move-item", "tee-object", "tee", "rename-item", "ren", "rni", "export-clixml", "export-csv"}  # 3.4.1.2
#: 3.4.1.2 (ENGINE-4): `Get-Item .env | Get-Content` -- an item cmdlet's path read by the reader it is piped into
_ITEM = {"get-item", "gi", "get-childitem", "resolve-path", "rvpa", "get-itemproperty"}
_PIPED_READER = re.compile(r"\|\s*(?:get-content|gc|cat|type|format-hex|fhx|select-string|sls|import-csv|ipcsv|"
                           r"import-clixml)\b", re.IGNORECASE)
_DRIVE_VAR = re.compile(r"\$\{([A-Za-z]:[^}]*)\}")  # `${C:\path}` reads (or, assigned, writes) the file
_NEWIO = re.compile(r"""(?:\[(?:System\.)?IO\.(\w+)\]::new|New-Object\s+(?:-TypeName\s+)?(?:System\.)?IO\.(\w+)"""
                    r"""(?:\s+-ArgumentList)?)\s*\(?\s*("[^"]*"|'[^']*')""", re.IGNORECASE)
_IO_READ = {"streamreader", "filestream", "binaryreader", "fileinfo"}
_IO_WRITE = {"streamwriter", "filestream", "binarywriter"}
_CD = {"set-location", "push-location", "pushd"}
_NOT_PATHS = {"-value", "-encoding", "-pattern", "-totalcount", "-tail", "-head", "-first", "-delimiter", "-filter",
              "-include", "-exclude", "-stream", "-inputobject", "-itemtype", "-type", "-readcount", "-width",
              "-variable", "-count", "-offset", "-depth"}
_SWITCHES = {"-raw", "-force", "-recurse", "-wait", "-nonewline", "-append", "-noclobber", "-passthru", "-asbytestream",
             "-whatif", "-confirm", "-simplematch", "-casesensitive", "-quiet", "-list", "-notmatch", "-allmatches",
             "-container"}
_REDIRECT = re.compile(r"""(?:^|[\s;|])[1-6*]?>>?\s*("[^"]*"|'[^']*'|[^\s;|&>]+)""")
_IOFILE = re.compile(r"""\[(?:System\.)?IO\.File\]::(\w+)\(([^)]*)\)""", re.IGNORECASE)
_STR = re.compile(r""""([^"]*)"|'([^']*)'""")
_SHARE = re.compile(r"^[\\/]{2}(?:\?[\\/]UNC[\\/])?[^\\/]+[\\/][A-Za-z]\$(?=[\\/]|$)", re.IGNORECASE)


def _head(tokens: list) -> str:
    from halo_harness.permissions import canonicalize_powershell
    return canonicalize_powershell(_pa._unquote(tokens[0])).split()[0].lower() if tokens else ""


def _args(tokens: list) -> "tuple[list, list, bool]":
    """(the words that may name a path, the -Destination words, -Recurse given)."""
    out, dest, recurse, take = [], [], False, None
    for tok in tokens:
        words = [w for w in _pa._unquote(tok).split(",") if w.strip()]
        if take is not None:
            (dest if take == "-destination" else out).extend(words if take not in _NOT_PATHS else [])
            take = None
            continue
        low = tok.lower()
        if low.startswith("-") and len(low) > 1 and not low[1].isdigit():
            name, colon, glued = low.partition(":")
            recurse = recurse or name == "-recurse"
            if colon and name not in _NOT_PATHS:
                (dest if name == "-destination" else out).append(tok.split(":", 1)[1])
            elif not colon and name not in _SWITCHES:
                take = name  # the next word is its value: checked unless the parameter takes no path
            continue
        out += words
    return out, dest, recurse


def _expand(word: str, cwd) -> str:
    w = word.strip().strip("'\"")
    home = os.path.expanduser("~")
    for pre in ("${env:USERPROFILE}", "$env:USERPROFILE", "${env:HOME}", "$env:HOME", "${HOME}", "$HOME", "~"):
        if w == pre or w.lower().startswith(pre.lower() + "/") or w.lower().startswith(pre.lower() + "\\"):
            return home + w[len(pre):]
    for pre in ("${PWD}", "$PWD", "$pwd"):
        if cwd is not None and (w == pre or w.startswith((pre + "/", pre + "\\"))):
            return str(cwd) + w[len(pre):]
    return w


def _targets(word: str, cwd) -> "Optional[list]":
    """The paths a word names ([] when it cannot be resolved here, None when it is opaque: `$var`)."""
    w = _expand(word, cwd)
    if not w or w in ("-", "&1", "&2", "$null"):
        return []
    if any(ch in _SHARE.sub("", w) for ch in "$`"):  # an admin share's `C$` is a name, not a variable
        return None
    if os.name != "nt":
        w = w.replace("\\", "/")
    rooted = Path(w).is_absolute() or w.startswith(("/", "\\"))
    if not rooted and cwd is None:
        return []
    full = w if rooted else str(Path(cwd) / w)
    if any(ch in w for ch in "*?["):
        return _glob.glob(full)[:200]
    return [full]


def _units(command: str, cwd, depth: int = 0) -> list:
    from halo_harness.permissions import split_powershell_segments
    out = []
    for seg in split_powershell_segments(command):
        tokens = _pa._tokens(_pa.clean_head(seg))
        if _head(tokens) in _CD:
            words = _args(tokens[1:])[0]
            if words:
                got = _targets(words[0], cwd)
                cwd = Path(got[0]) if got else None
            continue
        out.append((seg, cwd))
        if depth < 3:
            for payload in _pa.payloads(seg) + _pa.start_process_targets(seg):
                out += _units(payload, cwd, depth + 1)
    if depth < 3:
        for body in _pa.bodies(command):
            out += _units(body, cwd, depth + 1)
    return out


def _words(seg: str, cwd, read: bool, command: str = "") -> "tuple[list, bool]":
    """(words naming a path this segment reads (`read`) or writes, whether a folder operand is walked)."""
    tokens = _pa._tokens(_pa.clean_head(seg))
    head, words, walk = _head(tokens), [], False
    if head in (READERS if read else WRITERS):
        args, dest, recurse = _args(tokens[1:])
        if head in ("copy-item", "move-item"):
            if not dest and len(args) > 1:
                args, dest = args[:-1], args[-1:]
            # a copy reads its sources and writes its destination; a move also takes its sources away
            args = args if read else dest + (args if head == "move-item" else [])
        words, walk = args, read and head == "copy-item" and recurse
        if head in ("rename-item", "ren", "rni") and len(args) > 1:  # the new name sits beside the item
            words = args[:1] if read else args[:1] + [str(Path(_pa._unquote(args[0])).parent / _pa._unquote(args[1]))]
    elif read and head in _ITEM and _PIPED_READER.search(command or ""):
        words = _args(tokens[1:])[0]
    if not read:
        words += [m for m in _REDIRECT.findall(seg)]
    words += _DRIVE_VAR.findall(seg) if (read or re.search(r"\$\{[A-Za-z]:[^}]*\}\s*=(?!=)", seg)) else []
    for kind_a, kind_b, name in _NEWIO.findall(seg):
        if (kind_a or kind_b).lower() in (_IO_READ if read else _IO_WRITE):
            words.append(name)
    for method, inner in _IOFILE.findall(seg):
        m = method.lower()
        names = [a or b for a, b in _STR.findall(inner)]
        if read and (m.startswith(("read", "open")) or m == "copy"):
            words += names[:1]
        if not read and not m.startswith(("read", "exists", "get")):
            words += names if m in ("move", "replace") else names[-1:] if m == "copy" else names[:1]
    return words, walk


def _hit(engine, command: str, rules: list, tool: str, action: str, read: bool):
    for seg, cwd in _units(command, engine.cwd):
        words, walk = _words(seg, cwd, read, command)
        for word in words:
            paths = _targets(word, cwd)
            if paths is None:  # `$var`: a reader's path cannot be checked, so it counts as a hit (as for Bash)
                if read:
                    return rules[0]
                continue
            for p in paths:
                hit = engine._path_rule_hit(rules, tool, {"file_path": p}, None, action=action)
                if hit is None and walk:
                    hit = engine._dir_rule_hit(rules, Path(p), action)
                if hit is not None:
                    return hit
    return None


def read_hit(engine, command: str, action: str = "deny"):
    rules = [r for r in (engine.deny_rules if action == "deny" else engine.ask_rules) if r.kind == "path"
             and r.tool == "Read"]
    return _hit(engine, command, rules, "Read", action, True) if rules else None


def write_hit(engine, command: str):
    rules = [r for r in engine.deny_rules if r.kind == "path" and r.tool in ("Edit", "Write")]
    return _hit(engine, command, rules, "Edit", "deny", False) if rules else None
