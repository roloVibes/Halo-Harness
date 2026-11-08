"""halo_harness.packs.test_run_mcp -- `halo pack test`'s MCP handshake (Halo 3.3.12.0 R4): start a pack's stdio
server, ask `initialize` and `tools/list`, read the tools, stop it.

    handshake(cfg, env, cwd, timeout) -> ([tool name], '' | the line saying what went wrong)
    declared_tools(r, server) -> the tool names the pack itself names for that server (a bio's tools.allow, a policy's
                                 when.tools: mcp__<server>__<tool> or mcp__plugin_<id>_<server>__<tool>)

One reader thread reads the server's stdout line by line into a queue; each request waits on the queue for its own
answer up to `timeout` seconds, so a server that never answers is one line ("no answer to initialize within 10 s").
The server's stdin is closed, it is waited for, and stopped when it does not end by itself; the reader ends with it.
"""

from __future__ import annotations

import json
import queue
import subprocess
import threading
import time
from pathlib import Path


def _ask(proc, lines: "queue.Queue", msg: dict, timeout: float) -> "tuple[dict | None, str]":
    proc.stdin.write((json.dumps(msg) + "\n").encode("utf-8"))
    proc.stdin.flush()
    end = time.monotonic() + timeout
    while True:
        left = end - time.monotonic()
        if left <= 0:
            return None, f"no answer to {msg['method']} within {timeout:g} s"
        try:
            line = lines.get(timeout=left)
        except queue.Empty:
            continue
        if line is None:
            return None, f"the server ended before it answered {msg['method']}"
        try:
            got = json.loads(line)
        except ValueError:
            continue  # a log line on stdout: not an answer
        if isinstance(got, dict) and got.get("id") == msg["id"]:
            if "error" in got:
                return None, f"{msg['method']} answered an error: {got['error']}"
            return got.get("result") if isinstance(got.get("result"), dict) else {}, ""


def _read(stream, lines: "queue.Queue") -> None:
    try:
        for raw in iter(stream.readline, b""):
            lines.put(raw.decode("utf-8", "replace"))
    except (OSError, ValueError):
        pass
    lines.put(None)


def handshake(cfg, env: dict, cwd, timeout: float) -> "tuple[list[str], str]":
    if cfg is None or not cfg.command:
        return [], "the server's entry in .mcp.json has no command"
    argv = [str(cfg.command)] + [str(a) for a in cfg.args or []]
    try:
        proc = subprocess.Popen(argv, cwd=str(cwd), env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL)
    except OSError as e:
        return [], f"the server did not start: {e}"
    lines: "queue.Queue" = queue.Queue()
    reader = threading.Thread(target=_read, args=(proc.stdout, lines), daemon=True)
    reader.start()
    tools, line = [], ""
    try:
        result, line = _ask(proc, lines, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                          "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                                                     "clientInfo": {"name": "halo-pack-test", "version": "1"}}}, timeout)
        if not line:
            proc.stdin.write(b'{"jsonrpc": "2.0", "method": "notifications/initialized"}\n')
            proc.stdin.flush()
            result, line = _ask(proc, lines, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}, timeout)
        if not line:
            raw = (result or {}).get("tools")
            bad = [t for t in raw or [] if not (isinstance(t, dict) and t.get("name") and isinstance(t.get("inputSchema"), dict))]
            if not isinstance(raw, list) or not raw:
                line = "tools/list answered no tools"
            elif bad:
                line = f"tools/list: {len(bad)} tool(s) without a name and an inputSchema"
            tools = [str(t.get("name")) for t in raw or [] if isinstance(t, dict)]
    except OSError as e:
        line = line or f"the server's stdin closed: {e}"
    finally:
        try:
            proc.stdin.close()
        except OSError:
            pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        reader.join(timeout=5)
    return tools, line


def declared_tools(r, server: str) -> "list[str]":
    from halo_harness.agents_yaml import _read_yaml_file
    names: "list[str]" = []
    for bio in sorted((Path(r.root) / "agents").glob("*.yaml")) if (Path(r.root) / "agents").is_dir() else []:
        allow = ((_read_yaml_file(bio) or {}).get("tools") or {}).get("allow") or []
        names += [a for a in allow if isinstance(a, str)]
    for e in (r.manifest.get("contributes") or {}).get("policy") or []:
        names += [t for t in ((e or {}).get("when") or {}).get("tools") or [] if isinstance(t, str)]
    out = []
    for n in names:
        if n.startswith("mcp__") and n.count("__") >= 2:
            srv, tool = n[5:].rsplit("__", 1)
            if srv in (server, f"plugin_{r.pack.id}_{server}", f"plugin_{r.pack.id.replace('-', '_')}_{server}"):
                out.append(tool)
    return list(dict.fromkeys(out))
