"""halo_harness.packs.bio_models -- a bio's model by what it needs (Halo
3.2.0.0 R2, docs/PACKS.md "A pack's bios").

A pack never names one provider: its bio says `models.capabilities: [<tag>,
...]` and, optionally, a bare family name in `models.preference`
(`claude-sonnet`). At load (`agents_yaml.resolve_agent_bio`) the bio runs on
the best catalog model carrying every tag -- a model of that family first --
and on your `default` model when none does (the bio says so in `_model`:
"no model in the catalog has long-context"). The same works in a bio of your
own (a pack bio you cloned keeps the line); there a full model ref in
`models.preference` is a pin and wins.

    TAGS                                  # tag -> what it means
    row_tags(row)                         # the tags one catalog row carries
    provider_word(ref)                    # "" for a family name or `default`, else what pins it to one provider
    pick(models, rows=...)                # {"capabilities", "prefer", "ref", "how", "problem"} or None
    apply(resolved_bio, cwd=, state_dir=) # in place: models.preference and `_model`

The catalog is Studio's (`studio.model.model_rows`, the session's provider
resolution), read from the cache files only (no network), kept 60 s per home.
Tests set `ROWS` to a callable `(state_dir, cwd) -> rows`.
"""

from __future__ import annotations

import re
import threading
import time
from typing import Callable, Optional

from halo_harness.capabilities import _ctx, _tier, capability_profile

#: The tags a bio may ask for, each read from a fact the catalog states (never guessed).
TAGS = {
    "long-context": "a context window of 200k tokens or more",
    "vision": "reads images",
    "audio": "listens to audio",
    "video": "watches video",
    "files": "reads files (PDFs and the like)",
    "image-out": "makes images",
    "tools": "calls tools",
    "local": "runs on this machine or the LAN (Ollama, a local Hugging Face model)",
    # 3.2.1.0 R1: three more facts 3.1.9.0 R1's enriched catalog rows state (providers/model_row_facts.py)
    "reasoning": "thinks before it answers (its row's reasoning kind is native or openai)",
    "open-weights": "its weights are published (you could run it yourself)",
    "audio-out": "speaks (audio among what it puts out)",
}
LONG_CONTEXT = 200_000
_PREFIX_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*):")
_TTL_S = 60.0
ROWS: "Optional[Callable]" = None
_cache: dict = {}
_lock = threading.Lock()


def row_tags(row: dict) -> "set[str]":
    prof = capability_profile(row)
    tags = {t for t, key in (("vision", "vision"), ("audio", "audio"), ("video", "video"), ("files", "files"),
                             ("image-out", "image_out")) if prof.get(key)}
    if _ctx(row) >= LONG_CONTEXT:
        tags.add("long-context")
    if row.get("tools") is True:
        tags.add("tools")
    reasoning = row.get("reasoning")
    if isinstance(reasoning, dict) and str(reasoning.get("kind") or "none") != "none":
        tags.add("reasoning")
    if row.get("open_weights") is True:
        tags.add("open-weights")
    out = row.get("modalities_out")
    if isinstance(out, (list, tuple, set)) and "audio" in out:
        tags.add("audio-out")
    # the row's own `local` when it states one (Studio's rows always do: a Hugging Face router row is remote);
    # the provider only for a row without the key
    if (bool(row["local"]) if "local" in row else row.get("provider") in ("ollama", "huggingface")):
        tags.add("local")
    return tags


def provider_word(ref) -> str:
    """What makes `ref` one provider's: its route prefix, a vendor/model path, a Databricks name; '' otherwise."""
    if not isinstance(ref, str) or not ref.strip():
        return ""
    ref = ref.strip()
    m = _PREFIX_RE.match(ref)
    if m:
        return f"the {m.group(1)}: route"
    if "/" in ref:
        return "a vendor/model path (one provider's catalog)"
    if ref.startswith(("databricks-", "system.ai.")):
        return "a Databricks endpoint name"
    return ""


def tags_of(models) -> "list[str]":
    caps = (models or {}).get("capabilities") if isinstance(models, dict) else None
    if isinstance(caps, str):
        caps = [caps]
    return [c.strip() for c in caps if isinstance(c, str) and c.strip()] if isinstance(caps, list) else []


def unknown_tags(tags) -> "list[str]":
    return [t for t in tags if t not in TAGS]


def catalog_rows(state_dir=None, cwd=None) -> list:
    """The catalog rows (Studio's shape), cached 60 s per home and folder; [] when it cannot be read."""
    if ROWS is not None:
        return list(ROWS(state_dir, cwd) or [])
    from pathlib import Path
    from halo_harness.config.paths import bridge_home
    home = Path(state_dir or bridge_home())
    key = (str(home), str(cwd or ""), tuple(_mtime(home / f) for f in ("models.json", "dbx-endpoints.json", "routes.json")))
    with _lock:
        hit = _cache.get(key)
    if hit is not None and time.monotonic() - hit[0] < _TTL_S:
        return hit[1]
    try:
        from halo_harness.studio.model import model_rows
        rows = model_rows(state_dir, cwd)
    except Exception:  # a broken catalog never breaks a bio: it falls back to the default model
        rows = []
    with _lock:
        if len(_cache) > 16:
            _cache.clear()
        _cache[key] = (time.monotonic(), rows)
    return rows


def _mtime(path) -> int:
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return 0


def forget() -> None:
    with _lock:
        _cache.clear()


def _family(ref: str) -> str:
    """`or:anthropic/claude-sonnet-4.5` -> `anthropic/claude-sonnet-4.5` (lower-case), for a family match."""
    m = _PREFIX_RE.match(ref)
    return (ref[m.end():] if m else ref).lower()


def _default_ref() -> str:
    from halo_harness.theme import get_config_value
    real = get_config_value("model", default=None)
    return real.strip() if isinstance(real, str) and real.strip() else "default"


def pick(models, *, rows: "Optional[list]" = None, state_dir=None, cwd=None) -> "Optional[dict]":
    """The model a bio's `models` section resolves to by its tags; None when it asks for none.

    `how`: "preference" (a full ref of your own pins it), "capabilities" (the best row with every tag),
    "default" (none has them: your default model, and `problem` says which tags)."""
    tags = tags_of(models)
    if not tags:
        return None
    pref = models.get("preference") if isinstance(models.get("preference"), str) else ""
    pref = pref.strip()
    info = {"capabilities": tags, "prefer": "", "ref": "", "how": "", "problem": ""}
    if pref and pref != "default" and provider_word(pref):
        return {**info, "ref": pref, "how": "preference"}
    info["prefer"] = "" if pref == "default" else pref
    rows = catalog_rows(state_dir, cwd) if rows is None else rows
    want = set(tags)
    fits = [r for r in rows if r.get("ref") and r.get("provider") != "alias" and want <= row_tags(r)]
    family = [r for r in fits if info["prefer"] and info["prefer"].lower() in _family(str(r["ref"]))]
    ranked = sorted(family or fits, key=lambda r: (-_tier(r)[0], -_ctx(r), str(r["ref"])))
    if ranked:
        return {**info, "ref": str(ranked[0]["ref"]), "how": "capabilities"}
    default = _default_ref()
    shown = ", ".join(tags)
    return {**info, "ref": default, "how": "default",
            "problem": f"no model in the catalog has {shown} (it runs on your default model, {default})"}


def chain_preference(name: str, *, cwd=None, state_dir=None) -> str:
    """The `models.preference` the bio's own file names, else its nearest `extends` parent's, as written
    (before a parent's tags or `default` became a model); '' when none does."""
    from halo_harness.agents_yaml import load_agent_bio_raw
    seen: "list[str]" = []
    while name and name not in seen:
        seen.append(name)
        raw = load_agent_bio_raw(name, cwd=cwd, state_dir=state_dir)
        if raw is None:
            return ""
        models = raw.get("models") if isinstance(raw.get("models"), dict) else {}
        if isinstance(models.get("preference"), str) and models["preference"].strip():
            return models["preference"].strip()
        parent = raw.get("extends")
        name = parent.strip() if isinstance(parent, str) else ""
    return ""


def apply(bio: dict, *, cwd=None, state_dir=None, rows: "Optional[list]" = None) -> dict:
    """`bio` (resolved) with `models.preference` set from its tags and `_model` attached; unchanged without tags.
    The preference read is the one the files name (`chain_preference`), never a parent's resolved model."""
    models = bio.get("models") if isinstance(bio.get("models"), dict) else None
    if not models or not tags_of(models):
        return bio
    written = chain_preference(str(bio.get("name") or ""), cwd=cwd, state_dir=state_dir)
    models = {k: v for k, v in models.items() if k != "preference"}
    if written:
        models["preference"] = written
    info = pick(models, rows=rows, state_dir=state_dir, cwd=cwd)
    if info is None:
        return bio
    bio["models"] = {**models, "preference": info["ref"]}
    bio["_model"] = info
    return bio


def describe(info: "Optional[dict]", preference: str = "") -> str:
    """One line: what the bio runs on and why (`halo pack inspect`, `halo agents show`)."""
    if not info:
        return preference or "the session model"
    tags = ", ".join(info.get("capabilities") or [])
    if info.get("how") == "capabilities":
        family = f", family {info['prefer']}" if info.get("prefer") else ""
        return f"{info['ref']} (the best catalog model with {tags}{family})"
    if info.get("how") == "preference":
        return f"{info['ref']} (its models.preference; it also asks for {tags})"
    return f"{info['ref']} ({info.get('problem') or 'your default model'})"
