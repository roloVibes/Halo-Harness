"""halo_harness.strata.route -- a Strata server answers `route` like a host (Halo 3.3.9.2; docs/MODELS-strata.md "In
placement"; local_sched/place.py asks it beside the Ollama hosts, the pool and FreeToken -- freetoken/route.py's shape).

    StHost(name, url, model, local, strata=True)   the pseudo-host place.solve scores
    st_hosts(state_dir=None) -> [StHost]   this machine's Strata server (the roster's runtime strata: Halo's or one the
        auto-detect named) and each paired host's (its join's / announce's `servers` rows of runtime strata), named by
        the host's own name ("pc"; "pc/strata" when a FreeToken server there has the name)
    route(host, need, *, state_dir=None) -> {host, via: "strata", fits, now, warm, evicts, load_s, installed, capable,
        need_bytes, usable_bytes, verdict, st_tax}
        the set it serves: warm, nothing to load; another set Strata names: a restart onto it with the loading tax said
        -- its experts read into RAM (their GB over DISK_BPS) and, when the set is not on that machine, the first
        launch's download (its GB, the user's to run); any other model: out ("Strata serves the sets it names")
Reads only: nothing restarts a server; Strata serves one model per port.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

DISK_BPS = 1.5e9  # local_pool/route's figure for a load from disk (freetoken/route.DISK_BPS)


@dataclass(frozen=True)
class StHost:
    name: str
    url: str = ""
    model: Optional[str] = None
    local: bool = True
    strata: bool = True
    max_ctx: Optional[int] = None


def _norm(m) -> str:
    return str(m or "").lower().removeprefix("hf:local/").split("@", 1)[0]


def st_hosts(state_dir=None) -> list:
    out = []
    try:
        from halo_harness.ollama_steward.servers_hf import roster
        rows = sorted((s for s in roster(state_dir) if s.runtime == "strata"), key=lambda s: s.source == "auto")
        if rows:
            out.append(StHost(name=rows[0].name, url=rows[0].url, model=rows[0].model, local=True))
    except Exception:
        pass
    try:
        from halo_harness.fleet import store
        entries = [e for e in store.hosts() if e.get("state", "joined") == "joined"]
    except Exception:
        entries = []
    for e in entries:
        ft = any(isinstance(r, dict) and r.get("runtime") == "freetoken" for r in e.get("servers") or [])
        for r in e.get("servers") or []:
            if isinstance(r, dict) and r.get("runtime") == "strata" and r.get("addr") and r.get("port"):
                name = str(e.get("name") or r.get("addr")) + ("/strata" if ft else "")
                if not any(h.name.lower() == name.lower() for h in out):
                    out.append(StHost(name=name, url=f"http://{r['addr']}:{int(r['port'])}/v1", model=r.get("model"),
                                      local=False))
    return out


def route(host: StHost, need: dict, *, state_dir=None) -> dict:
    from halo_harness.strata.catalog import match
    want = _norm(need.get("model"))
    out = {"host": host.name, "via": "strata", "fits": None, "now": False, "warm": False, "evicts": [], "load_s": None,
           "installed": None, "capable": True, "need_bytes": None, "usable_bytes": None, "verdict": "", "st_tax": ""}
    served = _norm(host.model)
    if served and (want == served or want in served or served in want):
        return {**out, "fits": True, "now": True, "warm": True, "installed": True, "load_s": 0.0, "st_tax": "warm: no load",
                "verdict": f"Strata serves {host.model} on {host.name}"}
    row = match(want)
    if row is None:
        return {**out, "fits": False, "verdict": f"Strata serves the sets it names (`strata models list`; docs/MODELS-strata.md), not "
                                                 f"{need.get('model')}"}
    load = round(row["experts_gb"] * 1e9 / DISK_BPS, 1) if row.get("experts_gb") else None
    dl = f", the first launch's {row['download_gb']:g} GB download if the set is not there (yours to run)" if row.get(
        "download_gb") else ""
    tax = (f"a restart onto {row['model']} {row['set']}" + (f", ~{load:.0f} s reading its experts into RAM" if load else "")
           + dl + (f", evicts {host.model}" if host.model else ""))
    out.update(load_s=load, st_tax=tax, evicts=[host.model] if host.model else [],
               verdict=f"{row['model']} {row['set']} would replace {host.model or 'nothing'} on {host.name}'s Strata "
                       "server")
    if host.local:
        from halo_harness.local_sched.fit_st import fit, host_for
        from halo_harness.providers.local_server_cmd import this_machine_card
        from halo_harness.strata.requirements import os_word
        card, _name = this_machine_card()
        got = fit(row, host_for(host.name, card, os_name=os_word()))
        out["fits"] = {"fits": True, "tight": True, "no": False}.get(got["level"])
        out["verdict"] = got["line"]
    return out
