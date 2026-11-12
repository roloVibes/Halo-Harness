"""halo_harness.packs.shipped_newer -- an installed pack older than the one this Halo ships (Halo 3.4.1.0 R5, live
re-check defect 30). After `halo update` to 3.4.0.1 both machines kept the fleet pack 1.0.0 (installed from Halo's
shipped folder) while Halo shipped 1.0.1; `pack list`, `pack inspect`, `pack doctor`, `halo doctor` and Studio's Packs
all said 1.0.0 with no word of 1.0.1. Each now says it in one line with `halo pack update <id>`.

    ships(pack_id)                  this Halo's shipped version of `pack_id`, or ""
    newer(pack_id, version, source) the shipped version when the pack came from a Halo's shipped folder and that is newer
    note(pack_id, version, ships)   "<id> <version> is older than the <ships> this Halo ships: halo pack update <id>"
    stale(state_dir=None)           [{id, version, ships, line}] for every installed (not linked, not removed) pack
"""

from __future__ import annotations

from pathlib import Path


def ships(pack_id: str) -> str:
    from halo_harness.packs.discover import read_pack
    from halo_harness.packs.sources import shipped_dir
    folder = shipped_dir() / str(pack_id)
    if not (folder / "pack.yaml").is_file():
        return ""
    try:
        return str(read_pack(folder, "source", folder_is_id=False).version or "")
    except Exception:
        return ""


def _from_shipped(pack_id: str, source: str) -> bool:
    """A Halo's shipped folder: this one's, or an older install's (`.../templates/packs/<id>`)."""
    parts = [p.lower() for p in Path(str(source or "")).parts]
    return len(parts) >= 3 and parts[-3:] == ["templates", "packs", str(pack_id).lower()]


def newer(pack_id: str, version: str, source: str) -> str:
    from halo_harness.packs.semver import compare
    if not _from_shipped(pack_id, source):
        return ""
    have, got = str(version or ""), ships(pack_id)
    try:
        return got if got and have and compare(got, have) > 0 else ""
    except ValueError:
        return ""


def note(pack_id: str, version: str, shipped: str) -> str:
    return f"{pack_id} {version} is older than the {shipped} this Halo ships: halo pack update {pack_id}"


def stale(state_dir=None) -> "list[dict]":
    from halo_harness.packs import state as S
    out = []
    for pid, rec in sorted((S.load(state_dir).get("installed") or {}).items()):
        if not isinstance(rec, dict) or rec.get("removed") or rec.get("link"):
            continue
        got = newer(pid, str(rec.get("version") or ""), str(rec.get("source") or ""))
        if got:
            out.append({"id": pid, "version": str(rec.get("version")), "ships": got, "line": note(pid, str(rec.get("version")), got)})
    return out
