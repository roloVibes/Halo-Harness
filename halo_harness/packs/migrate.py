"""halo_harness.packs.migrate -- a pack's `migrations` between two versions
(Halo 3.2.0.0 R7; docs/EXTENSION_API.md "Compatibility and migration",
docs/PACKS.md "Updating and rolling back").

An entry is `{from, to, note, settings?: {<old key>: <new key>}}`. `note` is
what changes for you: `halo pack update` (and the Pack Manager's Update)
prints it before anything is replaced. `settings` is the one kind Halo
applies itself: each `packs.settings.<id>.<old>` you set moves to `<new>`
(a dotted key reaches into a mapping); a `<new>` you set already wins and
`<old>` stays. Every move is a journal row (`op: "migrate"`, the update's
`op_id`), which `halo pack rollback` reads to move it back.

    between(manifest, "1.1.0", "1.3.0")   # the entries an update from 1.1.0 to 1.3.0 crosses, oldest first
    note_lines("doc-review", entries)      # ["doc-review 1.1 -> 1.3: settings key `lint.level` is now `lint.strictness`"]
    plan_lines("doc-review", entries)      # what an update would rename, said before (and by --dry-run)
    apply("doc-review", entries, op_id=)   # the moves, made and journaled: one line each
    undo("doc-review", op_id)              # the moves of that update, back: one line each
"""

from __future__ import annotations

import copy
import re
import time

from halo_harness.packs import semver as V

KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*(\.[A-Za-z_][A-Za-z0-9_-]*)*$")


def settings_lines(value, *, where: str = "settings") -> "list[str]":
    """The manifest lines for one entry's `settings` (None: no renames)."""
    if value is None:
        return []
    if not isinstance(value, dict):
        return [f"{where} is a mapping {{old key: new key}} of packs.settings.<id> names"]
    out = []
    for old, new in value.items():
        if not isinstance(old, str) or not KEY_RE.match(old) or not isinstance(new, str) or not KEY_RE.match(new):
            out.append(f"{where}: {old!r}: {new!r} is not a setting rename (names of letters, digits, _ and -, "
                       "dotted for a nested key)")
        elif old == new:
            out.append(f"{where}: {old!r} is renamed to itself")
    return out


def between(manifest: dict, old: str, new: str) -> "list[dict]":
    """The entries from the installed version `old` up to the new version `new`, oldest first."""
    out = []
    for m in (manifest or {}).get("migrations") or []:
        if not isinstance(m, dict) or V.release(m.get("from")) is None or V.release(m.get("to")) is None:
            continue
        try:
            after_old = V.release(old) is None or V.compare(m["from"], old) >= 0
            upto_new = V.compare(m["to"], new) <= 0
        except ValueError:
            continue
        if after_old and upto_new:
            out.append(m)
    return sorted(out, key=lambda m: (V.release(m["from"]), V.release(m["to"])))


def note_lines(pack_id: str, entries) -> "list[str]":
    return [f"{pack_id} {m['from']} -> {m['to']}: {str(m.get('note') or '').strip()}" for m in entries]


def renames(entries) -> "list[tuple[str, str]]":
    out = []
    for m in entries:
        pairs = m.get("settings") if isinstance(m.get("settings"), dict) else {}
        out += [(old, new) for old, new in pairs.items() if not settings_lines({old: new})]
    return out


def _find(d: dict, key: str):
    cur = d
    for part in key.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return False, None
        cur = cur[part]
    return True, cur


def _put(d: dict, key: str, value) -> None:
    parts = key.split(".")
    cur = d
    for part in parts[:-1]:
        if not isinstance(cur.get(part), dict):
            cur[part] = {}
        cur = cur[part]
    cur[parts[-1]] = value


def _drop(d: dict, key: str) -> None:
    parts = key.split(".")
    trail, cur = [], d
    for part in parts[:-1]:
        trail.append((cur, part))
        cur = cur[part]
    cur.pop(parts[-1], None)
    for parent, part in reversed(trail):  # a mapping the move emptied goes too
        if parent[part] == {}:
            parent.pop(part)


def _moves(values: dict, pairs) -> "tuple[list[tuple], list[tuple]]":
    """Rename in `values` (mutated): `(moved [(old, new, value)], kept [(old, new)])`."""
    moved, kept = [], []
    for old, new in pairs:
        have, value = _find(values, old)
        if not have:
            continue
        if _find(values, new)[0]:
            kept.append((old, new))
            continue
        _put(values, new, value)
        _drop(values, old)
        moved.append((old, new, value))
    return moved, kept


def _lines(pack_id: str, moved, kept, *, would: bool = False) -> "list[str]":
    verb = "would rename" if would else "renamed"
    out = [f"{verb} packs.settings.{pack_id}.{old} to {new} (your value {value!r})" for old, new, value in moved]
    out += [f"packs.settings.{pack_id}.{new} is set already, so {old} stays as it is" for old, new in kept]
    return out


def plan_lines(pack_id: str, entries) -> "list[str]":
    """What an update's renames would do to your settings, touching nothing."""
    from halo_harness.packs.settings import user_values
    pairs = renames(entries)
    if not pairs:
        return []
    moved, kept = _moves(copy.deepcopy(user_values(pack_id)), pairs)
    return _lines(pack_id, moved, kept, would=True) or [
        f"no setting of yours to rename ({', '.join(old for old, _new in pairs)} not set)"]


def _write(pack_id: str, values: dict) -> "list[str]":
    from halo_harness.theme import set_config_value
    try:
        set_config_value(f"packs.settings.{pack_id}", values)
    except Exception as e:  # CorruptConfigError: config.json does not parse
        return [f"packs.settings.{pack_id} is not changed: {e}"]
    return []


def _journal(row: dict, state_dir) -> None:
    from halo_harness.packs.journal import _append
    _append({"ts": round(time.time(), 3), **row}, state_dir)


def apply(pack_id: str, entries, *, op_id: str, state_dir=None) -> "list[str]":
    """Make the entries' settings renames in `packs.settings.<id>` and journal each one."""
    from halo_harness.packs.settings import user_values
    pairs = renames(entries)
    if not pairs:
        return []
    values = copy.deepcopy(user_values(pack_id))
    moved, kept = _moves(values, pairs)
    if moved:
        problem = _write(pack_id, values)
        if problem:
            return problem
        for old, new, value in moved:
            _journal({"op": "migrate", "op_id": op_id, "pack": pack_id, "setting": old, "to": new, "value": value}, state_dir)
    return _lines(pack_id, moved, kept) or [f"no setting of yours to rename ({', '.join(o for o, _n in pairs)} not set)"]


def undo(pack_id: str, op_id: str, *, state_dir=None) -> "list[str]":
    """Move back every setting the update `op_id` renamed (its value where it is now); journaled as `unmigrate`."""
    from halo_harness.packs.journal import rows
    from halo_harness.packs.settings import user_values
    done = [r for r in rows(state_dir, pack=pack_id) if r.get("op") == "migrate" and r.get("op_id") == op_id]
    if not done:
        return []
    values = copy.deepcopy(user_values(pack_id))
    moved, kept = _moves(values, [(r["to"], r["setting"]) for r in reversed(done)])
    if moved:
        problem = _write(pack_id, values)
        if problem:
            return problem
        for new, old, value in moved:
            _journal({"op": "unmigrate", "op_id": op_id, "pack": pack_id, "setting": new, "to": old, "value": value}, state_dir)
    return ([f"moved packs.settings.{pack_id}.{new} back to {old} (value {value!r})" for new, old, value in moved]
            + [f"packs.settings.{pack_id}.{old} is set again, so {new} stays as it is" for new, old in kept])
