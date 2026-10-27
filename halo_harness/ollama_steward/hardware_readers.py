"""halo_harness.ollama_steward.hardware_readers -- Halo 3.3.4.0 R1: the
readers behind the hardware card, each optional and each read-only. Every
reader returns `(value, why_not)`: a value, or None and one short reason
the card prints as "not read: <reader> (<why>)".

- the server log: the local file (`%LOCALAPPDATA%\\Ollama\\server.log`,
  `~/.ollama/logs/server.log`), else journald on Linux
- `/api/version` and `/api/ps` through Halo's one Ollama client
  (`providers.ollama`, which goes through the network choke point)
- `nvidia-smi` and `system_profiler` / `sysctl` through `providers.
  ollama_hw._run_tool` (the subprocess seam every GPU probe uses), over
  `ollama_hw.run_via_ssh` for a remote host with an `ssh:` entry

A command never runs and the network is never read under
`BRIDGE_TEST_NO_BACKGROUND_NET` unless the caller injects its own seam,
the same rule `ollama_hw.get_local_gpu_memory` follows.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Callable, Optional

from halo_harness.ollama_steward import hardware_sources as hs

_LOG_CAP_BYTES = 64 * 2 ** 20
_TIMEOUT_S = 5.0
_NVIDIA_GPUS = ["nvidia-smi", "--query-gpu=index,name,memory.total,memory.free", "--format=csv,noheader,nounits"]
_NVIDIA_APPS = ["nvidia-smi", "--query-compute-apps=pid,process_name,used_gpu_memory", "--format=csv,noheader,nounits"]


def _off() -> bool:
    from halo_harness.config.paths import background_net_disabled
    return background_net_disabled()


def server_log_path(platform: Optional[str] = None) -> Path:
    """Where Ollama writes its log on this OS (knowledge/log-vocabulary.md);
    under BRIDGE_TEST_HOME the Windows path is taken under that home too."""
    from halo_harness.config.paths import home
    platform = platform or sys.platform
    if platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA")
        if "BRIDGE_TEST_HOME" in os.environ or not base:
            base = str(home() / "AppData" / "Local")
        return Path(base) / "Ollama" / "server.log"
    return home() / ".ollama" / "logs" / "server.log"


def _read_tail(path: Path) -> Optional[str]:
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - _LOG_CAP_BYTES))
            return f.read().decode("utf-8", "replace")
    except OSError:
        return None


def read_server_log(*, path: Optional[Path] = None, platform: Optional[str] = None,
                    runner: Optional[Callable] = None):
    """The newest startup block of the local server log, parsed."""
    platform = platform or sys.platform
    target = Path(path) if path is not None else server_log_path(platform)
    text = _read_tail(target) if target.exists() else None
    where = str(target)
    if text is None and path is None and platform.startswith("linux"):
        if runner is None and _off():
            return None, f"no file at {where}; journald not read (background reads are off)"
        from halo_harness.providers.ollama_hw import _run_tool
        text = _run_tool(["journalctl", "-u", "ollama", "--no-pager", "-o", "cat", "-n", "20000"],
                         timeout=_TIMEOUT_S, runner=runner)
        where = "journalctl -u ollama"
    if text is None:
        return None, f"no file at {where}"
    startup = hs.parse_startup(text)
    if startup is None:
        return None, f"no startup block in {where}"
    startup["where"] = where
    return startup, None


def read_api(host, *, api: Optional[Callable] = None):
    """`/api/version` and `/api/ps` -> ({"version", "loaded"}, why_not)."""
    if api is None:
        if _off():
            return None, "background reads are off"
        from halo_harness.providers.ollama import fetch_ps, probe_version

        def api(path):
            return probe_version(host) if path == "/api/version" else fetch_ps(host)
    version = api("/api/version")
    ps = api("/api/ps")
    if not isinstance(version, dict) and not isinstance(ps, dict):
        return None, "the server did not answer"
    return {"version": (version or {}).get("version") if isinstance(version, dict) else None,
            "loaded": hs.parse_ps(ps) if isinstance(ps, dict) else None}, None


def _ssh_runner(host, ssh_runner):
    target = getattr(host, "ssh", None)
    if not target:
        return None, "no ssh entry for this host"
    if ssh_runner is not None:
        return ssh_runner, None
    if _off():
        return None, "background reads are off"
    from halo_harness.providers.ollama_hw import run_via_ssh
    return run_via_ssh(target, timeout=_TIMEOUT_S), None


def read_nvidia(runner: Optional[Callable]):
    """`nvidia-smi` cards and compute apps -> ({"gpus", "apps"}, why_not)."""
    from halo_harness.providers.ollama_hw import _run_tool
    out = _run_tool(_NVIDIA_GPUS, timeout=_TIMEOUT_S, runner=runner)
    gpus = hs.parse_nvidia_gpus(out or "")
    if not gpus:
        return None, "no nvidia-smi answer"
    apps_out = _run_tool(_NVIDIA_APPS, timeout=_TIMEOUT_S, runner=runner)
    return {"gpus": gpus, "apps": hs.parse_compute_apps(apps_out) if apps_out else None}, None


def read_local_gpus(*, runner: Optional[Callable] = None, platform: Optional[str] = None):
    """(d): `nvidia-smi` where present; on a Mac `system_profiler` for the
    chip and `sysctl` for the memory (`ollama_hw.probe_apple_unified_memory`)."""
    if runner is None and _off():
        return None, "background reads are off"
    platform = platform or sys.platform
    found, why = read_nvidia(runner)
    if found is not None or not platform.startswith("darwin"):
        return found, (why if found is None else None)
    return read_apple(runner)


def read_apple(runner: Optional[Callable]):
    from halo_harness.providers.ollama_hw import _run_tool, probe_apple_unified_memory
    prof = hs.parse_system_profiler(_run_tool(["system_profiler", "SPDisplaysDataType"],
                                              timeout=_TIMEOUT_S, runner=runner) or "")
    mem = probe_apple_unified_memory(timeout=_TIMEOUT_S, runner=runner)
    if prof is None and mem is None:
        return None, "no system_profiler or sysctl answer"
    gpu = {"id": "0", "name": (prof or {}).get("name"), "library": "Metal",
           "total_bytes": mem.total_bytes if mem else None,
           "available_bytes": mem.free_bytes if mem else None,
           "estimated": bool(mem and mem.estimated)}
    return {"gpus": [gpu], "apps": None, "unified": True, "ram_bytes": mem.total_bytes if mem else None}, None


def read_remote_gpus(host, *, ssh_runner: Optional[Callable] = None):
    """(c): the same reads over `ollama_hw.run_via_ssh` for a remote host
    with `ssh:`; `ollama_hw.probe_remote_gpu_memory` for a non-NVIDIA card."""
    runner, why = _ssh_runner(host, ssh_runner)
    if runner is None:
        return None, why
    found, _why = read_nvidia(runner)
    if found is not None:
        return found, None
    from halo_harness.providers.ollama_hw import probe_remote_gpu_memory
    mem = probe_remote_gpu_memory(host.ssh, timeout=_TIMEOUT_S, runner=runner)
    if mem is None:
        return None, "the ssh read found no GPU"
    gpu = {"id": "0", "name": mem.name, "library": {"apple": "Metal", "amd": "ROCm"}.get(mem.vendor, mem.vendor),
           "total_bytes": mem.total_bytes, "available_bytes": mem.free_bytes, "estimated": mem.estimated}
    return {"gpus": [gpu], "apps": None, "unified": mem.vendor == "apple" or None}, None
