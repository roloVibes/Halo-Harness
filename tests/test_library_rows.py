"""tests.test_library_rows -- Halo 3.3.5.0 R2: a library row, its card and its fit badge
(models_library/row_builders.py, rows.py), from the shipped snapshot and the hub fixtures (tests/fixtures/library):

1. card_for_row: a coder (qwen3-coder:30b), a vision model (gemma3:27b), an embedding model (nomic-embed-text), a
   thinking model (deepseek-r1:8b), a Hugging Face GGUF file (unsloth's Qwen3.8-27B Q4_K_M) and an MLX repo; the
   window's source is "library" and every `how` line says "once pulled";
2. fit_for_row on R1's fixture host card (tests/helpers/local_seed.box_card: a 24 GB card, f16 KV, 64 GiB RAM) at
   three windows -- fits at 8,192, tight at 16,384, no at 131,072 -- with the numbers (weights + KV against the free
   memory) in `why`; the newest resources sample lowers the budget; no host card says so; a repo's config.json makes
   the shape exact;
3. the pull lines and the row's sources.
Run: python -m tests.test_library_rows
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
ensure_default_provider_credentials()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.steward_seed import Home  # noqa: E402

test, TESTS = new_registry()
FIX = Path(__file__).resolve().parent / "fixtures" / "library"
GIB = 2 ** 30


def _ollama(name: str, size: str) -> dict:
    from halo_harness.models_library import snapshot
    from halo_harness.models_library.row_builders import ollama_row
    return ollama_row(snapshot.entry_of(name), size, snapshot.tags_of(name), snapshot.manifest_of(name, size), "the snapshot")


def _hf_repo(name: str) -> dict:
    from halo_harness.models_library.hf_hub import parse_repo
    return parse_repo((FIX / f"hf_repo_{name}.json").read_text(encoding="utf-8"))


def _box() -> dict:
    from tests.helpers.local_seed import box_card
    return box_card(SimpleNamespace(ps_snapshot=lambda: {"models": []}))


@test
def test_cards_for_a_coder_a_vision_an_embedding_and_a_thinking_model(ctx: Ctx):
    from halo_harness.models_library.rows import card_for_row
    with Home(hosts=[]):
        coder, vis = card_for_row(_ollama("qwen3-coder", "30b")), card_for_row(_ollama("gemma3", "27b"))
        emb, think = card_for_row(_ollama("nomic-embed-text", "latest")), card_for_row(_ollama("deepseek-r1", "8b"))
    ctx.check(f"the coder: purpose coder, tools from the chips, no thinking, got {coder['purpose']} {coder['tools']} {coder['thinks']}",
              coder["purpose"] == "coder" and coder["tools"] == "declared" and coder["thinks"] == "no"
              and coder["sources"]["tools"] == "the library's chips: tools" and coder["fit_for"]["coder"] is True)
    ctx.check(f"the vision model sees and is the eyes, got {vis['vision']} {vis['fit_for']['eyes']} {vis['sources']['vision']}",
              vis["vision"] is True and vis["fit_for"]["eyes"] is True and "chips" in vis["sources"]["vision"])
    ctx.check(f"the embedding model holds no role, got {emb['purpose']} {emb['embedding_only']} {emb['fit_for']}",
              emb["purpose"] == "embedding" and emb["embedding_only"] and not any(emb["fit_for"].values())
              and emb["how"][0].startswith("embeddings only"))
    ctx.check(f"the thinking model: reasoning, thinks by default, got {think['purpose']} {think['thinks']}",
              think["purpose"] == "reasoning" and think["thinks"] == "default-on")
    ctx.check(f"the window is the listing's context, source library, got {coder['window']}",
              coder["window"]["tokens"] == 262144 and coder["window"]["source"] == "library")
    ctx.check(f"every how line says once pulled, got {coder['how']}", coder["how"] and all(h.endswith("(once pulled)") for h in coder["how"]))
    ctx.check("the purpose's source is the library's chips, not /api/show", "/api/show" not in str(coder["sources"]) + str(think["sources"]))


@test
def test_cards_for_a_hub_gguf_file_and_an_mlx_repo(ctx: Ctx):
    from halo_harness.models_library.hf_hub import shape_from_config
    from halo_harness.models_library.row_builders import hf_file_row
    from halo_harness.models_library.rows import card_for_row
    repo = _hf_repo("unsloth--Qwen3.8-27B-GGUF")
    q4 = next(f for f in repo["files"] if f["quant"] == "UD-Q4_K_M")
    shape = shape_from_config((FIX / "hf_config_unsloth--Qwen3.8-27B-GGUF.json").read_text(encoding="utf-8"))
    row = hf_file_row(repo, q4, shape)
    mlx_repo = _hf_repo("lmstudio-community--Qwen3.8-27B-MLX-4bit")
    mlx = hf_file_row(mlx_repo, mlx_repo["files"][0])
    with Home(hosts=[]):
        c, m = card_for_row(row), card_for_row(mlx)
    ctx.check(f"the GGUF file: its bytes, the projector, the quant, the pull line, got {row['size_bytes']} {row['quant']} {row['pull_line']}",
              row["weights_bytes"] == q4["size"] and row["projector_bytes"] == 927_607_488 and row["quant"] == "UD-Q4_K_M"
              and row["pull_line"] == "ollama pull hf.co/unsloth/Qwen3.8-27B-GGUF:UD-Q4_K_M"
              and row["alt_line"] == "halo local download unsloth/Qwen3.8-27B-GGUF Qwen3.8-27B-UD-Q4_K_M.gguf")
    ctx.check(f"its card: runs through Ollama, tools unknown until pulled, the repo's context, got {c['kind']} {c['tools']} {c['window']}",
              c["kind"] == "ollama" and c["tools"] == "unknown" and c["window"]["tokens"] == 262144 and c["params"] == 27.321)
    ctx.check(f"the MLX repo: kind mlx, OpenAI dialect, 4bit, its download line, got {m['kind']} {m['dialect']} {mlx['quant']} {mlx['pull_line']}",
              m["kind"] == "mlx" and m["dialect"] == "openai" and mlx["quant"] == "4bit"
              and mlx["pull_line"] == "halo local download lmstudio-community/Qwen3.8-27B-MLX-4bit" and m["vision"] is True)


@test
def test_the_fit_badge_at_three_windows_with_its_numbers(ctx: Ctx):
    from halo_harness.models_library.rows import fit_for_row
    with Home(hosts=[]):
        row = _ollama("gemma3", "27b")
        hc = _box()
        got = {w: fit_for_row(row, hc, w, host_name="box") for w in (8192, 16384, 131072)}
    levels = [got[w]["level"] for w in (8192, 16384, 131072)]
    ctx.check(f"fits, tight, no, got {levels}", levels == ["fits", "tight", "no"])
    n8, n16 = got[8192]["numbers"], got[16384]["numbers"]
    ctx.check(f"the weights are the manifest's, the KV doubles with the window, got {n8} {n16}",
              n8["weights"] == row["weights_bytes"] and n16["kv"] == 2 * n8["kv"] and n8["budget"] == 24564 * 2 ** 20
              and n8["window"] == 8192 and n8["kv_cache"] == "f16")
    why = got[8192]["why"]
    ctx.check(f"why says the numbers, got {why!r}", why.startswith(f"weights {n8['weights'] / GIB:.1f} GiB + KV ")
              and "of 24.0 GiB free" in why and "an estimate until pulled" in why)
    ctx.check(f"no: what it needs against the card and the RAM, got {got[131072]['why'][-200:]!r}",
              "the card has 24.0 GiB and the RAM 64.0 GiB" in got[131072]["why"])
    ctx.check(f"the shape's source is named, got {got[8192]['shape_source']!r}", got[8192]["shape_source"].startswith("the published shape of gemma3:27b"))


@test
def test_the_newest_sample_no_card_and_an_exact_shape(ctx: Ctx):
    from halo_harness.models_library.hf_hub import shape_from_config
    from halo_harness.models_library.row_builders import hf_file_row
    from halo_harness.models_library.rows import fit_for_row
    from halo_harness.ollama_steward.resources import STORE
    with Home(hosts=[]):
        row = _ollama("qwen3-coder", "30b")
        hc = {**_box(), "read_at": "2026-01-01T00:00:00Z"}
        before = fit_for_row(row, hc, 32768, host_name="box")
        STORE.add({"host": "box", "t": time.time(), "others": 6 * GIB, "sources": {}})
        try:
            after = fit_for_row(row, hc, 32768, host_name="box")
        finally:
            STORE.clear()
        nocard = fit_for_row(row, None, 32768, host_name="box")
        repo = _hf_repo("unsloth--Qwen3.8-27B-GGUF")
        shape = shape_from_config((FIX / "hf_config_unsloth--Qwen3.8-27B-GGUF.json").read_text(encoding="utf-8"))
        exact = fit_for_row(hf_file_row(repo, next(f for f in repo["files"] if f["quant"] == "Q4_0"), shape), _box(), 32768)
    ctx.check(f"a ComfyUI holding 6 GiB: the budget drops and the badge says so, got {before['level']} -> {after['level']} {after['numbers']}",
              before["level"] == "fits" and after["level"] in ("tight", "spill") and after["numbers"]["others"] == 6 * GIB
              and after["numbers"]["others_from"] == "the newest resources sample" and "newest resources sample" in after["why"])
    ctx.check(f"no hardware card: unknown, and why, got {nocard['level']} {nocard['why']!r}",
              nocard["level"] == "unknown" and "no hardware card read for box" in nocard["why"])
    ctx.check(f"the repo's config.json: the shape is exact, got {exact['shape_source']} {exact['estimate']} {exact['level']}",
              exact["shape_source"] == "the repo's config.json" and exact["estimate"] is False and exact["level"] in ("fits", "tight"))


@test
def test_pull_lines_and_sources(ctx: Ctx):
    from halo_harness.models_library.hf_hub import parse_search
    from halo_harness.models_library.row_builders import hf_repo_row
    with Home(hosts=[]):
        r = _ollama("qwen3.5", "9b")
        latest = _ollama("nomic-embed-text", "latest")
        hits = parse_search((FIX / "hf_search_gguf.json").read_text(encoding="utf-8"), "gguf")
        hub = hf_repo_row(next(x for x in hits if x["id"] == "unsloth/Qwen3.8-27B-GGUF"))
    ctx.check(f"an Ollama row: its pull line, key and the manifest's bytes, got {r['pull_line']} {r['key']} {r['sources']['size_bytes']!r}",
              r["pull_line"] == "ollama pull qwen3.5:9b" and r["key"] == "ollama/qwen3.5:9b"
              and "model layer" in r["sources"]["size_bytes"] and r["capabilities"] == ["vision", "tools", "thinking"])
    ctx.check(f"a model with no size chip uses latest, got {latest['pull_line']}", latest["pull_line"] == "ollama pull nomic-embed-text:latest")
    ctx.check(f"a hub repo: an estimate until it is opened, got {hub['size_bytes']} {hub['sources']['size_bytes']!r} {hub['pull_line']}",
              hub["estimate"] and hub["params"] == 27.0 and "estimate" in hub["sources"]["size_bytes"]
              and hub["pull_line"] == "ollama pull hf.co/unsloth/Qwen3.8-27B-GGUF" and hub["license"] == "apache-2.0")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
