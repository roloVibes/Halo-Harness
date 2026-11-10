"""tests.helpers.mock_copilot -- a loopback stand-in for Entra ID, the Work IQ A2A endpoint and Graph's /beta Copilot
Chat API (Halo 3.3.17.0 R1). Nothing here is a real tenant: `pretend-tenant`, app id
`00000000-0000-0000-0000-000000000000`, the account `someone@pretend-tenant.example`.

    with MockCopilot() as m:
        os.environ.update(m.env())          # HALO_COPILOT_AUTHORITY / _WORKIQ_URL / _GRAPH_URL
        m.scenario["workiq"] = "401"        # one-shot failure modes, see `_workiq`, `_chat`, `_token`

Entra: `GET /<tenant>/oauth2/v2.0/authorize` redirects (302) to the request's redirect_uri with a code and the state;
`POST .../token` checks the code against its PKCE challenge (S256) and redirect_uri, hands out access + refresh +
id tokens, refreshes (a revoked refresh token answers invalid_grant), and answers the device-code grant
authorization_pending twice before the token; `POST .../devicecode` starts one (interval 0).
Work IQ: `POST /a2a/` -- JSON-RPC SendMessage, `A2A-Version: 1.0` required, a bearer it issued required; a turn
answers a Message with a contextId (the second turn keeps the one it was sent) and two citations.
Graph: `POST /beta/copilot/conversations` -> {id}; `POST .../{id}/chat` -> the conversation with Copilot's reply: two
attributions, the sensitivity label "Confidential", the file URIs echoed, "web off" said when web grounding is off.
"""

from __future__ import annotations

import base64
import hashlib
import json
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

TENANT = "pretend-tenant"
CLIENT_ID = "00000000-0000-0000-0000-000000000000"
USER = "someone@pretend-tenant.example"


class _Server(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def _b64(obj) -> str:
    return base64.urlsafe_b64encode(json.dumps(obj).encode("utf-8")).rstrip(b"=").decode("ascii")


def id_token() -> str:
    return f"{_b64({'alg': 'none'})}.{_b64({'preferred_username': USER, 'name': 'Pretend Person', 'tid': TENANT})}.sig"


class MockCopilot:
    def __init__(self) -> None:
        self.codes: dict = {}          # code -> (challenge, redirect_uri)
        self.access: set = set()
        self.refresh: set = set()
        self.revoked: set = set()
        self.device_polls = 0
        self.scenario: dict = {}       # endpoint -> failure mode (consumed once unless it ends with "!")
        self.requests: list = []       # (method, path, headers, body) of every call
        self.n = 0
        self.lock = threading.Lock()
        self.server = _Server(("127.0.0.1", 0), self._handler())
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def env(self) -> dict:
        return {"HALO_COPILOT_AUTHORITY": self.url, "HALO_COPILOT_WORKIQ_URL": f"{self.url}/a2a/",
                "HALO_COPILOT_GRAPH_URL": self.url}

    def __enter__(self):
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()

    def take(self, endpoint: str) -> str:
        mode = self.scenario.get(endpoint, "")
        if mode and not mode.endswith("!"):
            self.scenario.pop(endpoint, None)
        return mode.rstrip("!")

    def tokens(self) -> dict:
        with self.lock:
            self.n += 1
            at, rt = f"at-{self.n}", f"rt-{self.n}"
            self.access.add(at)
            self.refresh.add(rt)
        return {"token_type": "Bearer", "access_token": at, "refresh_token": rt, "expires_in": 3600, "id_token": id_token()}

    def calls(self, path_part: str) -> list:
        return [r for r in self.requests if path_part in r[1]]

    def _handler(self):
        mock = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, status, obj=None, headers=None):
                body = json.dumps(obj).encode("utf-8") if obj is not None else b""
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                for k, v in (headers or {}).items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(body)

            def _body(self):
                n = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(n).decode("utf-8") if n else ""
                if "json" in (self.headers.get("Content-Type") or ""):
                    return json.loads(raw) if raw else {}
                return {k: v[0] for k, v in urllib.parse.parse_qs(raw).items()}

            def do_GET(self):
                mock.requests.append(("GET", self.path, dict(self.headers), None))
                u = urllib.parse.urlparse(self.path)
                if u.path.endswith("/oauth2/v2.0/authorize"):
                    q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
                    code = f"code-{len(mock.codes) + 1}"
                    mock.codes[code] = (q.get("code_challenge"), q.get("redirect_uri"), q.get("code_challenge_method"))
                    extra = {"error": "access_denied", "error_description": "AADSTS65001: The user or administrator has "
                             "not consented to use the application."} if mock.take("authorize") == "consent" else {"code": code}
                    loc = f"{q['redirect_uri']}?{urllib.parse.urlencode({**extra, 'state': q.get('state', '')})}"
                    return self._send(302, None, {"Location": loc})
                return self._send(404, {"error": "not found"})

            def do_POST(self):
                body = self._body()
                mock.requests.append(("POST", self.path, dict(self.headers), body))
                p = urllib.parse.urlparse(self.path).path
                from tests.helpers.mock_copilot_routes import chat, devicecode, token, workiq
                if p.endswith("/oauth2/v2.0/token"):
                    return token(mock, self, body)
                if p.endswith("/oauth2/v2.0/devicecode"):
                    return devicecode(mock, self, body)
                if p.rstrip("/") == "/a2a":
                    return workiq(mock, self, body)
                if p.startswith("/beta/copilot/conversations"):
                    return chat(mock, self, body, p)
                return self._send(404, {"error": "not found"})

        return H


def pkce_ok(verifier: str, challenge: str) -> bool:
    digest = hashlib.sha256((verifier or "").encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii") == challenge
