"""tests.helpers.preflight_seed -- a scratch Halo home for the run-start
preflight tests (tests/test_preflight.py): a seeded `or` catalog
(models.json), bios with a live id, a dead id, a dead fallback and an empty
tool allow-list, a bad lineup (`pf-bad`: every finding at once), a clean one
(`pf-good`) and a flow whose roles step uses a lineup. No model is called.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import yaml

BAD = {"name": "pf-bad", "agents": [
    {"agent": "live-bio", "role": "main"},
    {"agent": "dead-bio", "role": "subagent", "as": "worker"},
    {"agent": "notools-bio", "role": "tester"},
    {"agent": "ghost-bio", "role": "reviewer", "as": "ghost"},
    {"agent": "deadfb-bio", "role": "helper"}],
    "tiers": [{"name": "top", "members": ["worker"]}]}
GOOD = {"name": "pf-good", "agents": [{"agent": "live-bio", "role": "main"}, {"agent": "deadfb-bio", "role": "helper"}]}


class Home:
    """BRIDGE_TEST_HOME and BRIDGE_STATE_DIR for this one test (put back after)."""

    def __init__(self, catalog: bool = True):
        self.catalog = catalog

    def __enter__(self):
        from halo_harness.agents_yaml import save_agent_bio
        self._saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
        root = Path(tempfile.mkdtemp(prefix="preflight-"))
        os.environ["BRIDGE_TEST_HOME"] = str(root)
        os.environ["BRIDGE_STATE_DIR"] = str(root / ".halo")
        self.root, self.state_dir = root, root / ".halo"
        self.cwd = root / "project"
        self.cwd.mkdir(parents=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        if self.catalog:
            (self.state_dir / "models.json").write_text(json.dumps(
                {"vendor/live": {"price_in_per_m": 1.0, "price_out_per_m": 2.0}}), encoding="utf-8")
        for name, bio in (("live-bio", {"models": {"preference": "or:vendor/live"}}),
                          ("dead-bio", {"models": {"preference": "or:vendor/gone"}}),
                          ("notools-bio", {"models": {"preference": "or:vendor/live"}, "tools": {"allow": []}}),
                          ("deadfb-bio", {"models": {"preference": "or:vendor/live", "fallback": "or:vendor/gone2"}})):
            save_agent_bio(name, {"description": name, **bio}, state_dir=self.state_dir)
        teams = self.state_dir / "teams"
        teams.mkdir(parents=True, exist_ok=True)
        for data in (BAD, GOOD):  # written directly: save_team_template refuses the missing bio
            (teams / f"{data['name']}.yaml").write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        return self

    def flow(self, lineup: str, name: str = "pf-flow") -> Path:
        flows = self.state_dir / "flows"
        flows.mkdir(parents=True, exist_ok=True)
        path = flows / f"{name}.flow.yaml"
        path.write_text(yaml.safe_dump({"name": name, "steps": [
            {"id": "intake", "kind": "intake", "form": {"brief": "text"}},
            {"id": "plan", "kind": "roles", "uses": f"lineup:{lineup}", "roles": ["main"]},
            {"id": "done", "kind": "done"}]}, sort_keys=False), encoding="utf-8")
        return path

    def use_team(self, name: str) -> None:
        from halo_harness.theme import set_config_value
        set_config_value("team", name)

    def __exit__(self, *exc):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
