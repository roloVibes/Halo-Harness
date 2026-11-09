"""halo_harness.ext.host -- what Halo does for a pack's own code that the pack cannot do alone (Halo 3.3.13.0 R2,
extension API 1.2; docs/EXTENSION_API.md "The host services"). A pack imports `from halo_harness.ext import host`.
Each call goes through Halo's own code, so it follows the owner's config, the offline switch and the network choke
point the way Halo's own features do.

    host.state_dir()                          Halo's state folder (~/.halo, or the scratch home of a test)
    host.models(task="", cwd=None, limit=12)  model rows for a picker ({ref, label, provider, ...}), the best for
                                              `task` first (a word such as design, code, vision); [] when none
    host.media_models(kind="all")             ComfyUI's model rows, by what each makes (the cached inventory)
    host.mcp_servers(cwd=None)                {name: entry} of every MCP server a session in `cwd` sees
    host.mcp_probe(name, entry, cwd=None, env=None)
                                              start that server, list its tools, stop it:
                                              {state, tools: [names], error, elapsed}
    host.child_env(env=None)                  the environment Halo gives a tool's process (its provider keys left out)
    host.fetch(url, timeout_s=20, limit=2_000_000)
                                              a page's text through Halo's one network door (offline mode says no)
    host.halo_command()                       [python, "-m", "halo_harness"]: Halo as a child process
    host.comfy()                              the ComfyUI Halo is pointed at: queue(workflow, sets, source="", cwd=None)
                                              -> {prompt_id, source, label}, wait(pid, timeout_s, poll_s, on_progress),
                                              outputs(entry), view(filename, subfolder, type) -> bytes, url
    HostError                                 what a host call raises: its message and `status` (an HTTP-like code)
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Callable, Optional


class HostError(Exception):
    def __init__(self, message: str, status: int = 0):
        super().__init__(message)
        self.status = status


def state_dir() -> Path:
    from halo_harness.providers.config import default_state_dir
    return Path(default_state_dir())


def models(task: str = "", cwd=None, limit: int = 12) -> list:
    from halo_harness.studio import model as M
    rows = M.model_rows(state_dir(), cwd)
    if not task:
        return list(rows)[:limit]
    from halo_harness.capabilities import best_for
    return best_for(rows, task, limit=limit)


def media_models(kind: str = "all"):
    from halo_harness.providers.media_models import rows_for
    return rows_for(kind, state_dir())


def mcp_servers(cwd=None, claude_json: Optional[dict] = None) -> dict:
    from halo_harness.config.claude_json import load_claude_json, mcp_servers_for
    data = load_claude_json() if claude_json is None else claude_json
    return {str(k): v for k, v in mcp_servers_for(Path(cwd or os.getcwd()), data).items() if isinstance(v, dict)}


def child_env(env: Optional[dict] = None) -> dict:
    from halo_harness.providers.config import tool_child_env
    return dict(tool_child_env(dict(os.environ if env is None else env)))


def mcp_probe(name: str, entry: dict, cwd=None, env: Optional[dict] = None) -> dict:
    from halo_harness.mcp.manager import McpManager, mcp_timeout_s, parse_server
    cfg = parse_server(name, entry, scope="user")
    if cfg is None:
        return {"state": "failed", "tools": [], "error": f"{name}: not an MCP server entry", "elapsed": 0.0}
    mgr = McpManager({name: cfg}, tool_env=child_env() if env is None else dict(env), cwd=Path(cwd or os.getcwd()))
    h, t0, err = mgr.handles[name], time.monotonic(), ""
    try:
        h.start()
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
    finally:
        tools = [str(getattr(t, "name", None) or (t.get("name") if isinstance(t, dict) else "") or "")
                 for t in getattr(h, "tools", None) or []]
        out = {"state": getattr(h, "state", "unknown"), "tools": [t for t in tools if t],
               "error": getattr(h, "error", None) or getattr(h, "tools_fetch_failed_error", None) or err or "",
               "elapsed": round(time.monotonic() - t0, 2)}
        mgr.close_all(timeout=mcp_timeout_s() + 5.0)
    return out


def fetch(url: str, timeout_s: float = 20, limit: int = 2_000_000) -> str:
    from halo_harness.providers.http import urlopen_tls
    try:
        with urlopen_tls(url, timeout=timeout_s) as r:
            return r.read(limit).decode("utf-8", "replace")
    except Exception as e:
        raise HostError(f"{url}: {e}", getattr(e, "code", 0) or 0) from e


def halo_command() -> list:
    return [sys.executable, "-m", "halo_harness"]


class _Comfy:
    def __init__(self):
        from halo_harness.studio.media_api import _client
        self._c = _client()
        self.url = self._c.url

    def _call(self, fn: Callable, *a, **k):
        from halo_harness.media.comfy_client import ComfyError
        try:
            return fn(*a, **k)
        except ComfyError as e:
            raise HostError(str(e), e.status) from e

    def queue(self, workflow: str, sets: dict, source: str = "", cwd=None) -> dict:
        from halo_harness.media import comfy_ops
        from halo_harness.studio.media_api import _graph
        graph, src, label = self._call(_graph, self._c, workflow, source)
        pid = self._call(lambda: self._c.queue_prompt(comfy_ops.build_graph(self._c, graph, sets, cwd=cwd)))
        return {"prompt_id": pid, "source": src, "label": label}

    def wait(self, pid: str, timeout_s: float = 1800, poll_s: float = 1.0, on_progress=None):
        return self._call(self._c.wait, pid, timeout_s=timeout_s, poll_s=poll_s, on_progress=on_progress)

    def outputs(self, entry) -> list:
        return self._call(self._c.outputs, entry)

    def view(self, filename: str, subfolder: str = "", kind: str = "output") -> bytes:
        return self._call(self._c.view, filename, subfolder, kind)


def comfy() -> _Comfy:
    return _Comfy()
