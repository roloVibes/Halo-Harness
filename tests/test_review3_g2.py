"""tests.test_review3_g2 -- pins for the 3.0.2.0 review fix pass, round G2
(local catalog), first half:

  * item 59  the fit store and capability cache no longer share one tmp name
             and their read-modify-write is locked across processes
  * item 60  ensure_mlx_server probes a registry hit before reusing it
  * item 61  a crafted .gguf header degrades to (None, None), never raises
  * item 62  a malformed Ollama host URL makes every probe return None
The other items of the round live in test_review3_g2b.py / test_review3_g2c.py.
"""
from __future__ import annotations

import contextlib
import os
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

ensure_scoped_state_dir_once()
test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
_ENV_PREFIXES = ("OPENROUTER_", "DATABRICKS_", "ANTHROPIC_", "BRIDGE_", "HALO_", "ROLO_CLAUDE_", "TYPESAFE_",
                 "OPENAI_", "OLLAMA_")


@contextlib.contextmanager
def env_patch(**kv):
    """Set/clear variables for one test; EVERY provider-prefixed variable is
    snapshotted and restored afterwards."""
    saved = {k: v for k, v in os.environ.items() if k.startswith(_ENV_PREFIXES)}
    for k, v in kv.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    try:
        yield
    finally:
        for k in [k for k in os.environ if k.startswith(_ENV_PREFIXES)]:
            os.environ.pop(k, None)
        os.environ.update(saved)


def _tmp(prefix: str) -> Path:
    return Path(tempfile.mkdtemp(prefix=prefix))


# ---- item 59: unique tmp names + a cross-process lock ----------------------

@test
def test_g2_59_stores_write_through_a_unique_tmp_name(ctx: Ctx):
    from halo_harness.providers import ollama_calibrate, ollama_capability
    seen = []
    real = os.replace

    def spy(src, dst):
        seen.append(Path(src).name)
        return real(src, dst)

    sd = _tmp("g2-59-")
    os.replace = spy
    try:
        ollama_calibrate.save_fit_store(sd, {"entries": [], "last_turns": {}})
        ollama_capability.save_capability_cache(sd, {"d": {"tool_calls": True}})
    finally:
        os.replace = real
    ctx.check(f"two replaces seen, got {seen}", len(seen) == 2)
    ctx.check(f"neither uses the shared fixed name, got {seen}",
              all(n not in ("ollama-fit.json.tmp", "ollama-capabilities.json.tmp") for n in seen))
    ctx.check(f"each carries this pid, got {seen}", all(str(os.getpid()) in n for n in seen))
    ctx.check("both files read back", ollama_calibrate.load_fit_store(sd)["entries"] == []
              and ollama_capability.load_capability_cache(sd) == {"d": {"tool_calls": True}})


_WRITER = (
    "import sys\n"
    "from halo_harness.providers.ollama_calibrate import record_last_turn_throughput\n"
    "sd, tag, n = sys.argv[1], sys.argv[2], int(sys.argv[3])\n"
    "for i in range(n):\n"
    "    record_last_turn_throughput(sd, host_url='http://h', model=tag + str(i), tokens_per_second=1.0,\n"
    "                                prefill_seconds=0.1, offloaded=False)\n"
)


@test
def test_g2_59_concurrent_processes_keep_the_seeded_cap_and_every_write(ctx: Ctx):
    from halo_harness.providers.ollama_calibrate import load_fit_store, lookup_learned_cap, record_calibration
    sd = _tmp("g2-59b-")
    record_calibration(sd, host_url="http://h", model="qwen3:30b", digest="d", max_full_gpu_ctx=16384,
                       ollama_version="0.9")
    env = {k: v for k, v in os.environ.items() if not k.startswith(_ENV_PREFIXES)}
    env["PYTHONPATH"] = str(REPO)
    env["BRIDGE_TEST_HOME"] = str(sd)
    procs = [subprocess.Popen([sys.executable, "-c", _WRITER, str(sd), tag, "25"], env=env, cwd=str(REPO),
                              stdout=subprocess.DEVNULL, stderr=subprocess.PIPE) for tag in ("a", "b", "c")]
    errs = [p.communicate(timeout=120)[1] for p in procs]
    ctx.check("all writers exited cleanly", all(p.returncode == 0 for p in procs))
    store = load_fit_store(sd)
    ctx.check(f"every one of the 75 interleaved writes survived, got {len(store['last_turns'])}",
              len(store["last_turns"]) == 75)
    cap = lookup_learned_cap(sd, host_url="http://h", model="qwen3:30b", digest="d", ollama_version="0.9")
    ctx.check(f"the seeded learned cap survived, got {cap!r} {errs!r}", cap == 16384)


# ---- item 60: a dead registry row is never handed out ----------------------

_MLX_STUB = (
    "import json, sys\n"
    "from http.server import BaseHTTPRequestHandler, HTTPServer\n"
    "port = int(sys.argv[sys.argv.index('--port') + 1])\n"
    "mid = sys.argv[sys.argv.index('--model') + 1]\n"
    "class H(BaseHTTPRequestHandler):\n"
    "    def log_message(self, *a): pass\n"
    "    def do_GET(self):\n"
    "        body = json.dumps({'object': 'list', 'data': [{'id': mid}]}).encode()\n"
    "        self.send_response(200)\n"
    "        self.send_header('Content-Length', str(len(body)))\n"
    "        self.end_headers()\n"
    "        self.wfile.write(body)\n"
    "HTTPServer(('127.0.0.1', port), H).serve_forever()\n"
)
_REPO_ID = "mlx-community/Qwen2.5-7B-Instruct-4bit"


def _ensure(sd, stub):
    from halo_harness.providers.huggingface_mlx import ensure_mlx_server
    return ensure_mlx_server(_REPO_ID, state_dir=sd, platform_name="darwin", machine="arm64",
                             binary_argv=[sys.executable, str(stub)], env={})


@test
def test_g2_60_stale_registry_row_is_dropped_and_a_fresh_server_started(ctx: Ctx):
    from halo_harness.providers.local_runtime import find_free_port, load_registry, save_registry, stop_managed_server
    sd = _tmp("g2-60-")
    stub = sd / "stub.py"
    stub.write_text(_MLX_STUB, encoding="utf-8")
    dead = f"http://127.0.0.1:{find_free_port()}/v1"
    save_registry(sd, [{"model": _REPO_ID, "runtime": "mlx_lm", "pid": 999999, "port": 1, "base_url": dead,
                        "started": "x", "keep": True}])
    server, lines = _ensure(sd, stub)
    try:
        ctx.check(f"a server was returned, got {lines}", server is not None)
        ctx.check(f"it is not the dead port, got {server and server.base_url}", server.base_url != dead)
        ctx.check(f"nothing said 'Reusing', got {lines}", not any("Reusing" in ln for ln in lines))
        rows = load_registry(sd)
        ctx.check(f"registry holds only the fresh row, got {rows}",
                  len(rows) == 1 and rows[0]["base_url"] == server.base_url)
    finally:
        stop_managed_server(_REPO_ID, state_dir=sd)


@test
def test_g2_60_live_registry_row_is_still_reused(ctx: Ctx):
    from halo_harness.providers.local_runtime import stop_managed_server
    sd = _tmp("g2-60b-")
    stub = sd / "stub.py"
    stub.write_text(_MLX_STUB, encoding="utf-8")
    first, _ = _ensure(sd, stub)
    try:
        second, lines = _ensure(sd, stub)
        ctx.check(f"the second call reuses the first server, got {lines}",
                  first is not None and second is not None and second.base_url == first.base_url
                  and any("Reusing" in ln for ln in lines))
    finally:
        stop_managed_server(_REPO_ID, state_dir=sd)


# ---- item 61: crafted GGUF files -------------------------------------------

def _gguf(kv_tail: bytes) -> bytes:
    key = b"general.architecture"
    return (b"GGUF" + struct.pack("<IQQ", 3, 0, 1) + struct.pack("<Q", len(key)) + key + kv_tail)


@test
def test_g2_61_crafted_headers_return_none_not_an_exception(ctx: Ctx):
    from halo_harness.providers.gguf_header import GGUFParseError, gguf_model_info_for_file, parse_gguf_header
    from halo_harness.providers.local_fit import read_fit_inputs_for_path
    arr, string = 9, 8
    deep = struct.pack("<I", arr) + struct.pack("<IQ", arr, 1) + struct.pack("<IQ", arr, 1) * 5000
    cases = {
        "deeply nested arrays": _gguf(deep),
        "string length near 2**64": _gguf(struct.pack("<IIQQ", arr, string, 1, 2 ** 64 - 1)),
        "scalar array count near 2**63": _gguf(struct.pack("<IIQ", arr, 5, 2 ** 63)),
    }
    d = _tmp("g2-61-")
    for label, blob in cases.items():
        p = d / (f"case{len(list(d.iterdir()))}.gguf")
        p.write_bytes(blob)
        try:
            parse_gguf_header(p)
            kind = "parsed"
        except GGUFParseError:
            kind = "GGUFParseError"
        except Exception as e:  # noqa: BLE001
            kind = type(e).__name__
        ctx.check(f"{label}: the strict parser raises GGUFParseError, got {kind}", kind == "GGUFParseError")
        ctx.check(f"{label}: gguf_model_info_for_file gives (None, None)", gguf_model_info_for_file(p) == (None, None))
        info, quant, weight = read_fit_inputs_for_path(p, fmt="gguf")
        ctx.check(f"{label}: the fit-input read degrades, got {(info, quant, weight)}",
                  info == {} and quant is None and weight == len(blob))


# ---- item 62: malformed host URLs ------------------------------------------

@test
def test_g2_62_malformed_host_url_probes_return_none(ctx: Ctx):
    from halo_harness.providers.ollama import OllamaHost, fetch_ps, fetch_tags, probe_version
    from halo_harness.providers.ollama_hw import is_local_host, is_ollama_cloud_host
    for url in ("http://localhost:port", "http://gpu-box:11434x", "http://[::1"):
        host = OllamaHost(name="bad", url=url)
        ctx.check(f"{url}: probe_version is None", probe_version(host) is None)
        ctx.check(f"{url}: fetch_tags/fetch_ps are None", fetch_tags(host) is None and fetch_ps(host) is None)
        ctx.check(f"{url}: host classifiers do not raise",
                  is_local_host(host) in (True, False) and is_ollama_cloud_host(host) in (True, False))


@test
def test_g2_62_doctor_and_local_view_survive_ollama_host_env(ctx: Ctx):
    from halo_harness.doctor import _check_ollama_hosts
    from halo_harness.providers.huggingface_local_probe import probe_models_endpoint
    from halo_harness.providers.local_models import build_local_view
    with env_patch(OLLAMA_HOST="localhost:port", BRIDGE_TEST_NO_BACKGROUND_NET="1"):
        lines = _check_ollama_hosts()
        ctx.check(f"doctor returned a line for the host, got {lines}", bool(lines) and "Ollama" in lines[0][1])
        rows = build_local_view(state_dir=_tmp("g2-62-"))
        ctx.check("build_local_view returned a list", isinstance(rows, list))
    ctx.check("a malformed manual local-server url probes to None",
              probe_models_endpoint("http://localhost:port/v1") is None)


@test
def test_g2_62_config_entry_with_unusable_url_is_skipped(ctx: Ctx):
    from halo_harness.providers.ollama import _host_from_dict
    ctx.check("a bad-port entry is skipped", _host_from_dict({"name": "x", "url": "http://h:99x"}) is None)
    ok = _host_from_dict({"name": "y", "url": "gpu-box:11434"})
    ctx.check(f"a good entry still resolves, got {ok}", ok is not None and ok.url == "http://gpu-box:11434")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
