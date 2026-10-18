"""tests.helpers.config_seed -- a scratch home and repo for the `halo config
where` and `halo doctor --config` tests (3.1.1.0 R2).

`ConfigHome()` is a context manager: a fresh `BRIDGE_TEST_HOME` (with
`BRIDGE_STATE_DIR` unset, so the state dir is `<home>/.halo`), the managed
settings folder pointed inside it (`BRIDGE_TEST_MANAGED_DIR`), and every
provider variable snapshotted and restored on exit. `seed(home)` writes one
file of every kind `config where` lists; the fake secrets it writes are the
module constants, so a test can assert they never reach the output.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

FAKE_KEY = "sk-or-v1-FAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKE1234567890abcdef"  # tests/privacy_scan_allowlist.txt
DOT_ENV_VALUE = "dotenv-value-never-printed"
CONFIG_SECRET = "plaintext-secret-in-config"
PREFIXES = ("OPENROUTER_", "DATABRICKS_", "ANTHROPIC_", "BRIDGE_", "HALO_", "ROLO_CLAUDE_", "TYPESAFE_", "OPENAI_")


class ConfigHome:
    def __enter__(self):
        self._saved = {k: v for k, v in os.environ.items() if k.startswith(PREFIXES)}
        for k in list(os.environ):
            if k.startswith(PREFIXES) and k not in ("BRIDGE_TEST_NO_BACKGROUND_NET",):
                os.environ.pop(k)
        self.home = Path(tempfile.mkdtemp(prefix="config-where-"))
        os.environ["BRIDGE_TEST_HOME"] = str(self.home)
        os.environ["BRIDGE_TEST_MANAGED_DIR"] = str(self.home / "managed")
        os.environ["BRIDGE_TEST_NO_BACKGROUND_NET"] = "1"
        self.state = self.home / ".halo"
        self.repo = self.home / "repo"
        self.repo.mkdir(parents=True)
        self.state.mkdir()
        return self

    def __exit__(self, *exc):
        for k in list(os.environ):
            if k.startswith(PREFIXES):
                os.environ.pop(k)
        os.environ.update(self._saved)
        shutil.rmtree(self.home, ignore_errors=True)

    def write(self, rel: str, text: str, *, base: "Path | None" = None) -> Path:
        path = (base or self.home) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def config(self, data: dict) -> Path:
        return self.write(".halo/config.json", json.dumps(data))


def seed(h: ConfigHome) -> ConfigHome:
    """One file of every kind, with the clashes the precedence tests read."""
    h.config({"model": "or:vendor/from-config", "team": "mine", "theme": "doom",
              "ollama": {"hosts": [{"name": "lan", "api_key": CONFIG_SECRET}]}})
    h.write(".halo/routes.json", json.dumps({"default": "or:vendor/from-routes"}))
    h.write(".config/halo/env", f"OPENROUTER_API_KEY={FAKE_KEY}\nDATABRICKS_HOST=your-workspace.cloud.databricks.com\n")
    h.write(".env", f"REPO_ONLY_TOKEN={DOT_ENV_VALUE}\n", base=h.repo)
    h.write(".halo/config.json", json.dumps({"theme": "mario"}), base=h.repo)
    h.write(".halo/teams/mine.yaml", "extends: standard\ndelegation: {mode: manual}\nroles: {main: coder}\n")
    h.write(".halo/teams/standard.yaml", "description: the repo's own\nroles: {main: coder}\n", base=h.repo)
    h.write(".halo/agents/coder.yaml", "description: my coder\nkind: main\n")
    h.write(".halo/team.yaml", "name: repo-team\nbrief: BRIEF.md\nmembers: [{name: a, lineup: standard, role: main}]\n",
            base=h.repo)
    h.write("BRIEF.md", "# brief\n", base=h.repo)
    h.write(".halo/teams/repo.team.yaml", "name: kept-outside\n")
    h.write(".halo/flows/social-post.flow.yaml", "name: social-post\nsteps: [{id: a, kind: intake, form: {x: text}}]\n")
    h.write(".claude/settings.json", json.dumps({"model": "project-model", "env": {"A": "1"}}), base=h.repo)
    h.write(".claude/settings.local.json", json.dumps({"model": "local-model"}), base=h.repo)
    h.write(".claude/settings.json", json.dumps({"theme": "claude-light"}))
    h.write(".mcp.json", json.dumps({"mcpServers": {"fs": {"command": "repo-fs"}}}), base=h.repo)
    h.write(".claude.json", json.dumps({"mcpServers": {"fs": {"command": "user-fs"}, "web": {"command": "w"}}}))
    return h


def by(rows: list, kind: str, file: str) -> dict:
    """The one row of `kind` whose display name is `file` (AssertionError otherwise)."""
    hits = [r for r in rows if r["kind"] == kind and r["file"] == file]
    assert len(hits) == 1, f"expected one {kind} row {file!r}, got {[(r['kind'], r['file']) for r in rows]}"
    return hits[0]
