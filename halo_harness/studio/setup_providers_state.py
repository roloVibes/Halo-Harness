"""halo_harness.studio.setup_providers_state -- the Providers and Local models
blocks of `GET setup/state` (Halo 3.3.0.0 R2, Studio's Setup section;
docs/STUDIO-setup.md): what the terminal wizard's Providers tabs and its
Local models step show, read from the same places (init_providers.
tab_credential_state, config.json's `ollama.hosts` / `huggingface.*`, the
env file). A key is never in it: a provider says `set`, where the key comes
from and its last four characters.

    env_file: the env file's path (`HALO_ENV_FILE`, else ~/.config/halo/env)
    providers: {<name>: {label, set, source ("env file" | "environment" | "config.json" | "not set"),
                         tail ("****1234" | ""), enabled, reachable ("ok" | "no" | "not checked"),
                         catalog_count, detail, host_hint, fields: [{id, label, secret, present, placeholder}]}}
    ollama: {hosts: [{name, url, default, key_env}]}
    huggingface: {token_set, endpoints: [{name, url, token_env}], local_servers: [{name, url, key_env}]}
    local_models: {model_dirs: [...], runtime, runtimes: [{id, label, note}], detection: [lines]}

`reachable` is what the last Save & test of this Studio found ("not checked"
until one ran): a read never probes a host.
"""

from __future__ import annotations

import threading
import time

# The variables each card's fields write (the wizard's `fields` names -> the env var they land in).
KEY_FIELDS = {
    "databricks": (("host", "DATABRICKS_HOST", False), ("token", "DATABRICKS_TOKEN", True)),
    "openrouter": (("key", "OPENROUTER_API_KEY", True),),
    "anthropic": (("key", "ANTHROPIC_API_KEY", True),),
    "openai": (("key", "OPENAI_API_KEY", True),),
    "typesafe": (("key", "TYPESAFE_API_KEY", True),),
    "experiential": (("key", "EXPLABS_API_KEY", True),),
    "huggingface": (("token", "HF_TOKEN", True),),
}
DBX_PLACEHOLDER = "e.g. https://your-workspace.cloud.databricks.com"  # sent in the state: the page bundle spells no URL
RUNTIMES = (("llama-server", "llama-server (GGUF)", "runs .gguf files; the usual pick on Linux and Windows"),
            ("mlx_lm", "mlx_lm (Apple Silicon)", "runs MLX / safetensors folders on a Mac with Apple Silicon"))

# The last Save & test per provider in this process: "ok" | "no" | "not checked".
LAST_REACH: dict = {}
TYPED: dict = {}  # 3.3.5.0 R0 (g): {provider: {field id}} saved through a card in this Studio process
_DETECT: dict = {"lines": None, "at": 0.0, "thread": None}
_DETECT_TTL = 60.0
_LOCK = threading.Lock()


def tail(value) -> str:
    """"****" and the last four characters of a key ("****" alone for a short one, "" for none)."""
    if not isinstance(value, str) or not value:
        return ""
    return "****" + value[-4:] if len(value) >= 8 else "****"


def _secret(name: str, env: dict):
    """The key a provider resolves to now (the variable it came from, the value), or (None, None)."""
    from halo_harness.providers import config as C
    try:
        if name == "databricks":
            dbx = C.resolve_databricks(env)
            return ("DATABRICKS_TOKEN", dbx.token) if dbx is not None else (None, None)
        if name == "typesafe":
            return ("TYPESAFE_API_KEY", env.get("TYPESAFE_API_KEY")) if env.get("TYPESAFE_API_KEY") else (None, None)
        resolver = {"openrouter": C.resolve_openrouter, "anthropic": C.resolve_anthropic, "openai": C.resolve_openai,
                    "experiential": C.resolve_experiential, "huggingface": C.resolve_huggingface}.get(name)
        found = resolver(env) if resolver else None
        if found is None:
            return None, None
        return KEY_FIELDS[name][-1][1], getattr(found, "api_key", None)
    except Exception:
        return None, None


def env_file_vars() -> dict:
    """The env file's variables (`HALO_ENV_FILE`, else ~/.config/halo/env), read, never written."""
    from halo_harness.config.paths import env_file_path
    from halo_harness.providers.config import _parse_env_file
    try:
        return _parse_env_file(env_file_path())
    except Exception:
        return {}


def _count(name: str, state_dir) -> int:
    from halo_harness.init_providers import model_entries_for_provider
    try:
        return len(model_entries_for_provider(name, state_dir))
    except Exception:
        return 0


def _config_list(key: str) -> list:
    from halo_harness.theme import get_config_value
    raw = get_config_value(key, default=None)
    return [e for e in raw if isinstance(e, dict)] if isinstance(raw, list) else []


def provider_row(name: str, env: dict, file_vars: dict, state_dir=None, cwd=None) -> dict:
    from halo_harness.init_providers import TAB_LABEL, tab_credential_state
    from halo_harness.providers.enablement import is_enabled
    try:
        st = tab_credential_state(name, cwd=cwd)
    except Exception:
        st = {"configured": False, "fields": []}
    configured = bool(st.get("configured"))
    var, value = _secret(name, env)
    if not configured:
        source = "not set"
    elif var and value:
        source = "env file" if file_vars.get(var) == value else "environment"
    else:
        source = "config.json"
    if name in KEY_FIELDS:
        fields = [{"id": fid, "label": label, "secret": secret, "present": bool(env.get(label)),
                   "placeholder": DBX_PLACEHOLDER if label == "DATABRICKS_HOST" else ""} for fid, label, secret in KEY_FIELDS[name]]
    else:
        fields = [{"id": f["name"], "label": f["label"], "secret": bool(f["secret"]), "present": False, "placeholder": ""}
                  for f in st.get("fields") or []]
    detail = ""
    if name == "databricks":
        detail = str(env.get("DATABRICKS_HOST") or st.get("known_host") or "")
    sources = field_sources(name, env, file_vars, st, fields)
    try:
        enabled = bool(is_enabled(name, state_dir=state_dir, detected=configured))
    except Exception:
        enabled = configured
    return {"label": TAB_LABEL.get(name, name), "set": configured, "source": source, "tail": tail(value) if configured else "",
            "enabled": enabled, "reachable": LAST_REACH.get(name, "not checked"), "catalog_count": _count(name, state_dir) if configured else 0,
            "detail": detail, "host_hint": str(st.get("host_hint") or ""), "fields": fields, "field_sources": sources}


def field_sources(name: str, env: dict, file_vars: dict, st: dict, fields: list) -> dict:
    """3.3.5.0 R0 (g): where each field's value came from -- "typed here" (saved through the card in this
    Studio), "env file", "environment", "Claude Code's settings.json" (a host discovered there), "the team
    config", or "" when it has none."""
    if name not in KEY_FIELDS:
        return {}  # Ollama and Hugging Face cards keep their own line (hosts, entries)
    typed = TYPED.get(name) or set()
    out = {}
    for f in fields:
        fid, label = f["id"], f["label"]
        value = env.get(label)
        if fid in typed and (value or not f.get("secret")):
            out[fid] = "typed here"
        elif value:
            import os
            out[fid] = "env file" if file_vars.get(label) == value else (
                "environment" if os.environ.get(label) == value else "Claude Code's settings.json")
        elif name == "databricks" and fid == "host" and st.get("known_host"):
            out[fid] = str(st.get("host_from") or st.get("source") or "")
        else:
            out[fid] = ""
    return out


def ollama_block() -> dict:
    hosts = _config_list("ollama.hosts")
    return {"hosts": [{"name": str(h.get("name") or h.get("url") or "?"), "url": str(h.get("url") or ""),
                       "default": bool(h.get("default")), "key_env": str(h.get("api_key_env") or "")} for h in hosts]}


def huggingface_block(env: dict) -> dict:
    _var, token = _secret("huggingface", env)
    return {"token_set": bool(token),
            "endpoints": [{"name": str(e.get("name") or ""), "url": str(e.get("url") or ""), "token_env": str(e.get("token_env") or "")}
                          for e in _config_list("huggingface.endpoints")],
            "local_servers": [{"name": str(s.get("name") or ""), "url": str(s.get("url") or ""), "key_env": str(s.get("api_key_env") or "")}
                              for s in _config_list("huggingface.local_servers")]}


def folder_line() -> "list[str]":
    """One line on what the model folders hold now (local_model_dirs.scan_model_dirs), [] with no folder."""
    from halo_harness.providers.local_model_dirs import resolve_model_dirs, scan_model_dirs
    try:
        dirs = resolve_model_dirs()
        found = scan_model_dirs(dirs) if dirs else []
    except Exception:
        return []
    if not dirs:
        return []
    kinds = sorted({f.format for f in found})
    return [f"The {len(dirs)} model folder{'' if len(dirs) == 1 else 's'} {'holds' if len(dirs) == 1 else 'hold'} {len(found)} model"
            f"{'' if len(found) == 1 else 's'}" + (f" ({', '.join(kinds)})." if kinds else ".")]


def _detect_now() -> None:
    from halo_harness.config.paths import background_net_disabled
    from halo_harness.providers.local_models import detection_summary_lines
    if background_net_disabled():
        lines = ["Ollama, local servers and the GPU were not probed (no network in this run)."]
    else:
        try:
            lines = detection_summary_lines()
        except Exception:
            lines = []
    lines = [*lines, *folder_line()]
    with _LOCK:
        _DETECT.update(lines=lines or ["Nothing detected on this machine yet (no Ollama daemon, no local server, no cached model files)."],
                       at=time.monotonic(), thread=None)


def forget_detection() -> None:
    """The next read detects again (a folder or the runtime just changed)."""
    with _LOCK:
        _DETECT.update(lines=None, at=0.0)


def detection(wait: float = 4.0) -> list:
    """The Local models step's detection lines (providers.local_models.detection_summary_lines), kept a minute;
    a detection still running after `wait` seconds says so and lands on the next read."""
    with _LOCK:
        fresh = _DETECT["lines"] is not None and time.monotonic() - _DETECT["at"] < _DETECT_TTL
        if fresh:
            return list(_DETECT["lines"])
        t = _DETECT["thread"]
        if t is None:
            t = threading.Thread(target=_detect_now, name="setup-detect", daemon=True)
            _DETECT["thread"] = t
            t.start()
    t.join(wait)
    with _LOCK:
        if _DETECT["lines"] is not None and _DETECT["thread"] is None:
            return list(_DETECT["lines"])
    return ["Still detecting what is on this machine: the lines show on the next read."]


def local_models_block() -> dict:
    from halo_harness.providers.local_model_dirs import resolve_model_dirs
    from halo_harness.theme import get_config_value
    runtime = get_config_value("huggingface.preferred_runtime", default="")
    return {"model_dirs": [str(d) for d in resolve_model_dirs()], "runtime": runtime if isinstance(runtime, str) else "",
            "runtimes": [{"id": i, "label": label, "note": note} for i, label, note in RUNTIMES], "detection": detection()}


def provider_blocks(cwd=None, state_dir=None) -> dict:
    """The parts `setup_state` merges in: providers, env_file (the path keys land in), ollama, huggingface,
    local_models."""
    from halo_harness.config.paths import env_file_path
    from halo_harness.init_providers import TAB_PROVIDERS
    from halo_harness.providers.config import listing_effective_env
    env = listing_effective_env(cwd)
    file_vars = env_file_vars()
    return {"providers": {n: provider_row(n, env, file_vars, state_dir, cwd) for n in TAB_PROVIDERS}, "env_file": str(env_file_path()),
            "ollama": ollama_block(), "huggingface": huggingface_block(env), "local_models": local_models_block()}
