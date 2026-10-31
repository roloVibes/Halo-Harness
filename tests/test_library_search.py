"""tests.test_library_search -- Halo 3.3.6.0 R2 "the filters and the ranking" (models_library/search.py,
search_filters.py, search_cost.py) over the shipped library snapshot and the hub's fixtures with a fixture host
card (tests/helpers/search_rig.py: `box`, a 24 GB CUDA card, qwen3.5:9b resident) and fixture profiles; no request,
no model call, nothing pulled:

1. needs at a truth floor: declared keeps the declared, verified only the probed, `any` keeps "needs a probe";
2. the ranking: verified first, declared second, expected last; then fits, measured speed, size, licence;
3. each fit filter (fits at the window, fully on the GPU, co-resides, quant, params, disk, speed, cold load, KV);
4. each supply filter (licence, gated, source, runs here, Ollama supports, freshness);
5. the cost preview's numbers (download and eta, assumed and measured; VRAM; cold load; tok/s; evicts);
6. the labelling: the chips' glyphs, the two verdicts, a crashed row greyed and last; `halo models browse`'s flags.
Run: python -m tests.test_library_search
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.search_rig import GIB, SearchHome, box_card  # noqa: E402

test, TESTS = new_registry()
RES = [{"model": "qwen3.5:9b", "size": 8 * GIB, "size_vram": 8 * GIB, "expires": "2026-10-30T10:00:00Z"}]


def _names(ans) -> list:
    return [r["name"] for r in ans["rows"]]


def _row(ans, name):
    return next((r for r in ans["rows"] if r["name"] == name), None)


@test
def test_needs_at_a_truth_floor(ctx: Ctx):
    with SearchHome(card=box_card(loaded=RES)) as h:
        h.profile("qwen3-coder:30b")
        dec = h.library(q="qwen3-coder", search={"needs": {"tools": "declared"}})
        ver = h.library(q="qwen3", search={"needs": {"tools": "verified"}})
        anyp = h.library(q="qwen3-coder", search={"needs": {"agentic-ready": "any"}})
        strict = h.library(q="qwen3", search={"needs": {"agentic-ready": "verified"}})
    ctx.check(f"declared: every qwen3-coder row (its chips declare tools), got {_names(dec)}",
              "qwen3-coder:30b" in _names(dec) and all(r["facts"]["tools"]["truth"] in ("declared", "verified") for r in dec["rows"]))
    ctx.check(f"verified: only the probed one, got {_names(ver)}", _names(ver) == ["qwen3-coder:30b"])
    ctx.check(f"any: unprobed rows stay at tier 0 with 'needs a probe', got {[(r['name'], r['gate_tier']) for r in anyp['rows']]}",
              _row(anyp, "qwen3-coder:30b")["gate_tier"] == 3 and any(r["gate_tier"] == 0 for r in anyp["rows"]))
    ctx.check(f"verified agentic-ready: the probed agent only, got {_names(strict)}", _names(strict) == ["qwen3-coder:30b"])


@test
def test_the_ranking_order(ctx: Ctx):
    with SearchHome(card=box_card(loaded=RES)) as h:
        h.profile("qwen3:8b", speed={"tok_s": 120.0, "cold_load_s": 6.0, "at_window": 32768}, size_gb=5.2)
        h.profile("qwen3:14b", speed={"tok_s": 80.0, "cold_load_s": 9.0, "at_window": 32768}, size_gb=9.3)
        ans = h.library(q="qwen3", search={"needs": {"tools": "expected"}})
        big = h.library(window=131072, q="qwen3:", search={"needs": {"tools": "declared"}})
    tiers = [r["gate_tier"] for r in ans["rows"]]
    ctx.check(f"verified first, declared second, expected last, got {tiers[:6]}...{tiers[-3:]}",
              tiers == sorted(tiers, reverse=True) and tiers[0] == 3 and 2 in tiers and 1 in tiers)
    ctx.check(f"two probed: the faster one first, got {_names(ans)[:2]}", _names(ans)[:2] == ["qwen3:8b", "qwen3:14b"])
    lv = [r["fit"]["level"] for r in big["rows"] if r["gate_tier"] == 2]
    order = {"fits": 4, "tight": 3, "unknown": 2, "spill": 1, "no": 0}
    ctx.check(f"within a tier, fits before tight before spill and no, got {lv}", [order[x] for x in lv] == sorted((order[x] for x in lv), reverse=True))
    same = [r for r in ans["rows"] if r["gate_tier"] == 2 and r["fit"]["level"] == "fits"]
    sizes = [r["size_bytes"] for r in same if isinstance(r["size_bytes"], int)]
    ctx.check(f"then the smaller download first, got {sizes[:6]}", sizes == sorted(sizes))
    ctx.check(f"every row says why its rank, got {ans['rows'][0]['why_this_rank']!r}",
              "tools verified" in ans["rows"][0]["why_this_rank"] and "measured" in ans["rows"][0]["why_this_rank"])


@test
def test_each_fit_filter(ctx: Ctx):
    with SearchHome(card=box_card(loaded=RES)) as h:
        n = lambda **f: _names(h.library(q="qwen3", search={"fit": f}))  # noqa: E731
        wide = h.library(window=131072, q="qwen3", search={"fit": {"fits_at": True}})
        got = {"all": n(), "fits": n(fits_at=True), "gpu": n(fully_on_gpu=True), "co": n(co_resides_with=["qwen3.5:9b"]),
               "q4": n(quant_max="Q4"), "p8": n(params_max=9), "d5": n(disk_max_gb=5), "s100": n(speed_min=100),
               "c10": n(cold_load_max_s=10), "kv": n(kv_efficiency=40)}
    ctx.check(f"fits at 131,072 keeps only fits and tight, got {[r['fit']['level'] for r in wide['rows']][:8]}",
              all(r["fit"]["level"] in ("fits", "tight") for r in wide["rows"]) and len(wide["rows"]) < len(got["fits"]))
    ctx.check(f"fully on the GPU is a subset of fits, got {len(got['gpu'])} of {len(got['fits'])}", set(got["gpu"]) <= set(got["fits"]))
    ctx.check(f"co-resides with the resident 9B drops the biggest, got {'qwen3-coder:30b' in got['co']}",
              "qwen3-coder:30b" not in got["co"] and "qwen3:8b" in got["co"])
    ctx.check(f"each ceiling narrows the list, got {[len(got[k]) for k in got]}",
              all(0 < len(got[k]) < len(got["all"]) for k in ("q4", "p8", "d5", "s100", "c10", "kv")))
    ctx.check(f"params <= 9 has the 8B and no 14B, got {got['p8']}", "qwen3:14b" not in got["p8"] and "qwen3:8b" in got["p8"])


@test
def test_each_supply_filter(ctx: Ctx):
    with SearchHome(card=box_card()) as h:
        s = lambda **f: h.library(search={"supply": f})["rows"]  # noqa: E731
        perm, open_, mlx, here = s(licence="permissive"), s(gated=False), s(source="mlx"), s(runs_here=True)
        supp, fresh = s(ollama_supports=True), s(fresh_within_months=3)
        allr = h.library()["rows"]
    with SearchHome(card=box_card(library="Metal")) as h:
        mac = h.library(search={"supply": {"runs_here": True, "source": "mlx"}})["rows"]
    ctx.check(f"permissive: apache / mit rows only, got {sorted({r['license'] for r in perm})}",
              perm and all(r["license"].startswith(("apache", "mit")) for r in perm))
    from halo_harness.models_library.search_filters import keep_supply
    ctx.check("not gated drops a gated hub repo; gated keeps only those",
              not keep_supply({"gated": True}, {"gated": False}, {})[0] and keep_supply({"gated": False}, {"gated": False}, {})[0]
              and not keep_supply({"gated": False}, {"gated": True}, {})[0] and len(open_) == len(allr))
    ctx.check(f"source mlx: MLX repos only, got {len(mlx)}", mlx and all(r["kind"] == "mlx" for r in mlx))
    ctx.check("runs here on a CUDA card drops every MLX row; on a Mac they stay",
              not any(r["kind"] == "mlx" for r in here) and len(mac) == len(mlx))
    ctx.check(f"Ollama supports: an architecture it may not load leaves, got {len(supp)} of {len(allr)}",
              0 < len(supp) < len(allr) and all(r["supports"] for r in supp))
    ctx.check(f"fresh within 3 months: newer rows only, got {len(fresh)}", 0 < len(fresh) < len(allr))


@test
def test_the_cost_preview_numbers(ctx: Ctx):
    with SearchHome(card=box_card(loaded=RES)) as h:
        a = _row(h.library(q="qwen3-coder"), "qwen3-coder:30b")["cost"]
        (h.state / "ollama").mkdir(exist_ok=True)
        (h.state / "ollama" / "pulls.json").write_text(json.dumps({"jobs": [{"ok": True, "speed": 100e6, "started": 1.0}]}))
        h.profile("qwen3-coder:30b", speed={"tok_s": 188.0, "cold_load_s": 31.0, "at_window": 32768})
        b = _row(h.library(q="qwen3-coder"), "qwen3-coder:30b")["cost"]
        c = _row(h.library(q="qwen3"), "qwen3:14b")["cost"]
    size = 18_556_688_481
    ctx.check(f"download and eta at the assumed 50 MB/s, got {a['download_gb']} {a['download_eta_s']} {a['line_from']}",
              abs(a["download_gb"] - round(size / 1e9, 2)) < 0.2 and abs(a["download_eta_s"] - a["download_gb"] * 1e9 / 50e6) < 5
              and a["line_from"] == "assumed 50 MB/s")
    ctx.check(f"VRAM at the window, cold load from the assumed disk, tok/s expected from 3.3B active, got {a}",
              a["vram_at_window"] > 18 * GIB and a["cold_from"].startswith("assumed") and 150 < a["tok_s_expected"] < 260
              and "3.3B active" in a["tok_from"])
    ctx.check(f"it evicts the resident 9B to fit, got {a['evicts']}", a["evicts"] == ["qwen3.5:9b"])
    ctx.check(f"measured: the last pull's speed, its probe's cold load and tok/s, got {b}",
              b["line_from"].startswith("measured 100 MB/s") and b["cold_load_s"] == 31.0 and b["tok_s_expected"] == 188.0
              and "its probe" in b["tok_from"])
    ctx.check(f"another row on this host: the measured disk and GB/s, got {c['cold_from']} {c['tok_from']}",
              c["cold_from"].startswith("measured") and "this host's probed models" in c["tok_from"])
    ctx.check(f"the one line, got {b['text']!r}", "GiB at 32,768" in b["text"] and "188 tok/s" in b["text"])


@test
def test_the_labelling_and_the_cli(ctx: Ctx):
    with SearchHome(card=box_card(loaded=RES)) as h:
        h.profile("qwen3:8b", tools="no", agentic_ready=False, sits="bulk worker · non-agentic")
        h.library(q="qwen3")  # the panel has read the card (its KV type) before the crash
        h.events({"kind": "loaded", "severity": "info", "say": "", "evidence": "", "at": None, "model": "qwen3:14b",
                  "data": {"size": 12 * GIB, "size_vram": 9 * GIB, "context_length": 65536}},
                 {"kind": "gpu-memory", "severity": "error", "say": "", "evidence": "CUDA error: an illegal memory access was encountered",
                  "at": None, "model": None, "data": {}})
        ans = h.library(q="qwen3", search={"exclude_crashed": True, "needs": {"tools": "expected"}})
        plain = h.library(q="qwen3")
        out = io.StringIO()
        from halo_harness.catalog_cli import cmd_models
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            rc = cmd_models(["browse", "--host", "box", "--preset", "coder", "--need", "tools=declared", "--exclude-crashed",
                             "--why", "--source", "ollama", "qwen3-coder"])
    r = _row(plain, "qwen3-coder:30b")
    glyphs = {c["cap"]: c["glyph"] for c in r["chips"]}
    ctx.check(f"chips carry their truth glyph, got {glyphs}", glyphs.get("tools") == "◇" and glyphs.get("coder") == "≈"
              and glyphs.get("agentic-ready") == "?")
    ctx.check(f"not probed: fits yes, role-ready not yet (download and verify), got {r['verdicts']}",
              r["verdicts"]["fits"]["word"].startswith("yes") and r["verdicts"]["role_ready"]["ok"] is None
              and "download and verify" in r["verdicts"]["role_ready"]["why"])
    n8 = _row(plain, "qwen3:8b")
    ctx.check(f"probed with no tools: role-ready no (no tool calls), got {n8['verdicts']['role_ready']}", n8["verdicts"]["role_ready"]["ok"] is False)
    crashed = _row(ans, "qwen3:14b")
    ctx.check(f"the crashed model is greyed with the reason and last, got {crashed and crashed['crashed']}",
              crashed and crashed["greyed"] and "CUDA error (an illegal memory access) after a spill at 65,536 with q8_0 KV"
              in crashed["crashed"]["line"] and _names(ans)[-1] == "qwen3:14b")
    text = out.getvalue()
    ctx.check(f"the CLI: the search line, the marks, the verdicts, the cost and the rank, got {text[:900]!r}",
              rc == 0 and "search: Coder" in text and "tools◇" in text and "role-ready:" in text and "cost:" in text and "rank:" in text)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
