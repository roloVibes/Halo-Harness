"""__NAME__'s `rg` MCP server: one tool, `search`, that runs ripgrep (https://github.com/BurntSushi/ripgrep, MIT OR
Unlicense) over the project. It starts once the owner grants `mcp:rg`; pack.yaml's `requires:` names rg with the
install line for each OS, and Halo never installs it.

How it wraps the tool -- the pattern to copy for any command-line tool:
- the program is found on PATH (`shutil.which`), never a path baked into the pack;
- it runs as an argument list, never a shell string, with `--` before the user's pattern;
- the input is checked first: a pattern of at most 200 characters, a folder inside the project;
- it has a time limit, and its output is cut to the first 50 matches.
Standard library only.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

INSTALL = {"win32": "winget install BurntSushi.ripgrep.MSVC", "darwin": "brew install ripgrep"}
TOOLS = [
    {"name": "search", "description": "Search the project's files for a pattern with ripgrep; one line per match.",
     "inputSchema": {"type": "object", "required": ["pattern"],
                     "properties": {"pattern": {"type": "string", "description": "a regular expression, 200 characters at most"},
                                    "path": {"type": "string", "description": "a folder of the project (default: all of it)"}}}},
]


def _text(text: str, error: bool = False) -> dict:
    return {"content": [{"type": "text", "text": text}], "isError": error}


def search(args: dict) -> dict:
    rg = shutil.which("rg")
    if rg is None:
        return _text("rg (ripgrep) is not installed here: " + INSTALL.get(sys.platform, "sudo apt install ripgrep"), True)
    pattern = args.get("pattern")
    if not isinstance(pattern, str) or not pattern.strip() or len(pattern) > 200:
        return _text("pattern: a non-empty string of at most 200 characters", True)
    root = Path(os.getcwd()).resolve()
    folder = (root / str(args.get("path") or ".")).resolve()
    if folder != root and root not in folder.parents:
        return _text(f"{args.get('path')!r} is not a folder of the project", True)
    argv = [rg, "--line-number", "--no-heading", "--color", "never", "--max-count", "50", "--", pattern, str(folder)]
    try:
        done = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20)
    except subprocess.TimeoutExpired:
        return _text("rg took longer than 20 s; narrow the folder", True)
    lines = done.stdout.splitlines()[:50]
    return _text("\n".join(lines) if lines else "no match", done.returncode not in (0, 1))


def answer(msg: dict):
    method, params = msg.get("method"), msg.get("params") or {}
    if "id" not in msg:
        return None
    if method == "initialize":
        result = {"protocolVersion": params.get("protocolVersion") or "2024-11-05", "capabilities": {"tools": {}},
                  "serverInfo": {"name": "__ID__-rg", "version": "0.1.0"}}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call" and params.get("name") == "search":
        result = search(params.get("arguments") or {})
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
            print(json.dumps(reply), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
