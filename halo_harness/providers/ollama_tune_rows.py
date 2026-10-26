"""halo_harness.providers.ollama_tune_rows -- Halo 3.2.3.0 R3: where tuned
twins show. `catalog_twin_fields` gives an Ollama catalog row its `twin_of`
(and the window and layer count the twin carries); `twin_order` puts each
twin beside its original -- before it for the pickers (`/model`, Studio's
Models rows through `local_models`: the twin is the one to pick), after it
for the listings (`halo ollama`, `halo local`: the twin under its original).
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

log = logging.getLogger("bridge")


def catalog_twin_fields(host, name: str, show, *, state_dir=None) -> dict:
    """`{"twin_of", "twin_window", "twin_layers"}` when `show` (the model's
    `/api/show`) is a tuned twin, else `{}`. Never raises."""
    try:
        from halo_harness.providers.ollama_tune_names import _int, parse_parameters, twin_origin
        from halo_harness.providers.ollama_tune_store import lookup_twin_record
        if state_dir is None:
            from halo_harness.config.paths import bridge_home
            state_dir = bridge_home()
        record = lookup_twin_record(state_dir, host_url=host.url, twin=name)
        origin = twin_origin(show, name=name, record=record)
        if not origin:
            return {}
        params = parse_parameters((show or {}).get("parameters"))
        return {"twin_of": origin, "twin_window": _int(params.get("num_ctx")),
                "twin_layers": _int(params.get("num_gpu"))}
    except Exception:
        log.debug("ollama: twin fields for %s failed", name, exc_info=True)
        return {}


def twin_order(items: list, *, key: "Callable[[object], Optional[str]]",
               twin_of: "Callable[[object], Optional[str]]", twin_first: bool = True) -> list:
    """`items` with every twin moved next to its original -- right before
    it (`twin_first`) or right after it. `key(item)` is the item's own
    name, `twin_of(item)` its original's (None for an original); both
    compared through `normalize_ollama_model_name`. A twin whose original
    is not in `items` keeps its place; every other order is unchanged."""
    from halo_harness.providers.ollama import normalize_ollama_model_name as norm
    names = {norm(key(i)) for i in items if key(i)}
    twins: "dict[str, list]" = {}
    for item in items:
        origin = norm(twin_of(item)) if twin_of(item) else None
        if origin and origin in names and origin != norm(key(item)):
            twins.setdefault(origin, []).append(item)
    out: list = []
    for item in items:
        origin = norm(twin_of(item)) if twin_of(item) else None
        if origin and origin in names and origin != norm(key(item)):
            continue  # placed beside its original below
        mine = twins.get(norm(key(item)) if key(item) else "", [])
        out.extend(mine if twin_first else [])
        out.append(item)
        out.extend([] if twin_first else mine)
    return out


def _ref_name(ref: Optional[str]) -> Optional[str]:
    """`ol:qwen3-halo:8b@pc` -> `qwen3-halo:8b`."""
    if not ref or not ref.startswith("ol:"):
        return None
    return ref[3:].rsplit("@", 1)[0] if "@" in ref else ref[3:]


def picker_twins_first(members: "list[dict]") -> "list[dict]":
    """The `/model` picker's rows of one group with each twin (a row with
    `twin_of`) right before its original -- whatever the sort key."""
    return twin_order(members, key=lambda m: _ref_name(m.get("ref")), twin_of=lambda m: m.get("twin_of"),
                      twin_first=True)
