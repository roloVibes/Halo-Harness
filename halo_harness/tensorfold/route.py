"""halo_harness.tensorfold.route -- a TensorFold server answers `route` like a host (Halo 3.3.9.3; docs/MODELS-
tensorfold.md "In placement"; local_sched/place.py asks it beside the Ollama hosts, the pool, FreeToken and Strata --
strata/route.py's shape). The Mac's TensorFold server is the case it is for: placement and the adviser see it beside
the Mac's mlx_lm.server and Ollama.

    TfHost(name, url, model, local, tensorfold=True)   the pseudo-host place.solve scores
    tf_hosts(state_dir=None) -> [TfHost]   this machine's TensorFold server (the roster's runtime tensorfold: Halo's or
        one the auto-detect named) and each paired host's (its join's / announce's `servers` rows of runtime
        tensorfold), named by the host's own name ("mac"; "mac/tensorfold" when FreeToken or Strata there has the name)
    route(host, need, *, state_dir=None) -> {host, via: "tensorfold", fits, now, warm, evicts, load_s, installed,
        capable, need_bytes, usable_bytes, verdict, tf_tax}
        the model it serves: warm, nothing to load; another model TensorFold's table names: a restart onto it with
        the loading tax said -- the checkpoint read into memory (its GB over DISK_BPS: minutes for a big one) and the
        `tensorfold pull` when it is not on that machine (its GB, the user's to run); any other model: out
Reads only: nothing restarts a server; TensorFold serves one model per port.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

DISK_BPS = 1.5e9  # local_pool/route's figure for a load from disk (freetoken/route.DISK_BPS, strata/route.DISK_BPS)


@dataclass(frozen=True)
class TfHost:
    name: str
    url: str = ""
    model: Optional[str] = None
    local: bool = True
    tensorfold: bool = True
    max_ctx: Optional[int] = None


def _norm(m) -> str:
    return str(m or "").lower().removeprefix("hf:local/").split("@", 1)[0].rsplit("/", 1)[-1]


def tf_hosts(state_dir=None) -> list:
    out = []
    try:
        from halo_harness.ollama_steward.servers_hf import roster
        rows = sorted((s for s in roster(state_dir) if s.runtime == "tensorfold"), key=lambda s: s.source == "auto")
        if rows:
            out.append(TfHost(name=rows[0].name, url=rows[0].url, model=rows[0].model, local=True))
    except Exception:
        pass
    try:
        from halo_harness.fleet import store
        entries = [e for e in store.hosts() if e.get("state", "joined") == "joined"]
    except Exception:
        entries = []
    for e in entries:
        other = any(isinstance(r, dict) and r.get("runtime") in ("freetoken", "strata") for r in e.get("servers") or [])
        for r in e.get("servers") or []:
            if isinstance(r, dict) and r.get("runtime") == "tensorfold" and r.get("addr") and r.get("port"):
                name = str(e.get("name") or r.get("addr")) + ("/tensorfold" if other else "")
                if not any(h.name.lower() == name.lower() for h in out):
                    out.append(TfHost(name=name, url=f"http://{r['addr']}:{int(r['port'])}/v1", model=r.get("model"),
                                      local=False))
    return out


def route(host: TfHost, need: dict, *, state_dir=None) -> dict:
    from halo_harness.tensorfold.catalog import match
    want = _norm(need.get("model"))
    out = {"host": host.name, "via": "tensorfold", "fits": None, "now": False, "warm": False, "evicts": [],
           "load_s": None, "installed": None, "capable": True, "need_bytes": None, "usable_bytes": None, "verdict": "",
           "tf_tax": ""}
    served = _norm(host.model)
    if served and want == served:
        return {**out, "fits": True, "now": True, "warm": True, "installed": True, "load_s": 0.0,
                "tf_tax": "warm: no load", "verdict": f"TensorFold serves {host.model} on {host.name}"}
    row = match(need.get("model"))
    if row is None:
        return {**out, "fits": False, "verdict": f"TensorFold serves the models its table names (halo models browse "
                                                 f"--source hf tensorfold), not {need.get('model')}"}
    load = round(row["size_bytes"] / DISK_BPS, 1) if row.get("size_bytes") else None
    pull = f", the {row['size_words']} `tensorfold pull` if it is not there (yours to run)" if row.get("size_words") else (
        ", its `tensorfold pull` if it is not there (yours to run)")
    tax = (f"a restart onto {row['title']}" + (f", ~{load:.0f} s reading the checkpoint into memory" if load else "")
           + pull + (f", evicts {host.model}" if host.model else ""))
    out.update(load_s=load, tf_tax=tax, evicts=[host.model] if host.model else [], need_bytes=row.get("size_bytes"),
               verdict=f"{row['title']} would replace {host.model or 'nothing'} on {host.name}'s TensorFold server")
    if host.local:
        from halo_harness.local_sched.fit_tf import fit, host_for
        from halo_harness.providers.local_server_cmd import this_machine_card
        from halo_harness.tensorfold.requirements import os_word
        card, _name = this_machine_card()
        got = fit(row, host_for(host.name, card, os_name=os_word()), window=need.get("window"))
        out["fits"] = {"fits": True, "tight": True, "no": False}.get(got["level"])
        out["verdict"] = got["line"]
    return out
