"""The Documentation Review pack's lint MCP server (`.mcp.json` names it; it
starts once you grant `mcp:lint`): a stdio JSON-RPC server, one JSON message
per line, with two tools over a Markdown file -- check_links (relative links
whose target is not there) and check_headings (a second title, a skipped
level). Standard library only, plus halo_harness.ext for the pack's settings
(`max_findings`), read when that import works."""

import json
import os
import re
import sys
from pathlib import Path

try:
    from halo_harness.ext import API_VERSION, get_config
except ImportError:  # the `python` on PATH is not the one Halo runs in: the defaults
    API_VERSION, get_config = "1.0", None

LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)")
HEADING = re.compile(r"^(#{1,6})\s+\S")
TOOLS = [
    {"name": "check_links", "description": "List the relative links in a Markdown file whose target is not there.",
     "inputSchema": {"type": "object", "properties": {"path": {"type": "string", "description": "the Markdown file"}},
                     "required": ["path"]}},
    {"name": "check_headings", "description": "List a second title and every skipped heading level in a Markdown file.",
     "inputSchema": {"type": "object", "properties": {"path": {"type": "string", "description": "the Markdown file"}},
                     "required": ["path"]}},
]


def _limit() -> int:
    value = get_config("doc-review", "max_findings", 20) if get_config else 20
    return value if isinstance(value, int) and value > 0 else 20


def check_links(path: Path) -> "list[str]":
    out = []
    for no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        for target in LINK.findall(line):
            if re.match(r"^[a-z]+:", target, re.I) or target.startswith("#"):
                continue
            if not (path.parent / target.split("#", 1)[0]).exists():
                out.append(f"{path.name} line {no}: {target} is not there")
    return out


def check_headings(path: Path) -> "list[str]":
    out, last, titles = [], 0, 0
    for no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        m = HEADING.match(line)
        if not m:
            continue
        level = len(m.group(1))
        titles += level == 1
        if level == 1 and titles > 1:
            out.append(f"{path.name} line {no}: a second title")
        if last and level > last + 1:
            out.append(f"{path.name} line {no}: heading level {level} after level {last}")
        last = level
    return out


def call_tool(name: str, args: dict) -> dict:
    target = Path(os.getcwd()) / str((args or {}).get("path") or "")
    if name not in ("check_links", "check_headings"):
        return {"content": [{"type": "text", "text": f"no tool {name}"}], "isError": True}
    if not target.is_file():
        return {"content": [{"type": "text", "text": f"{target} is not a file"}], "isError": True}
    found = (check_links if name == "check_links" else check_headings)(target)[:_limit()]
    return {"content": [{"type": "text", "text": "\n".join(found) or "nothing found"}], "isError": False}


def answer(msg: dict):
    """The reply to one request (None for a notification)."""
    method, params = msg.get("method"), msg.get("params") or {}
    if "id" not in msg:
        return None
    if method == "initialize":
        result = {"protocolVersion": params.get("protocolVersion") or "2024-11-05", "capabilities": {"tools": {}},
                  "serverInfo": {"name": "doc-review-lint", "version": "1.0.0", "extensionApi": API_VERSION}}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        result = call_tool(str(params.get("name") or ""), params.get("arguments") or {})
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
