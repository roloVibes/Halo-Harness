"""halo_harness.providers.ollama_tune_store -- Halo 3.2.3.0 R3: Halo's own
record of each tuned twin it made, `twins` in `~/.halo/ollama-fit.json`
(beside R1's calibration entries; one small file of host+model facts):
`{"<host_url>|<twin>": {"origin", "window", "layers", "at"}}`. Read when a
server's `/api/show` leaves `details.parent_model` empty, and by the
listings for the window a twin was made at.
"""

from __future__ import annotations

import time
from typing import Optional


def _key(host_url: str, twin: str) -> str:
    from halo_harness.providers.ollama import normalize_ollama_model_name
    return f"{host_url}|{normalize_ollama_model_name(twin)}"


def record_twin(state_dir, *, host_url: str, twin: str, origin: str, window: int, layers: int) -> dict:
    from halo_harness.filelock import file_lock
    from halo_harness.providers.ollama_calibrate import _fit_store_path, load_fit_store, save_fit_store
    entry = {"origin": origin, "window": int(window), "layers": int(layers), "at": time.time()}
    with file_lock(_fit_store_path(state_dir)):
        store = load_fit_store(state_dir)
        twins = store.get("twins") if isinstance(store.get("twins"), dict) else {}
        twins[_key(host_url, twin)] = entry
        store["twins"] = twins
        save_fit_store(state_dir, store)
    return entry


def lookup_twin_record(state_dir, *, host_url: str, twin: str) -> Optional[dict]:
    from halo_harness.providers.ollama_calibrate import load_fit_store
    try:
        twins = load_fit_store(state_dir).get("twins")
    except Exception:
        return None
    entry = twins.get(_key(host_url, twin)) if isinstance(twins, dict) else None
    return entry if isinstance(entry, dict) and entry.get("origin") else None


def forget_twin(state_dir, *, host_url: str, twin: str) -> None:
    """Drops the twin's record and its calibration entry (the model is gone)."""
    from halo_harness.filelock import file_lock
    from halo_harness.providers.ollama import ollama_names_match
    from halo_harness.providers.ollama_calibrate import _fit_store_path, load_fit_store, save_fit_store
    with file_lock(_fit_store_path(state_dir)):
        store = load_fit_store(state_dir)
        twins = store.get("twins")
        if isinstance(twins, dict):
            twins.pop(_key(host_url, twin), None)
        store["entries"] = [e for e in store["entries"]
                            if not (isinstance(e, dict) and e.get("host_url") == host_url
                                    and ollama_names_match(e.get("model"), twin))]
        save_fit_store(state_dir, store)
