"""halo_harness.settings_catalog_rows_b -- the Settings rows of Providers, Ollama and Network and routing
(settings_catalog.py has the shape; one row per line: key, group, title, kind, default, choices, help, effect,
secret)."""

from __future__ import annotations

from halo_harness.settings_catalog import Row

ROWS = [
    Row("providers.<name>.enabled", "providers", "Provider on", "keyed", True, (), "Turn one provider on or off; unset, a provider whose credentials are found is on.", "now"),
    Row("databricks.gateway.<endpoint>", "providers", "Databricks gateway dialect", "keyed", None, ("anthropic", "openai"), "How one Databricks endpoint is called; unset, Claude foundation models go anthropic and every other one openai.", "now"),
    Row("databricks.dbu_price_usd", "providers", "DBU price (USD)", "float", None, (), "The dollar price of one DBU; unset, Databricks costs show as raw DBUs.", "now"),
    Row("databricks.catalog_max_age_hours", "providers", "Databricks catalog age (hours)", "int", 24, (), "How old the Databricks endpoint catalog may be before it is read again.", "now"),
    Row("openai.dialect_overrides", "providers", "OpenAI dialect overrides", "mapping", None, (), "A map of bare oai: model id to chat or responses; it always wins over the built-in table.", "now"),
    Row("experiential.dialect_overrides", "providers", "Experiential dialect overrides", "mapping", None, (), "A map of xp: slug to chat or responses; it always wins over the default.", "now"),
    Row("experiential.tool_search", "providers", "Experiential tool search", "bool", False, (), "Use the gateway's tool search convention for Halo's deferred tools on xp: routes.", "now"),
    Row("experiential.routing.allow_fallbacks", "providers", "Experiential fallbacks", "bool", True, (), "Sent on every xp: request once set; unset, the gateway's own default (effectively on).", "now"),
    Row("experiential.routing.route_id", "providers", "Experiential route", "string", None, (), "Pin every xp: request to one waterfall rung, from /xp routes.", "now"),
    Row("experiential.retry.max_attempts_per_route", "providers", "Experiential attempts per route", "int", 1, (), "Attempts per route the gateway makes (Halo's own retry loop is the outer layer).", "now"),
    Row("experiential.retry.max_total_attempts", "providers", "Experiential total attempts", "int", None, (), "Attempts in all the gateway makes; unset, the gateway's own default.", "now"),
    Row("experiential.retry.backoff", "providers", "Experiential backoff", "mapping", None, (), "The gateway's backoff policy (type exponential with its delays, or type none); unset keeps the gateway's own.", "now"),
    Row("experiential.zdr", "providers", "Experiential zero data retention", "bool", False, (), "Ask for zero-data-retention routing on every xp: request.", "now"),
    Row("huggingface.endpoints", "providers", "Hugging Face endpoints", "list", None, (), "Dedicated endpoints, each with name, url, token_env and default; hf:endpoint/<name> picks one.", "now"),
    Row("huggingface.bill_to", "providers", "Hugging Face bill to", "string", None, (), "A Team or Enterprise org name billed for every router request.", "now"),
    Row("huggingface.local_servers", "providers", "Hugging Face local servers", "list", None, (), "Local servers, each with name, url, api_key_env, default and offline_ok; hf:local/<model>@<name> picks one.", "now"),
    Row("huggingface.local_probe_ports", "providers", "Local probe ports", "list", [8080, 8000, 1234], (), "The loopback ports the hf:local auto-detect sweep asks.", "now"),
    Row("huggingface.lmstudio_models_dir", "providers", "LM Studio model folder", "path", "~/.lmstudio/models", (), "Where LM Studio keeps its models, when its own Model Storage setting moved them.", "now"),
    Row("huggingface.model_dirs", "providers", "Model folders", "list", [], (), "Folders Halo scans for .gguf files and safetensors or MLX model folders (/local add).", "now"),
    Row("huggingface.preferred_runtime", "providers", "Local runtime", "enum", None, ("llama-server", "mlx_lm"), "The runtime halo local serve uses for a file it is not told one for.", "now"),
    Row("ollama.hosts", "ollama", "Ollama hosts", "list", None, (), "The Ollama hosts, each with name and url (and keep_alive, max_ctx, dialect ...); unset, one default host on this machine.", "now"),
    Row("ollama.hosts[].kv_cache_type", "ollama", "KV cache type", "keyed", "f16", ("f16", "q8_0", "q4_0"), "Set it to match that host's own OLLAMA_KV_CACHE_TYPE so the fit estimate counts its memory right.", "now"),
    Row("ollama.hosts[].ssh", "ollama", "SSH GPU read", "keyed", None, (), "An optional user@host for a read-only GPU probe of a remote host over ssh.", "now"),
    Row("ollama.tools_max", "ollama", "Tools at most", "int", None, (), "The ol: route's tool-catalog cap; unset, derived from the context size.", "now"),
    Row("ollama.ledger", "ollama", "Traffic ledger", "bool", True, (), "Every call to a local model server leaves one line in ~/.halo/ollama/traffic.jsonl (halo ollama traffic reads it).", "now"),
    Row("ollama.auto_calibrate", "ollama", "Auto calibrate", "bool", True, (), "Run the fit calibration the first time a model is used on a host with no learned cap.", "now"),
    Row("ollama.discover.ports", "ollama", "Discovery ports", "list", [11434], (), "The ports Find Ollama servers and Scan this network ask on every address.", "now"),
    Row("ollama.discover.subnets", "ollama", "Discovery subnets", "list", [], (), "Extra IPv4 CIDRs the network scan sweeps besides this machine's own /24.", "now"),
    Row("network.offline", "network", "Offline", "bool", False, (), "Only local hosts are called; every request to a remote host fails at once.", "now"),
    Row("routing.escalation", "network", "Escalation", "mapping", None, (), "Hand a local session's turn to a cloud model: to (a model ref), when (the triggers) and ask.", "next session"),
]
