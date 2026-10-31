"""tests.helpers.logs_rig -- Halo 3.3.6.0 R3: a scratch home for the server-log work (remote logs, the log status,
crash forensics, the fit evidence, the Logs routes). Never a real ssh (the fake remote, tests/helpers/fake_ssh_logs.py,
through server_log_remote.SEAMS), never a request to a server (BRIDGE_TEST_NO_BACKGROUND_NET=1, OLLAMA_HOST on a
refused port), never the real ~/.halo.

    with LogsHome(hosts=[...]) as h:
        h.state, h.root, h.local_log (this machine's server.log path under the home), h.remote("pc", platform)
        h.write_local(text|bytes), h.call(host, model, at, **fields) (a ledger line), h.cli(fn, *argv) -> (code, out)
    T(sec, minute=14) -> an ISO `time=` stamp near now; GIN(sec, status) a [GIN] line at that local time
"""

from __future__ import annotations

import contextlib
import datetime as dt
import io
import json
import os
import tempfile
import time
from pathlib import Path

_VARS = ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "OLLAMA_HOST", "BRIDGE_TEST_NO_BACKGROUND_NET", "LOCALAPPDATA")
BASE = time.time() - 120.0  # every fixture line is stamped in the last two minutes


def T(sec: float) -> str:
    return dt.datetime.fromtimestamp(BASE + sec).astimezone().isoformat(timespec="milliseconds")


def GIN(sec: float, status: int = 200, took: str = "7.0006466s") -> str:
    when = dt.datetime.fromtimestamp(BASE + sec)
    return f"[GIN] {when:%Y/%m/%d - %H:%M:%S} | {status} | {took} | 192.0.2.30 | POST \"/api/chat\""


def crash_log(model: str = "qwen3.8:27b", at: float = 0.0) -> str:
    """The 2026-10-29 shape (knowledge/server-log.md): flash attention + a q8_0 KV cache + a spill -> CUDA IMA ->
    the runner dies with 0xc0000409 -> a 500."""
    cmd = ("llama-server.exe --model C:\\\\Users\\\\example\\\\.ollama\\\\models\\\\blobs\\\\sha256-0000 --port 50060 -c 65536 "
           "-np 1 --cache-type-k q8_0 --cache-type-v q8_0 --flash-attn on")
    return "\n".join([
        f'time={T(at)} level=INFO source=routes.go:2439 msg="server config" env="map[OLLAMA_FLASH_ATTENTION:true '
        'OLLAMA_KV_CACHE_TYPE:q8_0 OLLAMA_NUM_PARALLEL:1]"',
        f'time={T(at + 0.1)} level=INFO source=routes.go:2501 msg="Listening on [::]:11434 (version 0.40.6)"',
        f'time={T(at + 1)} level=INFO source=llama_server.go:457 msg="starting llama-server" cmd="{cmd}"',
        "load_tensors: offloaded 59/66 layers to GPU",
        "llama_kv_cache:      CUDA0 KV buffer size =  1904.00 MiB",
        "llama_kv_cache:        CPU KV buffer size =   272.00 MiB",
        "sched_reserve: graph splits = 14",
        f'time={T(at + 20)} level=INFO source=llama_server.go:1403 msg="llama-server started in 19.20 seconds"',
        f'time={T(at + 20.1)} level=INFO source=images.go:422 msg="template selection" model=registry.ollama.ai/library/{model}',
        "CUDA error: an illegal memory access was encountered",
        f'time={T(at + 31)} level=ERROR source=server.go:1520 msg="llama runner terminated" error="exit status 0xc0000409"',
        GIN(at + 31, 500, "11.2s"), ""])


class LogsHome:
    def __init__(self, hosts=None) -> None:
        self.hosts = hosts if hosts is not None else [{"name": "box", "url": "http://127.0.0.1:9"}]

    def __enter__(self):
        global BASE
        BASE = time.time() - 120.0  # fresh per home: a long suite run never ages the fixture lines
        self._saved = {k: os.environ.get(k) for k in _VARS}
        self.root = Path(tempfile.mkdtemp(prefix="lg_logs-")).resolve()
        self.state = self.root / ".halo"
        self.state.mkdir(parents=True)
        os.environ.update(BRIDGE_TEST_HOME=str(self.root), BRIDGE_STATE_DIR=str(self.state),
                          OLLAMA_HOST="http://127.0.0.1:9", BRIDGE_TEST_NO_BACKGROUND_NET="1")
        os.environ.pop("LOCALAPPDATA", None)
        (self.state / "config.json").write_text(json.dumps({"ollama": {"hosts": self.hosts}}), encoding="utf-8")
        from halo_harness.ollama_steward import log_tail, server_log_remote
        from halo_harness.providers.ollama import reset_catalog_cache
        reset_catalog_cache()
        log_tail._LAST.clear()
        log_tail._RULES.clear()
        self._seams = dict(server_log_remote.SEAMS)
        self.remotes: dict = {}
        server_log_remote.SEAMS["ssh"] = lambda host: self.remotes[host.name].runner
        from halo_harness.ollama_steward.hardware_readers import server_log_path
        self.local_log = server_log_path()
        return self

    def remote(self, name: str, platform: str = "posix", journal=None):
        from tests.helpers.fake_ssh_logs import FakeRemote
        self.remotes[name] = FakeRemote(self.root / "remote" / name, platform, journal)
        return self.remotes[name]

    def write_local(self, text, append: bool = False) -> Path:
        self.local_log.parent.mkdir(parents=True, exist_ok=True)
        data = text.encode("utf-8") if isinstance(text, str) else text
        with open(self.local_log, "ab" if append else "wb") as f:
            f.write(data)
        return self.local_log

    def call(self, host: dict, model: str, at: float, **fields) -> None:
        from halo_harness.ollama_steward.ledger import blank_line, now_iso, record_call
        record_call(self.state, blank_line(host=host, model=model, at=now_iso(at), status=200, **fields))

    def events(self, *evs, host: str = "box") -> list:
        from halo_harness.ollama_steward.server_events import record_events
        return record_events(self.state, list(evs), host=host)

    @staticmethod
    def cli(fn, *argv) -> "tuple[int, str]":
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = fn(list(argv))
        return code, out.getvalue()

    def __exit__(self, *exc):
        from halo_harness.ollama_steward import server_log_remote
        server_log_remote.SEAMS.clear()
        server_log_remote.SEAMS.update(self._seams)
        from halo_harness.providers.ollama import reset_catalog_cache
        reset_catalog_cache()
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
