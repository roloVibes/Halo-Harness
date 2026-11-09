"""A stand-in craft app for the design pack's tests: an MCP server on stdio (newline-delimited JSON-RPC 2.0) that
answers `initialize` and `tools/list` with FAKE_CRAFT_TOOLS tools (default 5) named `tool_0..`, none of them a craft
app's render tool, so a probe finds it up and its render step missing. Stdlib only: `python fake_craft.py`.
"""

import json
import os
import sys


def answer(msg: dict):
    method, mid = msg.get("method"), msg.get("id")
    if mid is None:  # a notification (notifications/initialized): no answer
        return None
    if method == "initialize":
        version = (msg.get("params") or {}).get("protocolVersion") or "2024-11-05"
        result = {"protocolVersion": version, "capabilities": {"tools": {}},
                  "serverInfo": {"name": "fake-craft", "version": "1.0.0"}}
    elif method == "tools/list":
        n = int(os.environ.get("FAKE_CRAFT_TOOLS") or 5)
        result = {"tools": [{"name": f"tool_{i}", "description": f"tool {i} of the fake craft app",
                             "inputSchema": {"type": "object", "properties": {}}} for i in range(n)]}
    elif method == "ping":
        result = {}
    else:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"no method {method}"}}
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            out = answer(json.loads(line))
        except ValueError:
            continue
        if out is not None:
            sys.stdout.write(json.dumps(out) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
