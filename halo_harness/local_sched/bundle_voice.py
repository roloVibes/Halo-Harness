"""halo_harness.local_sched.bundle_voice -- a bundle's speech needs, resolved through the speech catalog and what is
on disk (Halo 3.3.9.0 R1; docs/MODELS-bundles.md "Speech needs"; voice/catalog.py, voice/install.py).

    pick(role, need) -> Pick      bundle_needs.pick's speech branch, the Pick shape of an Ollama need plus
                                  {present, cpu_gb, says, command}
    place(picks, *, free, total, reserve_gb, coder_gb) -> None   a `cpu-or-gpu` need goes on the GPU when its GPU
                                  figure fits beside the bundle and the coder, else it stays on the CPU (the options'
                                  "GPU STT ... would break that" line says why)
    tail(picks) -> "; stt (...) and tts (...) on the CPU: no VRAM; stt: faster-whisper:small.en present (0.5 GB on the
                    GPU, 0.9 GB on the CPU); tts: not present -- halo voice download kokoro-82m (0.34 GB)"

The model a need takes: on the CPU the smallest of its any_of, on the GPU the first; a present one of the any_of
before an absent one, in that order. Present: its footprint on the device the need allows (`cpu` -> the CPU figure,
no VRAM; `gpu` -> the GPU figure). Absent: "not present -- `halo voice download <model>` (N GB)", one download of the
verdict (the class a missing Ollama model gets). A name the catalog does not hold is said so, never sized.
"""

from __future__ import annotations

from typing import Optional


def _order(names: list, on_cpu: bool) -> list:
    from halo_harness.voice.catalog import get
    if not on_cpu:
        return list(names)
    return sorted(names, key=lambda n: (get(n).cpu_gb if get(n) else 99.0, names.index(n)))


def pick(role: str, need: dict) -> dict:
    from halo_harness.models_library.advise_lines import cost
    from halo_harness.voice.catalog import footprint, get
    from halo_harness.voice.install import present
    names = list(need.get("any_of") or [])
    on_cpu = need.get("device") in ("cpu", "cpu-or-gpu")
    order = _order(names, on_cpu)
    here = {n: present(n) is not None for n in names if get(n) is not None}
    model = next((n for n in order if here.get(n)), None) or (order[0] if order else "")
    row = get(model)
    first = get(names[0]) if names else None
    out = {"role": role, "model": model or None, "runtime": "voice", "device": need.get("device"),
           "placed": "cpu" if on_cpu else "gpu", "window": None, "gpu_model": names[0] if names else None,
           "gpu_gb": first.gpu_gb if first else None, "smaller": [], "minutes": 0, "cpu_gb": row.cpu_gb if row else None,
           "need": dict(need)}
    if row is None:
        return {**out, "installed": None, "present": None, "gb": None if not on_cpu else 0.0, "download_gb": None,
                "why": f"{model or 'no model'}: not in the speech catalog (halo voice models lists it)", "command": None}
    ok = bool(here.get(model))
    dl = 0.0 if ok else row.download_gb
    says = f"{model} present ({footprint(row)})" if ok else \
        f"not present -- halo voice download {model} ({row.download_gb:g} GB)"
    return {**out, "installed": ok, "present": ok, "gb": 0.0 if on_cpu else row.gpu_gb, "download_gb": dl,
            "minutes": 0 if ok else cost(dl, None, None, None)["minutes"], "why": says, "says": says,
            "command": None if ok else f"halo voice download {model}"}


def place(picks: dict, *, free: float, total: float, reserve_gb: float, coder_gb: Optional[float]) -> float:
    """A `cpu-or-gpu` speech need takes its GPU pick (the first of its any_of) when that fits beside the bundle and the
    coder; returns the new GPU total."""
    for role, p in list(picks.items()):
        if p.get("runtime") != "voice" or p.get("device") != "cpu-or-gpu" or not p.get("gpu_gb"):
            continue
        if total + float(p["gpu_gb"]) + float(coder_gb or 0) <= free:
            on = pick(role, {**(p.get("need") or {}), "device": "gpu"})
            if p.get("installed") and not on.get("installed"):
                continue  # the GPU would ask a download the CPU pick does not need
            picks[role] = {**on, "device": "cpu-or-gpu"}
            total += float(on.get("gb") or 0)
    return total


def tail(picks: dict) -> str:
    voice = [p for p in picks.values() if p.get("runtime") == "voice"]
    if not voice:
        return ""
    cpu = [p for p in voice if p["placed"] == "cpu" and p.get("model")]
    out = (f"; {' and '.join('%s (%s)' % (p['role'], p['model']) for p in cpu)} on the CPU: no VRAM" if cpu else "")
    return out + "".join(f"; {p['role']}: {p['why']}" for p in voice)
