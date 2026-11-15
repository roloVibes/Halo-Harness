"""The fake MCP server (tests/helpers/fake_mcp_server.py) started the way Halo starts an MCP server, recording its pid
and the HALO_OWNER it was given in $R10_MCP_PIDFILE first (tests/test_closing.py, 3.6.0.0 R10)."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
path = os.environ.get("R10_MCP_PIDFILE")
if path:
    with open(path + ".tmp", "w", encoding="utf-8") as fh:
        json.dump({"pid": os.getpid(), "marker": os.environ.get("HALO_OWNER", "")}, fh)
    os.replace(path + ".tmp", path)
from tests.helpers.fake_mcp_server import main  # noqa: E402

main()
