"""halo_harness.ollama_steward.resources_readers -- Halo 3.3.5.0 R1: what the
Local tab's live strip reads once a second, each reader read-only, stdlib only.

    gpu(seams)      {gpu, vram_used, vram_total, temp, cards, source} | None, why
                    nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,
                    temperature.gpu (Linux, Windows); rocm-smi --json (Linux, Windows);
                    on a Mac `ioreg -r -d 1 -w 0 -c IOAccelerator` (the GPU's
                    PerformanceStatistics: memory in use, the utilization when it is
                    there) over `sysctl -n hw.memsize` (unified memory); GPU use is None
                    ("n/a") on a Mac whose registry does not say it and whose
                    `powermetrics` is not readable without sudo
    apps(seams)     nvidia-smi --query-compute-apps -> [{pid, name, bytes}] (bytes None
                    under Windows WDDM, every process [N/A])
    (the RAM and CPU readers are resources_system.py)

`Seams(runner, read_file, platform, win)` are what the tests replace: `runner(argv,
timeout) -> stdout | None` (providers/ollama_hw._run_tool's seam), `read_file(path) ->
text | None`, `win` = {"mem": fn() -> (used, total), "times": fn() -> (idle, kernel,
user)}. Nothing runs under BRIDGE_TEST_NO_BACKGROUND_NET unless a seam is given.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from typing import Callable, Optional

TIMEOUT_S = 3.0
MIB = 2 ** 20
NVIDIA_QUERY = ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu",
                "--format=csv,noheader,nounits"]
NVIDIA_APPS = ["nvidia-smi", "--query-compute-apps=pid,process_name,used_gpu_memory", "--format=csv,noheader,nounits"]
ROCM_QUERY = ["rocm-smi", "--showuse", "--showmeminfo", "vram", "--showtemp", "--json"]
IOREG_QUERY = ["ioreg", "-r", "-d", "1", "-w", "0", "-c", "IOAccelerator"]


@dataclass
class Seams:
    runner: Optional[Callable] = None
    read_file: Optional[Callable] = None
    platform: str = field(default_factory=lambda: sys.platform)
    win: Optional[dict] = None
    injected: bool = False


def default_seams() -> Seams:
    from halo_harness.providers.ollama_hw import _run_tool

    def runner(argv, timeout):
        return _run_tool(argv, timeout=timeout)

    def read_file(path):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        except OSError:
            return None
    return Seams(runner=runner, read_file=read_file, win=None)


def off(seams: Seams) -> bool:
    if seams.injected:
        return False
    from halo_harness.config.paths import background_net_disabled
    return background_net_disabled()


def _num(text) -> Optional[float]:
    try:
        return float(str(text).strip().strip("%").strip())
    except (TypeError, ValueError):
        return None


def parse_nvidia(text: str) -> Optional[dict]:
    """`0, 30, 23028, 28` per card (util %, MiB used, MiB total, deg C; `[N/A]` = unknown) -> the machine's reading."""
    cards = []
    for line in (text or "").splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 3:
            continue
        util, used, total = _num(parts[0]), _num(parts[1]), _num(parts[2])
        temp = _num(parts[3]) if len(parts) > 3 else None
        if used is None or total is None:
            continue
        cards.append((util, used, total, temp))
    if not cards:
        return None
    utils = [c[0] for c in cards if c[0] is not None]
    temps = [c[3] for c in cards if c[3] is not None]
    return {"gpu": round(sum(utils) / len(utils)) if utils else None, "vram_used": int(sum(c[1] for c in cards) * MIB),
            "vram_total": int(sum(c[2] for c in cards) * MIB), "temp": max(temps) if temps else None,
            "cards": len(cards), "source": "nvidia-smi --query-gpu"}


def parse_rocm(text: str) -> Optional[dict]:
    """`rocm-smi --showuse --showmeminfo vram --showtemp --json` -> the machine's reading (every card summed)."""
    try:
        data = json.loads(text or "")
    except ValueError:
        return None
    cards = [v for k, v in (data.items() if isinstance(data, dict) else []) if str(k).startswith("card") and isinstance(v, dict)]
    rows = []
    for c in cards:
        pick = lambda word: next((_num(v) for k, v in c.items() if word in k.lower()), None)  # noqa: E731
        used, total = pick("vram total used memory"), pick("vram total memory")
        if used is None or total is None:
            continue
        rows.append((pick("gpu use"), used, total, pick("temperature")))
    if not rows:
        return None
    utils = [r[0] for r in rows if r[0] is not None]
    temps = [r[3] for r in rows if r[3] is not None]
    return {"gpu": round(sum(utils) / len(utils)) if utils else None, "vram_used": int(sum(r[1] for r in rows)),
            "vram_total": int(sum(r[2] for r in rows)), "temp": max(temps) if temps else None, "cards": len(rows),
            "source": "rocm-smi --json"}


def parse_ioreg(text: str) -> dict:
    """The Apple GPU's PerformanceStatistics: {in_use (bytes), util (%)} (either None when absent)."""
    used = re.search(r'"In use system memory"\s*=\s*(\d+)', text or "")
    util = re.search(r'"Device Utilization %"\s*=\s*(\d+)', text or "")
    return {"in_use": int(used.group(1)) if used else None, "util": int(util.group(1)) if util else None}


def _mac_total(seams: Seams) -> Optional[int]:
    out = seams.runner(["sysctl", "-n", "hw.memsize"], TIMEOUT_S) if seams.runner else None
    n = _num(out)
    return int(n) if n and n > 0 else None


_POWERMETRICS: dict = {}


def _mac_gpu(seams: Seams):
    total = _mac_total(seams)
    reg = parse_ioreg(seams.runner(IOREG_QUERY, TIMEOUT_S) or "") if seams.runner else {"in_use": None, "util": None}
    if total is None and reg["in_use"] is None:
        return None, "no ioreg or sysctl answer"
    util, src = reg["util"], "ioreg IOAccelerator"
    if util is None and _POWERMETRICS.get("ok") is not False and seams.runner:
        out = seams.runner(["powermetrics", "--samplers", "gpu_power", "-i", "200", "-n", "1"], TIMEOUT_S)
        m = re.search(r"GPU (?:HW )?active residency:\s*(\d+(?:\.\d+)?)%", out or "")
        _POWERMETRICS["ok"] = bool(m)
        util = round(float(m.group(1))) if m else None
        src = "powermetrics" if m else src
    return {"gpu": util, "vram_used": reg["in_use"], "vram_total": total, "temp": None, "cards": 1, "unified": True,
            "source": f"{src} over sysctl hw.memsize (unified memory)", "gpu_na": util is None}, None


def gpu(seams: Seams):
    """The machine's GPU reading, or (None, why)."""
    if off(seams):
        return None, "background reads are off"
    if seams.platform.startswith("darwin"):
        return _mac_gpu(seams)
    found = parse_nvidia(seams.runner(NVIDIA_QUERY, TIMEOUT_S) or "") if seams.runner else None
    if found is not None:
        return found, None
    found = parse_rocm(seams.runner(ROCM_QUERY, TIMEOUT_S) or "") if seams.runner else None
    if found is not None:
        return found, None
    return None, "no nvidia-smi or rocm-smi answer"


def apps(seams: Seams):
    """The GPU's compute processes (nvidia-smi only), or (None, why)."""
    if off(seams) or seams.platform.startswith("darwin") or not seams.runner:
        return None, "no per-process GPU read here"
    out = seams.runner(NVIDIA_APPS, TIMEOUT_S)
    if out is None:
        return None, "no nvidia-smi --query-compute-apps answer"
    from halo_harness.ollama_steward.hardware_sources import parse_compute_apps
    return parse_compute_apps(out), None
