"""halo_harness.providers.effort_on -- Halo 3.3.5.0 R0 (e): what the effort
level does on THIS model.

    effort_on(ref, catalog_row, *, effort=None, explicit=True, think_choice=None)
        -> {kind: "levels" | "think" | "none", options, word}

- `levels` on a cloud route: the route's own levels (`options` from the
  provider profile when the caller passes them in the row, else the five
  named levels), `word` the level as today.
- `think` on an Ollama model with the `thinking` capability: Ollama's
  `think` field is the whole of it -- on / off (low and below is off,
  medium and above on), and gpt-oss takes low / medium / high. `word` is
  what the next call sends: `think on`, `think off`, `think high`, or
  `think default` when no field is sent (the model's own default).
- `none` on an Ollama model without the capability and on every Hugging Face
  local server (`huggingface_send.py` sends no effort field): `word` is
  `effort n/a`.

`models.think.<ref>` (on / off / default; low / medium / high on gpt-oss)
remembers a choice per model and wins over the effort level on a `think`
model (`think_choice`, read by `think_choice_for`).
"""

from __future__ import annotations

from typing import Optional

LEVELS = ("low", "medium", "high", "xhigh", "max")
THINK_OPTIONS = ("on", "off", "default")
GRADED_OPTIONS = ("low", "medium", "high", "default")
NA_WORD = "effort n/a"
CONFIG_KEY = "models.think"


def _thinks(catalog_row) -> Optional[bool]:
    """True / False from the row's capabilities or reasoning kind, None when the row says nothing."""
    row = catalog_row if isinstance(catalog_row, dict) else {}
    caps = row.get("capabilities")
    if isinstance(caps, (list, tuple)) and caps:
        return "thinking" in {str(c).lower() for c in caps}
    reasoning = row.get("reasoning")
    if isinstance(reasoning, dict) and reasoning.get("kind") in ("none", "native", "openai"):
        return reasoning["kind"] != "none"
    return None


def is_graded(model: str) -> bool:
    return "gpt-oss" in (model or "").lower()


def _local_kind(ref) -> str:
    provider = getattr(ref, "provider", "")
    if provider == "ollama":
        return "ollama"
    if provider == "local" or (provider == "huggingface" and (getattr(ref, "local", False) or getattr(ref, "mlx", False))):
        return "hf-local"
    return "cloud"


def think_choice_for(raw_ref: str) -> Optional[str]:
    """`models.think.<ref>` for this ref string (None when unset). Read as the
    whole mapping, since a ref carries dots of its own."""
    try:
        from halo_harness.theme import get_config_value
        table = get_config_value(CONFIG_KEY, default=None)
    except Exception:
        return None
    value = table.get(raw_ref) if isinstance(table, dict) else None
    return value if isinstance(value, str) and value in THINK_OPTIONS + GRADED_OPTIONS else None


def set_think_choice(raw_ref: str, value: Optional[str]) -> None:
    from halo_harness.theme import get_config_value, set_config_value, unset_config_value
    table = get_config_value(CONFIG_KEY, default=None)
    table = dict(table) if isinstance(table, dict) else {}
    if value is None:
        table.pop(raw_ref, None)
    else:
        table[raw_ref] = value
    if table:
        set_config_value(CONFIG_KEY, table)
    else:
        unset_config_value(CONFIG_KEY)


def think_value(effort: Optional[str], model: str, *, explicit: bool, think_choice: Optional[str]):
    """The `think` field a call to a thinking model sends (None: none sent)."""
    if think_choice == "default":
        return None
    if think_choice == "on":
        return "medium" if is_graded(model) else True
    if think_choice == "off":
        return "low" if is_graded(model) else False
    if think_choice in ("low", "medium", "high"):
        return think_choice if is_graded(model) else think_choice != "low"
    if not explicit:
        return None
    from halo_harness.providers.ollama import think_value_for_effort
    return think_value_for_effort(effort, model, supports_thinking=True)


def think_word(value) -> str:
    if value is None:
        return "think default"
    if value is True:
        return "think on"
    if value is False:
        return "think off"
    return f"think {value}"


def effort_on(ref, catalog_row=None, *, effort: Optional[str] = None, explicit: bool = True,
              think_choice: Optional[str] = None, levels=None) -> dict:
    """See the module docstring."""
    kind = _local_kind(ref)
    model = getattr(ref, "model", "") or ""
    if kind == "hf-local":
        return {"kind": "none", "options": [], "word": NA_WORD}
    if kind == "ollama":
        thinks = _thinks(catalog_row)
        if thinks is False:
            return {"kind": "none", "options": [], "word": NA_WORD}
        options = list(GRADED_OPTIONS if is_graded(model) else THINK_OPTIONS)
        value = think_value(effort, model, explicit=explicit, think_choice=think_choice)
        return {"kind": "think", "options": options, "word": think_word(value)}
    opts = list(levels) if levels else list(LEVELS)
    return {"kind": "levels", "options": opts, "word": effort or ""}


def none_answer(model_label: str) -> str:
    """`/effort` on a model whose effort does nothing."""
    return f"{model_label} has no adjustable effort: n/a (it would set think on/off on a thinking model)"


def cached_row(ref, env=None) -> Optional[dict]:
    """The Ollama catalog row already in this process's catalog cache (never a request)."""
    try:
        from halo_harness.providers import ollama as O
        from halo_harness.providers.ollama_hw import catalog_row
        host = O.resolve_ollama_host(getattr(ref, "host", None), env)
        if host is None:
            return None
        with O._CATALOG_LOCK:
            entry = O._CATALOG_CACHE.get(host.url)
        return catalog_row(entry[1], ref.model) if entry else None
    except Exception:
        return None


def local_word(session) -> Optional[str]:
    """The status bar's effort word on a local model (None on a cloud route: the level as today)."""
    if _local_kind(getattr(session, "model_ref", None)) == "cloud":
        return None
    try:
        return for_session(session)["word"]
    except Exception:
        return None


def for_session(session) -> dict:
    """`effort_on` for a live session's model (the catalog row from the cached catalog; no request)."""
    ref = getattr(session, "model_ref", None)
    row = None
    if getattr(ref, "provider", "") == "ollama":
        row = cached_row(ref, getattr(getattr(session, "settings", None), "effective_env", None))
        if row is None and getattr(session, "_ollama_supports_thinking", None) is not None:
            row = {"capabilities": ["thinking"] if session._ollama_supports_thinking else ["completion"]}
    profile = getattr(session, "provider_profile", None)
    return effort_on(ref, row, effort=getattr(session, "effort", None),
                     explicit=getattr(session, "effort_source", None) in ("flag", "session"),
                     think_choice=think_choice_for(getattr(ref, "raw", "") or ""),
                     levels=getattr(profile, "effort_values_supported", None))


def effort_command(session, args: str) -> Optional[str]:
    """`/effort` on a local model (None on a cloud route: `_cmd_effort` answers as before)."""
    ref = getattr(session, "model_ref", None)
    if session is None or _local_kind(ref) == "cloud":
        return None
    here = for_session(session)
    label = getattr(ref, "raw", "this model")
    asked = (args or "").strip().lower()
    stored = getattr(session, "effort", None)
    if here["kind"] == "none":
        if asked and asked not in THINK_OPTIONS:
            session.effort, session.effort_requested, session.effort_source = asked, asked, "session"
            return f"{none_answer(label)} -- '{asked}' is kept for the next model that can use it."
        tail = f" -- '{stored}' is kept for the next model that can use it." if stored else ""
        return none_answer(label) + tail
    options = ", ".join(here["options"])
    if not asked:
        choice = think_choice_for(label)
        why = f"models.think for this model: {choice}" if choice else \
            ("from the effort level" if here["word"] != "think default" else "no think field sent: the model's own default")
        return (f"Effort on {label}: {here['word']} ({why})\n"
                f"Options: {options} (an effort level works too: low turns thinking off, medium and above on)")
    if asked in here["options"]:
        set_think_choice(label, asked)
        now = for_session(session)["word"]
        return f"{label}: {now} -- saved as models.think[{label!r}]; takes effect on the next message."
    if asked in LEVELS or asked in ("none", "minimal"):
        session.effort, session.effort_requested, session.effort_source = asked, asked, "session"
        now = for_session(session)["word"]
        note = f" (models.think for this model, {think_choice_for(label)}, wins over the level)" if think_choice_for(label) else ""
        return f"Effort level set to '{asked}' on {label}: {now}{note} -- takes effect on the next message."
    return f"{label} takes: {options}, or an effort level ({', '.join(LEVELS)})."


def row_word(ref_raw: str, row: Optional[dict]) -> str:
    """A picker row's effort word: `think on/off` (`think low/medium/high` on gpt-oss) for a thinking
    local model, `effort n/a` for a local model whose effort does nothing, "" for a cloud row."""
    from types import SimpleNamespace
    raw = str(ref_raw or "")
    if raw.startswith("ol:"):
        provider, local = "ollama", False
    elif raw.startswith(("hf:local/", "hf:mlx/")):
        provider, local = "huggingface", True
    elif raw.startswith("local:"):
        provider, local = "local", False
    else:
        return ""
    model = raw.split(":", 1)[1].split("@", 1)[0]
    got = effort_on(SimpleNamespace(provider=provider, model=model, local=local, mlx=False, raw=raw), row)
    if got["kind"] == "think":
        return "think low/medium/high" if is_graded(model) else "think on/off"
    return got["word"]
