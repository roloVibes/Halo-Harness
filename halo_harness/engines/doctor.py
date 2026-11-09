"""halo_harness.engines.doctor -- `halo doctor --local`'s line per engine of the descriptor table that is found here:
its program on PATH or configured (`huggingface.engine_bins.<id>`, or the old `huggingface.<id>_bin`), or a server of
its runtime in the roster. A user with none of them gets no line. One short local command per engine found
(`<program> --version`), never a model, never the network; an engine that is missing or silent is a WARN with the
owner's install line for this OS, an old config word is said with the new one.

    found(engine, state_dir=None) -> "configured" | "path" | "running" | None
    steps(state_dir=None) -> [{step, ok, reason, elapsed_s, tag?}]
"""

from __future__ import annotations

from typing import Optional

from halo_harness.engines.descriptors import TABLE, install_line


def _running(engine: str, state_dir=None) -> list:
    try:
        from halo_harness.ollama_steward.servers_hf import roster
        return [s for s in roster(state_dir) if s.runtime == engine]
    except Exception:
        return []


def found(engine: str, state_dir=None) -> Optional[str]:
    from halo_harness.engines.adapter import binary
    _prefix, src = binary(engine)
    if src.startswith("huggingface."):
        return "configured"
    if _running(engine, state_dir):
        return "running"
    return "path" if src else None


def steps(state_dir=None) -> list:
    from halo_harness.doctor_local_ids import _step
    from halo_harness.engines import adapter as A
    out = []
    for engine, d in TABLE.items():
        how = found(engine, state_dir)
        if how is None:
            continue
        prefix, src = A.binary(engine)
        v = A.version(engine, prefix) if prefix else None
        servers = _running(engine, state_dir)
        where = "; serving: " + ", ".join(f"{s.name} at {s.url}" for s in servers[:3]) if servers else ""
        old = (f"; {src} is the old word: it is read as huggingface.engine_bins.{engine}"
               if src == A.old_key(engine) else "")
        tail = f" (its log patterns are unverified until a live run){where}{old}" if not d["verified"] else f"{where}{old}"
        if v:
            out.append(_step(f"engine {engine}", True, f"{d['label']}: {d['programs'][0]} --version {v} ({src}){tail}",
                             "WARN" if old else ""))
        else:
            head = "did not answer --version" if prefix else "has no program here"
            out.append(_step(f"engine {engine}", True, f"{d['label']} {head}: {install_line(d, A.os_word())}{tail}",
                             "WARN"))
    return out
