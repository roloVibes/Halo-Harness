"""halo_harness.providers.databricks_price_table -- Databricks' published
pay-per-token rates for the foundation-model endpoints it serves (Halo
3.3.3.1, "costs are always dollars"). The data only; the lookup and the
dollar conversion are providers/databricks_prices.py.

Sources (read 2026-10-27):
  https://www.databricks.com/product/pricing/foundation-model-serving
    (open-weight models: Kimi, GLM, DeepSeek, Llama, Qwen, GPT-OSS, Gemma)
  https://www.databricks.com/product/pricing/proprietary-foundation-model-serving
    (OpenAI GPT, Anthropic Claude, Google Gemini, xAI Grok)

Databricks publishes these in DBUs per 1M tokens ("Standard Pay Per Token"),
not dollars; each figure here is copied as published. A model with a short
and a long context rate carries the short one. Rates the page marks as a
time-limited promotion (GPT-5.6 Sol to 2026-11-21, Gemini 4 Argon to
2026-11-30, Gemini 3.6-3.8 Flash to 2026-12-31) are the promotional ones.
Regional processing (data residency) adds 10 % on the marked models; that
uplift is not applied here.

Each row: normalized endpoint name (providers/databricks_prices.normalize:
lower case, no `databricks-` prefix, `.`/`_` as `-`) ->
(input, output, cache read or None, cache write or None), DBU per 1M tokens.
"""

from __future__ import annotations

_OPEN = {
    "kimi-k3": (42.857, 214.286, 4.286, None),
    "glm-5-2": (20.000, 62.857, 3.714, None),
    "glm-5-3": (20.000, 62.857, 3.714, None),
    "deepseek-v4-pro": (18.857, 56.571, 1.886, None),
    "inkling": (14.286, 57.857, 2.429, None),
    "kimi-k2-7": (13.571, 57.143, 2.714, None),
    "glm-5-3-flash": (2.143, 7.143, 0.429, None),
    "deepseek-v4-1-flash": (4.286, 17.143, 0.100, None),
    "deepseek-v4-flash": (2.000, 4.000, 0.400, None),
    "qwen35-122b": (3.143, 31.429, None, None),
    "llama-4-maverick": (7.143, 21.429, None, None),
    "meta-llama-4-maverick": (7.143, 21.429, None, None),
    "meta-llama-3-3-70b-instruct": (7.143, 21.429, None, None),
    "qwen3-next-80b-a3b-instruct": (2.143, 17.143, None, None),
    "gpt-oss-120b": (2.143, 8.571, None, None),
    "gemma-3-12b": (2.143, 7.143, None, None),
    "meta-llama-3-1-8b-instruct": (2.143, 6.429, None, None),
    "gpt-oss-20b": (1.000, 4.286, None, None),
}

_OPENAI = {
    "gpt-6-astra": (142.857, 714.286, 14.286, 178.571),
    "gpt-6-1-sol": (28.571, 142.857, 1.429, 35.714),
    "gpt-6-sol": (28.571, 142.857, 2.857, 35.714),
    "gpt-6-luna": (1.429, 7.143, 0.143, 1.786),
    "gpt-5-6-sol": (57.143, 285.714, 5.714, 71.429),
    "gpt-5-6-terra": (28.571, 171.429, 2.857, 35.714),
    "gpt-5-6-luna": (2.857, 17.143, 0.286, 3.571),
    "gpt-5-4-pro": (428.571, 2571.43, None, None),
    "gpt-5-5-pro": (428.571, 2571.43, None, None),
    "gpt-5-5": (71.429, 428.571, 7.143, None),
    "gpt-5-4": (35.714, 214.286, 3.571, None),
    "gpt-5-4-mini": (10.714, 64.286, 1.071, None),
    "gpt-5-4-nano": (2.857, 17.857, 0.286, None),
    "gpt-5-3-codex": (25.0, 200.0, 2.5, None),
    "gpt-5-2": (25.0, 200.0, 2.5, None),
    "gpt-5": (17.857, 142.857, 1.786, None),
    "gpt-5-1": (17.857, 142.857, 1.786, None),
    "gpt-5-mini": (3.571, 28.571, 0.357, None),
    "gpt-5-nano": (0.714, 5.714, 0.071, None),
}

_CLAUDE = {
    "claude-fable-5-1": (142.857, 714.286, 3.571, 178.571),
    "claude-fable-5": (142.857, 714.286, 14.286, 178.571),
    "claude-opus-5-5": (57.143, 285.714, 2.857, 71.429),
    "claude-opus-5": (71.429, 357.143, 7.143, 89.286),
    "claude-opus-4-8": (71.429, 357.143, 7.143, 89.286),
    "claude-opus-4-7": (71.429, 357.143, 7.143, 89.286),
    "claude-opus-4-6": (71.429, 357.143, 7.143, 89.286),
    "claude-opus-4-5": (71.429, 357.143, 7.143, 89.286),
    "claude-opus-4-1": (214.286, 1071.43, 21.429, 267.857),
    "claude-opus-4": (214.286, 1071.43, 21.429, 267.857),
    "claude-sonnet-5-5": (28.571, 142.857, 2.857, 35.714),
    "claude-sonnet-5": (28.571, 142.857, 2.857, 35.714),
    "claude-sonnet-4-6": (42.857, 214.286, 4.286, 53.571),
    "claude-sonnet-4-5": (42.857, 214.286, 4.286, 53.571),
    "claude-sonnet-4": (42.857, 214.286, 4.286, 53.571),
    "claude-haiku-5-5": (1.429, 7.143, 0.143, 1.786),
    "claude-haiku-4-5": (14.286, 71.429, 1.429, 17.857),
}

_GOOGLE_XAI = {
    "gemini-4-argon": (35.714, 178.571, 1.786, None),
    "gemini-3-1-pro": (35.714, 214.286, 3.571, None),
    "gemini-3-8-flash": (10.714, 53.571, 1.071, None),
    "gemini-3-7-flash": (10.714, 53.571, 1.071, None),
    "gemini-3-6-flash": (10.714, 53.571, 1.071, None),
    "gemini-3-5-flash": (26.786, 160.714, 2.679, None),
    "gemini-3-flash": (8.929, 53.571, 0.893, None),
    "gemini-3-5-flash-lite": (5.357, 44.643, 0.536, None),
    "gemini-3-1-flash-lite": (4.464, 26.786, 0.446, None),
    "gemini-2-5-flash-lite": (1.786, 7.143, 0.179, None),
    "grok-4-7": (35.714, 107.143, 8.929, None),
    "grok-4-6": (35.714, 107.143, 8.929, None),
}

DBU_PER_M: dict = {**_OPEN, **_OPENAI, **_CLAUDE, **_GOOGLE_XAI}
