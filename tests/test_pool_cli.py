"""tests.test_pool_cli -- Halo 3.3.8.0 R1 deliverable 5: `halo pool scan | members | add | remove | recommend | verdict`
(pool_cli.py, pool_scan_cli.py) in-process over a scratch home (tests/helpers/pool_rig.py); the scan's network layer
faked and an rpc-server stand-in on 127.0.0.1:0; no model call:

1. add / members / remove: the lines, the exit codes, --json; `halo pool` alone is usage (2), an unknown verb 2;
2. recommend and verdict on two members with stated VRAM (40 + 20 GB): the ranked lines, --batch, --json, the preview,
   an unknown model (1), and the line that says what R1 cannot do yet;
3. scan: the candidate, the member it is, the member probes, the note; --json; every verb's --help.
Run: python -m tests.test_pool_cli
"""
from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.pool_rig import PoolHome, rpc_listener  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _run(*argv) -> "tuple[int, str, str]":
    from halo_harness.cli import main
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = main(["pool", *argv])
    return rc, out.getvalue(), err.getvalue()


@test
def test_add_members_remove(ctx: Ctx):
    with PoolHome() as h:
        rc, out, _ = _run()
        ctx.check(f"`halo pool` alone: usage, 2, got {rc}", rc == 2 and "halo pool members" in out)
        rc, _o, err = _run("frobnicate")
        ctx.check(f"an unknown verb: 2, got {rc}", rc == 2 and "usage: halo pool" in err)
        rc, out, _ = _run("add", "worker1", "worker1.local:50052", "--vram", "40")
        ctx.check(f"add: 0, VRAM as you stated it, got {rc} {out!r}", rc == 0 and out.strip() ==
                  "added worker1 (worker1.local:50052): VRAM as you stated it (40 GB)")
        rc, out, _ = _run("add", "worker2", "192.0.2.12", "--vram", "20", "--json")
        got = json.loads(out)
        ctx.check(f"add --json: ok, both members, got {got}", rc == 0 and got["ok"] and len(got["members"]) == 2)
        rc, _o, err = _run("add", "worker2", "worker9.local")
        ctx.check(f"a name twice: 1, the line on stderr, got {rc} {err!r}", rc == 1 and "worker2 is a member twice" in err)
        rc, out, _ = _run("members")
        ctx.check(f"members: the head with the split, each line, the R2 line, got {out!r}", rc == 0 and out.startswith(
            "2 members, 2 with VRAM read: 60.0 GB free of 60.0 GB; split 0.67 / 0.33 (from free VRAM)")
                  and "worker2 (192.0.2.12:50052): 20.0 GB free -- VRAM as you stated it; link unknown; RTT not probed (Scan) "
                  "-- share 0.33" in out and "warm and stop arrive in R2" in out)
        rc, out, _ = _run("members", "--json")
        got = json.loads(out)
        ctx.check(f"members --json: the rows, the split, the port, got {list(got)}", rc == 0 and got["split"] == [0.6667, 0.3333]
                  and got["rpc_port"] == 50052 and [m["name"] for m in got["members"]] == ["worker1", "worker2"])
        rc, out, _ = _run("remove", "worker2")
        ctx.check(f"remove: 0, got {rc} {out!r}", rc == 0 and "removed worker2 from the pool (1 member left)" in out)
        rc, _o, err = _run("remove", "worker2")
        ctx.check(f"remove again: 1, got {rc} {err!r}", rc == 1 and "no member named 'worker2'" in err)
        h.config(**{"huggingface.local_servers": [{"name": "pool", "url": "http://127.0.0.1:8080/v1"}]})
        rc, out, _ = _run("members")
        ctx.check(f"a local server named pool: the reserved-name line, got {out!r}", rc == 0
                  and "! huggingface.local_servers has an entry named 'pool': the pool becomes that entry in R2" in out)


@test
def test_recommend_and_verdict(ctx: Ctx):
    with PoolHome():
        _run("add", "worker1", "worker1.local", "--vram", "40")
        _run("add", "worker2", "worker2.local", "--vram", "20")
        rc, out, _ = _run("recommend")
        ctx.check(f"recommend: the head, Qwen3-Next ranked 1, gpt-oss not fitting, Llama left out, got {out!r}", rc == 0
                  and out.startswith("2 of 2 members with their VRAM read, 60.0 GB free; 1 fits the pool, 0 fit one node, "
                                     "1 does not fit, 1 batch-only left out")
                  and "1. Qwen3-Next-80B-A3B Q4_K_M [b7186+]: fits the pool: 2 nodes, split 0.69 / 0.31, 32k F16 / 32k Q8_0"
                  in out and "-  gpt-oss-120b MXFP4: does not fit: needs 106.0 GB with 20 GB of routing tables per node, "
                  "60.0 GB free across 2 nodes" in out and "-  Llama 3.3 70B Q4_K_M: batch-only, left out" in out
                  and out.rstrip().endswith("warm and stop arrive in R2 (the controller); this round reads and recommends only"))
        rc, out, _ = _run("recommend", "--batch")
        ctx.check(f"--batch: Llama ranked 2, tagged, got {rc}", rc == 0 and "2. Llama 3.3 70B Q4_K_M [batch-only]: fits the pool"
                  in out)
        rc, out, _ = _run("recommend", "--json")
        got = json.loads(out)
        ctx.check(f"--json: rows, others, hidden, got {list(got)}", rc == 0 and [r["model"] for r in got["rows"]] ==
                  ["qwen3-next-80b-a3b-q4km"] and got["hidden"][0]["model"] == "llama-3.3-70b-q4km")
        rc, out, _ = _run("verdict", "Qwen3-Next-80B-A3B Q4_K_M")
        ctx.check(f"verdict by display name: every line and the preview, got {out!r}", rc == 0
                  and "worker1: VRAM as you stated it (40 GB); no card read there" in out and "preview: needs 53.6 GB -- 60.0 GB "
                  "free across 2 nodes; 32k Q8_0; one 2 GB routing table per node; download 46 GB" in out)
        rc, out, _ = _run("verdict", "gpt-oss-120b", "--json")
        got = json.loads(out)
        ctx.check(f"verdict --json, got {got.get('state')} {got.get('badge')}", rc == 0 and got["state"] == "no"
                  and got["badge"] == "pool: no" and got["download"] is None)
        rc, _o, err = _run("verdict", "llama-9000")
        ctx.check(f"an unknown model: 1, the catalog named, got {rc} {err!r}", rc == 1 and "is not in the pool catalog" in err
                  and "gpt-oss-120b" in err)


@test
def test_scan(ctx: Ctx):
    from halo_harness.providers import rpc_probe as P
    with PoolHome(), rpc_listener() as port:
        _run("add", "w1", f"127.0.0.1:{port}", "--vram", "24")
        rc, out, _ = _run("scan", "--port", str(port))
        ctx.check(f"no seam: the scan is off in tests, the member still probed, got {out!r}", rc == 0
                  and "note: the network scan is off in tests" in out and f"member w1: 127.0.0.1:{port} answers in" in out)
        P.SEAMS.update(sweep=lambda networks, ports, deadline: [("127.0.0.1", port)], own=lambda: "192.0.2.5")
        rc, out, _ = _run("scan", "--port", str(port))
        ctx.check(f"the candidate is the member w1, got {out!r}", rc == 0 and out.startswith(
            f"1 rpc-server port answered on :{port} across 192.0.2.0/24; 1 of 1 members answer") and "(member w1)" in out)
        rc, out, _ = _run("scan", "--port", str(port), "--no-own-subnet", "--subnet", "192.0.2.64/26", "--json")
        got = json.loads(out)
        ctx.check(f"--json, --subnet, --no-own-subnet, got {got['networks']}", rc == 0 and got["networks"] == ["192.0.2.64/26"])
    for verb in ("members", "add", "remove", "recommend", "verdict", "scan"):
        rc, out, _ = _run(verb, "--help")
        ctx.check(f"halo pool {verb} --help: 0, got {rc}", rc == 0 and f"halo pool {verb}" in out)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
