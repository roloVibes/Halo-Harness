"""__NAME__'s MCP server `words` (.mcp.json names it; it starts once the owner grants `mcp:words`): a stdio JSON-RPC
server, one JSON message per line, with one tool, `count_words`, over a text file in the project. A session sees it as
mcp__plugin___ID___words__count_words. Standard library only; `halo pack test` starts it, asks `initialize` and
`tools/list`, and stops it.
"""

import json
import os
import sys
from pathlib import Path

TOOLS = [
    {"name": "count_words", "description": "Count the words and lines of a text file in the project.",
     "inputSchema": {"type": "object", "properties": {"path": {"type": "string", "description": "the file, from the project"}},
                     "required": ["path"]}},
]


def count_words(args: dict) -> dict:
    root = Path(os.getcwd()).resolve()
    target = (root / str((args or {}).get("path") or "")).resolve()
    if root not in target.parents or not target.is_file():
        return {"content": [{"type": "text", "text": f"{args.get('path')!r} is not a file in the project"}], "isError": True}
    text = target.read_text(encoding="utf-8", errors="replace")
    return {"content": [{"type": "text", "text": f"{len(text.split())} words, {len(text.splitlines())} lines"}],
            "isError": False}


def answer(msg: dict):
    """The reply to one request (None for a notification)."""
    method, params = msg.get("method"), msg.get("params") or {}
    if "id" not in msg:
        return None
    if method == "initialize":
        result = {"protocolVersion": params.get("protocolVersion") or "2024-11-05", "capabilities": {"tools": {}},
                  "serverInfo": {"name": "__ID__-words", "version": "0.1.0"}}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call" and params.get("name") == "count_words":
        result = count_words(params.get("arguments") or {})
    else:
        return {"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32601, "message": f"no method {method}"}}
    return {"jsonrpc": "2.0", "id": msg["id"], "result": result}


def main() -> int:
    for line in sys.stdin:
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        reply = answer(msg) if isinstance(msg, dict) else None
        if reply is not None:
            sys.stdout.write(json.dumps(reply) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
