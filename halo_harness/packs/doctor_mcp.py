"""halo_harness.packs.doctor_mcp -- `halo pack doctor`'s "not-on-path" rows (Halo 3.3.10.0 R3): a running pack's
`.mcp.json` server whose `command` this machine does not have.

A pack may name a program its owner installs (the concord pack's `concord-mcp`, from `npm install -g
@concord-ai/concord-mcp`); Halo never installs it. Until it is on PATH the server does not start, so the doctor
says so, one warns row per server:

    concord: MCP server concord runs concord-mcp, which is not on PATH -> install it (the pack's README says how), or
    put its folder on PATH

A command with a placeholder (`${halo_python}`, Halo's own Python; `${CLAUDE_PLUGIN_ROOT}/...`, a file of the pack)
and a server reached by url are not checked: Halo puts those in itself.

    rows(pack) -> [{severity, check, text, fix, path}]
"""

from __future__ import annotations

import shutil
from pathlib import Path


def rows(pack) -> "list[dict]":
    from halo_harness.packs.manifest import mcp_servers
    out = []
    for name, raw in sorted(mcp_servers(pack.root).items()):
        cmd = raw.get("command") if isinstance(raw, dict) else None
        if not isinstance(cmd, str) or not cmd.strip() or "${" in cmd:
            continue
        cmd = cmd.strip()
        if Path(cmd).is_absolute() and Path(cmd).is_file():
            continue
        if shutil.which(cmd) is not None:
            continue
        out.append({"severity": "warns", "check": "not-on-path", "path": str(Path(pack.root) / ".mcp.json"),
                    "fix": "install it (the pack's README says how), or put its folder on PATH",
                    "text": f"{pack.id}: MCP server {name} runs {cmd}, which is not on PATH"})
    return out
