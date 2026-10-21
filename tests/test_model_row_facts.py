"""tests.test_model_row_facts -- the catalog row knows more (Halo 3.1.9.0 R1,
"what each model is good at"): `build_model_rows`, the one row source, gives
every model row the same optional keys -- modalities_in / modalities_out,
tools, reasoning {kind, efforts}, open_weights, local, measured -- filled per
provider from the caches each source already has, None when unknown:

1. OpenRouter (output_modalities kept by the probe, "file" = pdf), models.dev
   for Databricks (exact id and the vendor family), OpenAI and Experiential,
   the Hugging Face router's provider rows, the Anthropic table plus
   anthropic_caps, a decision-only endpoint without tools;
2. Ollama's `/api/show` capabilities LIST: local vision detected, tools and
   thinking, and the measured tool-call probe as `measured.tools_probe`;
3. `measured` from the gym, a learned tools rejection, telemetry's speed (from
   the state dir it is given) and the canary census;
4. `local` is `is_local_model_ref` (a Hugging Face router row is remote);
   `ModelProfile.audio` follows the catalog's audio input.
Fixture caches and a loopback mock only. Run: python -m tests.test_model_row_facts
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers import catalog_facts_seed as S  # noqa: E402

test, TESTS = new_registry()
KEYS = ("modalities_in", "modalities_out", "tools", "reasoning", "open_weights", "local", "measured")


@test
def test_every_provider_fills_the_new_keys(ctx: Ctx):
    with S.home() as (_root, state):
        rows = S.rows_by_ref(state, S.seed(state))
        models = [r for r in rows.values() if r.get("provider") != "alias"]
        ctx.check("every model row carries every new key", all(all(k in r for k in KEYS) for r in models))
        eyes = rows.get("or:v/eyes") or {}
        ctx.check(f"OpenRouter: file input reads as pdf, output and tools and reasoning stated, got {eyes}",
                  eyes.get("modalities_in") == ["text", "image", "pdf"] and eyes.get("modalities_out") == ["text"]
                  and eyes.get("tools") is True and eyes.get("reasoning") == {"kind": "openai", "efforts": []})
        plain = rows.get("or:v/plain") or {}
        ctx.check("OpenRouter: an entry that states nothing stays None, never guessed",
                  all(plain.get(k) is None for k in ("modalities_in", "modalities_out", "tools", "reasoning", "open_weights")))
        dbx = rows.get("dbx:databricks-gemini-x-pro") or {}
        ctx.check(f"Databricks (exact models.dev id): every input, tools, closed weights, the effort levels, got {dbx}",
                  dbx.get("modalities_in") == ["text", "image", "audio", "video", "pdf"] and dbx.get("tools") is True
                  and dbx.get("open_weights") is False
                  and dbx.get("reasoning") == {"kind": "native", "efforts": ["low", "medium", "high"]})
        fam = rows.get("dbx:databricks-gemini-9-flash") or {}
        ctx.check(f"Databricks (the google family row): vision, no reasoning, got {fam}",
                  fam.get("modalities_in") == ["text", "image"] and fam.get("reasoning") == {"kind": "none", "efforts": []})
        judge = rows.get("dbx:databricks-openjev-qwen35-4b") or {}
        ctx.check("a decision-only endpoint takes no tools", judge.get("tools") is False)
        oai = rows.get("oai:gpt-x") or {}
        ctx.check(f"OpenAI via models.dev: pdf in, reasoning openai with its efforts, got {oai}",
                  oai.get("modalities_in") == ["text", "image", "pdf"]
                  and oai.get("reasoning") == {"kind": "openai", "efforts": ["minimal", "low", "medium", "high"]})
        xp = rows.get("xp:claude-haiku-9") or {}
        ctx.check(f"Experiential: the gateway's tools / reasoning / efforts, the family's modalities, got {xp}",
                  xp.get("tools") is True and xp.get("reasoning") == {"kind": "native", "efforts": ["low", "high"]}
                  and xp.get("modalities_in") == ["text", "image", "pdf"] and xp.get("open_weights") is False)
        ctx.check("Experiential: a model the gateway says has no tools", (rows.get("xp:xp-text-1") or {}).get("tools") is False)
        hf = rows.get("hf:Org/Model-7B") or {}
        ctx.check(f"Hugging Face router: the picked provider's tools, and remote (not local), got {hf}",
                  hf.get("tools") is True and hf.get("local") is False and hf.get("modalities_in") is None)
        ant = rows.get("ant:opus") or {}
        ctx.check(f"Anthropic: text + image + pdf in, tools, native reasoning with xhigh, got {ant}",
                  ant.get("modalities_in") == ["text", "image", "pdf"] and ant.get("tools") is True
                  and (ant.get("reasoning") or {}).get("kind") == "native" and "xhigh" in ant["reasoning"]["efforts"])
        ctx.check("Anthropic: Haiku 4.5 (budget thinking) names no effort levels",
                  (rows.get("ant:haiku") or {}).get("reasoning") == {"kind": "native", "efforts": []})


@test
def test_ollama_capabilities_list_reaches_the_row(ctx: Ctx):
    from halo_harness.providers.ollama_capability import save_capability_cache
    from tests.helpers.mock_ollama import MockUpstream
    mock = MockUpstream(show_responses=json.loads(json.dumps(S.OLLAMA_SHOW))).start()
    try:
        with S.home() as (_root, state):
            S.seed(state, ollama_url=mock.base_url, providers=False)
            save_capability_cache(state, {"sha256:deadbeef2": {"tool_calls": False, "checked_at": time.time(),
                                                                "model": "gpt-oss:20b", "host": "box"}})
            rows = S.rows_by_ref(state, {})
            q, g = rows.get("ol:qwen3:30b") or {}, rows.get("ol:gpt-oss:20b") or {}
            ctx.check(f"local vision is detected from /api/show (it read unknown before), got {q}",
                      q.get("modalities_in") == ["text", "image"] and q.get("tools") is True and q.get("local") is True)
            ctx.check(f"thinking reads as native reasoning, open weights, got {g}",
                      g.get("reasoning") == {"kind": "native", "efforts": []} and g.get("open_weights") is True)
            ctx.check(f"the measured tool-call probe lands in measured.tools_probe, got {g.get('measured')}",
                      (g.get("measured") or {}).get("tools_probe") is False and q.get("measured") is None)
    finally:
        mock.stop()


def _stats_cache(path: Path, ref: str) -> None:
    from halo_harness import telemetry
    counters = telemetry._new_model_counters()
    counters.update({"calls": 4, "ttft_values": [400, 500, 600, 700], "ttft_sum_ms": 2200, "ttft_n": 4,
                     "latency_sum_ms": 6200, "latency_n": 4, "tokens_out": 4000})
    summary = {"session_id": "s1", "slug": "p", "path": "s1.jsonl", "mtime": 1.0, "size": 1, "turns": 2,
               "models": {f"{ref}\x1fopenrouter": counters}}
    path.write_text(json.dumps({"s1": {"summary": summary}, telemetry._SCHEMA_KEY: telemetry.STATS_CACHE_SCHEMA}),
                    encoding="utf-8")


@test
def test_measured_reads_the_gym_rules_speed_and_census(ctx: Ctx):
    from halo_harness.gym import save_result
    from halo_harness.preflight import record_canary_result
    from halo_harness.providers.learned_rules import learn_tools_rejected
    from halo_harness.providers.speed import speed_by_ref
    with S.home() as (root, state):
        env = S.seed(state)
        save_result(state, {"model": "v/eyes", "model_ref": "or:v/eyes", "host_name": "cloud", "digest": None,
                            "tool_call_accuracy": {"score": 0.9}, "edit_success": {"score": 0.7},
                            "context_recall": {"score": 1.0}, "instruction_adherence": {"score": 0.8},
                            "tokens_per_second": 61.0, "finished_at": time.time()})
        record_canary_result(state, "or:v/cheap", {"ref": "or:v/cheap", "ok": False,
                                                   "checks": {"text": True, "tools": False, "vision": None}})
        learn_tools_rejected(state, "databricks", "databricks-gemini-9-flash")
        _stats_cache(state / "stats-cache.json", "or:v/ears")
        other = root / "elsewhere"
        other.mkdir()
        _stats_cache(other / "stats-cache.json", "or:v/other")
        ctx.check("speed_by_ref reads the state dir it is given", set(speed_by_ref(other)) == {"or:v/other"}
                  and set(speed_by_ref(state)) == {"or:v/ears"})
        rows = S.rows_by_ref(state, env)
        m_eyes = (rows.get("or:v/eyes") or {}).get("measured") or {}
        ctx.check(f"the gym result is measured.gym, got {m_eyes}",
                  (m_eyes.get("gym") or {}).get("score") == 0.85 and m_eyes["gym"]["tool_call_accuracy"] == 0.9
                  and set(m_eyes) == {"gym", "tools_probe", "tools_rejected", "ttft_s", "tokens_per_second", "canary"})
        m_cheap = (rows.get("or:v/cheap") or {}).get("measured") or {}
        ctx.check(f"the canary census is measured.canary, got {m_cheap}",
                  m_cheap.get("canary", {}).get("ok") is False and m_cheap["canary"]["tools"] is False)
        m_dbx = (rows.get("dbx:databricks-gemini-9-flash") or {}).get("measured") or {}
        ctx.check(f"a learned tools rejection is measured.tools_rejected, got {m_dbx}", m_dbx.get("tools_rejected") is True)
        m_ears = (rows.get("or:v/ears") or {}).get("measured") or {}
        ctx.check(f"telemetry's speed is measured, got {m_ears}",
                  m_ears.get("ttft_s") == 0.55 and isinstance(m_ears.get("tokens_per_second"), float))
        ctx.check("a row with nothing measured has measured None", (rows.get("or:v/painter") or {}).get("measured") is None)


@test
def test_local_is_is_local_model_ref_everywhere(ctx: Ctx):
    from halo_harness.capabilities import _tier
    from halo_harness.model import is_local_ref_string
    from halo_harness.orchestra.coach_prices import price_of
    ctx.check("ol: / hf:local / hf:mlx are local; a Hugging Face router ref is not",
              is_local_ref_string("ol:qwen3:30b") and is_local_ref_string("hf:local/x") and is_local_ref_string("hf:mlx/a/b")
              and not is_local_ref_string("hf:Org/Model-7B") and not is_local_ref_string("or:v/eyes"))
    router = {"ref": "hf:Org/Model-7B", "provider": "huggingface", "price_in_per_m": 0.2}
    ctx.check("capabilities._tier prices a router row like any remote row", "local" not in _tier(router)[1])
    ctx.check("coach_prices.price_of keeps a router row's own price", price_of([router], router["ref"]) == 0.2)
    ctx.check("and a local row is still free", price_of([{"ref": "hf:local/x", "provider": "huggingface"}], "hf:local/x") == 0.0)


@test
def test_model_profile_audio_follows_the_catalog(ctx: Ctx):
    from halo_harness.model import parse_model_ref, resolve_model_profile
    with S.home() as (_root, state):
        S.seed(state)
        ears = resolve_model_profile(parse_model_ref("or:v/ears", {}), state)
        eyes = resolve_model_profile(parse_model_ref("or:v/eyes", {}), state)
        dbx = resolve_model_profile(parse_model_ref("dbx:databricks-gemini-x-pro", {}), state)
        ctx.check(f"audio input in the catalog makes ModelProfile.audio true, got {ears.audio} {dbx.audio}",
                  ears.audio is True and dbx.audio is True and eyes.audio is False and eyes.vision is True)


@test
def test_an_audio_tool_result_reaches_a_chat_model_as_input_audio(ctx: Ctx):
    """With ModelProfile.audio real, an MCP tool's audio block reaches an
    OpenAI-chat-dialect model as an `input_audio` part, never silently dropped."""
    from halo_harness.providers.translate import _flatten_messages
    audio = {"type": "audio", "source": {"type": "base64", "media_type": "audio/mpeg", "data": "QUJD"}}
    msgs = [{"role": "user", "content": [{"type": "text", "text": "listen"}]},
            {"role": "assistant", "content": [{"type": "tool_use", "id": "t1", "name": "rec", "input": {}}]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": [audio]}]}]
    protos = _flatten_messages(msgs, None)
    tool = next(p for p in protos if p.get("role") == "tool")
    parts = [part for p in protos if p.get("role") == "user" and isinstance(p.get("content"), list) for part in p["content"]]
    ctx.check(f"the tool message says the audio follows, got {tool}", "(audio in next message)" in tool["content"])
    ctx.check(f"the audio rides as input_audio (mp3), got {parts}",
              {"type": "input_audio", "input_audio": {"data": "QUJD", "format": "mp3"}} in parts)


@test
def test_the_openrouter_probe_keeps_output_modalities(ctx: Ctx):
    from halo_harness.providers.databricks import load_models_json, probe_openrouter_models, write_models_json
    from tests.helpers.mock_get_endpoints import MockGetEndpoints
    body = {"data": [{"id": "v/painter", "context_length": 32000, "architecture": {
        "input_modalities": ["text", "image"], "output_modalities": ["image", "text"]}}]}
    mock = MockGetEndpoints({"/api/v1/models": (200, body)}).start()
    try:
        with S.home() as (_root, state):
            write_models_json(state, probe_openrouter_models(mock.base_url + "/api/v1", "sk-or-fixture"))
            entry = load_models_json(state).get("v/painter") or {}
            ctx.check(f"output_modalities is stored, got {entry}", entry.get("output_modalities") == ["image", "text"])
    finally:
        mock.stop()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="model row facts tests"))
