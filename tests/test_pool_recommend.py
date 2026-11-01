"""tests.test_pool_recommend -- Halo 3.3.8.0 R1 deliverable 3: the recommendation and the honest preview
(local_pool/recommend.py), the reference pool_kit's test_recommend.py cases ported, the preview line's numbers written
out by hand. No network, no model: budget rows built by hand (pool_rig.rows), a scratch home for the download rate.

The ETA: 46 GB = 46 x 2^30 bytes; at the assumed 50 MB/s that is 987.8 s (~16 min); at a measured 100 MB/s 493.9 s
(~8 min).
Run: python -m tests.test_pool_recommend
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.pool_rig import PoolHome, rows  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
QWEN, OSS, LLAMA = "qwen3-next-80b-a3b-q4km", "gpt-oss-120b", "llama-3.3-70b-q4km"


def _rec(*free, **kw):
    from halo_harness.local_pool.recommend import recommend
    return recommend(rows(*free), **kw)


@test
def test_single_node_rows_rank_last(ctx: Ctx):  # ref test_recommend_single_node_first: 80 + 80
    with PoolHome():
        r = _rec(80.0, 80.0, allow_batch=True)
        got = [(v["model"], v["state"], v["rank"]) for v in r["rows"]]
        ctx.check(f"gpt-oss pools first; Qwen3-Next (3B) then Llama (70B) on one node, last, got {got}",
                  got == [(OSS, "pool", 1), (QWEN, "single", 2), (LLAMA, "single", 3)] and not r["others"])
        ctx.check(f"the head, got {r['head']!r}", r["head"] == "2 of 2 members with their VRAM read, 160.0 GB free; 1 fits the "
                  "pool, 2 fit one node, 0 do not fit")


@test
def test_batch_only_gated_and_tagged(ctx: Ctx):  # ref test_batch_only_gated / test_batch_only_allowed
    with PoolHome():
        r = _rec(32.0, 32.0)
        ctx.check(f"Llama left out, with its line, got {r['hidden']}", [v["model"] for v in r["rows"]] == [QWEN]
                  and r["hidden"][0]["model"] == LLAMA and r["hidden"][0]["line"].startswith(
                      "Llama 3.3 70B Q4_K_M: batch-only, left out (--batch shows it): fits the pool"))
        r = _rec(32.0, 32.0, allow_batch=True)
        ll = next(v for v in r["rows"] if v["model"] == LLAMA)
        ctx.check(f"--batch: it ranks by its 70B active, always tagged, got {ll['rank']} {ll['tags']}", ll["rank"] == 2
                  and ll["tags"] == ["batch-only"] and "batch-only: ~3-6 tok/s pooled" in " ".join(ll["lines"]))
        ctx.check("gpt-oss does not fit 64 GB: under others, no rank", [v["model"] for v in r["others"]] == [OSS]
                  and r["others"][0]["rank"] is None)


@test
def test_ordering_by_active_params(ctx: Ctx):  # ref: 42 x 3 -> Qwen3-Next then gpt-oss
    with PoolHome():
        r = _rec(42.0, 42.0, 42.0)
        ctx.check(f"42 x 3: gpt-oss needs 59 + 60 + 3 + 5 = 127.0 of 126.0 -- three routing copies, so only Qwen3-Next, got "
                  f"{[(v['model'], v['state']) for v in r['rows']]} {r['others'][0]['need_gb']}",
                  [v["model"] for v in r["rows"]] == [QWEN] and r["others"][0]["need_gb"] == 127.0)
        r = _rec(44.0, 44.0, 44.0)
        ctx.check(f"44 x 3: both pool, 3B before 5.1B, ranks 1, 2, got {[(v['model'], v['rank']) for v in r['rows']]}",
                  [(v["model"], v["rank"]) for v in r["rows"]] == [(QWEN, 1), (OSS, 2)])


@test
def test_a_model_not_in_the_catalog_and_no_members(ctx: Ctx):
    from halo_harness.local_pool.catalog import CATALOG
    from halo_harness.local_pool.recommend import recommend, verdict
    with PoolHome():
        cat = {k: v for k, v in CATALOG.items() if k != QWEN}
        names = [v["model"] for v in recommend(rows(44.0, 44.0, 44.0), catalog=cat)["rows"]]
        ctx.check(f"a catalog without Qwen3-Next does not list it, got {names}", QWEN not in names and names == [OSS])
        r = recommend([])
        ctx.check(f"no members: nothing ranked, every model under others, got {r['head']!r}", r["rows"] == []
                  and len(r["others"]) == 2 and r["head"].startswith("0 of 0 members"))
        ctx.check("verdict of an unknown name: None", verdict("nope", rows(32.0, 32.0)) is None)


@test
def test_the_preview_before_any_download(ctx: Ctx):
    from halo_harness.local_pool.recommend import verdict
    with PoolHome() as h:
        v = verdict(QWEN, rows(32.0, 32.0), state_dir=h.state)
        ctx.check(f"the pool preview, got {v['preview']!r}", v["preview"] ==
                  "needs 53.6 GB -- 64.0 GB free across 2 nodes; 32k Q8_0; one 2 GB routing table per node; download 46 GB, "
                  "~16 min at the assumed 50 MB/s (no download measured yet) -- nothing downloads until you press it")
        d = v["download"]
        ctx.check(f"the one button's job: the repo, Q4_K_M, 988 s, the cli line, got {d}", d["repo"] ==
                  "Qwen/Qwen3-Next-80B-A3B-Instruct-GGUF" and d["file"] == "Q4_K_M" and d["eta_s"] == 988
                  and d["cli"] == "halo local download Qwen/Qwen3-Next-80B-A3B-Instruct-GGUF Q4_K_M")
        ctx.check(f"the speed word and the tags, got {v['speed_word']!r} {v['tags']}", v["speed_word"] ==
                  "30-45 tok/s extrapolated (no pool speed card yet: halo local bench --host pool)"
                  and v["speed"]["measured"] is False and v["tags"] == ["b7186+"])  # 3.3.8.0 R4: the pool's card word
        pulls = h.state / "ollama" / "pulls.json"
        pulls.parent.mkdir(parents=True, exist_ok=True)
        pulls.write_text(json.dumps({"jobs": [{"ok": True, "speed": 100e6, "started": 100.0, "kind": "download",
                                               "name": "unsloth/x-GGUF"}]}), encoding="utf-8")
        v = verdict(QWEN, rows(32.0, 32.0), state_dir=h.state)
        ctx.check(f"at your last measured rate, got {v['preview']!r}", v["preview"].endswith(
            "download 46 GB, ~8 min at your last measured 100 MB/s (download of unsloth/x-GGUF) -- nothing downloads until you "
            "press it") and v["download"]["eta_s"] == 494)
        v = verdict(QWEN, rows(80.0, 80.0), state_dir=h.state)
        ctx.check(f"the single-node preview, got {v['preview']!r}", v["preview"].startswith(
            "needs 50.6 GB -- worker1 has 80.0 GB free; 32k F16 there, no pool; download 46 GB"))
        v = verdict(OSS, rows(32.0, 32.0), state_dir=h.state)
        ctx.check(f"what does not fit offers no download, got {v['preview']!r} {v['download']}", v["preview"] ==
                  "needs 106.0 GB -- 64.0 GB free; does not fit, so nothing to download" and v["download"] is None
                  and v["speed_word"].startswith("33.8 tok/s measured elsewhere (no pool speed card yet"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
