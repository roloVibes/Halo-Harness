"""halo_harness.studio.local_uses -- Halo 3.3.5.0 R3: what uses a model, the
card Local's Delete shows first (and `halo models rm` prints). Read from the
files that name a model -- never a server, never a model call:

    uses_of(ref, *, cwd=None, state_dir=None) -> {ref, model, host, lineups [{name, role}], roles [name],
                                                compaction: bool, default_model: bool, profiles [key],
                                                sessions [{id, title, live}], any: bool, live: int, line}

- lineups: your lineup files (user and project; not the shipped templates),
  every member whose model -- the card's, its bio's, its tier's, the fallback
  (teams_yaml.member_model) -- is this model on this host;
- roles: config.json `roles`; `compactionModel`; `model` (the default);
- profiles: `ollama.profiles` keys `<host>|<model>`;
- sessions: this harness's live sessions (remote/registry.list_live) whose
  model, from the registry entry or the session's own log, is this one.

A ref matches `ol:<model>@<host>` (or `ol:<model>`: the default host) with the
tag rule of providers/ollama.ollama_names_match. 3.3.5.0 R5: an `hf:local/<model>`
ref (a file on disk Halo serves; `@<server>` or bare) matches any `hf:local/<model>`
value and, given the repo, `hf:mlx/<repo>`; its profiles are keyed `<server>|<model>`
(`refers_to_hf`). `READERS["live"]` replaces the live-session reader (the tests' seam).
"""

from __future__ import annotations

from typing import Optional

READERS: dict = {}


def split_ref(ref: str) -> "tuple[str, str]":
    """(model, host) of `ol:<model>@<host>`; host "" = the default host."""
    r = str(ref or "").strip()
    if r.startswith("ol:"):
        r = r[3:]
    model, at, host = r.rpartition("@")
    return (model, host) if at and model else (r, "")


def _default_host() -> str:
    try:
        from halo_harness.providers.ollama import resolve_ollama_host
        h = resolve_ollama_host(None)
        return h.name if h is not None else ""
    except Exception:
        return ""


def refers_to(value, model: str, host: str) -> bool:
    from halo_harness.providers.ollama import ollama_names_match
    from halo_harness.roles import role_value_parts
    raw = role_value_parts(value)[0] if isinstance(value, dict) else value
    if not isinstance(raw, str) or not raw.strip().startswith("ol:"):
        return False
    m, h = split_ref(raw)
    return ollama_names_match(m, model) and (h or _default_host()).lower() == (host or _default_host()).lower()


def hf_parts(value) -> "tuple[str, str]":
    """('local', model) of `hf:local/<model>[@server]`, ('mlx', repo) of `hf:mlx/<repo>`, else ('', '')."""
    from halo_harness.roles import role_value_parts
    raw = role_value_parts(value)[0] if isinstance(value, dict) else value
    raw = raw.strip() if isinstance(raw, str) else ""
    if raw.startswith("hf:local/"):
        return "local", raw[len("hf:local/"):].rpartition("@")[0] or raw[len("hf:local/"):]
    if raw.startswith("hf:mlx/"):
        return "mlx", raw[len("hf:mlx/"):]
    return "", ""


def refers_to_hf(value, model: str, repo: str = "") -> bool:
    kind, name = hf_parts(value)
    return bool(kind) and ((kind == "local" and name.lower() == model.lower())
                           or (kind == "mlx" and bool(repo) and name.lower() == repo.lower()))


def _matcher(ref: str, host: str, repo: str):
    if hf_parts(ref)[0]:
        model = hf_parts(ref)[1]
        return model, lambda v: refers_to_hf(v, model, repo)
    model = split_ref(ref)[0]
    return model, lambda v: refers_to(v, model, host)


def _tier_is_default(raw: dict, entry: dict) -> bool:
    from halo_harness.agents_yaml import DEFAULT_MODEL_REFERENCE
    from halo_harness.teams_yaml import tier_model_for
    return tier_model_for(raw, entry.get("as") or entry.get("role")) == DEFAULT_MODEL_REFERENCE


def _lineups(match, cwd, state_dir) -> list:
    from halo_harness.teams_yaml import list_team_templates, load_team_template_raw, member_model
    out = []
    for name in list_team_templates(cwd=cwd, state_dir=state_dir, include_templates=False):
        try:
            raw = load_team_template_raw(name, cwd=cwd, state_dir=state_dir) or {}
        except Exception:
            continue
        for entry in raw.get("agents") or []:
            if not isinstance(entry, dict):
                continue
            try:
                pref, fallback, src = member_model(raw, entry, cwd=cwd, state_dir=state_dir)
            except Exception:
                pref, fallback, src = "", "", ""
            if src == "session" or (src.startswith("tier:") and _tier_is_default(raw, entry)):
                pref = ""  # "the session's model": the default model's own use, counted once as `model`
            if match(pref) or match(fallback):
                out.append({"name": name, "role": str(entry.get("as") or entry.get("role") or entry.get("agent") or "?")})
    return out


def _live_rows() -> list:
    if "live" in READERS:
        return list(READERS["live"]() or [])
    try:
        from halo_harness.remote import registry
        rows = [r for r in registry.list_live() if isinstance(r, dict) and r.get("session_id")]
    except Exception:
        return []
    out = []
    for r in rows:
        model = r.get("model")
        if not model:
            try:
                from halo_harness.agent.sessions import _model_for, _read_nodes, sessions_dir
                model = _model_for(_read_nodes(sessions_dir(r.get("cwd")) / f"{r['session_id']}.jsonl"))
            except Exception:
                model = ""
        out.append({"session_id": r["session_id"], "title": r.get("title") or "", "model": model})
    return out


def line(u: dict) -> str:
    """'qwen3-coder:30b is the coder in `local-coder` and the model of 2 profiles; 1 live session is on it'."""
    parts = []
    by: dict = {}
    for x in u["lineups"]:
        by.setdefault(x["role"], []).append(f"`{x['name']}`")
    parts += [f"the {role} in {' and '.join(names)}" for role, names in by.items()]
    if u["roles"]:
        parts.append("the " + ", ".join(f"`{r}`" for r in u["roles"]) + (" role" if len(u["roles"]) == 1 else " roles"))
    if u["default_model"]:
        parts.append("the default model (`model`)")
    if u["compaction"]:
        parts.append("the compaction model (`compactionModel`)")
    if u.get("servers"):
        parts.append("named by huggingface.local_servers (" + ", ".join(f"`{n}`" for n in u["servers"]) + ")")
    if u["profiles"]:
        n = len(u["profiles"])
        parts.append(f"the model of {n} profile{'s' if n != 1 else ''}")
    head = u["model"] + (" is " + ", ".join(parts[:-1]) + (" and " if len(parts) > 1 else "") + parts[-1] if parts
                         else ": nothing Halo knows of uses it")
    live = u["live"]
    if live:
        on = f"{live} live session{'s are' if live != 1 else ' is'} on it"
        head = f"{head}; {on}" if parts else f"{u['model']}: {on}"
    return head


def _servers(model: str) -> list:
    """`huggingface.local_servers` entries that name the model (their `model` or `name`)."""
    from halo_harness.theme import get_config_value
    rows = get_config_value("huggingface.local_servers", default=None)
    return [str(e.get("name")) for e in rows if isinstance(e, dict) and model.lower() in
            (str(e.get("model") or "").lower(), str(e.get("name") or "").lower())] if isinstance(rows, list) else []


def uses_of(ref: str, *, cwd=None, state_dir=None, host: Optional[str] = None, repo: str = "") -> dict:
    from halo_harness.ollama_steward.profiles import all_profiles, split_key
    from halo_harness.providers.ollama import ollama_names_match
    from halo_harness.roles import configured_role_table
    from halo_harness.theme import get_config_value
    hf = bool(hf_parts(ref)[0])
    host = "" if hf else (host or split_ref(ref)[1] or _default_host())
    model, match = _matcher(ref, host, repo)
    roles = [k for k, v in configured_role_table().items() if match(v)]
    profiles = [k for k in sorted(all_profiles()) if (hf and split_key(k)[1].lower() == model.lower()) or (
        not hf and split_key(k)[0].lower() == host.lower() and ollama_names_match(split_key(k)[1], model))]
    sessions = [{"id": r["session_id"], "title": r.get("title") or "", "live": True} for r in _live_rows() if match(r.get("model"))]
    u = {"ref": f"hf:local/{model}" if hf else f"ol:{model}@{host}", "model": model, "host": host,
         "lineups": _lineups(match, cwd, state_dir), "roles": roles,
         "compaction": match(get_config_value("compactionModel", default=None)),
         "default_model": match(get_config_value("model", default=None)),
         "profiles": profiles, "sessions": sessions, "live": len(sessions), "servers": _servers(model) if hf else []}
    u["any"] = bool(u["lineups"] or roles or u["compaction"] or u["default_model"] or profiles or sessions or u["servers"])
    u["line"] = line(u)
    return u


__all__ = ["READERS", "hf_parts", "line", "refers_to", "refers_to_hf", "split_ref", "uses_of"]
