"""halo_harness.permissions_paths -- Halo 3.3.13.1 (plans/REVIEW-2026-11.md #2, PERMS-2): Windows spellings of a
local file that a drive-anchored path rule missed. With `Read(.env)` denied, `\\\\?\\C:\\<proj>\\.env` and
`\\\\localhost\\C$\\<proj>\\.env` decided allow and the Read tool returned the file.

    plain_drive(posix, windows=None) -> str
        `//?/C:/x` and `//./C:/x` -> `C:/x`; `//?/UNC/host/share/x` -> `//host/share/x`, then
        `//localhost/C$/x`, `//127.0.0.1/C$/x`, `//[::1]/C$/x` and `//<this host>/C$/x` -> `C:/x`
        (permissions._abs_posix runs every target and rule base through it on Windows)
    unc_ask(engine, tool_name, tool_input, tool) -> Rule | None
        any other `\\\\`-rooted path for a path tool, while a deny or ask path rule exists that covers that tool:
        the rule the call is asked about (the engine cannot tell which file a network path names)
"""

from __future__ import annotations

import dataclasses
import os
import re
import socket
from typing import Optional

_LONG_UNC = re.compile(r"^//[?.]/UNC/(.*)$", re.IGNORECASE)
_LONG_DRIVE = re.compile(r"^//[?.]/([A-Za-z]:(?:/.*)?)$")
_ADMIN_SHARE = re.compile(r"^//([^/]+)/([A-Za-z])\$(/.*)?$")
_PATH_KEYS = ("file_path", "path", "notebook_path")


def _this_host() -> set:
    names = {"localhost", "127.0.0.1", "[::1]", "::1"}
    try:
        host = socket.gethostname()
        names |= {host.lower(), host.split(".")[0].lower()}
    except OSError:
        pass
    return names


def plain_drive(s: str, windows: Optional[bool] = None) -> str:
    """A posix-style absolute path with the long-path and this machine's admin-share prefixes taken off."""
    if not (os.name == "nt" if windows is None else windows) or not s.startswith("//"):
        return s
    m = _LONG_UNC.match(s)
    if m:
        s = "//" + m.group(1)
    else:
        m = _LONG_DRIVE.match(s)
        if m:
            return m.group(1)
    m = _ADMIN_SHARE.match(s)
    if m and m.group(1).lower() in _this_host():
        return f"{m.group(2).upper()}:{m.group(3) or '/'}"
    return s


def _raw_path(tool_input, tool) -> str:
    if tool is not None:
        try:
            got = tool.permission_content(tool_input)
            if isinstance(got, str) and got:
                return got
        except Exception:
            pass
    for key in _PATH_KEYS:
        v = tool_input.get(key) if isinstance(tool_input, dict) else None
        if isinstance(v, str) and v:
            return v
    return ""


def unc_ask(engine, tool_name: str, tool_input, tool, *, windows: Optional[bool] = None):
    """The rule to ask about for a network path the engine cannot map to a drive, or None."""
    if not (os.name == "nt" if windows is None else windows):
        return None
    from halo_harness.permissions import _applicable_path_rule_source_tools
    raw = _raw_path(tool_input, tool)
    s = raw.replace("\\", "/")
    if not s.startswith("//") or not plain_drive(s, True).startswith("//"):
        return None
    for rules, action in ((engine.deny_rules, "deny"), (engine.ask_rules, "ask")):
        tools = _applicable_path_rule_source_tools(tool_name, action)
        hit = next((r for r in rules if r.kind == "path" and r.tool in tools and not r.negated), None)
        if hit is not None:
            return dataclasses.replace(hit, raw=f"{hit.raw}; {raw[:120]} is a network path that cannot be matched "
                                                f"to a drive, so the call is asked")
    return None
