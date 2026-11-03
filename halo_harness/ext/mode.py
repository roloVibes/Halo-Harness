"""halo_harness.ext.mode -- a pack's runtime mode (extension API 1.1, Halo 3.3.10.0 R1; docs/EXTENSION_API.md
"Policy hooks", stable since 3.3.10.0 R2).

    set_mode("policy-fence", "fenced")            # [] when written: the mode is on, its policies armed
    set_mode("policy-fence", "fenced", on=False)  # [] when written: off, its policies disarmed
    current_mode("policy-fence")                  # "fenced", or None when no mode is on

The record is `~/.halo/packs/.data/<id>/mode.json` (packs/mode_state.py); this is the door a pack's own commands
and hooks use, never a write by hand. A mode the pack's `contributes.modes` does not declare is one line and
nothing is written; every change is the pack's `mode` event in its events log.
"""

from __future__ import annotations

from typing import Optional


def _check_id(pack_id) -> None:
    from halo_harness.packs.names import pack_id_problem
    line = pack_id_problem(pack_id)
    if line:
        raise ValueError(line)


def set_mode(pack_id: str, mode_id: str, on: bool = True, *, note: str = "") -> "list[str]":
    """`[]` when mode.json was written; else the one line saying why not."""
    from halo_harness.packs.mode_state import set_mode as _set
    _check_id(pack_id)
    ok, lines = _set(pack_id, str(mode_id), bool(on), by=f"pack:{pack_id}", note=str(note or ""))
    return [] if ok else lines[:1]


def current_mode(pack_id: str) -> Optional[str]:
    from halo_harness.packs.mode_state import read
    _check_id(pack_id)
    return read(pack_id)["mode"]


__all__ = ["set_mode", "current_mode"]
