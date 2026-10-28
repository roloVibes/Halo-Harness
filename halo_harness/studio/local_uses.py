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
tag rule of providers/ollama.ollama_names_match. `READERS["live"]` replaces the
live-session reader (the tests' seam).
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


def _tier_is_default(raw: dict, entry: dict) -> bool:
    from halo_harness.agents_yaml import DEFAULT_MODEL_REFERENCE
    from halo_harness.teams_yaml import tier_model_for
    return tier_model_for(raw, entry.get("as") or entry.get("role")) == DEFAULT_MODEL_REFERENCE


def _lineups(model: str, host: str, cwd, state_dir) -> list:
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
            if refers_to(pref, model, host) or refers_to(fallback, model, host):
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


def uses_of(ref: str, *, cwd=None, state_dir=None, host: Optional[str] = None) -> dict:
    from halo_harness.ollama_steward.profiles import all_profiles, split_key
    from halo_harness.providers.ollama import ollama_names_match
    from halo_harness.roles import configured_role_table
    from halo_harness.theme import get_config_value
    model, h = split_ref(ref)
    host = host or h or _default_host()
    roles = [k for k, v in configured_role_table().items() if refers_to(v, model, host)]
    profiles = [k for k in sorted(all_profiles()) if split_key(k)[0].lower() == host.lower()
                and ollama_names_match(split_key(k)[1], model)]
    sessions = [{"id": r["session_id"], "title": r.get("title") or "", "live": True} for r in _live_rows()
                if refers_to(r.get("model"), model, host)]
    u = {"ref": f"ol:{model}@{host}", "model": model, "host": host,
         "lineups": _lineups(model, host, cwd, state_dir), "roles": roles,
         "compaction": refers_to(get_config_value("compactionModel", default=None), model, host),
         "default_model": refers_to(get_config_value("model", default=None), model, host),
         "profiles": profiles, "sessions": sessions, "live": len(sessions)}
    u["any"] = bool(u["lineups"] or roles or u["compaction"] or u["default_model"] or profiles or sessions)
    u["line"] = line(u)
    return u


__all__ = ["READERS", "line", "refers_to", "split_ref", "uses_of"]
