"""tests.test_no_local_reads -- Halo 3.3.5.0 R3: the test rigs never read this machine's Ollama. A listener on
127.0.0.1:0 poses as the default host (`OLLAMA_HOST` = it, `ollama.hosts` empty: the host Halo makes up); under
BRIDGE_TEST_NO_BACKGROUND_NET=1 the server path of the two Roles Chrome tests (`GET models`, the Roles model list),
Setup's state read (`GET setup/state`), `halo local`'s view and the catalog refresh (`build_local_view`, refresh too),
Local's Hosts, Models and Library pages (3.3.6.0 R2: the search and Download and verify too), every control route (3.3.6.0 R1: the probe too) and (3.3.5.0 R5) Local -> Hugging Face's routes must send
it nothing (a download under the flag reads no hub); without the flag the same
model list does read it (so the listener is reachable and the pin means something). The rigs' environment pins
`OLLAMA_HOST` to a refused port when it is unset or names a real address (tests/helpers/chrome_driver.driver_env,
tests/run_all.py).
Run: python -m tests.test_no_local_reads
"""
from __future__ import annotations

import json
import os
import socket
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
_VARS = ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "OLLAMA_HOST", "OLLAMA_API_KEY", "BRIDGE_TEST_NO_BACKGROUND_NET",
         "HF_LOCAL_PROBE_PORTS", "HF_ENDPOINT")


class Listener:
    """Accepts every connection, records the first line, answers an empty /api/tags."""

    def __init__(self):
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(16)
        self.port = self.sock.getsockname()[1]
        self.seen: list = []
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        while True:
            try:
                conn, _a = self.sock.accept()
            except OSError:
                return
            try:
                conn.settimeout(2)
                self.seen.append(conn.recv(4096).split(b"\r\n", 1)[0].decode("latin-1"))
                body = b'{"models": []}'
                conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: %d\r\n"
                             b"Connection: close\r\n\r\n%s" % (len(body), body))
            except OSError:
                pass
            finally:
                conn.close()

    def close(self):
        self.sock.close()


class Home:
    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in _VARS}
        self.root = Path(tempfile.mkdtemp(prefix="l3_noreads-")).resolve()
        self.state = self.root / ".halo"
        self.state.mkdir(parents=True)
        (self.state / "config.json").write_text(json.dumps({"model": "ol:qwen3:30b"}), encoding="utf-8")
        self.listener = Listener()
        os.environ.pop("BRIDGE_STATE_DIR", None)
        os.environ.pop("HF_ENDPOINT", None)
        os.environ.update(BRIDGE_TEST_HOME=str(self.root), OLLAMA_HOST=f"http://127.0.0.1:{self.listener.port}",
                          BRIDGE_TEST_NO_BACKGROUND_NET="1", HF_LOCAL_PROBE_PORTS="9")
        from halo_harness.providers.ollama import reset_catalog_cache
        from halo_harness.studio import local_catalog, ollama_hosts_view
        reset_catalog_cache()
        local_catalog.reset()
        ollama_hosts_view.reset_cache()
        return self

    def api(self, method: str, path: str, body=None, query=None):
        from halo_harness.studio.api import Request, dispatch
        return dispatch(Request(method=method, path=path, query=query or {}, body=body or {}, cwd=self.root,
                                state_dir=self.state, server=None))

    def __exit__(self, *exc):
        self.listener.close()
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


@test
def test_the_roles_model_list_and_setup_never_read_the_default_host(ctx: Ctx):
    with Home() as h:
        from halo_harness.providers.ollama import resolve_ollama_host
        ctx.check("the default host is the made-up one on the listener",
                  resolve_ollama_host(None).synthesized and str(h.listener.port) in resolve_ollama_host(None).url)
        status, _rows = h.api("GET", "models")
        ctx.check(f"GET models (the Roles model list) answered, got {status}", status == 200)
        status, _s = h.api("GET", "setup/state")
        ctx.check(f"GET setup/state answered, got {status}", status == 200)
        ctx.check(f"the listener received nothing, got {h.listener.seen}", h.listener.seen == [])


@test
def test_the_local_view_the_refresh_and_the_local_pages_never_read_it(ctx: Ctx):
    with Home() as h:
        from halo_harness.providers.local_models import build_local_view
        from halo_harness.providers.model_enumeration import _local_probe
        build_local_view(state_dir=h.state)
        build_local_view(refresh=True, state_dir=h.state)
        _local_probe(h.state, dict(os.environ))  # the catalog refresh's local job (/model's refresh)
        for path in ("local/hosts", "local/models", "local/pulls", "local/host/default/loaded", "local/probes",
                     "local/profiles"):  # 3.3.6.0 R1: the battery's reads
            h.api("GET", path)
        h.api("GET", "local/library", query={"q": "qwen3", "source": "ollama"})
        # 3.3.6.0 R2: the search, its presets and crashes, Download and verify under the flag
        h.api("GET", "local/library", query={"q": "qwen3", "source": "ollama", "preset": "coder", "exclude_crashed": "1"})
        for path in ("local/library/presets", "local/library/verifies", "local/crashes"):
            h.api("GET", path)
        h.api("POST", "local/library/verify", {"host": "default", "name": "qwen3:30b", "role": "verify"})
        h.api("GET", "local/host/default/show", query={"model": "qwen3:30b"})
        for act, body in (("load", {"model": "qwen3:30b"}), ("unload", {"model": "qwen3:30b"}), ("pull", {"name": "qwen3:30b"}), ("delete", {"name": "qwen3:30b", "force": True}),
                          ("copy", {"src": "a", "dst": "b"}), ("twin", {"name": "qwen3:30b", "window": 8192}),
                          ("probe", {"model": "qwen3:30b"})):  # 3.3.6.0 R1: the battery under the flag sends nothing
            h.api("POST", f"local/host/default/{act}", body)
        # 3.3.5.0 R5: Local -> Hugging Face's routes (the hub is HF_ENDPOINT or huggingface.co: blocked under the flag)
        for path in ("local/hf/dirs", "local/downloads", "local/servers", "local/server/llama-1/status"):
            h.api("GET", path)
        h.api("GET", "local/hf/uses", query={"path": str(h.root / "x.gguf")})
        models = h.root / "models"
        models.mkdir()
        h.api("POST", "local/hf/dirs", {"path": str(models)})
        code, dl = h.api("POST", "local/hf/download", {"repo": "example-org/Tiny-1B-GGUF", "accept": True})
        ctx.check(f"a download under the flag reads no hub, got {code} {dl.get('error')}", code == 502 and "test flag" in dl["error"])
        for path, body in (("local/hf/serve", {"path": str(models / "x.gguf")}), ("local/hf/delete", {"path": str(models / "x.gguf")}),
                           ("local/server/llama-1/stop", {})):
            h.api("POST", path, body)
        import time
        time.sleep(0.3)  # a pull job's thread, had it started one
        ctx.check(f"the listener received nothing, got {h.listener.seen}", h.listener.seen == [])


@test
def test_without_the_flag_the_same_list_reads_it(ctx: Ctx):
    with Home() as h:
        os.environ.pop("BRIDGE_TEST_NO_BACKGROUND_NET")
        from halo_harness.providers.local_models import build_local_view
        build_local_view(state_dir=h.state)
        ctx.check(f"the listener is reachable: /api/tags read without the flag, got {h.listener.seen}",
                  any("/api/tags" in s for s in h.listener.seen))


@test
def test_the_rigs_pin_ollama_host_to_a_refused_port(ctx: Ctx):
    from tests.helpers.chrome_driver import driver_env, pinned_ollama_host
    saved = os.environ.get("OLLAMA_HOST")
    try:
        for value, want in ((None, "http://127.0.0.1:9"), ("0.0.0.0:11434", "http://127.0.0.1:9"),
                            ("http://127.0.0.1:11434", "http://127.0.0.1:9"), ("http://192.0.2.10:11434", "http://127.0.0.1:9"),
                            ("http://127.0.0.1:9", "http://127.0.0.1:9"), ("http://127.0.0.1:45123", "http://127.0.0.1:45123")):
            ctx.check(f"{value!r} -> {want}, got {pinned_ollama_host(value)}", pinned_ollama_host(value) == want)
        os.environ.pop("OLLAMA_HOST", None)
        ctx.check("driver_env pins it", driver_env()["OLLAMA_HOST"] == "http://127.0.0.1:9")
        src = (Path(__file__).resolve().parent / "run_all.py").read_text(encoding="utf-8")
        ctx.check("run_all pins it for the whole run", "pinned_ollama_host" in src)
    finally:
        if saved is None:
            os.environ.pop("OLLAMA_HOST", None)
        else:
            os.environ["OLLAMA_HOST"] = saved


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
