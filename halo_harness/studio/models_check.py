"""halo_harness.studio.models_check -- `GET models/check?ref=<ref>` (Halo 3.4.1.3 "Pick, don't type").

The model picker's last row, "use a reference that is not listed", checks what you type as you type it, against the
same parser a session uses (`model.parse_model_ref`, with routes.json's aliases): it answers

    {ok, ref, provider, model, line, prefixes}

`line` is one plain sentence: "or: OpenRouter, model vendor/model" when the route parses, else why not -- a prefix
Halo does not know names the ones it does. Nothing is called: no provider request, no network.
"""
from __future__ import annotations

import re

# The route prefixes a reference may start with, and what each reaches (docs/MODELS-references.md).
PREFIXES = (
    ("or:", "OpenRouter"), ("dbx:", "Databricks"), ("ant:", "Anthropic"), ("oai:", "the OpenAI API"),
    ("ol:", "Ollama"), ("hf:", "Hugging Face"), ("xp:", "Experiential Labs"), ("cp:", "your work's Copilot"),
    ("local:", "a local server"),
)
_PROVIDER_WORDS = {"openrouter": "OpenRouter", "databricks": "Databricks", "anthropic": "Anthropic", "openai": "the OpenAI API",
                   "ollama": "Ollama", "huggingface": "Hugging Face", "experiential": "Experiential Labs", "copilot": "your work's Copilot"}
_PREFIX_SHAPE = re.compile(r"^([a-z]{1,8}):")


def _routes(state_dir) -> dict:
    try:
        from halo_harness.providers.config import load_routes
        path = state_dir / "routes.json" if state_dir is not None and (state_dir / "routes.json").exists() else None
        got = load_routes(path)
        return got if isinstance(got, dict) else {}
    except Exception:
        return {}


def known_prefixes() -> "list[str]":
    return [p for p, _ in PREFIXES]


def check_ref(ref: str, state_dir=None) -> dict:
    """One reference checked by the session's own parser: ok, the provider and model it reaches, or why not."""
    ref = (ref or "").strip()
    out = {"ok": False, "ref": ref, "provider": "", "model": "", "line": "", "prefixes": known_prefixes()}
    if not ref:
        out["line"] = "type a reference, e.g. or:vendor/model or ol:name:tag"
        return out
    if any(ch.isspace() for ch in ref):
        out["line"] = "a reference has no spaces"
        return out
    m = _PREFIX_SHAPE.match(ref)
    known = known_prefixes() + ["databricks-", "system.ai."]
    if m and m.group(0) not in known_prefixes() and not ref.startswith(("http:", "https:")):
        out["line"] = f"{m.group(0)} is not a prefix Halo knows; the prefixes are {', '.join(known_prefixes())}"
        return out
    try:
        from halo_harness.model import parse_model_ref
        parsed = parse_model_ref(ref, _routes(state_dir))
    except Exception as e:  # InvalidModelError, a provider turned off: the parser's own sentence
        text = str(e).strip() or type(e).__name__
        hint = "" if any(p in text for p in known) else f" (the prefixes are {', '.join(known_prefixes())})"
        out["line"] = text + hint
        return out
    provider = str(getattr(parsed, "provider", "") or "")
    model = str(getattr(parsed, "model", "") or "")
    out.update(ok=True, provider=provider, model=model,
               line=f"{_PROVIDER_WORDS.get(provider, provider or 'a route')}, model {model or ref}")
    return out


def get_models_check(req):
    return 200, check_ref(str(req.query.get("ref") or ""), getattr(req, "state_dir", None))
