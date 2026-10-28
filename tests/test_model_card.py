"""tests.test_model_card -- Halo 3.3.5.0 R0b (a): the model card
(`providers/model_card.py`, `model_card_purpose.py`, `model_card_words.py`)
from fixture `/api/show` answers and tool-call probe results
(tests/helpers/model_card_fixtures.py: a coder, a reasoning model, a vision
model, an embedding model, gpt-oss, the owner's models and their obliterated
twins), an HF local server, an mlx model and a cloud model:

1. each field and its source (the `/api/show` row, the probe's cache, the
   family rule, the name);
2. `how`: the exact way Halo calls it (think, tools, images, window and
   reserve, dialect), `models.think` named as "you set it";
3. `fit_for` and `fit_why` per role;
4. the card is kept in the catalog row and made again when the probe changes;
5. `halo models show <ref>` (a mock Ollama on 127.0.0.1:0) and `--cards`.
No real server, no model call, a scratch home per test.
Run: python -m tests.test_model_card
"""
from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
ensure_default_provider_credentials()

from tests.helpers.model_card_fixtures import CLOUD, ROWS, host_card, tags_and_show, write_probes  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.steward_seed import Home  # noqa: E402

test, TESTS = new_registry()


def _card(h, name, *, hc=None, probes=True):
    from halo_harness.providers.model_card import card_of
    if probes:
        write_probes(h.state)
    return card_of(f"ol:{name}@pc", state_dir=h.state, catalog=dict(ROWS[name]), host_card=hc)


@test
def test_a_coding_model_with_no_tool_calling_here(ctx: Ctx):
    with Home() as h:
        c = _card(h, "qwen3-coder:30b", hc=host_card())
    ctx.check(f"kind ollama on pc, got {c['kind']} {c['host']}", c["kind"] == "ollama" and c["host"] == "pc")
    ctx.check(f"purpose coder from the name, got {c['purpose']} ({c['purpose_source']})",
              c["purpose"] == "coder" and "the name" in c["purpose_source"])
    ctx.check(f"declared tools, but the probe got no call: none, got {c['tools']} ({c['sources']['tools']})",
              c["tools"] == "none" and "probe" in c["sources"]["tools"])
    ctx.check(f"does not think (/api/show), got {c['thinks']} ({c['thinks_source']})",
              c["thinks"] == "no" and "/api/show" in c["thinks_source"])
    ctx.check(f"30.5B Q4_K_M from details, got {c['params']} {c['quant']}", c["params"] == 30.5 and c["quant"] == "Q4_K_M")
    ctx.check(f"the window is bounded by the card's fit, got {c['window']}", c["window"]["source"] == "the card's fit")
    ctx.check(f"how: no think field, no tools, captions, native, got {c['how']}",
              c["how"][0].startswith("no think field") and c["how"][1].startswith("no tools: answers only")
              and c["how"][2] == "images as captions (no vision)" and c["how"][-1].startswith("dialect: native"))
    ctx.check(f"how: the window line names its source and the reserve, got {c['how'][3]}",
              c["how"][3].startswith("window ") and "(the card's fit)" in c["how"][3] and "reserve" in c["how"][3])
    ctx.check(f"not the orchestrator, the coder lane, got {c['fit_for']}",
              c["fit_for"]["orchestrator"] is False and c["fit_for"]["coder"] is True and c["fit_for"]["reviewer"] is True)
    ctx.check(f"the one reason, got {c['fit_why']}",
              c["fit_why"]["orchestrator"] == "no tool calling on this server: it can write and answer but cannot act"
              and "30.5B" in c["fit_why"]["small"] and "orchestrator" not in c["fit_why"].get("coder", ""))


@test
def test_the_owners_main_model_and_its_twins(ctx: Ctx):
    with Home() as h:
        big = _card(h, "qwen3.8:27b", hc=host_card())
        bare = _card(h, "tinyrick/Qwen3.8-27B-OBLITERATED:Q6_K", hc=host_card())
        twin = _card(h, "qwen3.8-obliterated:27b-q4-gpu", hc=host_card())
        nine = _card(h, "qwen3.5:9b", hc=host_card())
        myth = _card(h, "mythos-sec:24b", hc=host_card())
    ctx.check(f"qwen3.8:27b thinks by default, sees, a chat model that can think, got {big['thinks']} {big['vision']} "
              f"{big['purpose']} ({big['purpose_source']})",
              big["thinks"] == "default-on" and big["vision"] and big["purpose"] == "instruct" and "think" in big["purpose_source"])
    ctx.check(f"qwen3.8:27b holds every role but small, got {big['fit_for']}",
              big["fit_for"] == {"orchestrator": True, "coder": True, "reviewer": True, "small": False, "eyes": True})
    ctx.check(f"how: think default, it thinks; tools native declared, got {big['how'][:2]}",
              big["how"][0].startswith("think default: no think field sent, so it thinks")
              and big["how"][1] == "tools: native Ollama format (declared, not probed)")
    ctx.check(f"the bare upload has no tool template: tools none, no orchestrator, got {bare['tools']} {bare['fit_for']}",
              bare["tools"] == "none" and bare["fit_for"]["orchestrator"] is False and bare["quant"] == "Q6_K")
    ctx.check(f"the q4 twin passed the probe: tools probed, got {twin['tools']} {twin['how'][1]}",
              twin["tools"] == "probed" and "the probe made a call" in twin["how"][1] and twin["fit_for"]["orchestrator"])
    ctx.check(f"qwen3.5:9b is small and can orchestrate, got {nine['fit_for']} {nine['params']}",
              nine["fit_for"]["small"] and nine["fit_for"]["orchestrator"] and nine["params"] == 9.0)
    ctx.check(f"mythos-sec:24b: an instruct model with tools, got {myth['purpose']} {myth['tools']} {myth['fit_for']}",
              myth["purpose"] == "instruct" and myth["tools"] == "declared" and myth["fit_for"]["orchestrator"])


@test
def test_reasoning_vision_embedding_and_gpt_oss(ctx: Ctx):
    with Home() as h:
        r1 = _card(h, "deepseek-r1:14b")
        vl = _card(h, "qwen2.5vl:7b")
        emb = _card(h, "nomic-embed-text:latest")
        oss = _card(h, "gpt-oss:20b")
        from halo_harness.providers.effort_on import set_think_choice
        set_think_choice("ol:gpt-oss:20b@pc", "high")
        oss_high = _card(h, "gpt-oss:20b")
    ctx.check(f"deepseek-r1: reasoning by name, thinks by default, got {r1['purpose']} {r1['thinks']}",
              r1["purpose"] == "reasoning" and r1["thinks"] == "default-on" and "r1" in r1["purpose_source"])
    ctx.check(f"deepseek-r1: no coder lane (a reasoning model), got {r1['fit_why'].get('coder')}",
              r1["fit_for"]["coder"] is False and r1["fit_why"]["coder"].startswith("a reasoning model"))
    ctx.check(f"qwen2.5vl: vision by name, eyes, got {vl['purpose']} {vl['vision']} {vl['fit_for']['eyes']}",
              vl["purpose"] == "vision" and vl["vision"] and vl["fit_for"]["eyes"] and vl["how"][2] == "images sent as images")
    ctx.check(f"nomic-embed: embedding only, no role at all, got {emb['embedding_only']} {emb['fit_for']}",
              emb["embedding_only"] and not any(emb["fit_for"].values()) and emb["how"][0].startswith("embeddings only"))
    ctx.check(f"nomic-embed: 137M from details, got {emb['params']}", emb["params"] == 0.137)
    ctx.check(f"gpt-oss: reasoning, orchestrator, got {oss['purpose']} {oss['fit_for']['orchestrator']}",
              oss["purpose"] == "reasoning" and oss["fit_for"]["orchestrator"] and oss["thinks"] == "default-on")
    ctx.check(f"gpt-oss with models.think high: 'think high (you set it ...)', got {oss_high['how'][0]}",
              oss_high["how"][0].startswith("think high (you set it"))


@test
def test_an_hf_local_server_an_mlx_model_and_a_cloud_model(ctx: Ctx):
    from halo_harness.providers.model_card import card_of
    with Home() as h:
        hf = card_of("hf:local/Qwen/Qwen2.5-Coder-7B-Instruct", state_dir=h.state, catalog={"runtime": "llama-server"})
        mlx = card_of("hf:mlx/mlx-community/Qwen3-8B-4bit", state_dir=h.state)
        cloud = card_of(CLOUD["ref"], state_dir=h.state, catalog=CLOUD)
    ctx.check(f"llama-server, coder by name, tools unknown, OpenAI dialect, got {hf['kind']} {hf['purpose']} {hf['tools']}",
              hf["kind"] == "llama-server" and hf["purpose"] == "coder" and hf["tools"] == "unknown" and hf["dialect"] == "openai")
    ctx.check(f"a local server takes no effort field, got {hf['how'][0]}", hf["how"][0].startswith("no effort field"))
    ctx.check(f"the name gives size and quantization: 7B, got {hf['params']} ({hf['sources']['params']})",
              hf["params"] == 7.0 and hf["sources"]["params"] == "the name")
    ctx.check(f"mlx: kind mlx, 8B, 4bit, got {mlx['kind']} {mlx['params']} {mlx['quant']}",
              mlx["kind"] == "mlx" and mlx["params"] == 8.0 and mlx["quant"] == "4bit")
    ctx.check(f"cloud: from the catalog's modalities, instruct, thinks, sees, got {cloud['kind']} {cloud['purpose']} "
              f"{cloud['thinks']} {cloud['vision']}",
              cloud["kind"] == "cloud" and cloud["purpose"] == "instruct" and cloud["thinks"] == "yes" and cloud["vision"])
    ctx.check(f"cloud: the window from the cloud catalog, can orchestrate, got {cloud['window']} {cloud['fit_for']}",
              cloud["window"]["tokens"] == 200000 and cloud["window"]["source"] == "cloud catalog"
              and cloud["fit_for"]["orchestrator"])


@test
def test_the_card_is_kept_in_the_row_until_the_probe_changes(ctx: Ctx):
    from halo_harness.providers.model_card import card_of
    with Home() as h:
        row = dict(ROWS["qwen3.5:9b"])
        a = card_of("ol:qwen3.5:9b@pc", state_dir=h.state, catalog=row)
        b = card_of("ol:qwen3.5:9b@pc", state_dir=h.state, catalog=row)
        ctx.check(f"kept in the catalog row with card_at, got {sorted(k for k in row if k.startswith('card'))}",
                  row.get("card") is a and isinstance(row.get("card_at"), float))
        ctx.check("the second read is the kept card", a is b)
        write_probes(h.state, {"sha256:q9": False})
        c = card_of("ol:qwen3.5:9b@pc", state_dir=h.state, catalog=row)
    ctx.check(f"a new probe result makes it again: tools none, got {c['tools']}", c is not a and c["tools"] == "none")


@test
def test_the_purpose_words_and_their_rules(ctx: Ctx):
    from halo_harness.providers.model_card_purpose import params_of, purpose_of, quant_of
    cases = {"qwen2.5-coder:7b": "coder", "devstral:24b": "coder", "qwq:32b": "reasoning", "gpt-oss:120b": "reasoning",
             "llava:13b": "vision", "qwen2.5vl:7b": "vision", "bge-m3:latest": "embedding", "mxbai-embed-large": "embedding",
             "gemma3:27b-it-qat": "instruct", "mistral-small3.2:24b-instruct": "instruct"}
    got = {n: purpose_of(n)[0] for n in cases}
    ctx.check(f"the name rules, got {got}", got == cases)
    ctx.check("no word, a chat model: instruct", purpose_of("llama3.3:70b", ["completion", "tools"])[0] == "instruct")
    ctx.check("nothing known: unknown", purpose_of("mystery")[0] == "unknown")
    ctx.check("params from the name", params_of("ol:qwen3-coder:30b@lan")[0] == 30.0)
    ctx.check("quant from the tag", quant_of("qwen3:8b-q8_0")[0] == "Q8_0")


def _mock(names):
    from tests.helpers.mock_ollama import MockUpstream
    tags, show = tags_and_show(names)
    return MockUpstream(tags_response=tags, show_responses=show).start()


@test
def test_halo_models_show_and_cards(ctx: Ctx):
    from halo_harness.catalog_cli import cmd_models
    from halo_harness.providers.ollama import reset_catalog_cache
    names = ["qwen3-coder:30b", "qwen3.8:27b"]
    mock = _mock(names)
    try:
        with Home(hosts=({"name": "pc", "url": mock.base_url, "default": True},)) as h:
            reset_catalog_cache()
            write_probes(h.state)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = cmd_models(["show", "ol:qwen3-coder:30b@pc"])
            text = out.getvalue()
            from halo_harness.studio import model as M
            real = M.catalog_rows
            M.catalog_rows = lambda *_a, **_k: [{"ref": "ol:qwen3-coder:30b", "local": True},
                                                {"ref": "ol:qwen3.8:27b", "local": True}, dict(CLOUD)]
            try:
                out2 = io.StringIO()
                with contextlib.redirect_stdout(out2):
                    rc2 = cmd_models(["--cards"])
            finally:
                M.catalog_rows = real
    finally:
        mock.stop()
        reset_catalog_cache()
    ctx.check(f"show exits 0, got {rc}", rc == 0)
    ctx.check(f"the card's head and its purpose, got {text[:200]!r}",
              text.startswith("ol:qwen3-coder:30b@pc: a coding model (ollama on pc)"))
    ctx.check("the sources are named", "tools: none (the tool-call probe got no call)" in text)
    ctx.check("how Halo calls it, and the roles", "how Halo calls it:" in text and "orchestrator: no (no tool calling" in text)
    lines = out2.getvalue().splitlines()
    ctx.check(f"--cards: one line per model, local first, and a count, got {lines}",
              rc2 == 0 and len(lines) == 4 and lines[0].startswith("ol:qwen3-coder:30b: no tools")
              and lines[2].startswith(CLOUD["ref"]) and lines[3].startswith("3 models (2 local)"))
    ctx.check(f"--cards names the roles, got {lines[1]}", "roles: orchestrator" in lines[1])


if __name__ == "__main__":
    results, passed, failed, skipped = run_all(TESTS, Ctx())
    sys.exit(print_results(results, passed, failed, skipped))
