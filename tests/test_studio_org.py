"""tests.test_studio_org -- Studio's Org mode backend (Halo 2.2.0 round C4)
over tests/helpers/fake_paperclip.py: `/api/pc/status` (reachable or not),
the proxy (GET/POST/PATCH forwarded with the board token, Paperclip's
status passed through, an unreachable instance a 502), `/api/pc/sync` and
`/api/pc/pull`, `/api/pc/link`, and the install endpoint's refusals; all
behind Studio's own token guard.
"""

from __future__ import annotations

import json
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.fake_paperclip import FakePaperclip  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


class _Studio:
    def __enter__(self):
        from halo_harness.providers.config import default_state_dir
        from halo_harness.studio.server import start_server
        self.state = Path(default_state_dir())
        self.srv = start_server(port=0, cwd=self.state.parent / "proj", state_dir=self.state)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.srv.server_address[1]}"
        return self

    def __exit__(self, *a):
        self.srv.shutdown()
        self.srv.server_close()

    def call(self, method, path, body=None, token=None):
        req = urllib.request.Request(self.base + path, method=method, data=json.dumps(body).encode() if body is not None else None)
        req.add_header("Authorization", "Bearer " + (self.srv.token if token is None else token))
        if body is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")


@test
def test_status_proxy_sync_pull_and_link(ctx: Ctx):
    from halo_harness.paperclip.client import load_config, save_config
    fake = FakePaperclip(company_name="Halo Harness", require_token="board-tok")
    try:
        with _Studio() as s:
            save_config({"base_url": "http://127.0.0.1:1"}, s.state)
            status, st = s.call("GET", "/api/pc/status")
            ctx.check("status over an unreachable instance says so without failing", status == 200 and st["reachable"] is False and st["error"])
            ctx.check("the proxy answers 502 for an unreachable instance", s.call("GET", "/api/pc/companies")[0] == 502)
            save_config({"base_url": fake.base_url, "token": "board-tok"}, s.state)
            status, st = s.call("GET", "/api/pc/status")
            ctx.check("status reads health and companies through the board token", status == 200 and st["reachable"] and st["companies"][0]["name"] == "Halo Harness" and st["token"] is True)
            ctx.check("the token never appears in the status payload", "board-tok" not in json.dumps(st))
            ctx.check("the proxy forwards GET with the board token", s.call("GET", "/api/pc/companies")[1][0]["name"] == "Halo Harness"
                      and any(h.get("Authorization") == "Bearer board-tok" for m, p, b, h in fake.requests))
            cid = fake.company["id"]
            status, agent = s.call("POST", f"/api/pc/companies/{cid}/agents", {"name": "ceo-bot", "role": "ceo", "adapterType": "process"})
            ctx.check("the proxy forwards POST bodies", status == 200 and agent["name"] == "ceo-bot")
            status, upd = s.call("PATCH", f"/api/pc/agents/{agent['id']}", {"title": "Chief"})
            ctx.check("the proxy forwards PATCH", status == 200 and upd["title"] == "Chief")
            ctx.check("Paperclip's own status codes pass through", s.call("GET", "/api/pc/agents/nope")[0] == 404)
            ctx.check("the guard still applies to pc routes", s.call("GET", "/api/pc/status", token="wrong")[0] == 401)
            status, r = s.call("POST", "/api/pc/sync", {"lineup": "halo-dev-cycle", "company_id": cid})
            ctx.check("sync creates the lineup's agents in the company", status == 200 and r["agents"] == 7 and any(line.startswith("boss") for line in r["org"]))
            status, r = s.call("POST", "/api/pc/sync", {"lineup": "nope", "company_id": cid})
            ctx.check("sync of an unknown lineup is a 422 with the reason", status == 422 and "nope" in r["error"])
            status, r = s.call("POST", "/api/pc/pull", {"lineup": "halo-dev-cycle", "company_id": cid})
            ctx.check("pull writes org.positions back", status == 200 and len(r["org"]["positions"]) == 7)
            status, r = s.call("POST", "/api/pc/link", {"company_id": cid})
            ctx.check("link remembers the company and reports the token as a bool", status == 200 and r["company_id"] == cid and r["token"] is True and load_config(s.state)["company_id"] == cid)
            status, r = s.call("POST", "/api/pc/install")
            ctx.check("install refuses when an instance is already reachable (or node is missing)", status in (409, 422))
    finally:
        fake.close()


@test
def test_org_capture_tool_flags(ctx: Ctx):
    tools = Path(__file__).resolve().parent.parent / "tools"
    text = (tools / "capture_studio.py").read_text(encoding="utf-8") + (tools / "capture_org_design.py").read_text(encoding="utf-8")
    ctx.check("the capture tool has an --org mode over the fake Paperclip", "--org" in text and "FakePaperclip" in text)
    routes = (Path(__file__).resolve().parent.parent / "halo_harness" / "studio" / "ui" / "src" / "routes" / "index.tsx").read_text(encoding="utf-8")
    ctx.check("Org is a React section (3.0.7.0 R3), not the framed page", "panels: orgPanels, view: OrgView" in routes)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="studio org tests"))
