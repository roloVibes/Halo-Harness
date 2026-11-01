"""tests.test_pool_launch -- Halo 3.3.8.0 R3 deliverable 5: the launch (local_pool/launch.py, local_pool/entry.py,
local_pool/spawn.py; `halo local serve --pool`), over tests/helpers/pool_run_rig.RunRig: the controller's llama-server
is tests/helpers/fake_llama_server.py on 127.0.0.1, the worker's rpc-server the FakeRpc stand-in; no model loads:

1. the argv for the 24/24/11 fixture pool and Qwen3-Next (three workers): --rpc in member order, the fit's split,
   -ngl 999, the LAN address, the api key, -c 32768 at F16; past the F16 window (19/19/19) the Q8_0 KV flags;
2. Warm: the claims, pc's rpc-server on, llama-server up, the `pool` entry (max_ctx, api_key_env, log, runtime,
   members); the key in the env file and the environment only -- never in config.json, the log or run.json; Stop:
   the process stopped, the entry gone, the claims released, the pivoted-out model back as a stated line, the
   rpc-server off; `halo local serve --pool --keep` and the foreground hold;
3. refusals, one line each and nothing left behind: a node out of memory (the node and its share, no CPU fallback),
   an rpc-server on another build (both versions), the GGUF not here (the Download line).
Run: python -m tests.test_pool_launch
"""
from __future__ import annotations

import io
import json
import os
import sys
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.pool_rig import rows  # noqa: E402
from tests.helpers.pool_run_rig import QWEN, RunRig  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
BUNDLE = f"pool:{QWEN}"


def _pf(free: tuple, window=None) -> dict:
    from halo_harness.local_pool.catalog import get
    from halo_harness.local_pool.fit import fit
    from halo_harness.local_pool.preflight import _window
    v = fit(get(QWEN), rows(*free))
    ctx_, q8, _line = _window(v, window)
    return {"model": QWEN, "rpc": [{"member": f"worker{i + 1}", "addr": f"192.0.2.{11 + i}:50052"} for i in range(len(free))],
            "split": v["split"], "q8": q8, "ctx": ctx_, "fit": v}


@test
def test_the_argv_for_the_fixture_pools(ctx: Ctx):
    from halo_harness.local_pool.launch import argv, redact
    pf = _pf((24, 24, 11))
    got = argv(["llama-server"], pf, gguf="/models/Qwen3-Next-80B-A3B-Instruct-Q4_K_M.gguf", port=8090,
               key_file="/state/pool/api-key", addr_="192.0.2.5")
    want = ["llama-server", "-m", "/models/Qwen3-Next-80B-A3B-Instruct-Q4_K_M.gguf", "--alias", QWEN, "--rpc",
            "192.0.2.11:50052,192.0.2.12:50052,192.0.2.13:50052", "--tensor-split", "0.42,0.42,0.16", "-ngl",
            "999", "--host", "192.0.2.5", "--port", "8090", "--api-key-file", "/state/pool/api-key", "-c", "32768"]
    ctx.check(f"24/24/11: the exact argv, the key as a file (3.3.8.0 R4), got {got}", got == want)
    shown = redact(argv(["llama-server"], pf, gguf="/m.gguf", port=8090, key="KEY", addr_="192.0.2.5"))
    ctx.check(f"the --api-key fallback: *** in every logged copy, got {shown[-4:]}",
              shown[shown.index("--api-key") + 1] == "***" and "KEY" not in shown)
    pf = _pf((19, 19, 19), window=32768)
    got = argv(["llama-server"], pf, gguf="/m.gguf", port=8091, key_file="/k", addr_="192.0.2.5")
    ctx.check(f"19/19/19 at 32768: past the F16 window ({pf['fit']['max_ctx_f16']}), Q8_0 KV, got {got[-8:]}",
              pf["fit"]["max_ctx_f16"] == 20480 and pf["q8"] is True and got[-8:] == [
                  "--cache-type-k", "q8_0", "--cache-type-v", "q8_0", "--flash-attn", "on", "-c", "32768"]
              and "--tensor-split" in got and got[got.index("--tensor-split") + 1] == "0.3333,0.3333,0.3334")


@test
def test_warm_writes_the_entry_and_stop_takes_it_back(ctx: Ctx):
    from halo_harness.local_pool import entry, launch
    from halo_harness.ollama_steward import changes_pool
    with RunRig() as rig:
        got = changes_pool.warm(QWEN, state_dir=rig.peer, by="test")
        e = entry.current() or {}
        r = launch.run(rig.peer)
        ctx.check(f"warmed, got {got['ok']} {got['lines']}", got["ok"] and got.get("ready") is True)
        ctx.check(f"the pool entry, got {e}", e.get("name") == "pool" and e.get("url") == f"http://127.0.0.1:{r['port']}/v1"
                  and e.get("max_ctx") == 32768 and e.get("api_key_env") == entry.KEY_ENV and e.get("runtime") ==
                  "llama-server" and e.get("log") == r["log"] and e.get("members") == ["pc", "me"] and "api_key" not in e)
        key = os.environ.get(entry.KEY_ENV) or ""
        cfg = (rig.peer / "config.json").read_text(encoding="utf-8")
        log = Path(r["log"]).read_text(encoding="utf-8")
        run_json = (rig.peer / "pool" / "run.json").read_text(encoding="utf-8")
        from halo_harness.init_cli import _env_file_path
        ctx.check(f"the key: in the env file only, got {len(key)} chars", len(key) >= 24 and key not in cfg
                  and key not in log and key not in run_json and f"{entry.KEY_ENV}={key}" in
                  _env_file_path().read_text(encoding="utf-8") and "--api-key ***" not in log)
        kf = launch.key_path(rig.peer)
        ctx.check(f"3.3.8.0 R4: the key as --api-key-file <state>/pool/api-key (private), the argv shows the path only, "
                  f"the fake read it, got {r['argv'][r['argv'].index('--port'):][:6]}",
                  f"--api-key-file {kf}" in log and "--api-key" not in [x for x in r["argv"] if x != "--api-key-file"]
                  and kf.read_text(encoding="utf-8").strip() == key and r.get("key_file") is True
                  and f"api key read from a file ({len(key)} characters" in log
                  and (os.name == "nt" or (kf.stat().st_mode & 0o777) == 0o600))
        ctx.check(f"pc's rpc-server was started, the argv carries it, got {r['argv'][:12]}", len(rig.fake.argvs) == 1
                  and f"127.0.0.1:{rig.rpc_port}" in r["argv"] and r["argv"][r["argv"].index("--host") + 1] == "127.0.0.1")
        from halo_harness.providers.huggingface import resolve_huggingface_local_server
        s = resolve_huggingface_local_server("pool")
        ctx.check(f"hf:local/...@pool resolves with the key, got {s and s.url}", s is not None and s.api_key == key
                  and s.max_ctx == 32768)
        done = changes_pool.stop(state_dir=rig.peer, by="test")
        lines = done["lines"]
        ctx.check(f"stop: stopped, the entry gone, released, the pivot back, rpc off, got {lines}",
                  lines[0].startswith("stopped the pool's llama-server") and entry.current() is None
                  and any(ln.startswith("released pool:") for ln in lines) and any(
                      ln.startswith("pivot: pool -> qwen3.8:27b on pc: qwen3.8:27b reloads on pc") for ln in lines)
                  and any("stopped rpc-server" in ln for ln in lines) and not rig.fake.socks
                  and launch.run(rig.peer) == {} and not kf.exists())


@test
def test_halo_local_serve_pool(ctx: Ctx):
    from halo_harness import pool_run_cli
    from halo_harness.local_hf_serve_cli import cmd_serve
    from halo_harness.ollama_steward import changes_pool
    with RunRig() as rig:
        pool_run_cli.SEAMS["hold"] = lambda: None  # Ctrl+C at once
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = cmd_serve(["--pool", QWEN])
        finally:
            pool_run_cli.SEAMS.clear()
        out = buf.getvalue()
        ctx.check(f"held in the foreground, then stopped, got {rc} {out[-500:]!r}", rc == 0
                  and "the pool runs while this command does" in out and "stopped the pool's llama-server" in out)
        changes_pool.COOLDOWN_S, saved = 0.0, changes_pool.COOLDOWN_S
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = cmd_serve(["--pool", QWEN, "--keep", "--json"])
            got = json.loads(buf.getvalue())
            ctx.check(f"--keep: it serves after the command, got {rc} {got['lines'][-1]!r}", rc == 0 and got["ok"]
                      and "--keep: the pool outlives this command" in got["lines"][-1])
            changes_pool.stop(state_dir=rig.peer, by="test")
        finally:
            changes_pool.COOLDOWN_S = saved


@test
def test_the_refusals(ctx: Ctx):
    from halo_harness.local_pool import entry, launch
    from halo_harness.local_sched import claims_file as CF
    from halo_harness.ollama_steward import changes_pool
    with RunRig() as rig:
        os.environ["FAKE_LLAMA_OOM"] = f"127.0.0.1:{rig.rpc_port}"
        try:
            got = changes_pool.warm(QWEN, state_dir=rig.peer, by="test")
        finally:
            os.environ.pop("FAKE_LLAMA_OOM", None)
        oom = next((ln for ln in got["lines"] if ln.startswith("refused: the load ran out of memory")), "")
        ctx.check(f"an OOM on pc: refused with the node and its share, no CPU fallback, got {got['lines']}",
                  not got["ok"] and "on pc (" in oom and "its share is 19.7 GB; no CPU fallback (-ngl 999)" in oom
                  and entry.current() is None and launch.run(rig.peer) == {} and not rig.fake.socks
                  and not [c for c in CF.read(CF.host_file(rig.home)) if c["bundle"] == BUNDLE])
    with RunRig(rpc_build=7100) as rig:
        got = changes_pool.warm(QWEN, state_dir=rig.peer, by="test")
        ctx.check(f"pc's rpc-server on another build: refused with both versions, got {got['lines']}", not got["ok"]
                  and any(ln.startswith("version mismatch: llama-server here is b7300 (fa1ec0de), rpc-server on pc is "
                                        "b7100") for ln in got["lines"]) and entry.current() is None
                  and not rig.fake.socks and not [c for c in CF.read(CF.host_file(rig.home)) if c["bundle"] == BUNDLE])
    with RunRig(gguf=False) as rig:
        got = changes_pool.warm(QWEN, state_dir=rig.peer, by="test")
        ctx.check(f"no GGUF: the Download line, nothing claimed, got {got['lines']}", not got["ok"]
                  and got["lines"][0].startswith("preflight blocks Qwen3-Next-80B-A3B Q4_K_M: the GGUF is not on this "
                                                 "machine: Download 46 GB") and not rig.fake.argvs
                  and CF.read(CF.host_file(rig.home)) == [])


@test
def test_a_build_without_the_key_file_flag(ctx: Ctx):
    """3.3.8.0 R4: a llama-server that refuses --api-key-file is started once more with --api-key, said in one line."""
    from halo_harness.local_pool import launch
    from halo_harness.ollama_steward import changes_pool
    with RunRig() as rig:
        os.environ["FAKE_LLAMA_NO_KEY_FILE"] = "1"
        try:
            got = changes_pool.warm(QWEN, state_dir=rig.peer, by="test")
        finally:
            os.environ.pop("FAKE_LLAMA_NO_KEY_FILE", None)
        r = launch.run(rig.peer)
        ctx.check(f"warmed on the second start, the stated line, the key *** in the argv, got {got['lines']}",
                  got["ok"] and launch.KEY_ARGV_LINE in got["lines"] and r.get("key_file") is False
                  and r["argv"][r["argv"].index("--api-key") + 1] == "***" and not launch.key_path(rig.peer).exists())
        changes_pool.stop(state_dir=rig.peer, by="test")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
