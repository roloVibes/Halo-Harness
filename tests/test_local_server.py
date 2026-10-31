"""tests.test_local_server -- Halo 3.3.5.0 R5: providers/local_server.py + local_server_cmd.py with the fake binary
(tests/helpers/fake_llama_server.py as `huggingface.llama_server_bin`; it binds 127.0.0.1 and loads no model), a
fresh home whose one Ollama host `box` (127.0.0.1:9, never asked: its hardware card comes from the
ollama_hosts_view.READERS seam) is this machine's card. Never a real llama-server or mlx_lm:

1. the flags from the planner: the window (every layer on the GPU, capped by the file's trained context) and -ngl
   from box's card, one slot, the card's kv_cache_type -> --cache-type-k/v and --flash-attn on; each with its source;
2. start: /health polled until ready, the command line, /props n_ctx = -c, the registry entry (id, kind, flags,
   log, halo), the catalog's `hf:local/<model>` row and the resolver landing on it;
3. status (/health, /slots), the log's tail, stop (the process gone, the row gone);
4. the "still loading" cap (the server keeps going, status later marks it ready);
5. a server Halo did not start cannot be stopped from here; exit_sweep stops ours unless keep;
6. a binary that exits says why (its log); no llama_server_bin under the test flag says so.
Run: python -m tests.test_local_server
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.mock_hub import gguf_bytes  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
FAKE = Path(__file__).resolve().parent / "helpers" / "fake_llama_server.py"
_VARS = ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "BRIDGE_TEST_NO_BACKGROUND_NET", "FAKE_LLAMA_LOAD_S", "FAKE_LLAMA_EXIT")
GIB, MIB = 2 ** 30, 2 ** 20


def box_card(kv: str = "f16") -> dict:
    return {"gpus": [{"id": "0", "name": "a 24 GB card", "library": "CUDA", "total_bytes": 24564 * MIB}], "unified": False,
            "ram_bytes": 64 * GIB, "other_users": [], "server": {"kv_cache_type": kv, "parallel": 1}, "loaded": [],
            "sources": [], "read_at": "fixture"}


class Home:
    def __init__(self, bin_set: bool = True, kv: str = "f16"):
        self.bin_set, self.kv = bin_set, kv

    def __enter__(self):
        from halo_harness.studio import ollama_hosts_view as V
        self._saved = {k: os.environ.get(k) for k in _VARS}
        self.root = Path(tempfile.mkdtemp(prefix="l4_srv-")).resolve()
        for k in ("BRIDGE_STATE_DIR", "FAKE_LLAMA_LOAD_S", "FAKE_LLAMA_EXIT"):
            os.environ.pop(k, None)
        os.environ.update(BRIDGE_TEST_HOME=str(self.root), BRIDGE_TEST_NO_BACKGROUND_NET="1")
        self.state = self.root / ".halo"
        self.models = self.root / "models"
        self.models.mkdir(parents=True)
        self.state.mkdir()
        self.gguf = self.models / "Tiny-1B-Q4_K_M.gguf"
        self.gguf.write_bytes(gguf_bytes(400_000, ctx=40960, layers=36))
        cfg = {"ollama": {"hosts": [{"name": "box", "url": "http://127.0.0.1:9"}]},
               "huggingface": {"model_dirs": [str(self.models)]}}
        if self.bin_set:
            cfg["huggingface"]["llama_server_bin"] = [sys.executable, str(FAKE)]
        (self.state / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
        V.reset_cache()
        V.READERS.update({"card": lambda h: box_card(self.kv), "catalog": lambda h: {"models": []}})
        return self

    def serve(self, **kw):
        from halo_harness.providers.local_server import start
        from halo_harness.providers.local_server_cmd import plan_flags
        f = plan_flags(self.gguf, "gguf", model="Tiny-1B-Q4_K_M")
        args = dict(runtime="llama-server", window=f["window"], ngl=f["ngl"], parallel=f["parallel"], kv_type=f["kv_type"],
                    flash_attn=f["flash_attn"], num_predict=f["num_predict"], state_dir=self.state, sources=f["sources"],
                    wait_s=20)
        args.update(kw)
        return f, start(self.gguf, **args)

    def __exit__(self, *exc):
        from halo_harness.providers.local_server import servers, stop
        from halo_harness.studio import ollama_hosts_view as V
        for e in servers(self.state):
            stop(e["id"], state_dir=self.state)
        V.READERS.clear()
        V.reset_cache()
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


@test
def test_the_flags_come_from_the_planner_and_say_why(ctx: Ctx):
    with Home() as h:
        from halo_harness.providers.local_server_cmd import llama_argv, plan_flags
        f = plan_flags(h.gguf, "gguf", model="Tiny-1B-Q4_K_M")
        ctx.check(f"window = the trained context (every layer fits), from box's card, got {f['window']} {f['sources']['window']}",
                  f["window"] == 40960 and "box" in f["sources"]["window"] and "trained context" in f["sources"]["window"])
        ctx.check(f"-ngl every layer + the output, got {f['ngl']} {f['sources']['ngl']}", f["ngl"] == 37 and "every layer" in f["sources"]["ngl"])
        ctx.check(f"one slot, no KV quant, got {f['parallel']} {f['kv_type']}", f["parallel"] == 1 and f["kv_type"] is None and not f["flash_attn"])
        argv = llama_argv(["llama-server"], path=h.gguf, model="m", port=8099, flags=f)
        ctx.check(f"the command line, got {argv}", argv[argv.index("-c") + 1] == "40960" and argv[argv.index("-ngl") + 1] == "37"
                  and argv[argv.index("-np") + 1] == "1" and argv[argv.index("--host") + 1] == "127.0.0.1" and "--cache-type-k" not in argv)
        asked = plan_flags(h.gguf, "gguf", window=8192)
        ctx.check(f"an asked window, got {asked['window']} {asked['sources']['window']}", asked["window"] == 8192 and asked["sources"]["window"] == "asked")
    with Home(kv="q8_0") as h:
        from halo_harness.providers.local_server_cmd import llama_argv, plan_flags
        f = plan_flags(h.gguf, "gguf")
        argv = llama_argv(["llama-server"], path=h.gguf, model="m", port=8099, flags=f)
        ctx.check(f"the card's q8_0 KV: --cache-type-k/v and --flash-attn on, got {argv} {f['sources']['kv_type']}",
                  argv[argv.index("--cache-type-k") + 1] == "q8_0" and argv[argv.index("--cache-type-v") + 1] == "q8_0"
                  and argv[argv.index("--flash-attn") + 1] == "on" and "kv_cache_type" in f["sources"]["kv_type"])


@test
def test_start_health_registry_and_the_catalog(ctx: Ctx):
    with Home() as h:
        f, info = h.serve()
        ctx.check(f"ready, got {info.ok} {info.ready} {info.say}", info.ok and info.ready and "hf:local/Tiny-1B-Q4_K_M" in info.say)
        from halo_harness.providers.local_server_cmd import get
        code, props = get(f"{info.url}/props")
        ctx.check(f"/props n_ctx = -c, got {props}", code == 200 and props["default_generation_settings"]["n_ctx"] == f["window"])
        from halo_harness.providers.local_runtime import load_registry
        row = next(e for e in load_registry(h.state) if e.get("id") == info.id)
        ctx.check(f"the registry row, got {row}", row["halo"] and row["kind"] == "llama-server" and row["ready"]
                  and row["flags"]["window"] == f["window"] and row["log"].endswith(f"{info.id}.log") and row["runtime"] == "llama-server")
        from halo_harness.providers.local_models import build_local_view
        refs = [r.ref for r in build_local_view(state_dir=h.state)]
        ctx.check(f"the catalog lists hf:local/<model>, got {refs}", "hf:local/Tiny-1B-Q4_K_M" in refs)
        from halo_harness.providers.huggingface_local_resolve import resolve_local_server
        got = resolve_local_server(None, model="Tiny-1B-Q4_K_M", state_dir=h.state)
        ctx.check(f"the resolver lands on it, got {got}", got is not None and got.base_url == f"{info.url}/v1")


@test
def test_status_tail_and_stop(ctx: Ctx):
    with Home() as h:
        from halo_harness.bg_run import pid_alive
        from halo_harness.providers.local_server import status, stop, tail
        _f, info = h.serve()
        st = status(info.id, state_dir=h.state)
        ctx.check(f"status: /health ok and /slots, got {st}", st["ready"] and st["health"] == {"status": "ok"} and len(st["slots"]) == 1)
        t = tail(info.id, 20, state_dir=h.state)
        ctx.check(f"the log's tail, got {t['lines'][-4:]}", any("offloaded 37/37 layers" in ln for ln in t["lines"])
                  and any("halo starts:" in ln for ln in t["lines"]))
        by_port = stop(str(info.port), state_dir=h.state)
        ctx.check(f"stop by port, got {by_port}", by_port["ok"] and "terminated" in by_port["say"])
        from halo_harness.providers.local_runtime import load_registry
        time.sleep(0.3)
        ctx.check("the process and the row are gone", not pid_alive(info.pid) and not [e for e in load_registry(h.state) if e.get("id") == info.id])


@test
def test_the_still_loading_cap(ctx: Ctx):
    with Home() as h:
        from halo_harness.providers.local_server import status
        os.environ["FAKE_LLAMA_LOAD_S"] = "2.5"
        _f, info = h.serve(wait_s=0.6)
        ctx.check(f"still loading, the server goes on, got {info.ready} {info.say}", info.ok and not info.ready and "still loading" in info.say)
        end = time.monotonic() + 15
        st = status(info.id, state_dir=h.state)
        while not st["ready"] and time.monotonic() < end:
            time.sleep(0.3)
            st = status(info.id, state_dir=h.state)
        from halo_harness.providers.local_runtime import load_registry
        ctx.check(f"later status says ready and marks the row, got {st}", st["ready"]
                  and next(e for e in load_registry(h.state) if e.get("id") == info.id)["ready"])


@test
def test_not_ours_cannot_be_stopped_and_the_exit_sweep(ctx: Ctx):
    with Home() as h:
        from halo_harness.providers.local_runtime import _upsert_registry_entry
        from halo_harness.providers.local_server import exit_sweep, servers, stop
        _upsert_registry_entry(h.state, {"model": "other", "runtime": "llama-server", "pid": 1, "port": 9999, "base_url": "http://127.0.0.1:9999/v1"})
        for key in ("9999", "nobody-1"):
            got = stop(key, state_dir=h.state)
            ctx.check(f"{key}: not Halo's, says so, got {got}", not got["ok"] and "did not start" in got["say"])
        _f, kept = h.serve(keep=True)
        _f, mine = h.serve()
        swept = exit_sweep(h.state)
        left = [e["id"] for e in servers(h.state)]
        ctx.check(f"the sweep stops ours, not the kept one, got {swept} {left}", [s.get("id") for s in swept] == [mine.id] and left == [kept.id])


@test
def test_a_binary_that_exits_and_no_binary_under_the_flag(ctx: Ctx):
    with Home() as h:
        os.environ["FAKE_LLAMA_EXIT"] = "1"
        _f, info = h.serve()
        ctx.check(f"it says it exited, with its log, got {info.say}", not info.ok and "exited" in info.say and "failed to load" in info.say)
    with Home(bin_set=False) as h:
        _f, info = h.serve()
        ctx.check(f"no binary under the flag says so, got {info.say}", not info.ok and "llama_server_bin" in info.say)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
