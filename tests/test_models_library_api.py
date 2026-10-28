"""tests.test_models_library_api -- Halo 3.3.5.0 R2: Local -> Library's routes (studio/models_library_api.py through
studio/local_api.dispatch_local) and `halo models browse` (models_browse_cli.py), on R1's seeded state
(tests/helpers/local_api_rig.Local: hosts pc and samus on 192.0.2.x placeholders, `box` a fake Ollama on
127.0.0.1:0, their hardware cards through the panel's READERS seam) with the fixture sources
(BRIDGE_TEST_NO_BACKGROUND_NET=1: Ollama's shipped snapshot, the hub's fixtures). No real request, no model call:

1. GET local/library: the rows with their card view, fit and intent scores; the sources named; the host and window;
2. the fit badge follows the host and the window; fits=1 keeps fits and tight;
3. the filters: source, capability, family, quant, size, licence; the query words;
4. the intent order (code: a coder first; embed: embedding models only) through R1's intent_scores + rank;
5. GET local/library/<source>/<id>: an Ollama model's tags and a hub repo's files, each with its fit;
6. POST local/library/refresh and the 404 / 405 answers;
7. `halo models browse`: the rows with the fit word and the pull line, `<source>/<id>`, --intent docs, --json.
Run: python -m tests.test_models_library_api
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
ensure_default_provider_credentials()

from tests.helpers.local_api_rig import Local  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _lib(h, **q):
    status, body = h.api("GET", "local/library", query={k: str(v) for k, v in q.items()})
    assert status == 200, (status, body)
    return body


def _row(body, name):
    return next((r for r in body["rows"] if r["name"] == name), None)


@test
def test_the_library_rows_and_their_sources(ctx: Ctx):
    with Local() as h:
        body = _lib(h)
    ctx.check(f"the sources named: the snapshot and the hub's fixtures, got {body['sources']}",
              body["sources"]["ollama"].startswith("snapshot 20") and body["sources"]["hf"] == "fixtures")
    ctx.check(f"every Ollama size and every hub repo, got {body['total']}", body["total"] > 300 and len(body["rows"]) == min(body["total"], 300))
    r = _row(body, "qwen3.5:9b")
    ctx.check(f"a row: the card view, the fit, the intent scores, the pull line, got {sorted(r)[:8]}",
              r and {"card", "fit", "intent", "pull_line", "sources", "key"} <= set(r) and r["card"]["chips"]["tools"] == "tools"
              and r["pull_line"] == "ollama pull qwen3.5:9b" and "shape" not in r)
    ctx.check(f"the host is the first configured, at its window, got {body['host']} {body['window']}",
              body["host"]["name"] == "pc" and body["host"]["card"] is True and body["window"] == 32768
              and [x["name"] for x in body["hosts"]] == ["pc", "samus", "box"])
    ctx.check("the intents are R1's", [i["id"] for i in body["intents"]] == ["code", "chat", "long", "images", "embed"])


@test
def test_the_fit_badge_follows_the_host_and_the_window(ctx: Ctx):
    with Local() as h:
        small = _row(_lib(h, host="box", window=8192, q="gemma3"), "gemma3:27b")
        mid = _row(_lib(h, host="box", window=16384, q="gemma3"), "gemma3:27b")
        big = _row(_lib(h, host="box", window=131072, q="gemma3"), "gemma3:27b")
        pc = _row(_lib(h, host="pc", window=8192, q="gemma3"), "gemma3:27b")
        fits = _lib(h, host="box", window=65536, fits=1)
    ctx.check(f"box: fits, tight, no as the window grows, got {small['fit']['level']} {mid['fit']['level']} {big['fit']['level']}",
              [small["fit"]["level"], mid["fit"]["level"], big["fit"]["level"]] == ["fits", "tight", "no"])
    ctx.check(f"the numbers ride in why, got {small['fit']['why'][:90]!r}", small["fit"]["why"].startswith("weights ") and small["fit"]["numbers"]["window"] == 8192)
    ctx.check(f"pc holds 2 GiB for ComfyUI: a lower budget, got {pc['fit']['numbers']['budget']} vs {small['fit']['numbers']['budget']}",
              pc["fit"]["numbers"]["budget"] < small["fit"]["numbers"]["budget"] and pc["fit"]["numbers"]["others"] == 2 * 2 ** 30)
    levels = {r["fit"]["level"] for r in fits["rows"]}
    ctx.check(f"fits=1 keeps what fits or is tight, got {levels} {fits['total']}", levels <= {"fits", "tight"} and fits["total"] > 20)


@test
def test_the_filters(ctx: Ctx):
    with Local() as h:
        hf = _lib(h, source="hf")
        emb = _lib(h, cap="embedding", source="ollama")
        fam = _lib(h, family="qwen", source="ollama")
        q8 = _lib(h, quant="q8", source="hf")
        small = _lib(h, max_gb=2, source="ollama")
        lic = _lib(h, license="apache")
        words = _lib(h, q="coder", source="ollama")
    ctx.check(f"source=hf: hub repos only, GGUF and MLX, got {hf['sources']} {sorted({r['kind'] for r in hf['rows']})}",
              list(hf["sources"]) == ["hf"] and {r["source"] for r in hf["rows"]} == {"hf"} and {r["kind"] for r in hf["rows"]} == {"gguf", "mlx"})
    ctx.check(f"cap=embedding: embedding models only, got {[r['name'] for r in emb['rows']][:4]}",
              emb["rows"] and all("embedding" in r["capabilities"] for r in emb["rows"]))
    ctx.check("family=qwen", fam["rows"] and all("qwen" in (r["family"] + r["id"]).lower() for r in fam["rows"]))
    ctx.check(f"quant=q8: the 8-bit MLX repos, got {[r['name'] for r in q8['rows']]}", q8["total"] == 0 or all("q8" in r["quant"].lower() for r in q8["rows"]))
    ctx.check(f"max_gb=2: nothing over 2 GB, got {max(r['size_bytes'] for r in small['rows'])}",
              small["rows"] and all(r["size_bytes"] <= 2e9 for r in small["rows"]))
    ctx.check("license=apache: only rows whose licence says so", lic["rows"] and all("apache" in r["license"] for r in lic["rows"]))
    ctx.check(f"the query's words, got {[r['name'] for r in words['rows']][:4]}",
              words["rows"] and all("coder" in (r["id"] + r["description"]).lower() for r in words["rows"]))


@test
def test_the_intent_order(ctx: Ctx):
    with Local() as h:
        code = _lib(h, host="box", intent="code", source="ollama")
        embed = _lib(h, host="box", intent="embed")
    first = code["rows"][0]
    scores = [r["intent"]["code"] for r in code["rows"]]
    ctx.check(f"code: a coder that fits first, scores falling, got {first['name']} {first['card']['purpose']} {scores[:3]}",
              first["card"]["purpose"] == "coder" and first["fit"]["level"] == "fits" and scores == sorted(scores, reverse=True)
              and code["intent"] == "code")
    ctx.check(f"embed: embedding models only, got {[r['name'] for r in embed['rows']][:5]}",
              embed["rows"] and all(r["card"]["purpose"] == "embedding" for r in embed["rows"]))


@test
def test_one_models_tags_and_one_repos_files(ctx: Ctx):
    with Local() as h:
        s, tags = h.api("GET", "local/library/ollama/qwen3.5:9b", query={"host": "box", "window": "32768"})
        s2, files = h.api("GET", "local/library/hf/unsloth/Qwen3.8-27B-GGUF", query={"host": "box"})
        s3, gone = h.api("GET", "local/library/hf/someone/not-there")
    names = [r["tag_or_file"] for r in tags["rows"]]
    ctx.check(f"the Ollama model's tags, each with its fit at the window, got {s} {names[:6]} {tags['window']}",
              s == 200 and "9b" in names and "27b" in names and all(r["fit"]["level"] != "" for r in tags["rows"])
              and tags["window"] == 32768 and tags["host"] == "box")
    q4 = next(r for r in files["rows"] if r["quant"] == "UD-Q4_K_M")
    ctx.check(f"the repo's files: one per quant with its fit, the shape from config.json, got {s2} {len(files['rows'])} {q4['fit']['level']}",
              s2 == 200 and len(files["rows"]) == 25 and q4["fit"]["shape_source"] == "the repo's config.json"
              and files["about"]["license"] == "apache-2.0" and q4["pull_line"].endswith(":UD-Q4_K_M"))
    ctx.check(f"a repo the hub does not answer for: no rows, and why, got {s3} {gone['note']!r}", s3 == 200 and gone["rows"] == [] and gone["note"])


@test
def test_refresh_and_the_wrong_methods(ctx: Ctx):
    with Local() as h:
        _lib(h)
        s, body = h.api("POST", "local/library/refresh")
        s2, _ = h.api("POST", "local/library")
        s3, _ = h.api("POST", "local/library/ollama/qwen3.5")
        s4, _ = h.api("GET", "local/library/elsewhere/x")
        s5, _ = h.api("GET", "local/models")
    ctx.check(f"refresh drops the cache, got {s} {body}", s == 200 and body["ok"] is True)
    ctx.check(f"405 for a POST to a GET route, 404 for an unknown source; R1's routes still answer, got {s2} {s3} {s4} {s5}",
              s2 == 405 and s3 == 405 and s4 == 404 and s5 == 200)


def _browse(*argv):
    from halo_harness.catalog_cli import cmd_models
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = cmd_models(["browse", *argv])
    return rc, out.getvalue(), err.getvalue()


@test
def test_halo_models_browse(ctx: Ctx):
    with Local():
        rc, text, _ = _browse("--host", "box", "--window", "8192", "--source", "ollama", "gemma3")
        rc2, tags, _ = _browse("ollama/qwen3-coder", "--host", "box")
        rc3, docs, _ = _browse("--intent", "docs", "--source", "ollama", "--host", "box", "--limit", "3")
        rc4, _o, bad = _browse("--intent", "poetry")
        rc5, js, _ = _browse("--json", "--source", "hf", "qwen3.8")
    lines = text.splitlines()
    row = next((ln for ln in lines if "gemma3:27b" in ln), "")
    ctx.check(f"the head names the sources and the host, got {lines[0]!r}",
              rc == 0 and lines[0].startswith("Ollama: snapshot 20") and "fit on box at 8,192" in lines[0])
    ctx.check(f"a row: the fit word, the size, the chips, the pull line, got {row!r}",
              row.strip().startswith("fits") and "17.4 GB" in row and row.endswith("->  ollama pull gemma3:27b") and "vision" in row)
    ctx.check(f"the count line, got {lines[-1]!r}", lines[-1].split(" ")[1].startswith("rows") and "halo models browse ollama/<model>" in lines[-1])
    ctx.check(f"<source>/<id>: the model's tags, got {tags.splitlines()[:2]}",
              rc2 == 0 and tags.startswith("ollama/qwen3-coder: ") and "ollama pull qwen3-coder:30b" in tags)
    drows = [ln for ln in docs.splitlines() if "->  ollama pull" in ln]
    ctx.check(f"--intent docs is long documents: what holds a long window here first, got {drows}",
              rc3 == 0 and len(drows) == 3 and all(ln.strip().split()[0] in ("fits", "tight") for ln in drows))
    ctx.check(f"a wrong intent says which ones there are, got {rc4} {bad!r}", rc4 == 2 and "code, chat, docs, images or embed" in bad)
    data = json.loads(js)
    ctx.check(f"--json is the route's answer, got {sorted(data)[:5]}", rc5 == 0 and data["sources"] == {"hf": "fixtures"} and data["rows"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
