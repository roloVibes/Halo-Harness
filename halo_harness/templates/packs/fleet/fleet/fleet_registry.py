"""halo_harness.packs.fleet_registry as the fleet pack reaches it (3.4.0.0 D: the registry is core again,
halo_harness/packs/fleet_registry.py, so capability checks run with this pack off; this name stays for the pack's
own modules and its tests)."""

from __future__ import annotations

from halo_harness.ext import core as _core

_R = _core.module("packs.fleet_registry")
section, entry, checks, pack_entry, refusal = _R.section, _R.entry, _R.checks, _R.pack_entry, _R.refusal
mission_metadata, pack_mission, host_catalog, inspector_text = _R.mission_metadata, _R.pack_mission, _R.host_catalog, _R.inspector_text
