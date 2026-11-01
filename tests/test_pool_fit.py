"""tests.test_pool_fit -- Halo 3.3.8.0 R1 deliverable 2: the pool catalog (local_pool/catalog.py) and the fit
(local_pool/fit.py), every case of the reference pool_kit's test_fit.py ported to the corrected arithmetic (one 16k
F16 floor for both checks; the matched-memory block only for a model with routing tables; FREE VRAM, never the card's
total), each case's numbers written out by hand. No network, no model: budget rows built by hand (pool_rig.rows).

GB = 2^30 bytes. Qwen3-Next: 46 GB + 2 GB routing per node, 100 KiB of KV per token (16k F16 = 1.5625 GB). gpt-oss-120b:
59 GB + 20 GB routing per node, 320 KiB per token (16k = 5 GB). Llama 3.3 70B: 42.5 GB dense, 320 KiB per token.
Buffers: 1 GB per node. Single node = W + R + kv(16k) + 1; the pool = W + n*R + n + kv(16k).
Run: python -m tests.test_pool_fit
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.pool_rig import rows  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
QWEN, OSS, LLAMA = "qwen3-next-80b-a3b-q4km", "gpt-oss-120b", "llama-3.3-70b-q4km"


def _fit(model, *free, **kw):
    from halo_harness.local_pool.catalog import CATALOG
    from halo_harness.local_pool.fit import fit
    return fit(CATALOG[model] if isinstance(model, str) else model, rows(*free, **kw))


@test
def test_the_catalog_marks_every_estimate(ctx: Ctx):
    from halo_harness.local_pool.catalog import CATALOG, get
    ctx.check(f"three rows in the candidates doc's order, got {list(CATALOG)}", list(CATALOG) == [QWEN, OSS, LLAMA])
    q, o, ll = CATALOG[QWEN], CATALOG[OSS], CATALOG[LLAMA]
    ctx.check("Qwen3-Next: 46 GB, 3B active, b7186+, 30-45 extrapolated", (q["weights_gb"], q["active_b"], q["min_build"])
              == (46.0, 3.0, 7186) and q["speed"] == {**q["speed"], "tok_s_low": 30.0, "tok_s_high": 45.0, "measured": False})
    ctx.check("gpt-oss: 59 GB, 5.1B active, 20 GB routing measured, 33.8 tok/s measured elsewhere",
              (o["weights_gb"], o["active_b"], o["routing_table_gb"]) == (59.0, 5.1, 20.0) and o["speed"]["measured"] is True
              and o["routing_from"].startswith("measured"))
    ctx.check("Llama 3.3 70B: 42.5 GB dense, batch-only, no routing, 3-6 not measured",
              ll["batch_only"] and ll["routing_table_gb"] == 0.0 and ll["speed"]["measured"] is False)
    ctx.check("every row: the fields the fit reads", all({"name", "display", "weights_gb", "active_b", "kv_bytes_per_token",
              "routing_table_gb", "min_build", "batch_only", "speed", "repo", "file"} <= set(r) for r in CATALOG.values()))
    ctx.check("get by display name or repo", get("gpt-oss-120b MXFP4") is o and get("Qwen/Qwen3-Next-80B-A3B-Instruct-GGUF") is q
              and get("nope") is None)


@test
def test_tensor_split_normalization(ctx: Ctx):  # ref: 16 / 32 / 8 -> 16/56, 32/56, 8/56 (of FREE VRAM now)
    from halo_harness.local_pool.budget import tensor_split
    got = tensor_split(rows(16.0, 32.0, 8.0))
    ctx.check(f"0.2857 / 0.5714 / 0.1429, summing to 1, got {got}", got == [0.2857, 0.5714, 0.1429]
              and abs(sum(got) - 1.0) < 1e-9)


@test
def test_fit_single_node_first(ctx: Ctx):  # ref: big 64 + small 16, Qwen3-Next -> run it on big
    v = _fit(QWEN, 64.0, 16.0)
    ctx.check(f"single on worker1: needs 46 + 2 + 1.5625 + 1 = 50.6 of 64.0, got {v['state']} {v['node']} {v['need_gb']}",
              v["state"] == "single" and v["node"] == "worker1" and v["need_gb"] == 50.6 and v["free_gb"] == 64.0)
    ctx.check(f"the room 64 - 46 - 2 - 1 = 15 GB holds 157,286 tokens: clamped 32k / 32k, got {v['max_ctx_f16']} {v['max_ctx_q8']}",
              v["max_ctx_f16"] == 32768 and v["max_ctx_q8"] == 32768)
    ctx.check(f"the line, got {v['verdict']!r}", v["verdict"] == "a single node holds it: worker1 has 64.0 GB free, it needs "
              "50.6 GB at 16k F16 -- run it there, pooling is unnecessary (32k F16 / 32k Q8_0 there)")
    ctx.check(f"the badge, got {v['badge']!r}", v["badge"] == "pool: 1 node holds it")


@test
def test_fit_pool_fits(ctx: Ctx):  # ref: 32 + 32, Llama 3.3 70B -> fits the pool
    v = _fit(LLAMA, 32.0, 32.0)
    ctx.check(f"pool: needs 42.5 + 0 + 2 + 5 = 49.5 of 64.0, split 0.5 / 0.5, got {v['state']} {v['need_gb']} {v['split']}",
              v["state"] == "pool" and v["need_gb"] == 49.5 and v["free_gb"] == 64.0 and v["split"] == [0.5, 0.5])
    ctx.check(f"room 64 - 42.5 - 2 = 19.5 GB = 63,897 tokens: 32k / 32k, got {v['max_ctx_f16']} {v['max_ctx_q8']}",
              v["max_ctx_f16"] == 32768 and v["max_ctx_q8"] == 32768)
    ctx.check(f"the lines, got {v['lines'][:2]}", v["lines"][:2] == [
        "fits the pool: 2 nodes, split 0.50 / 0.50, 32k F16 / 32k Q8_0",
        "needs 49.5 GB -- 64.0 GB free across 2 nodes (the split from free VRAM after each node's buffers)"])
    ctx.check(f"the badge, got {v['badge']!r}", v["badge"] == "pool: fits (2 nodes, 32k Q8_0)")


@test
def test_the_window_below_the_clamp(ctx: Ctx):  # ref test_fit_kv_budget_math, with numbers under the 32k clamp
    v = _fit(LLAMA, 26.0, 26.0)
    ctx.check(f"26 + 26: room 52 - 42.5 - 2 = 7.5 GB = 24,576 tokens: 24k F16, 49,152 Q8_0 clamped to 32k, got "
              f"{v['max_ctx_f16']} {v['max_ctx_q8']}", v["state"] == "pool" and v["max_ctx_f16"] == 24576 and v["max_ctx_q8"] == 32768)
    v = _fit(LLAMA, 25.0, 25.0)
    ctx.check(f"25 + 25: room 5.5 GB = 18,022 tokens: 17k F16 (17,408), 35,840 Q8_0 clamped, got {v['max_ctx_f16']} "
              f"{v['max_ctx_q8']} {v['verdict']!r}", v["max_ctx_f16"] == 17408 and v["max_ctx_q8"] == 32768
              and v["verdict"] == "fits the pool: 2 nodes, split 0.50 / 0.50, 17k F16 / 32k Q8_0")


@test
def test_one_16k_floor_for_both_checks(ctx: Ctx):
    v = _fit(LLAMA, 24.0, 24.0)
    ctx.check(f"24 + 24: needs 49.5, 48.0 free -- no (the reference's 4k pool floor said it fits at 11,468), got {v['lines']}",
              v["state"] == "no" and v["verdict"] == "does not fit: needs 49.5 GB, 48.0 GB free across 2 nodes")
    ctx.check("the Q8_0 line: room 3.5 GB = 22k at Q8_0, said as under the floor",
              "with the KV cache at Q8_0 it would hold 22k -- under the 16k F16 floor Halo promises, so it is not counted as a fit"
              in v["lines"])
    ctx.check("no matched-memory block for a dense model", not any("matched memory" in x for x in v["lines"]))
    v = _fit(LLAMA, 48.0, 8.0)
    ctx.check(f"48 + 8: one 48 GB card is short of 48.5 at 16k, so the pool: 49.5 of 56, got {v['state']} {v['split']}",
              v["state"] == "pool" and v["split"] == [0.8704, 0.1296] and v["need_gb"] == 49.5)


@test
def test_fit_matched_memory(ctx: Ctx):  # ref test_fit_matched_memory_warning: 40 + 20 Qwen3-Next warned; the rule moved
    v = _fit(QWEN, 40.0, 20.0)
    ctx.check(f"40 + 20 with 2 GB tables: the split from what each node has after its table (37 / 17 -> 0.6852 / 0.3148) "
              f"fits, no warning, got {v['state']} {v['split']} {v['lines']}", v["state"] == "pool" and v["split"] == [0.6852, 0.3148]
              and not any("matched memory" in x for x in v["lines"]))
    v = _fit(LLAMA, 40.0, 20.0)
    ctx.check("a dense model on mismatched nodes: no matched-memory line (its share shrinks with its node)",
              v["state"] == "pool" and not any("matched memory" in x for x in v["lines"]))
    v = _fit(OSS, 84.0, 40.0, 15.0)
    ctx.check(f"84 / 40 / 15 with 20 GB tables: 127.0 needed of 139.0, but worker3 cannot hold its own 20 GB copy, got "
              f"{v['state']} {v['split']} {v['lines'][:2]}", v["state"] == "no" and v["need_gb"] == 127.0 and v["free_gb"] == 139.0
              and v["split"] == [0.7683, 0.2317, 0.0] and v["lines"][:2] == [
                  "does not fit: worker3's share needs 21.0 GB, it has 15.0 GB free",
                  "matched memory: the 20 GB routing table replicates to every node; worker3 has 15.0 GB free and its share "
                  "needs 21.0 GB (0.0 GB of layers + 20 GB of routing tables + 1 GB of buffers)"])


@test
def test_an_ip_literal_member_fits_like_any(ctx: Ctx):  # ref test_fit_rejects_ip_literal: the rejection is dropped
    from halo_harness.local_pool.catalog import CATALOG
    from halo_harness.local_pool.fit import fit
    r = [{**x, "host": f"192.0.2.{11 + i}"} for i, x in enumerate(rows(32.0, 32.0))]
    v = fit(CATALOG[LLAMA], r)
    ctx.check(f"192.0.2.11 / 192.0.2.12 members: the same pool verdict, got {v['state']}", v["state"] == "pool"
              and v["members"] == ["worker1", "worker2"])


@test
def test_fit_no_routing_for_dense(ctx: Ctx):  # ref: 64 + 64 Llama -> fits; one node holds it, so single comes first
    v = _fit(LLAMA, 64.0, 64.0)
    ctx.check(f"single on worker1 (the tie goes by name): 42.5 + 0 + 5 + 1 = 48.5 of 64, room 20.5 GB -> 32k, got {v}",
              v["state"] == "single" and v["node"] == "worker1" and v["need_gb"] == 48.5 and v["max_ctx_f16"] == 32768
              and v["routing_table_gb"] == 0.0)


@test
def test_fit_routing_per_node(ctx: Ctx):  # ref: 64 + 64, a gpt-oss with 128,000 bytes of KV a token
    from halo_harness.local_pool.catalog import CATALOG
    m = {**CATALOG[OSS], "kv_bytes_per_token": 128000}
    v = _fit(m, 64.0, 64.0)
    ctx.check(f"single needs 59 + 20 + 1.95 + 1 = 82.0 > 64; the pool 59 + 40 + 2 + 1.95 = 103.0 of 128: fits, got "
              f"{v['state']} {v['need_gb']} {v['lines'][:2]}", v["state"] == "pool" and v["need_gb"] == 103.0 and v["lines"][:2] == [
                  "fits the pool: 2 nodes, split 0.50 / 0.50, 32k F16 / 32k Q8_0",
                  "needs 103.0 GB -- 128.0 GB free across 2 nodes (the split from free VRAM after each node's routing table "
                  "and buffers); one 20 GB routing table per node"])


@test
def test_free_vram_not_the_cards_total(ctx: Ctx):
    r = rows(48.0, 4.0)
    r[1]["total_gb"] = 48.0  # a 48 GB card with a 44 GB model resident
    from halo_harness.local_pool.catalog import CATALOG
    from halo_harness.local_pool.fit import fit
    v = fit(CATALOG[QWEN], r)
    ctx.check(f"48 free + 4 free (of two 48 GB cards) = 52.0, short of 53.6, got {v['verdict']!r}",
              v["state"] == "no" and v["verdict"] == "does not fit: needs 53.6 GB with 2 GB of routing tables per node, 52.0 GB "
              "free across 2 nodes")


@test
def test_the_three_models_on_24_24_and_24_10(ctx: Ctx):
    want = {(24.0, 24.0): {QWEN: ("no", 53.6, 48.0), OSS: ("no", 106.0, 48.0), LLAMA: ("no", 49.5, 48.0)},
            (24.0, 10.0): {QWEN: ("no", 53.6, 34.0), OSS: ("no", 106.0, 34.0), LLAMA: ("no", 49.5, 34.0)},
            (24.0, 24.0, 11.0): {QWEN: ("pool", 56.6, 59.0), OSS: ("no", 127.0, 59.0), LLAMA: ("pool", 50.5, 59.0)}}
    for pool, models in want.items():
        for name, (state, need, free) in models.items():
            v = _fit(name, *pool)
            ctx.check(f"{name} on {pool}: {state} {need} of {free}, got {v['state']} {v['need_gb']} {v['free_gb']}",
                      (v["state"], v["need_gb"], v["free_gb"]) == (state, need, free))
    v = _fit(QWEN, 24.0, 10.0)
    ctx.check(f"Qwen3-Next on 24 + 10: the matched-memory summary, got {v['lines'][1]!r}", v["lines"][1] ==
              "matched memory: the 2 GB routing table replicates to every node (4 GB of the 53.6 GB); the smallest node, worker2, "
              "has 10.0 GB free")
    v = _fit(QWEN, 24.0, 24.0, 11.0)
    ctx.check(f"Qwen3-Next on 24 / 24 / 11: 59 - 46 - 6 - 3 = 4 GB room, 41,943 tokens -> 32k / 32k, split 21 / 21 / 8, got "
              f"{v['split']} {v['max_ctx_f16']}", v["split"] == [0.42, 0.42, 0.16] and v["max_ctx_f16"] == 32768)


@test
def test_the_tail_lines(ctx: Ctx):
    v = _fit(QWEN, 32.0, 32.0, stated=True, link="Wi-Fi (adapter)")
    text = "\n".join(v["lines"])
    ctx.check(f"stated VRAM, Wi-Fi, the build, the speed extrapolated, got {v['lines']}",
              "worker1: VRAM as you stated it (32 GB); no card read there" in text
              and "worker2 is on Wi-Fi (adapter)" in text and "needs llama.cpp b7186+ on the controller and every rpc-server" in text
              and "speed: 30-45 tok/s pooled, extrapolated" in text)
    v = _fit(LLAMA, 32.0, 32.0)
    ctx.check("batch-only said", "batch-only: ~3-6 tok/s pooled, a background lane, not interactive" in v["lines"])
    v = _fit(OSS, 160.0, 4.0)
    ctx.check(f"gpt-oss on one 160 GB node: single, the speed measured elsewhere and the single-node note, got {v['lines']}",
              v["state"] == "single" and any("33.8 tok/s pooled, measured elsewhere" in x and "on one node it decodes faster" in x
                                             for x in v["lines"]))
    r = rows(32.0, 32.0) + [{"name": "worker3", "free_gb": None, "line": "worker3 (worker3.local:50052): VRAM not read"}]
    from halo_harness.local_pool.catalog import CATALOG
    from halo_harness.local_pool.fit import fit
    v = fit(CATALOG[LLAMA], r)
    ctx.check(f"a member with no VRAM read: not counted, one line, got {v['excluded']} {v['lines']}", v["excluded"] == ["worker3"]
              and v["nodes"] == 2 and any(x.startswith("worker3: not counted") for x in v["lines"]))
    v = fit(CATALOG[QWEN], rows(30.0))
    ctx.check(f"one member: a pool needs a second, got {v['verdict']!r}", v["state"] == "no" and "a pool needs a second member"
              in v["verdict"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
