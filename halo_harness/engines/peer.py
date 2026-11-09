"""halo_harness.engines.peer -- an engine's server answers like a host: to a paired peer through one generic offer,
and to placement as one more option.

    offer(home) -> {engine id: {name, url, model, runtime, lan, api_key}}   the host side (host/routes_view.catalog's
        `engines`): each engine entry Halo wrote in THAT home's config.json and bound to the LAN (a loopback-only server
        is not reachable from a peer, so it is not offered)
    remote_entry(name, home=None) -> HFLocalServer | None   the peer side: `hf:local/<model>@<id>` or `@<host>` (the
        host's own name; the table's order picks among a host's engines) through a paired host's catalog, its url on
        the host's LAN address (cached CACHE_S); providers/huggingface.resolve_huggingface_local_server falls back to it
    EngineHost(name, url, model, local, engine)   the pseudo-host local_sched/place.solve scores
    hosts(state_dir=None) -> [EngineHost]   this machine's server of each engine and each paired host's (its join's /
        announce's `servers` rows), named by the host's own name ("<host>/<id>" for a host's second engine)
    route(host, need, *, state_dir=None) -> {host, via, fits, now, warm, evicts, load_s, installed, capable, need_bytes,
        usable_bytes, verdict, engine_tax}   warm for the model it serves; another model the engine names: a restart
        with the loading tax (its GB over the disk's speed, the download said); any other model: out
An unpaired machine gets nothing: the host answers only signed requests from its peers. Reads only.
"""

from __future__ import annotations

import json
import os
import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from halo_harness.engines.descriptors import TABLE, get

CACHE_S = 30.0
_CACHE: dict = {}
GIB = 2 ** 30


def offer(home) -> dict:
    from halo_harness.engines.adapter import key, key_env, ours
    try:
        cfg = json.loads((Path(home) / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    rows = ((cfg.get("huggingface") or {}).get("local_servers") or []) if isinstance(cfg, dict) else []
    out = {}
    for engine in TABLE:
        e = next((r for r in rows if isinstance(r, dict) and ours(r, engine)), None)
        if e is not None and e.get("lan"):
            out[engine] = {"name": engine, "url": e.get("url"), "model": e.get("model"), "runtime": engine, "lan": True,
                           "api_key": os.environ.get(str(e.get("api_key_env") or key_env(engine))) or key(engine)}
    return out


def _on(addr: str, url: str, engine: str) -> str:
    u = urllib.parse.urlparse(str(url or ""))
    host = f"[{addr}]" if ":" in addr and not addr.startswith("[") else addr
    return u._replace(netloc=f"{host}:{u.port or get(engine)['default_port']}").geturl()


def _ask(name: str, home=None) -> Optional[dict]:
    try:
        from halo_harness.fleet import identity, store
        from halo_harness.ollama_steward.host_client import HostClient, HostError
        hosts = [e for e in store.hosts(home) if e.get("state", "joined") == "joined"]
    except Exception:
        return None
    for e in hosts:
        if name not in TABLE and name != str(e.get("name") or "").lower():
            continue
        key = store.key_for(e, home)
        if key is None:
            continue
        try:
            cat = HostClient(e, key, identity.harness()["id"]).catalog(4096)
        except HostError:
            continue
        offers = {**{k: cat.get(k) for k in TABLE if isinstance(cat.get(k), dict)}, **(cat.get("engines") or {})}
        pick = next((offers[k] for k in TABLE if isinstance(offers.get(k), dict) and offers[k].get("url")
                     and name in (k, str(e.get("name") or "").lower())), None)
        if pick is not None:
            addr = urllib.parse.urlparse(str(e.get("url") or "")).hostname or ""
            rt = str(pick.get("runtime") or name)
            return {**pick, "url": _on(addr, pick["url"], rt) if addr and get(rt) else pick["url"], "via": e.get("name")}
    return None


def remote_entry(name: str, home=None):
    from halo_harness.providers.huggingface import HFLocalServer
    k = str(name or "").lower()
    hit = _CACHE.get(k)
    if hit and time.monotonic() - hit[0] < CACHE_S:
        got = hit[1]
    else:
        got = _ask(k, home)
        _CACHE[k] = (time.monotonic(), got)
    if not got or not got.get("url"):
        return None
    return HFLocalServer(name=str(name), url=str(got["url"]), api_key=got.get("api_key") or None,
                         runtime=str(got.get("runtime") or k))


def reset() -> None:
    _CACHE.clear()


@dataclass(frozen=True)
class EngineHost:
    name: str
    url: str = ""
    model: Optional[str] = None
    local: bool = True
    engine: str = ""
    max_ctx: Optional[int] = None


def hosts(state_dir=None) -> list:
    out: list = []
    try:
        from halo_harness.ollama_steward.servers_hf import roster
        mine = roster(state_dir)
    except Exception:
        mine = []
    for engine in TABLE:
        rows = sorted((s for s in mine if s.runtime == engine), key=lambda s: s.source == "auto")
        if rows:
            out.append(EngineHost(name=rows[0].name, url=rows[0].url, model=rows[0].model, engine=engine))
    try:
        from halo_harness.fleet import store
        peers = [e for e in store.hosts() if e.get("state", "joined") == "joined"]
    except Exception:
        peers = []
    for e in peers:
        seen = 0
        for engine in TABLE:
            for r in e.get("servers") or []:
                if isinstance(r, dict) and r.get("runtime") == engine and r.get("addr") and r.get("port"):
                    name = str(e.get("name") or r.get("addr")) + (f"/{engine}" if seen else "")
                    seen += 1
                    if not any(h.name.lower() == name.lower() for h in out):
                        out.append(EngineHost(name=name, url=f"http://{r['addr']}:{int(r['port'])}/v1",
                                              model=r.get("model"), local=False, engine=engine))
    return out


def _norm(m) -> str:
    return str(m or "").lower().removeprefix("hf:local/").split("@", 1)[0]


def route(host: EngineHost, need: dict, *, state_dir=None) -> dict:
    from halo_harness.engines.models import match
    d, want, served = get(host.engine), _norm(need.get("model")), _norm(host.model)
    out = {"host": host.name, "via": host.engine, "fits": None, "now": False, "warm": False, "evicts": [], "load_s": None,
           "installed": None, "capable": True, "need_bytes": None, "usable_bytes": None, "verdict": "", "engine_tax": ""}
    if served and (want == served or want in served or served in want or
                   want.rsplit("/", 1)[-1] == served.rsplit("/", 1)[-1]):
        return {**out, "fits": True, "now": True, "warm": True, "installed": True, "load_s": 0.0,
                "engine_tax": "warm: no load", "verdict": f"{d['label']} serves {host.model} on {host.name}"}
    row = match(host.engine, want)
    if row is None:
        return {**out, "fits": False, "verdict": f"{d['label']} serves the models its docs name (docs/MODELS-engines.md), "
                                                 f"not {need.get('model')}"}
    gb = row.get("ram_gb") or row.get("size_gb")
    load = round(gb * GIB / d["fit"]["disk_bps"], 1) if gb else None
    tax = (f"a restart onto {row['name']}" + (f", ~{load:.0f} s reading it from disk" if load else "")
           + (f", the download ({row['size_gb']:.0f} GB) if it is not there (yours to run)" if row.get("size_gb") else "")
           + (", the first request's kernel compile on a first install" if d.get("first_wait_s") else "")
           + (f", evicts {host.model}" if host.model else ""))
    out.update(load_s=load, engine_tax=tax, evicts=[host.model] if host.model else [],
               need_bytes=int(row["size_gb"] * GIB) if row.get("size_gb") else None,
               verdict=f"{row['name']} would replace {host.model or 'nothing'} on {host.name}'s {d['label']} server")
    if host.local:
        from halo_harness.engines.adapter import facts
        from halo_harness.engines.fit import fit, host_for
        from halo_harness.providers.local_server_cmd import this_machine_card
        card, _name = this_machine_card()
        got = fit(host.engine, row, host_for(host.name, card, facts=facts()), window=need.get("window"))
        out["fits"] = {"fits": True, "tight": True, "no": False}.get(got["level"])
        out["verdict"] = got["line"]
    return out
