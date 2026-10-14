"""tests.test_design_crafts -- the craft apps as design engines (Halo
3.0.1.0 round D4): discovery from a claude.json-shaped dict (user and
project scope, case-insensitive, only the craft apps), the parsed configs,
a live probe over tests/helpers/fake_mcp_server.py registered under a craft
name (connected, tools counted, the render tool reported missing because
the fake does not have it), a dead command reported as failed, the doctor
lines, and `halo design doctor` with and without --probe. Scoped home.
"""

from __future__ import annotations

import io
import os
import sys
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

REPO_DIR = Path(__file__).resolve().parent.parent
test, TESTS = new_registry()

FAKE = {"type": "stdio", "command": sys.executable, "args": ["-m", "tests.helpers.fake_mcp_server"], "env": {}, "cwd": str(REPO_DIR)}


@test
def test_discovery_from_the_session_config(ctx: Ctx):
    from halo_harness.design.crafts_probe import craft_server_configs, craft_server_entries, registered_craft_servers
    cj = {"mcpServers": {"VectorCraft": dict(FAKE), "filesystem": dict(FAKE)},
          "projects": {str(REPO_DIR): {"mcpServers": {"pdfcraft": dict(FAKE)}}}}
    ents = craft_server_entries(cj, REPO_DIR)
    ctx.check("user and project craft servers are found, lower-cased, nothing else", set(ents) == {"vectorcraft", "pdfcraft"})
    ctx.check("registered_craft_servers is the same set", registered_craft_servers(cj, REPO_DIR) == {"vectorcraft", "pdfcraft"})
    ctx.check("an empty config is an empty set, never an error", registered_craft_servers({}, REPO_DIR) == set())
    cfgs = craft_server_configs(cj, REPO_DIR)
    ctx.check("configs parse through the manager's parser", set(cfgs) == {"vectorcraft", "pdfcraft"} and cfgs["vectorcraft"].command == sys.executable)
    from halo_harness.design.crafts import registered_craft_servers as via_crafts
    ctx.check("crafts.registered_craft_servers delegates", via_crafts(cj, REPO_DIR) == {"vectorcraft", "pdfcraft"})


@test
def test_probe_live_and_dead(ctx: Ctx):
    from halo_harness.design.crafts_probe import craft_server_configs, probe_crafts, probe_lines
    cj = {"mcpServers": {"vectorcraft": dict(FAKE),
                         "pdfcraft": {"type": "stdio", "command": "halo-no-such-binary-xyz", "args": [], "env": {}}}}
    env = dict(os.environ)
    env["FAKE_MCP_TOOL_COUNT"] = "9"
    rows = probe_crafts(craft_server_configs(cj, REPO_DIR), tool_env=env, cwd=REPO_DIR)
    by = {r["app"]: r for r in rows}
    ctx.check("the fake server under a craft name connects and its tools are counted", by["vectorcraft"]["state"] == "connected" and by["vectorcraft"]["tool_count"] >= 9)
    ctx.check("the render tool is reported missing on the fake", by["vectorcraft"]["render_tool"] == "export" and by["vectorcraft"]["render_present"] is False)
    ctx.check("a dead command is failed with a reason", by["pdfcraft"]["state"] != "connected" and by["pdfcraft"]["error"])
    lines = probe_lines(rows)
    ctx.check("the doctor lines say up/MISSING and the failure", any("up, " in l and "MISSING" in l for l in lines) and any("pdfcraft" in l and "up," not in l for l in lines))


@test
def test_doctor_command(ctx: Ctx):
    from halo_harness.design import cli as dcli
    from halo_harness.design import crafts_probe
    cj = {"mcpServers": {"vectorcraft": dict(FAKE)}}
    orig = crafts_probe.craft_server_configs
    crafts_probe.craft_server_configs = lambda claude_json=None, cwd=None: orig(cj, REPO_DIR)
    try:
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = dcli.cmd_design(["doctor"])
        out = buf.getvalue()
        ctx.check("doctor lists registration and hints at --probe", rc == 0 and "1 of 8 craft apps registered" in out and "--probe" in out)
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = dcli.cmd_design(["doctor", "--probe"])
        out = buf.getvalue()
        ctx.check("doctor --probe spawns and reports; a missing render tool fails the exit code", rc == 1 and "vectorcraft" in out and "MISSING" in out)
    finally:
        crafts_probe.craft_server_configs = orig


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="design crafts tests"))
