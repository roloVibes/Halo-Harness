"""halo_harness.packs.fleet_share -- what a pack's fleet contribution carries
to the hub, and the words the hub reads back (Halo 3.2.1.0 R3, docs/FLEET.md,
docs/PACKS.md "In the fleet").

    inspector_text(root, source)   {text, cut?}: an inspector line's file for the catalog, so a hub's Studio
                                   shows it for a member as it does for its own harness: a markdown, text or
                                   JSON file inside the pack (fleet_rules.INSPECTOR_SUFFIXES), its first
                                   INSPECTOR_BYTES, every path cut to its last part (fleet/capabilities.scrub);
                                   {} when the source is outside the pack, of another kind, or unreadable
    hidden(pack_id, name, hide)    fleet.capabilities.hide names the capability (`<name>` or `<pack>/<name>`)
    hide_packs(cat, hide)          {"packs": [...]} without the hidden capabilities (fleet/capabilities.
                                   apply_hide), {} when the catalog has no packs section
    hidden_of(pack, hide)          the names of a pack's own capabilities `hide` names (halo pack doctor)
    pack_refusal(line)             `line` is one packs/fleet_registry.refusal answers: the hub re-plans the
                                   part once onto another harness (fleet/mission_hold.py)
"""

from __future__ import annotations

from pathlib import Path

INSPECTOR_BYTES = 8192
REFUSAL_HEADS = ("this harness does not run pack ", "this harness has no pack with ")


def inspector_text(root, source) -> dict:
    from halo_harness.fleet.capabilities import scrub
    from halo_harness.packs.fleet_rules import INSPECTOR_SUFFIXES
    src = str(source or "")
    rel = Path(src)
    if not src or rel.is_absolute() or ".." in rel.parts or ":" in src or rel.suffix.lower() not in INSPECTOR_SUFFIXES:
        return {}
    try:
        base = Path(root).resolve()
        target = (base / rel).resolve()
        if base not in target.parents or not target.is_file():
            return {}
        with open(target, "rb") as fh:
            raw = fh.read(INSPECTOR_BYTES + 1)
    except (OSError, ValueError, TypeError):
        return {}
    text = scrub(raw[:INSPECTOR_BYTES].decode("utf-8", errors="ignore"))
    return {"text": text, "cut": True} if len(raw) > INSPECTOR_BYTES else {"text": text}


def hidden(pack_id, name, hide) -> bool:
    n = str(name or "").lower()
    return bool(hide) and (n in hide or f"{str(pack_id or '').lower()}/{n}" in hide)


def hide_packs(cat: dict, hide) -> dict:
    if not isinstance(cat.get("packs"), list):
        return {}
    return {"packs": [{**p, "capabilities": [c for c in p.get("capabilities") or [] if isinstance(c, dict)
                                             and not hidden(p.get("id"), c.get("name"), hide)]}
                      if isinstance(p, dict) else p for p in cat["packs"]]}


def hidden_of(pack, hide) -> "list[str]":
    from halo_harness.packs.fleet_rules import capabilities_of
    return [str(c["name"]) for c in capabilities_of(pack.manifest) if hidden(pack.id, c.get("name"), hide)]


def pack_refusal(line) -> bool:
    return str(line or "").startswith(REFUSAL_HEADS)
