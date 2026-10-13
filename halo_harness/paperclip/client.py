"""halo_harness.paperclip.client -- a stdlib REST client for a Paperclip
instance (Halo 2.2.0 round C1). Paperclip (github.com/paperclipai/paperclip)
is the company: agents with titles and reporting lines, goals, projects,
issues, heartbeat runs and budgets, served at `http://127.0.0.1:3100/api`
by default. Halo talks to it two ways:

* as the board (Studio's Org mode, `halo paperclip ...`): the base URL and
  a board token from `~/.halo/paperclip.json` (loopback `local_trusted`
  mode needs no token at all);
* as an agent inside a heartbeat run (`halo paperclip-run`): the
  `PAPERCLIP_API_URL` / `PAPERCLIP_API_KEY` / `PAPERCLIP_AGENT_ID` /
  `PAPERCLIP_COMPANY_ID` / `PAPERCLIP_RUN_ID` environment the process
  adapter injects (observed live 2026-10-11), the run id sent as
  `X-Paperclip-Run-Id` on every mutating call.

Every method returns the decoded JSON; a non-2xx answer raises
`PaperclipError(status, message)`. Nothing here imports Textual or the
agent loop.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Optional

DEFAULT_URL = "http://127.0.0.1:3100"
CONFIG_NAME = "paperclip.json"


class PaperclipError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(f"Paperclip {status}: {message}")
        self.status = status
        self.message = message


def config_path(state_dir: Optional[Path] = None) -> Path:
    if state_dir is None:
        from halo_harness.providers.config import default_state_dir
        state_dir = Path(default_state_dir())
    return Path(state_dir) / CONFIG_NAME


def load_config(state_dir: Optional[Path] = None) -> dict:
    p = config_path(state_dir)
    try:
        data = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}
    except (OSError, ValueError):
        data = {}
    return data if isinstance(data, dict) else {}


def save_config(data: dict, state_dir: Optional[Path] = None) -> Path:
    p = config_path(state_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass
    return p


class Paperclip:
    def __init__(self, base_url: str = DEFAULT_URL, token: str = "", *, run_id: str = "", timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        if self.base_url.endswith("/api"):
            self.base_url = self.base_url[:-4]
        self.token = token or ""
        self.run_id = run_id or ""
        self.timeout = timeout

    # -- construction -----------------------------------------------------------
    @classmethod
    def from_config(cls, state_dir: Optional[Path] = None, *, timeout: float = 30.0) -> "Paperclip":
        cfg = load_config(state_dir)
        return cls(str(cfg.get("base_url") or DEFAULT_URL), str(cfg.get("token") or ""), timeout=timeout)

    @classmethod
    def from_env(cls, env: Optional[dict] = None) -> "Paperclip":
        env = os.environ if env is None else env
        return cls(env.get("PAPERCLIP_API_URL") or env.get("PAPERCLIP_RUNTIME_API_URL") or DEFAULT_URL,
                   env.get("PAPERCLIP_API_KEY", ""), run_id=env.get("PAPERCLIP_RUN_ID", ""))

    # -- transport ----------------------------------------------------------------
    def request(self, method: str, path: str, body: Any = None, query: Optional[dict] = None) -> Any:
        url = f"{self.base_url}/api/{path.lstrip('/')}"
        if query:
            url += "?" + urllib.parse.urlencode({k: v for k, v in query.items() if v is not None})
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, method=method, data=data)
        req.add_header("Accept", "application/json")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        if self.run_id and method in ("POST", "PUT", "PATCH", "DELETE"):
            req.add_header("X-Paperclip-Run-Id", self.run_id)
        from halo_harness.providers.http import UpstreamConnectError, urlopen_tls
        try:
            with urlopen_tls(req, timeout=self.timeout) as r:
                raw = r.read()
        except urllib.error.HTTPError as e:
            raw = e.read() or b""
            try:
                msg = json.loads(raw).get("error") or json.loads(raw).get("message") or raw.decode("utf-8", "replace")
            except (ValueError, AttributeError):
                msg = raw.decode("utf-8", "replace")
            raise PaperclipError(e.code, str(msg)[:400]) from None
        except (urllib.error.URLError, OSError, UpstreamConnectError) as e:
            raise PaperclipError(0, f"cannot reach {self.base_url}: {e}") from None
        return json.loads(raw) if raw else None

    def get(self, path: str, **query):
        return self.request("GET", path, query=query or None)

    def post(self, path: str, body: Any = None):
        return self.request("POST", path, body if body is not None else {})

    def patch(self, path: str, body: Any):
        return self.request("PATCH", path, body)

    def delete(self, path: str):
        return self.request("DELETE", path)

    # -- instance and companies ----------------------------------------------------
    def health(self) -> dict:
        return self.get("health") or {}

    def reachable(self, timeout: float = 3.0) -> bool:
        """A health probe with its own short timeout: a host that drops
        packets answers False in seconds, not after the request timeout."""
        saved, self.timeout = self.timeout, min(self.timeout, timeout)
        try:
            return bool(self.health().get("status") == "ok")
        except PaperclipError:
            return False
        finally:
            self.timeout = saved

    def companies(self) -> list:
        return self.get("companies") or []

    def company(self, cid: str) -> dict:
        return self.get(f"companies/{cid}") or {}

    def create_company(self, name: str, description: str = "") -> dict:
        return self.post("companies", {"name": name, "description": description})

    # -- agents and the org chart --------------------------------------------------
    def me(self) -> dict:
        return self.get("agents/me") or {}

    def agents(self, cid: str) -> list:
        return self.get(f"companies/{cid}/agents") or []

    def agent(self, aid: str) -> dict:
        return self.get(f"agents/{aid}") or {}

    def create_agent(self, cid: str, payload: dict) -> dict:
        return self.post(f"companies/{cid}/agents", payload)

    def update_agent(self, aid: str, payload: dict) -> dict:
        return self.patch(f"agents/{aid}", payload)

    def delete_agent(self, aid: str):
        return self.delete(f"agents/{aid}")

    def agent_action(self, aid: str, action: str) -> Any:
        """pause | resume | approve | terminate | wakeup | heartbeat/invoke"""
        return self.post(f"agents/{aid}/{action}", {})

    def org(self, cid: str) -> Any:
        return self.get(f"companies/{cid}/org")

    # -- issues and runs ---------------------------------------------------------------
    def issues(self, cid: str, view: Optional[str] = None) -> list:
        data = self.get(f"companies/{cid}/issues", view=view)
        if isinstance(data, dict):
            data = data.get("issues") or data.get("items") or []
        return data or []

    def create_issue(self, cid: str, payload: dict) -> dict:
        return self.post(f"companies/{cid}/issues", payload)

    def issue(self, iid: str) -> dict:
        return self.get(f"issues/{iid}") or {}

    def update_issue(self, iid: str, payload: dict) -> dict:
        return self.patch(f"issues/{iid}", payload)

    def checkout(self, iid: str, agent_id: str, expected: Optional[list] = None) -> Any:
        body = {"agentId": agent_id}
        if expected:
            body["expectedStatuses"] = expected
        return self.post(f"issues/{iid}/checkout", body)

    def comment(self, iid: str, body: str, **extra) -> dict:
        return self.post(f"issues/{iid}/comments", {"body": body, **extra})

    def heartbeat_context(self, iid: str) -> Any:
        return self.get(f"issues/{iid}/heartbeat-context")

    def inbox_mine(self) -> Any:
        return self.get("agents/me/inbox/mine")

    def heartbeat_runs(self, cid: str) -> list:
        return self.get(f"companies/{cid}/heartbeat-runs") or []

    def run(self, run_id: str) -> dict:
        return self.get(f"heartbeat-runs/{run_id}") or {}

    def cost_event(self, cid: str, payload: dict) -> Any:
        return self.post(f"companies/{cid}/cost-events", payload)
