"""halo_harness.doctor_tensorfold -- Halo 3.3.9.3: `halo doctor --local`'s TensorFold lines, when the runtime is
configured (a `tensorfold` entry or server in huggingface.local_servers / the roster, or `huggingface.tensorfold_bin`
set): `tensorfold --version` and `tensorfold capabilities --json` (tensorfold/requirements.py: the backends this binary
has, Metal or CUDA, and its engine version), each OK or a WARN with the one install line for this OS (Homebrew on the
Mac, the release archive on Linux, the native build guide on Windows). Two short local commands, never a model, never
the network.

    configured(state_dir=None) -> bool
    tf_steps(state_dir=None, *, force=False) -> [{step, ok, reason, elapsed_s, tag?}]   [] when not configured
"""

from __future__ import annotations


def configured(state_dir=None) -> bool:
    from halo_harness.theme import get_config_value
    if get_config_value("huggingface.tensorfold_bin", default=None):
        return True
    try:
        from halo_harness.ollama_steward.servers_hf import roster
        return any(s.runtime == "tensorfold" for s in roster(state_dir))
    except Exception:
        return False


def tf_steps(state_dir=None, *, force: bool = False) -> list:
    if not (force or configured(state_dir)):
        return []
    from halo_harness.doctor_local_ids import _step
    from halo_harness.tensorfold.requirements import check
    c = check(state_dir)
    if not c["ok"]:
        return [_step("tensorfold", True, c["line"], "WARN")]
    out = [_step("tensorfold", True, f"tensorfold --version: {c['version']} ({c['tensorfold_from']})")]
    caps = c.get("capabilities")
    if caps is None:
        out.append(_step("tensorfold capabilities", True, "tensorfold capabilities --json did not answer (an older "
                         "binary: upgrade it through its package manager, or fetch a newer archive)", "WARN"))
        return out
    backends = c["backends"]
    want = "metal" if c["os"] == "macos" else "cuda"
    fams = len(caps.get("families") or {})
    line = (f"tensorfold capabilities --json: backends {', '.join(backends) or 'none'}, engine {caps.get('engine')} "
            f"{caps.get('version')}, {fams} model families" + (f", chip {caps['chip']}" if caps.get("chip") else ""))
    if backends and want not in backends:
        out.append(_step("tensorfold capabilities", True, line + f" -- this machine wants the {want} build", "WARN"))
    else:
        out.append(_step("tensorfold capabilities", True, line))
    return out
