"""tests.test_setup_state_no_probe -- a read of Setup's state opens no
connection (Halo 3.3.0.0 R3, deliverable 4b). R1's Default model rows
(studio/model.py model_rows -> build_local_view) asked every configured
Ollama host on each `GET setup/state`; the state's rows now come from what
is cached (`model_rows(cached=True)`, providers/local_models_cached.py), and
the guided first run's card and the check costs read the cached catalog too
(team_preview.catalog_by_ref). The hosts here are documentation addresses
(192.0.2.x); every connection attempt is refused and recorded.
Run: python -m tests.test_setup_state_no_probe
"""

from __future__ import annotations

import os
import socket
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.setup_home import SetupHome  # noqa: E402

test, TESTS = new_registry()
HOST = {"name": "lan", "url": "http://192.0.2.1:11434", "default": True}


class _NoNet(SetupHome):
    """The scratch home with the real Models rows (the helper stubs them), no connection possible, and every
    attempt, `fetch_tags` and `probe_version` call recorded."""

    def __enter__(self):
        super().__enter__()
        from halo_harness.providers import ollama
        from halo_harness.studio import model as M
        M.model_rows = self._rows_fn
        self.opened: list = []

        def refuse(*a, **_k):
            self.opened.append(repr(a[:1])[:80])
            raise OSError("no connection in this test")

        def record(name):
            return lambda *a, **_k: self.opened.append(name) or None
        self._net = (socket.create_connection, urllib.request.urlopen, ollama.fetch_tags, ollama.probe_version)
        socket.create_connection, urllib.request.urlopen = refuse, refuse
        ollama.fetch_tags, ollama.probe_version = record("fetch_tags"), record("probe_version")
        ollama.reset_catalog_cache()
        from halo_harness.theme import set_config_value
        set_config_value("ollama.hosts", [dict(HOST)])
        return self

    def __exit__(self, *exc):
        from halo_harness.providers import ollama
        socket.create_connection, urllib.request.urlopen, ollama.fetch_tags, ollama.probe_version = self._net
        ollama.reset_catalog_cache()
        return super().__exit__(*exc)


@test
def test_a_state_read_with_a_host_and_the_flag_opens_nothing(ctx: Ctx):
    with _NoNet() as e:
        t = time.monotonic()
        status, s = e.call("GET", "setup/state")
        took = time.monotonic() - t
        ctx.check(f"200 in under a second, got {status} in {took:.2f}s", status == 200 and took < 1.0)
        ctx.check(f"no connection attempted, no tags read, got {e.opened}", e.opened == [])
        ctx.check(f"the host nothing read yet says so, got {s['model_notes']}", s["model_notes"] == ["Ollama (lan): not read yet: Refresh"])
        ctx.check("no Ollama row is made up for it", not any(r["ref"].startswith("ol:") for r in s["models"]))


@test
def test_without_the_flag_a_state_read_still_never_calls_fetch_tags(ctx: Ctx):
    """The flag off (as in a real Studio): the rows, the card and the costs still read the cache only. The Local
    models block's detection lines (R2) are the one live read, kept a minute; stubbed here."""
    from halo_harness.studio import setup_providers_state as P
    with _NoNet() as e:
        saved, P.detection = P.detection, (lambda wait=4.0: ["(detection stubbed)"])
        os.environ.pop("BRIDGE_TEST_NO_BACKGROUND_NET", None)
        try:
            status, s = e.call("GET", "setup/state")
            _status, start = e.call("GET", "start")
        finally:
            os.environ["BRIDGE_TEST_NO_BACKGROUND_NET"] = "1"
            P.detection = saved
        ctx.check(f"200, nothing opened, no fetch_tags, got {status} {e.opened}", status == 200 and e.opened == [])
        ctx.check("GET start's card read the cache too", start["card"][0] == "The guided first run (halo start)")


@test
def test_a_host_a_refresh_read_shows_its_cached_models(ctx: Ctx):
    with _NoNet() as e:
        from halo_harness.providers import ollama
        host = ollama.resolve_ollama_hosts()[0]
        catalog = {"models": [{"name": "tiny:1b", "model": "tiny:1b", "size": 1000, "details": {"quantization_level": "Q4_K_M"},
                               "capabilities": ["completion", "tools"]}]}
        with ollama._CATALOG_LOCK:
            ollama._CATALOG_CACHE[host.url] = (time.monotonic() - 3600, catalog)  # read an hour ago: still what is shown
        status, s = e.call("GET", "setup/state")
        refs = [r["ref"] for r in s["models"]]
        ctx.check(f"the cached model is a row, got {refs}", status == 200 and "ol:tiny:1b" in refs)
        ctx.check(f"no note for a host that was read, nothing opened, got {s['model_notes']} {e.opened}", s["model_notes"] == [] and e.opened == [])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
