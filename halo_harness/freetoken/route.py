"""halo_harness.freetoken.route -- a FreeToken server answers `route` like a host (Halo 3.3.9.1; docs/MODELS-
freetoken.md "In placement"; local_sched/place.py asks it beside the Ollama hosts and the pool).

    FtHost(name, url, model, local, freetoken=True)   the pseudo-host place.solve scores
    ft_hosts(state_dir=None) -> [FtHost]   this machine's `freetoken` entry (Halo's or one named runtime freetoken) and
        each paired host's FreeToken server (its join's / announce's `servers` rows of runtime freetoken), named by the
        host's own name ("samus")
    route(host, need, *, state_dir=None) -> {host, via: "freetoken", fits, now, warm, evicts, load_s, installed,
        capable, need_bytes, usable_bytes, verdict, ft_tax}
        the model it serves: warm, nothing to load; another checkpoint FreeToken names: a restart onto it, the loading
        tax said -- its expert banks read from disk (the checkpoint's size over DISK_BPS) and, on a first install, the
        kernel JIT (minutes); a dense or unknown model: out ("FreeToken serves Mixture-of-Experts checkpoints")
Reads only: nothing restarts a server; FreeToken serves one model at a time.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

DISK_BPS = 1.5e9  # local_pool/route's figure for a load from disk
JIT_WORDS = "the kernel JIT on a first install (minutes, once)"


@dataclass(frozen=True)
class FtHost:
    name: str
    url: str = ""
    model: Optional[str] = None
    local: bool = True
    freetoken: bool = True
    max_ctx: Optional[int] = None


def _norm(m) -> str:
    return str(m or "").lower().removeprefix("hf:local/").split("@", 1)[0]


def ft_hosts(state_dir=None) -> list:
    out = []
    try:
        from halo_harness.ollama_steward.servers_hf import roster
        rows = sorted((s for s in roster(state_dir) if s.runtime == "freetoken"), key=lambda s: s.source == "auto")
        if rows:
            out.append(FtHost(name=rows[0].name, url=rows[0].url, model=rows[0].model, local=True))
    except Exception:
        pass
    try:
        from halo_harness.fleet import store
        entries = [e for e in store.hosts() if e.get("state", "joined") == "joined"]
    except Exception:
        entries = []
    for e in entries:
        for r in e.get("servers") or []:
            if isinstance(r, dict) and r.get("runtime") == "freetoken" and r.get("addr") and r.get("port"):
                name = str(e.get("name") or r.get("addr"))
                if not any(h.name.lower() == name.lower() for h in out):
                    out.append(FtHost(name=name, url=f"http://{r['addr']}:{int(r['port'])}/v1", model=r.get("model"),
                                      local=False))
    return out


def route(host: FtHost, need: dict, *, state_dir=None) -> dict:
    from halo_harness.freetoken.catalog import match, size_bytes
    want = _norm(need.get("model"))
    out = {"host": host.name, "via": "freetoken", "fits": None, "now": False, "warm": False, "evicts": [], "load_s": None,
           "installed": None, "capable": True, "need_bytes": None, "usable_bytes": None, "verdict": "", "ft_tax": ""}
    served = _norm(host.model)
    if served and (want == served or want in served or served in want):
        return {**out, "fits": True, "now": True, "warm": True, "installed": True, "load_s": 0.0, "ft_tax": "warm: no load",
                "verdict": f"FreeToken serves {host.model} on {host.name}"}
    row = match(want)
    if row is None:
        return {**out, "fits": False, "verdict": f"FreeToken serves Mixture-of-Experts checkpoints (halo models search "
                                                 f"freetoken), not {need.get('model')}"}
    size = size_bytes(row)
    load = round(size / DISK_BPS, 1) if size else None
    tax = (f"a restart onto {row['name']}" + (f", ~{load:.0f} s reading its experts from disk" if load else "")
           + f", {JIT_WORDS}" + (f", evicts {host.model}" if host.model else ""))
    out.update(load_s=load, ft_tax=tax, evicts=[host.model] if host.model else [],
               verdict=f"{row['name']} would replace {host.model or 'nothing'} on {host.name}'s FreeToken server")
    if host.local:
        from halo_harness.local_sched.fit_ft import fit, host_from_card
        from halo_harness.freetoken.requirements import platform_facts
        from halo_harness.freetoken.shape import of_row
        from halo_harness.providers.local_server_cmd import this_machine_card
        card, _name = this_machine_card()
        got = fit(of_row(row), host_from_card(host.name, card, facts=platform_facts()), state_dir=state_dir)
        out["fits"] = {"fits": True, "tight": True, "no": False}.get(got["level"])
        out["verdict"] = got["line"]
    return out
