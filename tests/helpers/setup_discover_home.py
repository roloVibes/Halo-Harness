"""tests.helpers.setup_discover_home -- the scratch home of
tests/test_setup_discover_api.py (Halo 3.3.0.0 R5): the Setup home
(tests/helpers/setup_home.py: its own env file, no background network, the
Models rows stubbed) plus two `MockUpstream`s on 127.0.0.1:0 with different
model lists, `ollama.discover.ports` naming their ports (the default port is
never asked), the live-feed frames collected instead of published, and the
discovery jobs and rows forgotten before and after."""

from __future__ import annotations

import time

from tests.helpers.mock_ollama import MockUpstream
from tests.helpers.setup_home import SetupHome

OTHER = {"models": [{"name": "llama3.2:3b", "model": "llama3.2:3b", "size": 2000, "digest": "sha256:feed1",
                     "details": {"family": "llama"}}]}


class DiscoverHome(SetupHome):
    """The Setup scratch home plus two mock Ollama servers named by `ollama.discover.ports`; frames collected."""

    def __enter__(self):
        super().__enter__()
        from halo_harness.providers.ollama_discover import reset_discover_cache
        from halo_harness.studio import setup_discover_api as A, setup_discover_jobs as J
        from halo_harness.theme import set_config_value
        J.forget()
        reset_discover_cache()
        self.a, self.b = MockUpstream().start(), MockUpstream(tags_response=OTHER).start()
        set_config_value("ollama.discover", {"ports": [self.a.port, self.b.port]})
        self.frames: list = []
        self._pub, A._publisher = A._publisher, (lambda req: self.frames.append)
        return self

    def __exit__(self, *exc):
        from halo_harness.studio import setup_discover_api as A, setup_discover_jobs as J
        A._publisher = self._pub
        for kind in ("scan", "measure"):
            J.stop(kind)
            wait_done(kind, 10)
        J.forget()
        self.a.stop()
        self.b.stop()
        return super().__exit__(*exc)

    def hosts(self) -> list:
        return (self.config().get("ollama") or {}).get("hosts") or []


def wait_done(kind: str, seconds: float = 15.0) -> bool:
    from halo_harness.studio import setup_discover_jobs as J
    deadline = time.monotonic() + seconds
    while J.alive(kind) and time.monotonic() < deadline:
        time.sleep(0.05)
    return not J.alive(kind)


def set_hosts(hosts: list) -> None:
    from halo_harness.theme import set_config_value
    set_config_value("ollama.hosts", hosts)
