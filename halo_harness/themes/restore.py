"""halo_harness.themes.restore -- a pack palette's restore record (Halo 3.3.12.0 R2; docs/EXTENSION_API.md "Themes").

    ~/.halo/packs/.data/<pack-id>/theme.json   {"theme": "<pack-id>/<id>", "previous": "claude-dark" | null, "since": ...}

When `theme` is set to a pack's palette (`theme.persist_theme`, the one door every writer of the key goes through),
the value saved before it is kept here; choosing a core palette, or unsetting the key, clears every record. When
the pack is disabled or removed while its palette is the saved `theme` (`packs/grants.disable`, `packs/remove.remove`),
the previous value is written back (or the key unset when there was none) and the command says so in one line; the
terminal and Studio follow as for any change of the key. Going from one pack's palette to another's carries the first
record's `previous` forward, so a restore always lands on a palette that does not depend on a pack.
A saved `theme` that names a pack palette whose pack is gone reads like a removed game theme: one line, the default
drawn, never a crash (`gone_line`, used by `theme.removed_theme_notice` and `halo doctor --config`).

    pack_of(name)                    the pack id of `<pack-id>/<id>[-modifier]`, "" for a core name
    note_choice(new, old)            persist_theme's record keeping (new None = the key unset)
    read(pack_id) / forget(pack_id)  the record
    on_pack_off(pack_id, ...)        disable / remove: restore when the saved theme is the pack's; the lines
    gone_line(name, using)           the line for a saved pack palette that is not there, or None
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

FILE = "theme.json"
SEP = "/"


def record_path(pack_id: str, state_dir=None) -> Path:
    from halo_harness.packs.discover import user_packs_dir
    return user_packs_dir(state_dir) / ".data" / pack_id / FILE


def pack_of(name) -> str:
    if not isinstance(name, str) or SEP not in name:
        return ""
    return name.split(SEP, 1)[0]


def read(pack_id: str, state_dir=None) -> Optional[dict]:
    try:
        raw = json.loads(record_path(pack_id, state_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    prev = raw.get("previous")
    return {"theme": raw.get("theme"), "previous": prev if isinstance(prev, str) and prev else None,
            "since": raw.get("since")}


def forget(pack_id: str, state_dir=None) -> bool:
    try:
        record_path(pack_id, state_dir).unlink()
        return True
    except OSError:
        return False


def _all(state_dir=None) -> "list[str]":
    from halo_harness.packs.discover import user_packs_dir
    data = user_packs_dir(state_dir) / ".data"
    try:
        return sorted(d.name for d in data.iterdir() if (d / FILE).is_file())
    except OSError:
        return []


def note_choice(new: Optional[str], old: Optional[str], state_dir=None) -> None:
    """Called before `theme` becomes `new` (None: unset) while it was `old`."""
    new_pack, old_pack = pack_of(new), pack_of(old)
    previous = old if isinstance(old, str) and old else None
    if old_pack:
        rec = read(old_pack, state_dir)
        previous = rec["previous"] if rec else None
    for pid in _all(state_dir):
        forget(pid, state_dir)
    if not new_pack:
        return
    from halo_harness.packs.state import now
    from halo_harness.privateio import write_private_atomic
    path = record_path(new_pack, state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_private_atomic(path, json.dumps({"theme": new, "previous": previous, "since": now()}, indent=2) + "\n")


def on_pack_off(pack_id: str, *, verb: str = "disabled", state_dir=None) -> "list[str]":
    """The pack is off now (`verb`: disabled | removed). When the saved `theme` is one of its palettes, write the
    previous value back (or unset the key) and say so in one line; the record goes either way."""
    from halo_harness import theme as T
    rec = read(pack_id, state_dir)
    forget(pack_id, state_dir)
    saved = T.load_persisted_theme()
    if pack_of(saved) != pack_id:
        return []
    prev = rec["previous"] if rec else None
    try:
        if prev and T.is_theme_value(prev):
            T.set_config_value("theme", prev)
            back = prev
        else:
            T.unset_config_value("theme")
            back = f"the default (theme unset: {T.DEFAULT_THEME} in the terminal and Studio)"
    except T.CorruptConfigError as e:
        return [f"theme: {saved} was {pack_id}'s palette; config.json was left as it is: {e}"]
    return [f"theme: {saved} was {pack_id}'s palette and the pack is {verb}; restored {back}"]


def gone_line(name, using: str) -> Optional[str]:
    """One line for a saved `theme` naming a pack palette that is not there now (its pack disabled, removed, or
    without that palette); None for any other name."""
    pack = pack_of(name)
    if not pack:
        return None
    from halo_harness.themes.registry import is_name
    if is_name(name):
        return None
    return f"theme: {name} is a palette of the pack {pack}, which is not enabled here (or no longer has it); using {using}"
