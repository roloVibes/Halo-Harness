"""halo_harness.ext.core -- the core modules a shipped pack that left Halo's core still drives (extension API 1.3,
draft: Halo 3.4.0.0 B; docs/EXTENSION_API.md "Core access").

The guided first run (the first-run pack) and the coach (the coach pack) were part of the core until 3.4.0.0; they
drive the Orchestra engine, the lineups and the checks as they always did. A pack imports `halo_harness.ext` and
nothing else (tests/test_ext_api.py), so this module is the one door, and REACHABLE names every core module it opens:

    from halo_harness.ext import core
    P = core.module("orchestra.plan")                  # the module halo_harness.orchestra.plan
    load_report = core.get("orchestra.report", "load_report")   # one name of it (a submodule when it is one)

A name not in REACHABLE raises ValueError naming the rule. Draft: these are Halo's own modules, as they are in the
Halo the pack ships with; they follow Halo's version, not the extension API's, so a third-party pack does not build
on them (the shipped packs move with Halo and are tested with it).
"""

from __future__ import annotations

import importlib

REACHABLE = (
    # the first-run pack (3.4.0.0 B)
    "checks.provider", "config.paths", "init_cli", "lineup_default", "lineup_preflight", "model",
    "orchestra", "orchestra.adapters", "orchestra.claims", "orchestra.goal", "orchestra.lanes",
    "orchestra.plan", "orchestra.report", "orchestra.run", "orchestra.view", "orchestra.workers", "orchestra_cli_plan",
    "packs.names", "roles", "studio.events", "studio.launch", "studio.model", "studio.orchestra_model",
    "studio.setup_door", "teams_tiers", "teams_yaml", "theme", "tui.dialogs.team_preview", "worktree",
    # the coach pack (3.4.0.0 B2): the run folders it reads, the writers its Apply uses, the probe's Orchestra runs,
    # /improve's session; outcomes are read through `outcomes.records` only; the fleet's mission folders and hub are
    # the fleet pack's, asked through `packs.fleet_door` (none when that pack is off; 3.4.0.0 C)
    "agents_doctor", "agents_yaml", "config.memory", "headless", "knowledge.store", "knowledge.writers",
    "orchestra.forecast", "orchestra.gate", "orchestra.gitops", "orchestra.jsonl", "orchestra.lane_facts",
    "orchestra.prices", "orchestra.split", "outcomes.records", "packs.fleet_door", "providers.hooks", "recall",
    "recall_fleet", "telemetry", "work_cli",
    # the fleet pack (3.4.0.0 C): the hub, missions and the relay over peers/ (the link) and live/ (the sessions);
    # the coach pack's mission coach and coach_library answer through `packs.contrib_cli` (none when it is off)
    "agent.agent_registry", "bg_run", "capabilities", "commands.skills", "config.claude_json",
    "events", "live.attention", "live.conflicts", "live.history", "live.journal",
    "live.push", "live.recording", "mcp.connectors_bridge", "mcp.doctor_deep", "mcp.manager", "mcp.tools_cache",
    "mcp_setup", "ollama_steward.job", "orchestra.hunks", "orchestra.to_report", "output",
    "packs.bio_models", "packs.contrib_cli", "packs.discover", "packs.fleet_rules", "packs.policy_audit",
    "packs.registry", "packs.state", "packs.studio_registry", "peers.capabilities_host", "peers.catalog",
    "peers.control_models", "peers.hub_hosts", "peers.hub_join", "peers.identity", "peers.local_view", "peers.net",
    "peers.ollama_share", "peers.pairing", "peers.protocol", "peers.relay", "peers.store", "peers.tls", "permissions",
    "privateio", "providers.config", "providers.enablement", "providers.media_models", "providers.model_enumeration",
    "providers.reachability", "redact", "remote.agent_control", "remote.base", "remote.cli_common",
    "remote.fleet_frames", "remote.fleet_identity", "remote.protocol", "remote.qr", "remote.registry",
    "remote.runtime", "studio.fleet_api", "studio.fleet_feed", "studio.fleet_handoff_api",
    "studio.fleet_panels_api", "studio.fleet_recording_api", "studio.fleet_send", "studio.fleet_watch",
    "studio.fleet_watch_sources", "studio.recall_api", "studio.sessions_api", "tools.screenshot",
    "work.adapters.part", "work.report", "work.states",
    # 3.4.0.0 D: the capability checker is core again (a pack workflow's `requires` and a pack's capability rows are
    # checked with the fleet pack off); the fleet pack re-exports it
    "packs.fleet_registry", "peers.needs", "peers.projects",
)


def version() -> str:
    """This Halo's version (`halo_harness.__version__`)."""
    from halo_harness import __version__
    return __version__


def _check(name: str) -> str:
    n = str(name or "").strip()
    if n not in REACHABLE:
        raise ValueError(f"halo_harness.{n} is not a core module a pack reaches (ext.core.REACHABLE lists them; "
                         "docs/EXTENSION_API.md \"Core access\")")
    return n


def module(name: str):
    """The core module `halo_harness.<name>` (a name REACHABLE lists)."""
    return importlib.import_module(f"halo_harness.{_check(name)}")


def get(name: str, attr: str):
    """`module(name).<attr>`; a submodule of a REACHABLE package when `attr` names one that is REACHABLE too."""
    mod = module(name)
    if hasattr(mod, attr):
        return getattr(mod, attr)
    return module(f"{name}.{attr}")


__all__ = ["REACHABLE", "module", "get", "version"]
