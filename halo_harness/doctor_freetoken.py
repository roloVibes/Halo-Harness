"""halo_harness.doctor_freetoken -- Halo 3.3.9.1: `halo doctor --local`'s FreeToken lines, when the runtime is configured
(a `freetoken` entry or server in huggingface.local_servers / the roster, or `huggingface.freetoken_bin` set): the
platform, `ft --version`, the NVIDIA driver (r580+, CUDA 13) and `nvcc` on PATH (freetoken/requirements.py), each OK
or a WARN with the one install line; under WSL2 the pinned-memory caveat. Nothing else runs: three short local
commands, never a model, never the network.

    configured(state_dir=None) -> bool
    ft_steps(state_dir=None, *, force=False) -> [{step, ok, reason, elapsed_s, tag?}]   [] when not configured
"""

from __future__ import annotations


def configured(state_dir=None) -> bool:
    from halo_harness.theme import get_config_value
    if get_config_value("huggingface.freetoken_bin", default=None):
        return True
    try:
        from halo_harness.ollama_steward.servers_hf import roster
        return any(s.runtime == "freetoken" for s in roster(state_dir))
    except Exception:
        return False


def ft_steps(state_dir=None, *, force: bool = False) -> list:
    if not (force or configured(state_dir)):
        return []
    from halo_harness.doctor_local_ids import _step
    from halo_harness.freetoken import CUDA_LINE, DRIVER_LINE, INSTALL_LINE, WSL_CAVEAT
    from halo_harness.freetoken.requirements import check
    c = check()
    f = c["facts"]
    out = []
    plat = f["linux"] and f["x86"]
    out.append(_step("freetoken platform", True, f"FreeToken platform: {f['os']} {f['arch']}"
                     + (" (WSL2)" if f.get("wsl") else "") if plat else
                     f"FreeToken runs on Linux x86_64; this machine is {f['os']} {f['arch']} (on Windows: WSL2 with "
                     "Ubuntu)", "" if plat else "WARN"))
    if c["ft"] and c["ft_version"]:
        out.append(_step("freetoken ft", True, f"ft --version: {c['ft_version']} ({c['ft_from']})"))
    else:
        out.append(_step("freetoken ft", True, ("ft did not answer --version" if c["ft"] else "ft is not on PATH")
                         + f": {INSTALL_LINE}", "WARN"))
    out.append(_step("freetoken driver", True, f"NVIDIA driver {c['driver']} (r580+, CUDA 13)" if c["driver_ok"] else
                     f"NVIDIA driver {c['driver'] or 'not found'}: FreeToken needs {DRIVER_LINE}",
                     "" if c["driver_ok"] else "WARN"))
    out.append(_step("freetoken nvcc", True, f"nvcc: CUDA {c['nvcc']} (kernels compile on first use)" if c["nvcc_ok"] else
                     f"nvcc {('CUDA ' + c['nvcc']) if c['nvcc'] else 'not on PATH'}: FreeToken compiles its kernels "
                     f"with it -- {CUDA_LINE}", "" if c["nvcc_ok"] else "WARN"))
    if f.get("wsl"):
        out.append(_step("freetoken wsl", True, f"WSL2: {WSL_CAVEAT}", "WARN"))
    return out
