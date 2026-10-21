"""tests.helpers.catalog_facts_seed -- a fresh Halo home whose cached catalogs
hold a few models from every provider (Halo 3.1.9.0 R1, "what each model is
good at"): OpenRouter's models.json, models.dev (Databricks, OpenAI and the
google / anthropic vendor families), the Databricks endpoint list, the
OpenAI id list, the Experiential gateway, the Hugging Face router, the
Anthropic key, and an optional mock Ollama host whose `/api/show` names
vision / tools / thinking. Fixture caches only -- no network, no model call.

`home()` snapshots and restores every provider variable (the WORKER-RULES
`_Env` convention) and yields `(home, state)`; `seed(state)` writes the
caches and returns the env dict the catalog resolves with.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path

PREFIXES = ("OPENROUTER_", "DATABRICKS_", "ANTHROPIC_", "BRIDGE_", "HALO_", "ROLO_CLAUDE_", "TYPESAFE_", "OPENAI_",
            "OLLAMA_", "HF_", "EXPLABS_", "CLAUDE_CONFIG_DIR")
ENV = {"OPENROUTER_API_KEY": "sk-or-fixture", "ANTHROPIC_API_KEY": "sk-ant-fixture",
       "DATABRICKS_HOST": "https://your-workspace.cloud.databricks.com", "DATABRICKS_TOKEN": "dapi-fixture",
       "HF_TOKEN": "hf_fixture", "OPENAI_API_KEY": "sk-oai-fixture", "EXPLABS_API_KEY": "xp-fixture"}


def _per_token(per_m: float) -> str:
    return f"{per_m / 1_000_000:.10f}"


OPENROUTER = {
    "v/eyes": {"context_length": 100000, "input_modalities": ["text", "image", "file"], "output_modalities": ["text"],
               "supported_parameters": ["tools", "reasoning"], "pricing": {"prompt": _per_token(1), "completion": _per_token(2)}},
    "v/cheap": {"context_length": 128000, "input_modalities": ["text"], "output_modalities": ["text"],
                "supported_parameters": ["tools", "temperature"], "pricing": {"prompt": _per_token(0.1), "completion": _per_token(0.4)}},
    "v/ears": {"context_length": 1000000, "input_modalities": ["text", "image", "audio", "video"], "output_modalities": ["text"],
               "supported_parameters": ["tools", "reasoning"], "pricing": {"prompt": _per_token(0.3), "completion": _per_token(2.5)}},
    "v/painter": {"context_length": 32000, "input_modalities": ["text", "image"], "output_modalities": ["image", "text"],
                  "pricing": {"prompt": _per_token(0.3), "completion": _per_token(2.5)}},
    "v/plain": {"context_length": 50000, "pricing": {"prompt": _per_token(1), "completion": _per_token(2)}},
}


def _md(inputs, *, tools=True, open_weights=False, reasoning=True, efforts=None, ctx=200000, cost=(1.0, 4.0)):
    entry = {"limit": {"context": ctx, "output": 32000}, "cost": {"input": cost[0], "output": cost[1]},
             "modalities": {"input": inputs, "output": ["text"]}, "tool_call": tools, "open_weights": open_weights,
             "reasoning": reasoning, "reasoning_options": [{"type": "effort", "values": efforts}] if efforts else []}
    return entry


MODELS_DEV = {
    "databricks": {"models": {"databricks-gemini-x-pro": _md(["text", "image", "audio", "video", "pdf"],
                                                             efforts=["low", "medium", "high"], ctx=1000000)}},
    "google": {"models": {"gemini-9-flash": _md(["text", "image"], reasoning=False, cost=(0.1, 0.4))}},
    "openai": {"models": {"gpt-x": _md(["text", "image", "pdf"], efforts=["minimal", "low", "medium", "high"])}},
    "anthropic": {"models": {"claude-haiku-9": _md(["text", "image", "pdf"])}},
}
DBX_ENDPOINTS = [{"name": n, "task": "llm/v1/chat", "ready": "READY"}
                 for n in ("databricks-gemini-x-pro", "databricks-gemini-9-flash", "databricks-openjev-qwen35-4b")]
XP = {"claude-haiku-9": {"context_window_tokens": 200000, "maximum_output_tokens": 64000, "supports_tools": True,
                         "supports_reasoning": True, "supported_reasoning_efforts": ["low", "high"],
                         "pricing": {"input_nano_usd_per_million_tokens": 1_000_000_000,
                                     "output_nano_usd_per_million_tokens": 5_000_000_000}},
      "xp-text-1": {"context_window_tokens": 32000, "supports_tools": False, "supports_reasoning": False}}
HF = [{"id": "Org/Model-7B", "context_length": 32768, "pricing": {"prompt": 0.2, "completion": 0.6},
       "providers": [{"provider": "p1", "status": "live", "supports_tools": True, "context_length": 32768,
                      "pricing": {"prompt": 0.2, "completion": 0.6}}]}]
# the mock Ollama host: qwen3:30b sees images and calls tools (the probe failed on gpt-oss:20b)
OLLAMA_SHOW = {
    "qwen3:30b": {"capabilities": ["completion", "vision", "tools"], "details": {"family": "qwen3", "quantization_level": "Q4_0"},
                  "model_info": {"qwen3.context_length": 40960}},
    "gpt-oss:20b": {"capabilities": ["completion", "tools", "thinking"], "details": {"family": "gptoss", "quantization_level": "Q4_0"},
                    "model_info": {"gptoss.context_length": 131072}},
}


@contextmanager
def home(prefix: str = "catalog-facts-"):
    saved = {k: v for k, v in os.environ.items() if k.startswith(PREFIXES)}
    for k in saved:
        os.environ.pop(k)
    root = Path(tempfile.mkdtemp(prefix=prefix))
    os.environ["BRIDGE_TEST_HOME"] = str(root)
    os.environ["BRIDGE_TEST_NO_BACKGROUND_NET"] = "1"
    os.environ["BRIDGE_TEST_CC_AUTH_STATUS"] = json.dumps({"loggedIn": False})
    from halo_harness.providers.config import default_state_dir
    state = Path(default_state_dir())
    state.mkdir(parents=True, exist_ok=True)
    try:
        yield root, state
    finally:
        try:
            from halo_harness.models_best_at import wait_for_rebuild
            wait_for_rebuild(state, 30)
        except Exception:
            pass
        for k in [k for k in os.environ if k.startswith(PREFIXES)]:
            os.environ.pop(k)
        os.environ.update(saved)
        shutil.rmtree(root, ignore_errors=True)


def seed(state: Path, *, ollama_url: str = "http://127.0.0.1:9", providers: bool = True) -> dict:
    """Write every provider cache under `state`; the env the catalog resolves with."""
    from halo_harness.providers.databricks import write_dbx_endpoints_json
    from halo_harness.providers.enablement import enable
    from halo_harness.providers.experiential_catalog import write_xp_models_json
    from halo_harness.providers.huggingface_catalog import write_hf_models_json
    from halo_harness.providers.models_dev import write_models_dev_json
    from halo_harness.providers.openai_catalog import write_oai_models_json
    from halo_harness.theme import set_config_value
    set_config_value("ollama.hosts", [{"name": "box", "url": ollama_url, "default": True}])
    if not providers:
        return {}
    (state / "models.json").write_text(json.dumps(OPENROUTER), encoding="utf-8")
    write_models_dev_json(state, MODELS_DEV)
    write_dbx_endpoints_json(state, DBX_ENDPOINTS)
    write_oai_models_json(state, ["gpt-x"])
    write_xp_models_json(state, XP)
    write_hf_models_json(state, HF)
    for name in ("openrouter", "anthropic", "databricks", "huggingface", "openai", "experiential"):
        enable(name)
    os.environ.update(ENV)
    return dict(ENV)


def rows_by_ref(state: Path, env: dict) -> dict:
    from halo_harness.providers.model_enumeration import build_model_rows
    return {r["ref"]: r for r in build_model_rows(state, env=env) if r.get("ref")}
