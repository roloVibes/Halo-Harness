"""tests.test_pool_preflight -- Halo 3.3.8.0 R3 deliverable 3: every check before a pool launches, one function, one
answer (local_pool/preflight.py; `halo pool preflight <model>`), over tests/helpers/pool_run_rig.RunRig (pc through
its halo host: a 24 GB card with qwen3.8:27b resident; me: this machine's 40 GB card); nothing starts:

1. green: the checks in order (fit, link, rpc, versions, build, gguf, resident, window), the resident model counted as
   room Warm pivots out, the split with the --rpc device first and this GPU last, the F16 window; the card is read
   NOW (a change on the host's card within the client's 15 s cache shows); the CLI prints it;
2. a Wi-Fi member (the card's link) is left out and the pool no longer fits -- `allow_wifi` keeps it, said;
3. the blocks, each one line with its number: the GGUF not here (the Download line, nothing downloads), a window past
   the Q8_0 window, a single node that holds it (run it there), an rpc-server on another build (both versions
   printed) and under Qwen3-Next's b7186.
Run: python -m tests.test_pool_preflight
"""
from __future__ import annotations

import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.pool_run_rig import CARD40, QWEN, RunRig  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
CHECKS = ["fit", "link", "rpc", "versions", "build", "gguf", "resident", "window"]


def _check(pf: dict, name: str) -> dict:
    return next(c for c in pf["checks"] if c["check"] == name)


@test
def test_a_green_preflight(ctx: Ctx):
    from halo_harness.local_pool.budget import budgets
    from halo_harness.local_pool.preflight import preflight
    with RunRig() as rig:
        budgets(state_dir=rig.peer)  # the client's card cache is now warm with qwen3.8:27b resident
        rig.gone.add("qwen3.8:27b")
        rig.svc.view._cards.clear()
        pf = preflight(QWEN, state_dir=rig.peer)
        ctx.check(f"green, every check in order, got {pf['line']!r} {[c['check'] for c in pf['checks']]}", pf["ok"]
                  and [c["check"] for c in pf["checks"]] == CHECKS and pf["line"].startswith(
                      "preflight green: Qwen3-Next-80B-A3B Q4_K_M on 2 nodes, -c 32,768 at F16 KV"))
        pc = next(r for r in pf["rows"] if r["name"] == "pc")
        ctx.check(f"the card read now (the unload shows through the 15 s cache), got {pc['resident']} {pc['free_gb']}",
                  pc["resident"] == [] and pc["free_gb"] == 22.0)
        ctx.check(f"the order: the --rpc device first, this GPU last, got {pf['order']} {pf['split']} {pf['rpc']}",
                  pf["order"] == ["pc", "me"] and abs(sum(pf["split"]) - 1.0) < 1e-6 and pf["split"][0] < pf["split"][1]
                  and pf["rpc"][0]["addr"] == f"127.0.0.1:{rig.rpc_port}" and pf["local"] == ["me"])
        ctx.check(f"rpc: Warm starts pc's, me needs none, got {_check(pf, 'rpc')['lines']}", _check(pf, "rpc")["lines"] == [
            "pc: rpc-server is not running -- Warm starts it through its halo host (control grant)",
            "me: this machine -- llama-server serves its share on its own GPU (no rpc-server)"])
        ctx.check(f"the controller's build read, got {_check(pf, 'versions')['lines'][0]!r}",
                  _check(pf, "versions")["lines"][0].startswith("llama-server here: b7300 (fa1ec0de)"))
        ctx.check(f"the GGUF found, got {_check(pf, 'gguf')['lines']}", "Q4_K_M.gguf" in _check(pf, "gguf")["lines"][0])
    with RunRig() as rig:
        from halo_harness.pool_run_cli import cmd_preflight
        pf = preflight(QWEN, state_dir=rig.peer)
        res = _check(pf, "resident")["lines"]
        ctx.check(f"a resident model is room Warm pivots out, got {res} {pf['fit']['free_gb']}", pf["ok"]
                  and res[0].startswith("pc: qwen3.8:27b resident (18.0 GB): pivoted out first") and pf["fit"]["free_gb"] == 62.0)
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cmd_preflight([QWEN])
        out = buf.getvalue()
        ctx.check(f"the CLI prints each check, got {rc} {out[:300]!r}", rc == 0 and out.startswith("preflight green")
                  and "  gguf      ok" in out and "  window    ok" in out)


@test
def test_a_wifi_member_is_left_out_unless_allowed(ctx: Ctx):
    from halo_harness.local_pool.preflight import preflight
    with RunRig() as rig:
        rig.svc.view.readers["link"] = lambda: {"type": "wireless", "speed_mbps": None, "iface": "wlan0", "source": "fixture"}
        rig.svc.view._cards.clear()
        pf = preflight(QWEN, state_dir=rig.peer)
        link = _check(pf, "link")["lines"]
        ctx.check(f"pc on Wi-Fi: left out, said, and the pool no longer fits, got {link} {pf['line']!r}", not pf["ok"]
                  and pf["excluded"] == ["pc"] and link[0].startswith("pc is on Wi-Fi (adapter): left out")
                  and pf["line"].startswith("preflight blocks Qwen3-Next-80B-A3B Q4_K_M: does not fit"))
        pf = preflight(QWEN, allow_wifi=True, state_dir=rig.peer)
        ctx.check(f"allowed: kept and said, got {_check(pf, 'link')['lines']}", pf["ok"] and pf["excluded"] == []
                  and _check(pf, "link")["lines"] == ["pc is on Wi-Fi (adapter): kept, as you allowed (expect a slower decode)"])


@test
def test_the_blocks_are_one_line_each(ctx: Ctx):
    from halo_harness.local_pool.preflight import preflight
    with RunRig(gguf=False) as rig:
        pf = preflight(QWEN, state_dir=rig.peer)
        ctx.check(f"no GGUF: the Download line, got {pf['blocks']}", not pf["ok"] and pf["blocks"][0].startswith(
            "the GGUF is not on this machine: Download 46 GB") and pf["blocks"][0].endswith(
            "nothing downloads until you press it") and "halo local download Qwen/Qwen3-Next-80B-A3B-Instruct-GGUF Q4_K_M"
            in pf["blocks"][0])
    with RunRig() as rig:
        pf = preflight(QWEN, window=65536, state_dir=rig.peer)
        ctx.check(f"65536: past the Q8_0 window, got {pf['blocks']}", not pf["ok"] and pf["blocks"] == [
            "refused: 65,536 is past the pool's Q8_0 window 32k (the fit: the room left after the weights, every node's "
            "routing table and buffers) -- a larger promise never reaches a request"])
        ok = preflight(QWEN, window=16384, state_dir=rig.peer)
        ctx.check(f"16384 at F16, got {ok['ctx']} {ok['q8']}", ok["ok"] and ok["ctx"] == 16384 and ok["q8"] is False)
        from halo_harness.studio import ollama_hosts_view as V
        V.READERS["card"] = lambda h: {**CARD40, "gpus": [{**CARD40["gpus"][0], "total_bytes": 80 * 2 ** 30}]} \
            if h.name == "me" else None
        V.reset_cache()
        pf = preflight(QWEN, state_dir=rig.peer)
        ctx.check(f"one node holds it: run it there, got {pf['blocks']}", not pf["ok"] and pf["blocks"][0].startswith(
            "a single node holds it: me has 80.0 GB free") and pf["blocks"][0].endswith("(halo local serve on me)"))
    with RunRig(rpc_build=7100) as rig:
        from halo_harness.local_pool.hosts import rpc
        rpc({"name": "pc", "host": "pc-host", "rpc_port": rig.rpc_port}, "on")
        pf = preflight(QWEN, state_dir=rig.peer)
        ctx.check(f"another build: blocked, both versions, and b7186+, got {pf['blocks']}", not pf["ok"]
                  and pf["blocks"][0].startswith("version mismatch: llama-server here is b7300 (fa1ec0de), rpc-server on "
                                                 "pc is b7100 (fa1ec0de)")
                  and "Qwen3-Next-80B-A3B Q4_K_M needs llama.cpp b7186+: rpc-server on pc is b7100" in pf["blocks"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
