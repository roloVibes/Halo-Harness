"""tests.helpers.fake_paperclip -- a stdlib stand-in for a Paperclip server
(Halo 2.2.0): the routes Halo's client, adapter and sync touch, with the
response shapes observed on a real instance (2026-10-11). In-memory, one
company, run in a daemon thread; `requests` records every call."""

from __future__ import annotations

import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit


class FakePaperclip:
    def __init__(self, *, company_name: str = "Fake Co", require_token: str = ""):
        self.company = {"id": str(uuid.uuid4()), "name": company_name, "status": "active", "issuePrefix": "FAK"}
        self.agents: dict = {}
        self.issues: dict = {}
        self.comments: list = []
        self.requests: list = []
        self.require_token = require_token
        self._srv = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self._srv.daemon_threads = True
        threading.Thread(target=self._srv.serve_forever, daemon=True).start()
        self.base_url = f"http://127.0.0.1:{self._srv.server_address[1]}"

    def close(self):
        self._srv.shutdown()
        self._srv.server_close()

    def add_agent(self, name: str, **fields) -> dict:
        a = {"id": str(uuid.uuid4()), "companyId": self.company["id"], "name": name, "role": "engineer", "status": "idle",
             "reportsTo": None, "title": None, "metadata": {}, "adapterType": "process", "adapterConfig": {}, **fields}
        self.agents[a["id"]] = a
        return a

    def add_issue(self, title: str, assignee: str = "", status: str = "todo", **fields) -> dict:
        n = len(self.issues) + 1
        i = {"id": str(uuid.uuid4()), "companyId": self.company["id"], "identifier": f"FAK-{n}", "title": title,
             "description": fields.pop("description", ""), "status": status, "assigneeAgentId": assignee or None,
             "executionRunId": None, "checkoutRunId": None, "priority": 3, "createdAt": f"2026-10-11T00:00:{n:02d}Z", **fields}
        self.issues[i["id"]] = i
        return i

    def org(self) -> list:
        def node(a):
            return {"id": a["id"], "name": a["name"], "role": a["role"], "status": a["status"],
                    "reports": [node(b) for b in self.agents.values() if b.get("reportsTo") == a["id"]]}
        return [node(a) for a in self.agents.values() if not a.get("reportsTo")]

    def _handler(self):
        fake = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, status, obj):
                body = json.dumps(obj).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _body(self):
                n = int(self.headers.get("Content-Length") or 0)
                return json.loads(self.rfile.read(n) or b"{}") if n else {}

            def _route(self, method):
                path = urlsplit(self.path).path
                body = self._body() if method in ("POST", "PATCH") else {}
                fake.requests.append((method, path, body, dict(self.headers)))
                if fake.require_token and self.headers.get("Authorization") != f"Bearer {fake.require_token}":
                    return self._send(401, {"error": "unauthorized"})
                parts = path.strip("/").split("/")
                cid = fake.company["id"]
                if path == "/api/health":
                    return self._send(200, {"status": "ok", "version": "fake", "deploymentMode": "local_trusted", "authReady": True})
                if path == "/api/companies" and method == "GET":
                    return self._send(200, [fake.company])
                if path == "/api/companies" and method == "POST":
                    fake.company = {**fake.company, "name": body.get("name", fake.company["name"])}
                    return self._send(201, fake.company)
                if path == f"/api/companies/{cid}":
                    return self._send(200, fake.company)
                if path == f"/api/companies/{cid}/agents" and method == "GET":
                    return self._send(200, list(fake.agents.values()))
                if path == f"/api/companies/{cid}/agents" and method == "POST":
                    return self._send(201, fake.add_agent(body.get("name", "agent"), **{k: v for k, v in body.items() if k != "name"}))
                if path == f"/api/companies/{cid}/org":
                    return self._send(200, fake.org())
                if path == f"/api/companies/{cid}/issues" and method == "GET":
                    return self._send(200, list(fake.issues.values()))
                if path == f"/api/companies/{cid}/issues" and method == "POST":
                    return self._send(201, fake.add_issue(body.get("title", ""), body.get("assigneeAgentId", ""), body.get("status", "todo"), description=body.get("description", "")))
                if path == "/api/agents/me":
                    me = next(iter(fake.agents.values()), None)
                    return self._send(200, me) if me else self._send(401, {"error": "no agent"})
                if parts[:2] == ["api", "agents"] and len(parts) == 3:
                    a = fake.agents.get(parts[2])
                    if not a:
                        return self._send(404, {"error": "no agent"})
                    if method == "PATCH":
                        a.update({k: v for k, v in body.items() if k != "replaceAdapterConfig"})
                    return self._send(200, a)
                if parts[:2] == ["api", "agents"] and len(parts) >= 4:
                    return self._send(202, {"id": str(uuid.uuid4()), "agentId": parts[2], "status": "queued"})
                if parts[:2] == ["api", "issues"] and len(parts) >= 3:
                    i = fake.issues.get(parts[2])
                    if not i:
                        return self._send(404, {"error": "no issue"})
                    if len(parts) == 3:
                        if method == "PATCH":
                            i.update(body)
                        return self._send(200, i)
                    if parts[3] == "checkout":
                        i["status"] = "in_progress"
                        i["checkoutRunId"] = self.headers.get("X-Paperclip-Run-Id")
                        return self._send(200, i)
                    if parts[3] == "comments":
                        c = {"id": str(uuid.uuid4()), "issueId": i["id"], "body": body.get("body", ""), "runId": self.headers.get("X-Paperclip-Run-Id")}
                        fake.comments.append(c)
                        return self._send(201, c)
                    if parts[3] == "heartbeat-context":
                        return self._send(200, {"issue": i, "goal": {"title": "Ship it"}, "project": {"name": "Halo"}, "ancestors": [], "wakeComment": None})
                return self._send(404, {"error": f"no fake route for {method} {path}"})

            def do_GET(self):
                self._route("GET")

            def do_POST(self):
                self._route("POST")

            def do_PATCH(self):
                self._route("PATCH")

            def do_DELETE(self):
                self._route("DELETE")

        return H
