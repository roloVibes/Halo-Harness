"""halo_harness.packs.mode_state -- a pack's runtime mode file (Halo 3.3.10.0 R1; docs/EXTENSION_API.md
"Policy hooks"; stable since R2).

    ~/.halo/packs/.data/<id>/mode.json
    {"mode": "fenced" | null, "since": "<UTC time>", "by": "cli" | "pack:<id>" | ..., "armed": ["fence"], "note": ""}

The one record of what a pack has on at run time: the mode and the armed policies (the lifecycle's enabled /
disabled record is state.json, packs/state.py; this is not it). It lives in the pack's data folder, beside its
events log, and is written only here, privately and atomically: `halo pack mode`, `halo pack policy arm | disarm`
and `ext.set_mode` are the doors, never a hand edit. Every change is the pack's typed event `mode` in its events
log (packs/events_log.py). Turning a mode on arms each policy whose `when.modes` names it, and turning it off
disarms them; `arm` / `disarm` name one policy. A mode or policy the manifest does not declare is one line naming
`contributes.modes` or `contributes.policy`, and nothing is written. Readers stat the file when they need it
(`signature`), so a change is seen at the next verdict without a watcher.

    read(pack_id, state_dir=None) -> the record (an empty one when there is none)
    set_mode(pack_id, mode, on=True, *, by, note="", cwd=None, state_dir=None) -> (ok, lines)
    arm(pack_id, policy_id, *, by, ...) / disarm(pack_id, policy_id=None, *, by, ...) -> (ok, lines)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

FILE = "mode.json"
EVENT = "mode"


def mode_path(pack_id: str, state_dir=None) -> Path:
    from halo_harness.packs.discover import user_packs_dir
    return user_packs_dir(state_dir) / ".data" / pack_id / FILE


def empty() -> dict:
    return {"mode": None, "since": None, "by": None, "armed": [], "note": ""}


def read(pack_id: str, state_dir=None) -> dict:
    try:
        raw = json.loads(mode_path(pack_id, state_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raw = None
    out = empty()
    if isinstance(raw, dict):
        out["mode"] = raw.get("mode") if isinstance(raw.get("mode"), str) else None
        out["since"], out["by"] = raw.get("since"), raw.get("by")
        out["armed"] = [a for a in raw.get("armed") or [] if isinstance(a, str)] if isinstance(raw.get("armed"), list) else []
        out["note"] = raw.get("note") if isinstance(raw.get("note"), str) else ""
    return out


def signature(pack_id: str, state_dir=None) -> tuple:
    try:
        st = mode_path(pack_id, state_dir).stat()
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return (None, None)


def _find(pack_id: str, cwd, state_dir):
    from halo_harness.packs.discover import find
    from halo_harness.packs.grants import no_pack_line
    pack = find(pack_id, cwd=cwd, state_dir=state_dir)
    return (pack, "") if pack is not None else (None, no_pack_line(pack_id))


def _write(pack, rec: dict, change: str, by: str, state_dir, cwd=None) -> None:
    from halo_harness.packs.events_log import append
    from halo_harness.packs.grants import notify_studio
    from halo_harness.packs.state import now
    from halo_harness.privateio import write_private_atomic
    rec = {"mode": rec.get("mode"), "since": rec.get("since") or now(), "by": by,
           "armed": sorted(set(rec.get("armed") or [])), "note": rec.get("note") or ""}
    write_private_atomic(mode_path(pack.id, state_dir), json.dumps(rec, indent=2) + "\n")
    append(pack.id, EVENT, {"change": change, "mode": rec["mode"], "armed": rec["armed"], "by": by}, state_dir=state_dir)
    live = sys.modules.get("halo_harness.packs.policy")  # a process this one runs for a policy no longer armed stops
    if live is not None:
        live.reconcile(pack.id, rec["armed"])
    gate = sys.modules.get("halo_harness.agent.policy_gate")  # 3.3.10.0 R2: a session process starts the armed now
    if gate is not None and rec["armed"]:
        gate.on_armed(cwd)
    notify_studio("mode")


def _runs_line(pack, cwd, state_dir) -> str:
    """'' when the pack runs here with the hooks grant; else the one line saying what it takes."""
    from halo_harness.packs import state as S
    from halo_harness.packs.registry import snapshot
    snap = snapshot(cwd=cwd, state_dir=state_dir)
    if pack.id not in snap.order:
        return f"it is not asked until the pack runs here: halo pack enable {pack.id} --grant hooks"
    if "hooks" not in S.granted(pack.id, snap.state):
        return f"it is not asked until hooks is granted: halo pack grant {pack.id} hooks"
    return ""


def set_mode(pack_id: str, mode: str, on: bool = True, *, by: str = "cli", note: str = "", cwd=None,
             state_dir=None) -> "tuple[bool, list[str]]":
    from halo_harness.packs import manifest_policy as MP
    from halo_harness.packs.state import now
    pack, line = _find(pack_id, cwd, state_dir)
    if pack is None:
        return False, [line]
    declared = MP.ids(MP.modes_of(pack.manifest))
    if mode not in declared:
        return False, [f"{pack.id} declares no mode {mode!r} (contributes.modes: {', '.join(declared) or 'none'})"]
    rec = read(pack.id, state_dir)

    def names(m) -> set:
        return {p["id"] for p in MP.policies_of(pack.manifest) if m and m in MP.when_of(p)[1]}
    if not on:
        if rec["mode"] != mode:
            return True, [f"{pack.id}: mode {mode} is not on (the mode now: {rec['mode'] or 'none'}); nothing changed"]
        gone = sorted(names(mode) & set(rec["armed"]))
        rec.update(mode=None, since=now(), note=note, armed=[a for a in rec["armed"] if a not in gone])
        _write(pack, rec, f"mode {mode} off", by, state_dir)
        return True, [f"{pack.id}: mode {mode} off" + (f"; disarmed: {', '.join(gone)}" if gone else "")]
    was = rec["mode"]
    keep = [a for a in rec["armed"] if a not in names(was) or a in names(mode)] if was and was != mode else rec["armed"]
    armed = sorted(set(keep) | names(mode))
    rec.update(mode=mode, since=now() if was != mode else rec["since"], note=note, armed=armed)
    _write(pack, rec, f"mode {mode} on", by, state_dir, cwd)
    label = (MP.mode_entry(pack.manifest, mode) or {}).get("label")
    lines = [f"{pack.id}: mode {mode} on" + (f" ({label})" if label else "") + (f", was {was}" if was and was != mode else "")
             + f"; armed: {', '.join(armed) or 'none'}"]
    runs = _runs_line(pack, cwd, state_dir) if armed else ""
    return True, lines + ([runs] if runs else [])


def arm(pack_id: str, policy_id: str, *, by: str = "cli", cwd=None, state_dir=None) -> "tuple[bool, list[str]]":
    from halo_harness.packs import manifest_policy as MP
    pack, line = _find(pack_id, cwd, state_dir)
    if pack is None:
        return False, [line]
    declared = MP.ids(MP.policies_of(pack.manifest))
    if policy_id not in declared:
        return False, [f"{pack.id} declares no policy {policy_id!r} (contributes.policy: {', '.join(declared) or 'none'})"]
    rec = read(pack.id, state_dir)
    if policy_id in rec["armed"]:
        return True, [f"{pack.id}: policy {policy_id} is already armed"]
    rec["armed"] = rec["armed"] + [policy_id]
    _write(pack, rec, f"arm {policy_id}", by, state_dir, cwd)
    lines = [f"{pack.id}: policy {policy_id} armed"]
    modes = MP.when_of(MP.entry(pack.manifest, policy_id))[1]
    if modes and rec["mode"] not in modes:
        lines.append(f"it is asked while mode {' or '.join(modes)} is on (the mode now: {rec['mode'] or 'none'})")
    runs = _runs_line(pack, cwd, state_dir)
    return True, lines + ([runs] if runs else [])


def disarm(pack_id: str, policy_id=None, *, by: str = "cli", cwd=None, state_dir=None) -> "tuple[bool, list[str]]":
    """One policy, or (`policy_id` None) every armed policy of the pack; the mode stays as it is."""
    from halo_harness.packs import manifest_policy as MP
    pack, line = _find(pack_id, cwd, state_dir)
    if pack is None:
        return False, [line]
    declared = MP.ids(MP.policies_of(pack.manifest))
    if policy_id is not None and policy_id not in declared:
        return False, [f"{pack.id} declares no policy {policy_id!r} (contributes.policy: {', '.join(declared) or 'none'})"]
    rec = read(pack.id, state_dir)
    gone = [a for a in rec["armed"] if policy_id is None or a == policy_id]
    if not gone:
        what = f"policy {policy_id} is not armed" if policy_id else "no policy is armed"
        return True, [f"{pack.id}: {what}; nothing changed"]
    rec["armed"] = [a for a in rec["armed"] if a not in gone]
    _write(pack, rec, f"disarm {', '.join(gone)}", by, state_dir)
    return True, [f"{pack.id}: disarmed {', '.join(gone)}"]
