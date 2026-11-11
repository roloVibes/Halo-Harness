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
from halo_harness.ext import core as _core

INSPECTOR_BYTES = _core.get("packs.fleet_registry", "INSPECTOR_BYTES")
REFUSAL_HEADS = ("this harness does not run pack ", "this harness has no pack with ")


inspector_text = _core.get("packs.fleet_registry", "inspector_text")  # 3.4.0.0 D: core


hidden = _core.get("packs.fleet_rules", "hidden")  # 3.4.0.0 D: core


def hide_packs(cat: dict, hide) -> dict:
    if not isinstance(cat.get("packs"), list):
        return {}
    return {"packs": [{**p, "capabilities": [c for c in p.get("capabilities") or [] if isinstance(c, dict)
                                             and not hidden(p.get("id"), c.get("name"), hide)]}
                      if isinstance(p, dict) else p for p in cat["packs"]]}


def hidden_of(pack, hide) -> "list[str]":
    capabilities_of = _core.get("packs.fleet_rules", "capabilities_of")
    return [str(c["name"]) for c in capabilities_of(pack.manifest) if hidden(pack.id, c.get("name"), hide)]


def pack_refusal(line) -> bool:
    return str(line or "").startswith(REFUSAL_HEADS)
