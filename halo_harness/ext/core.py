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
    # /improve's session; outcomes are read through `outcomes.records` only
    "agents_doctor", "agents_yaml", "config.memory", "headless", "knowledge.store", "knowledge.writers",
    "orchestra.forecast", "orchestra.gate", "orchestra.gitops", "orchestra.jsonl", "orchestra.lane_facts",
    "orchestra.prices", "orchestra.split", "outcomes.records", "providers.hooks", "recall", "telemetry", "work_cli",
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
