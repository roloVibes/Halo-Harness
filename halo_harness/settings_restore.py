"""halo_harness.settings_restore -- put the user's own `model` key back in
Claude Code's settings.json after a proxy launch (the launch hands claude a
private --settings file, so the real file is only ever touched to undo a
child that rewrote its `model`). Compares the parsed content, so a file that
is already right is left alone byte for byte (mtime, mode, indentation and
non-ASCII text included); when it does have to change, it is written through
the symlink's real target, keeping the old mode and indent.
"""

from __future__ import annotations

import copy
import json
import os
import re
from pathlib import Path
from typing import Any

_INDENT_RE = re.compile(r'^([ \t]+)"', re.MULTILINE)


def detect_indent(raw: str) -> "Any":
    """The indent argument `json.dumps` needs to reproduce `raw`'s layout:
    the width (or a tab) of its first indented key, 2 for a multi-line file
    with none, None for a one-line file."""
    m = _INDENT_RE.search(raw)
    if m:
        pad = m.group(1)
        return "\t" if pad.startswith("\t") else len(pad)
    return 2 if "\n" in raw.strip() else None


def restore_model(path: Path, snapshot_model: Any) -> bool:
    """Set (or drop, when `snapshot_model` is None) the top-level `model`
    key of `path`; True when the file was rewritten. Never raises."""
    from halo_harness.privateio import write_atomic_keep_mode
    try:
        path = Path(path)
        if not path.exists():
            return False
        raw = path.read_text(encoding="utf-8")
        current = json.loads(raw) if raw.strip() else {}
        if not isinstance(current, dict):
            return False
        before = copy.deepcopy(current)
        if snapshot_model is None:
            current.pop("model", None)
        else:
            current["model"] = snapshot_model
        if current == before:
            return False
        text = json.dumps(current, indent=detect_indent(raw), ensure_ascii=False)
        if raw.endswith("\n") or not raw:
            text += "\n"
        write_atomic_keep_mode(Path(os.path.realpath(path)), text)
        return True
    except Exception:
        return False
