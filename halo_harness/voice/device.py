"""halo_harness.voice.device -- where a speech server runs (Halo 3.3.9.0 R1; docs/VOICE.md "The device"):

    choose(row, asked=None) -> {device, gpu_free_mib, cuda_free_mib (the free MiB when the engines see CUDA), line}
        asked: --device auto | cpu | cuda, else voice.device, else auto. auto is CUDA when the engines see a CUDA device
        (engines.devices()) and this machine's card (the hardware card of the Ollama host served here) has the
        model's GPU footprint free, else the CPU -- said in one line either way:
        "faster-whisper:small.en on the CPU: 0.9 GB RAM, the GPU keeps its 22,000 MiB for the chat model"
    gpu_free_mib() -> the card's free MiB (its budget minus the models loaded on it), or None with no card

Reads only: the card through local_sched/facts (a fixture reader in tests), never a request to a model.
"""

from __future__ import annotations

from typing import Optional

MIB = 2 ** 20


def _asked(asked: Optional[str]) -> str:
    if asked in ("auto", "cpu", "cuda"):
        return asked
    try:
        from halo_harness.theme import get_config_value
        v = str(get_config_value("voice.device", default=None) or "auto").lower()
    except Exception:
        v = "auto"
    return v if v in ("auto", "cpu", "cuda") else "auto"


def gpu_free_mib() -> Optional[int]:
    try:
        from halo_harness.peers.ollama_share import served_here
        from halo_harness.local_sched import facts as F
        from halo_harness.providers.ollama import resolve_ollama_hosts
        host = next((h for h in resolve_ollama_hosts() if served_here(h.url)), None)
        card = F.card(host) if host is not None else {}
        if not card or not card.get("gpus"):
            return None
        b = F.budget(card, host.name)
        used = sum(int(r.get("size_vram") or 0) for r in card.get("loaded") or [] if isinstance(r, dict))
        return max(0, int(b.get("budget") or 0) - used) // MIB
    except Exception:
        return None


def choose(row, asked: Optional[str] = None, *, free_mib: Optional[int] = -1, seen: Optional[list] = None) -> dict:
    """`free_mib` / `seen` stand in for the card and the engines' devices (tests); -1 / None read them."""
    from halo_harness.voice.engines import devices
    seen = devices() if seen is None else seen
    out = _choose(row, _asked(asked), gpu_free_mib() if free_mib == -1 else free_mib, seen)
    out["cuda_free_mib"] = out["gpu_free_mib"] if "cuda" in seen else None  # the load line's: voice-cpu reads it
    return out


def _choose(row, want: str, free: Optional[int], seen: list) -> dict:
    need = int(round(row.gpu_gb * 1e9 / MIB))
    keeps = f", the GPU keeps its {free:,} MiB for the chat model" if isinstance(free, int) else ""
    cpu = f"{row.name} on the CPU: {row.cpu_gb:g} GB RAM{keeps}"
    gpu = f"{row.name} on the GPU: {row.gpu_gb:g} GB" + (f" of its {free:,} MiB free" if isinstance(free, int) else "")
    if want == "cpu":
        return {"device": "cpu", "gpu_free_mib": free, "line": cpu + " (--device cpu)"}
    if want == "cuda":
        tail = "" if "cuda" in seen else "; the engines see no CUDA device here, so its load may fail"
        return {"device": "cuda", "gpu_free_mib": free, "line": gpu + " (--device cuda)" + tail}
    if "cuda" not in seen:
        why = "the engines see no CUDA device"
    elif free is None:
        why = "no GPU card read for this machine"
    elif free < need:
        why = f"the GPU has {free:,} MiB free, it needs {need:,} there"
    else:
        return {"device": "cuda", "gpu_free_mib": free, "line": gpu + " (auto)"}
    return {"device": "cpu", "gpu_free_mib": free, "line": f"{cpu} (auto: {why})"}
