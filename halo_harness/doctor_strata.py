"""halo_harness.doctor_strata -- Halo 3.3.9.2: `halo doctor --local`'s Strata lines, when the runtime is configured (a
`strata` entry or server in huggingface.local_servers / the roster, or `huggingface.strata_bin` set): `strata --version`
(strata/requirements.py) and `strata launch --status` (strata/control.status_rows: what it serves now), each OK or a
WARN with the one install line for this OS. Two short local commands, never a model, never the network.

    configured(state_dir=None) -> bool
    st_steps(state_dir=None, *, force=False) -> [{step, ok, reason, elapsed_s, tag?}]   [] when not configured
"""

from __future__ import annotations


def configured(state_dir=None) -> bool:
    from halo_harness.theme import get_config_value
    if get_config_value("huggingface.strata_bin", default=None):
        return True
    try:
        from halo_harness.ollama_steward.servers_hf import roster
        return any(s.runtime == "strata" for s in roster(state_dir))
    except Exception:
        return False


def st_steps(state_dir=None, *, force: bool = False) -> list:
    if not (force or configured(state_dir)):
        return []
    from halo_harness.doctor_local_ids import _step
    from halo_harness.strata.control import status_rows
    from halo_harness.strata.requirements import check
    c = check()
    if not c["ok"]:
        return [_step("strata", True, c["line"], "WARN")]
    out = [_step("strata", True, f"strata --version: {c['version']} ({c['strata_from']})")]
    rows = status_rows(c["strata"])
    if rows is None:
        out.append(_step("strata launch", True, "strata launch --status --output json did not answer (an older "
                         "Terminal: strata update)", "WARN"))
    elif not rows:
        out.append(_step("strata launch", True, "strata launch --status: nothing from strata launch is serving"))
    else:
        out.append(_step("strata launch", True, "strata launch --status: " + "; ".join(
            f"{r.get('name')} {r.get('state')} at {r.get('url')}" for r in rows[:4])))
    return out
