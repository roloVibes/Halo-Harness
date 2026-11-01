"""tests.test_pool_versions -- Halo 3.3.8.0 R3 deliverable 2: the llama.cpp build on the controller and on every
rpc-server (local_pool/versions.py); `--version` answered through versions.SEAMS["run"] (no binary runs):

1. parse: llama.cpp's "version: 7210 (a1b2c3d)", a bare "build: 7186", rpc-server's "Starting RPC server v3.0.0";
   word() says "b7210 (a1b2c3d), rpc v3.0.0" or "not known";
2. read() is cached per binary path + mtime: a second read asks nothing, a new file on disk is read again; no binary
   and an answer with no version are "not known" with their line; under the test flag with no seam nothing runs;
3. compare(): a build that differs blocks with BOTH versions printed, an RPC protocol that differs blocks, a worker
   whose version is not known is a note (llama-server checks it itself at connect);
4. min_build(): Qwen3-Next's b7186+ blocks a node on b7100 (named), a node whose build is not known is a note, a model
   with no min_build says nothing.
Run: python -m tests.test_pool_versions
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.pool_rig import PoolHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


@test
def test_parse_and_word(ctx: Ctx):
    from halo_harness.local_pool.versions import parse, word
    a = parse("version: 7210 (a1b2c3d)\nbuilt with cc for x86_64-linux")
    ctx.check(f"llama.cpp's --version, got {a}", a["build"] == 7210 and a["commit"] == "a1b2c3d" and a["rpc_proto"] is None)
    b = parse("build: 7186 (fake) with fake compiler")
    ctx.check(f"a bare build line, got {b}", b["build"] == 7186 and b["commit"] is None)
    c = parse("create_backend: using CUDA backend\nStarting RPC server v3.0.0\n  endpoint : 192.0.2.11:50052")
    ctx.check(f"rpc-server's start line, got {c}", c["rpc_proto"] == "3.0.0" and c["build"] is None)
    ctx.check(f"word, got {word({**a, 'rpc_proto': '3.0.0'})!r} {word({})!r}",
              word({**a, "rpc_proto": "3.0.0"}) == "b7210 (a1b2c3d), rpc v3.0.0" and word({}) == "not known")


@test
def test_read_is_cached_per_path_and_mtime(ctx: Ctx):
    from halo_harness.local_pool import versions as V
    with PoolHome() as h:
        exe = Path(h.root) / "llama-server"
        exe.write_text("one", encoding="utf-8")
        asked = []
        V.forget()
        V.SEAMS["run"] = lambda argv: (asked.append(list(argv)), (0, "version: 7300 (fa1ec0de)"))[1]
        try:
            one = V.read([str(exe)])
            two = V.read([str(exe)])
            ctx.check(f"read once, cached, got {one} {len(asked)}", one["build"] == 7300 and one["ok"] and two == one
                      and len(asked) == 1 and asked[0] == [str(exe), "--version"])
            later = time.time() + 5
            exe.write_text("a new build", encoding="utf-8")
            os.utime(exe, (later, later))
            V.SEAMS["run"] = lambda argv: (asked.append(list(argv)), (0, "version: 7310 (b0b0b0b)"))[1]
            three = V.read([str(exe)])
            ctx.check(f"a new file on disk is read again, got {three['build']} {len(asked)}", three["build"] == 7310
                      and len(asked) == 2)
            V.SEAMS["run"] = lambda argv: (1, "error: unknown argument: --version")
            none = V.read([str(Path(h.root) / "rpc-server")])
            ctx.check(f"no version in the answer: not known, its line kept, got {none}", none["ok"] is False
                      and "unknown argument" in none["line"])
            ctx.check(f"no binary at all, got {V.read(None)}", V.read(None)["source"] == "no binary")
            V.SEAMS.clear()
            V.forget()
            flag = V.read([str(exe)])
            ctx.check(f"the test flag with no seam: nothing runs, got {flag['line']!r}", flag["ok"] is False
                      and "not run under the test flag" in flag["line"])
        finally:
            V.SEAMS.clear()
            V.forget()


@test
def test_compare_blocks_with_both_versions(ctx: Ctx):
    from halo_harness.local_pool.versions import compare
    ctl = {"build": 7300, "commit": "fa1ec0de", "rpc_proto": None, "line": ""}
    blocks, notes = compare(ctl, [{"name": "worker1", "version": {"build": 7300, "commit": "fa1ec0de"}},
                                  {"name": "worker2", "version": {"build": 7100, "commit": "0ld0ld0"}},
                                  {"name": "worker3", "version": {}}])
    ctx.check(f"worker2 blocks with both versions, got {blocks}", len(blocks) == 1 and blocks[0].startswith(
        "version mismatch: llama-server here is b7300 (fa1ec0de), rpc-server on worker2 is b7100 (0ld0ld0)"))
    ctx.check(f"worker3 not known: a note, got {notes}", len(notes) == 1 and notes[0].startswith(
        "rpc-server on worker3: its version is not known") and "refuses a worker that differs" in notes[0])
    blocks, _n = compare({"build": None, "rpc_proto": "3.0.0"}, [{"name": "w", "version": {"rpc_proto": "2.0.0"}}])
    ctx.check(f"an RPC protocol mismatch blocks, got {blocks}", blocks == [
        "RPC protocol mismatch: llama-server here speaks rpc v3.0.0, rpc-server on w speaks rpc v2.0.0"])


@test
def test_min_build_on_every_node(ctx: Ctx):
    from halo_harness.local_pool.catalog import get
    from halo_harness.local_pool.versions import min_build
    qwen, oss = get("qwen3-next-80b-a3b-q4km"), get("gpt-oss-120b")
    blocks, notes = min_build(qwen, {"build": 7300}, [{"name": "worker1", "version": {"build": 7100}},
                                                      {"name": "worker2", "version": {}}])
    ctx.check(f"b7186+: worker1 on b7100 blocks, worker2 not known is a note, got {blocks} {notes}", blocks == [
        "Qwen3-Next-80B-A3B Q4_K_M needs llama.cpp b7186+: rpc-server on worker1 is b7100"]
              and notes == ["Qwen3-Next-80B-A3B Q4_K_M needs llama.cpp b7186+: the build of rpc-server on worker2 is not "
                            "known"])
    ctx.check("a model with no min_build says nothing", min_build(oss, {"build": 1}, [{"name": "w", "version": {}}])
              == ([], []))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
