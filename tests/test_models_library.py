"""tests.test_models_library -- Halo 3.3.5.0 R2: the library's sources (halo_harness/models_library/) on the real
pages and API answers saved under tests/fixtures/library (ollama.com/library, three tags pages, two registry
manifests and a config blob, the Hugging Face Hub's GGUF and MLX searches, three repos, a config.json), and the
shipped snapshot. A fake site (cache.SEAMS["fetch"]) stands in for the network; no real request, a scratch home:

1. the catalog parser: names, descriptions, the capability, cloud and size chips, pulls, tags, updated;
2. the tags parser: size (the smaller of a range), context, input, the latest mark;
3. a markup change raises ShapeChanged and the source answers from the snapshot, saying why;
4. the registry manifest (the weights' and the projector's bytes) and its config blob (family, size, quant);
5. the hub API: the search rows, a GGUF repo as one file per quant (shards summed, projector apart), an MLX repo,
   a gated repo (the token sent for it only), config.json as a shape;
6. the snapshot's shape; 7. the cache's ages and --refresh; 8. BRIDGE_TEST_NO_BACKGROUND_NET: fixtures only.
Run: python -m tests.test_models_library
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
ensure_default_provider_credentials()

from tests.helpers.library_site import FIX, Site  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.steward_seed import Home  # noqa: E402

test, TESTS = new_registry()


def _text(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


@test
def test_the_catalog_parser_on_the_real_page(ctx: Ctx):
    from halo_harness.models_library.ollama_library import parse_catalog
    rows = parse_catalog(_text("ollama_library.html"))
    by = {r["name"]: r for r in rows}
    ctx.check(f"24 models in the fixture, most pulled first, got {len(rows)} {[r['name'] for r in rows[:3]]}",
              len(rows) == 24 and [r["name"] for r in rows[:3]] == ["llama3.1", "deepseek-r1", "nomic-embed-text"])
    l3 = by["llama3.1"]
    ctx.check(f"llama3.1: its line, chips, sizes, pulls, tags, updated, got {l3}",
              l3["description"].startswith("Llama 3.1 is a new state-of-the-art model") and l3["capabilities"] == ["tools"]
              and l3["sizes"] == ["8b", "70b", "405b"] and l3["pulls_n"] == 120_700_000 and l3["tags_count"] == 93
              and l3["updated"] == "1 year ago" and l3["updated_at"].endswith("UTC") and l3["cloud"] is False)
    ctx.check(f"deepseek-r1 thinks and calls tools, got {by['deepseek-r1']['capabilities']}",
              by["deepseek-r1"]["capabilities"] == ["tools", "thinking"])
    ctx.check(f"an embedding model with no size chip, got {by['nomic-embed-text']}",
              by["nomic-embed-text"]["capabilities"] == ["embedding"] and by["nomic-embed-text"]["sizes"] == [])
    g4 = by["gemma4"]
    ctx.check(f"the cloud chip apart from the capabilities, got {g4['capabilities']} {g4['cloud']} {g4['sizes']}",
              g4["cloud"] is True and "cloud" not in g4["capabilities"] and "vision" in g4["capabilities"] and "e4b" in g4["sizes"])


@test
def test_the_tags_parser(ctx: Ctx):
    from halo_harness.models_library.ollama_library import context_of, parse_tags, size_of
    tags = {t["tag"]: t for t in parse_tags(_text("ollama_tags_qwen3.5.html"), "qwen3.5")}
    t9 = tags["9b"]
    ctx.check(f"qwen3.5:9b: the smaller of the size range, 256K, text and image, the latest mark, got {t9}",
              t9["name"] == "qwen3.5:9b" and t9["size_text"] == "6.6GB - 7.6GB" and t9["size_bytes"] == 6_600_000_000
              and t9["context"] == 262144 and t9["input"] == ["Text", "Image"] and t9["latest"] is True
              and len(t9["digest"]) == 12 and t9["updated"])
    ctx.check(f"18 tags in the fixture, the quant variants among them, got {len(tags)}",
              len(tags) == 18 and "0.8b-q8_0" in tags and tags["latest"]["latest"] is False)
    coder = [t["tag"] for t in parse_tags(_text("ollama_tags_qwen3-coder.html"), "qwen3-coder")]
    ctx.check(f"qwen3-coder's tags, got {coder}", coder[:3] == ["latest", "30b", "480b"] and "30b-a3b-q8_0" in coder)
    emb = parse_tags(_text("ollama_tags_nomic-embed-text.html"), "nomic-embed-text")
    ctx.check(f"nomic-embed-text: 274MB, 2K, text, got {emb[0]}", emb[0]["size_bytes"] == 274_000_000 and emb[0]["context"] == 2048)
    ctx.check("the units", size_of("17GB - 20GB") == 17_000_000_000 and size_of("812MB") == 812_000_000
              and context_of("128K") == 131072 and context_of("1M") == 1048576 and size_of("") is None)


@test
def test_a_markup_change_fails_here_and_the_page_falls_back_to_the_snapshot(ctx: Ctx):
    from halo_harness.models_library import ollama_library as O
    from halo_harness.models_library import snapshot
    moved = _text("ollama_library.html").replace('<div  id="repo">', '<div id="models">')
    try:
        O.parse_catalog(moved)
        raised = False
    except O.ShapeChanged:
        raised = True
    ctx.check("ShapeChanged when the list moved", raised)
    with Home(hosts=[]) as h, Site({"ollama.com/library": moved}) as site:
        got = O.catalog(h.state)
    ctx.check(f"the source answers from the snapshot and says why, got {got['source']!r} {got['note']!r}",
              got["source"] == f"snapshot {snapshot.taken()}" and "no <div id=\"repo\">" in got["note"]
              and len(got["models"]) >= 150 and len(site.got) == 1)
    with Home(hosts=[]) as h, Site({"/tags": "<html>nothing</html>"}):
        t = O.tags(h.state, "qwen3.5")
    ctx.check(f"a tags page that moved: the snapshot's tags, got {t['source']} {len(t['tags'])}",
              t["source"].startswith("snapshot") and any(x["tag"] == "9b" for x in t["tags"]))


@test
def test_the_registry_manifest_and_its_config(ctx: Ctx):
    from halo_harness.models_library import ollama_registry as R
    m = R.parse_manifest(_text("registry_manifest_qwen3.5_9b.json"))
    ctx.check(f"the weights and the projector apart, got {m['weights']} {m['projector']} {[x['type'] for x in m['layers']]}",
              m["weights"] == 5_629_109_120 and m["projector"] == 921_704_832 and m["config_digest"].startswith("sha256:")
              and [x["type"] for x in m["layers"]] == ["projector", "model", "template", "license", "params"])
    c = R.parse_config(_text("registry_config_qwen3.5_9b.json"))
    ctx.check(f"the config blob: family, size, quant, got {c}", c["family"] == "qwen35" and c["params"] == 9.0 and c["quant"] == "Q4_K_M")
    coder = R.parse_manifest(_text("registry_manifest_qwen3-coder_30b.json"))
    ctx.check(f"a text model: no projector, got {coder['weights']} {coder['projector']}", coder["weights"] == 18_556_688_736 and coder["projector"] == 0)
    with Home(hosts=[]) as h, Site({"/manifests/9b": "registry_manifest_qwen3.5_9b.json", "/blobs/": "registry_config_qwen3.5_9b.json"}) as site:
        got = R.manifest(h.state, "qwen3.5", "9b")
        again = R.manifest(h.state, "qwen3.5", "9b")
    ctx.check(f"manifest(): the bytes and the config, read once (then the cache), got {got} {len(site.got)}",
              got["weights"] == 5_629_109_120 and got["quant"] == "Q4_K_M" and got["source"] == "registry.ollama.ai manifest"
              and again["weights"] == got["weights"] and len(site.got) == 2
              and site.got[0][1].get("Accept", "").startswith("application/vnd.docker.distribution.manifest.v2"))


@test
def test_the_hub_api_parsers_and_the_token_for_a_gated_repo(ctx: Ctx):
    from halo_harness.models_library import hf_hub as H
    s = H.parse_search(_text("hf_search_gguf.json"), "gguf")
    ctx.check(f"the search rows with their licence and gated flag, got {[(r['id'], r['license']) for r in s[:2]]}",
              len(s) == 14 and s[1]["id"] == "unsloth/Qwen3.8-27B-GGUF" and s[1]["license"] == "apache-2.0"
              and s[1]["downloads"] > 1_000_000 and s[1]["base_model"] == "Qwen/Qwen3.8-27B")
    r = H.parse_repo(_text("hf_repo_unsloth--Qwen3.8-27B-GGUF.json"))
    files = {f["quant"]: f for f in r["files"]}
    ctx.check(f"a GGUF repo: one file per quant, shards summed, the projector and the imatrix apart, got {len(r['files'])}",
              len(r["files"]) == 25 and files["BF16"]["parts"] == 2 and files["BF16"]["size"] == 49_986_159_616 + 4_671_576_000
              and files["Q8_0"]["size"] == 29_047_086_048 and not any("mmproj" in f["file"] or "imatrix" in f["file"]
                                                                       or "mtp" in f["file"].lower() for f in r["files"])
              and r["projector"] == 927_607_488 and r["context"] == 262144 and r["arch"] == "qwen35" and r["gated"] is False)
    mlx = H.parse_repo(_text("hf_repo_lmstudio-community--Qwen3.8-27B-MLX-4bit.json"))
    ctx.check(f"an MLX repo: its safetensors as one, 4bit, got {mlx['kind']} {mlx['files']}",
              mlx["kind"] == "mlx" and len(mlx["files"]) == 1 and mlx["files"][0]["parts"] == 3 and mlx["files"][0]["quant"] == "4bit")
    gated = H.parse_repo(_text("hf_repo_google--gemma-3-27b-it-qat-q4_0-gguf.json"))
    ctx.check(f"a gated repo: manual, its licence, got {gated['gated']} {gated['license']}", gated["gated"] == "manual" and gated["license"] == "gemma")
    shape = H.shape_from_config(_text("hf_config_unsloth--Qwen3.8-27B-GGUF.json"))
    ctx.check(f"config.json as a shape (text_config folded in), got {shape}",
              shape.get("qwen3_5.block_count") == 64 and shape.get("qwen3_5.attention.head_count_kv") == 4
              and shape.get("qwen3_5.attention.key_length") == 256 and shape.get("qwen3_5.full_attention_interval") == 4)
    saved = os.environ.get("HF_TOKEN")
    os.environ["HF_TOKEN"] = "hf_fixture_not_a_real_token"
    try:
        with Home(hosts=[]) as h, Site({"gemma-3-27b-it-qat-q4_0-gguf?blobs": "hf_repo_google--gemma-3-27b-it-qat-q4_0-gguf.json",
                                        "unsloth/Qwen3.8-27B-GGUF?blobs": "hf_repo_unsloth--Qwen3.8-27B-GGUF.json"}) as site:
            H.repo(h.state, "unsloth/Qwen3.8-27B-GGUF")
            H.repo(h.state, "google/gemma-3-27b-it-qat-q4_0-gguf", gated="manual")
    finally:
        os.environ.pop("HF_TOKEN", None) if saved is None else os.environ.__setitem__("HF_TOKEN", saved)
    auth = [bool(hd.get("Authorization")) for _u, hd in site.got]
    ctx.check(f"the token goes with the gated repo's request only, got {auth}", auth == [False, True])
    ctx.check("search_url: the documented query and the expand fields",
              H.search_url("qwen", "mlx").startswith("https://huggingface.co/api/models?filter=mlx&search=qwen&sort=downloads&limit=50")
              and "expand%5B%5D=gated" in H.search_url("qwen", "mlx"))


@test
def test_the_snapshot_shape(ctx: Ctx):
    from halo_harness.models_library import snapshot
    data = json.loads(snapshot.FILE.read_text(encoding="utf-8"))
    names = [m["name"] for m in data["models"]]
    ctx.check(f"dated, about 150 models, got {data.get('taken')} {len(names)}",
              len(data["taken"]) == 10 and isinstance(data["taken_at"], int) and 140 <= len(names) <= 160)
    ctx.check("the most pulled ones are there", all(n in names for n in ("llama3.1", "qwen3.5", "nomic-embed-text", "qwen3-coder", "gemma3")))
    bad = [(m["name"], t.get("tag")) for m in data["models"] for t in m["tags"]
           if not isinstance(t.get("size_bytes"), int) or not t.get("tag") or not isinstance(t.get("input"), list)]
    ctx.check(f"every tag has its name, its bytes and its input, got {bad[:5]}", not bad)
    m9 = snapshot.manifest_of("qwen3.5", "9b")
    ctx.check(f"a size chip's manifest: weights, projector, family, quant, got {m9}",
              m9 and m9["weights"] > 5e9 and m9["projector"] > 0 and m9["family"] == "qwen35" and m9["quant"])
    ctx.check(f"it stays small enough to ship, got {snapshot.FILE.stat().st_size:,} bytes", snapshot.FILE.stat().st_size < 700_000)


@test
def test_the_cache_ages_and_refresh(ctx: Ctx):
    from halo_harness.models_library import cache, hf_hub, ollama_library
    with Home(hosts=[]) as h, Site({"ollama.com/library": "ollama_library.html", "filter=gguf": "hf_search_gguf.json"}) as site:
        a = ollama_library.catalog(h.state)
        b = ollama_library.catalog(h.state)
        c = ollama_library.catalog(h.state, refresh=True)
        ctx.check(f"the catalog: live, then the cache, then --refresh reads again, got {a['source']} {b['note']!r} {len(site.got)}",
                  a["source"] == "live" and b["note"] == "from the cache" and c["note"] == "" and len(site.got) == 2)
        ctx.check(f"kept in <state>/cache/models-library.json, got {cache.path(h.state)}",
                  cache.path(h.state) == h.state / "cache" / "models-library.json" and cache.path(h.state).is_file())
        hf_hub.search(h.state, "qwen", "gguf")
        n = len(site.got)
        hf_hub.search(h.state, "qwen", "gguf")
        ctx.check("a search within the hour: the cache", len(site.got) == n)
        entry = json.loads(cache.path(h.state).read_text(encoding="utf-8"))
        entry["hf:search:gguf:qwen"]["at"] = time.time() - cache.SEARCH_TTL_S - 5
        entry["ollama:catalog"]["at"] = time.time() - cache.CATALOG_TTL_S + 60
        cache.path(h.state).write_text(json.dumps(entry), encoding="utf-8")
        hf_hub.search(h.state, "qwen", "gguf")
        ollama_library.catalog(h.state)
        ctx.check(f"a search an hour old is read again; a catalog under a day old is not, got {len(site.got) - n}", len(site.got) - n == 1)
        ctx.check("clear() drops the file", cache.clear(h.state) and not cache.path(h.state).exists())
        ctx.check("the ages", cache.CATALOG_TTL_S == 86400 and cache.SEARCH_TTL_S == 3600)


@test
def test_no_background_net_serves_fixtures_and_the_snapshot_only(ctx: Ctx):
    from halo_harness.models_library import hf_hub, ollama_library, ollama_registry
    from halo_harness.providers import http as HTTP
    opened = []
    real = HTTP.urlopen_tls
    HTTP.urlopen_tls = lambda *a, **k: opened.append(a) or (_ for _ in ()).throw(AssertionError("opened"))
    try:
        with Home(hosts=[]) as h:
            ctx.check("the flag is on in the scratch home", os.environ.get("BRIDGE_TEST_NO_BACKGROUND_NET") == "1")
            cat = ollama_library.catalog(h.state, refresh=True)
            tags = ollama_library.tags(h.state, "qwen3.5")
            man = ollama_registry.manifest(h.state, "qwen3.5", "9b")
            s = hf_hub.search(h.state, "qwen3.8 27b", "gguf")
            r = hf_hub.repo(h.state, "unsloth/Qwen3.8-27B-GGUF")
            none = hf_hub.repo(h.state, "someone/not-in-the-fixtures")
            shape = hf_hub.config(h.state, "unsloth/Qwen3.8-27B-GGUF")
    finally:
        HTTP.urlopen_tls = real
    ctx.check(f"Ollama: the snapshot, and it says so, got {cat['source']} {cat['note']!r}",
              cat["source"].startswith("snapshot ") and "background network reads are off" in cat["note"])
    ctx.check(f"tags and a manifest from the snapshot, got {tags['source']} {man and man.get('source')}",
              tags["source"].startswith("snapshot") and man and man["source"].startswith("snapshot") and man["weights"])
    ctx.check(f"the hub: its fixtures, the query narrowing them, got {s['source']} {[x['id'] for x in s['repos']]}",
              s["source"] == "fixtures" and s["repos"] and all("27b" in x["id"].lower() for x in s["repos"]))
    ctx.check(f"a repo from its fixture, an unknown one None, got {r and r['source']} {none}", r and r["source"] == "fixtures" and none is None)
    ctx.check("the config's shape from its fixture", shape.get("qwen3_5.block_count") == 64)
    ctx.check(f"nothing was opened, got {opened}", opened == [])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
