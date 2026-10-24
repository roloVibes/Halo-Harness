"""tests.helpers.packs_studio -- a real Studio server over a packs scratch home
(Halo 3.2.0.0 R3, tests/test_packs_studio_*.py).

    with PackStudio() as s:                      # PacksHome + start_server(cwd=repo, state_dir=home/.halo)
        s.install("doc-review", grants=["hooks"])
        status, body, headers = s.call("GET", "pack/registry")
        status, raw, headers = s.raw("/api/pack/doc-review/file/studio/notes.md")   # bytes, token header
        status, raw, headers = s.raw("/api/pack/x/file/a.js?t=" + s.token, auth=False)

Nothing reaches the real home (PacksHome scopes BRIDGE_TEST_HOME); no model is called.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request

from tests.helpers.packs_home import PacksHome


class PackStudio(PacksHome):
    def __enter__(self):
        super().__enter__()
        from halo_harness.studio.server import start_server
        self.srv = start_server(port=0, cwd=self.repo, state_dir=self.state)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.srv.server_address[1]}"
        self.token = self.srv.token
        return self

    def __exit__(self, *exc):
        self.srv.shutdown()
        self.srv.server_close()
        return super().__exit__(*exc)

    def install_pack(self, name: str = "doc-review", *, enable: bool = True, grants=()) -> None:
        self.install(self.source(name), enable=enable, grants=list(grants))

    def raw(self, path: str, *, method: str = "GET", body=None, auth: bool = True, token: "str | None" = None):
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method)
        if auth:
            req.add_header("Authorization", "Bearer " + (self.token if token is None else token))
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.status, r.read(), dict(r.headers)
        except urllib.error.HTTPError as e:
            return e.code, e.read(), dict(e.headers)

    def call(self, method: str, path: str, body=None):
        status, raw, headers = self.raw("/api/" + path, method=method, body=body)
        try:
            return status, json.loads(raw or b"{}"), headers
        except ValueError:
            return status, {"raw": raw.decode("utf-8", "replace")}, headers

    def frames(self):
        """A queue of every frame this server's bridge publishes from now on (no browser needed)."""
        from halo_harness.studio.events import bridge_for
        q = bridge_for(self.srv).subscribe("all")
        q.get(0.1)  # the subscribe's own `sessions` frame
        return q


def until(fn, timeout: float = 8.0, step: float = 0.1):
    """fn's first truthy answer within `timeout` seconds, else its last answer."""
    end = time.monotonic() + timeout
    got = fn()
    while not got and time.monotonic() < end:
        time.sleep(step)
        got = fn()
    return got


def next_kind(q, kind: str, timeout: float = 6.0):
    """The next frame of `kind` off a BrowserQueue, or None."""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        f = q.get(0.2)
        if f is not None and f.get("event") == kind:
            return f
    return None
