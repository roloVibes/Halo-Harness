"""tests.helpers.copilot_rig -- a scratch home with Copilot set up against the mock (Halo 3.3.17.0).

    with CopilotRig() as r:          # BRIDGE_TEST_HOME = a fresh temp dir, copilot.tenant / client_id set,
        r.signin()                   # the mock's seams in the environment, the browser = a urllib follower
        r.mock.scenario["workiq"] = "401"

Every variable it touches (BRIDGE_TEST_HOME, BRIDGE_STATE_DIR, HALO_*) is put back on exit; the token cache is
cleared on the way in and out; `copilot_auth.OPEN_BROWSER` is a stub that follows the authorize redirect to the
loopback (never a real browser) and `HALO_NO_BROWSER=1` stays set so nothing could open one.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import urllib.request
from pathlib import Path

from tests.helpers.mock_copilot import CLIENT_ID, TENANT, MockCopilot

_PREFIXES = ("HALO_", "BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")


def follow(url: str) -> bool:
    """The browser: GET the authorize URL and follow its redirect to the loopback."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(url, timeout=10) as resp:
        resp.read()
    return True


class CopilotRig:
    def __init__(self, *, configured: bool = True, api: str = "workiq", extra: dict = None):
        self.configured, self.api, self.extra = configured, api, extra or {}
        self.opened: list = []

    def __enter__(self):
        self._saved = {k: v for k, v in os.environ.items() if k.startswith(_PREFIXES)}
        for k in list(self._saved):
            os.environ.pop(k, None)
        self.home = Path(tempfile.mkdtemp(prefix="halo-copilot-"))
        os.environ["BRIDGE_TEST_HOME"] = str(self.home)
        os.environ["HALO_NO_BROWSER"] = "1"
        os.environ.setdefault("BRIDGE_TEST_NO_BACKGROUND_NET", "1")
        self.mock = MockCopilot().__enter__()
        os.environ.update(self.mock.env())
        if self.configured:
            self.config({"tenant": TENANT, "client_id": CLIENT_ID, "api": self.api, "timezone": "Europe/London",
                         **self.extra})
        from halo_harness.providers import copilot_auth, copilot_tokens
        copilot_tokens.forget_access()
        self._open, self._sleep = copilot_auth.OPEN_BROWSER, copilot_auth.SLEEP
        copilot_auth.OPEN_BROWSER = self._browser
        copilot_auth.SLEEP = lambda s: None
        from halo_harness.providers import copilot as adapter
        self._asleep = adapter.SLEEP
        self.waits: list = []
        adapter.SLEEP = self.waits.append
        return self

    def _browser(self, url: str) -> bool:
        self.opened.append(url)
        return follow(url)

    def config(self, values: dict) -> None:
        path = self.home / ".halo" / "config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        data.setdefault("copilot", {}).update(values)
        path.write_text(json.dumps(data), encoding="utf-8")

    def signin(self, **kw) -> dict:
        from halo_harness.providers.copilot_auth import signin
        from halo_harness.providers.copilot_config import load
        return signin(load(), say=lambda line: None, **kw)

    def env_file(self) -> Path:
        from halo_harness.config.paths import env_file_path
        return env_file_path()

    def every_file_text(self) -> str:
        """Every file under the home but the env file, joined (to look for a token that must not be there)."""
        env = self.env_file().resolve()
        out = []
        for p in self.home.rglob("*"):
            if p.is_file() and p.resolve() != env:
                try:
                    out.append(p.read_text(encoding="utf-8", errors="replace"))
                except OSError:
                    pass
        return "\n".join(out)

    def __exit__(self, *exc):
        from halo_harness.providers import copilot as adapter
        from halo_harness.providers import copilot_auth, copilot_tokens
        copilot_auth.OPEN_BROWSER, copilot_auth.SLEEP, adapter.SLEEP = self._open, self._sleep, self._asleep
        copilot_tokens.forget_access()
        self.mock.__exit__(*exc)
        for k in [k for k in os.environ if k.startswith(_PREFIXES)]:
            os.environ.pop(k, None)
        os.environ.update(self._saved)
        shutil.rmtree(self.home, ignore_errors=True)
        return False
