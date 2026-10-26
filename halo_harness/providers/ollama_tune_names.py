"""halo_harness.providers.ollama_tune_names -- Halo 3.2.3.0 R3: a tuned
twin's name rule and its marker (re-exported by `providers.ollama_tune`).

`twin_name`: `-halo` is appended to the model's name and the tag is kept
(`qwen3.8:27b` -> `qwen3.8-halo:27b`, `qwen3` -> `qwen3-halo:latest`).
`twin_origin`: what `/api/show` keeps of a twin -- `details.parent_model`
(Ollama's record of the `from` model), `parameters` with both `num_ctx`
and `num_gpu`, and the name following the rule; Halo's own record stands
in for `parent_model` when a server leaves it empty.
"""

from __future__ import annotations

from typing import Optional

TWIN_SUFFIX = "-halo"


def _split(model: str) -> "tuple[str, str]":
    name = (model or "").strip()
    slash = name.rfind("/")
    colon = name.rfind(":")
    if colon > slash:
        return name[:colon], name[colon + 1:] or "latest"
    return name, "latest"


def short_name(model: Optional[str]) -> str:
    """`registry.ollama.ai/library/qwen3:8b` -> `qwen3:8b`; always tagged."""
    name = (model or "").strip()
    for prefix in ("registry.ollama.ai/", "library/"):
        if name.startswith(prefix):
            name = name[len(prefix):]
    base, tag = _split(name)
    return f"{base}:{tag}" if base else ""


def twin_name(model: str) -> str:
    """`<name>-halo:<tag>` (see the module docstring); a name that already
    follows the rule is returned as it is."""
    base, tag = _split(short_name(model))
    if base.endswith(TWIN_SUFFIX):
        return f"{base}:{tag}"
    return f"{base}{TWIN_SUFFIX}:{tag}"


def origin_from_twin_name(name: str) -> Optional[str]:
    """The original a twin's NAME points at (`qwen3.8-halo:27b` ->
    `qwen3.8:27b`), None when the name does not follow the rule."""
    base, tag = _split(short_name(name))
    if not base.endswith(TWIN_SUFFIX) or len(base) == len(TWIN_SUFFIX):
        return None
    return f"{base[:-len(TWIN_SUFFIX)]}:{tag}"


def parse_parameters(text) -> "dict[str, str]":
    """`/api/show`'s `parameters` text (`num_ctx    65536` per line) as a
    dict of name -> the value text (quotes dropped); the last line wins."""
    out: "dict[str, str]" = {}
    for line in str(text or "").splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2:
            out[parts[0]] = parts[1].strip().strip('"')
    return out


def _int(value) -> Optional[int]:
    try:  # Ollama prints a JSON number with Go's %v: "65536", read "65536.0" / "6.5536e+04" too
        n = int(float(str(value).strip()))
    except (TypeError, ValueError, OverflowError):
        return None
    return n if n > 0 else None


def twin_origin(show, *, name: Optional[str] = None, record: Optional[dict] = None) -> Optional[str]:
    """The original `show` (an `/api/show` body) is a tuned twin of, or
    None. A twin carries `num_ctx` and `num_gpu` in its parameters and an
    origin -- `details.parent_model`, else Halo's own `record` -- whose
    `twin_name` is `name` (when given)."""
    if not isinstance(show, dict):
        return None
    params = parse_parameters(show.get("parameters"))
    if _int(params.get("num_ctx")) is None or _int(params.get("num_gpu")) is None:
        return None
    candidates = [(show.get("details") or {}).get("parent_model") if isinstance(show.get("details"), dict) else None,
                  (record or {}).get("origin")]
    for origin in candidates:
        origin = short_name(origin) if origin else ""
        if not origin or origin_from_twin_name(origin):
            continue
        if name is None or short_name(twin_name(origin)) == short_name(name):
            return origin
    return None


def is_twin(show, *, name: Optional[str] = None, record: Optional[dict] = None) -> bool:
    return twin_origin(show, name=name, record=record) is not None


def k_window(n: Optional[int]) -> str:
    return f"{int(n) // 1000}k" if isinstance(n, int) and n > 0 else "?"


def twin_note(origin: str, window: Optional[int]) -> str:
    """"tuned twin of qwen3.8:27b (65k window, all layers on the GPU)"."""
    return f"tuned twin of {origin} ({k_window(window)} window, all layers on the GPU)"
