"""halo_harness.ollama_steward.fingerprint_hf -- Halo 3.3.8.0 R2: what a crash fingerprint carries beyond 3.3.6.0's
facts (fingerprints.record calls `stamp` on each new one):

- `digest`: the build the model ran as -- an Ollama tag's digest when the crash was on an Ollama host
  (tag_digests.current), the model file's identity for a local server Halo started ("file:<sha1 of path, size, mtime>"
  from the registry's model_path) -- so a repeat is counted on one build (fingerprints.KEY) and a crash on a build the
  tag no longer has is judged stale (`same_build`), never by its age alone;
- `runtime` (llama-server | lmstudio | mlx) and `load_cmd`, the command Halo launched the server with, for a crash in a
  local server's log (server_log_hf.py puts both on the event).

    stamp(fp, ev, state_dir, host) -> fp
    digest_of(state_dir, host, model, data=None) -> str | None
    same_build(state_dir, fp) -> True | False | None (None: no digest on one side)
"""

from __future__ import annotations

import hashlib
import os
from typing import Optional


def _file_id(path) -> Optional[str]:
    try:
        st = os.stat(path)
    except (OSError, TypeError, ValueError):
        return None
    raw = f"{os.path.abspath(str(path))}|{st.st_size}|{int(st.st_mtime)}"
    return "file:" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _registry_path_of(state_dir, host) -> Optional[str]:
    try:
        from halo_harness.ollama_steward.servers_hf import by_name
        from halo_harness.providers.local_runtime import load_registry
        s = by_name(host, state_dir)
        if s is None or not s.id:
            return None
        row = next((e for e in load_registry(state_dir) if e.get("id") == s.id), None)
        return (row or {}).get("model_path") or None
    except Exception:
        return None


def digest_of(state_dir, host, model, data: Optional[dict] = None) -> Optional[str]:
    if state_dir is None or not host:
        return None
    if (data or {}).get("runtime"):
        p = _registry_path_of(state_dir, host)
        return _file_id(p) if p else None
    try:
        from halo_harness.ollama_steward.tag_digests import current
        return current(state_dir, host, model) if model else None
    except Exception:
        return None


def stamp(fp: dict, ev: dict, state_dir, host) -> dict:
    data = ev.get("data") or {}
    if data.get("runtime"):
        fp["runtime"] = data["runtime"]
    if data.get("launch") and not fp.get("load_cmd"):
        fp["load_cmd"] = data["launch"][:300]
        fp["facts_from"] = (fp.get("facts_from") or "the host card") + "; the command Halo launched it with"
    fp["digest"] = digest_of(state_dir, host, fp.get("model"), data)
    return fp


def same_build(state_dir, fp: dict) -> Optional[bool]:
    """Is the model the fingerprint names still the build it crashed on? None when either digest is unknown."""
    had = fp.get("digest")
    if not had:
        return None
    now = digest_of(state_dir, fp.get("host"), fp.get("model"), {"runtime": fp.get("runtime")} if fp.get("runtime") else None)
    return None if not now else now == had
