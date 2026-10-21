"""halo_harness.providers.model_row_facts -- what a catalog row states about a
model beyond price and context (Halo 3.1.9.0 R1, "what each model is good at").

`model_enumeration.build_model_rows` (the ONE row source) calls one reader per
provider here and `finish_rows` once at the end, so every model row carries
the same optional keys, each None when its source does not say (never
guessed):

  modalities_in   a subset of text, image, audio, video, pdf (OpenRouter's
                  "file" input is a PDF)
  modalities_out  a subset of text, image, audio
  tools           True / False (the catalog says) / None
  reasoning       {"kind": "none" | "native" | "openai", "efforts": [...]}
  open_weights    True / False / None
  local           `model.is_local_model_ref` for the row's ref
  measured        {gym, tools_probe, tools_rejected, ttft_s,
                  tokens_per_second, canary} or None when nothing was
                  measured here (providers/model_row_measured.py)

Sources: OpenRouter's models.json (input/output modalities, supported
parameters), models.dev (modalities, tool_call, open_weights, reasoning and
its options) for the Databricks, OpenAI and vendor-family rows, the
Experiential gateway's own catalog (tools, reasoning, efforts), the Hugging
Face router's provider rows (tools), the Anthropic table plus
`anthropic_caps`, and Ollama's `/api/show` capabilities list.
"""

from __future__ import annotations

from typing import Optional

ROW_KEYS = ("modalities_in", "modalities_out", "tools", "reasoning", "open_weights", "local", "measured")
MODALITIES = ("text", "image", "audio", "video", "pdf")
_SPELLINGS = {"file": "pdf", "document": "pdf", "vision": "image"}


def modalities(seq) -> Optional[list]:
    """A catalog's modality list -> the known subset in a fixed order; None
    for anything that is not a non-empty list of known names."""
    if not isinstance(seq, (list, tuple)):
        return None
    seen = set()
    for item in seq:
        name = str(item).strip().lower()
        seen.add(_SPELLINGS.get(name, name))
    out = [m for m in MODALITIES if m in seen]
    return out or None


def reasoning(kind: str, efforts=None) -> dict:
    return {"kind": kind, "efforts": [e for e in (efforts or []) if isinstance(e, str)]}


def models_dev_reasoning(entry: dict, *, kind: str = "native") -> Optional[dict]:
    """models.dev's `reasoning` bool plus the effort values its
    `reasoning_options` list (a `budget_tokens` option names no levels)."""
    stated = entry.get("reasoning") if isinstance(entry, dict) else None
    if not isinstance(stated, bool):
        return None
    if not stated:
        return reasoning("none")
    efforts: list = []
    for opt in entry.get("reasoning_options") or []:
        if isinstance(opt, dict) and opt.get("type") == "effort" and isinstance(opt.get("values"), list):
            efforts += [v for v in opt["values"] if isinstance(v, str) and v not in efforts]
    return reasoning(kind, efforts)


def models_dev_facts(entry, *, reasoning_kind: str = "native") -> dict:
    """One models.dev model entry -> the row keys it states."""
    if not isinstance(entry, dict):
        return {}
    mods = entry.get("modalities") if isinstance(entry.get("modalities"), dict) else {}
    out: dict = {}
    mi, mo = modalities(mods.get("input")), modalities(mods.get("output"))
    if mi:
        out["modalities_in"] = mi
    if mo:
        out["modalities_out"] = mo
    if isinstance(entry.get("tool_call"), bool):
        out["tools"] = entry["tool_call"]
    if isinstance(entry.get("open_weights"), bool):
        out["open_weights"] = entry["open_weights"]
    r = models_dev_reasoning(entry, kind=reasoning_kind)
    if r is not None:
        out["reasoning"] = r
    return out


def openrouter_facts(entry: dict) -> dict:
    """One models.json entry (OpenRouter `/models`, or its vendored fallback)."""
    pricing = entry.get("pricing") if isinstance(entry.get("pricing"), dict) else {}
    outs = entry.get("output_modalities")
    params = entry.get("supported_parameters")
    params = params if isinstance(params, list) and params else None
    image_out = bool(pricing.get("image_output")) or "image" in (outs if isinstance(outs, list) else [])
    return {
        "modalities_in": modalities(entry.get("input_modalities")),
        "modalities_out": modalities(outs) or (["text", "image"] if pricing.get("image_output") else None),
        "image_output": image_out,
        "tools": ("tools" in params) if params else None,
        "reasoning": (reasoning("openai" if any(p in params for p in ("reasoning", "include_reasoning")) else "none")
                      if params else None),
    }


def xp_facts(model_id: str, fields: dict) -> dict:
    """The Experiential gateway's own catalog fields (`xp_picker_fields`)."""
    out: dict = {}
    if "supports_tools" in fields:
        out["tools"] = bool(fields["supports_tools"])
    if "supports_reasoning" in fields:
        try:
            from halo_harness.providers.experiential import is_claude_slug
            claude = bool(is_claude_slug(model_id))
        except Exception:
            claude = False
        kind = ("native" if claude else "openai") if fields["supports_reasoning"] else "none"
        out["reasoning"] = reasoning(kind, fields.get("supported_reasoning_efforts"))
    return out


def hf_facts(entry: dict) -> dict:
    """A Hugging Face router entry: the provider row the router picks states tools."""
    providers = entry.get("providers") if isinstance(entry.get("providers"), list) else []
    if not providers:
        return {}
    try:
        from halo_harness.providers.huggingface_catalog import pick_best_provider_row
        best = pick_best_provider_row(providers) or {}
    except Exception:
        best = {}
    return {"tools": best["supports_tools"]} if isinstance(best.get("supports_tools"), bool) else {}


def ant_facts(model_id: str) -> dict:
    """An `ant:` id or alias: the Anthropic table (inputs) plus the family
    table (`anthropic_caps`: adaptive thinking and the effort levels). Tool
    use is part of the Messages API for every Claude model."""
    from halo_harness.providers.anthropic_aliases import ANT_ALIASES, ANT_INPUT_MODALITIES, profile_fields_for_ant_model
    from halo_harness.providers.anthropic_caps import capabilities
    from halo_harness.providers.profiles import ANTHROPIC_EFFORT_LEVELS, ANTHROPIC_EFFORT_LEVELS_XHIGH
    target = ANT_ALIASES.get(model_id, model_id)
    out: dict = {"tools": True, "open_weights": False, "modalities_out": ["text"]}
    fields = profile_fields_for_ant_model(target)
    if fields:
        out["modalities_in"] = list(ANT_INPUT_MODALITIES) if fields.get("vision", True) else ["text", "pdf"]
    try:
        caps = capabilities(target)
    except Exception:
        caps = {}
    if caps.get("adaptive_thinking"):
        out["reasoning"] = reasoning("native", ANTHROPIC_EFFORT_LEVELS_XHIGH if caps.get("effort_xhigh")
                                     else ANTHROPIC_EFFORT_LEVELS)
    elif caps:
        out["reasoning"] = reasoning("native")  # extended thinking with a token budget, no effort levels
    return out


def local_facts(capabilities_list, tools_probe: Optional[bool]) -> dict:
    """Ollama's `/api/show` capabilities list (vision / audio / tools /
    thinking) and the measured tool-call probe (`ollama_capability`)."""
    out: dict = {}
    if isinstance(capabilities_list, (list, tuple)) and capabilities_list:
        caps = {str(c).lower() for c in capabilities_list}
        out["modalities_in"] = [m for m, cap in (("text", None), ("image", "vision"), ("audio", "audio"))
                                if cap is None or cap in caps]
        out["modalities_out"] = ["text"]
        out["tools"] = "tools" in caps
        out["reasoning"] = reasoning("native" if "thinking" in caps else "none")
    if tools_probe is not None:
        out["measured"] = {"tools_probe": bool(tools_probe)}
    return out


def fill(row: dict, facts: dict, *, only_missing: bool = False) -> dict:
    """Merge `facts` into `row` (None values never overwrite a stated one)."""
    for key, value in (facts or {}).items():
        if value is None or (only_missing and row.get(key) is not None):
            continue
        row[key] = value
    return row


def finish_rows(rows: list, state_dir, *, speeds: Optional[dict] = None) -> None:
    """Every model row gets every `ROW_KEYS` key; `local` from
    `is_local_model_ref`; `measured` from the files this host keeps."""
    from halo_harness.model import is_local_ref_string
    from halo_harness.providers.model_row_measured import measured_index
    try:
        measured = measured_index(state_dir, rows, speeds=speeds or {})
    except Exception:
        measured = {}
    for row in rows:
        ref = row.get("ref")
        if not ref:
            continue
        for key in ROW_KEYS:
            row.setdefault(key, None)
        if row.get("provider") == "alias":
            continue
        row["local"] = is_local_ref_string(ref)
        row["measured"] = measured.get(ref)
