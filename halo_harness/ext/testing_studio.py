"""halo_harness.ext.testing_studio -- a live Studio for a pack's own tests (Halo 3.3.13.0 R2, extension API 1.2;
`testing.scratch_home` and `testing.studio`, docs/EXTENSION_API.md "The stable surface").

    home = testing.scratch_home()             # FIRST, before Halo reads its home: this process uses a fresh folder
    with testing.studio(PACK) as s:            # the pack linked into that home, enabled with every grant it asks
        status, body = s.call("GET", s.route("projects"))        # /api/packs/<id>/<prefix>/projects, with the token
        status, headers, raw = s.raw(s.route("files/a/b.html"))  # bytes, as an iframe gets them (?k= the pack's key)
        mod = s.module("server/store.py")      # one of the pack's modules, the same one Studio's routes import
        feed = s.listen(); feed.wait(lambda kind, frame: kind == "pack_live", 5); feed.close()

Studio runs in this process on a free loopback port, on Halo's own server code; nothing reaches the network (the
scratch home's offline switch is on unless the test turns it off) and no model is called unless the pack's code does.
"""

from __future__ import annotations

import json
import os
import queue
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

KEYS = ("OPENROUTER_", "DATABRICKS_", "ANTHROPIC_", "OPENAI_", "TYPESAFE_", "GEMINI_", "GOOGLE_API")


def scratch_home(prefix: str = "halo-pack-tests-") -> Path:
    """Point this process at a fresh home (or keep the one a test runner already gave it) and return it."""
    if os.environ.get("BRIDGE_TEST_HOME"):
        return Path(os.environ["BRIDGE_TEST_HOME"])
    home = Path(tempfile.mkdtemp(prefix=prefix))
    (home / ".halo").mkdir()
    for k in [k for k in os.environ if k.startswith(KEYS)]:
        os.environ.pop(k, None)
    os.environ.update({"BRIDGE_TEST_HOME": str(home), "BRIDGE_TEST_NO_BACKGROUND_NET": "1",
                       "OLLAMA_HOST": "http://127.0.0.1:9", "HALO_PACK_TEST": "1"})
    return home


def pack_module(folder, rel: str):
    """The pack's module `rel` (server/store.py) imported through its folder as the package `halo_packs.<id>`: the
    same module Studio's routes import when they serve that folder, so a test's fake set on it is the one they use."""
    import importlib
    from halo_harness.packs.manifest import load_manifest
    from halo_harness.studio.packs_routes import ensure_package
    folder = Path(folder).resolve()
    data, _problems = load_manifest(folder)
    name = ensure_package(str((data or {}).get("id") or folder.name), folder)
    return importlib.import_module(name + "." + ".".join(Path(rel).with_suffix("").parts))


class Feed:
    """The live feed's frames, `(kind, frame)` in a queue."""

    def __init__(self, url: str):
        self.frames: "queue.Queue" = queue.Queue()
        self.resp = urllib.request.urlopen(url, timeout=10)
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        kind = ""
        try:
            for raw in self.resp:
                line = raw.decode("utf-8").rstrip("\r\n")
                if line.startswith("event: "):
                    kind = line[7:]
                elif line.startswith("data: "):
                    self.frames.put((kind, json.loads(line[6:])))
        except Exception:
            pass

    def wait(self, pred, timeout: float):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            try:
                kind, frame = self.frames.get(timeout=max(0.01, end - time.monotonic()))
            except queue.Empty:
                break
            if pred(kind, frame):
                return frame
        return None

    def close(self) -> None:
        try:
            import socket
            self.resp.fp.raw._sock.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass


class studio:  # noqa: N801  (used as `with testing.studio(folder) as s`)
    def __init__(self, folder, cwd=None, grants=None):
        self.folder, self.cwd, self.grants = Path(folder).resolve(), cwd, grants

    def __enter__(self) -> "studio":
        if not os.environ.get("BRIDGE_TEST_HOME"):
            raise RuntimeError("call testing.scratch_home() first: a test's Studio runs in a scratch home")
        from halo_harness.packs import grants as G
        from halo_harness.packs import registry
        from halo_harness.packs.discover import find
        from halo_harness.packs.link import link
        from halo_harness.providers.config import default_state_dir
        from halo_harness.studio.server import start_server
        self.state = Path(default_state_dir())
        self.cwd = Path(self.cwd or self.state.parent / "proj")
        self.cwd.mkdir(parents=True, exist_ok=True)
        registry.invalidate()
        pack = find(self.folder.name, cwd=self.cwd, state_dir=self.state)
        if pack is None:
            ok, lines = link(str(self.folder), cwd=self.cwd, state_dir=self.state)
            if not ok:
                raise RuntimeError("the pack does not install: " + "; ".join(lines))
            registry.invalidate()
            pack = find(self.folder.name, cwd=self.cwd, state_dir=self.state)
        ok, lines = G.enable(pack, grant=self.grants, grant_all=self.grants is None, state_dir=self.state,
                             confirm=lambda _lines: True)  # 3.4.1.2: the author's own pack in a scratch home
        if not ok:
            raise RuntimeError("the pack does not enable: " + "; ".join(lines))
        self.pack = pack
        from halo_harness.packs.studio_view_rules import routes_of
        self.prefix = str(routes_of(pack.manifest).get("prefix") or "")
        self.srv = start_server(port=0, cwd=self.cwd, state_dir=self.state)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.srv.server_address[1]}"
        self.token = self.srv.token
        from halo_harness.studio.owner_proof import raw_key  # 3.3.14.0 R1: what a page embeds carries the pack's key
        self.key = raw_key(self.token, pack.id)
        return self

    def __exit__(self, *exc) -> None:
        self.srv.shutdown()
        self.srv.server_close()
        from halo_harness.studio.packs_routes import unload
        unload(self.pack.id)

    def route(self, rest: str = "") -> str:
        return f"/api/packs/{self.pack.id}/{self.prefix}/{rest}".rstrip("/")

    def call(self, method: str, path: str, body=None, token=None):
        req = urllib.request.Request(self.base + path, method=method,
                                     data=json.dumps(body).encode() if body is not None else None)
        req.add_header("Authorization", "Bearer " + (self.token if token is None else token))
        from halo_harness.studio.owner_proof import HEADER, header_for  # 3.3.14.0 R1: a test calls as the owner's page
        req.add_header(HEADER, header_for(self.srv))
        if body is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            raw = e.read() or b"{}"
            try:
                return e.code, json.loads(raw)
            except ValueError:
                return e.code, {"error": raw.decode("utf-8", "replace")}

    def raw(self, path: str, token: bool = True):
        """A GET as an iframe or an image makes it: no header, the pack's key in `?k=` (`token=False`: none)."""
        url = self.base + path + ((("&" if "?" in path else "?") + "k=" + self.key) if token else "")
        try:
            with urllib.request.urlopen(url, timeout=15) as r:
                return r.status, dict(r.headers), r.read()
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), e.read()

    def module(self, rel: str):
        """The pack's module `rel` (server/store.py), imported through the pack's folder as Studio's routes import it."""
        from halo_harness.studio.packs_routes import load
        load(self.pack)
        return pack_module(self.pack.root, rel)

    def listen(self) -> Feed:
        return Feed(f"{self.base}/api/events?t={self.token}")
